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
from typing import cast
from typing import Optional

from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.helpers import get_client_status
from gajim.common.i18n import _

from gajim.gtk.util import EventHelper


class AccountSideBar(Gtk.ListBox):
    def __init__(self) -> None:
        Gtk.ListBox.__init__(self)
        self.set_vexpand(True)
        self.set_valign(Gtk.Align.END)
        self.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.get_style_context().add_class('account-sidebar')
        self.connect('row-activated', self._on_row_activated)

        for account in app.settings.get_active_accounts():
            self.add_account(account)

    def add_account(self, account: str) -> None:
        self.add(Account(account))

    def remove_account(self, account: str) -> None:
        accounts = cast(list[Account], self.get_children())
        for row in accounts:
            if row.account == account:
                row.destroy()
                return

    @staticmethod
    def _on_row_activated(_listbox: AccountSideBar, row: Account) -> None:
        app.window.show_account_page(row.account)

    def activate_account_page(self, account: str) -> None:
        row = cast(Account, self.get_selected_row())
        if row is not None and row.account == account:
            return

        self.select_row(row)

    def update_unread_count(self, account: str, count: int) -> None:
        for row in cast(list[Account], self.get_children()):
            if row.account == account:
                row.set_unread_count(count)
                break


class Account(Gtk.ListBoxRow, EventHelper):
    def __init__(self, account: str) -> None:
        Gtk.ListBoxRow.__init__(self)
        EventHelper.__init__(self)
        self.get_style_context().add_class('account-sidebar-item')

        self.account = account
        self._account_class: Optional[str] = None

        self.register_events([
            ('account-enabled', ged.GUI1,
             self._update_account_color_visibility),
            ('account-disabled', ged.GUI1,
             self._update_account_color_visibility),
        ])

        app.settings.connect_signal(
            'account_label',
            self._on_account_label_changed,
            account)

        selection_bar = Gtk.Box()
        selection_bar.set_size_request(6, -1)
        selection_bar.get_style_context().add_class('selection-bar')

        self._image = AccountAvatar(account)

        self._unread_label = Gtk.Label()
        self._unread_label.get_style_context().add_class(
            'unread-counter')
        self._unread_label.set_no_show_all(True)
        self._unread_label.set_halign(Gtk.Align.END)
        self._unread_label.set_valign(Gtk.Align.START)

        self._account_color_bar = Gtk.Box()
        self._account_color_bar.set_no_show_all(True)
        self._account_color_bar.set_size_request(6, -1)
        self._account_color_bar.get_style_context().add_class(
            'account-identifier-bar')
        self._update_account_color_visibility()

        self._account_box = Gtk.Box(spacing=3)
        self._account_box.set_tooltip_text(
            _('Account: %s') % app.get_account_label(account))
        self._account_box.add(selection_bar)
        self._account_box.add(self._image)
        self._account_box.add(self._account_color_bar)
        self._set_account_color()

        overlay = Gtk.Overlay()
        overlay.add(self._account_box)
        overlay.add_overlay(self._unread_label)

        self.add(overlay)
        self.show_all()

    def _on_account_label_changed(self, value: str, *args: Any) -> None:
        self._account_box.set_tooltip_text(
            _('Account: %s') % value)

    def _set_account_color(self) -> None:
        context = self._account_color_bar.get_style_context()
        if self._account_class is not None:
            context.remove_class(self._account_class)

        self._account_class = app.css_config.get_dynamic_class(self.account)
        context.add_class(self._account_class)

    def set_unread_count(self, count: int) -> None:
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text('999+')
        self._unread_label.set_visible(bool(count))

    def _update_account_color_visibility(self, *args: Any) -> None:
        visible = len(app.settings.get_active_accounts()) > 1
        self._account_color_bar.set_visible(visible)


class AccountAvatar(Gtk.Image):
    def __init__(self, account: str) -> None:
        Gtk.Image.__init__(self)

        self._account = account

        jid = app.get_jid_from_account(self._account)
        self._client = app.get_client(self._account)

        self._client.connect_signal('state-changed', self._on_event)

        self._contact = self._client.get_module('Contacts').get_contact(jid)
        self._contact.connect('avatar-update', self._on_event)
        self._contact.connect('presence-update', self._on_event)

        self.connect('destroy', self._on_destroy)
        self._update_image()

    def _on_event(self, *args: Any) -> None:
        self._update_image()

    def _update_image(self) -> None:
        status = get_client_status(self._account)
        surface = app.app.avatar_storage.get_surface(
            self._contact,
            AvatarSize.ACCOUNT_SIDE_BAR,
            self.get_scale_factor(),
            status)
        self.set_from_surface(surface)

    def _on_destroy(self, _widget: Gtk.Image) -> None:
        self._contact.disconnect_all_from_obj(self)
        self._client.disconnect_all_from_obj(self)
        app.check_finalize(self)
