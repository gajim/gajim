# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal

import logging
from collections.abc import Iterator
from datetime import datetime

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.const import Direction
from gajim.common.const import RowHeaderType
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.message_util import get_nickname_from_message
from gajim.common.setting_values import OpenChatsSettingT
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.util.muc import get_group_chat_nick
from gajim.common.util.user_strings import get_moderation_text
from gajim.common.util.user_strings import get_retraction_text

from gajim.gtk.chat_filter import ChatFilters
from gajim.gtk.chat_list_row import ChatListRow
from gajim.gtk.start_chat import ChatTypeFilter
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_listbox_row_count
from gajim.gtk.util.misc import iterate_listbox_children

log = logging.getLogger("gajim.gtk.chatlist")


class ChatList(Gtk.ListBox, EventHelper, SignalManager):

    __gsignals__ = {
        "chat-order-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self, workspace_id: str) -> None:
        Gtk.ListBox.__init__(self)
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self._workspace_id = workspace_id

        self._chats: dict[tuple[str, JID], ChatListRow] = {}
        self._current_filter: ChatFilters = ChatFilters()
        self._current_filter_text: str = ""

        self.add_css_class("chatlist")
        self.set_filter_func(self._filter_func)
        self.set_header_func(self._header_func)
        self.set_sort_func(self._sort_func)
        self._set_placeholder()

        self._force_sort = False
        self._rows_need_sort = False
        self._context_menu_visible = False
        self._mouseover = False
        self._scheduled_sort_id = None

        hover_controller = Gtk.EventControllerMotion()
        self._connect(hover_controller, "enter", self._on_cursor_enter)
        self._connect(hover_controller, "leave", self._on_cursor_leave)
        self.add_controller(hover_controller)

        drop_target = Gtk.DropTarget(
            formats=Gdk.ContentFormats.new_for_gtype(ChatListRow),
            actions=Gdk.DragAction.MOVE,
        )
        self._connect(drop_target, "drop", self._on_drop)
        self.add_controller(drop_target)

        self._chat_order: list[ChatListRow] = []

        self.register_events(
            [
                ("account-enabled", ged.GUI2, self._on_account_changed),
                ("account-disabled", ged.GUI2, self._on_account_changed),
                ("bookmarks-received", ged.GUI1, self._on_bookmarks_received),
            ]
        )

        self._timer_id = GLib.timeout_add_seconds(60, self._update_row_state)

    def do_unroot(self) -> None:
        Gtk.ListBox.do_unroot(self)
        self._disconnect_all()
        self.unregister_events()
        self._abort_scheduled_sort("unroot")
        self.set_filter_func(None)
        self.set_header_func(None)
        self.set_sort_func(None)
        GLib.source_remove(self._timer_id)
        app.check_finalize(self)

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    def get_row_count(self) -> int:
        return get_listbox_row_count(self)

    def _iterate_rows(self) -> Iterator[ChatListRow]:
        for row in iterate_listbox_children(self):
            yield cast(ChatListRow, row)

    def get_unread_count(self) -> int:
        return sum(chats.unread_count for chats in self._chats.values())

    def get_chat_unread_count(
        self, account: str, jid: JID, include_silent: bool = False
    ) -> int | None:
        chat = self._chats.get((account, jid))
        if chat is not None:
            if include_silent:
                return chat.get_real_unread_count()
            return chat.unread_count
        return None

    def set_chat_unread_count(self, account: str, jid: JID, count: int) -> None:
        chat = self._chats.get((account, jid))
        if chat is not None:
            chat.unread_count = count

    def set_filter(self, chat_filter: ChatFilters) -> None:
        self._current_filter = chat_filter
        self.invalidate_filter()

    def set_filter_text(self, text: str) -> None:
        self._current_filter_text = text
        self.invalidate_filter()

    def get_chat_type(
        self, account: str, jid: JID
    ) -> Literal["chat", "groupchat", "pm"] | None:
        row = self._chats.get((account, jid))
        if row is not None:
            return row.type  # type: ignore
        return None

    def get_selected_chat(self) -> ChatListRow | None:
        row = cast(ChatListRow | None, self.get_selected_row())
        if row is None:
            return None
        return row

    def get_open_chats(self) -> OpenChatsSettingT:
        open_chats: OpenChatsSettingT = []
        for key, row in self._chats.items():
            account, jid = key
            open_chats.append(
                {
                    "account": account,
                    "jid": jid,
                    "type": row.type,  # type: ignore
                    "pinned": row.is_pinned,
                    "position": row.position,
                }
            )
        return open_chats

    def mark_as_read(self, account: str, jid: JID) -> None:
        chat = self._chats.get((account, jid))
        if chat is not None and chat.get_real_unread_count() > 0:
            chat.reset_unread()
            app.ged.raise_event(events.ChatRead(account=account, jid=jid))

    def toggle_chat_pinned(self, account: str, jid: JID) -> None:
        row = self._chats[(account, jid)]

        if row.is_pinned:
            self._chat_order.remove(row)
            row.position = -1
        else:
            self._chat_order.append(row)
            row.position = self._chat_order.index(row)

        row.toggle_pinned()
        self.invalidate_sort(force=True)

    def add_chat(
        self,
        account: str,
        jid: JID,
        type_: Literal["chat", "groupchat", "pm"],
        pinned: bool,
        position: int,
    ) -> None:

        key = (account, jid)
        if self._chats.get(key) is not None:
            # Chat is already in the List
            return

        row = ChatListRow(self._workspace_id, account, jid, type_, pinned, position)

        self._chats[key] = row
        if pinned:
            self._chat_order.insert(position, row)

        row.connect("unread-changed", self._on_row_unread_changed)
        row.connect("context-menu-state-changed", self._on_context_menu_state_changed)

        self.append(row)

    def select_chat(self, account: str, jid: JID) -> None:
        row = self._chats[(account, jid)]
        self.select_row(row)

    def select_next_chat(
        self, direction: Direction, unread_first: bool = False
    ) -> None:
        # Selects the next chat, but prioritizes chats with unread messages.
        row = self.get_selected_chat()
        if row is None:
            row = self.get_row_at_index(0)
            if row is None:
                return
            assert isinstance(row, ChatListRow)
            self.select_chat(row.account, row.jid)
            return

        unread_found = False
        if unread_first:
            index = row.get_index()
            current = index

            # Loop until finding a chat with unread count or completing a cycle
            while True:
                if direction == Direction.NEXT:
                    index += 1
                    if index >= self.get_row_count():
                        index = 0
                else:
                    index -= 1
                    if index < 0:
                        index = self.get_row_count() - 1

                row = self.get_row_at_index(index)
                if row is None:
                    return
                assert isinstance(row, ChatListRow)
                if row.unread_count > 0:
                    unread_found = True
                    break
                if index == current:
                    break

        if unread_found:
            self.select_chat(row.account, row.jid)
            return

        index = row.get_index()
        if direction == Direction.NEXT:
            next_row = self.get_row_at_index(index + 1)
        else:
            next_row = self.get_row_at_index(index - 1)
        if next_row is None:
            if direction == Direction.NEXT:
                next_row = self.get_row_at_index(0)
            else:
                last = self.get_row_count() - 1
                next_row = self.get_row_at_index(last)
            assert isinstance(next_row, ChatListRow)
            self.select_chat(next_row.account, next_row.jid)
            return

        assert isinstance(next_row, ChatListRow)
        self.select_chat(next_row.account, next_row.jid)

    def select_chat_number(self, number: int) -> None:
        row = self.get_row_at_index(number)
        if row is not None:
            assert isinstance(row, ChatListRow)
            self.select_chat(row.account, row.jid)

    def get_chat_list_rows(self) -> list[ChatListRow]:
        return list(self._iterate_rows())

    def remove_chat(self, account: str, jid: JID, emit_unread: bool = True) -> None:

        row = self._chats.pop((account, jid))

        if row.is_pinned:
            self._chat_order.remove(row)
        self.remove(row)

        if emit_unread:
            self._emit_unread_changed()

    def remove_chats_for_account(self, account: str) -> None:
        for row_account, jid in list(self._chats.keys()):
            if row_account != account:
                continue
            self.remove_chat(account, jid)
        self._emit_unread_changed()

    def clear_chat_list_row(self, account: str, jid: JID) -> None:
        chat = self._chats.get((account, jid))
        if chat is not None:
            chat.clear()

    def contains_chat(self, account: str, jid: JID) -> bool:
        return self._chats.get((account, jid)) is not None

    def process_event(self, event: events.ChatListEventT) -> None:
        if isinstance(event, events.MessageReceived):
            self._on_message_received(event)
        elif isinstance(event, events.MessageDeleted):
            self._on_message_deleted(event)
        elif isinstance(event, events.MessageCorrected):
            self._on_message_corrected(event)
        elif isinstance(event, events.MessageModerated):
            self._on_message_moderated(event)
        elif isinstance(event, events.MessageRetracted):
            self._on_message_retracted(event)
        elif isinstance(event, events.PresenceReceived):
            self._on_presence_received(event)
        elif isinstance(event, events.MessageSent):
            self._on_message_sent(event)
        elif isinstance(event, events.JingleRequestReceived):
            self._on_jingle_request_received(event)
        elif isinstance(
            event, events.FileRequestReceivedEvent
        ):  # pyright: ignore [reportUnnecessaryIsInstance] # noqa: E501
            self._on_file_request_received(event)
        else:
            log.warning("Unhandled Event: %s", event.name)

    def _set_placeholder(self) -> None:
        button = Gtk.Button(
            label=_("Start Chat"),
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            action_name="app.start-chat",
            action_target=GLib.Variant("as", ["", ""]),
        )
        button.add_css_class("suggested-action")
        self.set_placeholder(button)

    def _emit_unread_changed(self) -> None:
        count = self.get_unread_count()
        chat_list_stack = self.get_parent()
        assert chat_list_stack is not None
        chat_list_stack.emit("unread-count-changed", self._workspace_id, count)

    def _get_row_before(self, row: ChatListRow) -> ChatListRow | None:
        row_before = self.get_row_at_index(row.get_index() - 1)
        if row_before is None:
            return
        return cast(ChatListRow, row_before)

    def _get_row_after(self, row: ChatListRow) -> ChatListRow | None:
        row_after = self.get_row_at_index(row.get_index() + 1)
        if row_after is None:
            return
        return cast(ChatListRow, row_after)

    def _get_last_row(self) -> ChatListRow:
        index = self.get_row_count() - 1
        last_row = self.get_row_at_index(index)
        assert last_row is not None
        return cast(ChatListRow, last_row)

    def _on_row_unread_changed(self, row: ChatListRow) -> None:
        self._emit_unread_changed()

    def _on_context_menu_state_changed(
        self, row: ChatListRow, menu_is_visible: bool
    ) -> None:

        self._context_menu_visible = menu_is_visible
        self._schedule_sort()

    def _on_drop(
        self, _drop_target: Gtk.DropTarget, value: GObject.Value, _x: float, y: float
    ) -> bool:
        target_row = self.get_row_at_y(int(y))

        if not value or not isinstance(target_row, ChatListRow):
            # Reject drop
            return False

        if isinstance(value, ChatListRow):
            if not value.is_pinned or not target_row.is_pinned:
                log.debug("Only pinned rows can be reordered")
                return False

            self._change_pinned_order(value, target_row)
            return True

        # Reject drop
        log.debug("Unknown item type dropped")
        return False

    def _change_pinned_order(
        self, drag_row: ChatListRow, target_row: ChatListRow
    ) -> None:
        self._chat_order.remove(drag_row)
        self._chat_order.insert(target_row.position, drag_row)

        for row in self._chat_order:
            row.position = self._chat_order.index(row)

        self.emit("chat-order-changed")
        self.invalidate_sort(force=True)

    def _update_row_state(self) -> bool:
        for row in self._chats.values():
            row.update_row_state()
        return True

    def _filter_func(self, row: ChatListRow) -> bool:
        account = self._current_filter.account
        if account is not None and account != row.account:
            return False

        group = self._current_filter.group
        if (
            group is not None
            and isinstance(row.contact, BareContact)
            and group not in row.contact.groups
        ):
            return False

        is_groupchat = row.type == "groupchat"
        if self._current_filter.type == ChatTypeFilter.CHAT and is_groupchat:
            return False

        if self._current_filter.type == ChatTypeFilter.GROUPCHAT and not is_groupchat:
            return False

        if not self._current_filter_text:
            return True
        text = self._current_filter_text.lower()
        return text in row.contact_name.lower()

    @staticmethod
    def _header_func(row: ChatListRow, before: ChatListRow | None) -> None:
        if before is None:
            if row.is_pinned:
                row.set_header_type(RowHeaderType.PINNED)
            else:
                row.set_header_type(None)
        else:
            if row.is_pinned:
                if before.is_pinned:
                    row.set_header_type(None)
                else:
                    row.set_header_type(RowHeaderType.PINNED)
            else:
                if before.is_pinned:
                    row.set_header_type(RowHeaderType.CONVERSATIONS)
                else:
                    row.set_header_type(None)

    def _sort_func(self, row1: ChatListRow, row2: ChatListRow) -> int:
        if not self._force_sort and self._is_sort_inhibited():
            self._rows_need_sort = True
            log.debug("Delay sorting because it is inhibited")
            return 0

        # Sort pinned rows according to stored order
        if row1.is_pinned and row2.is_pinned:
            if row1.position > row2.position:
                return 1
            return -1

        # Sort pinned rows to top
        if row1.is_pinned > row2.is_pinned:
            return -1
        if row2.is_pinned > row1.is_pinned:
            return 1

        # Sort by timestamp
        return -1 if row1.timestamp > row2.timestamp else 1

    def invalidate_sort(self, *, force: bool = False) -> bool:  # pyright: ignore
        log.debug("Try sorting chatlist")
        if not force and self._is_sort_inhibited():
            log.debug("Abort sorting because it is inhibited")
            return False

        self._rows_need_sort = False
        self._force_sort = force
        Gtk.ListBox.invalidate_sort(self)
        self._force_sort = False
        log.debug("Sorting successful")
        return True

    def _is_sort_inhibited(self) -> bool:
        return self._mouseover or self._context_menu_visible

    def _schedule_sort(self) -> None:
        self._abort_scheduled_sort("schedule is renewed")
        log.debug("Schedule sort")
        self._scheduled_sort_id = GLib.timeout_add(100, self._execute_scheduled_sort)

    def _abort_scheduled_sort(self, reason: str) -> None:
        if self._scheduled_sort_id is not None:
            log.debug("Abort scheduled sort, reason: %s", reason)
            GLib.source_remove(self._scheduled_sort_id)
        self._scheduled_sort_id = None

    def _execute_scheduled_sort(self) -> int:
        log.debug("Execute scheduled sort")
        if not self._rows_need_sort:
            log.debug("Abort scheduled sort, reason: no rows changed")
            self._scheduled_sort_id = None
            return GLib.SOURCE_REMOVE

        sort_executed = self.invalidate_sort()
        if sort_executed:
            self._scheduled_sort_id = None
            return GLib.SOURCE_REMOVE

        return GLib.SOURCE_CONTINUE

    def _on_cursor_enter(
        self,
        _controller: Gtk.EventControllerMotion,
        _x: int,
        _y: int,
    ) -> None:
        self._mouseover = True
        self._abort_scheduled_sort("mouse over list")

    def _on_cursor_leave(self, _controller: Gtk.EventControllerMotion) -> None:
        self._mouseover = False
        self._schedule_sort()

    @staticmethod
    def _get_nick_for_received_message(account: str, message: Message) -> str:

        if message.direction == ChatDirection.OUTGOING:
            return _("Me")

        if message.type in (MessageType.GROUPCHAT, MessageType.PM):
            return get_nickname_from_message(message)

        return ""

    @staticmethod
    def _add_unread(row: ChatListRow, event: events.MessageReceived) -> None:
        message = event.message
        if message.direction == ChatDirection.OUTGOING:
            # Last message was from us (1:1), reset counter
            row.reset_unread()
            return

        our_nick = get_group_chat_nick(event.account, event.jid)
        if message.resource == our_nick:
            # Last message was from us (MUC), reset counter
            row.reset_unread()
            return

        control = app.window.get_control()
        if app.window.is_active() and row.is_selected() and control.view_is_at_bottom():
            return

        assert message.text is not None
        row.add_unread(message.text)

    def _on_message_received(self, event: events.MessageReceived) -> None:
        row = self._chats.get((event.account, JID.from_string(event.jid)))
        if row is None:
            return

        message = event.message
        if message.text is None:
            return

        assert message.id is not None

        nick = self._get_nick_for_received_message(event.account, message)
        row.set_nick(nick)
        row.set_timestamp(message.timestamp)
        row.set_stanza_id(message.stanza_id)
        row.set_message_id(message.id)
        row.set_message_text(message.text, nickname=nick, oob=message.oob)

        self._add_unread(row, event)
        row.changed()

    def _on_message_deleted(self, event: events.MessageDeleted) -> None:
        # TODO
        pass

    def _on_message_corrected(self, event: events.MessageCorrected) -> None:
        row = self._chats.get((event.account, JID.from_string(event.jid)))
        if row is None:
            return

        if event.correction_id == row.message_id:
            text = event.message.text
            assert text is not None
            row.set_message_text(
                text, self._get_nick_for_received_message(event.account, event.message)
            )

    def _on_message_moderated(self, event: events.MessageModerated) -> None:
        row = self._chats.get((event.account, event.jid))
        if row is None:
            return

        if event.moderation.stanza_id == row.stanza_id:
            text = get_moderation_text(event.moderation.by, event.moderation.reason)
            row.set_message_text(text)

    def _on_message_retracted(self, event: events.MessageRetracted) -> None:
        row = self._chats.get((event.account, event.jid))
        if row is None:
            return

        if event.retraction.id in (row.message_id, row.stanza_id):
            row.set_message_text(get_retraction_text(event.retraction.timestamp))

    def _on_message_sent(self, event: events.MessageSent) -> None:
        row = self._chats.get((event.account, JID.from_string(event.jid)))
        if row is None:
            return

        message = event.message
        assert message.text is not None

        row.set_nick(_("Me"))
        row.set_timestamp(message.timestamp)
        row.set_message_text(
            message.text, nickname=app.nicks[event.account], oob=message.oob
        )
        row.changed()

    def _on_presence_received(self, event: events.PresenceReceived) -> None:
        row = self._chats.get((event.account, JID.from_string(event.jid)))
        if row is None:
            return
        row.update_avatar()

    def _on_jingle_request_received(self, event: events.JingleRequestReceived) -> None:
        content_types: list[str] = []
        for item in event.contents:
            content_types.append(item.media)
        if "audio" in content_types or "video" in content_types:
            # AV Call received
            row = self._chats.get((event.account, JID.from_string(event.jid)))
            if row is None:
                return
            row.set_timestamp(datetime.now().astimezone())
            row.set_nick("")
            row.set_message_text(_("Call"), icon_name="call-start-symbolic")

    def _on_file_request_received(self, event: events.FileRequestReceivedEvent) -> None:
        row = self._chats.get((event.account, event.jid))
        if row is None:
            return
        row.set_timestamp(datetime.now().astimezone())
        row.set_nick("")
        row.set_message_text(_("File"), icon_name="text-x-generic-symbolic")

    def _on_account_changed(self, *args: Any) -> None:
        for row in self._iterate_rows():
            row.update_account_identifier()

    def _on_bookmarks_received(self, _event: events.BookmarksReceived) -> None:
        for row in self._iterate_rows():
            row.update_name()
