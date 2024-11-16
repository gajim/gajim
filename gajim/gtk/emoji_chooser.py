# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

from gi.repository import GLib
from gi.repository import Gtk


class EmojiChooser(Gtk.EmojiChooser):
    def __init__(self) -> None:
        Gtk.EmojiChooser.__init__(self)

        self._emoji_picked_func: Any = None

        self.connect("closed", self._on_closed)

    def set_emoji_picked_func(self, func: Any) -> None:
        self._emoji_picked_func = func
        self.connect("emoji-picked", self._emoji_picked_func)

    def _on_closed(self, _popover: Gtk.EmojiChooser) -> None:
        def _cleanup() -> None:
            parent = cast(Gtk.MenuButton, self.get_parent())
            parent.set_popover(None)
            self.disconnect_by_func(self._emoji_picked_func)
            self._emoji_picked_func = None

        GLib.idle_add(_cleanup)
