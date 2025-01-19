# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast
from typing import Literal

from functools import partial

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp import Namespace

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk import structs
from gajim.gtk.chat_filter import ChatFilter
from gajim.gtk.chat_list import ChatList
from gajim.gtk.chat_list_row import ChatListRow
from gajim.gtk.dialogs import ConfirmationCheckDialog
from gajim.gtk.dialogs import DialogButton


class ChatListStack(Gtk.Stack, EventHelper):

    __gsignals__ = {
        "unread-count-changed": (GObject.SignalFlags.RUN_LAST, None, (str, int)),
        "chat-selected": (GObject.SignalFlags.RUN_LAST, None, (str, str, object)),
        "chat-unselected": (GObject.SignalFlags.RUN_LAST, None, ()),
        "chat-removed": (GObject.SignalFlags.RUN_LAST, None, (str, object, str, bool)),
    }

    def __init__(self, chat_filter: ChatFilter, search_entry: Gtk.SearchEntry) -> None:
        Gtk.Stack.__init__(self)
        EventHelper.__init__(self)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_vhomogeneous(False)

        self._chat_lists: dict[str, ChatList] = {}

        self._last_visible_child_name: str = "default"

        self.add_named(Gtk.Box(), "default")

        self.connect("notify::visible-child-name", self._on_visible_child_name)
        search_entry.connect("search-changed", self._on_search_changed)
        chat_filter.connect("filter-changed", self._on_filter_changed)

        self._add_actions()

        self.register_events(
            [
                ("message-received", ged.GUI2, self._on_event),
                ("message-corrected", ged.GUI2, self._on_event),
                ("message-moderated", ged.GUI2, self._on_event),
                ("presence-received", ged.GUI2, self._on_event),
                ("message-sent", ged.GUI2, self._on_event),
                ("message-deleted", ged.GUI2, self._on_event),
                ("file-request-received", ged.GUI2, self._on_event),
                ("jingle-request-received", ged.GUI2, self._on_event),
            ]
        )

    def _add_actions(self) -> None:
        actions = [
            ("toggle-chat-pinned", "a{sv}", self._toggle_chat_pinned),
            ("move-chat-to-workspace", "a{sv}", self._move_chat_to_workspace),
            ("mark-as-read", "a{sv}", self._mark_as_read),
        ]

        for action in actions:
            action_name, variant, func = action
            variant = GLib.VariantType.new(variant)
            act = Gio.SimpleAction.new(action_name, variant)
            act.connect("activate", func)
            app.window.add_action(act)

    def _on_visible_child_name(self, _stack: Gtk.Stack, _param: str) -> None:
        new_visible_child_name = self.get_visible_child_name()
        if self._last_visible_child_name == new_visible_child_name:
            return

        if self._last_visible_child_name != "default":
            chat_list = cast(
                ChatList | None, self.get_child_by_name(self._last_visible_child_name)
            )
            if chat_list is not None:
                chat_list.set_filter_text("")

        self._last_visible_child_name = new_visible_child_name or "default"

    def get_chatlist(self, workspace_id: str) -> ChatList:
        return self._chat_lists[workspace_id]

    def get_selected_chat(self) -> ChatListRow | None:
        chat_list = self.get_current_chat_list()
        if chat_list is None:
            return None
        return chat_list.get_selected_chat()

    def get_current_chat_list(self) -> ChatList | None:
        workspace_id = self.get_visible_child_name()
        if workspace_id == "default" or workspace_id is None:
            return None

        return self._chat_lists[workspace_id]

    def is_chat_selected(self, account: str, jid: JID) -> bool:
        chat = self.get_selected_chat()
        if chat is None:
            return False
        return chat.account == account and chat.jid == jid

    def _on_filter_changed(self, chat_filter: ChatFilter) -> None:
        filters = chat_filter.get_filters()

        chat_list = cast(ChatList, self.get_visible_child())
        chat_list.set_filter(filters)

    def _on_search_changed(self, search_entry: Gtk.SearchEntry) -> None:
        chat_list = cast(ChatList, self.get_visible_child())
        chat_list.set_filter_text(search_entry.get_text())

    def add_chat_list(self, workspace_id: str) -> ChatList:
        chat_list = ChatList(workspace_id)
        chat_list.connect("row-selected", self._on_row_selected)
        chat_list.connect("chat-order-changed", self._on_chat_order_changed)

        self._chat_lists[workspace_id] = chat_list
        self.add_named(chat_list, workspace_id)
        return chat_list

    def remove_chat_list(self, workspace_id: str) -> None:
        chat_list = self._chat_lists[workspace_id]
        self.remove(chat_list)
        for open_chat in chat_list.get_open_chats():
            self.remove_chat(workspace_id, open_chat["account"], open_chat["jid"])

        self._chat_lists.pop(workspace_id)

    def _on_row_selected(self, _chat_list: ChatList, row: ChatListRow | None) -> None:
        if row is None:
            self.emit("chat-unselected")
            return

        self.emit("chat-selected", row.workspace_id, row.account, row.jid)

    def _on_chat_order_changed(self, chat_list: ChatList) -> None:

        self.store_open_chats(chat_list.workspace_id)

    def show_chat_list(self, workspace_id: str) -> None:
        cur_workspace_id = self.get_visible_child_name()
        if cur_workspace_id != "default" and cur_workspace_id is not None:
            self._chat_lists[cur_workspace_id].unselect_all()

        self.set_visible_child_name(workspace_id)

    def add_chat(
        self,
        workspace_id: str,
        account: str,
        jid: JID,
        type_: Literal["chat", "groupchat", "pm"],
        pinned: bool,
        position: int,
    ) -> None:

        chat_list = self._chat_lists.get(workspace_id)
        if chat_list is None:
            chat_list = self.add_chat_list(workspace_id)
        chat_list.add_chat(account, jid, type_, pinned, position)

    def select_chat(self, account: str, jid: JID) -> None:
        chat_list = self.find_chat(account, jid)
        if chat_list is None:
            return

        self.show_chat_list(chat_list.workspace_id)
        chat_list.select_chat(account, jid)

    def store_open_chats(self, workspace_id: str) -> None:
        chat_list = self._chat_lists[workspace_id]
        open_chats = chat_list.get_open_chats()
        app.settings.set_workspace_setting(workspace_id, "chats", open_chats)

    @structs.actionmethod
    def _toggle_chat_pinned(
        self, _action: Gio.SimpleAction, params: structs.ChatListEntryParam
    ) -> None:

        chat_list = self._chat_lists[params.workspace_id]
        chat_list.toggle_chat_pinned(params.account, params.jid)
        self.store_open_chats(params.workspace_id)

    @structs.actionmethod
    def _move_chat_to_workspace(
        self, _action: Gio.SimpleAction, params: structs.ChatListEntryParam
    ) -> None:

        workspace_id = params.workspace_id
        if not workspace_id:
            workspace_id = app.window.add_workspace(switch=False)

        source_chatlist = self.get_chatlist(params.source_workspace_id)
        type_ = source_chatlist.get_chat_type(params.account, params.jid)
        if type_ is None:
            return

        source_chatlist.remove_chat(params.account, params.jid)

        new_chatlist = self.get_chatlist(workspace_id)
        new_chatlist.add_chat(params.account, params.jid, type_, False, -1)

        self.store_open_chats(source_chatlist.workspace_id)
        self.store_open_chats(workspace_id)

    @structs.actionmethod
    def _mark_as_read(
        self, _action: Gio.SimpleAction, params: structs.AccountJidParam
    ) -> None:

        self.mark_as_read(params.account, params.jid)

    def remove_chat(self, workspace_id: str, account: str, jid: JID) -> None:
        chat_list = self._chat_lists[workspace_id]
        type_ = chat_list.get_chat_type(account, jid)

        def _leave(not_ask_again: bool, unregister: bool = False) -> None:
            if not_ask_again:
                app.settings.set("confirm_close_muc", False)
            _remove(unregister)

        def _remove(unregister: bool = False) -> None:
            chat_list.remove_chat(account, jid, emit_unread=False)
            self.store_open_chats(workspace_id)
            self.emit("chat-removed", account, jid, type_, unregister)

        if type_ != "groupchat" or not app.settings.get("confirm_close_muc"):
            _remove()
            return

        client = app.get_client(account)
        contact = client.get_module("Contacts").get_contact(jid)
        assert isinstance(contact, GroupchatContact)

        if contact.is_not_joined and client.state.is_available:
            # For example a chat opened from the search bar
            _remove()
            return

        muc_disco = contact.get_disco()
        us = contact.get_self()
        if muc_disco is None or us is None:
            _remove()
            return

        buttons = [
            DialogButton.make("Cancel"),
            DialogButton.make("Accept", text=_("_Leave"), callback=_leave),
        ]

        affiliation = us.affiliation
        text = _('By closing this chat, you will leave "%s".') % contact.name
        if Namespace.REGISTER in muc_disco.features and not affiliation.is_none:
            buttons.append(
                DialogButton.make(
                    "Delete",
                    text=_("Leave _Permanently"),
                    callback=partial(_leave, unregister=True),
                )
            )

            text += "\n"
            text += _(
                "You may need an invite to join this group chat again, "
                "if you choose to leave it permanently."
            )
            if affiliation.is_admin:
                text += "\n"
                text += _("Additionally, you will lose your administrator affiliation.")
            elif affiliation.is_owner:
                text += "\n"
                text += _("Additionally, you will lose your owner affiliation.")

        ConfirmationCheckDialog(
            _("Leave Group Chat"),
            _("Are you sure you want to leave this group chat?"),
            text,
            _("_Do not ask me again"),
            buttons,
            transient_for=app.window,
        ).show()

    def remove_chats_for_account(self, account: str) -> None:
        for workspace_id, chat_list in self._chat_lists.items():
            chat_list.remove_chats_for_account(account)
            self.store_open_chats(workspace_id)

    def find_chat(self, account: str, jid: JID) -> ChatList | None:
        for chat_list in self._chat_lists.values():
            if chat_list.contains_chat(account, jid):
                return chat_list
        return None

    def contains_chat(
        self, account: str, jid: JID, workspace_id: str | None = None
    ) -> bool:
        if workspace_id is None:
            return any(
                chat_list.contains_chat(account, jid)
                for chat_list in self._chat_lists.values()
            )

        chat_list = self._chat_lists[workspace_id]
        return chat_list.contains_chat(account, jid)

    def get_total_unread_count(self) -> int:
        count = 0
        for chat_list in self._chat_lists.values():
            count += chat_list.get_unread_count()
        return count

    def get_chat_unread_count(
        self, account: str, jid: JID, include_silent: bool = False
    ) -> int | None:
        for chat_list in self._chat_lists.values():
            count = chat_list.get_chat_unread_count(account, jid, include_silent)
            if count is not None:
                return count
        return None

    def set_chat_unread_count(self, account: str, jid: JID, count: int) -> None:
        for chat_list in self._chat_lists.values():
            chat_list.set_chat_unread_count(account, jid, count)

    def mark_as_read(self, account: str, jid: JID) -> None:
        for chat_list in self._chat_lists.values():
            chat_list.mark_as_read(account, jid)

    def _on_event(self, event: events.ChatListEventT) -> None:
        jid = JID.from_string(event.jid)

        chat_list = self.find_chat(event.account, jid)
        if chat_list is None:
            return
        chat_list.process_event(event)
