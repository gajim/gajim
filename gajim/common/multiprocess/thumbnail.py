# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import math
from io import BytesIO
from pathlib import Path

from gi.repository import GdkPixbuf
from gi.repository import GLib
from PIL import Image


def create_thumbnail(data: bytes | Path, size: int, mime_type: str) -> bytes:
    # Create thumbnail from bytes or Path and return bytes in PNG format

    if isinstance(data, Path):
        data = data.read_bytes()

    exceptions: list[Exception] = []

    try:
        return _create_thumbnail_with_pil(data, size)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        # Don't try to process image further
        raise

    except Exception as exc1:
        exceptions.append(exc1)

    try:
        return _create_thumbnail_with_pixbuf(data, size, mime_type)
    except Exception as exc2:
        exceptions.append(exc2)

    raise ExceptionGroup('Failed to generate thumbnail', exceptions)


def _create_thumbnail_with_pixbuf(
    data: bytes, size: int, mime_type: str
) -> bytes:
    # Reads data and returns thumbnail bytes in PNG format

    try:
        # Try to create GdKPixbuf loader with fixed mime-type to
        # fix mime-type detection for HEIF images on some systems
        loader = GdkPixbuf.PixbufLoader.new_with_mime_type(mime_type)
    except GLib.Error:
        loader = GdkPixbuf.PixbufLoader()

    loader.write(data)
    loader.close()

    pixbuf = loader.get_pixbuf()
    if pixbuf is None:
        raise ValueError('Loading pixbuf failed')

    if size > pixbuf.get_width() and size > pixbuf.get_height():
        return data

    width, height = get_thumbnail_size(pixbuf, size)
    thumbnail = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
    if thumbnail is None:
        raise ValueError('scale_simple() failed')

    _error, bytes_ = thumbnail.save_to_bufferv('png', [], [])

    return bytes_


def _create_thumbnail_with_pil(data: bytes, size: int) -> bytes:
    # Reads data and returns thumbnail bytes in PNG format

    input_file = BytesIO(data)
    try:
        image = Image.open(input_file)
    except Exception:
        input_file.close()
        raise

    input_file.close()

    image_width, image_height = image.size
    if size > image_width and size > image_height:
        image.close()
        return data

    output_file = BytesIO()

    image.thumbnail((size, size))
    image.save(
        output_file,
        format='png',
        optimize=True,
    )

    bytes_ = output_file.getvalue()

    image.close()
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
