# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast
from typing import Literal

from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import events

from gajim.gtk.account_page import AccountPage
from gajim.gtk.activity_list import ActivityListView
from gajim.gtk.activity_list import ResponseReaction
from gajim.gtk.activity_page import ActivityPage
from gajim.gtk.chat_list import ChatList
from gajim.gtk.chat_page import ChatPage

PageT = ChatPage | AccountPage


class MainStack(Gtk.Stack):
    __gtype_name__ = "MainStack"

    def __init__(self) -> None:
        Gtk.Stack.__init__(self)

        self.add_named(Gtk.Box(), "empty")

        self._chat_page = ChatPage()
        self._chat_page.connect("chat-selected", self._on_chat_selected)
        self.add_named(self._chat_page, "chats")
        self.add_named(AccountPage(), "account")

        activity_list = self._chat_page.get_activity_list()
        activity_list.connect("activate", self._on_activity_item_activate)
        activity_list.connect("unselected", self._on_activity_item_unselected)

    def _get_account_page(self) -> AccountPage:
        return cast(AccountPage, self.get_child_by_name("account"))

    def remove_account_page(self, account: str) -> None:
        account_page = self._get_account_page()
        if account_page.get_account() == account:
            account_page.set_account(None)
            self.set_visible_child_name("empty")

    def remove_chats_for_account(self, account: str) -> None:
        self._chat_page.remove_chats_for_account(account)

    def get_visible_page_name(self) -> str | None:
        return self.get_visible_child_name()

    def show_activity_page(self, context_id: str | None = None) -> None:
        self.set_visible_child_name("chats")
        self._chat_page.show_activity_page(context_id)

    def get_activity_page(self) -> ActivityPage:
        chat_stack = self._chat_page.get_chat_stack()
        activity_page = chat_stack.get_child_by_name("activity")
        assert isinstance(activity_page, ActivityPage)
        return activity_page

    def show_chats(self, workspace_id: str) -> None:
        self._chat_page.show_workspace_chats(workspace_id)
        self.set_visible_child_name("chats")

    def show_chat_page(self) -> None:
        self.set_visible_child_name("chats")

    def show_account(self, account: str) -> None:
        account_page = self._get_account_page()
        account_page.set_account(account)
        self.set_visible_child_name("account")

    def get_chat_page(self) -> ChatPage:
        chat_page = self.get_child_by_name("chats")
        assert isinstance(chat_page, ChatPage)
        return chat_page

    def _on_activity_item_activate(
        self, listview: ActivityListView, position: int
    ) -> None:
        item = listview.get_listitem(position)
        if isinstance(item, ResponseReaction):
            event = cast(events.ReactionUpdated, item.event)
            assert event.message is not None

            chat_list_stack = self._chat_page.get_chat_list_stack()
            chat_list = chat_list_stack.find_chat(event.account, event.jid)
            if chat_list is None:
                message_type = cast(
                    Literal["chat", "groupchat", "pm"], str(event.message_type).lower()
                )
                app.window.add_chat(event.account, event.jid, message_type, select=True)
            else:
                chat_list.select_chat(event.account, event.jid)

            control = self._chat_page.get_control()
            control.scroll_to_message(event.message.pk, event.message.timestamp)
            return

        self.get_activity_page().process_row_activated(item)

    def _on_activity_item_unselected(self, _listview: ActivityListView) -> None:
        self.get_activity_page().show_default_page()

    def _on_chat_selected(
        self, _chat_list: ChatList, _workspace_id: str, _account: str, _jid: JID
    ) -> None:
        self.set_visible_child_name("chats")
