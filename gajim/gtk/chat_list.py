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
import pickle

from gi.repository import Gio
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
import cairo

from nbxmpp import JID

from gajim.common import app
from gajim.common import ged
from gajim.common import events
from gajim.common.const import AvatarSize
from gajim.common.const import Direction
from gajim.common.const import KindConstant
from gajim.common.const import RowHeaderType
from gajim.common.i18n import _
from gajim.common.helpers import get_groupchat_name
from gajim.common.helpers import get_group_chat_nick
from gajim.common.helpers import get_retraction_text
from gajim.common.helpers import get_uf_relative_time
from gajim.common.helpers import message_needs_highlight
from gajim.common.helpers import AdditionalDataDict
from gajim.common.preview_helpers import filename_from_uri
from gajim.common.preview_helpers import guess_simple_file_type
from gajim.common.types import ChatContactT
from gajim.common.types import OneOnOneContactT

from .menus import get_chat_list_row_menu
from .builder import get_builder
from .util import EventHelper

log = logging.getLogger('gajim.gui.chatlist')

MessageEventT = Union[events.MessageReceived,
                      events.GcMessageReceived,
                      events.MamMessageReceived]


class ChatList(Gtk.ListBox, EventHelper):
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

        self.register_events([
            ('account-enabled', ged.GUI2, self._on_account_changed),
            ('account-disabled', ged.GUI2, self._on_account_changed),
            ('bookmarks-received', ged.GUI1, self._on_bookmarks_received),
        ])

        self.connect('destroy', self._on_destroy)

        self._timer_id = GLib.timeout_add_seconds(60, self._update_timer)

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

    def emit_unread_changed(self) -> None:
        count = self.get_unread_count()
        chat_list = cast(ChatList, self.get_parent())
        chat_list.emit('unread-count-changed',
                       self._workspace_id,
                       count)

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        GLib.source_remove(self._timer_id)

    def _update_timer(self) -> bool:
        self.update_time()
        return True

    def _filter_func(self, row: ChatRow) -> bool:
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
    def _header_func(row: ChatRow, before: ChatRow) -> None:
        if before is None:
            if row.is_pinned:
                row.header = RowHeaderType.PINNED
            # elif row.is_active():
            #    row.header = RowHeaderType.ACTIVE
            else:
                row.header = None
        else:
            if row.is_pinned:
                if before.is_pinned:
                    row.header = None
                else:
                    row.header = RowHeaderType.PINNED
            # elif row.is_active():
            #    if before.is_active() and not before.is_pinned:
            #        row.header = None
            #    else:
            #        row.header = RowHeaderType.ACTIVE
            else:
                # if before.is_active() or before.is_pinned:
                if before.is_pinned:
                    row.header = RowHeaderType.CONVERSATIONS
                else:
                    row.header = None

    def _sort_func(self, row1: ChatRow, row2: ChatRow) -> int:
        if self._mouseover:
            log.debug('Mouseover active, don’t sort rows')
            return 0

        # Don’t sort pinned rows themselves
        if row1.is_pinned and row2.is_pinned:
            return 0

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
        app.app.activate_action('start-chat', GLib.Variant('s', ''))

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

    def add_chat(self, account: str, jid: JID, type_: str,
                 pinned: bool = False) -> None:
        if self._chats.get((account, jid)) is not None:
            # Chat is already in the List
            return

        row = ChatRow(self._workspace_id, account, jid, type_, pinned)
        self._chats[(account, jid)] = row
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
            assert isinstance(row, ChatRow)
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
                assert isinstance(row, ChatRow)
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
            assert isinstance(next_row, ChatRow)
            self.select_chat(next_row.account, next_row.jid)
            return

        assert isinstance(next_row, ChatRow)
        self.select_chat(next_row.account, next_row.jid)

    def select_chat_number(self, number: int) -> None:
        row = self.get_row_at_index(number)
        if row is not None:
            assert isinstance(row, ChatRow)
            self.select_chat(row.account, row.jid)

    def toggle_chat_pinned(self, account: str, jid: JID) -> None:
        row = self._chats[(account, jid)]
        row.toggle_pinned()
        self.invalidate_sort()

    def remove_chat(self, account: str, jid: JID,
                    emit_unread: bool = True) -> None:
        row = self._chats.pop((account, jid))
        self.remove(row)
        row.destroy()
        if emit_unread:
            self.emit_unread_changed()

    def remove_chats_for_account(self, account: str) -> None:
        for row_account, jid in list(self._chats.keys()):
            if row_account != account:
                continue
            self.remove_chat(account, jid)
        self.emit_unread_changed()

    def get_selected_chat(self) -> Optional[ChatRow]:
        row = cast(ChatRow, self.get_selected_row())
        if row is None:
            return None
        return row

    def contains_chat(self, account: str, jid: JID) -> bool:
        return self._chats.get((account, jid)) is not None

    def get_open_chats(self) -> list[tuple[str, JID, str, bool]]:
        open_chats: list[tuple[str, JID, str, bool]] = []
        for key, value in self._chats.items():
            open_chats.append(key + (value.type, value.is_pinned))
        return open_chats

    def update_time(self) -> None:
        for _key, row in self._chats.items():
            row.update_time()

    def process_event(self, event: events.ApplicationEvent) -> None:
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
        elif isinstance(event, events.FileRequestReceivedEvent):
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
        row.set_message_id(event.unique_id)
        row.set_message_text(
            event.msgtxt,
            nickname=nick,
            additional_data=event.additional_data)

        self._add_unread(row, event)
        self.invalidate_sort()

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
        self.invalidate_sort()

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
    def _add_unread(row: ChatRow, event: MessageEventT) -> None:
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
        rows = cast(list[ChatRow], self.get_children())
        for row in rows:
            row.update_account_identifier()

    def _on_bookmarks_received(self, _event: events.BookmarksReceived) -> None:
        rows = cast(list[ChatRow], self.get_children())
        for row in rows:
            row.update_name()


class ChatRow(Gtk.ListBoxRow):
    def __init__(self, workspace_id: str, account: str, jid: JID, type_: str,
                 pinned: bool) -> None:
        Gtk.ListBoxRow.__init__(self)

        self.account = account
        self.jid = jid
        self.workspace_id = workspace_id
        self.type = type_

        self.active_label = ActiveHeader()
        self.conversations_label = ConversationsHeader()
        self.pinned_label = PinnedHeader()

        self._client = app.get_client(account)
        self.contact = self._client.get_module('Contacts').get_contact(jid)
        self.contact.connect('presence-update', self._on_presence_update)
        self.contact.connect('chatstate-update', self._on_chatstate_update)
        self.contact.connect('nickname-update', self._on_nickname_update)
        self.contact.connect('caps-update', self._on_avatar_update)
        self.contact.connect('avatar-update', self._on_avatar_update)

        self.contact_name: str = self.contact.name
        self.timestamp: float = 0
        self.stanza_id: Optional[str] = None
        self.message_id: Optional[str] = None
        self._unread_count: int = 0
        self._needs_muc_highlight: bool = False
        self._pinned: bool = pinned

        self.get_style_context().add_class('chatlist-row')

        self._ui = get_builder('chat_list_row.ui')
        self.add(self._ui.eventbox)

        self.connect('state-flags-changed', self._on_state_flags_changed)
        self._ui.eventbox.connect('button-press-event', self._on_button_press)
        self._ui.close_button.connect('clicked', self._on_close_button_clicked)

        # Drag and Drop
        entries = [Gtk.TargetEntry.new(
            'CHAT_LIST_ITEM',
            Gtk.TargetFlags.SAME_APP,
            0)]
        self._ui.eventbox.drag_source_set(
            Gdk.ModifierType.BUTTON1_MASK,
            entries,
            Gdk.DragAction.MOVE)
        self._ui.eventbox.connect('drag-begin', self._on_drag_begin)
        self._ui.eventbox.connect('drag-data-get', self._on_drag_data_get)

        if self.type == 'groupchat':
            self._ui.group_chat_indicator.show()

        self.update_avatar()
        self.update_name()
        self.update_account_identifier()

        if self.contact.is_groupchat and not self.contact.can_notify():
            self._ui.unread_label.get_style_context().add_class(
                'unread-counter-silent')

        # Get last chat message from archive
        line = app.storage.archive.get_last_conversation_line(account, jid)

        if line is None:
            self.show_all()
            return

        if line.message is not None:
            message_text = line.message

            if line.additional_data is not None:
                retracted_by = line.additional_data.get_value(
                    'retracted', 'by')
                if retracted_by is not None:
                    reason = line.additional_data.get_value(
                        'retracted', 'reason')
                    message_text = get_retraction_text(
                        self.account, retracted_by, reason)

            me_nickname = None
            if line.kind in (KindConstant.CHAT_MSG_SENT,
                             KindConstant.SINGLE_MSG_SENT):
                self.set_nick(_('Me'))
                me_nickname = app.nicks[account]

            if line.kind == KindConstant.GC_MSG:
                our_nick = get_group_chat_nick(account, jid)
                if line.contact_name == our_nick:
                    self.set_nick(_('Me'))
                    me_nickname = our_nick
                else:
                    self.set_nick(line.contact_name)
                    me_nickname = line.contact_name

            self.set_message_text(
                message_text,
                nickname=me_nickname,
                additional_data=line.additional_data)

            self.timestamp = line.time
            uf_timestamp = get_uf_relative_time(line.time)
            self._ui.timestamp_label.set_text(uf_timestamp)

            self.stanza_id = line.stanza_id
            self.message_id = line.message_id

        if line.kind in (KindConstant.FILE_TRANSFER_INCOMING,
                         KindConstant.FILE_TRANSFER_OUTGOING):
            self.set_message_text(
                _('File'), icon_name='text-x-generic-symbolic')
            self.timestamp = line.time
            uf_timestamp = get_uf_relative_time(line.time)
            self._ui.timestamp_label.set_text(uf_timestamp)

        if line.kind in (KindConstant.CALL_INCOMING,
                         KindConstant.CALL_OUTGOING):
            self.set_message_text(
                _('Call'), icon_name='call-start-symbolic')
            self.timestamp = line.time
            uf_timestamp = get_uf_relative_time(line.time)
            self._ui.timestamp_label.set_text(uf_timestamp)

        self.show_all()

    @property
    def header(self) -> Optional[RowHeaderType]:
        header = self.get_header()
        if header is None:
            return None
        assert isinstance(header, BaseHeader)
        return header.type

    @header.setter
    def header(self, type_: Optional[RowHeaderType]) -> None:
        if type_ == self.header:
            return
        if type_ is None:
            self.set_header(None)
        elif type_ is RowHeaderType.PINNED:
            self.set_header(self.pinned_label)
        elif type_ == RowHeaderType.ACTIVE:
            self.set_header(self.active_label)
        else:
            self.set_header(self.conversations_label)

    @property
    def is_pinned(self) -> bool:
        return self._pinned

    def _on_button_press(self,
                         _widget: Gtk.Widget,
                         event: Gdk.EventButton
                         ) -> None:
        if event.button == 3:  # right click
            self._popup_menu(event)
        elif event.button == 2:  # middle click
            app.window.activate_action(
                'remove-chat',
                GLib.Variant('as', [self.account, str(self.jid)]))

    def _popup_menu(self, event: Gdk.EventButton):
        menu = get_chat_list_row_menu(
            self.workspace_id, self.account, self.jid, self._pinned)

        rectangle = Gdk.Rectangle()
        rectangle.x = int(event.x)
        rectangle.y = int(event.y)
        rectangle.width = rectangle.height = 1

        popover = Gtk.Popover.new_from_model(self, menu)
        popover.set_relative_to(self)
        popover.set_position(Gtk.PositionType.RIGHT)
        popover.set_pointing_to(rectangle)
        popover.popup()

    def _on_drag_begin(self,
                       widget: Gtk.Widget,
                       drag_context: Gdk.DragContext
                       ) -> None:
        # Use rendered ChatListRow as drag icon
        alloc = self.get_allocation()
        surface = cairo.ImageSurface(
            cairo.Format.ARGB32, alloc.width, alloc.height)
        context = cairo.Context(surface)
        self.draw(context)
        coords = widget.translate_coordinates(self, 0, 0)
        if coords is None:
            return
        dest_x, dest_y = coords
        surface.set_device_offset(-dest_x, -dest_y)
        Gtk.drag_set_icon_surface(drag_context, surface)

    def _on_drag_data_get(self,
                          _widget: Gtk.Widget,
                          _drag_context: Gdk.DragContext,
                          selection_data: Gtk.SelectionData,
                          _info: int,
                          _time: int
                          ) -> None:
        drop_type = Gdk.Atom.intern_static_string('CHAT_LIST_ITEM')
        byte_data = pickle.dumps((self.account, self.jid))
        selection_data.set(drop_type, 8, byte_data)

    def toggle_pinned(self) -> None:
        self._pinned = not self._pinned

    def _on_presence_update(self,
                            _contact: ChatContactT,
                            _signal_name: str
                            ) -> None:
        self.update_avatar()

    def _on_avatar_update(self,
                          _contact: ChatContactT,
                          _signal_name: str
                          ) -> None:
        self.update_avatar()

    def update_avatar(self) -> None:
        scale = self.get_scale_factor()
        surface = self.contact.get_avatar(AvatarSize.ROSTER, scale)
        self._ui.avatar_image.set_from_surface(surface)

    def update_name(self) -> None:
        if self.type == 'pm':
            client = app.get_client(self.account)
            muc_name = get_groupchat_name(client, self.jid.new_as_bare())
            self._ui.name_label.set_text(f'{self.contact.name} ({muc_name})')
            return

        self.contact_name = self.contact.name
        if self.jid == self._client.get_own_jid().bare:
            self.contact_name = _('Note to myself')
        self._ui.name_label.set_text(self.contact_name)

    def update_account_identifier(self) -> None:
        account_class = app.css_config.get_dynamic_class(self.account)
        self._ui.account_identifier.get_style_context().add_class(account_class)
        show = len(app.settings.get_active_accounts()) > 1
        self._ui.account_identifier.set_visible(show)

    def _on_chatstate_update(self,
                             contact: OneOnOneContactT,
                             _signal_name: str
                             ) -> None:
        if contact.chatstate is None:
            self._ui.chatstate_image.hide()
        else:
            self._ui.chatstate_image.set_visible(contact.chatstate.is_composing)

    def _on_nickname_update(self,
                            _contact: ChatContactT,
                            _signal_name: str
                            ) -> None:
        self.update_name()

    def get_real_unread_count(self) -> int:
        return self._unread_count

    @property
    def unread_count(self) -> int:
        if (self.contact.is_groupchat and not self.contact.can_notify() and
                not self._needs_muc_highlight):
            return 0
        return self._unread_count

    @unread_count.setter
    def unread_count(self, value: int) -> None:
        self._unread_count = value
        self._update_unread()
        chat_list = cast(ChatList, self.get_parent())
        chat_list.emit_unread_changed()

    def _update_unread(self) -> None:
        unread_count = self._get_unread_string(self._unread_count)
        self._ui.unread_label.set_text(unread_count)
        self._ui.unread_label.set_visible(bool(self._unread_count))

    @staticmethod
    def _get_unread_string(count: int) -> str:
        if count < 1000:
            return str(count)
        return '999+'

    def add_unread(self, text: str) -> None:
        control = app.window.get_control()
        if (self.is_active and
                control.is_loaded(self.account, self.jid) and
                control.get_autoscroll()):
            return

        self._unread_count += 1
        self._update_unread()
        app.storage.cache.set_unread_count(
            self.account,
            self.jid,
            self.get_real_unread_count(),
            self.message_id,
            self.timestamp)

        if self.contact.is_groupchat:
            needs_highlight = message_needs_highlight(
                text,
                self.contact.nickname,
                self._client.get_own_jid().bare)
            if needs_highlight:
                self._needs_muc_highlight = True
                self._ui.unread_label.get_style_context().remove_class(
                    'unread-counter-silent')

        chat_list = cast(ChatList, self.get_parent())
        chat_list.emit_unread_changed()

    def reset_unread(self) -> None:
        self._needs_muc_highlight = False
        self._unread_count = 0
        self._update_unread()
        chat_list = cast(ChatList, self.get_parent())
        chat_list.emit_unread_changed()
        app.storage.cache.reset_unread_count(self.account, self.jid)

        # Add class again in case we were mentioned previously
        if self.contact.is_groupchat and not self.contact.can_notify():
            self._ui.unread_label.get_style_context().add_class(
                'unread-counter-silent')

    @property
    def is_active(self) -> bool:
        return (self.is_selected() and
                self.get_toplevel().get_property('is-active'))

    @property
    def is_recent(self) -> bool:
        if self._unread_count:
            return True
        return False

    def _on_state_flags_changed(self,
                                _row: ChatRow,
                                _flags: Gtk.StateFlags
                                ) -> None:
        state = self.get_state_flags()
        if (state & Gtk.StateFlags.PRELIGHT) != 0:
            self._ui.revealer.set_reveal_child(True)
        else:
            self._ui.revealer.set_reveal_child(False)

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        app.window.activate_action(
            'remove-chat',
            GLib.Variant('as', [self.account, str(self.jid)]))

    def set_timestamp(self, timestamp: int) -> None:
        self.timestamp = timestamp
        self.update_time()

    def set_stanza_id(self, stanza_id: str) -> None:
        self.stanza_id = stanza_id

    def set_message_id(self, message_id: str) -> None:
        self.message_id = message_id

    def update_time(self) -> None:
        if self.timestamp == 0:
            return
        self._ui.timestamp_label.set_text(
            get_uf_relative_time(self.timestamp))

    def set_nick(self, nickname: str) -> None:
        self._ui.nick_label.set_visible(bool(nickname))
        self._ui.nick_label.set_text(
            _('%(nickname)s:') % {'nickname': nickname})

    def set_message_text(self,
                         text: str,
                         nickname: Optional[str] = None,
                         icon_name: Optional[str] = None,
                         additional_data: Optional[AdditionalDataDict] = None
                         ) -> None:
        icon = None
        if icon_name is not None:
            icon = Gio.Icon.new_for_string(icon_name)
        if additional_data is not None:
            if app.preview_manager.is_previewable(text, additional_data):
                file_name = filename_from_uri(text)
                icon, file_type = guess_simple_file_type(text)
                text = f'{file_type} ({file_name})'

        text = GLib.markup_escape_text(text)
        if text.startswith('/me') and nickname is not None:
            nickname = GLib.markup_escape_text(nickname)
            text = text.replace('/me', f'* {nickname}', 1)
            text = f'<i>{text}</i>'

        # Split by newline and display last line (or first, if last is newline)
        lines = text.split('\n')
        text = lines[-1] or lines[0]
        self._ui.message_label.set_markup(text)

        if icon is None:
            self._ui.message_icon.hide()
        else:
            self._ui.message_icon.set_from_gicon(icon, Gtk.IconSize.MENU)
            self._ui.message_icon.show()


class BaseHeader(Gtk.Box):
    def __init__(self, row_type: RowHeaderType, text: str) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.type = row_type
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        self.add(label)
        self.get_style_context().add_class('header-box')
        self.show_all()


class ActiveHeader(BaseHeader):

    def __init__(self):
        BaseHeader.__init__(self,
                            RowHeaderType.ACTIVE,
                            _('Active'))


class ConversationsHeader(BaseHeader):

    def __init__(self):
        BaseHeader.__init__(self,
                            RowHeaderType.CONVERSATIONS,
                            _('Conversations'))


class PinnedHeader(BaseHeader):

    def __init__(self):
        BaseHeader.__init__(self,
                            RowHeaderType.PINNED,
                            _('Pinned'))
        self.get_style_context().add_class('header-box-first')
