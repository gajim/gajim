# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.gtk.account_page import AccountPage
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

    def _on_chat_selected(
        self, _chat_list: ChatList, _workspace_id: str, _account: str, _jid: JID
    ) -> None:
        self.set_visible_child_name("chats")
