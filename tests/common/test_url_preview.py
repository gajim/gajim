# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from gajim.common.multiprocess.url_preview import is_og_image_allowed

# IP literals, so no DNS lookup is needed
PUBLIC_PAGE = "https://8.8.8.8/article"
PRIVATE_PAGE = "http://192.168.1.10/intranet"


class TestOgImageAllowed(unittest.TestCase):
    def test_public_image(self) -> None:
        self.assertTrue(
            is_og_image_allowed(PUBLIC_PAGE, "https://1.1.1.1/a.png", False)
        )

    def test_relative_image(self) -> None:
        # og:image must be an absolute URL
        for image in ("/img/a.png", "//1.1.1.1/a.png"):
            with self.subTest(image):
                self.assertFalse(is_og_image_allowed(PUBLIC_PAGE, image, False))

    def test_public_page_private_image(self) -> None:
        for image in (
            "https://127.0.0.1:8767/secret.png",
            "https://192.168.1.1/snapshot.jpg",
            "https://169.254.169.254/latest/meta-data",
            "https://[::1]/secret.png",
        ):
            with self.subTest(image):
                self.assertFalse(is_og_image_allowed(PUBLIC_PAGE, image, False))

    def test_private_page_private_image(self) -> None:
        # Intranet pages keep their previews
        self.assertTrue(
            is_og_image_allowed(PRIVATE_PAGE, "http://192.168.1.20/a.png", False)
        )

    def test_scheme(self) -> None:
        for image in (
            "http://1.1.1.1/a.png",
            "file:///etc/passwd",
            "data:image/png;base64,AAAA",
        ):
            with self.subTest(image):
                self.assertFalse(is_og_image_allowed(PUBLIC_PAGE, image, False))

    def test_invalid_url(self) -> None:
        self.assertFalse(is_og_image_allowed(PUBLIC_PAGE, "https://[::1/a.png", False))

    def test_proxy(self) -> None:
        # With a proxy, hosts are resolved by the proxy (same as redirects)
        self.assertTrue(
            is_og_image_allowed(PUBLIC_PAGE, "https://127.0.0.1/a.png", True)
        )


if __name__ == "__main__":
    unittest.main()
