# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Literal

from gi.repository import Gtk

from gajim.common.configpaths import get_ui_path

from gajim.gtk.chat_filter import ChatFilter
from gajim.gtk.menus import get_start_chat_button_menu


@Gtk.Template(filename=get_ui_path("chat_list_header.ui"))
class ChatListHeader(Gtk.Grid):
    __gtype_name__ = "ChatListHeader"

    _header_bar_label: Gtk.Label = Gtk.Template.Child()
    _chat_page_header: Gtk.Box = Gtk.Template.Child()
    _search_entry: Gtk.SearchEntry = Gtk.Template.Child()
    _chat_filter: ChatFilter = Gtk.Template.Child()
    _start_chat_menu_button: Gtk.MenuButton = Gtk.Template.Child()

    def __init__(self):
        Gtk.Grid.__init__(self)

        self._start_chat_menu_button.set_menu_model(get_start_chat_button_menu())

    def get_chat_filter(self) -> ChatFilter:
        return self._chat_filter

    def get_search_entry(self) -> Gtk.SearchEntry:
        return self._search_entry

    def set_label(self, text: str) -> None:
        self._header_bar_label.set_label(text)

    def set_header_mode(self, mode: Literal["chat", "activity"]) -> None:
        is_chat = mode == "chat"
        self._start_chat_menu_button.set_visible(is_chat)
        self._chat_filter.set_visible(is_chat)

        if is_chat:
            self._search_entry.set_text("")
            self._chat_filter.reset()
