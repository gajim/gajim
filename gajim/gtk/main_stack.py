# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app

from gajim.gtk.account_page import AccountPage
from gajim.gtk.activity_list import ActivityList
from gajim.gtk.activity_list import ActivityListRow
from gajim.gtk.activity_page import ActivityPage
from gajim.gtk.chat_list import ChatList
from gajim.gtk.chat_page import ChatPage

PageT = ChatPage | AccountPage


class MainStack(Gtk.Stack):
    def __init__(self) -> None:
        Gtk.Stack.__init__(self)

        self.add_named(Gtk.Box(), "empty")

        self._chat_page = ChatPage()
        self._chat_page.connect("chat-selected", self._on_chat_selected)
        self.add_named(self._chat_page, "chats")

        activity_list = self._chat_page.get_activity_list()
        activity_list.connect("row-activated", self._on_activity_row_activated)
        activity_list.connect("row-removed", self._on_activity_row_removed)

        for account in app.settings.get_active_accounts():
            self.add_account_page(account)

    def add_account_page(self, account: str) -> None:
        account_page = AccountPage(account)
        self.add_named(account_page, account)

    def remove_account_page(self, account: str) -> None:
        account_page = self.get_child_by_name(account)
        assert account_page is not None
        app.check_finalize(account_page)
        self.remove(account_page)

    def remove_chats_for_account(self, account: str) -> None:
        self._chat_page.remove_chats_for_account(account)

    def get_visible_page_name(self) -> str | None:
        return self.get_visible_child_name()

    def show_activity_page(self) -> None:
        self.set_visible_child_name("chats")
        self._chat_page.show_activity_page()

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
        self.set_visible_child_name(account)

    def get_account_page(self, account: str) -> AccountPage:
        account_page = self.get_child_by_name(account)
        assert isinstance(account_page, AccountPage)
        return account_page

    def get_chat_page(self) -> ChatPage:
        chat_page = self.get_child_by_name("chats")
        assert isinstance(chat_page, ChatPage)
        return chat_page

    def _on_activity_row_activated(
        self, _listbox: ActivityList, row: ActivityListRow
    ) -> None:
        self.get_activity_page().process_row_activated(row)

    def _on_activity_row_removed(self, _listbox: ActivityList) -> None:
        self.get_activity_page().show_page("default")

    def _on_chat_selected(
        self, _chat_list: ChatList, _workspace_id: str, _account: str, _jid: JID
    ) -> None:
        self.set_visible_child_name("chats")
