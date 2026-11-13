# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import unittest

import gi

from gajim.common import i18n
from gajim.common.emoji import EmojiData


class EmojiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        i18n.init()

    def test_emoji_detection(self):
        # Emojis depend on emoji resource files shipped with Gtk
        try:
            gi.require_version("Gtk", "4.0")
        except Exception:
            self.skipTest("Gtk not available")

        gi.disable_legacy_autoinit()
        from gi.repository import Gtk

        Gtk.init()

        EmojiData.init()

        self.assertFalse(EmojiData.is_emoji(""))
        self.assertFalse(EmojiData.is_emoji("A"))
        self.assertFalse(EmojiData.is_emoji("1"))
        self.assertFalse(EmojiData.is_emoji("😃😃"))

        self.assertTrue(EmojiData.is_emoji("😃"))
        self.assertTrue(EmojiData.is_emoji("\U0001f56f\ufe0f"))
        # Gtk data contain only 0001F577 0000FE0F, check that emoji without
        # variant selector is still recognized as emoji
        self.assertTrue(EmojiData.is_emoji("\U0001f577"))

        self.assertFalse(EmojiData.contains_only_emojis("A"))
        self.assertFalse(EmojiData.contains_only_emojis(""))
        self.assertFalse(EmojiData.contains_only_emojis("😃😃 😃"))
        self.assertFalse(EmojiData.contains_only_emojis("😃😃", max_chars=1))

        self.assertTrue(EmojiData.contains_only_emojis("😃😃"))
        self.assertTrue(
            EmojiData.contains_only_emojis(
                "\U0001f3f4\U000e0067\U000e0062\U000e0065\U000e006e\U000e0067\U000e007f"
            )
        )
