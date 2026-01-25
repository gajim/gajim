# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import check_finalize

log = logging.getLogger("gajim.gtk.window")


class GajimAppWindow(Adw.ApplicationWindow, SignalManager):
    __gtype_name__ = "GajimAppWindow"

    def __init__(
        self,
        *,
        name: str,
        title: str | None = None,
        default_width: int = 0,
        default_height: int = 0,
        transient_for: Gtk.Window | None = None,
        modal: bool = False,
        add_window_padding: bool = False,
        header_bar: bool = False,
    ) -> None:
        SignalManager.__init__(self)

        self._add_window_padding = add_window_padding

        self._header_bar = None
        if header_bar:
            self._header_bar = Adw.HeaderBar()

        window_size = app.settings.get_window_size(name)
        if window_size is not None:
            default_width, default_height = window_size

        Adw.ApplicationWindow.__init__(
            self,
            application=app.app,
            resizable=True,
            name=name,
            title=title,
            default_width=default_width,
            default_height=default_height,
            transient_for=transient_for,
            modal=modal,
        )

        log.debug("Load Window: %s", name)

        self.add_css_class("gajim-app-window")

        self.__default_controller = Gtk.EventControllerKey(
            propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self.add_controller(self.__default_controller)

        self._connect_after(
            self.__default_controller, "key-pressed", self.__on_key_pressed
        )
        self._connect_after(self, "close-request", self.__on_close_request)

    def set_child(self, child: Gtk.Widget | None = None) -> None:
        if child is not None and self._add_window_padding:
            child.add_css_class("window-padding")

        if self._header_bar is not None:
            toolbar_view = Adw.ToolbarView(content=child)
            toolbar_view.add_top_bar(self._header_bar)
            self.set_content(toolbar_view)
        else:
            self.set_content(child)

    def get_default_controller(self) -> Gtk.EventController:
        return self.__default_controller

    def get_header_bar(self) -> Adw.HeaderBar | None:
        return self._header_bar

    def __on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Escape:
            self.close()
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE

    def __on_close_request(self, _widget: Adw.ApplicationWindow) -> bool:
        log.debug("Initiate Cleanup: %s", self.get_name())
        self._store_win_size()
        self._disconnect_all()
        self._cleanup()
        check_finalize(self)

        del self.__default_controller

        return Gdk.EVENT_PROPAGATE

    def _store_win_size(self) -> None:
        app.settings.set_window_size(
            self.get_name(),
            self.props.default_width,
            self.props.default_height,
        )

    def _cleanup(self) -> None:
        raise NotImplementedError
