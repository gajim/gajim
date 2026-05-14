# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast
from typing import Literal

from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gtk.account_page import AccountPage
from gajim.gtk.chat_list import ChatList
from gajim.gtk.chat_page import ChatPage

PageT = ChatPage | AccountPage


class MainStack(Gtk.Stack):
    __gtype_name__ = "MainStack"

    chat_list_collapsed = GObject.Property(type=bool, default=False)

    def __init__(self) -> None:
        Gtk.Stack.__init__(self)

        self.add_named(Gtk.Box(), "empty")

        self._chat_page = ChatPage()
        self._chat_page.connect("chat-selected", self._on_chat_selected)
        self.add_named(self._chat_page, "chats")
        self.add_named(AccountPage(), "account")

    def get_chat_list_collapsed(self) -> bool:
        return bool(self.get_property("chat-list-collapsed"))

    def _get_account_page(self) -> AccountPage:
        return cast(AccountPage, self.get_child_by_name("account"))

    def _switch_page(
        self, page_name: Literal["chats", "account", "empty"], title: str | None = None
    ) -> None:
        app.window.set_application_title(title)
        self.set_visible_child_name(page_name)

    def remove_account_page(self, account: str) -> None:
        account_page = self._get_account_page()
        if account_page.get_account() == account:
            account_page.set_account(None)
            self._switch_page("empty")

    def remove_chats_for_account(self, account: str) -> None:
        self._chat_page.remove_chats_for_account(account)

    def get_visible_page_name(self) -> str | None:
        return self.get_visible_child_name()

    def show_activity_page(self, context_id: str | None = None) -> None:
        self._switch_page("chats", _("Activity Feed"))
        self._chat_page.show_activity_page(context_id)

    def show_chats(self, workspace_id: str) -> None:
        self._switch_page("chats")
        self._chat_page.show_workspace_chats(workspace_id)

    def show_chat_page(self) -> None:
        self._switch_page("chats")

    def show_account(self, account: str) -> None:
        account_page = self._get_account_page()
        account_page.set_account(account)
        account_label = app.settings.get_account_setting(account, "account_label")
        self._switch_page("account", account_label)

    def get_chat_page(self) -> ChatPage:
        chat_page = self.get_child_by_name("chats")
        assert isinstance(chat_page, ChatPage)
        return chat_page

    def _on_chat_selected(
        self, _chat_list: ChatList, _workspace_id: str, account: str, jid: JID
    ) -> None:
        client = app.get_client(account)
        contact = client.get_module("Contacts").get_contact(jid)
        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant
        )
        if isinstance(contact, BareContact) and contact.is_self:
            chat_name = _("Note to myself")
        else:
            chat_name = contact.name

        self._switch_page("chats", chat_name)
