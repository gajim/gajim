# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlparse

from gajim.common.util.preview import filename_from_uri
from gajim.common.util.preview import get_image_paths
from gajim.common.util.preview import guess_mime_type
from gajim.common.util.preview import is_audio

ORIG_DIR = Path("downloads")
THUMB_DIR = Path("thumbs")


def _get_paths(uri: str, size: int = 300) -> tuple[Path, Path]:
    return get_image_paths(uri, urlparse(uri), size, ORIG_DIR, THUMB_DIR)


def _hash(uri: str) -> str:
    return hashlib.sha1(uri.encode()).hexdigest()


class TestFilenameFromUri(unittest.TestCase):
    def test_plain(self) -> None:
        self.assertEqual(
            filename_from_uri("https://example.org/files/photo.jpg"), "photo.jpg"
        )

    def test_query_and_fragment(self) -> None:
        self.assertEqual(
            filename_from_uri("https://example.org/photo.jpg?size=large#top"),
            "photo.jpg",
        )

    def test_percent_encoded(self) -> None:
        self.assertEqual(
            filename_from_uri("https://example.org/my%20photo.jpg"), "my photo.jpg"
        )

    def test_aesgcm(self) -> None:
        uri = "aesgcm://example.org/upload/photo.jpg#" + "a" * 88
        self.assertEqual(filename_from_uri(uri), "photo.jpg")

    def test_encoded_query_and_fragment_chars(self) -> None:
        # An encoded "?" or "#" belongs to the name and must not hide the
        # real extension
        self.assertEqual(
            filename_from_uri("https://example.org/photo.jpg%3F.exe"),
            "photo.jpg?.exe",
        )
        self.assertEqual(
            filename_from_uri("https://example.org/photo.jpg%23.exe"),
            "photo.jpg#.exe",
        )

    def test_right_to_left_override(self) -> None:
        self.assertEqual(
            filename_from_uri("https://example.org/photo%E2%80%AEgpj.exe"),
            "photogpj.exe",
        )

    def test_no_path(self) -> None:
        self.assertEqual(filename_from_uri("https://example.org"), "")


class TestGetImagePaths(unittest.TestCase):
    def test_plain(self) -> None:
        uri = "https://example.org/files/photo.jpg"
        orig, thumb = _get_paths(uri)
        self.assertEqual(orig, ORIG_DIR / f"photo_{_hash(uri)}.jpg")
        self.assertEqual(thumb, THUMB_DIR / f"photo_{_hash(uri)}_thumb_300.png")

    def test_thumbnail_size_and_format(self) -> None:
        uri = "https://example.org/anim.gif"
        _orig, thumb = _get_paths(uri, size=600)
        self.assertEqual(thumb.name, f"anim_{_hash(uri)}_thumb_600.png")

    def test_query_not_in_name(self) -> None:
        uri = "https://example.org/photo.jpg?width=100"
        orig, _thumb = _get_paths(uri)
        self.assertEqual(orig, ORIG_DIR / f"photo_{_hash(uri)}.jpg")

    def test_hash_depends_on_full_uri(self) -> None:
        orig1, _thumb = _get_paths("https://example.org/a/photo.jpg")
        orig2, _thumb = _get_paths("https://example.org/b/photo.jpg")
        self.assertNotEqual(orig1, orig2)

    def test_no_extension(self) -> None:
        uri = "https://example.org/photo"
        orig, _thumb = _get_paths(uri)
        self.assertEqual(orig, ORIG_DIR / f"photo_{_hash(uri)}")

    def test_extension_length(self) -> None:
        orig, _thumb = _get_paths("https://example.org/a.abcdefghij")
        self.assertEqual(orig.suffix, ".abcdefghij")

        orig, _thumb = _get_paths("https://example.org/a.abcdefghijk")
        self.assertEqual(orig.suffix, "")

    def test_unsafe_extension_dropped(self) -> None:
        # ":" would create an NTFS alternate data stream on Windows
        orig, _thumb = _get_paths("https://example.org/a.png%3Aads")
        self.assertNotIn(":", orig.name)
        self.assertEqual(orig.suffix, "")

        # Right-to-left override in the extension
        orig, _thumb = _get_paths("https://example.org/a.%E2%80%AEgpj")
        self.assertNotIn("\u202e", orig.name)
        self.assertEqual(orig.suffix, "")

    @patch.object(sys, "platform", "linux")
    def test_same_extension_as_displayed(self) -> None:
        # The saved file must have the extension the user is shown
        uri = "https://example.org/photo.jpg%3F.exe"
        orig, _thumb = _get_paths(uri)
        self.assertEqual(orig.suffix, Path(filename_from_uri(uri)).suffix)
        self.assertEqual(orig.suffix, ".exe")

    def test_stays_in_directory(self) -> None:
        uri = "https://example.org/..%2F..%2Fetc%2Fpasswd.jpg"
        orig, thumb = _get_paths(uri)
        self.assertEqual(orig.parent, ORIG_DIR)
        self.assertEqual(thumb.parent, THUMB_DIR)
        self.assertEqual(orig.name, f"passwd_{_hash(uri)}.jpg")


class TestGuessMimeType(unittest.TestCase):
    def test_m4a_on_macos(self) -> None:
        # Python's mimetypes reads /etc/apache2/mime.types on macOS,
        # which maps .m4a to audio/mp4a-latm
        with patch("mimetypes.guess_type", return_value=("audio/mp4a-latm", None)):
            mime_type = guess_mime_type("voice.m4a")
        self.assertEqual(mime_type, "audio/mp4")
        self.assertTrue(is_audio(mime_type))

    def test_m4a_received_as_mp4a_latm(self) -> None:
        # Files uploaded by macOS clients may carry this content type
        self.assertTrue(is_audio("audio/mp4a-latm"))


if __name__ == "__main__":
    unittest.main()
