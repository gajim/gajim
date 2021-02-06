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
        if row is None:
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
        for _, row in self._chats.items():
            row.update_time()

    def process_event(self, event):
        if event.name in ('message-received',
                          'mam-message-received',
                          'gc-message-received'):
            self._on_message_received(event)
        else:
            log.warning('Unhandled Event: %s', event.name)

    def _on_message_received(self, event):
        if not event.msgtxt:
            return

        row = self._chats.get((event.account, event.jid))
        row.add_unread()
        row.set_last_message_text('Me', event.msgtxt)


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

        contact = app.contacts.get_contact(account, jid)

        scale = self.get_scale_factor()
        if contact:
            if contact.is_groupchat:
                avatar = app.contacts.get_avatar(account,
                                                jid,
                                                AvatarSize.ROSTER,
                                                scale)
                con = app.connections[account]
                name = get_groupchat_name(con, jid)
            else:
                avatar = app.contacts.get_avatar(account,
                                                 contact.jid,
                                                 AvatarSize.ROSTER,
                                                 scale,
                                                 contact.show)
                name = contact.get_shown_name()
        else:
            avatar = app.contacts.get_avatar(account,
                                             jid,
                                             AvatarSize.ROSTER,
                                             scale)
            name = jid

        self._ui.avatar_image.set_from_surface(avatar)
        self._ui.name_label.set_text(name)

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

    def _on_state_flags_changed(self, _listboxrow, *args):
        state = self.get_state_flags()
        if (state & Gtk.StateFlags.PRELIGHT) != 0:
            self._ui.revealer.set_reveal_child(True)
        else:
            self._ui.revealer.set_reveal_child(False)

    def _on_close_button_clicked(self, _button):
        app.window.remove_chat(self.workspace_id, self.account, self.jid)

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

    def reset_unread(self):
        self.unread_count = 0

    def set_last_message_text(self, nickname, text):
        self._ui.message_label.set_text(text)
        self._ui.nick_label.set_text(nickname)
