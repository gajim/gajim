# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app

from gajim.gtk.account_page import AccountPage
from gajim.gtk.app_page import AppPage
from gajim.gtk.chat_list import ChatList
from gajim.gtk.chat_page import ChatPage

PageT = ChatPage | AccountPage | AppPage


class MainStack(Gtk.Stack):
    def __init__(self) -> None:
        Gtk.Stack.__init__(self)

        self.add_named(Gtk.Box(), 'empty')

        self._app_page = AppPage()
        self.add_named(self._app_page, 'app')

        self._chat_page = ChatPage()
        self._chat_page.connect('chat-selected', self._on_chat_selected)
        self.add_named(self._chat_page, 'chats')

        for account in app.settings.get_active_accounts():
            self.add_account_page(account)

    def add_account_page(self, account: str) -> None:
        account_page = AccountPage(account)
        self.add_named(account_page, account)

    def remove_account_page(self, account: str) -> None:
        account_page = self.get_child_by_name(account)
        assert account_page is not None
        account_page.destroy()

    def remove_chats_for_account(self, account: str) -> None:
        self._chat_page.remove_chats_for_account(account)

    def get_visible_page_name(self) -> str | None:
        return self.get_visible_child_name()

    def show_app_page(self) -> None:
        self.set_visible_child_name('app')

    def get_app_page(self) -> AppPage:
        app_page = self.get_child_by_name('app')
        assert isinstance(app_page, AppPage)
        return app_page

    def show_chats(self, workspace_id: str) -> None:
        self._chat_page.show_workspace_chats(workspace_id)
        self.set_visible_child_name('chats')

    def show_chat_page(self) -> None:
        self.set_visible_child_name('chats')

    def show_account(self, account: str) -> None:
        self.set_visible_child_name(account)

    def get_account_page(self, account: str) -> AccountPage:
        account_page = self.get_child_by_name(account)
        assert isinstance(account_page, AccountPage)
        return account_page

    def get_chat_page(self) -> ChatPage:
        chat_page = self.get_child_by_name('chats')
        assert isinstance(chat_page, ChatPage)
        return chat_page

    def _on_chat_selected(self,
                          _chat_list: ChatList,
                          _workspace_id: str,
                          _account: str,
                          _jid: JID) -> None:
        self.set_visible_child_name('chats')
