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

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.const import RowHeaderType
from gajim.common.i18n import _
from gajim.common.helpers import get_groupchat_name
from gajim.common.helpers import get_group_chat_nick
from gajim.common.helpers import get_uf_relative_time
from gajim.common.preview_helpers import filename_from_uri
from gajim.common.preview_helpers import guess_simple_file_type

from gajim.gui_menu_builder import get_chat_list_row_menu

from .util import get_builder
from .util import EventHelper

log = logging.getLogger('gajim.gui.chatlist')


class ChatList(Gtk.ListBox, EventHelper):
    def __init__(self, workspace_id):
        Gtk.ListBox.__init__(self)
        EventHelper.__init__(self)

        self._chats = {}
        self._current_filter = 'all'
        self._current_filter_text = ''
        self._workspace_id = workspace_id

        self.get_style_context().add_class('chatlist')
        self.set_filter_func(self._filter_func)
        self.set_header_func(self._header_func)
        self.set_sort_func(self._sort_func)
        self._set_placeholder()

        self._mouseover = False
        self.connect('enter-notify-event', self._on_mouse_focus_changed)
        self.connect('leave-notify-event', self._on_mouse_focus_changed)

        self.register_events([
            ('account-enabled', ged.GUI2, self._on_account_changed),
            ('account-disabled', ged.GUI2, self._on_account_changed),
            ('bookmarks-received', ged.GUI1, self._on_bookmarks_received),
        ])

        self.connect('destroy', self._on_destroy)

        self._timer_id = GLib.timeout_add_seconds(60, self._update_timer)

        self.show_all()

    @property
    def workspace_id(self):
        return self._workspace_id

    def get_unread_count(self):
        return sum([chats.unread_count for chats in self._chats.values()])

    def get_chat_unread_count(self, account, jid):
        chat = self._chats.get((account, jid))
        if chat is not None:
            return chat.unread_count
        return None

    def mark_as_read(self, account, jid):
        chat = self._chats.get((account, jid))
        if chat is not None:
            chat.reset_unread()
            self.emit_unread_changed()

    def emit_unread_changed(self):
        count = self.get_unread_count()
        self.get_parent().emit('unread-count-changed',
                               self._workspace_id,
                               count)

    def is_visible(self):
        return self.get_parent().get_property('child-widget') == self

    def _on_destroy(self, *args):
        GLib.source_remove(self._timer_id)

    def _update_timer(self):
        self.update_time()
        return True

    def _filter_func(self, row):
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
    def _header_func(row, before):
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

    def _sort_func(self, row1, row2):
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
        if row1.timestamp > row2.timestamp:
            return -1
        if row2.timestamp > row1.timestamp:
            return 1

    def _on_mouse_focus_changed(self, _widget, event):
        if event.type == Gdk.EventType.ENTER_NOTIFY:
            self._mouseover = True

        if event.type == Gdk.EventType.LEAVE_NOTIFY:
            if event.detail != Gdk.NotifyType.INFERIOR:
                # Not hovering a Gtk.ListBoxRow (row is INFERIOR)
                self._mouseover = False

    def _set_placeholder(self):
        button = Gtk.Button.new_with_label(_('Start Chat'))
        button.get_style_context().add_class('suggested-action')
        button.set_halign(Gtk.Align.CENTER)
        button.set_valign(Gtk.Align.CENTER)
        button.connect('clicked', self._on_start_chat_clicked)
        button.show()
        self.set_placeholder(button)

    @staticmethod
    def _on_start_chat_clicked(_widget):
        app.app.activate_action('start-chat', GLib.Variant('s', ''))

    def set_filter(self, name):
        self._current_filter = name
        self.invalidate_filter()

    def set_filter_text(self, text):
        self._current_filter_text = text
        self.invalidate_filter()

    def get_chat_type(self, account, jid):
        row = self._chats.get((account, jid))
        return row.type

    def add_chat(self, account, jid, type_, pinned=False):
        if self._chats.get((account, jid)) is not None:
            # Chat is already in the List
            return

        row = ChatRow(self._workspace_id, account, jid, type_, pinned)
        self._chats[(account, jid)] = row
        self.add(row)

    def select_chat(self, account, jid):
        row = self._chats[(account, jid)]
        self.select_row(row)

    def select_next_chat(self, forwards, unread_first=False):
        # Selects the next chat, but prioritizes chats with unread messages.
        # Direction is forwards (True) or backwards (False)
        row = self.get_selected_chat()
        if row is None:
            row = self.get_row_at_index(0)
            if row is not None:
                self.select_chat(row.account, row.jid)
                return

        unread_found = False
        if unread_first:
            index = row.get_index()
            current = index

            # Loop until finding a chat with unread count or completing a cycle
            while True:
                if forwards:
                    index += 1
                    if index >= len(self.get_children()):
                        index = 0
                else:
                    index -= 1
                    if index < 0:
                        index = len(self.get_children()) - 1

                row = self.get_row_at_index(index)
                if row.unread_count > 0:
                    unread_found = True
                    break
                if index == current:
                    break

        if unread_found:
            self.select_chat(row.account, row.jid)
            return

        index = row.get_index()
        if forwards:
            next_row = self.get_row_at_index(index + 1)
        else:
            next_row = self.get_row_at_index(index - 1)
        if next_row is None:
            if forwards:
                next_row = self.get_row_at_index(0)
            else:
                last = len(self.get_children()) - 1
                next_row = self.get_row_at_index(last)
            self.select_chat(next_row.account, next_row.jid)
            return

        self.select_chat(next_row.account, next_row.jid)

    def select_chat_number(self, number):
        row = self.get_row_at_index(number)
        if row is not None:
            self.select_chat(row.account, row.jid)

    def toggle_chat_pinned(self, account, jid):
        row = self._chats[(account, jid)]
        row.toggle_pinned()
        self.invalidate_sort()

    def remove_chat(self, account, jid):
        row = self._chats.pop((account, jid))
        self.remove(row)
        row.destroy()
        self.emit_unread_changed()

    def remove_chats_for_account(self, account):
        for row_account, jid in list(self._chats.keys()):
            if row_account != account:
                continue
            self.remove_chat(account, jid)

    def get_selected_chat(self):
        row = self.get_selected_row()
        if row is None:
            return None
        return row

    def contains_chat(self, account, jid):
        return self._chats.get((account, jid)) is not None

    def get_open_chats(self):
        open_chats = []
        for key, value in self._chats.items():
            open_chats.append(key + (value.type, value.is_pinned))
        return open_chats

    def update_time(self):
        for _key, row in self._chats.items():
            row.update_time()

    def process_event(self, event):
        if event.name in ('message-received',
                          'mam-message-received',
                          'gc-message-received'):
            self._on_message_received(event)
        elif event.name == 'presence-received':
            self._on_presence_received(event)
        elif event.name == 'message-sent':
            self._on_message_sent(event)
        else:
            log.warning('Unhandled Event: %s', event.name)

    def _on_message_received(self, event):
        if not event.msgtxt:
            return
        row = self._chats.get((event.account, event.jid))
        nick = self._get_nick_for_received_message(event)
        row.set_nick(nick)
        row.set_timestamp(event.properties.timestamp)
        GLib.idle_add(
            row.set_message_text, event.msgtxt, event.additional_data)
        self._add_unread(row, event.properties)
        self.invalidate_sort()

    def _on_message_sent(self, event):
        msgtext = event.message
        if not msgtext:
            return

        row = self._chats.get((event.account, event.jid))
        con = app.get_client(event.account)
        own_jid = con.get_own_jid()

        if own_jid.bare_match(event.jid):
            nick = ''
        else:
            nick = _('Me: ')
        row.set_nick(nick)

        # Set timestamp if it's None (outgoing MUC messages)
        row.set_timestamp(event.timestamp or time.time())
        GLib.idle_add(
            row.set_message_text, event.message, event.additional_data)
        self.invalidate_sort()

    @staticmethod
    def _get_nick_for_received_message(event):
        nick = _('Me: ')
        if event.properties.type.is_groupchat:
            event_nick = event.properties.muc_nickname
            our_nick = get_group_chat_nick(event.account, event.jid)
            if event_nick != our_nick:
                nick = _('%(incoming_nick)s: ') % {'incoming_nick': event_nick}
        else:
            con = app.get_client(event.account)
            own_jid = con.get_own_jid()
            if not own_jid.bare_match(event.properties.from_):
                nick = ''

        return nick

    def _on_presence_received(self, event):
        row = self._chats.get((event.account, event.jid))
        row.update_avatar()

    @staticmethod
    def _add_unread(row, properties):
        if properties.is_carbon_message and properties.carbon.is_sent:
            return

        if properties.is_from_us():
            return

        row.add_unread()

    def _on_account_changed(self, *args):
        for row in self.get_children():
            row.update_account_identifier()

    def _on_bookmarks_received(self, _event):
        for row in self.get_children():
            row.update_name()


class ChatRow(Gtk.ListBoxRow):
    def __init__(self, workspace_id, account, jid, type_, pinned):
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

        self.contact_name = self.contact.name
        self.timestamp = 0
        self._unread_count = 0
        self._pinned = pinned

        self.get_style_context().add_class('chatlist-row')

        self._ui = get_builder('chat_list_row.ui')
        self.add(self._ui.eventbox)

        self.connect('state-flags-changed', self._on_state_flags_changed)
        self._ui.eventbox.connect('button-press-event', self._on_button_press)
        self._ui.close_button.connect('clicked', self._on_close_button_clicked)

        if self.type == 'groupchat':
            self._ui.group_chat_indicator.show()

        self.update_avatar()
        self.update_name()
        self.update_account_identifier()

        # Get last chat message from archive
        line = app.storage.archive.get_last_conversation_line(account, jid)
        if line is not None and line.message is not None:
            GLib.idle_add(
                self.set_message_text, line.message, line.additional_data)
            if line.kind in (KindConstant.CHAT_MSG_SENT,
                             KindConstant.SINGLE_MSG_SENT):
                self._ui.nick_label.set_text(_('Me:'))
                self._ui.nick_label.show()

            if line.kind == KindConstant.GC_MSG:
                our_nick = get_group_chat_nick(account, jid)
                if line.contact_name == our_nick:
                    self._ui.nick_label.set_text(_('Me:'))
                else:
                    self._ui.nick_label.set_text(_('%(muc_nick)s: ') % {
                        'muc_nick': line.contact_name})
                self._ui.nick_label.show()

            self.timestamp = line.time
            uf_timestamp = get_uf_relative_time(line.time)
            self._ui.timestamp_label.set_text(uf_timestamp)

        self.show_all()

    @property
    def header(self):
        header = self.get_header()
        if header is None:
            return None
        return header.type

    @header.setter
    def header(self, type_):
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
    def is_pinned(self):
        return self._pinned

    def _on_button_press(self, _widget, event):
        if event.button == 3:  # right click
            self._popup_menu(event)

    def _popup_menu(self, event):
        menu = get_chat_list_row_menu(
            self.workspace_id, self.account, self.jid, self._pinned)

        rectangle = Gdk.Rectangle()
        rectangle.x = event.x
        rectangle.y = event.y
        rectangle.width = rectangle.height = 1

        popover = Gtk.Popover.new_from_model(self, menu)
        popover.set_relative_to(self)
        popover.set_position(Gtk.PositionType.RIGHT)
        popover.set_pointing_to(rectangle)
        popover.popup()

    def toggle_pinned(self):
        self._pinned = not self._pinned

    def _on_presence_update(self, _contact, _signal_name):
        self.update_avatar()

    def _on_avatar_update(self, _contact, _signal_name):
        self.update_avatar()

    def update_avatar(self):
        scale = self.get_scale_factor()
        surface = self.contact.get_avatar(AvatarSize.ROSTER, scale)
        self._ui.avatar_image.set_from_surface(surface)

    def update_name(self):
        if self.type == 'pm':
            client = app.get_client(self.account)
            muc_name = get_groupchat_name(client, self.jid.bare)
            self._ui.name_label.set_text(f'{self.contact.name} ({muc_name})')
            return

        self.contact_name = self.contact.name
        if self.jid == self._client.get_own_jid().bare:
            self.contact_name = _('Note to myself')
        self._ui.name_label.set_text(self.contact_name)

    def update_account_identifier(self):
        account_class = app.css_config.get_dynamic_class(self.account)
        self._ui.account_identifier.get_style_context().add_class(account_class)
        show = len(app.settings.get_active_accounts()) > 1
        self._ui.account_identifier.set_visible(show)

    def _on_chatstate_update(self, contact, _signal_name):
        if contact.chatstate is None:
            self._ui.chatstate_image.hide()
        else:
            self._ui.chatstate_image.set_visible(contact.chatstate.is_composing)

    def _on_nickname_update(self, _contact, _signal_name):
        self.update_name()

    @property
    def unread_count(self):
        return self._unread_count

    @unread_count.setter
    def unread_count(self, value):
        self._unread_count = value
        self._update_unread()
        self.get_parent().emit_unread_changed()

    @property
    def is_active(self):
        return (self.is_selected() and
                self.get_toplevel().get_property('is-active'))

    @property
    def is_recent(self):
        if self._unread_count:
            return True
        return False

    def _on_state_flags_changed(self, _listboxrow, *args):
        state = self.get_state_flags()
        if (state & Gtk.StateFlags.PRELIGHT) != 0:
            self._ui.revealer.set_reveal_child(True)
        else:
            self._ui.revealer.set_reveal_child(False)

    def _on_close_button_clicked(self, _button):
        app.window.activate_action(
            'remove-chat',
            GLib.Variant('as', [self.account, str(self.jid)]))

    def set_timestamp(self, timestamp):
        self.timestamp = timestamp
        self.update_time()

    def update_time(self):
        self._ui.timestamp_label.set_text(
            get_uf_relative_time(self.timestamp))

    def _update_unread(self):
        if self._unread_count < 1000:
            self._ui.unread_label.set_text(str(self._unread_count))
        else:
            self._ui.unread_label.set_text('999+')
        self._ui.unread_label.set_visible(bool(self._unread_count))

    def add_unread(self):
        control = app.window.get_control(self.account, self.jid)
        if self.is_active and control.get_autoscroll():
            return
        self.unread_count += 1
        if self.unread_count == 1:
            self.changed()

    def reset_unread(self):
        if not self.unread_count:
            return
        self.unread_count = 0

    def set_nick(self, nickname):
        self._ui.nick_label.set_visible(bool(nickname))
        self._ui.nick_label.set_text(nickname)

    def set_message_text(self, text, additional_data):
        icon = None
        if app.interface.preview_manager.get_previewable(text, additional_data):
            file_name = filename_from_uri(text)
            icon, file_type = guess_simple_file_type(text)
            text = _('%(file_type)s (%(file_name)s)') % {
                'file_type': file_type,
                'file_name': file_name}
        else:
            text = text.replace('\n', ' ')
        self._ui.message_label.set_text(text)
        if icon is None:
            self._ui.message_icon.hide()
        else:
            self._ui.message_icon.set_from_gicon(icon, Gtk.IconSize.MENU)
            self._ui.message_icon.show()


class BaseHeader(Gtk.Box):
    def __init__(self, row_type, text):
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
