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

from typing import Any
from typing import Literal
from typing import Optional
from typing import Union
from typing import Generator
from typing import cast

import logging
import time

from datetime import datetime
from datetime import timedelta

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Gio

from nbxmpp.errors import StanzaError
from nbxmpp.modules.security_labels import Displaymarking
from nbxmpp.structs import CommonError
from nbxmpp.structs import MucSubject
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import types
from gajim.common import events
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import to_user_string
from gajim.common.helpers import get_start_of_day
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.httpupload import HTTPFileTransfer
from gajim.common.storage.archive import ConversationRow
from gajim.common.modules.contacts import BareContact
from gajim.common.types import ChatContactT

from .rows.base import BaseRow
from .rows.read_marker import ReadMarkerRow
from .rows.scroll_hint import ScrollHintRow
from .rows.message import MessageRow
from .rows.info import InfoMessage
from .rows.call import CallRow
from .rows.command_output import CommandOutputRow
from .rows.date import DateRow
from .rows.file_transfer import FileTransferRow
from .rows.file_transfer_jingle import FileTransferJingleRow
from .rows.muc_subject import MUCSubject
from .rows.muc_join_left import MUCJoinLeft
from .rows.user_status import UserStatus

log = logging.getLogger('gajim.gui.conversation_view')


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

    def __init__(self) -> None:
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

        self._list_box = Gtk.ListBox()
        self._list_box.set_selection_mode(Gtk.SelectionMode.NONE)
        self._list_box.set_sort_func(self._sort_func)

        self._contact: Optional[ChatContactT] = None
        self._client = None

        # Keeps track of the number of rows shown in ConversationView
        self._row_count: int = 0
        self._max_row_count: int = 100

        # Keeps track of date rows we have added to the list
        self._active_date_rows: set[datetime] = set()

        # message_id -> row mapping
        self._message_id_row_map: dict[str, MessageRow] = {}

        self._read_marker_row = None
        self._scroll_hint_row = None

        self._current_upper: float = 0
        self._autoscroll: bool = True
        self._request_history_at_upper: Optional[float] = None
        self._upper_complete: bool = False
        self._lower_complete: bool = True
        self._requesting: Optional[str] = None
        self._block_signals = False

        self._signal_handlers_enabled = False
        self._signal_handler_ids = (0, 0)

        self.add(self._list_box)
        self.set_focus_vadjustment(Gtk.Adjustment())

        app.window.get_action('scroll-view-up').connect(
            'activate', self._on_scroll_view)
        app.window.get_action('scroll-view-down').connect(
            'activate', self._on_scroll_view)

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
        self._emit('request-history', True)

    def get_autoscroll(self) -> bool:
        return self._autoscroll

    def block_signals(self, value: bool) -> None:
        self._block_signals = value

    def _emit(self, signal_name: str, *args: Any) -> None:
        if not self._block_signals:
            log.debug('emit %s, %s', signal_name, args)
            self.emit(signal_name, *args)

    def _reset(self) -> None:
        self._current_upper = 0
        self._request_history_at_upper = None
        self._upper_complete = False
        self._lower_complete = True
        self._requesting = None
        self.set_history_complete(True, False)

        for row in self._list_box.get_children():
            row.destroy()

        self._row_count = 0
        self._active_date_rows = set()
        self._message_id_row_map = {}
        self._read_marker_row = None
        self._scroll_hint_row = None

        if self._contact is not None:
            # These need to be present if ConversationView is reset
            # without switch_contact being invoked
            self._read_marker_row = ReadMarkerRow(self._contact)
            self._list_box.add(self._read_marker_row)

            self._scroll_hint_row = ScrollHintRow(self._contact.account)
            self._list_box.add(self._scroll_hint_row)

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
        return cast(BaseRow, self._list_box.get_row_at_index(index))

    def get_first_message_row(self) -> Optional[MessageRow]:
        for row in self._list_box.get_children():
            if isinstance(row, MessageRow):
                return row
        return None

    def get_last_message_row(self) -> Optional[MessageRow]:
        children = self._list_box.get_children()
        children.reverse()
        for row in children:
            if isinstance(row, MessageRow):
                return row
        return None

    @staticmethod
    def _sort_func(row1: BaseRow, row2: BaseRow) -> int:
        if row1.timestamp == row2.timestamp:
            return 0
        return -1 if row1.timestamp < row2.timestamp else 1

    def add_muc_subject(self,
                        subject: MucSubject,
                        timestamp: Optional[float] = None
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
                         timestamp: Optional[float] = None
                         ) -> None:

        message = InfoMessage(self.contact.account, text, timestamp)
        self._insert_message(message)

    def add_file_transfer(self, transfer: HTTPFileTransfer) -> None:
        transfer_row = FileTransferRow(self.contact.account, transfer)
        self._insert_message(transfer_row)

    def add_jingle_file_transfer(self,
                                 event: Union[
                                     events.FileRequestReceivedEvent,
                                     events.FileRequestSent,
                                     None] = None,
                                 db_message: Optional[ConversationRow] = None
                                 ) -> None:

        assert isinstance(self._contact, BareContact)
        jingle_transfer_row = FileTransferJingleRow(
            self._contact.account,
            self._contact,
            event=event,
            db_message=db_message)
        self._insert_message(jingle_transfer_row)

    def add_call_message(self,
                         event: Optional[events.JingleRequestReceived] = None,
                         db_message: Optional[ConversationRow] = None
                         ) -> None:
        assert isinstance(self._contact, BareContact)
        call_row = CallRow(
            self._contact.account,
            self._contact,
            event=event,
            db_message=db_message)
        self._insert_message(call_row)

    def add_command_output(self, text: str, is_error: bool) -> None:
        command_output_row = CommandOutputRow(
            self.contact.account, text, is_error)
        self._insert_message(command_output_row)

    def add_message(self,
                    text: str,
                    kind: str,
                    name: str,
                    timestamp: float,
                    log_line_id: Optional[int] = None,
                    message_id: Optional[str] = None,
                    stanza_id: Optional[str] = None,
                    display_marking: Optional[Displaymarking] = None,
                    additional_data: Optional[AdditionalDataDict] = None,
                    marker: Optional[str] = None,
                    error: Union[CommonError, StanzaError, None] = None
                    ) -> None:

        if not timestamp:
            timestamp = time.time()

        message_row = MessageRow(
            self.contact.account,
            self.contact,
            message_id,
            stanza_id,
            timestamp,
            kind,
            name,
            text,
            additional_data=additional_data,
            display_marking=display_marking,
            marker=marker,
            error=error,
            log_line_id=log_line_id)

        if message_id is not None:
            self._message_id_row_map[message_id] = message_row

        if kind == 'incoming':
            assert self._read_marker_row is not None
            self._read_marker_row.set_last_incoming_timestamp(
                message_row.timestamp)
        if (marker is not None and marker == 'displayed' and
                message_id is not None):
            self.set_read_marker(message_id)

        self._insert_message(message_row)

    def _insert_message(self, message: BaseRow) -> None:
        self._list_box.add(message)
        self._add_date_row(message.timestamp)
        self._check_for_merge(message)
        assert self._read_marker_row is not None

        if message.kind == 'incoming':
            if message.timestamp > self._read_marker_row.timestamp:
                self._read_marker_row.hide()

    def _add_date_row(self, timestamp: datetime) -> None:
        start_of_day = get_start_of_day(timestamp)
        if start_of_day in self._active_date_rows:
            return

        date_row = DateRow(self.contact.account, start_of_day)
        self._active_date_rows.add(start_of_day)
        self._list_box.add(date_row)

        row = self._get_row_at_index(date_row.get_index() + 1)
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
            if message.is_mergeable(ancestor):
                message.set_merged(True)

    def _find_ancestor(self, message: MessageRow) -> Optional[MessageRow]:
        index = message.get_index()
        while index != 0:
            index -= 1
            row = self._get_row_at_index(index)
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
            row = self._get_row_at_index(index)
            if row is None:
                return

            if isinstance(row, ReadMarkerRow):
                continue

            if not isinstance(row, MessageRow):
                return

            if message.is_mergeable(row):
                row.set_merged(True)
                continue

            if message.is_same_sender(row):
                row.set_merged(False)
                self._update_descendants(row)
            return

    def reduce_message_count(self, before: bool) -> bool:
        success = False
        row_count = len(self._list_box.get_children())
        while row_count > self._max_row_count:
            if before:
                if self._reduce_messages_before():
                    row_count -= 1
                    success = True
            else:
                self._reduce_messages_after()
                row_count -= 1
                success = True

        return success

    def _reduce_messages_before(self) -> bool:
        success = False

        # We want to keep relevant DateRows when removing rows
        row1 = self._get_row_at_index(2)
        row2 = self._get_row_at_index(3)

        if row1.type == 'date' and row2.type == 'date':
            # First two rows are date rows,
            # it’s safe to remove the fist row
            row1.destroy()
            success = True

        if row1.type == 'date' and row2.type != 'date':
            # First one is a date row, keep it and
            # remove the second row instead
            row2.destroy()
            success = True

        if row1.type != 'date':
            # Not a date row, safe to remove
            row1.destroy()
            success = True

        return success

    def _reduce_messages_after(self) -> None:
        row = self._get_row_at_index(len(self._list_box.get_children()) - 1)
        row.destroy()

    def scroll_to_message_and_highlight(self, log_line_id: int) -> None:
        highlight_row = None
        for row in cast(list[BaseRow], self._list_box.get_children()):
            row.get_style_context().remove_class(
                'conversation-search-highlight')
            if row.log_line_id == log_line_id:
                highlight_row = row

        if highlight_row is not None:
            highlight_row.get_style_context().add_class(
                'conversation-search-highlight')
            # This scrolls the ListBox to the highlighted row
            highlight_row.grab_focus()

    def _get_row_by_message_id(self, id_: str) -> Optional[MessageRow]:
        return self._message_id_row_map.get(id_)

    def get_row_by_log_line_id(self, log_line_id: int) -> Optional[MessageRow]:
        for row in cast(list[BaseRow], self._list_box.get_children()):
            if not isinstance(row, MessageRow):
                continue
            if row.log_line_id == log_line_id:
                return row
        return None

    def get_row_by_stanza_id(self, stanza_id: str) -> Optional[MessageRow]:
        for row in cast(list[BaseRow], self._list_box.get_children()):
            if not isinstance(row, MessageRow):
                continue
            if row.stanza_id == stanza_id:
                return row
        return None

    def iter_rows(self) -> Generator[BaseRow, None, None]:
        for row in cast(list[BaseRow], self._list_box.get_children()):
            yield row

    def remove_rows_by_type(self, row_type: str) -> None:
        for row in self.iter_rows():
            if row.type == row_type:
                row.destroy()

    def update_call_rows(self) -> None:
        for row in cast(list[BaseRow], self._list_box.get_children()):
            if isinstance(row, CallRow):
                row.update()

    def set_read_marker(self, id_: str) -> None:
        if id_ is None:
            return

        row = self._get_row_by_message_id(id_)
        if row is None:
            return

        row.set_displayed()
        assert self._read_marker_row is not None
        timestamp = row.timestamp + timedelta(microseconds=1)
        if self._read_marker_row.timestamp > timestamp:
            return

        self._read_marker_row.set_timestamp(timestamp)

    def update_avatars(self) -> None:
        for row in cast(list[BaseRow], self._list_box.get_children()):
            if isinstance(row, MessageRow):
                row.update_avatar()

    def correct_message(self,
                        correct_id: str,
                        text: str,
                        nickname: Optional[str]
                        ) -> None:

        message_row = self._get_row_by_message_id(correct_id)
        if message_row is not None:
            message_row.set_correction(text, nickname)
            message_row.set_merged(False)

    def show_message_retraction(self, stanza_id: str, text: str) -> None:
        message_row = self.get_row_by_stanza_id(stanza_id)
        if message_row is not None:
            message_row.set_retracted(text)

    def show_receipt(self, id_: str) -> None:
        message_row = self._get_row_by_message_id(id_)
        if message_row is not None:
            message_row.set_receipt()

    def show_error(self, id_: str, error: StanzaError) -> None:
        message_row = self._get_row_by_message_id(id_)
        if message_row is not None:
            message_row.set_error(to_user_string(error))
            message_row.set_merged(False)

    def _on_contact_setting_changed(self,
                                    value: Any,
                                    setting: str,
                                    _account: Optional[str],
                                    _jid: Optional[JID]) -> None:

        if setting == 'print_join_left':
            if value:
                return
            self.remove_rows_by_type('muc-user-joined')
            self.remove_rows_by_type('muc-user-left')

        if setting == 'print_status':
            if value:
                return
            self.remove_rows_by_type('muc-user-status')

    def remove(self, widget: Gtk.Widget) -> None:
        self._list_box.remove(widget)
        widget.destroy()
