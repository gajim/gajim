# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from gajim.common.util import quarantine
from gajim.common.util.quarantine import copy_quarantine
from gajim.common.util.quarantine import get_quarantine_properties
from gajim.common.util.quarantine import set_quarantine


class TestQuarantine(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._file = Path(self._tmp_dir.name) / "download.zip"
        self._file.write_bytes(b"data")

    def tearDown(self) -> None:
        self._tmp_dir.cleanup()

    @patch.object(sys, "platform", "linux")
    def test_noop_on_other_platforms(self) -> None:
        with patch.object(quarantine, "_set_properties") as set_properties:
            set_quarantine(self._file)
            copy_quarantine(self._file, self._file)
        set_properties.assert_not_called()

    @unittest.skipUnless(sys.platform == "darwin", "macOS only")
    def test_set_quarantine(self) -> None:
        self.assertIsNone(get_quarantine_properties(self._file))

        set_quarantine(self._file)
        properties = get_quarantine_properties(self._file)
        assert properties is not None
        self.assertEqual(properties[quarantine.QUARANTINE_AGENT_NAME_KEY], "Gajim")
        self.assertEqual(
            properties[quarantine.QUARANTINE_TYPE_KEY],
            quarantine.QUARANTINE_TYPE_WEB_DOWNLOAD,
        )
        self.assertNotIn("LSQuarantineDataURL", properties)
        self.assertNotIn("LSQuarantineOriginURL", properties)

    @unittest.skipUnless(sys.platform == "darwin", "macOS only")
    def test_copy_quarantine(self) -> None:
        copy = self._file.with_name("copy.zip")
        copy.write_bytes(b"data")

        copy_quarantine(self._file, copy)
        self.assertIsNone(get_quarantine_properties(copy))

        set_quarantine(self._file)
        copy_quarantine(self._file, copy)
        properties = get_quarantine_properties(copy)
        assert properties is not None
        self.assertEqual(properties[quarantine.QUARANTINE_AGENT_NAME_KEY], "Gajim")

    @unittest.skipUnless(sys.platform == "darwin", "macOS only")
    def test_missing_file_is_logged(self) -> None:
        with self.assertLogs("gajim.c.util.quarantine", level="WARNING"):
            set_quarantine(self._file.with_name("missing.zip"))


if __name__ == "__main__":
    unittest.main()
