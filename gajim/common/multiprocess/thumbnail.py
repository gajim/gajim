# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import math
from io import BytesIO

from gi.repository import GdkPixbuf
from gi.repository import GLib
from PIL import Image

log = logging.getLogger('gajim.c.multiprocess.thumbnail')


def create_thumbnail(data: bytes, size: int, mime_type: str) -> bytes | None:
    # Create thumbnail from bytes and return bytes in PNG format

    try:
        thumbnail = _create_thumbnail_with_pil(data, size)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        # Don't try to process image further
        return None

    if thumbnail is not None:
        return thumbnail
    return _create_thumbnail_with_pixbuf(data, size, mime_type)


def _create_thumbnail_with_pixbuf(
    data: bytes, size: int, mime_type: str
) -> bytes | None:
    # Reads data and returns thumbnail bytes in PNG format

    try:
        # Try to create GdKPixbuf loader with fixed mime-type to
        # fix mime-type detection for HEIF images on some systems
        loader = GdkPixbuf.PixbufLoader.new_with_mime_type(mime_type)
    except GLib.Error as error:
        log.warning(
            'Creating pixbuf loader with mime ' 'type %s failed: %s', mime_type, error
        )
        loader = GdkPixbuf.PixbufLoader()

    try:
        loader.write(data)
        loader.close()
    except GLib.Error as error:
        log.warning('Loading pixbuf failed: %s', error)
        return None

    pixbuf = loader.get_pixbuf()
    if pixbuf is None:
        log.warning('Loading pixbuf failed')
        return None

    if size > pixbuf.get_width() and size > pixbuf.get_height():
        return data

    width, height = get_thumbnail_size(pixbuf, size)
    thumbnail = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
    if thumbnail is None:
        log.warning('scale_simple() returned None')
        return None

    try:
        _error, bytes_ = thumbnail.save_to_bufferv('png', [], [])
    except GLib.Error as err:
        log.warning('Saving pixbuf to buffer failed: %s', err)
        return None
    return bytes_


def _create_thumbnail_with_pil(data: bytes, size: int) -> bytes | None:
    # Reads data and returns thumbnail bytes in PNG format

    input_file = BytesIO(data)
    output_file = BytesIO()
    try:
        image = Image.open(input_file)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        log.warning('Decompression bomb detected: %s', error)
        raise
    except Exception as error:
        log.warning('making pil thumbnail failed: %s', error)
        input_file.close()
        output_file.close()
        return None

    image_width, image_height = image.size
    if size > image_width and size > image_height:
        image.close()
        input_file.close()
        output_file.close()
        return data

    try:
        image.thumbnail((size, size))
        image.save(
            output_file,
            format='png',
            optimize=True,
        )
    except Exception as error:
        log.warning('saving pil thumbnail failed: %s', error)
        return None

    bytes_ = output_file.getvalue()

    image.close()
    input_file.close()
    output_file.close()

    return bytes_


def get_thumbnail_size(pixbuf: GdkPixbuf.Pixbuf, size: int) -> tuple[int, int]:
    # Calculates the new thumbnail size while preserving the aspect ratio
    image_width = pixbuf.get_width()
    image_height = pixbuf.get_height()

    if image_width > image_height:
        if image_width > size:
            image_height = math.ceil(size / float(image_width) * image_height)
            image_width = int(size)
    else:
        if image_height > size:
            image_width = math.ceil(size / float(image_height) * image_width)
            image_height = int(size)

    return image_width, image_height
