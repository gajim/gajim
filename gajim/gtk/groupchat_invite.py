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

import locale

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.const import AvatarSize
from gajim.common.helpers import validate_jid

from .util import get_builder
from .util import AccountBadge


class GroupChatInvite(Gtk.Box):
    __gsignals__ = {
        'listbox-changed': (GObject.SignalFlags.RUN_LAST, None, (bool,))
    }

    def __init__(self, room_jid):
        Gtk.Box.__init__(self)
        self.set_size_request(-1, 300)
        self._ui = get_builder('groupchat_invite.ui')
        self.add(self._ui.invite_grid)

        self._ui.contacts_listbox.set_filter_func(self._filter_func, None)
        self._ui.contacts_listbox.set_sort_func(self._sort_func, None)
        self._ui.contacts_listbox.set_placeholder(self._ui.contacts_placeholder)
        self._ui.contacts_listbox.connect('row-activated',
                                          self._on_contacts_row_activated)

        self._ui.invitees_listbox.set_sort_func(self._sort_func, None)
        self._ui.invitees_listbox.set_placeholder(
            self._ui.invitees_placeholder)
        self._ui.invitees_listbox.connect('row-activated',
                                          self._on_invitees_row_activated)

        self._new_contact_row_visible = False
        self._room_jid = room_jid

        self._ui.search_entry.connect('search-changed',
                                      self._on_search_changed)
        self._ui.search_entry.connect('next-match',
                                      self._select_new_match, 'next')
        self._ui.search_entry.connect('previous-match',
                                      self._select_new_match, 'prev')
        self._ui.search_entry.connect(
            'stop-search', lambda *args: self._ui.search_entry.set_text(''))
        self._ui.search_entry.connect('activate',
                                      self._on_search_activate)
        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

        self.show_all()

    def _add_accounts(self):
        for account in self._accounts:
            self._ui.account_store.append([None, *account])

    def _add_contacts(self):
        show_account = len(self._accounts) > 1
        for account, _label in self._accounts:
            self.new_contact_rows[account] = None
            client = app.get_client(account)
            for contact in client.get_module('Roster').iter_contacts():

                # Exclude group chats
                if contact.is_groupchat:
                    continue
                # Exclude our own jid
                if contact.jid == client.get_own_jid().bare:
                    continue

                row = ContactRow(account, contact, contact.jid,
                                 contact.name, show_account)
                self._ui.contacts_listbox.add(row)

    def _on_contacts_row_activated(self, listbox, row):
        if row.new:
            jid = row.jid
            try:
                validate_jid(jid)
            except ValueError as error:
                icon = 'dialog-warning-symbolic'
                self._ui.search_entry.set_icon_from_icon_name(
                    Gtk.EntryIconPosition.SECONDARY, icon)
                self._ui.search_entry.set_icon_tooltip_text(
                    Gtk.EntryIconPosition.SECONDARY, str(error))
                return
            self._ui.search_entry.set_icon_from_icon_name(
                Gtk.EntryIconPosition.SECONDARY, None)
            show_account = len(self._accounts) > 1
            row = ContactRow(
                row.account, None, '', None, show_account)
            row.update_jid(jid)
            self._remove_new_jid_row()
        else:
            listbox.remove(row)
        self._ui.invitees_listbox.add(row)
        self._ui.invitees_listbox.unselect_row(row)
        self._ui.search_entry.set_text('')

        GLib.timeout_add(50, self._select_first_row)
        self._ui.search_entry.grab_focus()

        invitable = self._ui.invitees_listbox.get_row_at_index(0) is not None
        self.emit('listbox-changed', invitable)

    def _on_invitees_row_activated(self, listbox, row):
        listbox.remove(row)
        if not row.new:
            self._ui.contacts_listbox.add(row)
            self._ui.contacts_listbox.unselect_row(row)
        self._ui.search_entry.grab_focus()
        invitable = listbox.get_row_at_index(0) is not None
        self.emit('listbox-changed', invitable)

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Down:
            self._ui.search_entry.emit('next-match')
            return Gdk.EVENT_STOP

        if event.keyval == Gdk.KEY_Up:
            self._ui.search_entry.emit('previous-match')
            return Gdk.EVENT_STOP

        if event.keyval == Gdk.KEY_Return:
            row = self._ui.contacts_listbox.get_selected_row()
            if row is not None:
                row.emit('activate')
            return Gdk.EVENT_STOP

        self._ui.search_entry.grab_focus_without_selecting()

        return Gdk.EVENT_PROPAGATE

    def _on_search_activate(self, _entry):
        row = self._ui.contacts_listbox.get_selected_row()
        if row is not None and row.get_child_visible():
            row.emit('activate')

    def _on_search_changed(self, entry):
        search_text = entry.get_text()
        if '@' in search_text:
            self._add_new_jid_row()
            self._update_new_jid_rows(search_text)
        else:
            self._remove_new_jid_row()
        self._ui.contacts_listbox.invalidate_filter()

    def _add_new_jid_row(self):
        if self._new_contact_row_visible:
            return
        for account in self.new_contact_rows:
            show_account = len(self._accounts) > 1
            row = ContactRow(account, None, '', None, show_account)
            self.new_contact_rows[account] = row
            self._ui.contacts_listbox.add(row)
            row.get_parent().show_all()
        self._new_contact_row_visible = True

    def _remove_new_jid_row(self):
        if not self._new_contact_row_visible:
            return
        for row in self.new_contact_rows.values():
            self._ui.contacts_listbox.remove(row)
        self._new_contact_row_visible = False

    def _update_new_jid_rows(self, search_text):
        for row in self.new_contact_rows.values():
            row.update_jid(search_text)

    def _select_new_match(self, _entry, direction):
        selected_row = self._ui.contacts_listbox.get_selected_row()
        if selected_row is None:
            return

        index = selected_row.get_index()

        if direction == 'next':
            index += 1
        else:
            index -= 1

        while True:
            new_selected_row = self._ui.contacts_listbox.get_row_at_index(index)
            if new_selected_row is None:
                return
            if new_selected_row.get_child_visible():
                self._ui.contacts_listbox.select_row(new_selected_row)
                new_selected_row.grab_focus()
                return
            if direction == 'next':
                index += 1
            else:
                index -= 1

    def _select_first_row(self):
        first_row = self._ui.contacts_listbox.get_row_at_y(0)
        self._ui.contacts_listbox.select_row(first_row)

    def _scroll_to_first_row(self):
        self._ui.scrolledwindow.get_vadjustment().set_value(0)

    def _filter_func(self, row, _user_data):
        search_text = self._ui.search_entry.get_text().lower()
        search_text_list = search_text.split()
        row_text = row.get_search_text().lower()
        for text in search_text_list:
            if text not in row_text:
                GLib.timeout_add(50, self._select_first_row)
                return None
        GLib.timeout_add(50, self._select_first_row)
        return True

    @staticmethod
    def _sort_func(row1, row2, _user_data):
        name1 = row1.get_search_text()
        name2 = row2.get_search_text()
        account1 = row1.account
        account2 = row2.account

        result = locale.strcoll(account1.lower(), account2.lower())
        if result != 0:
            return result

        return locale.strcoll(name1.lower(), name2.lower())

    def load_contacts(self):
        self._ui.contacts_listbox.foreach(self._ui.contacts_listbox.remove)
        self._ui.invitees_listbox.foreach(self._ui.invitees_listbox.remove)
        self._accounts = app.get_enabled_accounts_with_labels()
        self.new_contact_rows = {}
        self._add_accounts()
        self._add_contacts()
        first_row = self._ui.contacts_listbox.get_row_at_index(0)
        self._ui.contacts_listbox.select_row(first_row)
        self._ui.search_entry.grab_focus()
        self.emit('listbox-changed', False)

    def focus_search_entry(self):
        self._ui.search_entry.grab_focus()

    def get_invitees(self):
        invitees = []
        for row in self._ui.invitees_listbox.get_children():
            invitees.append(row.jid)
        return invitees


class ContactRow(Gtk.ListBoxRow):
    def __init__(self, account, contact, jid, name, show_account):
        Gtk.ListBoxRow.__init__(self)
        self.get_style_context().add_class('start-chat-row')
        self.account = account
        self.account_label = app.get_account_label(account)
        self.show_account = show_account
        self.jid = jid
        self.contact = contact
        self.name = name
        self.new = jid == ''

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_size_request(260, -1)

        image = self._get_avatar_image(contact)
        image.set_size_request(AvatarSize.ROSTER, AvatarSize.ROSTER)
        grid.add(image)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_hexpand(True)

        if self.name is None:
            self.name = _('Invite New Contact')

        self.name_label = Gtk.Label(label=self.name)
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_label.set_xalign(0)
        self.name_label.set_width_chars(20)
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.get_style_context().add_class('bold16')
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_box.add(self.name_label)

        if show_account:
            account_badge = AccountBadge(account)
            account_badge.set_halign(Gtk.Align.END)
            account_badge.set_valign(Gtk.Align.START)
            account_badge.set_hexpand(True)
            name_box.add(account_badge)
        box.add(name_box)

        self.jid_label = Gtk.Label(label=str(jid))
        self.jid_label.set_tooltip_text(str(jid))
        self.jid_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.jid_label.set_xalign(0)
        self.jid_label.set_width_chars(22)
        self.jid_label.set_halign(Gtk.Align.START)
        self.jid_label.get_style_context().add_class('dim-label')
        box.add(self.jid_label)

        grid.add(box)

        self.add(grid)
        self.show_all()

    def _get_avatar_image(self, contact):
        if self.new:
            icon_name = 'avatar-default'
            return Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DND)

        scale = self.get_scale_factor()
        surface = contact.get_avatar(AvatarSize.ROSTER, scale)
        return Gtk.Image.new_from_surface(surface)

    def update_jid(self, jid):
        self.jid = jid
        self.jid_label.set_text(jid)

    def get_search_text(self):
        if self.contact is None:
            return str(self.jid)
        if self.show_account:
            return '%s %s %s' % (self.name, self.jid, self.account_label)
        return '%s %s' % (self.name, self.jid)
