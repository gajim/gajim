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

import logging
import time

from bisect import bisect_left
from bisect import bisect_right
from collections import deque
from datetime import datetime
from datetime import timedelta

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.helpers import to_user_string

from .util import scroll_to_end
from .conversation.rows.read_marker import ReadMarkerRow
from .conversation.rows.scroll_hint import ScrollHintRow
from .conversation.rows.message import MessageRow
from .conversation.rows.info import InfoMessageRow
from .conversation.rows.date import DateRow


log = logging.getLogger('gajim.gui.conversation_view')


class ConversationView(Gtk.ListBox):

    __gsignals__ = {
        'quote': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str, )
        ),
        'load-history': (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (str, )
        )
    }

    def __init__(self, account, contact, history_mode=False):
        Gtk.ListBox.__init__(self)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self._account = account
        self._client = app.get_client(account)
        self._contact = contact
        self._history_mode = history_mode

        self.encryption_enabled = False
        self.autoscroll = True
        self.clearing = False

        # Both first and last DateRow (datetime)
        self._first_date = None
        self._last_date = None

        # Keeps track of the number of rows shown in ConversationView
        self._row_count = 0
        self._max_row_count = 100

        # Keeps inserted message IDs to avoid re-inserting the same message
        self._message_ids_inserted = {}

        # We keep a sorted array of all the timestamps we've inserted, which
        # have a 1-to-1 mapping to the actual child elements of this ListBox
        # (*all* rows are included).
        # Binary-searching this array enables us to insert a message with a
        # discontinuous timestamp (not less than or greater than the first or
        # last message timestamp in the list), and insert it at the correct
        # place in the ListBox.
        self._timestamps_inserted = deque()

        # Stores the timestamp of the first *chat* row inserted
        # (not a system row or date row)
        self.first_message_timestamp = None

        # Last incoming chat message timestamp (used for ReadMarkerRows)
        self._last_incoming_timestamp = datetime.fromtimestamp(0)

        # Insert the very first row, containing the scroll hint and load button
        self.add(ScrollHintRow(self._account))
        self._timestamps_inserted.append(datetime.fromtimestamp(0))

    def clear(self):
        self.clearing = True
        for row in self.get_children()[1:]:
            self.remove(row)

        GLib.idle_add(self._reset_conversation_view)

    def _reset_conversation_view(self):
        self._first_date = None
        self._last_date = None
        self._message_ids_inserted.clear()
        self.first_message_timestamp = None
        self._last_incoming_timestamp = datetime.fromtimestamp(0)
        self._timestamps_inserted.clear()
        self._row_count = 0
        self.clearing = False

    def add_message(self,
                    text,
                    kind,
                    name,
                    timestamp,
                    other_text_tags=None,
                    message_id=None,
                    correct_id=None,
                    display_marking=None,
                    additional_data=None,
                    subject=None,
                    marker=None,
                    error=None,
                    history=False,
                    graphics=True):

        log.debug(
            'Adding message: %s, %s, %s, %s, message_id: %s, correct_id: %s, '
            'other_text_tags: %s, display_marking: %s, additional_data: %s, '
            'subject: %s, marker: %s, error: %s, history: %s, graphics: %s',
            text, kind, name, timestamp, message_id, correct_id,
            other_text_tags, display_marking, additional_data, subject,
            marker, error, history, graphics)

        if message_id:
            if message_id in self._message_ids_inserted:
                log.warning('Rejecting insertion of duplicate message_id %s',
                            str(message_id))
                return
            self._message_ids_inserted[message_id] = True

        if not timestamp:
            timestamp = time.time()
        time_ = datetime.fromtimestamp(timestamp)

        if other_text_tags is None:
            other_text_tags = []

        if kind in ('status', 'info') or subject:
            message = InfoMessageRow(
                self._account,
                time_,
                text,
                other_text_tags,
                kind,
                subject,
                graphics,
                history_mode=self._history_mode)
        else:
            if correct_id:
                self.correct_message(
                    correct_id,
                    message_id,
                    text,
                    other_text_tags,
                    kind,
                    name,
                    additional_data=additional_data)
                return

            avatar = self._get_avatar(kind, name)
            message = MessageRow(
                self._account,
                message_id,
                time_,
                kind,
                name,
                text,
                other_text_tags,
                avatar,
                self._contact.is_groupchat,
                additional_data=additional_data,
                display_marking=display_marking,
                marker=marker,
                error=error,
                encryption_enabled=self.encryption_enabled,
                history_mode=self._history_mode)

        self._insert_message(message, time_, kind, history)

        # Check for maximum message count
        if self.autoscroll and self._row_count > self._max_row_count:
            self._reduce_message_count()

    def _get_avatar(self, kind, name):
        scale = self.get_scale_factor()
        if self._contact.is_groupchat:
            contact = self._contact.get_resource(name)
            return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

        if kind == 'outgoing':
            contact = self._client.get_module('Contacts').get_contact(
                str(self._client.get_own_jid().bare))
        else:
            contact = self._contact

        return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

    def _insert_message(self, message, time_, kind, history):
        current_date = time_.strftime('%a, %d %b %Y')

        if self._is_out_of_order(time_, history):
            insertion_point = bisect_left(self._timestamps_inserted, time_)
            date_check_point = min(len(
                self._timestamps_inserted) - 1, insertion_point - 1)
            date_at_dcp = self._timestamps_inserted[date_check_point].strftime(
                '%a, %d %b %Y')
            if date_at_dcp != current_date:
                associated_timestamp = time_ - timedelta(
                    hours=time_.hour,
                    minutes=time_.minute,
                    seconds=time_.second)
                date_row = DateRow(
                    self._account, current_date, associated_timestamp)
                self.insert(date_row, insertion_point)
                self._timestamps_inserted.insert(
                    insertion_point, associated_timestamp)
                self._row_count += 1
                insertion_point += 1
            if (kind in ('incoming', 'incoming_queue') and
                    time_ > self._last_incoming_timestamp):
                self._last_incoming_timestamp = time_
            self.insert(message, insertion_point)
            self._timestamps_inserted.insert(insertion_point, time_)
            current_timestamp = time_
            self._row_count += 1
        elif history:
            if current_date != self._first_date:
                associated_timestamp = time_ - timedelta(
                    hours=time_.hour,
                    minutes=time_.minute,
                    seconds=time_.second)
                date_row = DateRow(
                    self._account, current_date, associated_timestamp)
                self.insert(date_row, 1)
                self._timestamps_inserted.insert(1, associated_timestamp)
                self._row_count += 1
            self._first_date = current_date
            if kind in ('incoming', 'incoming_queue', 'outgoing'):
                self.first_message_timestamp = time_
            if (kind in ('incoming', 'incoming_queue') and
                    time_ > self._last_incoming_timestamp):
                self._last_incoming_timestamp = time_
            self.insert(message, 2)
            self._timestamps_inserted.insert(2, time_)
            if self._last_date is None:
                self._last_date = current_date
            current_timestamp = time_
            self._row_count += 1
        else:
            if current_date != self._last_date:
                associated_timestamp = time_ - timedelta(
                    hours=time_.hour,
                    minutes=time_.minute,
                    seconds=time_.second)
                date_row = DateRow(
                    self._account, current_date, associated_timestamp)
                self.add(date_row)
                self._timestamps_inserted.append(associated_timestamp)
                self._row_count += 1
            if self._first_date is None:
                self._first_date = current_date
            if (kind in ('incoming', 'incoming_queue', 'outgoing') and not
                    self.first_message_timestamp):
                self.first_message_timestamp = time_
            if (kind in ('incoming', 'incoming_queue') and
                    time_ > self._last_incoming_timestamp):
                self._last_incoming_timestamp = time_
            self._last_date = current_date
            self.add(message)
            self._timestamps_inserted.append(time_)
            current_timestamp = time_
            self._row_count += 1

        if message.type == 'chat':
            self._merge_message(current_timestamp)
            self._update_read_marker(current_timestamp)

        self.show_all()

    def _is_out_of_order(self, time_: datetime, history: bool) -> bool:
        if history:
            if self.first_message_timestamp:
                return time_ > self.first_message_timestamp
            return False
        if len(self._timestamps_inserted) > 1:
            return time_ < self._timestamps_inserted[-1]
        return False

    def _merge_message(self, timestamp):
        # 'Merge' message rows if they both meet certain conditions
        # (see _is_mergeable). A merged message row does not display any
        # avatar or meta info, and makes it look merged with the previous row.
        if self._contact.is_groupchat:
            return

        current_index = self._timestamps_inserted.index(timestamp)
        previous_row = self.get_row_at_index(current_index - 1)
        current_row = self.get_row_at_index(current_index)
        next_row = self.get_row_at_index(current_index + 1)
        if next_row is not None:
            if self._is_mergeable(current_row, next_row):
                next_row.set_merged(True)

        if self._is_mergeable(current_row, previous_row):
            current_row.set_merged(True)
            if next_row is not None:
                if self._is_mergeable(current_row, next_row):
                    next_row.set_merged(True)

    @staticmethod
    def _is_mergeable(row1, row2):
        # TODO: Check for same encryption
        timestamp1 = row1.timestamp.strftime('%H:%M')
        timestamp2 = row2.timestamp.strftime('%H:%M')
        kind1 = row1.kind
        kind2 = row2.kind
        if timestamp1 == timestamp2 and kind1 == kind2:
            return True
        return False

    def _reduce_message_count(self):
        while self._row_count > self._max_row_count:
            # We want to keep relevant DateRows when removing rows
            row1 = self.get_row_at_index(1)
            row2 = self.get_row_at_index(2)

            if row1.type == row2.type == 'date':
                # First two rows are date rows,
                # it’s safe to remove the fist row
                self.remove(row1)
                self._timestamps_inserted.remove(row1.timestamp)
                self._first_date = row2.timestamp.strftime('%a, %d %b %Y')
                self._row_count -= 1
                continue

            if row1.type == 'date' and row2.type != 'date':
                # First one is a date row, keep it and
                # remove the second row instead
                self.remove(row2)
                self._timestamps_inserted.remove(row2.timestamp)
                if row2.message_id:
                    self._message_ids_inserted.pop(row2.message_id)
                chat_row = self._get_first_chat_row()
                if chat_row is not None:
                    self.first_message_timestamp = chat_row.timestamp
                else:
                    self.first_message_timestamp = None
                self._row_count -= 1
                continue

            if row1.type != 'date':
                # Not a date row, safe to remove
                self.remove(row1)
                self._timestamps_inserted.remove(row1.timestamp)
                if row1.message_id:
                    self._message_ids_inserted.pop(row1.message_id)
                if row2.type == 'chat':
                    self.first_message_timestamp = row2.timestamp
                else:
                    chat_row = self._get_first_chat_row()
                    if chat_row is not None:
                        self.first_message_timestamp = chat_row.timestamp
                    else:
                        self.first_message_timestamp = None
                self._row_count -= 1

    def _get_row_by_id(self, id_):
        for row in self.get_children():
            if row.message_id == id_:
                return row
        return None

    def _get_first_chat_row(self):
        for row in self.get_children():
            if row.type == 'chat':
                return row
        return None

    def set_read_marker(self, id_):
        message_row = self._get_row_by_id(id_)
        if message_row is None:
            return

        message_row.set_displayed()
        self._update_read_marker(message_row.timestamp)

    def _update_read_marker(self, current_timestamp):
        marker_shown = False

        for row in self.get_children():
            if row.type == 'read_marker':
                # We already have a ReadMarkerRow, decide if we keep it
                marker_shown = True

                if self._last_incoming_timestamp > row.timestamp:
                    # Last incoming message is newer than read marker
                    self.remove(row)
                    self._timestamps_inserted.remove(row.timestamp)
                    marker_shown = False
                    break

                if self._last_incoming_timestamp > current_timestamp:
                    # Last incoming message is newer than current message
                    break

                if current_timestamp > row.timestamp:
                    # Message is newer than current ReadMarkerRow
                    current_row = self.get_row_at_index(
                        self._timestamps_inserted.index(current_timestamp))
                    if current_row.has_displayed:
                        # Current row has a displayed marker, which means
                        # that the current ReadMarkerRow is out of date
                        self.remove(row)
                        self._timestamps_inserted.remove(row.timestamp)
                        marker_shown = False
                        break
                break

        if self._last_incoming_timestamp >= current_timestamp:
            # Don’t add ReadMarkerRow if last incoming message is newer
            return

        if marker_shown:
            # There is a ReadMarkerRow which has not been removed by previous
            # rules, thus it’s the most current one (nothing more to do)
            return

        current_row = self.get_row_at_index(
            self._timestamps_inserted.index(current_timestamp))
        if current_row.type != 'chat':
            return

        if current_row.has_displayed:
            # Add a new ReadMarkerRow, if there is a marker for the current row
            self._insert_read_marker(current_timestamp)

    def _insert_read_marker(self, timestamp):
        insertion_point = bisect_right(
            self._timestamps_inserted, timestamp)
        read_marker_row = ReadMarkerRow(
            self._account, self._contact, timestamp)
        self.insert(read_marker_row, insertion_point)
        self._timestamps_inserted.insert(insertion_point, timestamp)

    def update_avatars(self):
        for row in self.get_children():
            if row.type == 'chat':
                avatar = self._get_avatar(row.kind, row.name)
                row.update_avatar(avatar)

    def update_text_tags(self):
        for row in self.get_children():
            row.update_text_tags()

    def scroll_to_end(self, force=False):
        if self.autoscroll or force:
            GLib.idle_add(scroll_to_end, self.get_parent().get_parent())

    def correct_message(self, correct_id, message_id, text,
                        other_text_tags, kind, name, additional_data=None):
        message_row = self._get_row_by_id(correct_id)
        if message_row is not None:
            message_row.set_correction(
                message_id, text, other_text_tags, kind, name,
                additional_data=additional_data)
            message_row.set_merged(False)

    def show_receipt(self, id_):
        message_row = self._get_row_by_id(id_)
        if message_row is not None:
            message_row.set_receipt()

    def show_error(self, id_, error):
        message_row = self._get_row_by_id(id_)
        if message_row is not None:
            message_row.set_error(to_user_string(error))
            message_row.set_merged(False)

    def on_quote(self, text):
        self.emit('quote', text)

    # TODO: focus_out_line for group chats
