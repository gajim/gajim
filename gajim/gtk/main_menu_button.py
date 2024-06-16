# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app


class MainMenuButton(Gtk.MenuButton):
    def __init__(self) -> None:
        Gtk.MenuButton.__init__(
            self, halign=Gtk.Align.CENTER, no_show_all=True, margin_top=12
        )

        image = Gtk.Image.new_from_icon_name('open-menu-symbolic', Gtk.IconSize.BUTTON)
        self.set_image(image)

        self.set_menu_model(app.app.get_menubar())

        menu_toggle_action = app.window.lookup_action('toggle-menu-bar')
        assert menu_toggle_action is not None
        menu_toggle_action.connect('activate', self._on_menu_toggle_action)

        self.set_visible(not app.settings.get_app_setting('show_main_menu'))

    def _on_menu_toggle_action(
        self, _action: Gio.SimpleAction, _param: GLib.Variant | None
    ) -> None:
        if app.window.get_show_menubar():
            self.hide()
        else:
            self.show()
