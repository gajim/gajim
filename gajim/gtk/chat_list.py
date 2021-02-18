import logging

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import KindConstant
from gajim.common.i18n import _
from gajim.common.helpers import get_groupchat_name
from gajim.common.helpers import get_group_chat_nick
from gajim.common.helpers import get_uf_relative_time

from .tooltips import RosterTooltip
from .util import get_builder

log = logging.getLogger('gajim.gui.chatlist')


class ChatList(Gtk.ListBox):
    def __init__(self, workspace_id):
        Gtk.ListBox.__init__(self)

        self._chats = {}
        self._current_filter_text = ''
        self._workspace_id = workspace_id

        self.get_style_context().add_class('chatlist')
        self.set_filter_func(self._filter_func)
        self.set_sort_func(self._sort_func)
        self.set_has_tooltip(True)

        self.connect('destroy', self._on_destroy)
        self.connect('query-tooltip', self._query_tooltip)

        self._timer_id = GLib.timeout_add_seconds(60, self._update_timer)
        self._tab_tooltip = RosterTooltip()

        self.show_all()

    @property
    def workspace_id(self):
        return self._workspace_id

    def get_unread_count(self):
        return sum([chats.unread_count for chats in self._chats.values()])

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

    def _query_tooltip(self, widget, _x_pos, y_pos, _keyboard_mode, tooltip):
        row = self.get_row_at_y(y_pos)
        if row is None or row.type == 'pm':
            self._tab_tooltip.clear_tooltip()
            return False

        connected_contacts = []
        contacts = app.contacts.get_contacts(row.account, row.jid)
        if row.type == 'contact':
            for contact in contacts:
                if contact.show not in ('offline', 'error'):
                    connected_contacts.append(contact)
            if not connected_contacts:
                # no connected contacts, show the offline one
                connected_contacts = contacts
        elif row.type == 'groupchat':
            connected_contacts = contacts
        else:
            # TODO
            connected_contacts = [row.jid]

        value, widget = self._tab_tooltip.get_tooltip(
            row, connected_contacts, row.account, None)
        tooltip.set_custom(widget)
        return value

    def _filter_func(self, row):
        if not self._current_filter_text:
            return True
        return self._current_filter_text in row.jid

    @staticmethod
    def _sort_func(row1, row2):
        if row1.is_recent == row2.is_recent:
            return 0
        return -1 if row1.is_recent else 1

    def set_filter_text(self, text):
        self._current_filter_text = text
        self.invalidate_filter()

    def get_chat_type(self, account, jid):
        row = self._chats.get((account, jid))
        return row.type

    def add_chat(self, account, jid, type_):
        if self._chats.get((account, jid)) is not None:
            # Chat is already in the List
            return

        row = ChatRow(self._workspace_id, account, jid, type_)
        self._chats[(account, jid)] = row
        self.add(row)

    def select_chat(self, account, jid):
        row = self._chats[(account, jid)]
        self.select_row(row)

    def remove_chat(self, account, jid):
        row = self._chats.pop((account, jid))
        self.remove(row)
        row.destroy()

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
            open_chats.append(key + (value.type,))
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
        elif event.name == 'chatstate-received':
            self._on_chatstate_received(event)
        else:
            log.warning('Unhandled Event: %s', event.name)

    def _on_message_received(self, event):
        if not event.msgtxt:
            return

        row = self._chats.get((event.account, event.jid))
        nick = self._get_nick_for_received_message(event)
        row.set_last_message_text(nick, event.msgtxt)
        row.set_timestamp(event.properties.timestamp)

        self._add_unread(row, event.properties)

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
        row.set_last_message_text(nick, msgtext)
        row.set_timestamp(event.timestamp)

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

    def _on_chatstate_received(self, event):
        row = self._chats.get((event.account, event.jid))
        if event.contact.is_gc_contact:
            chatstate = event.contact.chatstate
        else:
            chatstate = app.contacts.get_combined_chatstate(
                row.account, row.jid)
        row.set_chatstate(chatstate)

    @staticmethod
    def _add_unread(row, properties):
        if properties.is_carbon_message and properties.carbon.is_sent:
            return

        if properties.is_from_us():
            return

        row.add_unread()


class ChatRow(Gtk.ListBoxRow):
    def __init__(self, workspace_id, account, jid, type_):
        Gtk.ListBoxRow.__init__(self)

        self.account = account
        self.jid = jid
        self.workspace_id = workspace_id
        self.type = type_

        self._timestamp = None
        self._unread_count = 0

        self.get_style_context().add_class('chatlist-row')

        self._ui = get_builder('chat_list_row.ui')
        self.add(self._ui.overlay)

        self.connect('state-flags-changed', self._on_state_flags_changed)
        self._ui.close_button.connect('clicked', self._on_close_button_clicked)

        account_class = app.css_config.get_dynamic_class(account)
        self._ui.account_identifier.get_style_context().add_class(account_class)
        if len(app.get_enabled_accounts_with_labels()) > 1:
            self._ui.account_identifier.show()

        if self.type == 'groupchat':
            self._ui.group_chat_indicator.show()

        self.update_avatar()
        self.update_name()

        # Get last chat message from archive
        line = app.storage.archive.get_last_conversation_line(account, jid)
        if line is not None and line.message is not None:
            one_line = ' '.join(line.message.splitlines())
            self._ui.message_label.set_text(one_line)
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

            #  TODO: file transfers have to be displayed differently

            self._timestamp = line.time
            uf_timestamp = get_uf_relative_time(line.time)
            self._ui.timestamp_label.set_text(uf_timestamp)

        self.show_all()

    def update_avatar(self):
        scale = self.get_scale_factor()

        if self.type == 'pm':
            jid, resource = app.get_room_and_nick_from_fjid(self.jid)
            contact = app.contacts.get_gc_contact(
                self.account, jid, resource)
            avatar = contact.get_avatar(AvatarSize.ROSTER,
                                        scale,
                                        contact.show.value)
            self._ui.avatar_image.set_from_surface(avatar)
            return

        contact = app.contacts.get_contact(self.account, self.jid)
        if contact:
            if contact.is_groupchat:
                avatar = app.contacts.get_avatar(self.account,
                                                 self.jid,
                                                 AvatarSize.ROSTER,
                                                 scale)
            else:
                avatar = app.contacts.get_avatar(self.account,
                                                 contact.jid,
                                                 AvatarSize.ROSTER,
                                                 scale,
                                                 contact.show)
        else:
            avatar = app.contacts.get_avatar(self.account,
                                             self.jid,
                                             AvatarSize.ROSTER,
                                             scale)

        self._ui.avatar_image.set_from_surface(avatar)

    def update_name(self):
        if self.type == 'pm':
            jid, resource = app.get_room_and_nick_from_fjid(self.jid)
            contact = app.contacts.get_gc_contact(
                self.account, jid, resource)
            client = app.get_client(self.account)
            muc_name = get_groupchat_name(client, jid)
            self._ui.name_label.set_text(
                f'{contact.get_shown_name()} ({muc_name})')
            return

        contact = app.contacts.get_contact(self.account, self.jid)
        if contact is None:
            self._ui.name_label.set_text(self.jid)
            return

        if contact.is_groupchat:
            client = app.get_client(self.account)
            name = get_groupchat_name(client, self.jid)
        else:
            name = contact.get_shown_name()

        self._ui.name_label.set_text(name)

    def set_chatstate(self, chatstate):
        if chatstate == 'composing':
            self._ui.chatstate_image.show()
        else:
            self._ui.chatstate_image.hide()

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
        app.window.remove_chat(self.workspace_id, self.account, self.jid)

    def set_timestamp(self, timestamp):
        self._timestamp = timestamp
        self.update_time()

    def update_time(self):
        if self._timestamp is not None:
            self._ui.timestamp_label.set_text(
                get_uf_relative_time(self._timestamp))

    def _update_unread(self):
        if self._unread_count < 1000:
            self._ui.unread_label.set_text(str(self._unread_count))
        else:
            self._ui.unread_label.set_text('999+')
        self._ui.unread_label.set_visible(bool(self._unread_count))

    def add_unread(self):
        if self.is_active:
            return
        self.unread_count += 1
        if self.unread_count == 1:
            self.changed()

    def reset_unread(self):
        if not self.unread_count:
            return
        self.unread_count = 0

    def set_last_message_text(self, nickname, text):
        self._ui.message_label.set_text(text)
        self._ui.nick_label.set_visible(bool(nickname))
        self._ui.nick_label.set_text(nickname)
