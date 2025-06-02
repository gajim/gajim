# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import datetime as dt
import logging

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.util.user_strings import format_idle_time

from gajim.gtk.builder import GajimBuilder
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import container_remove_all

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
        header_bar: bool = True,
    ) -> None:

        SignalManager.__init__(self)

        self._add_window_padding = add_window_padding

        window_size = app.settings.get_window_size(name)
        if window_size is not None:
            default_width, default_height = window_size

        self.window = Adw.ApplicationWindow(
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

        self._header_bar = None
        if header_bar:
            self._header_bar = Adw.HeaderBar()

        log.debug("Load Window: %s", name)

        self._ui = cast(GajimBuilder, None)

        self.window.add_css_class("gajim-app-window")

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
        self.window.set_visible(True)

    def close(self) -> None:
        self.window.close()

    def get_scale_factor(self) -> int:
        return self.window.get_scale_factor()

    def set_default_widget(self, widget: Gtk.Widget | None) -> None:
        self.window.set_default_widget(widget)

    def set_child(self, child: Gtk.Widget | None = None) -> None:
        if child is not None and self._add_window_padding:
            child.add_css_class("window-padding")

        if self._header_bar is not None:
            toolbar_view = Adw.ToolbarView(content=child)
            toolbar_view.add_top_bar(self._header_bar)
            self.window.set_content(toolbar_view)
        else:
            self.window.set_content(child)

    def get_header_bar(self) -> Adw.HeaderBar | None:
        return self._header_bar

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
        self._store_win_size()
        self._disconnect_all()
        self._cleanup()
        app.check_finalize(self.window)
        app.check_finalize(self)

        del self.window.wrapper  # pyright: ignore
        del self._ui
        del self.__default_controller
        del self.window

        return Gdk.EVENT_PROPAGATE

    def _store_win_size(self) -> None:
        app.settings.set_window_size(
            self.window.get_name(),
            self.window.props.default_width,
            self.window.props.default_height,
        )

    def _cleanup(self) -> None:
        raise NotImplementedError


class MultiLineLabel(Gtk.Label):
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        Gtk.Label.__init__(self, *args, **kwargs)
        self.set_wrap(True)
        self.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
        self.set_single_line_mode(False)
        self.set_selectable(True)


class GroupBadge(Gtk.Label):
    def __init__(self, group: str) -> None:
        Gtk.Label.__init__(
            self,
            ellipsize=Pango.EllipsizeMode.END,
            halign=Gtk.Align.END,
            hexpand=True,
            label=group,
            valign=Gtk.Align.CENTER,
            max_width_chars=20,
        )

        self.add_css_class("group")


class GroupBadgeBox(Gtk.Box):
    __gtype_name__ = "GroupBadgeBox"

    def __init__(self) -> None:
        Gtk.Box.__init__(self)

        self._groups: list[str] = []

    @GObject.Property(type=object)
    def groups(self) -> list[str]:  # pyright: ignore
        return self._groups

    @groups.setter
    def groups(self, groups: list[str] | None) -> None:
        if groups is None:
            groups = []

        self._groups = groups[:3]
        container_remove_all(self)
        visible = bool(groups)
        self.set_visible(visible)
        if not visible:
            return

        for group in self._groups:
            self.append(GroupBadge(group))


class IdleBadge(Gtk.Label):
    __gtype_name__ = "IdleBadge"

    def __init__(self, idle: dt.datetime | None = None) -> None:
        Gtk.Label.__init__(
            self,
            halign=Gtk.Align.START,
            hexpand=True,
            ellipsize=Pango.EllipsizeMode.NONE,
            visible=False,
        )
        self.set_size_request(50, -1)
        self.add_css_class("dim-label")
        self.add_css_class("small-label")

    @GObject.Property(type=object)
    def idle(self) -> str:  # pyright: ignore
        return self.get_text()

    @idle.setter
    def idle(self, value: dt.datetime | None) -> None:
        return self._set_idle(value)

    def _set_idle(self, value: dt.datetime | None) -> None:
        self.set_visible(bool(value))
        if value is None:
            return

        self.set_text(_("Last seen: %s") % format_idle_time(value))
        format_string = app.settings.get("date_time_format")
        self.set_tooltip_text(value.strftime(format_string))


class AccountBadge(Gtk.Label):
    __gtype_name__ = "AccountBadge"

    def __init__(self, account: str | None = None, bind_setting: bool = False) -> None:
        Gtk.Label.__init__(self)
        self.set_ellipsize(Pango.EllipsizeMode.END)
        self.set_max_width_chars(12)
        self.set_size_request(50, -1)
        self.add_css_class("badge")

        self._bind_setting = bind_setting

        if account is not None:
            self.set_account(account)

        self.set_visible(account is not None)

    def do_unroot(self) -> None:
        app.settings.disconnect_signals(self)
        Gtk.Label.do_unroot(self)
        app.check_finalize(self)

    @GObject.Property(type=str)
    def account(self) -> str:  # pyright: ignore
        return self.get_text()

    @account.setter
    def account(self, value: str) -> None:
        self.set_account(value)

    def set_account(self, account: str) -> None:
        label = app.get_account_label(account)
        self.set_text(label)

        for style_class in self.get_css_classes():
            if style_class.startswith("gajim_class"):
                self.remove_css_class(style_class)

        account_class = app.css_config.get_dynamic_class(account)
        self.add_css_class(account_class)

        self.set_tooltip_text(_("Account: %s") % label)
        if self._bind_setting:
            app.settings.disconnect_signals(self)
            app.settings.connect_signal(
                "account_label", self._on_account_label_changed, account
            )

    def _on_account_label_changed(
        self, _value: str, _setting: str, account: str | None, *args: Any
    ) -> None:

        assert account is not None
        self.set_account(account)


class GdkRectangle(Gdk.Rectangle):
    def __init__(self, x: int, y: int, height: int = 1, width: int = 1) -> None:

        Gdk.Rectangle.__init__(self)
        self.x = x
        self.y = y
        self.height = height
        self.width = width


class GajimPopover(Gtk.PopoverMenu):
    __gtype_name__ = "GajimPopover"

    def __init__(
        self,
        menu: Gio.MenuModel | None = None,
        position: Gtk.PositionType = Gtk.PositionType.RIGHT,
        event: Any | None = None,
    ) -> None:

        Gtk.PopoverMenu.__init__(self, autohide=True)

        if menu is not None:
            self.set_menu_model(menu)

        self.set_position(position)
        if event is not None:
            self.set_pointing_from_event(event)

    def set_pointing_from_event(self, event: Any) -> None:
        self.set_pointing_to_coord(event.x, event.y)

    def set_pointing_to_coord(self, x: float, y: float) -> None:
        rectangle = GdkRectangle(x=int(x), y=int(y))
        self.set_pointing_to(rectangle)

    def do_unroot(self) -> None:
        Gtk.PopoverMenu.do_unroot(self)
        app.check_finalize(self)
