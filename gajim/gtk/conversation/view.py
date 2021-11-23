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

from typing import Dict
from typing import Set
from typing import Optional
from typing import Generator

import logging
import time

from datetime import datetime
from datetime import timedelta

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from nbxmpp.errors import StanzaError
from nbxmpp.modules.security_labels import Displaymarking

from gajim.common import app
from gajim.common.client import Client
from gajim.common.helpers import AdditionalDataDict
from gajim.common.helpers import to_user_string
from gajim.common.helpers import get_start_of_day
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.httpupload import HTTPFileTransfer

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
from .rows.muc_user_status import MUCUserStatus

from ..types import ConversationRowType
from ..util import scroll_to_end

log = logging.getLogger('gajim.gui.conversation_view')


class ConversationView(Gtk.ListBox):

    __gsignals__ = {
        'quote': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str, )
        ),
        'mention': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str, )
        ),
        'accept-call': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (object, )
        ),
        'decline-call': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (object, )
        ),
    }

    def __init__(self, account, contact):
        Gtk.ListBox.__init__(self)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_sort_func(self._sort_func)
        self.set_filter_func(self._filter_func)
        self._account = account
        self._client: Optional[Client] = None
        if account is not None:
            self._client = app.get_client(account)
        self._contact = contact

        self.encryption_enabled: bool = False
        self.autoscroll: bool = True
        self.locked: bool = False

        # Keeps track of the number of rows shown in ConversationView
        self._row_count: int = 0
        self._max_row_count: int = 100

        # Keeps track of date rows we have added to the list
        self._active_date_rows: Set[datetime] = set()

        # message_id -> row mapping
        self._message_id_row_map: Dict[str, MessageRow] = {}

        app.settings.connect_signal('print_join_left',
                                    self._on_contact_setting_changed,
                                    account=self._account,
                                    jid=self._contact.jid)

        app.settings.connect_signal('print_status',
                                    self._on_contact_setting_changed,
                                    account=self._account,
                                    jid=self._contact.jid)

        if self._contact is not None:
            self._read_marker_row = ReadMarkerRow(self._account, self._contact)
            self.add(self._read_marker_row)

        self._scroll_hint_row = ScrollHintRow(self._account)
        self.add(self._scroll_hint_row)

    def lock(self) -> None:
        self.locked = True

    def unlock(self) -> None:
        self.locked = False

    def clear(self) -> None:
        for row in self.get_children()[2:]:
            if row.type == 'read_marker':
                continue
            self.remove(row)
        self._reset_conversation_view()

    def _reset_conversation_view(self) -> None:
        self._row_count = 0
        self._active_date_rows = set()
        self._message_id_row_map = {}

    def get_first_message_row(self) -> Optional[MessageRow]:
        for row in self.get_children():
            if isinstance(row, MessageRow):
                return row
        return None

    def get_last_message_row(self) -> Optional[MessageRow]:
        children = self.get_children()
        children.reverse()
        for row in children:
            if isinstance(row, MessageRow):
                return row
        return None

    def set_history_complete(self, complete: bool) -> None:
        self._scroll_hint_row.set_history_complete(complete)

    @staticmethod
    def _sort_func(row1, row2):
        if row1.timestamp == row2.timestamp:
            return 0
        return -1 if row1.timestamp < row2.timestamp else 1

    def _filter_func(self, row):
        if row.type in ('muc-user-joined', 'muc-user-left'):
            return self._contact.settings.get('print_join_left')
        if row.type == 'muc-user-status':
            return self._contact.settings.get('print_status')

        return True

    def add_muc_subject(self, text: str, nick: str, date: str) -> None:
        subject = MUCSubject(self._account, text, nick, date)
        self._insert_message(subject)

    def add_muc_user_left(self, nick: str, reason: str,
                          error: bool = False) -> None:
        join_left = MUCJoinLeft('muc-user-left',
                                self._account,
                                nick,
                                reason=reason,
                                error=error)
        self._insert_message(join_left)

    def add_muc_user_joined(self, nick: str) -> None:
        join_left = MUCJoinLeft('muc-user-joined',
                                self._account,
                                nick)
        self._insert_message(join_left)

    def add_muc_user_status(self, user_contact: GroupchatParticipant,
                            is_self: bool) -> None:
        user_status = MUCUserStatus(self._account, user_contact, is_self)
        self._insert_message(user_status)

    def add_info_message(self, text: str) -> None:
        message = InfoMessage(self._account, text)
        self._insert_message(message)

    def add_file_transfer(self, transfer: HTTPFileTransfer) -> None:
        transfer_row = FileTransferRow(self._account, transfer)
        self._insert_message(transfer_row)

    def add_jingle_file_transfer(self, event=None, db_message=None):
        jingle_transfer_row = FileTransferJingleRow(
            self._account, self._contact, event=event, db_message=db_message)
        self._insert_message(jingle_transfer_row)

    def add_call_message(self, event=None, db_message=None):
        call_row = CallRow(
            self._account, self._contact, event=event, db_message=db_message)
        self._insert_message(call_row)

    def add_command_output(self, text: str, is_error: bool) -> None:
        command_output_row = CommandOutputRow(self._account, text, is_error)
        self._insert_message(command_output_row)

    def add_message(self,
                    text: str,
                    kind: str,
                    name: str,
                    timestamp: float,
                    log_line_id: Optional[str] = None,
                    message_id: Optional[str] = None,
                    stanza_id: Optional[str] = None,
                    display_marking: Optional[Displaymarking] = None,
                    additional_data: Optional[AdditionalDataDict] = None,
                    marker: Optional[str] = None,
                    error: Optional[StanzaError] = None) -> None:

        if not timestamp:
            timestamp = time.time()

        message = MessageRow(
            self._account,
            self._contact,
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
            encryption_enabled=self.encryption_enabled,
            log_line_id=log_line_id)

        if message.type == 'chat':
            if message_id is not None:
                self._message_id_row_map[message_id] = message

            if kind == 'incoming':
                self._read_marker_row.set_last_incoming_timestamp(
                    message.timestamp)
            if (marker is not None and marker == 'displayed'
                    and message_id is not None):
                self.set_read_marker(message_id)

        self._insert_message(message)

    def _insert_message(self, message: MessageRow) -> None:
        self.add(message)
        self._add_date_row(message.timestamp)
        self._check_for_merge(message)

        if message.kind == 'incoming':
            if message.timestamp > self._read_marker_row.timestamp:
                self._read_marker_row.hide()

        GLib.idle_add(message.queue_resize)

    def _add_date_row(self, timestamp: datetime) -> None:
        start_of_day = get_start_of_day(timestamp)
        if start_of_day in self._active_date_rows:
            return

        date_row = DateRow(self._account, start_of_day)
        self._active_date_rows.add(start_of_day)
        self.add(date_row)

        row = self.get_row_at_index(date_row.get_index() + 1)
        if row is None:
            return

        if row.type != 'chat':
            return

        row.set_merged(False)

    def _check_for_merge(self, message: ConversationRowType) -> None:
        if message.type != 'chat':
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
            row = self.get_row_at_index(index)
            if row is None:
                return None

            if row.type == 'read_marker':
                continue

            if row.type != 'chat':
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
            row = self.get_row_at_index(index)
            if row is None:
                return

            if row.type == 'read_marker':
                continue

            if row.type != 'chat':
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
        row_count = len(self.get_children())
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
        row1 = self.get_row_at_index(2)
        row2 = self.get_row_at_index(3)

        if row1.type == row2.type == 'date':
            # First two rows are date rows,
            # it’s safe to remove the fist row
            self.remove(row1)
            success = True

        if row1.type == 'date' and row2.type != 'date':
            # First one is a date row, keep it and
            # remove the second row instead
            self.remove(row2)
            success = True

        if row1.type != 'date':
            # Not a date row, safe to remove
            self.remove(row1)
            success = True

        return success

    def _reduce_messages_after(self) -> None:
        row = self.get_row_at_index(len(self.get_children()) - 1)
        self.remove(row)

    def scroll_to_message_and_highlight(self, log_line_id: str) -> None:
        highlight_row = None
        for row in self.get_children():
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

    def get_row_by_log_line_id(self, log_line_id: str) -> Optional[MessageRow]:
        for row in self.get_children():
            if row.log_line_id == log_line_id:
                return row
        return None

    def get_row_by_stanza_id(self, stanza_id: str) -> Optional[MessageRow]:
        for row in self.get_children():
            if row.type != 'chat':
                continue
            if row.stanza_id == stanza_id:
                return row
        return None

    def iter_rows(self) -> Generator[ConversationRowType, None, None]:
        for row in self.get_children():
            yield row

    def update_call_rows(self) -> None:
        for row in self.get_children():
            if row.type == 'call':
                row.update()

    def set_read_marker(self, id_: str) -> None:
        if id_ is None:
            return

        row = self._get_row_by_message_id(id_)
        if row is None:
            return

        row.set_displayed()

        timestamp = row.timestamp + timedelta(microseconds=1)
        if self._read_marker_row.timestamp > timestamp:
            return

        self._read_marker_row.set_timestamp(timestamp)

    def update_avatars(self) -> None:
        for row in self.get_children():
            if row.type == 'chat':
                row.update_avatar()

    def update_text_tags(self) -> None:
        for row in self.get_children():
            row.update_text_tags()

    def scroll_to_end(self, force: bool = False) -> None:
        if self.autoscroll or force:
            GLib.idle_add(scroll_to_end, self.get_parent().get_parent())

    def correct_message(self, correct_id: str, text: str) -> None:
        message_row = self._get_row_by_message_id(correct_id)
        if message_row is not None:
            message_row.set_correction(text)
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

    def on_quote(self, text: str) -> None:
        self.emit('quote', text)

    def on_mention(self, name: str) -> None:
        self.emit('mention', name)

    def accept_call(self, event):
        self.emit('accept-call', event)

    def decline_call(self, event):
        self.emit('decline-call', event)

    def _on_contact_setting_changed(self, *args):
        self.invalidate_filter()
