# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import hashlib
import logging
import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import ParseResult
from urllib.parse import unquote
from urllib.parse import urlparse

from gi.repository import Gio
from gi.repository import GLib

from gajim.common import app
from gajim.common.const import ALL_MIME_TYPES
from gajim.common.const import AUDIO_MIME_TYPES
from gajim.common.const import IMAGE_MIME_TYPES
from gajim.common.const import VIDEO_MIME_TYPES
from gajim.common.helpers import sanitize_filename
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.regex import IRI_RX
from gajim.common.storage.archive import models as mod
from gajim.common.util.uri import Coords
from gajim.common.util.uri import get_geo_choords

log = logging.getLogger("gajim.c.util.preview")

MIME_TYPE_MAP = {"application/x-ext-webp": "image/webp"}


def get_image_paths(
    uri: str, urlparts: ParseResult, size: int, orig_dir: Path, thumb_dir: Path
) -> tuple[Path, Path]:

    path = Path(unquote(urlparts.path))
    web_stem = path.stem
    extension = path.suffix

    web_stem = sanitize_filename(web_stem)

    name_hash = hashlib.sha1(str(uri).encode()).hexdigest()

    orig_filename = f"{web_stem}_{name_hash}{extension}"

    thumb_filename = f"{web_stem}_{name_hash}_thumb_{size}.png"

    orig_path = orig_dir / orig_filename
    thumb_path = thumb_dir / thumb_filename
    return orig_path, thumb_path


def format_geo_coords(coords: Coords) -> str:
    lat = float(coords.lat)
    lon = float(coords.lon)

    def fmt(f: float) -> str:
        i = int(round(f * 3600.0))
        seconds = i % 60
        i //= 60
        minutes = i % 60
        i //= 60
        degrees = i
        return "%d°%02d′%02d′′" % (degrees, minutes, seconds)

    if lat >= 0:
        slat = p_("positive latitude", "%sN") % fmt(lat)
    else:
        slat = p_("negative latitude", "%sS") % fmt(-lat)
    if lon >= 0:
        slon = p_("positive longitude", "%sE") % fmt(lon)
    else:
        slon = p_("negative longitude", "%sW") % fmt(-lon)
    return f"{slat} {slon}"


def filename_from_uri(uri: str) -> str:
    urlparts = urlparse(unquote(uri))
    path = Path(urlparts.path)
    return path.name


def contains_audio_streams(file_path: Path) -> bool:
    # Check if it is really an audio file

    from gi.repository import GstPbutils

    has_audio = False
    discoverer = GstPbutils.Discoverer()
    try:
        info = discoverer.discover_uri(file_path.as_uri())
        has_audio = bool(info.get_audio_streams())
    except GLib.Error as err:
        log.error("Error while reading %s: %s", str(file_path), err)
        return False
    if not has_audio:
        log.warning("File does not contain audio stream: %s", str(file_path))
    return has_audio


def guess_mime_type(file_path: Path | str, data: bytes | None = None) -> str:
    file_path = str(file_path)

    # The mimetypes module maps extensions to mime types
    # it does no guessing based on file content
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None:
        # Gio does also guess based on file content
        extension, _ = Gio.content_type_guess(file_path, data)
        mime_type = Gio.content_type_get_mime_type(extension)

    if mime_type is not None:
        # Mime type guessing via Gio on Windows is partly broken, which results in
        # e.g. "application/x-ext-webp". Try to map those mime types.
        # See https://gitlab.gnome.org/GNOME/librsvg/-/issues/1181#note_2526154
        mime_type = MIME_TYPE_MAP.get(mime_type, mime_type)

    log.debug("Guessed MIME type: %s", mime_type)
    return mime_type or ""


def guess_simple_file_type(
    file_path: str, data: bytes | None = None
) -> tuple[Gio.Icon, str, str]:

    mime_type = guess_mime_type(file_path, data)
    icon = get_icon_for_mime_type(mime_type)

    file_type = _("File")
    if mime_type.startswith("audio/"):
        file_type = _("Audio File")
    if mime_type.startswith("image/"):
        file_type = _("Image")
    if mime_type.startswith("video/"):
        file_type = _("Video")
    if mime_type.startswith("text/"):
        file_type = _("Text File")

    return icon, file_type, mime_type


def get_size_and_mime_type(path: Path) -> tuple[str, int]:
    return guess_mime_type(path), os.path.getsize(path)


def get_icon_for_mime_type(mime_type: str | None) -> Gio.Icon:
    if not mime_type:
        return Gio.Icon.new_for_string("lucide-file-symbolic")
    return Gio.content_type_get_icon(mime_type)


def is_audio(mime_type: str) -> bool:
    return mime_type in AUDIO_MIME_TYPES


def is_video(mime_type: str) -> bool:
    return mime_type in VIDEO_MIME_TYPES


def is_image(mime_type: str) -> bool:
    return mime_type in IMAGE_MIME_TYPES


@dataclass
class UrlPreview:
    uri: str
    mime_type: str
    file_name: str
    text: str
    icon: Gio.Icon
    encrypted: bool

    @classmethod
    def from_uri(cls, uri: str) -> UrlPreview:
        encrypted = uri.startswith("aesgcm://")
        file_name = filename_from_uri(uri)
        icon, file_type, mime_type = guess_simple_file_type(uri)
        text = f"{file_type} ({file_name})"
        return cls(
            uri=uri,
            mime_type=mime_type,
            file_name=file_name,
            text=text,
            icon=icon,
            encrypted=encrypted,
        )


@dataclass
class GeoPreview:
    uri: str
    text: str
    icon: Gio.Icon
    coords: Coords

    @classmethod
    def from_coords(cls, uri: str, coords: Coords) -> GeoPreview:
        icon = Gio.Icon.new_for_string("lucide-map-pin-symbolic")
        text = format_geo_coords(coords)
        return cls(uri=uri, text=text, icon=icon, coords=coords)


def get_preview_data(
    uri: str, oob_data: list[mod.OOB]
) -> GeoPreview | UrlPreview | None:

    if not IRI_RX.fullmatch(uri):
        # urlparse removes whitespace (and who knows what else) from URLs,
        # so can't be used for validation.
        return None

    try:
        urlparts = urlparse(uri)
    except Exception:
        return None

    if urlparts.scheme == "geo":
        coords = get_geo_choords(uri)
        if coords is not None:
            return GeoPreview.from_coords(uri, coords)
        return None

    if not urlparts.netloc:
        return None

    oob_url = None if not oob_data else oob_data[0].url

    if uri == oob_url or urlparts.scheme == "aesgcm":
        return UrlPreview.from_uri(uri)

    # http/https
    if urlparts.scheme not in ("https", "http"):
        log.info("Unsupported URI scheme: %s", uri)
        return None

    if not app.settings.get("preview_allow_all_images"):
        return None

    mime_type = guess_mime_type(uri)
    if mime_type not in ALL_MIME_TYPES:
        log.info("%s not in allowed mime types", mime_type)
        return None

    return UrlPreview.from_uri(uri)
