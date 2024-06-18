# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import logging
from io import BytesIO
from pathlib import Path

from gi.repository import GdkPixbuf
from gi.repository import GLib
from PIL import Image
from PIL import ImageFile
from PIL import UnidentifiedImageError

log = logging.getLogger('gajim.c.image_helpers')

ImageFile.LOAD_TRUNCATED_IMAGES = True


def get_pixbuf_from_file(
    path: str | Path, size: int | None = None
) -> GdkPixbuf.Pixbuf | None:
    '''Tries to load Pixbuf from file to return it with size.
    If Pixbuf fails, Pillow is used as fallback.
    '''
    try:
        if size is None:
            return GdkPixbuf.Pixbuf.new_from_file(str(path))
        return GdkPixbuf.Pixbuf.new_from_file_at_scale(str(path), size, size, True)

    except GLib.Error:
        try:
            with open(path, 'rb') as image_handle:
                img = Image.open(image_handle)  # pyright: ignore
                converted_image = img.convert('RGBA')
        except (NameError, OSError, UnidentifiedImageError):
            log.warning('Pillow convert failed: %s', path)
            log.debug('Error', exc_info=True)
            return None

        array = GLib.Bytes.new(converted_image.tobytes())  # pyright: ignore
        width, height = converted_image.size
        pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
            array, GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * 4
        )
        if size is not None:
            width, height = scale_with_ratio(size, width, height)
            return pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        return pixbuf

    except RuntimeError as error:
        log.warning('Loading pixbuf failed: %s', error)
        return None


def get_pixbuf_from_data(data: bytes) -> GdkPixbuf.Pixbuf | None:
    '''
    Load data into PixbufLoader and return GdkPixbuf.Pixbuf if possible.
    Pillow is used as fallback mechanism.
    '''
    pixbufloader = GdkPixbuf.PixbufLoader()
    try:
        pixbufloader.write(data)
        pixbufloader.close()
        pixbuf = pixbufloader.get_pixbuf()
    except GLib.Error:
        pixbufloader.close()

        log.warning(
            'Loading image data using PixbufLoader failed. '
            'Trying to convert image data using Pillow.'
        )
        try:
            image = Image.open(BytesIO(data)).convert('RGBA')  # pyright: ignore
            array = GLib.Bytes.new(image.tobytes())  # pyright: ignore
            width, height = image.size
            pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                array, GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * 4
            )
            image.close()
        except Exception:
            log.warning(
                'Could not use Pillow to convert image data. '
                'Image cannot be displayed',
                exc_info=True,
            )
            return None

    if pixbuf is None:
        return None

    pixbuf = pixbuf.apply_embedded_orientation()
    return pixbuf


def scale_with_ratio(size: int, width: int, height: int) -> tuple[int, int]:
    if height == width:
        return size, size
    if height > width:
        ratio = height / float(width)
        return int(size / ratio), size

    ratio = width / float(height)
    return size, int(size / ratio)


def scale_pixbuf(pixbuf: GdkPixbuf.Pixbuf, size: int) -> GdkPixbuf.Pixbuf | None:
    width, height = scale_with_ratio(size, pixbuf.get_width(), pixbuf.get_height())
    return pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)


def scale_pixbuf_from_data(data: bytes, size: int) -> GdkPixbuf.Pixbuf | None:
    pixbuf = get_pixbuf_from_data(data)
    assert pixbuf is not None
    return scale_pixbuf(pixbuf, size)
