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

from datetime import timedelta

from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.helpers import to_user_string
from gajim.common.helpers import get_start_of_day

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
    }

    def __init__(self, account, contact, history_mode=False):
        Gtk.ListBox.__init__(self)
        self.set_selection_mode(Gtk.SelectionMode.NONE)
        self.set_sort_func(self._sort_func)
        self._account = account
        self._client = app.get_client(account)
        self._contact = contact
        self._history_mode = history_mode

        self.encryption_enabled = False
        self.autoscroll = True
        self.clearing = False

        # Keeps track of the number of rows shown in ConversationView
        self._row_count = 0
        self._max_row_count = 100

        # Keeps track of date rows we have added to the list
        self._active_date_rows = set()

        # message_id -> row mapping
        self._message_id_row_map = {}

        self._read_marker_row = ReadMarkerRow(self._account, self._contact)
        self.add(self._read_marker_row)

        self._scroll_hint_row = ScrollHintRow(self._account,
                                              history_mode=self._history_mode)
        self.add(self._scroll_hint_row)

    def clear(self):
        self.clearing = True
        for row in self.get_children()[1:]:
            self.remove(row)

        GLib.idle_add(self._reset_conversation_view)

    def get_first_message_row(self):
        for row in self.get_children():
            if isinstance(row, MessageRow):
                return row
        return None

    def set_history_complete(self, complete):
        self._scroll_hint_row.set_history_complete(complete)

    def _reset_conversation_view(self):
        self._row_count = 0
        self.clearing = False

    def _sort_func(self, row1, row2):
        if row1.timestamp == row2.timestamp:
            return 0
        return -1 if row1.timestamp < row2.timestamp else 1

    def add_message(self,
                    text,
                    kind,
                    name,
                    timestamp,
                    other_text_tags=None,
                    log_line_id=None,
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

        if not timestamp:
            timestamp = time.time()

        if other_text_tags is None:
            other_text_tags = []

        if (kind in ('status', 'info') or
                (subject and self._contact.is_groupchat)):
            message = InfoMessageRow(
                self._account,
                timestamp,
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
                timestamp,
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
                history_mode=self._history_mode,
                log_line_id=log_line_id)

        if message.type == 'chat':
            self._message_id_row_map[message.message_id] = message

        self._insert_message(message)

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

    def _insert_message(self, message):
        self.add(message)
        self._add_date_row(message.timestamp)
        self._check_for_merge(message)

    def _add_date_row(self, timestamp):
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

    def _check_for_merge(self, message):
        if message.type != 'chat':
            return

        ancestor = self._find_ancestor(message)
        if ancestor is None:
            self._update_descendants(message)
        else:
            if message.is_mergeable(ancestor):
                message.set_merged(True)

    def _find_ancestor(self, message):
        index = message.get_index()
        while index != 0:
            index -= 1
            row = self.get_row_at_index(index)
            if row is None:
                return None

            if row.type != 'chat':
                return None

            if not message.is_same_sender(row):
                return None

            if not row.is_merged:
                return row
        return None

    def _update_descendants(self, message):
        index = message.get_index()
        while True:
            index += 1
            row = self.get_row_at_index(index)
            if row is None:
                return

            if row.type != 'chat':
                return

            if message.is_mergeable(row):
                row.set_merged(True)
                continue

            if message.is_same_sender(row):
                row.set_merged(False)
                self._update_descendants(row)
            return

    def reduce_message_count(self):
        successful = False
        while self._row_count > self._max_row_count:
            # We want to keep relevant DateRows when removing rows
            row1 = self.get_row_at_index(1)
            row2 = self.get_row_at_index(2)

            if row1.type == row2.type == 'date':
                # First two rows are date rows,
                # it’s safe to remove the fist row
                self.remove(row1)
                successful = True
                self._row_count -= 1
                continue

            if row1.type == 'date' and row2.type != 'date':
                # First one is a date row, keep it and
                # remove the second row instead
                self.remove(row2)
                successful = True
                self._row_count -= 1
                continue

            if row1.type != 'date':
                # Not a date row, safe to remove
                self.remove(row1)
                successful = True
                self._row_count -= 1

        return successful

    def _get_row_by_message_id(self, id_):
        return self._message_id_row_map.get(id_)

    def get_row_by_log_line_id(self, log_line_id):
        for row in self.get_children():
            if row.log_line_id == log_line_id:
                return row
        return None

    def iter_rows(self):
        for row in self.get_children():
            yield row

    def set_read_marker(self, id_):
        if id_ is None:
            self._read_marker_row.hide()
            return

        row = self._get_row_by_message_id(id_)
        if row is None:
            return

        row.set_displayed()

        timestamp = row.timestamp + timedelta(microseconds=1)
        self._read_marker_row.set_timestamp(timestamp)

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
        message_row = self._get_row_by_message_id(correct_id)
        if message_row is not None:
            message_row.set_correction(
                message_id, text, other_text_tags, kind, name,
                additional_data=additional_data)
            message_row.set_merged(False)

    def show_receipt(self, id_):
        message_row = self._get_row_by_message_id(id_)
        if message_row is not None:
            message_row.set_receipt()

    def show_error(self, id_, error):
        message_row = self._get_row_by_message_id(id_)
        if message_row is not None:
            message_row.set_error(to_user_string(error))
            message_row.set_merged(False)

    def on_quote(self, text):
        self.emit('quote', text)
