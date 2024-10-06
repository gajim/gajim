# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.util import iterate_children


class GajimAppWindow(Gtk.ApplicationWindow):
    def __init__(
        self,
        *,
        name: str,
        title: str | None = None,
        default_width: int = -1,
        default_height: int = 1,
        transient_for: Gtk.Window | None = None,
        add_window_padding: bool = True,
    ) -> None:
        Gtk.ApplicationWindow.__init__(
            self,
            application=app.app,
            resizable=True,
            name=name,
            title=title,
            default_width=default_width,
            default_height=default_height,
            transient_for=transient_for,
        )
        self.add_css_class('gajim-app-window')

        if add_window_padding:
            self.add_css_class('window-padding')

        self.__main_box = Gtk.Box()
        super().set_child(self.__main_box)

        self.__default_controller = Gtk.EventControllerKey(
            propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self.__default_controller.connect('key-pressed', self.__on_key_pressed)
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

    def __on_key_pressed(
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
