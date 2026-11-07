# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import struct
import tempfile
import unittest
import zlib
from io import BytesIO
from pathlib import Path

import PIL.Image

from gajim.common.util.image import create_thumbnail
from gajim.common.util.image import ErrorType
from gajim.common.util.image import ImageTooLarge
from gajim.common.util.image import load_image
from gajim.common.util.image import MAX_OG_PIXELS
from gajim.common.util.image import NoLoaderFound
from gajim.common.util.image import PillowLoader
from gajim.common.util.image import PixbufLoader
from gajim.common.util.image import ScalingType

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
EXIF_ORIENTATION = 274


def _svg() -> bytes:
    return b'<svg xmlns="http://www.w3.org/2000/svg" width="100000" height="100000"><rect width="100000" height="100000" fill="red"/></svg>'


def _png(width: int, height: int, mode: str = "RGB") -> bytes:
    output = BytesIO()
    PIL.Image.new(mode, (width, height), "red").save(output, format="PNG")
    return output.getvalue()


def _jpeg(width: int, height: int, orientation: int | None = None) -> bytes:
    image = PIL.Image.new("RGB", (width, height), "blue")
    exif = PIL.Image.Exif()
    if orientation is not None:
        exif[EXIF_ORIENTATION] = orientation
    output = BytesIO()
    image.save(output, format="JPEG", exif=exif)
    return output.getvalue()


def _gif(durations: list[int]) -> bytes:
    frames = [
        PIL.Image.new("RGB", (40, 30), (60 * i, 0, 255 - 60 * i))
        for i in range(len(durations))
    ]
    output = BytesIO()
    frames[0].save(
        output,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
    )
    return output.getvalue()


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    chunk = chunk_type + data
    return struct.pack(">I", len(data)) + chunk + struct.pack(">I", zlib.crc32(chunk))


def _truncated_png(width: int, height: int) -> bytes:
    """A few hundred bytes that declare a huge image: the size in the header,
    then only the start of the pixel data. Loading it must fail before any
    memory for the pixels is allocated."""
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    idat = zlib.compress(bytes(256))
    return PNG_SIGNATURE + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", idat)


def _size_of_png(data: bytes) -> tuple[int, int]:
    assert data.startswith(PNG_SIGNATURE), "not a PNG file"
    with PIL.Image.open(BytesIO(data)) as image:
        assert image.format == "PNG"
        return image.size


class TempFileMixin:
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    def _write(self, name: str, data: bytes) -> Path:
        path = Path(self._tmp_dir.name) / name
        path.write_bytes(data)
        return path


class TestLoadImageWithPillow(unittest.TestCase):
    def test_png(self) -> None:
        pixbuf = load_image(
            _png(30, 20), onerror=ErrorType.RAISE, with_loader=PillowLoader
        )
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (30, 20))

    def test_unknown_format(self) -> None:
        with self.assertRaises(NoLoaderFound):
            load_image(
                b"this is not an image",
                onerror=ErrorType.RAISE,
                with_loader=PillowLoader,
            )

    def test_max_image_pixels(self) -> None:
        with self.assertRaises(ImageTooLarge):
            load_image(
                _png(300, 300),
                max_image_pixels=256 * 256,
                onerror=ErrorType.RAISE,
                with_loader=PillowLoader,
            )

        pixbuf = load_image(
            _png(256, 256),
            max_image_pixels=256 * 256,
            onerror=ErrorType.RAISE,
            with_loader=PillowLoader,
        )
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (256, 256))

    def test_declared_size_too_large(self) -> None:
        # 9000x9000 is above MAX_IMAGE_PIXELS (8192x8192)
        with self.assertRaises(ImageTooLarge):
            load_image(
                _truncated_png(9000, 9000),
                onerror=ErrorType.RAISE,
                with_loader=PillowLoader,
            )


class TestLoadImage(TempFileMixin, unittest.TestCase):
    def test_svg(self) -> None:
        with self.assertRaises(ImageTooLarge):
            load_image(_svg(), onerror=ErrorType.RAISE)

    def test_bytes(self) -> None:
        pixbuf = load_image(_png(30, 20), onerror=ErrorType.RAISE)
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (30, 20))

    def test_path(self) -> None:
        pixbuf = load_image(
            self._write("image.png", _png(30, 20)), onerror=ErrorType.RAISE
        )
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (30, 20))

    def test_scaling(self) -> None:
        pixbuf = load_image(_png(400, 200), size=100, onerror=ErrorType.RAISE)
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (100, 50))

        # DOWN never enlarges
        pixbuf = load_image(
            _png(50, 25), size=100, scaling=ScalingType.DOWN, onerror=ErrorType.RAISE
        )
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (50, 25))

        # UP_DOWN enlarges too
        pixbuf = load_image(_png(50, 25), size=100, onerror=ErrorType.RAISE)
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (100, 50))

    def test_embedded_orientation(self) -> None:
        # EXIF orientation 6 means the image has to be rotated by 90 degrees
        pixbuf = load_image(_jpeg(40, 20, orientation=6), onerror=ErrorType.RAISE)
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (20, 40))

    def test_unknown_format(self) -> None:
        self.assertIsNone(load_image(b"this is not an image"))
        with self.assertRaises(NoLoaderFound):
            load_image(b"this is not an image", onerror=ErrorType.RAISE)

    def test_declared_size_too_large(self) -> None:
        self.assertIsNone(load_image(_truncated_png(13000, 13000)))
        with self.assertRaises(ImageTooLarge):
            load_image(_truncated_png(13000, 13000), onerror=ErrorType.RAISE)

    def test_max_image_pixels(self) -> None:
        self.assertIsNone(load_image(_png(513, 512), max_image_pixels=MAX_OG_PIXELS))
        with self.assertRaises(ImageTooLarge):
            load_image(
                _png(513, 512),
                max_image_pixels=MAX_OG_PIXELS,
                onerror=ErrorType.RAISE,
            )

        pixbuf = load_image(
            _png(512, 512), max_image_pixels=MAX_OG_PIXELS, onerror=ErrorType.RAISE
        )
        self.assertEqual((pixbuf.get_width(), pixbuf.get_height()), (512, 512))


class TestCreateThumbnail(TempFileMixin, unittest.TestCase):
    LOADERS = (PillowLoader, PixbufLoader)

    def test_small_png_is_not_enlarged(self) -> None:
        # Images smaller than the thumbnail size keep their size, and the
        # result is still a PNG file (not raw pixel data)
        path = self._write("small.png", _png(200, 150, mode="RGBA"))
        for loader in self.LOADERS:
            with self.subTest(loader.__name__):
                thumbnail, _metadata = create_thumbnail(
                    path, None, 300, with_loader=loader
                )
                self.assertEqual(_size_of_png(thumbnail), (200, 150))

    def test_large_image_is_scaled_down(self) -> None:
        path = self._write("large.png", _png(2000, 1000))
        for loader in self.LOADERS:
            with self.subTest(loader.__name__):
                thumbnail, _metadata = create_thumbnail(
                    path, None, 300, with_loader=loader
                )
                self.assertEqual(_size_of_png(thumbnail), (300, 150))

    def test_jpeg_becomes_png(self) -> None:
        path = self._write("photo.jpg", _jpeg(600, 400))
        for loader in self.LOADERS:
            with self.subTest(loader.__name__):
                thumbnail, _metadata = create_thumbnail(
                    path, None, 300, with_loader=loader
                )
                self.assertEqual(_size_of_png(thumbnail), (300, 200))

    def test_photo_above_old_limit(self) -> None:
        # 20 megapixels, above the 4096x4096 limit of the first version,
        # like photos from current phone cameras
        path = self._write("photo_20mp.png", _png(5000, 4000, mode="L"))
        for loader in self.LOADERS:
            with self.subTest(create_thumbnail.__name__):
                thumbnail, _metadata = create_thumbnail(
                    path, None, 300, with_loader=loader
                )
                self.assertEqual(_size_of_png(thumbnail), (300, 240))

    def test_embedded_orientation(self) -> None:
        path = self._write("rotated.jpg", _jpeg(400, 200, orientation=6))
        for loader in self.LOADERS:
            with self.subTest(create_thumbnail.__name__):
                thumbnail, _metadata = create_thumbnail(
                    path, None, 300, with_loader=loader
                )
                self.assertEqual(_size_of_png(thumbnail), (150, 300))

    def test_animated_gif(self) -> None:
        path = self._write("animated.gif", _gif([100, 200, 300]))
        thumbnail, _metadata = create_thumbnail(
            path, None, 300, with_loader=PillowLoader
        )
        self.assertEqual(_size_of_png(thumbnail), (40, 30))
        with PIL.Image.open(BytesIO(thumbnail)) as image:
            self.assertFalse(getattr(image, "is_animated", False))

    def test_declared_size_too_large(self) -> None:
        path = self._write("bomb.png", _truncated_png(9000, 9000))
        for loader in self.LOADERS:
            with (
                self.subTest(create_thumbnail.__name__),
                self.assertRaises(Exception),  # noqa: B017
            ):
                create_thumbnail(path, None, 300, with_loader=loader)


class TestAnimatedImages(TempFileMixin, unittest.TestCase):
    def test_is_image_animated(self) -> None:
        self.assertTrue(
            PillowLoader.is_image_animated(self._write("a.gif", _gif([100, 100])))
        )
        self.assertFalse(
            PillowLoader.is_image_animated(self._write("s.gif", _gif([100])))
        )
        self.assertFalse(
            PillowLoader.is_image_animated(self._write("s.png", _png(10, 10)))
        )

    def test_extract_frames(self) -> None:
        path = self._write("animated.gif", _gif([100, 200, 300]))
        frames = PillowLoader.extract_frames(path)
        self.assertEqual([duration for _data, duration in frames], [100, 200, 300])
        for data, _duration in frames:
            with PIL.Image.open(BytesIO(data)) as frame:
                self.assertEqual(frame.format, "WEBP")
                self.assertEqual(frame.size, (40, 30))

    def test_extract_frames_too_large(self) -> None:
        path = self._write("animated.gif", _gif([100, 200]))
        with self.assertRaises(ImageTooLarge):
            PillowLoader.extract_frames(path, max_image_pixels=100)


if __name__ == "__main__":
    unittest.main()
