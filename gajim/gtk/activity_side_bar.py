# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from gajim.gtk.activity_list import ActivityListView
from gajim.gtk.chat_list_stack import ChatListStack
from gajim.gtk.chat_page import ChatPage
from gajim.gtk.util.classes import SignalManager


class ActivitySideBar(Gtk.Box, SignalManager):
    def __init__(self, chat_page: ChatPage) -> None:
        Gtk.Box.__init__(
            self,
            tooltip_text=_("Activity"),
            height_request=AvatarSize.ACCOUNT_SIDE_BAR + 12,
        )
        SignalManager.__init__(self)

        self.add_css_class("activity-sidebar")

        activity_list = chat_page.get_activity_list()
        activity_list.connect("notify::unread-count", self._on_unread_count_changed)

        chat_list_stack = chat_page.get_chat_list_stack()
        self._connect(chat_list_stack, "chat-selected", self._on_chat_selected)

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

        image = Gtk.Image(icon_name="feather-bell-symbolic", pixel_size=28)
        container.append(image)

        self._unread_label = Gtk.Label(
            halign=Gtk.Align.END, valign=Gtk.Align.START, visible=False
        )
        self._unread_label.add_css_class("unread-counter")

        overlay = Gtk.Overlay()
        overlay.set_child(container)
        overlay.add_overlay(self._unread_label)

        self.append(overlay)

    def select(self) -> None:
        self._selection_bar.add_css_class("selection-bar-selected")

    def unselect(self) -> None:
        self._selection_bar.remove_css_class("selection-bar-selected")

    def _on_chat_selected(
        self, _chat_list_stack: ChatListStack, workspace_id: str, *args: Any
    ) -> None:
        self.unselect()

    def _on_unread_count_changed(self, listview: ActivityListView, *args: Any) -> None:
        count = listview.unread_count
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text("999+")
        self._unread_label.set_visible(bool(count))

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
