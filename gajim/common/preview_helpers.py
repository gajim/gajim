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
from typing import List
from typing import Tuple
from typing import Optional

import math
import logging
import binascii
import hashlib
import mimetypes
from io import BytesIO
from collections import namedtuple
from pathlib import Path
from urllib.parse import urlparse
from urllib.parse import unquote

from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gio
from gi.repository import GstPbutils

from PIL import Image

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher
from cryptography.hazmat.primitives.ciphers import algorithms
from cryptography.hazmat.primitives.ciphers.modes import GCM

from gajim.common.i18n import _

log = logging.getLogger('gajim.c.preview_helpers')

Coords = namedtuple('Coords', 'location lat lon')


def resize_gif(image: Image, output_file: BytesIO,
               resize_to: Tuple[int, int]) -> None:
    frames, result = extract_and_resize_frames(image, resize_to)

    frames[0].save(output_file,
                   format='GIF',
                   optimize=True,
                   save_all=True,
                   append_images=frames[1:],
                   duration=result['duration'],
                   loop=1000)


def analyse_image(image: Image) -> Tuple[Image, Dict[str, Any]]:
    '''
    Pre-process pass over the image to determine the mode (full or additive).
    Necessary as assessing single frames isn't reliable. Need to know the mode
    before processing all frames.
    '''

    result = {
        'size': image.size,
        'mode': 'full',
        'duration': image.info.get('duration', 0)
    }

    try:
        while True:
            if image.tile:
                tile = image.tile[0]
                update_region = tile[1]
                update_region_dimensions = update_region[2:]
                if update_region_dimensions != image.size:
                    result['mode'] = 'partial'
                    break
            image.seek(image.tell() + 1)
    except EOFError:
        image.seek(0)
    return image, result


def extract_and_resize_frames(image: Image, resize_to: Tuple[int, int]
                              ) -> Tuple[List[Image], Dict[str, Any]]:
    image, result = analyse_image(image)

    i = 0
    palette = image.getpalette()
    last_frame = image.convert('RGBA')

    frames = []

    try:
        while True:
            '''
            If the GIF uses local colour tables,
            each frame will have its own palette.
            If not, we need to apply the global palette to the new frame.
            '''
            if not image.getpalette():
                image.putpalette(palette)

            new_frame = Image.new('RGBA', image.size)

            '''
            Is this file a "partial"-mode GIF where frames update a region
            of a different size to the entire image?
            If so, we need to construct the new frame by
            pasting it on top of the preceding frames.
            '''
            if result['mode'] == 'partial':
                new_frame.paste(last_frame)

            new_frame.paste(image, (0, 0), image.convert('RGBA'))

            # This method preservs aspect ratio
            new_frame.thumbnail(resize_to, Image.ANTIALIAS)
            frames.append(new_frame)

            i += 1
            last_frame = new_frame
            image.seek(image.tell() + 1)
    except EOFError:
        pass

    return frames, result


def create_thumbnail(data: bytes, size:int) -> Optional[bytes]:
    thumbnail = create_thumbnail_with_pil(data, size)
    if thumbnail is not None:
        return thumbnail
    return create_thumbnail_with_pixbuf(data, size)


def create_thumbnail_with_pixbuf(data: bytes, size: int) -> Optional[bytes]:
    loader = GdkPixbuf.PixbufLoader()
    try:
        loader.write(data)
        loader.close()
    except GLib.Error as error:
        log.warning('making pixbuf failed: %s', error)
        return None

    pixbuf = loader.get_pixbuf()

    if size > pixbuf.get_width() and size > pixbuf.get_height():
        return data

    width, height = get_thumbnail_size(pixbuf, size)
    thumbnail = pixbuf.scale_simple(width,
                                    height,
                                    GdkPixbuf.InterpType.BILINEAR)
    try:
        _error, bytes_ = thumbnail.save_to_bufferv('png', [], [])
    except GLib.Error as err:
        log.warning('Saving pixbuf to buffer failed: %s', err)
        return None
    return bytes_


def create_thumbnail_with_pil(data: bytes, size: int) -> Optional[bytes]:
    input_file = BytesIO(data)
    output_file = BytesIO()
    try:
        image = Image.open(input_file)
    except OSError as error:
        log.warning('making pil thumbnail failed: %s', error)
        log.warning('fallback to pixbuf')
        input_file.close()
        output_file.close()
        return None

    image_width, image_height = image.size
    if size > image_width and size > image_height:
        image.close()
        input_file.close()
        output_file.close()
        return data

    if image.format == 'GIF' and image.n_frames > 1:
        resize_gif(image, output_file, (size, size))
    else:
        image.thumbnail((size, size))
        image.save(output_file,
                   format=image.format,
                   exif=image.info.get('exif', b''),
                   optimize=True)

    bytes_ = output_file.getvalue()

    image.close()
    input_file.close()
    output_file.close()

    return bytes_


def get_thumbnail_size(pixbuf: GdkPixbuf.Pixbuf, size: int) -> Tuple[int, int]:
    # Calculates the new thumbnail size while preserving the aspect ratio
    image_width = pixbuf.get_width()
    image_height = pixbuf.get_height()

    if image_width > image_height:
        if image_width > size:
            image_height = math.ceil((size / float(image_width) * image_height))
            image_width = int(size)
    else:
        if image_height > size:
            image_width = math.ceil((size / float(image_height) * image_width))
            image_height = int(size)

    return image_width, image_height


def pixbuf_from_data(data: bytes) -> GdkPixbuf.Pixbuf:
    loader = GdkPixbuf.PixbufLoader()
    try:
        loader.write(data)
        loader.close()
    except GLib.Error:
        # Fallback to Pillow
        input_file = BytesIO(data)
        image = Image.open(BytesIO(data)).convert('RGBA')
        array = GLib.Bytes.new(image.tobytes())
        width, height = image.size
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(array,
                                                 GdkPixbuf.Colorspace.RGB,
                                                 True,
                                                 8,
                                                 width,
                                                 height,
                                                 width * 4)
        image.close()
        input_file.close()
        return pixbuf

    return loader.get_pixbuf().apply_embedded_orientation()


def parse_fragment(fragment: str) -> Tuple[bytes, bytes]:
    if not fragment:
        raise ValueError('Invalid fragment')

    fragment = binascii.unhexlify(fragment)
    size = len(fragment)
    # Clients started out with using a 16 byte IV but long term
    # want to swtich to the more performant 12 byte IV
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


def get_image_paths(uri, urlparts, size, orig_dir, thumb_dir):
    path = Path(unquote(urlparts.path))
    web_stem = path.stem
    extension = path.suffix

    if len(web_stem) > 90:
        # Many Filesystems have a limit on filename length
        # Most have 255, some encrypted ones only 143
        # We add around 50 chars for the hash,
        # so the filename should not exceed 90
        web_stem = web_stem[:90]

    name_hash = hashlib.sha1(str(uri).encode()).hexdigest()

    orig_filename = '%s_%s%s' % (web_stem, name_hash, extension)

    thumb_filename = '%s_%s_thumb_%s%s' % (web_stem,
                                           name_hash,
                                           size,
                                           extension)

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


def filename_from_uri(uri: str) -> str:
    urlparts = urlparse(unquote(uri))
    path = Path(urlparts.path)
    return path.name


def aes_decrypt(preview, payload):
    # Use AES128 GCM with the given key and iv to decrypt the payload
    data = payload[:-16]
    tag = payload[-16:]
    decryptor = Cipher(
        algorithms.AES(preview.key),
        GCM(preview.iv, tag=tag),
        backend=default_backend()).decryptor()
    return decryptor.update(data) + decryptor.finalize()


def contains_audio_streams(file_path):
    # Check if it is really an audio file
    has_audio = False
    discoverer = GstPbutils.Discoverer()
    try:
        info = discoverer.discover_uri(f'file://{file_path}')
        has_audio = bool(info.get_audio_streams())
    except GLib.Error as err:
        log.error('Error while reading %s: %s', str(file_path), err)
        return False
    if not has_audio:
        log.warning('File does not contain audio stream: %s', str(file_path))
    return has_audio


def get_previewable_mime_types():
    previewable_mime_types = set()
    for fmt in GdkPixbuf.Pixbuf.get_formats():
        for mime_type in fmt.get_mime_types():
            previewable_mime_types.add(mime_type.lower())
    if Image is not None:
        Image.init()
        for mime_type in Image.MIME.values():
            previewable_mime_types.add(mime_type.lower())
    return tuple(filter(
        lambda mime_type: mime_type.startswith('image'),
        previewable_mime_types
    ))


def guess_mime_type(file_path: str,
                    data: Optional[bytes] = None
                    ) -> str:
    mime_type, _ = mimetypes.MimeTypes().guess_type(str(file_path))
    if mime_type is None:
        # Try to guess MIME type by file name
        mime_type, _ = Gio.content_type_guess(str(file_path), data)
    log.debug('Guessed MIME type: %s', str(mime_type))
    return mime_type


def guess_simple_file_type(file_path: str,
                           data: Optional[bytes] = None
                           ) -> Tuple[Gio.Icon, str]:
    mime_type = guess_mime_type(file_path, data)
    icon = get_icon_for_mime_type(mime_type)
    if file_path.startswith('geo:'):
        return icon, _('Location')
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
    if mime_type is None:
        return Gio.Icon.new_for_string('mail-attachment')
    return Gio.content_type_get_icon(mime_type)
