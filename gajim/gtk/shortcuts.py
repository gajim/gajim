# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.builder import get_builder


class ShortcutsWindow:
    def __init__(self):
        transient = app.app.get_active_window()
        assert transient
        builder = get_builder("shortcuts_window.ui", self)
        self.window = cast(Gtk.Window, builder.get_object("shortcuts_window"))
        self.window.connect("close-request", self._on_close)
        self.window.set_transient_for(transient)
        self.window.present()

    def _on_close(self, _window: Gtk.Window) -> None:
        self.window = None
