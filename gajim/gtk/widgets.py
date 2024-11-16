# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

import logging

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.builder import GajimBuilder
from gajim.gtk.util import SignalManager

log = logging.getLogger("gajim.gtk.widgets")


class GajimAppWindow(SignalManager):
    def __init__(
        self,
        *,
        name: str,
        title: str | None = None,
        default_width: int = 0,
        default_height: int = 0,
        transient_for: Gtk.Window | None = None,
        modal: bool = False,
        add_window_padding: bool = True,
    ) -> None:

        SignalManager.__init__(self)

        self.window = Gtk.ApplicationWindow(
            application=app.app,
            resizable=True,
            name=name,
            title=title,
            default_width=default_width,
            default_height=default_height,
            transient_for=transient_for,
            modal=modal,
        )
        # Hack to get the instance in get_app_window
        self.window.wrapper = self  # pyright: ignore

        log.debug("Load Window: %s", name)

        self._ui = cast(GajimBuilder, None)

        self.window.add_css_class("gajim-app-window")

        if add_window_padding:
            self.window.add_css_class("window-padding")

        self.window.set_child(Gtk.Box())

        self.__default_controller = Gtk.EventControllerKey(
            propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self.window.add_controller(self.__default_controller)

        self._connect_after(
            self.__default_controller, "key-pressed", self.__on_key_pressed
        )
        self._connect_after(self.window, "close-request", self.__on_close_request)

    def present(self) -> None:
        self.window.present()

    def show(self) -> None:
        self.window.show()

    def close(self) -> None:
        self.window.close()

    def get_scale_factor(self) -> int:
        return self.window.get_scale_factor()

    def set_default_widget(self, widget: Gtk.Widget | None) -> None:
        self.window.set_default_widget(widget)

    def set_child(self, child: Gtk.Widget | None = None) -> None:
        box = cast(Gtk.Box, self.window.get_child())
        current_child = box.get_first_child()
        if current_child is not None:
            box.remove(current_child)

        if child is None:
            return

        box.append(child)

    def get_default_controller(self) -> Gtk.EventController:
        return self.__default_controller

    def __on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:

        if keyval == Gdk.KEY_Escape:
            self.window.close()
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE

    def __on_close_request(self, _widget: Gtk.ApplicationWindow) -> bool:
        log.debug("Initiate Cleanup: %s", self.window.get_name())
        self._disconnect_all()
        self._cleanup()
        app.check_finalize(self.window)
        app.check_finalize(self)

        del self.window.wrapper  # pyright: ignore
        del self._ui
        del self.__default_controller
        del self.window

        return Gdk.EVENT_PROPAGATE

    def _cleanup(self) -> None:
        raise NotImplementedError
