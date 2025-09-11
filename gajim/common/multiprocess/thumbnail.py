# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import math
from io import BytesIO
from pathlib import Path

from gi.repository import GdkPixbuf
from gi.repository import GLib
from PIL import Image


def create_thumbnail(input_: bytes | Path,
    output: Path | None,
    size: int,
    mime_type: str
) -> tuple[bytes, dict[str, Any]]:

    if isinstance(input_, Path):
        data = input_.read_bytes()
    else:
        data = input_

    exceptions: list[Exception] = []
    thumbnail_bytes = None
    metadata = {}

    try:
        thumbnail_bytes, metadata = _create_thumbnail_with_pil(data, size)
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        # Don't try to process image further
        raise

    except Exception as exc1:
        exceptions.append(exc1)

    try:
        thumbnail_bytes, metadata = _create_thumbnail_with_pixbuf(data, size, mime_type)
    except Exception as exc2:
        exceptions.append(exc2)

    if exceptions:
        raise ExceptionGroup('Failed to generate thumbnail', exceptions)

    assert thumbnail_bytes is not None
    if output is not None:
        output.write_bytes(thumbnail_bytes)
    return thumbnail_bytes, metadata


def _create_thumbnail_with_pixbuf(
    data: bytes, size: int, mime_type: str
) -> tuple[bytes, dict[str, Any]]:
    # Reads data and returns thumbnail bytes in PNG format

    metadata: dict[str, Any] = {}

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
        return data, metadata

    width, height = get_thumbnail_size(pixbuf, size)
    thumbnail = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
    if thumbnail is None:
        raise ValueError('scale_simple() failed')

    _error, bytes_ = thumbnail.save_to_bufferv('png', [], [])

    return bytes_, metadata


def _create_thumbnail_with_pil(data: bytes, size: int) -> tuple[bytes, dict[str, Any]]:
    # Reads data and returns thumbnail bytes in PNG format

    metadata: dict[str, Any] = {}
    input_file = BytesIO(data)
    try:
        image = Image.open(input_file)
    except Exception:
        input_file.close()
        raise

    image_width, image_height = image.size
    if size > image_width and size > image_height:
        image.close()
        input_file.close()
        return data, metadata

    output_file = BytesIO()

    image.thumbnail((size, size))
    image.save(
        output_file,
        format='png',
        optimize=True,
    )

    bytes_ = output_file.getvalue()

    image.close()
    input_file.close()
    output_file.close()

    return bytes_, metadata


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
