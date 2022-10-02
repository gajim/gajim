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

from typing import Optional
from typing import Any
from typing import cast
from typing import Union

import logging
import time

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from nbxmpp import JID

from gajim.common import app
from gajim.common import ged
from gajim.common import events
from gajim.common.const import Direction
from gajim.common.const import RowHeaderType
from gajim.common.i18n import _
from gajim.common.helpers import get_group_chat_nick
from gajim.common.helpers import get_retraction_text
from gajim.common.setting_values import OpenChatsSettingT

from .chat_list_row import ChatListRow
from .util import EventHelper


log = logging.getLogger('gajim.gui.chatlist')

MessageEventT = Union[events.MessageReceived,
                      events.GcMessageReceived,
                      events.MamMessageReceived]


class ChatList(Gtk.ListBox, EventHelper):

    __gsignals__ = {
        'chat-order-changed': (GObject.SignalFlags.RUN_LAST,
                               None,
                               ()),
    }

    def __init__(self, workspace_id: str) -> None:
        Gtk.ListBox.__init__(self)
        EventHelper.__init__(self)
        self._workspace_id = workspace_id

        self._chats: dict[tuple[str, JID], Any] = {}
        self._current_filter: str = 'all'
        self._current_filter_text: str = ''

        self.get_style_context().add_class('chatlist')
        self.set_filter_func(self._filter_func)
        self.set_header_func(self._header_func)
        self.set_sort_func(self._sort_func)
        self._set_placeholder()

        self._mouseover: bool = False
        self.connect('enter-notify-event', self._on_mouse_focus_changed)
        self.connect('leave-notify-event', self._on_mouse_focus_changed)

        # Drag and Drop
        entries = [Gtk.TargetEntry.new(
            'CHAT_LIST_ITEM',
            Gtk.TargetFlags.SAME_APP,
            0)]
        self.drag_dest_set(
            Gtk.DestDefaults.MOTION | Gtk.DestDefaults.DROP,
            entries,
            Gdk.DragAction.MOVE)

        self._drag_row: Optional[ChatListRow] = None
        self._chat_order: list[ChatListRow] = []

        self.register_events([
            ('account-enabled', ged.GUI2, self._on_account_changed),
            ('account-disabled', ged.GUI2, self._on_account_changed),
            ('bookmarks-received', ged.GUI1, self._on_bookmarks_received),
        ])

        self.connect('drag-data-received', self._on_drag_data_received)
        self.connect('destroy', self._on_destroy)

        self._timer_id = GLib.timeout_add_seconds(60, self._update_time)

        self.show_all()

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    def get_unread_count(self) -> int:
        return sum(chats.unread_count for chats in self._chats.values())

    def get_chat_unread_count(self,
                              account: str,
                              jid: JID,
                              include_silent: bool = False
                              ) -> Optional[int]:
        chat = self._chats.get((account, jid))
        if chat is not None:
            if include_silent:
                return chat.get_real_unread_count()
            return chat.unread_count
        return None

    def set_chat_unread_count(self,
                              account: str,
                              jid: JID,
                              count: int
                              ) -> None:
        chat = self._chats.get((account, jid))
        if chat is not None:
            chat.unread_count = count

    def mark_as_read(self, account: str, jid: JID) -> None:
        chat = self._chats.get((account, jid))
        if chat is not None:
            chat.reset_unread()

    def _emit_unread_changed(self) -> None:
        count = self.get_unread_count()
        chat_list = self.get_parent()
        assert chat_list is not None
        chat_list.emit('unread-count-changed',
                       self._workspace_id,
                       count)

    def _get_row_before(self, row: ChatListRow) -> Optional[ChatListRow]:
        row_before = self.get_row_at_index(row.get_index() - 1)
        if row_before is None:
            return
        return cast(ChatListRow, row_before)

    def _get_row_after(self, row: ChatListRow) -> Optional[ChatListRow]:
        row_after = self.get_row_at_index(row.get_index() + 1)
        if row_after is None:
            return
        return cast(ChatListRow, row_after)

    def _get_last_row(self) -> ChatListRow:
        index = len(self.get_children()) - 1
        last_row = self.get_row_at_index(index)
        assert last_row is not None
        return cast(ChatListRow, last_row)

    def _on_row_drag_begin(self,
                           row: ChatListRow,
                           _drag_context: Gdk.DragContext
                           ) -> None:

        self._drag_row = row

    def _on_row_unread_changed(self, row: ChatListRow) -> None:
        self._emit_unread_changed()

    def _on_drag_data_received(self,
                               _widget: Gtk.Widget,
                               _drag_context: Gdk.DragContext,
                               _x_coord: int,
                               y_coord: int,
                               selection_data: Gtk.SelectionData,
                               _info: int,
                               _time: int
                               ) -> None:

        item_type = selection_data.get_data_type().name()
        if item_type != 'CHAT_LIST_ITEM':
            log.debug('Unknown item type dropped')
            return

        assert self._drag_row is not None

        if not self._drag_row.is_pinned:
            log.debug('Dropped row is not pinned')
            return

        row = cast(ChatListRow, self.get_row_at_y(y_coord))
        if row is not None:
            alloc = row.get_allocation()
            hover_row_y = alloc.y
            hover_row_height = alloc.height

            if y_coord < hover_row_y + hover_row_height / 2:
                row_before = self._get_row_before(row)
                row_after = row
            else:
                row_before = row
                row_after = self._get_row_after(row)
        else:
            row_before = self._get_last_row()
            row_after = None

        if self._drag_row in (row_before, row_after):
            log.debug('Dropped row on self')
            return

        if row_before is not None and not row_before.is_pinned:
            log.debug('Dropped under not pinned row')
            return

        self._change_pinned_order(row_before)

    def _change_pinned_order(self, row_before: Optional[ChatListRow]) -> None:
        assert self._drag_row is not None

        self._chat_order.remove(self._drag_row)

        if row_before is None:
            self._chat_order.insert(0, self._drag_row)
        else:
            offset = 0
            if row_before.position < self._drag_row.position:
                offset = 1
            self._chat_order.insert(
                row_before.position + offset, self._drag_row)

        for row in self._chat_order:
            row.position = self._chat_order.index(row)

        self.emit('chat-order-changed')
        self.invalidate_sort()

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        GLib.source_remove(self._timer_id)

    def _update_time(self) -> bool:
        for _key, row in self._chats.items():
            row.update_time()
        return True

    def _filter_func(self, row: ChatListRow) -> bool:
        is_groupchat = row.type == 'groupchat'
        if self._current_filter == 'chats' and is_groupchat:
            return False

        if self._current_filter == 'group_chats' and not is_groupchat:
            return False

        if not self._current_filter_text:
            return True
        text = self._current_filter_text.lower()
        return text in row.contact_name.lower()

    @staticmethod
    def _header_func(row: ChatListRow, before: ChatListRow) -> None:
        if before is None:
            if row.is_pinned:
                row.header = RowHeaderType.PINNED
            else:
                row.header = None
        else:
            if row.is_pinned:
                if before.is_pinned:
                    row.header = None
                else:
                    row.header = RowHeaderType.PINNED
            else:
                if before.is_pinned:
                    row.header = RowHeaderType.CONVERSATIONS
                else:
                    row.header = None

    def _sort_func(self, row1: ChatListRow, row2: ChatListRow) -> int:
        if self._mouseover:
            log.debug('Mouseover active, don’t sort rows')
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

    def _on_mouse_focus_changed(self,
                                _widget: Gtk.ListBox,
                                event: Gdk.EventCrossing
                                ) -> None:

        if event.type == Gdk.EventType.ENTER_NOTIFY:
            self._mouseover = True

        if event.type == Gdk.EventType.LEAVE_NOTIFY:
            if event.detail != Gdk.NotifyType.INFERIOR:
                # Not hovering a Gtk.ListBoxRow (row is INFERIOR)
                self._mouseover = False

    def _set_placeholder(self) -> None:
        button = Gtk.Button.new_with_label(_('Start Chat'))
        button.get_style_context().add_class('suggested-action')
        button.set_halign(Gtk.Align.CENTER)
        button.set_valign(Gtk.Align.CENTER)
        button.connect('clicked', self._on_start_chat_clicked)
        button.show()
        self.set_placeholder(button)

    @staticmethod
    def _on_start_chat_clicked(_button: Gtk.Button) -> None:
        app.app.activate_action('start-chat', GLib.Variant('as', ['', '']))

    def set_filter(self, name: str) -> None:
        self._current_filter = name
        self.invalidate_filter()

    def set_filter_text(self, text: str) -> None:
        self._current_filter_text = text
        self.invalidate_filter()

    def get_chat_type(self, account: str, jid: JID) -> Optional[str]:
        row = self._chats.get((account, jid))
        if row is not None:
            return row.type
        return None

    def add_chat(self,
                 account: str,
                 jid: JID,
                 type_: str,
                 pinned: bool,
                 position: int
                 ) -> None:

        key = (account, jid)
        if self._chats.get(key) is not None:
            # Chat is already in the List
            return

        row = ChatListRow(self._workspace_id,
                          account,
                          jid,
                          type_,
                          pinned,
                          position)

        self._chats[key] = row
        if pinned:
            self._chat_order.insert(position, row)

        row.connect('drag-begin', self._on_row_drag_begin)
        row.connect('unread-changed', self._on_row_unread_changed)

        self.add(row)

    def select_chat(self, account: str, jid: JID) -> None:
        row = self._chats[(account, jid)]
        self.select_row(row)

    def select_next_chat(self, direction: Direction,
                         unread_first: bool = False) -> None:
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
                    if index >= len(self.get_children()):
                        index = 0
                else:
                    index -= 1
                    if index < 0:
                        index = len(self.get_children()) - 1

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
                last = len(self.get_children()) - 1
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

    def toggle_chat_pinned(self, account: str, jid: JID) -> None:
        row = self._chats[(account, jid)]

        if row.is_pinned:
            self._chat_order.remove(row)
            row.position = -1
        else:
            self._chat_order.append(row)
            row.position = self._chat_order.index(row)

        row.toggle_pinned()
        self.invalidate_sort()

    def remove_chat(self,
                    account: str,
                    jid: JID,
                    emit_unread: bool = True
                    ) -> None:

        row = self._chats.pop((account, jid))
        if row.is_pinned:
            self._chat_order.remove(row)
        self.remove(row)
        row.destroy()
        if emit_unread:
            self._emit_unread_changed()

    def remove_chats_for_account(self, account: str) -> None:
        for row_account, jid in list(self._chats.keys()):
            if row_account != account:
                continue
            self.remove_chat(account, jid)
        self._emit_unread_changed()

    def get_selected_chat(self) -> Optional[ChatListRow]:
        row = cast(ChatListRow, self.get_selected_row())
        if row is None:
            return None
        return row

    def contains_chat(self, account: str, jid: JID) -> bool:
        return self._chats.get((account, jid)) is not None

    def get_open_chats(self) -> OpenChatsSettingT:
        open_chats: OpenChatsSettingT = []
        for key, row in self._chats.items():
            account, jid = key
            open_chats.append({'account': account,
                               'jid': jid,
                               'type': row.type,
                               'pinned': row.is_pinned,
                               'position': row.position})
        return open_chats

    def process_event(self, event: events.ChatListEventT) -> None:
        if isinstance(event, (events.MessageReceived,
                              events.MamMessageReceived,
                              events.GcMessageReceived)):
            self._on_message_received(event)
        elif isinstance(event, events.MessageUpdated):
            self._on_message_updated(event)
        elif isinstance(event, events.MessageModerated):
            self._on_message_moderated(event)
        elif isinstance(event, events.PresenceReceived):
            self._on_presence_received(event)
        elif isinstance(event, events.MessageSent):
            self._on_message_sent(event)
        elif isinstance(event, events.JingleRequestReceived):
            self._on_jingle_request_received(event)
        elif isinstance(event, events.FileRequestReceivedEvent):  # pyright: ignore [reportUnnecessaryIsInstance] # noqa
            self._on_file_request_received(event)
        else:
            log.warning('Unhandled Event: %s', event.name)

    def _on_message_received(self, event: MessageEventT) -> None:
        if not event.msgtxt:
            return
        row = self._chats.get((event.account, JID.from_string(event.jid)))
        if row is None:
            return
        nick = self._get_nick_for_received_message(event)
        row.set_nick(nick)
        if event.name == 'mam-message-received':
            row.set_timestamp(event.properties.mam.timestamp)
        else:
            row.set_timestamp(event.properties.timestamp)

        row.set_stanza_id(event.stanza_id)
        row.set_message_id(event.properties.id)
        row.set_message_text(
            event.msgtxt,
            nickname=nick,
            additional_data=event.additional_data)

        self._add_unread(row, event)
        row.changed()

    @staticmethod
    def _get_nick_for_received_message(event: MessageEventT) -> str:
        nick = _('Me')
        if event.properties.type.is_groupchat:
            event_nick = event.properties.muc_nickname
            our_nick = get_group_chat_nick(event.account, event.jid)
            if event_nick != our_nick:
                nick = event_nick
        else:
            con = app.get_client(event.account)
            own_jid = con.get_own_jid()
            if not own_jid.bare_match(event.properties.from_):
                nick = ''
        return nick

    def _on_message_updated(self, event: events.MessageUpdated) -> None:
        row = self._chats.get((event.account, JID.from_string(event.jid)))
        if row is None:
            return

        if event.correct_id == row.message_id:
            row.set_message_text(event.msgtxt, event.nickname)

    def _on_message_moderated(self, event: events.MessageModerated) -> None:
        row = self._chats.get((event.account, event.jid))
        if row is None:
            return

        if event.moderation.stanza_id == row.stanza_id:
            text = get_retraction_text(
                event.account,
                event.moderation.moderator_jid,
                event.moderation.reason)
            row.set_message_text(text)

    def _on_message_sent(self, event: events.MessageSent) -> None:
        msgtext = event.message
        if not msgtext:
            return

        row = self._chats.get((event.account, JID.from_string(event.jid)))
        if row is None:
            return

        client = app.get_client(event.account)
        own_jid = client.get_own_jid()

        if own_jid.bare_match(event.jid):
            nick = ''
        else:
            nick = _('Me')
        row.set_nick(nick)

        # Set timestamp if it's None (outgoing MUC messages)
        row.set_timestamp(event.timestamp or time.time())
        row.set_message_text(
            event.message,
            nickname=app.nicks[event.account],
            additional_data=event.additional_data)
        row.changed()

    def _on_presence_received(self, event: events.PresenceReceived) -> None:
        row = self._chats.get((event.account, JID.from_string(event.jid)))
        if row is None:
            return
        row.update_avatar()

    def _on_jingle_request_received(self,
                                    event: events.JingleRequestReceived
                                    ) -> None:
        content_types: list[str] = []
        for item in event.contents:
            content_types.append(item.media)
        if 'audio' in content_types or 'video' in content_types:
            # AV Call received
            row = self._chats.get((event.account, JID.from_string(event.jid)))
            if row is None:
                return
            row.set_timestamp(time.time())
            row.set_nick('')
            row.set_message_text(
                _('Call'), icon_name='call-start-symbolic')

    def _on_file_request_received(self,
                                  event: events.FileRequestReceivedEvent
                                  ) -> None:
        row = self._chats.get((event.account, event.jid))
        if row is None:
            return
        row.set_timestamp(time.time())
        row.set_nick('')
        row.set_message_text(
            _('File'), icon_name='text-x-generic-symbolic')

    @staticmethod
    def _add_unread(row: ChatListRow, event: MessageEventT) -> None:
        if event.properties.is_carbon_message:
            if event.properties.carbon.is_sent:
                return

        if event.properties.is_from_us():
            # Last message was from us (1:1), reset counter
            row.reset_unread()
            return

        our_nick = get_group_chat_nick(event.account, event.jid)
        if event.properties.muc_nickname == our_nick:
            # Last message was from us (MUC), reset counter
            row.reset_unread()
            return

        row.add_unread(event.msgtxt)

    def _on_account_changed(self, *args: Any) -> None:
        rows = cast(list[ChatListRow], self.get_children())
        for row in rows:
            row.update_account_identifier()

    def _on_bookmarks_received(self, _event: events.BookmarksReceived) -> None:
        rows = cast(list[ChatListRow], self.get_children())
        for row in rows:
            row.update_name()
