# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gajim.common import configpaths

from gajim.gtk.avatar import AvatarStorage


class AvatarPathSecurityTest(unittest.TestCase):
    def test_accepts_only_contained_regular_hash_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            avatar_root = Path(temp_dir)
            avatar_hash = "a" * 40
            avatar_path = avatar_root / avatar_hash
            avatar_path.write_bytes(b"avatar")

            with patch.object(configpaths, "get", return_value=avatar_root):
                self.assertEqual(
                    AvatarStorage.get_avatar_path(avatar_hash),
                    avatar_path.resolve(),
                )
                self.assertIsNone(AvatarStorage.get_avatar_path("../outside"))
                self.assertIsNone(AvatarStorage.get_avatar_path("/outside"))

    def test_rejects_symlinked_hash_file(self) -> None:
        with (
            tempfile.TemporaryDirectory() as temp_dir,
            tempfile.NamedTemporaryFile() as target,
        ):
            avatar_root = Path(temp_dir)
            avatar_hash = "b" * 40
            (avatar_root / avatar_hash).symlink_to(target.name)

            with patch.object(configpaths, "get", return_value=avatar_root):
                self.assertIsNone(AvatarStorage.get_avatar_path(avatar_hash))


if __name__ == "__main__":
    unittest.main()
