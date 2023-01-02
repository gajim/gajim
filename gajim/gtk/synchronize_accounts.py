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

from .builder import get_builder
from .dialogs import ErrorDialog
from .util import get_app_window


class SynchronizeAccounts(Gtk.ApplicationWindow):
    def __init__(self, account: str) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_default_size(400, 550)
        self.set_resizable(True)
        self.set_title(_('Synchronize Accounts'))
        self.set_transient_for(get_app_window('AccountsWindow'))

        if not app.account_is_available(account):
            ErrorDialog(
                _('You are not connected to the server'),
                _('You cannot synchronize with an account unless it is '
                  'connected.'))
            raise GajimGeneralException('You are not connected to the server')

        self.account = account
        self._local_client = app.get_client(account)

        self._remote_account = None
        self._remote_client = None

        self._ui = get_builder('synchronize_accounts.ui')
        self.add(self._ui.stack)

        # Accounts
        model = Gtk.ListStore(str, str, bool)
        self._ui.accounts_treeview.set_model(model)
        renderer = Gtk.CellRendererText()
        self._ui.accounts_treeview.insert_column_with_attributes(
            -1, _('Name'), renderer, text=0)
        renderer = Gtk.CellRendererText()
        self._ui.accounts_treeview.insert_column_with_attributes(
            -1, _('Server'), renderer, text=1)

        # Contacts
        model = Gtk.ListStore(bool, str)
        self._ui.contacts_treeview.set_model(model)
        # columns
        renderer1 = Gtk.CellRendererToggle()
        renderer1.set_property('activatable', True)
        renderer1.connect('toggled', self._on_sync_toggled)
        self._ui.contacts_treeview.insert_column_with_attributes(
            -1, _('Synchronise'), renderer1, active=0)
        renderer2 = Gtk.CellRendererText()
        self._ui.contacts_treeview.insert_column_with_attributes(
            -1, _('Name'), renderer2, text=1)

        self._ui.connect_signals(self)
        self.connect('key-press-event', self._on_key_press)

        self._init_accounts()

        self.show_all()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _init_accounts(self) -> None:
        '''
        Initialize listStore with existing accounts
        '''
        model = self._ui.accounts_treeview.get_model()
        assert isinstance(model, Gtk.ListStore)
        model.clear()
        for remote_account in app.settings.get_active_accounts():
            if remote_account == self.account:
                # Do not show the account we're sync'ing
                continue
            iter_ = model.append()
            model.set(
                iter_,
                {0: remote_account,
                 1: app.get_hostname_from_account(remote_account)})

    def _on_next_clicked(self, _button: Gtk.Button) -> None:
        selection = self._ui.accounts_treeview.get_selection()
        (model, iter_) = selection.get_selected()
        if not iter_:
            return

        self._remote_account = model.get_value(iter_, 0)
        if not app.account_is_available(self._remote_account):
            ErrorDialog(
                _('This account is not connected to the server'),
                _('You cannot synchronize with an account unless it is '
                  'connected.'))
            return

        self._remote_client = app.get_client(self._remote_account)
        self._init_contacts()
        self._ui.stack.set_visible_child_full(
            'contacts', Gtk.StackTransitionType.SLIDE_LEFT)

    def _on_back_clicked(self, _button: Gtk.Button) -> None:
        self._ui.stack.set_visible_child_full(
            'accounts', Gtk.StackTransitionType.SLIDE_RIGHT)

    def _init_contacts(self):
        model = self._ui.contacts_treeview.get_model()
        assert isinstance(model, Gtk.ListStore)
        model.clear()

        # recover local contacts
        local_jid_list: list[str] = []
        for contact in self._local_client.get_module('Roster').iter_contacts():
            local_jid_list.append(str(contact.jid))

        remote_jid_list: list[str] = []
        assert self._remote_client is not None
        for contact in self._remote_client.get_module('Roster').iter_contacts():
            remote_jid_list.append(str(contact.jid))

        for remote_jid in remote_jid_list:
            if remote_jid not in local_jid_list:
                iter_ = model.append()
                model.set(
                    iter_,
                    {0: True,
                     1: remote_jid})

    def _on_sync_toggled(self, cell: Gtk.CellRendererToggle, path: str) -> None:
        model = self._ui.contacts_treeview.get_model()
        assert isinstance(model, Gtk.ListStore)
        iter_ = model.get_iter(path)
        model[iter_][0] = not cell.get_active()

    def _on_sync_clicked(self, _button: Gtk.Button) -> None:
        assert self._remote_account is not None
        assert self._remote_client is not None
        model = self._ui.contacts_treeview.get_model()
        assert isinstance(model, Gtk.ListStore)
        iter_ = model.get_iter_first()
        while iter_:
            if model[iter_][0]:
                # it is selected
                remote_jid = model[iter_][1]
                hostname = app.get_hostname_from_account(self._remote_account)
                message = _('I’m synchronizing my contacts from my account at '
                            '"%s". Could you please add this address to your '
                            'contact list?' % hostname)
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
        self.destroy()
