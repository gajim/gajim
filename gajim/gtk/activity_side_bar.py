# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from gajim.gtk.activity_list import ActivityList
from gajim.gtk.util.classes import SignalManager


class ActivitySideBar(Gtk.Box, SignalManager):
    def __init__(self, activity_list: ActivityList) -> None:
        Gtk.Box.__init__(
            self,
            tooltip_text=_("Activity"),
            height_request=AvatarSize.ACCOUNT_SIDE_BAR + 12,
        )
        SignalManager.__init__(self)

        self.add_css_class("activity-sidebar")

        activity_list.connect("unread-count-changed", self._on_unread_count_changed)

        gesture_primary_click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        self._connect(gesture_primary_click, "pressed", self._on_button_press)
        self.add_controller(gesture_primary_click)

        hover_controller = Gtk.EventControllerMotion()
        self._connect(hover_controller, "enter", self._on_cursor_enter)
        self._connect(hover_controller, "leave", self._on_cursor_leave)
        self.add_controller(hover_controller)

        container = Gtk.Box()

        self._selection_bar = Gtk.Box(width_request=6, margin_start=1)
        self._selection_bar.add_css_class("selection-bar")
        container.append(self._selection_bar)

        texture = app.app.avatar_storage.get_activity_sidebar_icon(
            AvatarSize.ACCOUNT_SIDE_BAR, self.get_scale_factor()
        )
        image = Gtk.Image.new_from_paintable(texture)
        image.set_pixel_size(AvatarSize.ACCOUNT_SIDE_BAR)
        container.append(image)

        self._unread_label = Gtk.Label(
            halign=Gtk.Align.END, valign=Gtk.Align.START, visible=False
        )
        self._unread_label.add_css_class("unread-counter")

        overlay = Gtk.Overlay()
        overlay.set_child(container)
        overlay.add_overlay(self._unread_label)

        self.append(overlay)

    def set_unread_count(self, count: int) -> None:
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text("999+")
        self._unread_label.set_visible(bool(count))

    def select(self) -> None:
        self._selection_bar.add_css_class("selection-bar-selected")

    def unselect(self) -> None:
        self._selection_bar.remove_css_class("selection-bar-selected")

    def _on_unread_count_changed(self, _widget: ActivityList, count: int) -> None:
        self.set_unread_count(count)

    def _on_cursor_enter(
        self,
        _controller: Gtk.EventControllerMotion,
        _x: int,
        _y: int,
    ) -> None:
        self._selection_bar.add_css_class("selection-bar-hover")

    def _on_cursor_leave(self, _controller: Gtk.EventControllerMotion) -> None:
        self._selection_bar.remove_css_class("selection-bar-hover")

    def _on_button_press(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> int:
        app.window.show_activity_page()
        return True
