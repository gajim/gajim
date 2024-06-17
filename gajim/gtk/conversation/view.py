# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal

import logging
from collections.abc import Generator
from datetime import datetime
from datetime import timedelta

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.errors import StanzaError
from nbxmpp.protocol import JID
from nbxmpp.structs import MucSubject

from gajim.common import app
from gajim.common import events
from gajim.common import types
from gajim.common.const import Direction
from gajim.common.helpers import get_start_of_day
from gajim.common.helpers import to_user_string
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.httpupload import HTTPFileTransfer
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.models import Message
from gajim.common.types import ChatContactT

from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.call import CallRow
from gajim.gtk.conversation.rows.command_output import CommandOutputRow
from gajim.gtk.conversation.rows.date import DateRow
from gajim.gtk.conversation.rows.encryption_info import EncryptionInfoRow
from gajim.gtk.conversation.rows.file_transfer import FileTransferRow
from gajim.gtk.conversation.rows.file_transfer_jingle import \
    FileTransferJingleRow
from gajim.gtk.conversation.rows.info import InfoMessage
from gajim.gtk.conversation.rows.message import MessageRow
from gajim.gtk.conversation.rows.muc_join_left import MUCJoinLeft
from gajim.gtk.conversation.rows.muc_subject import MUCSubject
from gajim.gtk.conversation.rows.read_marker import ReadMarkerRow
from gajim.gtk.conversation.rows.scroll_hint import ScrollHintRow
from gajim.gtk.conversation.rows.user_status import UserStatus
from gajim.gtk.conversation.rows.widgets import MessageRowActions

log = logging.getLogger('gajim.gtk.conversation_view')


class ConversationView(Gtk.ScrolledWindow):

    __gsignals__ = {
        'request-history': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (bool, )
        ),
        'autoscroll-changed': (
            GObject.SignalFlags.RUN_LAST,
            None,
            (bool,)
        )
    }

    def __init__(self, message_row_actions: MessageRowActions) -> None:
        Gtk.ScrolledWindow.__init__(self)

        self.set_overlay_scrolling(False)
        self.get_style_context().add_class('scrolled-no-border')
        self.get_style_context().add_class('no-scroll-indicator')
        self.get_style_context().add_class('scrollbar-style')
        self.set_shadow_type(Gtk.ShadowType.IN)
        self.set_vexpand(True)

        self.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        # This is a workaround: as soon as a line break occurs in Gtk.TextView
        # with word-char wrapping enabled, a hyphen character is automatically
        # inserted before the line break. This triggers the hscrollbar to show,
        # see: https://gitlab.gnome.org/GNOME/gtk/-/issues/2384
        # Using set_hscroll_policy(Gtk.Scrollable.Policy.NEVER) would cause bad
        # performance during resize, and prevent the window from being shrunk
        # horizontally under certain conditions (applies to GroupchatControl)
        self.get_hscrollbar().hide()

        self._message_row_actions = message_row_actions

        self._contact: ChatContactT | None = None
        self._client = None

        self._list_box = Gtk.ListBox()

        # Keeps track of the number of rows shown in ConversationView
        self._row_count: int = 0
        self._max_row_count: int = 100

        # Keeps track of date rows we have added to the list
        self._active_date_rows: set[datetime] = set()

        self._message_id_row_map: dict[str, MessageRow] = {}
        self._stanza_id_row_map: dict[str, MessageRow] = {}

        self._read_marker_row = None
        self._scroll_hint_row = None

        self._current_upper: float = 0
        self._autoscroll: bool = True
        self._request_history_at_upper: float | None = None
        self._upper_complete: bool = False
        self._lower_complete: bool = True
        self._requesting: str | None = None
        self._block_signals = False

        self._signal_handlers_enabled = False
        self._signal_handler_ids = (0, 0)

        self.add(self._list_box)
        self.set_focus_vadjustment(Gtk.Adjustment())

        app.window.get_action('scroll-view-up').connect(
            'activate', self._on_scroll_view)
        app.window.get_action('scroll-view-down').connect(
            'activate', self._on_scroll_view)

    def copy_selected_messages(self) -> None:
        format_string = app.settings.get('date_time_format')
        selection_text = ''
        for row in cast(list[BaseRow], self._list_box.get_selected_rows()):
            if isinstance(row, MessageRow):
                timestamp_formatted = row.timestamp.strftime(format_string)
                selection_text += (f'{timestamp_formatted} - {row.name}:\n'
                                   f'{row.get_text()}\n')

        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(selection_text, -1)

        self.disable_row_selection()

    def enable_row_selection(self,
                             pk: int | None
                             ) -> None:

        self._list_box.set_selection_mode(Gtk.SelectionMode.MULTIPLE)

        if pk is not None:
            row = self.get_row_by_pk(pk)
            self._list_box.select_row(row)

        for row in self.iter_rows():
            row.enable_selection_mode()

    def disable_row_selection(self) -> None:
        self._list_box.unselect_all()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)

        for row in self.iter_rows():
            row.disable_selection_mode()

    def _on_scroll_view(self,
                        action: Gio.SimpleAction,
                        _param: Literal[None]) -> None:

        action_name = action.get_name()
        if action_name == 'scroll-view-down':
            self.emit('scroll-child', Gtk.ScrollType.PAGE_DOWN, False)

        elif action_name == 'scroll-view-up':
            self.emit('scroll-child', Gtk.ScrollType.PAGE_UP, False)

    def _enable_signal_handlers(self, enable: bool) -> None:
        if self._signal_handlers_enabled == enable:
            return

        vadjustment = self.get_vadjustment()

        if enable:
            upper_id = vadjustment.connect('notify::upper',
                                           self._on_adj_upper_changed)
            value_id = vadjustment.connect('notify::value',
                                           self._on_adj_value_changed)
            self._signal_handler_ids = (upper_id, value_id)
        else:
            upper_id, value_id = self._signal_handler_ids
            vadjustment.disconnect(upper_id)
            vadjustment.disconnect(value_id)

        self._signal_handlers_enabled = enable

    def clear(self) -> None:
        app.settings.disconnect_signals(self)
        self._enable_signal_handlers(False)
        self._reset()

        self._contact = None
        self._client = None

    def switch_contact(self, contact: ChatContactT) -> None:
        self._contact = contact
        self._client = app.get_client(contact.account)

        self._enable_signal_handlers(False)
        self._block_signals = True
        self._reset()

        self.disable_row_selection()

        self._read_marker_row = ReadMarkerRow(self._contact)
        self._list_box.add(self._read_marker_row)

        self._scroll_hint_row = ScrollHintRow(self._contact.account)
        self._list_box.add(self._scroll_hint_row)

        app.settings.disconnect_signals(self)

        app.settings.connect_signal('print_join_left',
                                    self._on_contact_setting_changed,
                                    account=contact.account,
                                    jid=contact.jid)

        app.settings.connect_signal('print_status',
                                    self._on_contact_setting_changed,
                                    account=contact.account,
                                    jid=contact.jid)

        self._block_signals = False
        self._enable_signal_handlers(True)

    def get_autoscroll(self) -> bool:
        return self._autoscroll

    def block_signals(self, value: bool) -> None:
        self._block_signals = value

    def _emit(self, signal_name: str, *args: Any) -> None:
        if not self._block_signals:
            log.debug('emit %s, %s', signal_name, args)
            self.emit(signal_name, *args)

    def _reset_list_box(self) -> None:
        self._list_box.destroy()
        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.set_sort_func(self._sort_func)
        self._list_box.show()

        current_child = self.get_child()
        assert current_child is not None
        current_child.destroy()
        self.add(self._list_box)

    def _reset(self) -> None:
        self._current_upper = 0
        self._autoscroll = True
        self._request_history_at_upper = None
        self._upper_complete = False
        self._lower_complete = True
        self._requesting = None
        self.set_history_complete(True, False)

        self._reset_list_box()

        self._row_count = 0
        self._active_date_rows = set()
        self._message_id_row_map = {}
        self._stanza_id_row_map = {}
        self._read_marker_row = None
        self._scroll_hint_row = None

    def reset(self) -> None:
        assert self._contact is not None
        self.switch_contact(self._contact)

    def set_history_complete(self, before: bool, complete: bool) -> None:
        if before:
            self._upper_complete = complete
            if self._scroll_hint_row is None:
                return
            self._scroll_hint_row.set_history_complete(complete)
        else:
            self._lower_complete = complete

    def get_lower_complete(self) -> bool:
        return self._lower_complete

    def _on_adj_upper_changed(self,
                              adj: Gtk.Adjustment,
                              _pspec: GObject.ParamSpec) -> None:

        upper = adj.get_upper()
        diff = upper - self._current_upper

        if diff != 0:
            self._current_upper = upper
            if self._autoscroll:
                adj.set_value(adj.get_upper() - adj.get_page_size())
            else:
                # Workaround
                # https://gitlab.gnome.org/GNOME/gtk/merge_requests/395
                self.set_kinetic_scrolling(True)
                if self._requesting == 'before':
                    adj.set_value(adj.get_value() + diff)

        if upper == adj.get_page_size():
            # There is no scrollbar
            if not self._block_signals:
                self._emit('request-history', True)
            self._lower_complete = True
            self._autoscroll = True
            self._emit('autoscroll-changed', self._autoscroll)

        self._requesting = None

    def _on_adj_value_changed(self,
                              adj: Gtk.Adjustment,
                              _pspec: GObject.ParamSpec) -> None:

        if self._requesting is not None:
            return

        bottom = adj.get_upper() - adj.get_page_size()

        self._autoscroll = bottom - adj.get_value() < 1
        self._emit('autoscroll-changed', self._autoscroll)

        if self._upper_complete:
            self._request_history_at_upper = None
            if self._lower_complete:
                return

        if self._request_history_at_upper == adj.get_upper():
            # Abort here if we already did a history request and the upper
            # did not change. This can happen if we scroll very fast and the
            # value changes while the request has not been fulfilled.
            return

        self._request_history_at_upper = None

        distance = adj.get_page_size() * 2
        if adj.get_value() < distance:
            # Load messages when we are near the top
            if self._upper_complete:
                return
            self._request_history_at_upper = adj.get_upper()
            # Workaround: https://gitlab.gnome.org/GNOME/gtk/merge_requests/395
            self.set_kinetic_scrolling(False)
            if not self._block_signals:
                self._emit('request-history', True)
            self._requesting = 'before'

        elif (adj.get_upper() - (adj.get_value() + adj.get_page_size()) <
                distance):
            # ..or near the bottom
            if self._lower_complete:
                return
            # Workaround: https://gitlab.gnome.org/GNOME/gtk/merge_requests/395
            self.set_kinetic_scrolling(False)
            if not self._block_signals:
                self._emit('request-history', False)
            self._requesting = 'after'

    @property
    def contact(self) -> types.ChatContactT:
        assert self._contact is not None
        return self._contact

    def _get_row_at_index(self, index: int) -> BaseRow:
        row = self._list_box.get_row_at_index(index)
        assert row is not None
        return cast(BaseRow, row)

    def get_first_row(self
    ) -> MessageRow | CallRow | FileTransferJingleRow | None:
        for row in self._list_box.get_children():
            if isinstance(row, MessageRow | CallRow | FileTransferJingleRow):
                return row
        return None

    def get_last_row(
        self
    ) -> MessageRow | CallRow | FileTransferJingleRow | None:
        children = reversed(self._list_box.get_children())
        for row in children:
            if isinstance(row, MessageRow | CallRow | FileTransferJingleRow):
                return row
        return None

    def get_first_message_row(self
    ) -> MessageRow | None:
        for row in self._list_box.get_children():
            if isinstance(row, MessageRow):
                return row
        return None

    def get_last_message_row(
        self
    ) -> MessageRow | None:
        children = reversed(self._list_box.get_children())
        for row in children:
            if isinstance(row, MessageRow):
                return row
        return None

    def get_first_event_row(self) -> InfoMessage | MUCJoinLeft | None:
        for row in self._list_box.get_children():
            if isinstance(row, InfoMessage | MUCJoinLeft):
                return row
        return None

    def get_last_event_row(self) -> InfoMessage | MUCJoinLeft | None:
        children = self._list_box.get_children()
        children.reverse()
        for row in children:
            if isinstance(row, InfoMessage | MUCJoinLeft):
                return row
        return None

    @staticmethod
    def _sort_func(row1: BaseRow, row2: BaseRow) -> int:
        if row1.timestamp == row2.timestamp:
            return 0
        return -1 if row1.timestamp < row2.timestamp else 1

    def add_muc_subject(self,
                        subject: MucSubject,
                        timestamp: float | None = None
                        ) -> None:

        muc_subject = MUCSubject(self.contact.account, subject, timestamp)
        self._insert_message(muc_subject)

    def add_muc_user_left(self,
                          event: events.MUCUserLeft,
                          error: bool = False
                          ) -> None:

        assert isinstance(self._contact, GroupchatContact)
        if not self._contact.settings.get('print_join_left'):
            return
        join_left = MUCJoinLeft('muc-user-left',
                                self._contact.account,
                                event.nick,
                                reason=event.reason,
                                error=error,
                                timestamp=event.timestamp)
        self._insert_message(join_left)

    def add_muc_user_joined(self, event: events.MUCUserJoined) -> None:
        assert isinstance(self._contact, GroupchatContact)
        if not self._contact.settings.get('print_join_left'):
            return
        join_left = MUCJoinLeft('muc-user-joined',
                                self._contact.account,
                                event.nick,
                                timestamp=event.timestamp)
        self._insert_message(join_left)

    def add_user_status(self, name: str, show: str, status: str) -> None:
        user_status = UserStatus(self.contact.account, name, show, status)
        self._insert_message(user_status)

    def add_info_message(self,
                         text: str,
                         timestamp: datetime | None = None
                         ) -> None:

        message = InfoMessage(self.contact.account, text, timestamp)
        self._insert_message(message)

    def add_file_transfer(self, transfer: HTTPFileTransfer) -> None:
        transfer_row = FileTransferRow(self.contact.account, transfer)
        self._insert_message(transfer_row)

    def add_jingle_file_transfer(
        self,
        event: (events.FileRequestReceivedEvent |
                events.FileRequestSent |
                None) = None,
        message: Message | None = None
    ) -> None:

        assert isinstance(self._contact, BareContact)
        jingle_transfer_row = FileTransferJingleRow(
            self._contact.account,
            self._contact,
            event=event,
            message=message)
        self._insert_message(jingle_transfer_row)

    def add_encryption_info(self, event: events.EncryptionInfo) -> None:
        assert self._contact is not None
        self._insert_message(EncryptionInfoRow(event))

    def add_call_message(self,
                         event: events.JingleRequestReceived | None = None,
                         message: Message | None = None
                         ) -> None:
        assert isinstance(self._contact, BareContact)
        call_row = CallRow(
            self._contact.account,
            self._contact,
            event=event,
            message=message)
        self._insert_message(call_row)

    def add_command_output(self, text: str, is_error: bool) -> None:
        command_output_row = CommandOutputRow(
            self.contact.account, text, is_error)
        self._insert_message(command_output_row)

    def add_message_from_db(self, message: Message) -> None:
        message_row = MessageRow.from_db_row(self.contact, message)
        message_row.connect(
            'state-flags-changed', self._on_message_row_state_flags_changed)
        message_id = message.id
        stanza_id = message.stanza_id

        if stanza_id is not None:
            self._stanza_id_row_map[stanza_id] = message_row

        if message_id is not None:
            self._message_id_row_map[message_id] = message_row

        if message.corrections:
            # Store the same MessageRow object also with the message id
            # of the last correction, because we need it for XEP-0184 Receipts
            # which does not reference the original message id.
            corr_message_id = message.get_last_correction().id
            if corr_message_id is not None:
                self._message_id_row_map[corr_message_id] = message_row

        if message.direction == ChatDirection.INCOMING:
            assert self._read_marker_row is not None
            self._read_marker_row.set_last_incoming_timestamp(
                message_row.timestamp)

        if message.markers:
            assert message_id is not None
            self.set_read_marker(message_id)

        self._insert_message(message_row)

    def _insert_message(self, message: BaseRow) -> None:
        self._list_box.add(message)
        self._add_date_row(message.timestamp)
        self._check_for_merge(message)
        assert self._read_marker_row is not None

        if message.direction == ChatDirection.INCOMING:
            if message.timestamp > self._read_marker_row.timestamp:
                self._read_marker_row.hide()

    def _add_date_row(self, timestamp: datetime) -> None:
        start_of_day = get_start_of_day(timestamp.astimezone())
        if start_of_day in self._active_date_rows:
            return

        date_row = DateRow(self.contact.account, start_of_day)
        self._active_date_rows.add(start_of_day)
        self._list_box.add(date_row)

        row = self._list_box.get_row_at_index(date_row.get_index() + 1)
        if row is None:
            return

        if not isinstance(row, MessageRow):
            return

        row.set_merged(False)

    def _check_for_merge(self, message: BaseRow) -> None:
        if not isinstance(message, MessageRow):
            return

        if not app.settings.get('chat_merge_consecutive_nickname'):
            return

        ancestor = self._find_ancestor(message)
        if ancestor is None:
            self._update_descendants(message)
        else:
            message.set_merged(message.is_mergeable(ancestor))

    def _find_ancestor(self, message: MessageRow) -> MessageRow | None:
        index = message.get_index()
        while index != 0:
            index -= 1
            row = self._list_box.get_row_at_index(index)
            if row is None:
                return None

            if isinstance(row, ReadMarkerRow):
                continue

            if not isinstance(row, MessageRow):
                return None

            if not message.is_same_sender(row):
                return None

            if not row.is_merged:
                return row
        return None

    def _update_descendants(self, message: MessageRow) -> None:
        index = message.get_index()
        while True:
            index += 1
            row = self._list_box.get_row_at_index(index)
            if row is None:
                return

            if isinstance(row, ReadMarkerRow):
                continue

            if not isinstance(row, MessageRow):
                return

            merge = message.is_mergeable(row)
            row.set_merged(merge)
            return

    def _on_message_row_state_flags_changed(
        self,
        row: MessageRow,
        previous_flags: Gtk.StateFlags
    ) -> None:
        current_flags = self.get_state_flags()

        if (current_flags & Gtk.StateFlags.BACKDROP or
                previous_flags & Gtk.StateFlags.BACKDROP):
            # Don't react to backdrop changes and focus changes when in background
            return

        if previous_flags & Gtk.StateFlags.PRELIGHT:
            self._message_row_actions.hide_actions()
        else:
            coords = row.translate_coordinates(self, 0, 0)
            if coords is None:
                return
            _x_coord, y_coord = coords
            self._message_row_actions.update(y_coord, row)

    def remove_message(self, pk: int) -> None:
        row = self.get_row_by_pk(pk)
        if row is None:
            return

        self._remove_from_maps(row)
        index = row.get_index()
        row.destroy()
        decendant_row = self._list_box.get_row_at_index(index)
        if isinstance(decendant_row, MessageRow):
            # Unset possible merged state if we delete a 'top level' message.
            # Checks for same sender etc. are not necessary, since we simply
            # unset merged state.
            decendant_row.set_merged(False)

    def _remove_from_maps(self, row: MessageRow) -> None:
        for key, val in dict(self._message_id_row_map).items():
            if val is row:
                del self._message_id_row_map[key]

        for key, val in dict(self._stanza_id_row_map).items():
            if val is row:
                del self._stanza_id_row_map[key]

    def acknowledge_message(self, event: events.MessageAcknowledged) -> None:
        row = self.get_row_by_pk(event.pk)
        if row is None:
            return

        if event.stanza_id is not None:
            self._stanza_id_row_map[event.stanza_id] = row
        row.set_acknowledged(event.stanza_id)
        self._check_for_merge(row)

    def scroll_to_message_and_highlight(self, pk: int) -> None:
        highlight_row = None
        for row in cast(list[BaseRow], self._list_box.get_children()):
            if row.pk == pk:
                highlight_row = row
                break

        if highlight_row is None:
            return

        # Scroll ListBox to row and highlight it
        coordinates = highlight_row.translate_coordinates(self._list_box, 0, 0)
        if coordinates is None:
            return

        _x_coord, y_coord = coordinates
        _minimum_height, natural_height = highlight_row.get_preferred_height()
        adjustment = self._list_box.get_adjustment()
        adjustment.set_value(
            y_coord - (adjustment.get_page_size() - natural_height) / 2)

        highlight_row.get_style_context().remove_class(
            'conversation-row-highlight')
        highlight_row.get_style_context().add_class(
            'conversation-row-highlight')

        GLib.timeout_add(1500, self._remove_highligh_class, highlight_row)

    def _remove_highligh_class(self, highlight_row: BaseRow) -> None:
        highlight_row.get_style_context().remove_class(
            'conversation-row-highlight')

    def scroll_to_end(self) -> None:
        adj = self.get_vadjustment()
        adj.set_value(adj.get_upper() - adj.get_page_size())

    def _get_row_by_message_id(self, message_id: str) -> MessageRow | None:
        return self._message_id_row_map.get(message_id)

    def _get_row_by_stanza_id(self, stanza_id: str) -> MessageRow | None:
        return self._stanza_id_row_map.get(stanza_id)

    def _get_message_row_by_direction(
        self,
        pk: int,
        direction: Direction | None = None
    ) -> MessageRow | None:

        row = self.get_row_by_pk(pk)
        if row is None:
            return None

        if direction is None:
            return row

        index = row.get_index()
        while True:
            if direction == Direction.PREV:
                index -= 1
            else:
                index += 1

            row = self._list_box.get_row_at_index(index)
            if row is None:
                return None

            if isinstance(row, MessageRow):
                return row

    def get_prev_message_row(
        self,
        pk: int | None
    ) -> MessageRow | None:
        if pk is None:
            return self.get_last_message_row()
        return self._get_message_row_by_direction(
            pk, direction=Direction.PREV)

    def get_next_message_row(
        self,
        pk: int | None
    ) -> MessageRow | None:
        if pk is None:
            return None
        return self._get_message_row_by_direction(
            pk, direction=Direction.NEXT)

    def get_row_by_pk(self, pk: int) -> MessageRow | None:
        for row in cast(list[BaseRow], self._list_box.get_children()):
            if not isinstance(row, MessageRow):
                continue
            if pk in {row.pk, row.orig_pk}:
                return row

        return None

    def iter_rows(self) -> Generator[BaseRow, None, None]:
        yield from cast(list[BaseRow], self._list_box.get_children())

    def _remove_rows_by_type(self, row_type: str) -> None:
        for row in self.iter_rows():
            if row.type == row_type:
                row.destroy()

    def update_call_rows(self) -> None:
        for row in cast(list[BaseRow], self._list_box.get_children()):
            if isinstance(row, CallRow):
                row.update()

    def set_read_marker(self, id_: str) -> None:
        row = self._get_row_by_message_id(id_)
        if row is None:
            return

        assert self._read_marker_row is not None
        timestamp = row.timestamp + timedelta(microseconds=1)
        if self._read_marker_row.timestamp > timestamp:
            return

        self._read_marker_row.set_timestamp(timestamp)

    def correct_message(self, event: events.MessageCorrected) -> None:
        message_row = self._get_row_by_message_id(event.correction_id)
        if message_row is None:
            return

        # Store the message row also with the correction message id
        # because e.g. message receipts reference this id.
        if event.message.id is not None:
            self._message_id_row_map[event.message.id] = message_row

        message_row.refresh()

        assert self._read_marker_row is not None
        timestamp = message_row.timestamp + timedelta(microseconds=1)
        if self._read_marker_row.timestamp == timestamp:
            # This exact message has been marked as read
            # -> set read marker to before this message
            self._read_marker_row.set_timestamp(
                message_row.timestamp - timedelta(microseconds=1), force=True)

    def show_message_moderation(self, stanza_id: str, text: str) -> None:
        message_row = self._get_row_by_stanza_id(stanza_id)
        if message_row is not None:
            message_row.set_moderated(text)

    def update_message_reactions(self, reaction_id: str) -> None:
        if isinstance(self._contact, GroupchatContact):
            message_row = self._get_row_by_stanza_id(reaction_id)
        else:
            message_row = self._get_row_by_message_id(reaction_id)

        if message_row is not None:
            message_row.update_reactions()

    def set_receipt(self, id_: str) -> None:
        message_row = self._get_row_by_message_id(id_)
        if message_row is None:
            return

        if message_row.last_message_id == id_:
            message_row.set_receipt(True)
            self._check_for_merge(message_row)

    def show_error(self, id_: str, error: StanzaError) -> None:
        message_row = self._get_row_by_message_id(id_)
        if message_row is not None:
            message_row.show_error(to_user_string(error))
            message_row.set_merged(False)

    def _on_contact_setting_changed(self,
                                    value: Any,
                                    setting: str,
                                    _account: str | None,
                                    _jid: JID | None) -> None:

        if setting == 'print_join_left':
            if value:
                return
            self._remove_rows_by_type('muc-user-joined')
            self._remove_rows_by_type('muc-user-left')

        if setting == 'print_status':
            if value:
                return
            self._remove_rows_by_type('muc-user-status')
