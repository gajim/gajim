# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

import logging
import math
from io import BytesIO
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from PIL import Image
from PIL import ImageFile
from PIL import UnidentifiedImageError

log = logging.getLogger('gajim.c.util.image')

ImageFile.LOAD_TRUNCATED_IMAGES = True


def get_texture_from_file(
    path: str | Path,
    size: int | None = None
) -> Gdk.Texture | None:
    pixbuf = get_pixbuf_from_file(path, size)
    if pixbuf is None:
        return None
    return Gdk.Texture.new_for_pixbuf(pixbuf)


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
                img = Image.open(image_handle)
                converted_image = img.convert('RGBA')
        except (NameError, OSError, UnidentifiedImageError):
            log.warning('Pillow convert failed: %s', path)
            log.debug('Error', exc_info=True)
            return None

        array = GLib.Bytes.new(converted_image.tobytes())
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


def get_texture_from_data(data: bytes, size: int | None = None) -> Gdk.Texture | None:
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
            image = Image.open(BytesIO(data)).convert('RGBA')
            array = GLib.Bytes.new(image.tobytes())
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
    assert pixbuf is not None

    if size is not None:
        width, height = scale_with_ratio(size, pixbuf.get_width(), pixbuf.get_height())
        pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        assert pixbuf is not None

    return Gdk.Texture.new_for_pixbuf(pixbuf)


def scale_with_ratio(size: int, width: int, height: int) -> tuple[int, int]:
    if height == width:
        return size, size
    if height > width:
        ratio = height / float(width)
        return int(size / ratio), size

    ratio = width / float(height)
    return size, int(size / ratio)


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
        # Disabled after port to Gtk4
        # if image.format == 'GIF' and image.n_frames > 1:
        #     assert isinstance(image, ImageFile.ImageFile)
        #     resize_gif(image, output_file, (size, size))
        # else:
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


def resize_gif(
    image: ImageFile.ImageFile, output_file: BytesIO, resize_to: tuple[int, int]
) -> None:
    frames, result = extract_and_resize_frames_from_gif(image, resize_to)

    frames[0].save(
        output_file,
        format='GIF',
        optimize=True,
        save_all=True,
        append_images=frames[1:],
        duration=result['duration'],
        loop=1000,
    )


def extract_and_resize_frames_from_gif(
    image: ImageFile.ImageFile, resize_to: tuple[int, int]
) -> tuple[list[Image.Image], dict[str, str | int | tuple[int, int]]]:

    image, result = analyse_gif_image(image)

    i = 0
    palette = image.getpalette()
    last_frame = image.convert('RGBA')

    frames: list[Image.Image] = []

    try:
        while True:
            # If the GIF uses local colour tables,
            # each frame will have its own palette.
            # If not, we need to apply the global palette to the new frame.

            if not image.getpalette():  # type: ignore
                assert palette is not None
                image.putpalette(palette)

            new_frame = Image.new('RGBA', image.size)

            # Is this file a "partial"-mode GIF where frames update a region
            # of a different size to the entire image?
            # If so, we need to construct the new frame by
            # pasting it on top of the preceding frames.

            if result['mode'] == 'partial':
                new_frame.paste(last_frame)

            new_frame.paste(image, (0, 0), image.convert('RGBA'))

            # This method preservs aspect ratio
            new_frame.thumbnail(resize_to, Image.Resampling.LANCZOS)
            frames.append(new_frame)

            i += 1
            last_frame = new_frame
            image.seek(image.tell() + 1)
    except EOFError:
        pass

    return frames, result


def analyse_gif_image(
    image: ImageFile.ImageFile,
) -> tuple[ImageFile.ImageFile, dict[str, str | int | tuple[int, int]]]:
    '''
    Pre-process pass over the image to determine the mode (full or additive).
    Necessary as assessing single frames isn't reliable. Need to know the mode
    before processing all frames.
    '''

    duration = cast(int, image.info.get('duration', 0))  # type: ignore
    result = {
        'size': image.size,
        'mode': 'full',
        'duration': duration,
    }

    try:
        while True:
            if image.tile:  # type: ignore
                tile = image.tile[0]  # type: ignore
                update_region = tile[1]  # type: ignore
                update_region_dimensions = update_region[2:]  # type: ignore
                if update_region_dimensions != image.size:
                    result['mode'] = 'partial'
                    break
            image.seek(image.tell() + 1)
    except EOFError:
        image.seek(0)
    return image, result
