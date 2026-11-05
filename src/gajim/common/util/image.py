# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast
from typing import Literal
from typing import overload

import io
import logging
import math
from enum import IntEnum
from io import BytesIO
from pathlib import Path

import PIL
import PIL.Image
import PIL.ImageFile
from gi.repository import GdkPixbuf
from gi.repository import GLib

log = logging.getLogger("gajim.c.util.image")

MAX_IMAGE_PIXELS = 4096 * 4096
# If the number of pixels is greater than twice MAX_IMAGE_PIXELS,
# then a DecompressionBombError will be raised instead.
PIL.Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
PIL.ImageFile.LOAD_TRUNCATED_IMAGES = True


class ErrorType(IntEnum):
    RAISE = 0
    LOG = 1


class ScalingType(IntEnum):
    UP = 0
    DOWN = 1
    UP_DOWN = 2


class ImageTooLarge(Exception):
    pass


class UnknownImageFormat(Exception):
    pass


def get_pixbuf_mime_types() -> set[str]:
    pixbuf_mime_types: set[str] = set()

    for fmt in GdkPixbuf.Pixbuf.get_formats():
        mime_types = fmt.get_mime_types()
        if not mime_types:
            continue
        for mime_type in mime_types:
            pixbuf_mime_types.add(mime_type.lower())

    return pixbuf_mime_types


def get_pillow_mime_types() -> set[str]:
    pil_mime_types: set[str] = set()

    PIL.Image.init()
    for mime_type in PIL.Image.MIME.values():
        pil_mime_types.add(mime_type.lower())

    return set(filter(lambda mime_type: mime_type.startswith("image"), pil_mime_types))


def _load_image_with_pixbuf(
    file: Path | bytes, *, max_image_pixels: int = MAX_IMAGE_PIXELS
) -> GdkPixbuf.Pixbuf:
    size_prepare_exception = None

    def _on_size_prepared(
        loader: GdkPixbuf.PixbufLoader, width: int, height: int
    ) -> None:
        # Raising an Exception in this handler will not propagate
        nonlocal size_prepare_exception

        if width * height <= max_image_pixels:
            return

        size_prepare_exception = ImageTooLarge(f"Image too large: {width}x{height}")
        # A size of 0 makes the loader stop with an error
        loader.set_size(0, 0)

    pixbufloader = GdkPixbuf.PixbufLoader()
    pixbufloader.connect("size-prepared", _on_size_prepared)

    if isinstance(file, Path):
        file = file.read_bytes()

    try:
        pixbufloader.write(file)
        pixbufloader.close()
        pixbuf = pixbufloader.get_pixbuf()
    except GLib.Error:
        pixbufloader.close()

        if size_prepare_exception is not None:
            raise size_prepare_exception

        log.warning(
            "Loading image data using PixbufLoader failed. "
            "Trying to convert image data using Pillow."
        )

        image = load_image_with_pillow(file, max_image_pixels=max_image_pixels)
        pixbuf = convert_image_to_pixbuf(image, has_alpha=True)

    if pixbuf is None:
        raise ValueError("Unexpected error while loading image")

    pixbuf = pixbuf.apply_embedded_orientation()
    assert pixbuf is not None
    return pixbuf


def load_image_with_pillow(
    file: Path | BytesIO | bytes, *, max_image_pixels: int = MAX_IMAGE_PIXELS
) -> PIL.Image.Image:
    if isinstance(file, bytes):
        file = BytesIO(file)

    # The context manager makes sure that the pointer to the file is removed
    # See https://pillow.readthedocs.io/en/stable/reference/open_files.html#file-handling
    try:
        with PIL.Image.open(file) as image:
            if image.width * image.height > max_image_pixels:
                raise ImageTooLarge(f"Image too large: {image.width}x{image.height}")
            image.load()
    except PIL.UnidentifiedImageError:
        raise UnknownImageFormat

    return cast(PIL.Image.Image, image)


def convert_image_to_pixbuf(
    image: PIL.Image.Image, *, has_alpha: bool, rowstride: int = 4
) -> GdkPixbuf.Pixbuf:
    width, height = image.size
    image = image.convert("RGBA" if has_alpha else "RGB")
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(image.tobytes()),
        GdkPixbuf.Colorspace.RGB,
        has_alpha,
        8,
        width,
        height,
        width * rowstride,
    )


@overload
def load_image(
    file: Path | bytes,
    *,
    size: int | None = None,
    scaling: ScalingType = ScalingType.UP_DOWN,
    max_image_pixels: int = MAX_IMAGE_PIXELS,
    onerror: Literal[ErrorType.LOG],
) -> GdkPixbuf.Pixbuf | None: ...
@overload
def load_image(
    file: Path | bytes,
    *,
    size: int | None = None,
    scaling: ScalingType = ScalingType.UP_DOWN,
    max_image_pixels: int = MAX_IMAGE_PIXELS,
    onerror: Literal[ErrorType.RAISE],
) -> GdkPixbuf.Pixbuf: ...
@overload
def load_image(
    file: Path | bytes,
    *,
    size: int | None = None,
    scaling: ScalingType = ScalingType.UP_DOWN,
    max_image_pixels: int = MAX_IMAGE_PIXELS,
    onerror: ... = ErrorType.LOG,
) -> GdkPixbuf.Pixbuf | None: ...
def load_image(
    file: Path | bytes,
    *,
    size: int | None = None,
    scaling: ScalingType = ScalingType.UP_DOWN,
    max_image_pixels: int = MAX_IMAGE_PIXELS,
    onerror: ErrorType = ErrorType.LOG,
) -> GdkPixbuf.Pixbuf | None:
    try:
        pixbuf = _load_image_with_pixbuf(file, max_image_pixels=max_image_pixels)
    except Exception as error:
        if onerror == ErrorType.RAISE:
            raise
        log.error("Unable to load image: %s", error)
        return None

    if size is None:
        return pixbuf

    return scale_pixbuf(pixbuf, size, scaling)


def _scale_with_ratio(
    size: int, width: int, height: int, scaling: ScalingType
) -> tuple[int, int, bool]:
    if scaling == ScalingType.UP_DOWN:
        if size == width and size == height:
            return width, height, False

        if height == width:
            return size, size, True

    elif scaling == ScalingType.UP:
        if size <= width and size <= height:
            return width, height, False

    elif scaling == ScalingType.DOWN:
        if size >= width and size >= height:
            return width, height, False

    else:
        raise ValueError(f"Unknown scaling type: {scaling}")

    if height > width:
        ratio = height / float(width)
        return math.ceil(size / ratio), size, True

    ratio = width / float(height)
    return size, math.ceil(size / ratio), True


def scale_pixbuf(
    pixbuf: GdkPixbuf.Pixbuf, size: int, scaling: ScalingType
) -> GdkPixbuf.Pixbuf:
    width = pixbuf.get_width()
    height = pixbuf.get_height()
    width, height, scaling_needed = _scale_with_ratio(size, width, height, scaling)
    pixbuf_ = pixbuf
    if scaling_needed:
        pixbuf_ = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        assert pixbuf_ is not None
    return pixbuf_


def image_size(image_path: Path) -> tuple[int, int]:
    try:
        with PIL.Image.open(image_path) as image:
            return image.size
    except Exception:
        log.warning("Could not determine image size for %s", image_path, exc_info=True)
        return 0, 0


def is_image_animated(image_path: Path) -> bool:
    try:
        with PIL.Image.open(image_path) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ImageTooLarge(f"Image too large: {image.width}x{image.height}")

            n_frames: int = getattr(image, "n_frames", 1)
            return getattr(image, "is_animated", False) and n_frames > 1
    except Exception:
        log.warning(
            "Could not determine if image is animated: %s", image_path, exc_info=True
        )
        return False


def get_image_orientation(image: PIL.Image.Image) -> int:
    exif = image.getexif()
    exif_orientation_code = 274
    orientation = exif.get(exif_orientation_code, 1)
    degrees = {1: 0, 3: 180, 6: 270, 8: 90}.get(orientation, 0)

    return degrees


def apply_embedded_orientation(image: PIL.Image.Image) -> PIL.Image.Image:
    image_orientation = get_image_orientation(image)
    if image_orientation != 0:
        image = image.rotate(image_orientation, expand=True)
    return image


def create_thumbnail_with_pillow(file: Path | bytes, size: int) -> bytes:
    image = load_image_with_pillow(file)
    image = apply_embedded_orientation(image)
    if image.format == "PNG" and size >= image.width and size >= image.height:
        # Fast path if there is no need for scaling or conversion
        return image.tobytes()

    output = BytesIO()
    image.thumbnail((size, size))
    image.save(output, format="PNG", optimize=True, save_all=False)
    return output.getvalue()


def create_thumbnail_with_pixbuf(file: Path | bytes, size: int) -> bytes:
    pixbuf = _load_image_with_pixbuf(file)
    pixbuf = scale_pixbuf(pixbuf, size, ScalingType.DOWN)
    _error, bytes_ = pixbuf.save_to_bufferv("png", [], [])
    return bytes_


def extract_frames_with_pillow(
    path: Path, *, max_image_pixels: int = MAX_IMAGE_PIXELS
) -> list[tuple[bytes, int]]:
    with PIL.Image.open(path) as image:
        n_frames: int = getattr(image, "n_frames", 1)

        frames: list[tuple[bytes, int]] = []
        for i in range(n_frames):
            image.seek(i)
            frame = image.copy()
            if frame.width * frame.height > max_image_pixels:
                raise ImageTooLarge(f"Image too large: {frame.width}x{frame.height}")

            with io.BytesIO() as byte_io:
                frame.save(
                    byte_io,
                    format="WEBP",
                    lossless=False,
                    method=0,
                    exact=False,
                    quality=50,
                    alpha_quality=50,
                )
                frame_bytes = byte_io.getvalue()
            duration_ms = int(frame.info.get("duration", 100))
            frames.append((frame_bytes, duration_ms))
            del frame

    return frames
