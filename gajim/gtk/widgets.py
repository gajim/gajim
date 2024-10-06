# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.gtk.util import iterate_children


class GajimAppWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        *,
        name: str,
        application: Gtk.Application,
        title: str,
    ) -> None:
        Gtk.ApplicationWindow.__init__(
            self,
            name=name,
            application=application,
            title=title,
            resizable=True,
        )

        self.add_css_class('gajim-app-window')

        self.__main_box = Gtk.Box()
        super().set_child(self.__main_box)

        self.__default_controller = Gtk.EventControllerKey()
        self.__default_controller.connect('key-pressed', self._on_key_pressed)
        self.add_controller(self.__default_controller)

    def set_child(self, child: Gtk.Widget | None = None) -> None:
        children = list(iterate_children(self.__main_box))
        for c in children:
            self.__main_box.remove(c)

        if child is None:
            return

        self.__main_box.append(child)

    def get_default_controller(self) -> Gtk.EventController:
        return self.__default_controller

    def _on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.destroy()
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE
