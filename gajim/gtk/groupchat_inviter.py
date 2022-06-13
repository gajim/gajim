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
from typing import Optional

import locale

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common import types
from gajim.common.i18n import _
from gajim.common.const import AvatarSize
from gajim.common.const import Direction
from gajim.common.helpers import validate_jid

from .builder import get_builder
from .contacts_flowbox import ContactsFlowBox
from .util import AccountBadge


class ContactRow(Gtk.ListBoxRow):
    def __init__(self,
                 account: str,
                 contact: Optional[types.BareContact],
                 jid: str,
                 name: str,
                 show_account: bool
                 ) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.get_style_context().add_class('start-chat-row')
        self.account = account
        self.jid = jid

        self._contact = contact
        self._name = name
        self._show_account = show_account

        self._account_label = app.get_account_label(account)
        self.is_new: bool = jid == ''

        grid = Gtk.Grid()
        grid.set_column_spacing(12)
        grid.set_size_request(260, -1)

        image = self._get_avatar_image(contact)
        image.set_size_request(AvatarSize.ROSTER, AvatarSize.ROSTER)
        grid.add(image)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        box.set_hexpand(True)

        if self._name is None:
            self._name = _('Invite New Contact')

        self._name_label = Gtk.Label(label=self._name)
        self._name_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._name_label.set_xalign(0)
        self._name_label.set_width_chars(20)
        self._name_label.set_halign(Gtk.Align.START)
        self._name_label.get_style_context().add_class('bold16')
        name_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        name_box.add(self._name_label)

        if show_account:
            account_badge = AccountBadge(account)
            account_badge.set_halign(Gtk.Align.END)
            account_badge.set_valign(Gtk.Align.START)
            account_badge.set_hexpand(True)
            name_box.add(account_badge)
        box.add(name_box)

        self._jid_label = Gtk.Label(label=str(jid))
        self._jid_label.set_tooltip_text(str(jid))
        self._jid_label.set_ellipsize(Pango.EllipsizeMode.END)
        self._jid_label.set_xalign(0)
        self._jid_label.set_width_chars(22)
        self._jid_label.set_halign(Gtk.Align.START)
        self._jid_label.get_style_context().add_class('dim-label')
        box.add(self._jid_label)

        grid.add(box)

        self.add(grid)
        self.show_all()

    def _get_avatar_image(self,
                          contact: Optional[types.BareContact]
                          ) -> Gtk.Image:
        if contact is None:
            icon_name = 'avatar-default'
            return Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.DND)

        scale = self.get_scale_factor()
        surface = contact.get_avatar(AvatarSize.ROSTER, scale)
        assert not isinstance(surface, GdkPixbuf.Pixbuf)
        return Gtk.Image.new_from_surface(surface)

    def update_jid(self, jid: str) -> None:
        self.jid = jid
        self._jid_label.set_text(jid)

    def get_search_text(self):
        if self._contact is None:
            return str(self.jid)
        if self._show_account:
            return f'{self._name} {self.jid} {self._account_label}'
        return f'{self._name} {self.jid}'


class GroupChatInviter(Gtk.Box):
    __gsignals__ = {
        'listbox-changed': (GObject.SignalFlags.RUN_LAST, None, (bool,))
    }

    def __init__(self, room_jid: str) -> None:
        Gtk.Box.__init__(self)
        self.set_size_request(-1, 250)
        self._ui = get_builder('groupchat_inviter.ui')
        self.add(self._ui.invite_box)

        self._invitees_box = ContactsFlowBox()
        self._invitees_box.connect('contact-removed', self._on_invitee_removed)
        self._ui.invitees_scrolled.add(self._invitees_box)

        self._ui.contacts_listbox.set_filter_func(self._filter_func, None)
        self._ui.contacts_listbox.set_sort_func(self._sort_func, None)
        self._ui.contacts_listbox.connect(
            'row-activated', self._on_contacts_row_activated)

        self._room_jid = room_jid

        self._new_contact_row_visible = False
        self._new_contact_rows: dict[str, Optional[ContactRow]] = {}
        self._accounts: list[list[str]] = []

        self._ui.search_entry.connect(
            'search-changed', self._on_search_changed)
        self._ui.search_entry.connect(
            'next-match', self._select_new_match, Direction.NEXT)
        self._ui.search_entry.connect(
            'previous-match', self._select_new_match, Direction.PREV)
        self._ui.search_entry.connect(
            'stop-search', lambda *args: self._ui.search_entry.set_text(''))
        self._ui.search_entry.connect(
            'activate', self._on_search_activate)
        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)

        self.show_all()

    def _add_accounts(self) -> None:
        for account in self._accounts:
            self._ui.account_store.append([None, *account])

    def _add_contacts(self) -> None:
        show_account = len(self._accounts) > 1
        for account, _label in self._accounts:
            self._new_contact_rows[account] = None
            client = app.get_client(account)
            for contact in client.get_module('Roster').iter_contacts():
                # Exclude group chats
                if contact.is_groupchat:
                    continue
                # Exclude our own jid
                if contact.jid == client.get_own_jid().bare:
                    continue

                row = ContactRow(account,
                                 contact,
                                 str(contact.jid),
                                 contact.name,
                                 show_account)
                self._ui.contacts_listbox.add(row)

    def _on_contacts_row_activated(self,
                                   listbox: Gtk.ListBox,
                                   row: ContactRow
                                   ) -> None:
        if row.is_new:
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
            self._remove_new_contact_row()

        self._invitees_box.add_contact(row.account, row.jid, is_new=row.is_new)

        if not row.is_new:
            listbox.remove(row)
            row.destroy()

        self._ui.search_entry.set_text('')
        GLib.timeout_add(50, self._select_first_row)
        self._ui.search_entry.grab_focus()

        invitable = self._invitees_box.has_contacts()
        self.emit('listbox-changed', invitable)

    def _on_invitee_removed(self,
                            flowbox: ContactsFlowBox,
                            account: str,
                            jid: str,
                            is_new: bool
                            ) -> None:
        if not is_new:
            show_account = len(self._accounts) > 1
            client = app.get_client(account)
            contact = client.get_module('Contacts').get_contact(jid)
            row = ContactRow(account,
                             contact,
                             str(contact.jid),
                             contact.name,
                             show_account)
            self._ui.contacts_listbox.add(row)
        self._ui.search_entry.grab_focus()
        self.emit('listbox-changed', flowbox.has_contacts())

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> int:
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

    def _on_search_activate(self, _entry: Gtk.SearchEntry) -> None:
        row = self._ui.contacts_listbox.get_selected_row()
        if row is not None and row.get_child_visible():
            row.emit('activate')

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        search_text = entry.get_text()
        if '@' in search_text:
            self._add_new_contact_row()
            self._update_new_contact_rows(search_text)
        else:
            self._remove_new_contact_row()
        self._ui.contacts_listbox.invalidate_filter()

    def _add_new_contact_row(self) -> None:
        if self._new_contact_row_visible:
            return

        for account in self._new_contact_rows:
            show_account = len(self._accounts) > 1
            row = ContactRow(account,
                             None,
                             '',
                             _('New Contact'),
                             show_account)
            self._new_contact_rows[account] = row
            self._ui.contacts_listbox.add(row)
        self._new_contact_row_visible = True

    def _remove_new_contact_row(self) -> None:
        if not self._new_contact_row_visible:
            return

        for row in self._new_contact_rows.values():
            if row is not None:
                self._ui.contacts_listbox.remove(row)
        self._new_contact_row_visible = False

    def _update_new_contact_rows(self, search_text: str) -> None:
        for row in self._new_contact_rows.values():
            if row is not None:
                row.update_jid(search_text)

    def _select_new_match(self,
                          _entry: Gtk.SearchEntry,
                          direction: Direction
                          ) -> None:
        selected_row = self._ui.contacts_listbox.get_selected_row()
        if selected_row is None:
            return

        index = selected_row.get_index()

        if direction == Direction.NEXT:
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
            if direction == Direction.NEXT:
                index += 1
            else:
                index -= 1

    def _select_first_row(self) -> None:
        first_row = self._ui.contacts_listbox.get_row_at_y(0)
        self._ui.contacts_listbox.select_row(first_row)

    def _scroll_to_first_row(self) -> None:
        self._ui.scrolledwindow.get_vadjustment().set_value(0)

    def _filter_func(self,
                     row: ContactRow,
                     _user_data: Optional[Any]
                     ) -> bool:
        search_text = self._ui.search_entry.get_text().lower()
        search_text_list = search_text.split()
        row_text = row.get_search_text().lower()
        for text in search_text_list:
            if text not in row_text:
                GLib.timeout_add(50, self._select_first_row)
                return False
        GLib.timeout_add(50, self._select_first_row)
        return True

    @staticmethod
    def _sort_func(row1: ContactRow,
                   row2: ContactRow,
                   _user_data: Optional[Any]
                   ) -> int:
        name1 = row1.get_search_text()
        name2 = row2.get_search_text()
        account1 = row1.account
        account2 = row2.account

        result = locale.strcoll(account1.lower(), account2.lower())
        if result != 0:
            return result

        return locale.strcoll(name1.lower(), name2.lower())

    def _reset(self) -> None:
        def _remove(row: Gtk.ListBoxRow) -> None:
            self.remove(row)
            row.destroy()
        self._ui.contacts_listbox.foreach(_remove)
        self._invitees_box.clear()

    def load_contacts(self) -> None:
        self._reset()

        self._accounts = app.get_enabled_accounts_with_labels()
        self._new_contact_rows = {}
        self._add_accounts()

        self._add_contacts()

        first_row = self._ui.contacts_listbox.get_row_at_index(0)
        self._ui.contacts_listbox.select_row(first_row)
        self._ui.search_entry.grab_focus()
        self.emit('listbox-changed', False)

    def focus_search_entry(self) -> None:
        self._ui.search_entry.grab_focus()

    def get_invitees(self) -> list[str]:
        return self._invitees_box.get_contact_jids()
