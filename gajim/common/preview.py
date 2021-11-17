# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from typing import Any
from typing import Dict
from typing import Optional
from typing import Tuple

import logging
import os
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import ParseResult

from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Soup

from gajim.common import app
from gajim.common import configpaths
from gajim.common.const import MIME_TYPES
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import load_file_async
from gajim.common.helpers import write_file_async
from gajim.common.helpers import get_tls_error_phrase
from gajim.common.helpers import get_user_proxy
from gajim.common.preview_helpers import aes_decrypt
from gajim.common.preview_helpers import filename_from_uri
from gajim.common.preview_helpers import parse_fragment
from gajim.common.preview_helpers import create_thumbnail
from gajim.common.preview_helpers import split_geo_uri
from gajim.common.preview_helpers import get_previewable_mime_types
from gajim.common.preview_helpers import get_image_paths
from gajim.common.preview_helpers import guess_mime_type
from gajim.common.preview_helpers import pixbuf_from_data

log = logging.getLogger('gajim.c.preview')

PREVIEWABLE_MIME_TYPES = get_previewable_mime_types()
mime_types = set(MIME_TYPES)
# Merge both: if it’s a previewable image, it should be allowed
ALLOWED_MIME_TYPES = mime_types.union(PREVIEWABLE_MIME_TYPES)


class Preview:
    def __init__(self, 
                 uri: str,
                 urlparts: Optional[ParseResult],
                 orig_path: Optional[Path],
                 thumb_path: Optional[Path],
                 size: int,
                 widget: Any) -> None:
        self._uri = uri
        self._urlparts = urlparts
        self._filename = filename_from_uri(uri)
        self._widget = widget

        self.account = widget.account
        self.orig_path = orig_path
        self.thumb_path = thumb_path
        self.size = size

        self.thumbnail: Optional[bytes] = None
        self.mime_type: str = ''
        self.file_size: int = 0

        self.key: Optional[bytes] = None
        self.iv: Optional[bytes] = None
        if self.is_aes_encrypted and urlparts is not None:
            self.key, self.iv = parse_fragment(urlparts.fragment)

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
    def uri(self) -> str:
        return self._uri

    @property
    def filename(self) -> str:
        return self._filename

    @property
    def request_uri(self) -> Optional[str]:
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

    def thumb_exists(self) -> bool:
        if self.thumb_path is None:
            return False
        return self.thumb_path.exists()

    def orig_exists(self) -> bool:
        if self.orig_path is None:
            return False
        return self.orig_path.exists()

    def create_thumbnail(self, data: bytes) -> bool:
        self.thumbnail = create_thumbnail(data, self.size)
        if self.thumbnail is None:
            log.warning('Creating thumbnail failed for: %s', self.orig_path)
            return False
        return True

    def update_widget(self, data: Optional[GdkPixbuf.Pixbuf] = None) -> None:
        self._widget.update(self, data)


class PreviewManager:
    def __init__(self) -> None:
        self._sessions: Dict[
            str,
            Tuple[Soup.Session, Optional[Gio.SimpleProxyResolver]]] = {}

        self._orig_dir = Path(configpaths.get('MY_DATA')) / 'downloads'
        self._thumb_dir = Path(configpaths.get('MY_CACHE')) / 'downloads.thumb'

        if GLib.mkdir_with_parents(str(self._orig_dir), 0o700) != 0:
            log.error('Failed to create: %s', self._orig_dir)

        if GLib.mkdir_with_parents(str(self._thumb_dir), 0o700) != 0:
            log.error('Failed to create: %s', self._thumb_dir)

    def _get_session(self, account: str) -> Soup.Session:
        if account not in self._sessions:
            self._sessions[account] = self._create_session(account)
        return self._sessions[account][0]

    @staticmethod
    def _create_session(account: str) -> Tuple[
            Soup.Session, Optional[Gio.SimpleProxyResolver]]:
        session = Soup.Session()
        session.add_feature_by_type(Soup.ContentSniffer)
        session.props.https_aliases = ['aesgcm']
        session.props.ssl_strict = False

        proxy = get_user_proxy(account)
        if proxy is None:
            resolver = None
        else:
            resolver = proxy.get_resolver()

        session.props.proxy_resolver = resolver
        return session, resolver

    @staticmethod
    def _accept_uri(urlparts: ParseResult,
                    uri: str,
                    additional_data: AdditionalDataDict) -> bool:
        try:
            oob_url = additional_data['gajim']['oob_url']
        except (KeyError, AttributeError):
            oob_url = None

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
                       additional_data: AdditionalDataDict) -> bool:
        if len(text.split(' ')) > 1:
            # urlparse doesn't recognise spaces as URL delimiter
            log.debug('Text is not an uri: %s...', text[:15])
            return False

        uri = text
        urlparts = urlparse(uri)
        if not self._accept_uri(urlparts, uri, additional_data):
            return False

        if uri.startswith('geo:'):
            try:
                split_geo_uri(uri)
            except Exception as err:
                log.error(uri)
                log.error(err)
                return False

        return True

    def create_preview(self, uri: str, widget: Any, context: str) -> None:
        if uri.startswith('geo:'):
            preview = Preview(uri, None, None, None, 96, widget)
            preview.update_widget()
            return

        preview = self._process_web_uri(uri, widget)

        if not preview.orig_exists():
            if context is not None:
                allow_in_public = app.settings.get('preview_anonymous_muc')
                if context == 'public' and not allow_in_public:
                    preview.update_widget()
                    return

            self.download_content(preview)

        elif not preview.thumb_exists():
            load_file_async(preview.orig_path,
                            self._on_orig_load_finished,
                            preview)

        else:
            load_file_async(preview.thumb_path,
                            self._on_thumb_load_finished,
                            preview)

    def _process_web_uri(self, uri: str, widget: Any) -> Preview:
        urlparts = urlparse(uri)
        size = app.settings.get('preview_size')
        orig_path, thumb_path = get_image_paths(uri,
                                                urlparts,
                                                size,
                                                self._orig_dir,
                                                self._thumb_dir)
        return Preview(uri,
                       urlparts,
                       orig_path,
                       thumb_path,
                       size,
                       widget)

    def _on_orig_load_finished(self,
                               data: Optional[bytes],
                               error: Gio.AsyncResult,
                               preview: Preview) -> None:
        if preview.thumb_path is None or preview.orig_path is None:
            return

        if data is None:
            log.error('%s: %s', preview.orig_path.name, error)
            return

        preview.mime_type = guess_mime_type(preview.orig_path)
        preview.file_size = os.path.getsize(preview.orig_path)
        if preview.is_previewable:
            if preview.create_thumbnail(data):
                write_file_async(preview.thumb_path,
                                 preview.thumbnail,
                                 self._on_thumb_write_finished,
                                 preview)
        else:
            preview.update_widget()

    @staticmethod
    def _on_thumb_load_finished(data: Optional[bytes],
                                error: Gio.AsyncResult,
                                preview: Preview) -> None:
        if preview.thumb_path is None or preview.orig_path is None:
            return

        if data is None:
            log.error('%s: %s', preview.thumb_path.name, error)
            return

        preview.thumbnail = data
        preview.mime_type = guess_mime_type(preview.orig_path)
        preview.file_size = os.path.getsize(preview.orig_path)

        try:
            pixbuf = pixbuf_from_data(preview.thumbnail)
        except Exception as err:
            log.error('Unable to load: %s, %s',
                      preview.thumb_path.name,
                      err)
            return
        preview.update_widget(data=pixbuf)

    def download_content(self,
                         preview: Preview,
                         force: bool = False) -> None:
        if preview.account is None:
            # History Window can be opened without account context
            # This means we can not apply proxy settings
            return
        log.info('Start downloading: %s', preview.request_uri)
        message = Soup.Message.new('GET', preview.request_uri)
        message.connect('starting', self._check_certificate, preview)
        message.connect(
            'content-sniffed', self._on_content_sniffed, preview, force)

        session = self._get_session(preview.account)
        session.queue_message(message, self._on_finished, preview)

    def _check_certificate(self,
                           message: Soup.Message,
                           preview: Preview) -> None:
        _https_used, _tls_certificate, tls_errors = message.get_https_status()

        if not app.settings.get('preview_verify_https'):
            return

        if tls_errors:
            phrase = get_tls_error_phrase(tls_errors)
            log.warning('TLS verification failed: %s', phrase)
            session = self._get_session(preview.account)
            session.cancel_message(message, Soup.Status.CANCELLED)
            return

    def _on_content_sniffed(self,
                            message: Soup.Message,
                            type_: str,
                            _params: GLib.HashTable,
                            preview: Preview,
                            force: bool) -> None:
        file_size = message.props.response_headers.get_content_length()
        uri = message.props.uri.to_string(False)
        session = self._get_session(preview.account)
        preview.mime_type = type_
        preview.file_size = file_size

        if type_ not in ALLOWED_MIME_TYPES:
            log.info('Not an allowed content type: %s, %s', type_, uri)
            session.cancel_message(message, Soup.Status.CANCELLED)
            return

        max_file_size = app.settings.get('preview_max_file_size')
        if file_size == 0 or file_size > int(max_file_size):
            log.info(
                'File size (%s) too big or unknown (zero) for URL: \'%s\'',
                file_size, uri)
            if not force:
                session.cancel_message(message, Soup.Status.CANCELLED)

        preview.update_widget()

    def _on_finished(self,
                     _session: Soup.Session,
                     message: Soup.Message,
                     preview: Preview) -> None:
        if message.status_code != Soup.Status.OK:
            log.warning('Download failed: %s', preview.request_uri)
            log.warning(Soup.Status.get_phrase(message.status_code))
            preview.update_widget()
            return

        data = message.props.response_body_data.get_data()
        if data is None:
            return

        if preview.is_aes_encrypted:
            if preview.key is not None and preview.iv is not None:
                data = aes_decrypt(preview.key, preview.iv, data)

        if preview.mime_type == 'application/octet-stream':
            if preview.orig_path is not None:
                preview.mime_type = guess_mime_type(preview.orig_path, data)

        write_file_async(preview.orig_path,
                         data,
                         self._on_orig_write_finished,
                         preview)

        if preview.is_previewable:
            if preview.create_thumbnail(data):
                write_file_async(preview.thumb_path,
                                 preview.thumbnail,
                                 self._on_thumb_write_finished,
                                 preview)

    @staticmethod
    def _on_orig_write_finished(_result: bool,
                                error: GLib.Error,
                                preview: Preview) -> None:
        if preview.orig_path is None:
            return

        if error is not None:
            log.error('%s: %s', preview.orig_path.name, error)
            return

        log.info('File stored: %s', preview.orig_path.name)
        preview.file_size = os.path.getsize(preview.orig_path)
        if not preview.is_previewable:
            # Don’t update preview if thumb is already displayed,
            # but update preview for audio files
            preview.update_widget()

    @staticmethod
    def _on_thumb_write_finished(_result: bool,
                                 error: GLib.Error,
                                 preview: Preview) -> None:
        if preview.thumb_path is None:
            return

        if error is not None:
            log.error('%s: %s', preview.thumb_path.name, error)
            return

        log.info('Thumbnail stored: %s ', preview.thumb_path.name)

        if preview.thumbnail is None:
            return

        try:
            pixbuf = pixbuf_from_data(preview.thumbnail)
        except Exception as err:
            log.error('Unable to load: %s, %s',
                      preview.thumb_path.name,
                      err)
            return
        preview.update_widget(data=pixbuf)
