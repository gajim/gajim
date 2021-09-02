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

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.exceptions import GajimGeneralException
from gajim.common.i18n import _

from .dialogs import ErrorDialog
from .util import get_app_window
from .util import get_builder


class SynchroniseSelectAccountDialog:
    def __init__(self, account):
        # 'account' can be None if we are about to create our first one
        if not app.account_is_available(account):
            ErrorDialog(
                _('You are not connected to the server'),
                _('You cannot synchronize with an account unless it is '
                  'connected.'))
            raise GajimGeneralException('You are not connected to the server')
        self.account = account
        self.xml = get_builder('synchronise_select_account_dialog.ui')
        self.dialog = self.xml.get_object('synchronise_select_account_dialog')
        self.dialog.set_transient_for(get_app_window('AccountsWindow'))
        self.accounts_treeview = self.xml.get_object('accounts_treeview')
        model = Gtk.ListStore(str, str, bool)
        self.accounts_treeview.set_model(model)
        # columns
        renderer = Gtk.CellRendererText()
        self.accounts_treeview.insert_column_with_attributes(
            -1, _('Name'), renderer, text=0)
        renderer = Gtk.CellRendererText()
        self.accounts_treeview.insert_column_with_attributes(
            -1, _('Server'), renderer, text=1)

        self.xml.connect_signals(self)
        self.init_accounts()
        self.dialog.show_all()

    def on_accounts_window_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def init_accounts(self):
        """
        Initialize listStore with existing accounts
        """
        model = self.accounts_treeview.get_model()
        model.clear()
        for remote_account in app.connections:
            if remote_account == self.account:
                # Do not show the account we're sync'ing
                continue
            iter_ = model.append()
            model.set(
                iter_,
                0,
                remote_account,
                1,
                app.get_hostname_from_account(remote_account))

    def on_cancel_button_clicked(self, _widget):
        self.dialog.destroy()

    def on_ok_button_clicked(self, _widget):
        sel = self.accounts_treeview.get_selection()
        (model, iter_) = sel.get_selected()
        if not iter_:
            return
        remote_account = model.get_value(iter_, 0)

        if not app.account_is_available(remote_account):
            ErrorDialog(
                _('This account is not connected to the server'),
                _('You cannot synchronize with an account unless it is '
                  'connected.'))
            return

        try:
            SynchroniseSelectContactsDialog(self.account, remote_account)
        except GajimGeneralException:
            # if we showed ErrorDialog, there will not be dialog instance
            return
        self.dialog.destroy()

    @staticmethod
    def on_destroy(_widget):
        del app.interface.instances['import_contacts']


class SynchroniseSelectContactsDialog:
    def __init__(self, local_account, remote_account):
        self._remote_account = remote_account

        self._local_client = app.get_client(local_account)
        self._remote_client = app.get_client(remote_account)

        self.xml = get_builder('synchronise_select_contacts_dialog.ui')
        self.dialog = self.xml.get_object('synchronise_select_contacts_dialog')
        self.contacts_treeview = self.xml.get_object('contacts_treeview')
        model = Gtk.ListStore(bool, str)
        self.contacts_treeview.set_model(model)
        # columns
        renderer1 = Gtk.CellRendererToggle()
        renderer1.set_property('activatable', True)
        renderer1.connect('toggled', self.toggled_callback)
        self.contacts_treeview.insert_column_with_attributes(
            -1, _('Synchronise'), renderer1, active=0)
        renderer2 = Gtk.CellRendererText()
        self.contacts_treeview.insert_column_with_attributes(
            -1, _('Name'), renderer2, text=1)

        self.xml.connect_signals(self)
        self.init_contacts()
        self.dialog.show_all()

    def toggled_callback(self, cell, path):
        model = self.contacts_treeview.get_model()
        iter_ = model.get_iter(path)
        model[iter_][0] = not cell.get_active()

    def on_contacts_window_key_press_event(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.window.destroy()

    def init_contacts(self):
        """
        Initialize listStore with existing accounts
        """
        model = self.contacts_treeview.get_model()
        model.clear()

        # recover local contacts
        local_jid_list = []
        for contact in self._local_client.get_module('Roster').iter_contacts():
            local_jid_list.append(str(contact.jid))

        remote_jid_list = []
        for contact in self._remote_client.get_module('Roster').iter_contacts():
            remote_jid_list.append(str(contact.jid))

        for remote_jid in remote_jid_list:
            if remote_jid not in local_jid_list:
                iter_ = model.append()
                model.set(iter_, 0, True, 1, remote_jid)

    def on_cancel_button_clicked(self, _widget):
        self.dialog.destroy()

    def on_ok_button_clicked(self, _widget):
        model = self.contacts_treeview.get_model()
        iter_ = model.get_iter_first()
        while iter_:
            if model[iter_][0]:
                # it is selected
                remote_jid = model[iter_][1]
                message = _('I’m synchronizing my contacts from my account at '
                            '"%s". Could you please add this address to your '
                            'contact list?' % app.get_hostname_from_account(
                                self._remote_account))
                remote_contact = self._remote_client.get_module(
                    'Contacts').get_contact(remote_jid)

                # keep same groups and same nickname
                self._local_client.get_module('Presence').subscribe(
                    remote_jid,
                    msg=message,
                    name=remote_contact.name,
                    groups=remote_contact.groups,
                    auto_auth=True)

            iter_ = model.iter_next(iter_)
        self.dialog.destroy()
