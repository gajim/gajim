# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import datetime as dt
import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.util.user_strings import format_idle_time
from gajim.common.util.user_strings import get_uf_relative_time

from gajim.gtk.util.misc import container_remove_all

# Backwards compat import for Plugins
from gajim.gtk.window import GajimAppWindow as GajimAppWindow  # noqa: PLC0414

log = logging.getLogger("gajim.gtk.widgets")


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

        self.add_css_class("badge")
        self.add_css_class("badge-group")


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
        self.add_css_class("dimmed")
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


class TimeLabel(Gtk.Label):
    __gtype_name__ = "TimeLabel"

    def __init__(self) -> None:
        Gtk.Label.__init__(self)
        self._timestamp = None
        app.pulse_manager.add_callback(self.pulse)

    def do_unroot(self) -> None:
        app.pulse_manager.remove_callback(self.pulse)
        Gtk.Label.do_unroot(self)

    def set_timestamp(self, timestamp: dt.datetime) -> None:
        self._timestamp = timestamp
        self.pulse()

    def pulse(self) -> None:
        if self._timestamp is None:
            return
        rel_string = get_uf_relative_time(self._timestamp)
        self.set_text(rel_string)
