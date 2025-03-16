# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app


class MainMenuButton(Gtk.MenuButton):
    def __init__(self) -> None:
        Gtk.MenuButton.__init__(
            self,
            halign=Gtk.Align.CENTER,
            margin_top=12,
            icon_name="open-menu-symbolic",
        )

        menu_model = app.window.get_main_menu()

        menu = Gtk.PopoverMenu.new_from_model_full(
            menu_model, Gtk.PopoverMenuFlags.NESTED
        )

        self.set_popover(menu)

        menu_toggle_action = app.window.lookup_action("toggle-menu-bar")
        assert menu_toggle_action is not None
        menu_toggle_action.connect("activate", self._on_menu_toggle_action)

        self.set_visible(not app.settings.get_app_setting("show_main_menu"))

    def _on_menu_toggle_action(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        self.set_visible(not app.settings.get_app_setting("show_main_menu"))
