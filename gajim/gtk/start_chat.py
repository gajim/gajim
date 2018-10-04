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
from gi.repository import Gtk
from gi.repository import GLib
from gi.repository import Pango

from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _
from gajim.common.const import AvatarSize

from gajim.gtk.util import get_iconset_name_for
from gajim.gtk.util import get_builder


class StartChatDialog(Gtk.ApplicationWindow):
    def __init__(self):
        Gtk.ApplicationWindow.__init__(self)
        self.set_name('StartChatDialog')
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Start new Conversation'))
        self.set_default_size(-1, 400)
        self.ready_to_destroy = False

        self.builder = get_builder('start_chat_dialog.ui')
        self.listbox = self.builder.get_object('listbox')
        self.search_entry = self.builder.get_object('search_entry')
        self.box = self.builder.get_object('box')

        self.add(self.box)

        self.new_contact_row_visible = False
        self.new_contact_rows = {}
        self.new_groupchat_rows = {}
        self.accounts = app.connections.keys()
        self.add_contacts()
        self.add_groupchats()

        self.search_entry.connect('search-changed',
                                  self._on_search_changed)
        self.search_entry.connect('next-match',
                                  self._select_new_match, 'next')
        self.search_entry.connect('previous-match',
                                  self._select_new_match, 'prev')
        self.search_entry.connect('stop-search',
                                  lambda *args: self.search_entry.set_text(''))

        self.listbox.set_filter_func(self._filter_func, None)
        self.listbox.set_sort_func(self._sort_func, None)
        self.listbox.connect('row-activated', self._on_row_activated)

        self.connect('key-press-event', self._on_key_press)
        self.connect('destroy', self._destroy)

        self.select_first_row()
        self.show_all()

    def add_contacts(self):
        show_account = len(self.accounts) > 1
        for account in self.accounts:
            self.new_contact_rows[account] = None
            for jid in app.contacts.get_jid_list(account):
                contact = app.contacts.get_contact_with_highest_priority(
                    account, jid)
                if contact.is_groupchat():
                    continue
                row = ContactRow(account, contact, jid,
                                 contact.get_shown_name(), show_account)
                self.listbox.add(row)

    def add_groupchats(self):
        show_account = len(self.accounts) > 1
        for account in self.accounts:
            self.new_groupchat_rows[account] = None
            con = app.connections[account]
            bookmarks = con.get_module('Bookmarks').bookmarks
            groupchats = {}
            for jid, bookmark in bookmarks.items():
                groupchats[jid] = bookmark['name']

            for jid in app.contacts.get_gc_list(account):
                if jid in groupchats:
                    continue
                groupchats[jid] = None

            for jid in groupchats:
                name = groupchats[jid]
                if not name:
                    name = app.get_nick_from_jid(jid)
                row = ContactRow(account, None, jid, name,
                                 show_account, True)
                self.listbox.add(row)

    def _on_row_activated(self, listbox, row):
        row = row.get_child()
        self._start_new_chat(row)

    def _on_key_press(self, widget, event):
        if event.keyval in (Gdk.KEY_Down, Gdk.KEY_Tab):
            self.search_entry.emit('next-match')
            return True

        if (event.state == Gdk.ModifierType.SHIFT_MASK and
              event.keyval == Gdk.KEY_ISO_Left_Tab):
            self.search_entry.emit('previous-match')
            return True

        if event.keyval == Gdk.KEY_Up:
            self.search_entry.emit('previous-match')
            return True

        if event.keyval == Gdk.KEY_Escape:
            if self.search_entry.get_text() != '':
                self.search_entry.emit('stop-search')
            else:
                self.destroy()
            return True

        if event.keyval == Gdk.KEY_Return:
            row = self.listbox.get_selected_row()
            if row is not None:
                row.emit('activate')
            return True

        self.search_entry.grab_focus_without_selecting()

    def _start_new_chat(self, row):
        if row.new:
            if not app.account_is_connected(row.account):
                app.interface.raise_dialog('start-chat-not-connected')
                return
            try:
                helpers.parse_jid(row.jid)
            except helpers.InvalidFormat as e:
                app.interface.raise_dialog('invalid-jid-with-error', str(e))
                return

        if row.groupchat:
            app.interface.join_gc_minimal(row.account, row.jid)
        else:
            app.interface.new_chat_from_jid(row.account, row.jid)

        self.ready_to_destroy = True

    def _on_search_changed(self, entry):
        search_text = entry.get_text()
        if '@' in search_text:
            self._add_new_jid_row()
            self._update_new_jid_rows(search_text)
        else:
            self._remove_new_jid_row()
        self.listbox.invalidate_filter()

    def _add_new_jid_row(self):
        if self.new_contact_row_visible:
            return
        for account in self.new_contact_rows:
            show_account = len(self.accounts) > 1
            row = ContactRow(account, None, '', None, show_account)
            self.new_contact_rows[account] = row
            group_row = ContactRow(account, None, '', None, show_account, True)
            self.new_groupchat_rows[account] = group_row
            self.listbox.add(row)
            self.listbox.add(group_row)
            row.get_parent().show_all()
        self.new_contact_row_visible = True

    def _remove_new_jid_row(self):
        if not self.new_contact_row_visible:
            return
        for account in self.new_contact_rows:
            self.listbox.remove(self.new_contact_rows[account].get_parent())
            self.listbox.remove(self.new_groupchat_rows[account].get_parent())
        self.new_contact_row_visible = False

    def _update_new_jid_rows(self, search_text):
        for account in self.new_contact_rows:
            self.new_contact_rows[account].update_jid(search_text)
            self.new_groupchat_rows[account].update_jid(search_text)

    def _select_new_match(self, entry, direction):
        selected_row = self.listbox.get_selected_row()
        index = selected_row.get_index()

        if direction == 'next':
            index += 1
        else:
            index -= 1

        while True:
            new_selected_row = self.listbox.get_row_at_index(index)
            if new_selected_row is None:
                return
            if new_selected_row.get_child_visible():
                self.listbox.select_row(new_selected_row)
                new_selected_row.grab_focus()
                return
            if direction == 'next':
                index += 1
            else:
                index -= 1

    def select_first_row(self):
        first_row = self.listbox.get_row_at_y(0)
        self.listbox.select_row(first_row)

    def _filter_func(self, row, user_data):
        search_text = self.search_entry.get_text().lower()
        search_text_list = search_text.split()
        row_text = row.get_child().get_search_text().lower()
        for text in search_text_list:
            if text not in row_text:
                GLib.timeout_add(50, self.select_first_row)
                return
        GLib.timeout_add(50, self.select_first_row)
        return True

    @staticmethod
    def _sort_func(row1, row2, user_data):
        name1 = row1.get_child().get_search_text()
        name2 = row2.get_child().get_search_text()
        account1 = row1.get_child().account
        account2 = row2.get_child().account
        is_groupchat1 = row1.get_child().groupchat
        is_groupchat2 = row2.get_child().groupchat
        new1 = row1.get_child().new
        new2 = row2.get_child().new

        result = locale.strcoll(account1.lower(), account2.lower())
        if result != 0:
            return result

        if new1 != new2:
            return 1 if new1 else -1

        if is_groupchat1 != is_groupchat2:
            return 1 if is_groupchat1 else -1

        return locale.strcoll(name1.lower(), name2.lower())

    @staticmethod
    def _destroy(*args):
        del app.interface.instances['start_chat']


class ContactRow(Gtk.Grid):
    def __init__(self, account, contact, jid, name, show_account,
                 groupchat=False):
        Gtk.Grid.__init__(self)
        self.set_column_spacing(12)
        self.set_size_request(260, -1)
        self.account = account
        self.account_label = app.get_account_label(account)
        self.show_account = show_account
        self.jid = jid
        self.contact = contact
        self.name = name
        self.groupchat = groupchat
        self.new = jid == ''

        if self.groupchat:
            muc_icon = get_iconset_name_for(
                'muc-inactive' if self.new else 'muc-active')
            image = Gtk.Image.new_from_icon_name(muc_icon, Gtk.IconSize.DND)
        else:
            scale = self.get_scale_factor()
            avatar = app.contacts.get_avatar(
                account, jid, AvatarSize.ROSTER, scale)
            if avatar is None:
                image = Gtk.Image.new_from_icon_name(
                    'avatar-default', Gtk.IconSize.DND)
            else:
                image = Gtk.Image.new_from_surface(avatar)

        image.set_size_request(AvatarSize.ROSTER, AvatarSize.ROSTER)
        self.add(image)

        middle_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        middle_box.set_hexpand(True)

        if self.name is None:
            if self.groupchat:
                self.name = _('New Groupchat')
            else:
                self.name = _('New Contact')

        self.name_label = Gtk.Label(label=self.name)
        self.name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.name_label.set_xalign(0)
        self.name_label.set_width_chars(25)
        self.name_label.set_halign(Gtk.Align.START)
        self.name_label.get_style_context().add_class('bold16')

        status = contact.show if contact else 'offline'
        css_class = helpers.get_css_show_color(status)
        if css_class is not None:
            self.name_label.get_style_context().add_class(css_class)
        middle_box.add(self.name_label)

        self.jid_label = Gtk.Label(label=jid)
        self.jid_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.jid_label.set_xalign(0)
        self.jid_label.set_width_chars(25)
        self.jid_label.set_halign(Gtk.Align.START)
        middle_box.add(self.jid_label)

        self.add(middle_box)

        if show_account:
            account_label = Gtk.Label(label=self.account_label)
            account_label.set_halign(Gtk.Align.START)
            account_label.set_valign(Gtk.Align.START)

            right_box = Gtk.Box()
            right_box.set_vexpand(True)
            right_box.add(account_label)
            self.add(right_box)

        self.show_all()

    def update_jid(self, jid):
        self.jid = jid
        self.jid_label.set_text(jid)

    def get_search_text(self):
        if self.contact is None and not self.groupchat:
            return self.jid
        if self.show_account:
            return '%s %s %s' % (self.name, self.jid, self.account_label)
        return '%s %s' % (self.name, self.jid)
