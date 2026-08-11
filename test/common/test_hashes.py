# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from gajim.common.util.hashes import is_valid_sha1


class HashValidationTest(unittest.TestCase):
    def test_canonical_sha1(self) -> None:
        self.assertTrue(is_valid_sha1("0123456789abcdef" * 2 + "01234567"))

    def test_rejects_noncanonical_values(self) -> None:
        invalid_values = [
            "",
            "a" * 39,
            "a" * 41,
            "A" * 40,
            "g" * 40,
            "../" + "a" * 40,
            "/outside/" + "a" * 40,
        ]
        for value in invalid_values:
            with self.subTest(value=value):
                self.assertFalse(is_valid_sha1(value))


if __name__ == "__main__":
    unittest.main()
