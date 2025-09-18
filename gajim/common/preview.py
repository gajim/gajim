# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import hashlib
import logging
import os
import re
from collections.abc import Callable
from concurrent.futures import Future
from dataclasses import dataclass
from dataclasses import field
from functools import partial
from pathlib import Path
from urllib.parse import ParseResult
from urllib.parse import urlparse

from gi.repository import GLib
from gi.repository import GObject

from gajim.common import app
from gajim.common import configpaths
from gajim.common import regex
from gajim.common.aes import AESKeyData
from gajim.common.const import MIME_TYPES
from gajim.common.enum import FTState
from gajim.common.helpers import determine_proxy
from gajim.common.helpers import load_file_async
from gajim.common.http_manager import HTTPTransferObject
from gajim.common.i18n import _
from gajim.common.multiprocess.http import CancelledError
from gajim.common.multiprocess.http import ContentTypeNotAllowed
from gajim.common.multiprocess.http import HTTPStatusError
from gajim.common.multiprocess.http import MaxContentLengthExceeded
from gajim.common.multiprocess.thumbnail import create_thumbnail
from gajim.common.multiprocess.video_thumbnail import (
    extract_video_thumbnail_and_properties,
)
from gajim.common.storage.archive import models as mod
from gajim.common.util.preview import filename_from_uri
from gajim.common.util.preview import get_image_paths
from gajim.common.util.preview import get_previewable_image_mime_types
from gajim.common.util.preview import get_previewable_mime_types
from gajim.common.util.preview import get_previewable_video_mime_types
from gajim.common.util.preview import guess_mime_type
from gajim.common.util.preview import parse_fragment
from gajim.common.util.preview import split_geo_uri

log = logging.getLogger('gajim.c.preview')

IRI_RX = re.compile(regex.IRI)

PREVIEWABLE_IMAGE_MIME_TYPES = get_previewable_image_mime_types()
PREVIEWABLE_VIDEO_MIME_TYPES = get_previewable_video_mime_types()
PREVIEWABLE_MIME_TYPES = get_previewable_mime_types()
mime_types = set(MIME_TYPES)
# Merge both: if it’s a previewable image, it should be allowed
ALLOWED_MIME_TYPES = mime_types.union(PREVIEWABLE_MIME_TYPES)


AudioSampleT = list[tuple[float, float]]


@dataclass
class AudioPreviewState:
    duration: float = 0.0
    position: float = 0.0
    is_eos: bool = False
    speed: float = 1.0
    is_timestamp_positive: bool = True
    samples: AudioSampleT = field(default_factory=list)
    is_audio_analyzed = False


class PreviewManager:
    def __init__(self) -> None:
        self._orig_dir = configpaths.get('DOWNLOADS')
        self._thumb_dir = configpaths.get('DOWNLOADS_THUMB')

        self._previews: dict[str, Preview] = {}

        # Holds active audio preview sessions
        # for resuming after switching chats
        self._audio_sessions: dict[int, AudioPreviewState] = {}

        # References a stop function for each audio preview, which allows us
        # to stop previews by preview_id, see stop_audio_except(preview_id)
        self._audio_stop_functions: dict[int, Callable[..., None]] = {}

        log.info('Supported mime types for preview')
        log.info(sorted(PREVIEWABLE_MIME_TYPES))

    def get_preview(self, preview_id: str) -> Preview | None:
        return self._previews.get(preview_id)

    def clear_previews(self) -> None:
        self._previews.clear()

    def get_audio_state(self,
                        preview_id: int
                        ) -> AudioPreviewState:

        state = self._audio_sessions.get(preview_id)
        if state is not None:
            return state
        self._audio_sessions[preview_id] = AudioPreviewState()
        return self._audio_sessions[preview_id]

    def register_audio_stop_func(self,
                                 preview_id: int,
                                 stop_func: Callable[..., None]
                                 ) -> None:

        self._audio_stop_functions[preview_id] = stop_func

    def unregister_audio_stop_func(self, preview_id: int) -> None:
        self._audio_stop_functions.pop(preview_id, None)

    def stop_audio_except(self, preview_id: int) -> None:
        # Stops playback of all audio previews except of for preview_id.
        # This makes sure that only one preview is played at the time.
        for id_, stop_func in self._audio_stop_functions.items():
            if id_ != preview_id:
                stop_func()

    @staticmethod
    def _accept_uri(urlparts: ParseResult,
                    uri: str,
                    oob_url: str | None
                    ) -> bool:

        # geo
        if urlparts.scheme == 'geo':
            return True

        if not urlparts.netloc:
            return False

        # aesgcm
        if urlparts.scheme == 'aesgcm':
            return True

        # http/https
        if urlparts.scheme in ('https', 'http'):
            if app.settings.get('preview_allow_all_images'):
                mime_type = guess_mime_type(uri)
                if mime_type not in MIME_TYPES:
                    log.info('%s not in allowed mime types', mime_type)
                    return False

                if mime_type == 'application/octet-stream' and uri != oob_url:  # noqa: SIM103
                    # guess_mime_type yields 'application/octet-stream' for
                    # paths without suffix. Check oob_url to make sure we
                    # display a preview for files sent via http upload.
                    return False
                return True

            if oob_url is None:
                log.info('No oob url for: %s', uri)
                return False

            if uri != oob_url:
                log.info('uri != oob url: %s != %s', uri, oob_url)
                return False
            return True

        log.info('Unsupported URI scheme: %s', uri)
        return False

    def is_previewable(self,
                       text: str,
                       oob_data: list[mod.OOB]
                       ) -> bool:


        if not IRI_RX.fullmatch(text):
            # urlparse removes whitespace (and who knows what else) from URLs,
            # so can't be used for validation.
            return False

        uri = text
        try:
            urlparts = urlparse(uri)
        except Exception:
            return False

        oob_url = None if not oob_data else oob_data[0].url
        if not self._accept_uri(urlparts, uri, oob_url):
            return False

        if urlparts.scheme == 'geo':
            try:
                split_geo_uri(uri)
            except Exception as err:
                log.info('Bad geo URI %s: %s', uri, err)
                return False

        return True

    def create_preview(self,
                       account: str,
                       uri: str,
                       from_us: bool,
                       context: str | None = None
                       ) -> Preview:

        preview_id = hashlib.sha256(uri.encode()).hexdigest()
        preview = self._previews.get(preview_id)
        if preview is not None:
            return preview

        if uri.startswith('geo:'):
            preview = Preview(preview_id, account, uri, None, None, None, 96)
            self._previews[preview_id] = preview
            return preview

        urlparts = urlparse(uri)
        size = app.settings.get('preview_size')
        orig_path, thumb_path = get_image_paths(uri,
                                                urlparts,
                                                size,
                                                self._orig_dir,
                                                self._thumb_dir)

        preview = Preview(
            preview_id,
            account,
            uri,
            urlparts,
            orig_path,
            thumb_path,
            size,
            from_us,
            context=context
        )

        self._previews[preview_id] = preview
        return preview


class Preview(GObject.Object):
    __gtype_name__ = "Preview"

    __gsignals__ = {
        "update": (GObject.SignalFlags.RUN_LAST, None, ()),
        "progress": (GObject.SignalFlags.RUN_LAST, None, (float,)),
    }

    def __init__(
        self,
        id_: str,
        account: str,
        uri: str,
        urlparts: ParseResult | None,
        orig_path: Path | None,
        thumb_path: Path | None,
        size: int,
        from_us: bool = False,
        context: str | None = None
    ) -> None:

        GObject.Object.__init__(self)
        self.id = id_
        self._uri = uri
        self._urlparts = urlparts
        self._filename = filename_from_uri(uri)
        self._from_us = from_us
        self._context = context

        self.account = account
        self.orig_path = orig_path
        self.thumb_path = thumb_path
        self.size = size * app.window.get_scale_factor()

        self.thumbnail: bytes | None = None
        self.mime_type: str = ''
        self.file_size: int = 0
        self.download_in_progress = False

        self.info_message: str | None = None

        self._http_obj = None

        self.key: bytes | None = None
        self.iv: bytes | None = None
        if self.is_aes_encrypted and urlparts is not None:
            try:
                self.key, self.iv = parse_fragment(urlparts.fragment)
            except ValueError as err:
                log.error('Parsing fragment for AES decryption '
                          'failed: %s', err)

        if not app.settings.get('enable_file_preview') or uri.startswith("geo:"):
            self.emit("update")
            return

        if not self.orig_exists:
            if context is not None and not from_us:
                allow_in_public = app.settings.get('preview_anonymous_muc')
                if context == 'public' and not allow_in_public:
                    self.emit("update")
                    return

            self._download_content()

        elif not self.thumb_exists:
            assert self.orig_path is not None
            self.mime_type = guess_mime_type(self.orig_path)
            self.file_size = os.path.getsize(self.orig_path)
            self.emit("update")
            if self.is_image:
                self._create_thumbnail()
            elif self.is_video:
                self._create_video_thumbnail()

        else:
            assert self.thumb_path is not None
            load_file_async(self.thumb_path, self._on_thumb_load_finished)

    @property
    def is_geo_uri(self) -> bool:
        return self._uri.startswith('geo:')

    @property
    def is_web_uri(self) -> bool:
        return not self.is_geo_uri

    @property
    def is_previewable(self) -> bool:
        return self.mime_type in PREVIEWABLE_MIME_TYPES

    @property
    def is_audio(self) -> bool:
        is_allowed = bool(self.mime_type in ALLOWED_MIME_TYPES)
        return is_allowed and self.mime_type.startswith('audio/')

    @property
    def is_image(self) -> bool:
        is_allowed = bool(self.mime_type in ALLOWED_MIME_TYPES)
        return is_allowed and self.mime_type.startswith('image/')

    @property
    def is_video(self) -> bool:
        is_allowed = bool(self.mime_type in ALLOWED_MIME_TYPES)
        return is_allowed and self.mime_type.startswith('video/')

    @property
    def uri(self) -> str:
        return self._uri

    @property
    def from_us(self) -> bool:
        return self._from_us

    @property
    def context(self) -> str | None:
        return self._context

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def request_uri(self) -> str:
        if self._urlparts is None:
            return ''
        if self.is_aes_encrypted:
            # Remove fragments so we dont transmit it to the server
            urlparts = self._urlparts._replace(scheme='https', fragment='')
            return urlparts.geturl()
        return self._urlparts.geturl()

    @property
    def is_aes_encrypted(self) -> bool:
        if self._urlparts is None:
            return False
        return self._urlparts.scheme == 'aesgcm'

    @property
    def thumb_exists(self) -> bool:
        if self.thumb_path is None:
            return False

        try:
            return self.thumb_path.exists()
        except Exception as error:
            log.error("Could not check if thumbnail exists: %s", error)
            return False

    @property
    def orig_exists(self) -> bool:
        if self.orig_path is None:
            return False

        try:
            return self.orig_path.exists()
        except Exception as error:
            log.error("Could not check if original file exists: %s", error)
            return False

    def get_decryption_data(self) -> AESKeyData | None:
        if not self.is_aes_encrypted:
            return None
        if self.key is None or self.iv is None:
            return None
        return AESKeyData(self.key, self.iv)

    def cancel(self) -> None:
        if self._http_obj is None:
            return
        self._http_obj.cancel()

    def download(self) -> None:
        if self.orig_exists:
            return

        self._download_content(force=True)

    def _on_download_progress(
        self,
        obj: HTTPTransferObject,
        _param: GObject.ParamSpec,
    ) -> None:

        self.emit("progress", obj.progress)

    def _on_thumb_load_finished(
        self,
        data: bytes | None,
        error: GLib.Error | None,
        user_data: Any
    ) -> None:

        if self.thumb_path is None or self.orig_path is None:
            return

        if data is None:
            log.error('%s: %s', self.thumb_path.name, error)
            return

        self.thumbnail = data
        # Thumbnails are stored always as PNG, we don’t know the
        # mime-type of the original picture
        assert self.orig_path is not None
        self.mime_type = guess_mime_type(self.orig_path)
        self.file_size = os.path.getsize(self.orig_path)

        self.emit("update", data)

    def _download_content(self, force: bool = False) -> None:

        if self.download_in_progress:
            log.info('Download already in progress')
            return

        log.info('Start downloading: %s', self.request_uri)
        self.download_in_progress = True

        max_content_length = None if force else app.settings.get('preview_max_file_size')  # noqa: E501
        allowed_content_types = None if force else ALLOWED_MIME_TYPES

        obj = app.http_manager.download(
            self.request_uri,
            self.id,
            output=self.orig_path,
            with_progress=force,
            max_content_length=max_content_length,
            allowed_content_types=allowed_content_types,
            decryption_data=self.get_decryption_data(),
            proxy=determine_proxy(self.account),
        )
        if obj is None:
            return

        obj.connect("finished", self._on_download_finished)
        obj.connect("notify::progress", self._on_download_progress)
        self._http_obj = obj

    def _on_download_finished(
        self,
        ftobj: HTTPTransferObject,
    ) -> None:

        assert self.orig_path is not None
        self.info_message = None
        uri = self.request_uri

        try:
            ftobj.raise_for_error()
        except ContentTypeNotAllowed as error:
            log.info('Not an allowed content type: %s, %s', error, uri)

        except MaxContentLengthExceeded as error:
            log.info('File size (%s) too big for URL: "%s"', error, uri)
            self.info_message = _('Automatic preview disabled '
                                     '(file too big)')

        except HTTPStatusError as error:
            log.info('Status error for %s: %s', uri, error)
            self.info_message = str(error)

        except OverflowError as error:
            log.info("Content-Length overflow for %s: %s", uri, error)

        except CancelledError:
            log.info("Download cancelled for %s", uri)

        except Exception:
            log.exception("Unknown error for: %s", uri)
            self.info_message = _('Unknown Error')

        finally:
            if metadata := ftobj.get_metadata():
                if self.orig_path.exists():
                    self.mime_type = guess_mime_type(self.orig_path)
                elif metadata.content_type is not None:
                    self.mime_type = metadata.content_type

                self.file_size = metadata.content_length

            self.download_in_progress = False
            self.emit("update")

        if ftobj.state != FTState.FINISHED:
            # Some error happened
            return

        log.info('File stored: %s', self.orig_path.name)

        if not app.settings.get('enable_file_preview'):
            return

        if not self.is_previewable:
            return

        if self.is_image:
            self._create_thumbnail()

        elif self.is_video:
            self._create_video_thumbnail()

    def _create_thumbnail(self) -> None:
        assert self.thumb_path is not None
        assert self.orig_path is not None
        try:
            future = app.process_pool.submit(
                create_thumbnail,
                self.orig_path,
                self.thumb_path,
                self.size
            )
            future.add_done_callback(
                partial(GLib.idle_add, self._create_thumbnail_finished)
            )
        except Exception as error:
            self.info_message = _('Creating thumbnail failed')
            self.emit("update")
            log.warning('Creating thumbnail failed for: %s %s',
                        self.orig_path, error)

    def _create_video_thumbnail(self) -> None:
        if self.thumb_path is None:
            log.warning("Creating thumbnail failed, thumbnail path is None")
            return

        assert self.orig_path is not None

        try:
            future = app.process_pool.submit(
                extract_video_thumbnail_and_properties,
                self.orig_path,
                self.thumb_path,
                self.size
            )
            future.add_done_callback(
                partial(GLib.idle_add, self._create_thumbnail_finished)
            )
        except Exception as error:
            self.info_message = _("Creating thumbnail failed")
            self.emit("update")
            log.warning("Creating thumbnail failed for: %s %s",
                        self.orig_path, error)

    def _create_thumbnail_finished(
        self,
        future: Future[tuple[bytes, dict[str, Any]]]
    ) -> bool:
        try:
            thumbnail_bytes, _metadata = future.result()
        except Exception as error:
            self.info_message = _('Creating thumbnail failed')
            log.exception('Creating thumbnail failed for: %s %s',
                          self.orig_path, error)
        else:
            self.thumbnail = thumbnail_bytes

        self.emit("update")

        return GLib.SOURCE_REMOVE
