# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Union
from typing import cast

from nbxmpp.protocol import JID

from gi.repository import Gtk

from gajim.common import app
from gajim.common.events import ApplicationEvent

from .app_page import AppPage
from .chat_list import ChatList
from .chat_page import ChatPage
from .account_page import AccountPage


PageT = Union[ChatPage, AccountPage, AppPage]


class MainStack(Gtk.Stack):
    def __init__(self) -> None:
        Gtk.Stack.__init__(self)

        self.add_named(Gtk.Box(), 'empty')

        self._app_page = AppPage()
        self.add_named(self._app_page, 'app')

        self._chat_page = ChatPage()
        self._chat_page.connect('chat-selected', self._on_chat_selected)
        self.add_named(self._chat_page, 'chats')

        for account in list(app.connections.keys()):
            self.add_account_page(account)

    def add_account_page(self, account: str) -> None:
        account_page = AccountPage(account)
        self.add_named(account_page, account)

    def remove_account_page(self, account: str) -> None:
        account_page = self.get_child_by_name(account)
        account_page.destroy()

    def remove_chats_for_account(self, account: str) -> None:
        self._chat_page.remove_chats_for_account(account)

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

    def process_event(self, event: ApplicationEvent) -> None:
        empty_box = self.get_child_by_name('empty')
        pages = cast(list[PageT], self.get_children())
        for page in pages:
            if page is empty_box:
                continue

            if isinstance(page, AccountPage):
                continue

            page.process_event(event)

    def _on_chat_selected(self,
                          _chat_list: ChatList,
                          _workspace_id: str,
                          _account: str,
                          _jid: JID) -> None:
        self.set_visible_child_name('chats')
