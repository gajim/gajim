# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Literal

import logging

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.chat_filter import ChatFilter

# from gajim.gtk.menus import get_account_notifications_menu
from gajim.gtk.menus import get_start_chat_button_menu
from gajim.gtk.widgets import SignalManager

log = logging.getLogger("gajim.gtk.chat_page_header")


class ChatPageHeader(Gtk.Grid, SignalManager):

    def __init__(self):
        Gtk.Grid.__init__(self, row_spacing=3)
        SignalManager.__init__(self)

        self._mode: Literal["chat", "activity"] = "chat"

        self.add_css_class("chat-page-header")

        section_name_box = Gtk.Box(height_request=39, spacing=12)
        self.attach(section_name_box, 0, 0, 1, 1)

        self._section_label = Gtk.Label(
            ellipsize=Pango.EllipsizeMode.END, halign=Gtk.Align.START, hexpand=True
        )
        self._section_label.add_css_class("bold16")
        section_name_box.append(self._section_label)

        self._workspace_settings_button = Gtk.Button.new_from_icon_name(
            "preferences-system-symbolic"
        )
        self._workspace_settings_button.set_visible(False)
        self._workspace_settings_button.set_valign(Gtk.Align.CENTER)
        self._workspace_settings_button.set_tooltip_text(_("Workspace settings…"))
        self._connect(
            self._workspace_settings_button,
            "clicked",
            self._on_edit_workspace_clicked,
        )
        section_name_box.append(self._workspace_settings_button)

        separator = Gtk.Separator(margin_start=6, margin_end=6, margin_top=6)
        self.attach(separator, 0, 1, 0, 0)

        constrols_box = Gtk.Box(margin_top=6, spacing=12)
        self.attach(constrols_box, 0, 2, 1, 1)

        self._search_entry = Gtk.SearchEntry(
            hexpand=True, placeholder_text=_("Search…")
        )
        constrols_box.append(self._search_entry)

        self._chat_filter = ChatFilter()
        constrols_box.append(self._chat_filter)

        self._start_chat_menu_button = Gtk.MenuButton(
            tooltip_text=(_("Start Chat…")), menu_model=get_start_chat_button_menu()
        )
        self._start_chat_menu_button.add_css_class("suggested-action")
        constrols_box.append(self._start_chat_menu_button)

        start_chat_menu_button_icon = Gtk.Image.new_from_icon_name(
            "feather-plus-symbolic"
        )
        self._start_chat_menu_button.set_child(start_chat_menu_button_icon)

        self._more_menu_button = Gtk.MenuButton(visible=False)
        # TODO: account-specific "deny-all" action or global one?
        # self._more_menu_button.set_menu_model(get_account_notifications_menu(account))
        constrols_box.append(self._more_menu_button)

        more_menu_button_icon = Gtk.Image.new_from_icon_name("view-more-symbolic")
        self._more_menu_button.set_child(more_menu_button_icon)

        section_hover_controller = Gtk.EventControllerMotion()
        self._connect(section_hover_controller, "enter", self._on_section_label_enter)
        self._connect(section_hover_controller, "leave", self._on_section_label_leave)
        section_name_box.add_controller(section_hover_controller)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Grid.do_unroot(self)

    def get_chat_filter(self) -> ChatFilter:
        return self._chat_filter

    def get_search_entry(self) -> Gtk.SearchEntry:
        return self._search_entry

    def set_mode(self, mode: Literal["chat", "activity"]) -> None:
        self._mode = mode
        if self._mode == "chat":
            self._search_entry.set_text("")
            self._chat_filter.set_visible(True)
            self._chat_filter.reset()
            self._start_chat_menu_button.set_visible(True)
            self._more_menu_button.set_visible(False)
        else:
            self._section_label.set_text(_("Activity"))
            self._chat_filter.set_visible(False)
            self._start_chat_menu_button.set_visible(False)
            self._more_menu_button.set_visible(True)

    def set_header_text(self, text: str) -> None:
        self._section_label.set_text(text)

    def _on_section_label_enter(
        self,
        _controller: Gtk.EventControllerMotion,
        _x: int,
        _y: int,
    ) -> None:
        if self._mode == "activity":
            # Don't show edit button for activities list
            return

        self._workspace_settings_button.set_visible(True)

    def _on_section_label_leave(self, controller: Gtk.EventControllerMotion) -> None:
        self._workspace_settings_button.set_visible(False)

    def _on_edit_workspace_clicked(self, _button: Gtk.Button) -> None:
        app.window.activate_action("win.edit-workspace", GLib.Variant("s", ""))
