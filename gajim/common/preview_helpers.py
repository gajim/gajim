# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import NamedTuple

import binascii
import hashlib
import logging
import mimetypes
import sys
from pathlib import Path
from urllib.parse import ParseResult
from urllib.parse import unquote
from urllib.parse import urlparse

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers.modes import GCM
from gi.repository import GdkPixbuf
from gi.repository import Gio
from gi.repository import GLib
from PIL import Image
from PIL import ImageFile

from gajim.common.helpers import sanitize_filename
from gajim.common.i18n import _
from gajim.common.i18n import p_

log = logging.getLogger('gajim.c.preview_helpers')

ImageFile.LOAD_TRUNCATED_IMAGES = True


class Coords(NamedTuple):
    location: str
    lat: str
    lon: str


def parse_fragment(fragment_string: str) -> tuple[bytes, bytes]:
    if not fragment_string:
        raise ValueError('Invalid fragment')

    fragment = binascii.unhexlify(fragment_string)
    size = len(fragment)
    # Clients started out with using a 16 byte IV but long term
    # want to switch to the more performant 12 byte IV
    # We have to support both
    if size == 48:
        key = fragment[16:]
        iv = fragment[:16]
    elif size == 44:
        key = fragment[12:]
        iv = fragment[:12]
    else:
        raise ValueError('Invalid fragment size: %s' % size)

    return key, iv


def get_image_paths(uri: str,
                    urlparts: ParseResult,
                    size: int,
                    orig_dir: Path,
                    thumb_dir: Path) -> tuple[Path, Path]:

    path = Path(unquote(urlparts.path))
    web_stem = path.stem
    extension = path.suffix

    web_stem = sanitize_filename(web_stem)

    name_hash = hashlib.sha1(str(uri).encode()).hexdigest()

    orig_filename = f'{web_stem}_{name_hash}{extension}'

    thumb_filename = f'{web_stem}_{name_hash}_thumb_{size}{extension}'

    orig_path = orig_dir / orig_filename
    thumb_path = thumb_dir / thumb_filename
    return orig_path, thumb_path


def split_geo_uri(uri: str) -> Coords:
    # Example:
    # geo:37.786971,-122.399677,122.3;CRS=epsg:32718;U=20;mapcolors=abc
    # Assumption is all coordinates are CRS=WGS-84

    # Remove "geo:"
    coords = uri[4:]

    # Remove arguments
    if ';' in coords:
        coords, _ = coords.split(';', maxsplit=1)

    # Split coords
    coords = coords.split(',')
    if len(coords) not in (2, 3):
        raise ValueError('Invalid geo uri: invalid coord count')

    # Remoove coord-c (altitude)
    if len(coords) == 3:
        coords.pop(2)

    lat, lon = coords
    if float(lat) < -90 or float(lat) > 90:
        raise ValueError('Invalid geo_uri: invalid latitude %s' % lat)

    if float(lon) < -180 or float(lon) > 180:
        raise ValueError('Invalid geo_uri: invalid longitude %s' % lon)

    location = ','.join(coords)
    return Coords(location=location, lat=lat, lon=lon)


def format_geo_coords(lat: float, lon: float) -> str:
    def fmt(f: float) -> str:
        i = int(round(f * 3600.0))
        seconds = i % 60
        i //= 60
        minutes = i % 60
        i //= 60
        degrees = i
        return '%d°%02d′%02d′′' % (degrees, minutes, seconds)
    if lat >= 0:
        slat = p_('positive latitude', '%sN') % fmt(lat)
    else:
        slat = p_('negative latitude', '%sS') % fmt(-lat)
    if lon >= 0:
        slon = p_('positive longitude', '%sE') % fmt(lon)
    else:
        slon = p_('negative longitude', '%sW') % fmt(-lon)
    return f'{slat} {slon}'


def filename_from_uri(uri: str) -> str:
    urlparts = urlparse(unquote(uri))
    path = Path(urlparts.path)
    return path.name


def aes_decrypt(key: bytes, iv: bytes, payload: bytes) -> bytes:
    # Use AES256 GCM with the given key and iv to decrypt the payload
    data = payload[:-16]
    tag = payload[-16:]
    decryptor = Cipher(algorithms.AES(key),
                       GCM(iv, tag=tag),
                       backend=default_backend()).decryptor()
    return decryptor.update(data) + decryptor.finalize()


def contains_audio_streams(file_path: Path) -> bool:
    # Check if it is really an audio file

    from gi.repository import GstPbutils

    has_audio = False
    discoverer = GstPbutils.Discoverer()
    try:
        info = discoverer.discover_uri(file_path.as_uri())
        has_audio = bool(info.get_audio_streams())
    except GLib.Error as err:
        log.error('Error while reading %s: %s', str(file_path), err)
        return False
    if not has_audio:
        log.warning('File does not contain audio stream: %s', str(file_path))
    return has_audio


def get_previewable_mime_types() -> set[str]:
    previewable_mime_types: set[str] = set()
    for fmt in GdkPixbuf.Pixbuf.get_formats():
        for mime_type in fmt.get_mime_types():
            previewable_mime_types.add(mime_type.lower())

    Image.init()
    for mime_type in Image.MIME.values():
        previewable_mime_types.add(mime_type.lower())

    return set(filter(
        lambda mime_type: mime_type.startswith('image'),
        previewable_mime_types
    ))


def guess_mime_type(file_path: Path | str,
                    data: bytes | None = None
                    ) -> str:
    file_path = str(file_path)

    if not mimetypes.inited:
        # On Windows both mime types are only available
        # with python 3.11, so this can be removed once
        # the Windows build uses python 3.11
        mimetypes.add_type('image/webp', '.webp')
        mimetypes.add_type('image/avif', '.avif')

    # The mimetypes module maps extensions to mime types
    # it does no guessing based on file content
    mime_type, _ = mimetypes.guess_type(file_path)
    if mime_type is None and not sys.platform == 'win32':
        # Does not work on Windows see
        # https://gitlab.gnome.org/GNOME/glib/-/issues/3399
        # Gio does also guess based on file content
        extension, _ = Gio.content_type_guess(file_path, data)
        mime_type = Gio.content_type_get_mime_type(extension)

    log.debug('Guessed MIME type: %s', mime_type)
    return mime_type or ''


def guess_simple_file_type(file_path: str,
                           data: bytes | None = None
                           ) -> tuple[Gio.Icon, str]:
    mime_type = guess_mime_type(file_path, data)
    if mime_type == 'application/octet-stream':
        mime_type = ''
    icon = get_icon_for_mime_type(mime_type)
    if mime_type.startswith('audio/'):
        return icon, _('Audio File')
    if mime_type.startswith('image/'):
        return icon, _('Image')
    if mime_type.startswith('video/'):
        return icon, _('Video')
    if mime_type.startswith('text/'):
        return icon, _('Text File')
    return icon, _('File')


def get_icon_for_mime_type(mime_type: str) -> Gio.Icon:
    if mime_type == '':
        return Gio.Icon.new_for_string('mail-attachment')
    return Gio.content_type_get_icon(mime_type)
