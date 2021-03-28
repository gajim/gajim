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

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import TRUST_SYMBOL_DATA
from gajim.common.helpers import from_one_line
from gajim.common.helpers import reduce_chars_newlines
from gajim.common.helpers import to_user_string
from gajim.common.i18n import _
from gajim.common.i18n import Q_

from .conversation_textview import ConversationTextview
from .util import convert_rgba_to_hex
from .util import format_fingerprint
from .util import scroll_to_end
from .util import text_to_color
from .util import get_cursor

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
            message = TextMessageRow(
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


class ConversationRow(Gtk.ListBoxRow):
    def __init__(self, account, widget='label', history_mode=False):
        Gtk.ListBoxRow.__init__(self)
        self.type = ''
        self.timestamp = None
        self.kind = None
        self.name = None
        self.message_id = None
        self.text = ''

        self.get_style_context().add_class('conversation-row')

        self.grid = Gtk.Grid(row_spacing=3, column_spacing=12)
        self.add(self.grid)

        if widget == 'textview':
            self.label = None
            self.textview = ConversationTextview(
                account, history_mode=history_mode)
        else:
            self.textview = None
            self.label = Gtk.Label()
            self.label.set_selectable(True)
            self.label.set_line_wrap(True)
            self.label.set_xalign(0)
            self.label.set_line_wrap_mode(
                Pango.WrapMode.WORD_CHAR)

    def update_text_tags(self):
        if self.textview is not None:
            self.textview.update_text_tags()

    @staticmethod
    def create_timestamp_widget(timestamp: datetime) -> Gtk.Label:
        # TODO: maybe change default to '%H:%M'
        time_format = from_one_line(app.settings.get('time_stamp'))
        timestamp_formatted = timestamp.strftime(time_format)
        label = Gtk.Label(label=timestamp_formatted)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.END)
        label.get_style_context().add_class('conversation-meta')
        label.set_tooltip_text(timestamp.strftime('%a, %d %b %Y - %H:%M:%S'))
        return label

    @staticmethod
    def create_name_widget(name: str, kind: str,
                           is_groupchat: bool) -> Gtk.Label:
        label = Gtk.Label()
        label.set_selectable(True)
        label.get_style_context().add_class('conversation-nickname')

        name = GLib.markup_escape_text(name)
        if is_groupchat:
            rgba = Gdk.RGBA(*text_to_color(name))
            nick_color = convert_rgba_to_hex(rgba)
            label.set_markup(
                f'<span foreground="{nick_color}">{name}</span>')
        else:
            if kind in ('incoming', 'incoming_queue'):
                label.get_style_context().add_class(
                    'gajim-incoming-nickname')
            elif kind == 'outgoing':
                label.get_style_context().add_class(
                    'gajim-outgoing-nickname')
            label.set_markup(name)
        return label


class ScrollHintRow(ConversationRow):
    def __init__(self, account):
        ConversationRow.__init__(self, account)
        self.type = 'system'
        self.timestamp = datetime.fromtimestamp(0)
        self.get_style_context().add_class('conversation-system-row')

        self._button = Gtk.Button.new_from_icon_name(
            'go-up-symbolic', Gtk.IconSize.BUTTON)
        self._button.set_tooltip_text(_('Load more messages'))
        self._button.connect('clicked', self._on_load_history)
        self.grid.attach(self._button, 0, 0, 1, 1)

        self.label.set_text(_('Scroll up to load more chat history…'))
        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_hexpand(True)
        self.label.get_style_context().add_class(
            'conversation-meta')
        self.grid.attach(self.label, 0, 1, 1, 1)

    def _on_load_history(self, _button):
        self.get_parent().emit('load-history', 30)


class ReadMarkerRow(ConversationRow):
    def __init__(self, account, contact, timestamp):
        ConversationRow.__init__(self, account)
        self.type = 'read_marker'
        self.timestamp = timestamp

        text = _('%s has read up to this point') % contact.name
        self.label.set_text(text)
        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_hexpand(True)
        self.label.get_style_context().add_class(
            'conversation-read-marker')
        self.grid.attach(self.label, 0, 0, 1, 1)
        self.show_all()


class DateRow(ConversationRow):
    def __init__(self, account, date_string, timestamp):
        ConversationRow.__init__(self, account)
        self.type = 'date'
        self.timestamp = timestamp
        self.get_style_context().add_class('conversation-date-row')

        self.label.set_text(date_string)
        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_hexpand(True)
        self.label.get_style_context().add_class(
            'conversation-meta')
        self.grid.attach(self.label, 0, 0, 1, 1)


class InfoMessageRow(ConversationRow):
    def __init__(self,
                 account,
                 timestamp,
                 text,
                 other_text_tags,
                 kind,
                 subject,
                 graphics,
                 history_mode=False):
        ConversationRow.__init__(self, account, widget='textview',
                                 history_mode=history_mode)
        self.type = 'info'
        self.timestamp = timestamp
        self.kind = kind

        if subject:
            subject_title = _('Subject:')
            text = (f'{subject_title}\n'
                    f'{GLib.markup_escape_text(subject)}\n'
                    f'{GLib.markup_escape_text(text)}')
        else:
            text = GLib.markup_escape_text(text)

        other_text_tags.append('status')

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 2)
        timestamp_widget = self.create_timestamp_widget(timestamp)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 2, 0, 1, 1)

        self.textview.set_justification(Gtk.Justification.CENTER)
        self.textview.print_text(
            text,
            other_text_tags=other_text_tags,
            kind=kind,
            graphics=graphics)

        self.grid.attach(self.textview, 1, 0, 1, 1)


class TextMessageRow(ConversationRow):
    def __init__(self,
                 account,
                 message_id,
                 timestamp,
                 kind,
                 name,
                 text,
                 other_text_tags,
                 avatar,
                 is_groupchat,
                 additional_data=None,
                 display_marking=None,
                 marker=None,
                 error=None,
                 encryption_enabled=False,
                 history_mode=False):

        # other_tags_for_name contained 'marked', 'bold' and
        # 'muc_nickname_color_', which are now derived from
        # other_text_tags ('marked')

        # other_tags_for_time were always empty?

        ConversationRow.__init__(self, account, widget='textview',
                                 history_mode=history_mode)
        self.type = 'chat'
        self.timestamp = timestamp
        self.message_id = message_id
        self.kind = kind
        self.name = name or ''
        self.text = text

        self._corrections = []
        self._has_receipt = marker == 'received'
        self._has_displayed = marker == 'displayed'

        if is_groupchat:
            if other_text_tags and 'marked' in other_text_tags:
                self.get_style_context().add_class(
                    'conversation-mention-highlight')

        self.textview.connect('quote', self._on_quote_selection)
        self.textview.print_text(
            text,
            other_text_tags=other_text_tags,
            kind=kind,
            name=name,
            additional_data=additional_data)

        self._meta_box = Gtk.Box(spacing=6)
        self._meta_box.pack_start(
            self.create_name_widget(name, kind, is_groupchat), False, True, 0)
        timestamp_label = self.create_timestamp_widget(timestamp)
        timestamp_label.set_margin_start(6)
        self._meta_box.pack_end(timestamp_label, False, True, 0)
        # TODO: implement app.settings.get('print_time') 'always', 'sometimes'?

        if kind in ('incoming', 'incoming_queue', 'outgoing'):
            encryption_img = self._get_encryption_image(
                additional_data, encryption_enabled)
            if encryption_img:
                self._meta_box.pack_end(encryption_img, False, True, 0)

        if display_marking:
            label_text = GLib.markup_escape_text(display_marking.name)
            if label_text:
                bgcolor = display_marking.bgcolor
                fgcolor = display_marking.fgcolor
                label_text = (
                    f'<span size="small" bgcolor="{bgcolor}" '
                    f'fgcolor="{fgcolor}"><tt>[{label_text}]</tt></span>')
                display_marking_label = Gtk.Label()
                display_marking_label.set_markup(label_text)
                self._meta_box.add(display_marking_label)

        self._message_icons = MessageIcons()

        if error is not None:
            self.set_error(to_user_string(error))

        if marker is not None:
            if marker in ('received', 'displayed'):
                self.set_receipt()

        self._meta_box.pack_end(self._message_icons, False, True, 0)

        self._avatar_surface = Gtk.Image.new_from_surface(avatar)
        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        avatar_placeholder.set_valign(Gtk.Align.START)
        avatar_placeholder.add(self._avatar_surface)

        bottom_box = Gtk.Box(spacing=6)
        bottom_box.add(self.textview)
        bottom_box.add(MoreMenuButton(self))

        self.grid.attach(avatar_placeholder, 0, 0, 1, 2)
        self.grid.attach(self._meta_box, 1, 0, 1, 1)
        self.grid.attach(bottom_box, 1, 1, 1, 1)

    def _on_copy_message(self, _widget):
        timestamp = self.timestamp.strftime('%x, %X')
        clip = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clip.set_text(
            f'{timestamp} - {self.name}: {self.textview.get_text()}', -1)

    def _on_quote_message(self, _widget):
        self.get_parent().on_quote(self.textview.get_text())

    def _get_encryption_image(self, additional_data, encryption_enabled=None):
        details = self._get_encryption_details(additional_data)
        if details is None:
            # Message was not encrypted
            if not encryption_enabled:
                return None
            icon = 'channel-insecure-symbolic'
            color = 'unencrypted-color'
            tooltip = _('Not encrypted')
        else:
            name, fingerprint, trust = details
            tooltip = _('Encrypted (%s)') % (name)
            if trust is None:
                # The encryption plugin did not pass trust information
                icon = 'channel-secure-symbolic'
                color = 'encrypted-color'
            else:
                icon, trust_tooltip, color = TRUST_SYMBOL_DATA[trust]
                tooltip = '%s\n%s' % (tooltip, trust_tooltip)
            if fingerprint is not None:
                fingerprint = format_fingerprint(fingerprint)
                tooltip = '%s\n<tt>%s</tt>' % (tooltip, fingerprint)

        image = Gtk.Image.new_from_icon_name(icon, Gtk.IconSize.MENU)
        image.set_tooltip_markup(tooltip)
        image.get_style_context().add_class(color)
        image.show()
        return image

    @staticmethod
    def _get_encryption_details(additional_data):
        name = additional_data.get_value('encrypted', 'name')
        if name is None:
            return None

        fingerprint = additional_data.get_value('encrypted', 'fingerprint')
        trust = additional_data.get_value('encrypted', 'trust')
        return name, fingerprint, trust

    def _on_quote_selection(self, _widget, text):
        self.get_parent().on_quote(text)

    @property
    def has_receipt(self):
        return self._has_receipt

    @property
    def has_displayed(self):
        return self._has_displayed

    def set_receipt(self):
        self._has_receipt = True
        self._message_icons.set_receipt_icon_visible(True)

    def set_displayed(self):
        self._has_displayed = True

    def set_correction(self, message_id, text, other_text_tags, kind, name,
                       additional_data=None):
        self._corrections.append(self.textview.get_text())
        self.textview.clear()
        self._has_receipt = False
        self._message_icons.set_receipt_icon_visible(False)
        self._message_icons.set_correction_icon_visible(True)

        self.textview.print_text(
            text,
            other_text_tags=other_text_tags,
            kind=kind,
            name=name,
            additional_data=additional_data)

        corrections = '\n'.join(line for line in self._corrections)
        corrections = reduce_chars_newlines(
            corrections, max_chars=150, max_lines=10)
        self._message_icons.set_correction_tooltip(
            _('Message corrected. Original message:\n%s') % corrections)
        # Update message_id for this row
        self.message_id = message_id

    def set_error(self, tooltip):
        self._message_icons.set_error_icon_visible(True)
        self._message_icons.set_error_tooltip(tooltip)

    def update_avatar(self, avatar):
        self._avatar_surface.set_from_surface(avatar)

    def set_merged(self, merged):
        if merged:
            self._avatar_surface.set_no_show_all(True)
            self._avatar_surface.hide()
            self._meta_box.set_no_show_all(True)
            self._meta_box.hide()
        else:
            self._avatar_surface.set_no_show_all(False)
            self._avatar_surface.show()
            self._meta_box.set_no_show_all(False)
            self._meta_box.show()


class MessageIcons(Gtk.Box):
    def __init__(self):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL)

        self._correction_image = Gtk.Image.new_from_icon_name(
            'document-edit-symbolic', Gtk.IconSize.MENU)
        self._correction_image.set_no_show_all(True)
        self._correction_image.get_style_context().add_class('dim-label')

        self._marker_image = Gtk.Image()
        self._marker_image.set_no_show_all(True)
        self._marker_image.get_style_context().add_class('dim-label')

        self._error_image = Gtk.Image.new_from_icon_name(
            'dialog-warning-symbolic', Gtk.IconSize.MENU)
        self._error_image.get_style_context().add_class('warning-color')
        self._error_image.set_no_show_all(True)

        self.add(self._correction_image)
        self.add(self._marker_image)
        self.add(self._error_image)
        self.show_all()

    def set_receipt_icon_visible(self, visible):
        if not app.settings.get('positive_184_ack'):
            return
        self._marker_image.set_visible(visible)
        self._marker_image.set_from_icon_name(
            'feather-check-symbolic', Gtk.IconSize.MENU)
        self._marker_image.set_tooltip_text(Q_('?Message state:Received'))

    def set_correction_icon_visible(self, visible):
        self._correction_image.set_visible(visible)

    def set_correction_tooltip(self, text):
        self._correction_image.set_tooltip_markup(text)

    def set_error_icon_visible(self, visible):
        self._error_image.set_visible(visible)

    def set_error_tooltip(self, text):
        self._error_image.set_tooltip_markup(text)


class MoreMenuButton(Gtk.MenuButton):
    def __init__(self, row):
        Gtk.MenuButton.__init__(self)

        self.connect_after('realize', self._on_realize)

        self.set_valign(Gtk.Align.START)
        self.set_halign(Gtk.Align.END)
        self.set_relief(Gtk.ReliefStyle.NONE)
        image = Gtk.Image.new_from_icon_name(
            'feather-more-horizontal-symbolic', Gtk.IconSize.BUTTON)
        self.add(image)

        self._create_popover(row)

        self.get_style_context().add_class('conversation-more-button')

    def _create_popover(self, row):
        menu_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        menu_box.get_style_context().add_class('padding-6')

        quote_button = Gtk.ModelButton()
        quote_button.set_halign(Gtk.Align.START)
        quote_button.connect('clicked', row._on_quote_message)
        quote_button.set_label(_('Quote…'))
        quote_button.set_image(Gtk.Image.new_from_icon_name(
            'mail-reply-sender-symbolic', Gtk.IconSize.MENU))
        menu_box.add(quote_button)

        copy_button = Gtk.ModelButton()
        copy_button.set_halign(Gtk.Align.START)
        copy_button.connect('clicked', row._on_copy_message)
        copy_button.set_label(_('Copy'))
        copy_button.set_image(Gtk.Image.new_from_icon_name(
            'edit-copy-symbolic', Gtk.IconSize.MENU))
        menu_box.add(copy_button)

        menu_box.show_all()

        popover = Gtk.PopoverMenu()
        popover.add(menu_box)
        self.set_popover(popover)

    def _on_realize(self, *args):
        self.get_window().set_cursor(get_cursor('pointer'))
