# Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005 Alex Podaras <bigpod AT gmail.com>
#                    Stéphan Kochen <stephan AT kochen.nl>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
# Copyright (C) 2006-2007 Travis Shirk <travis AT pobox.com>
#                         Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 James Newton <redshodan AT gmail.com>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
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

from gi.repository import Gtk
from gi.repository import GObject

from gajim.common import app
from gajim.common.i18n import _

from gajim import dialogs

from gajim import gui_menu_builder

from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import ConfirmationDialogDoubleRadio
from gajim.gtk.dialogs import ErrorDialog
from gajim.gtk.util import get_builder


class FakeDataForm(Gtk.Table):
    """
    Class for forms that are in XML format <entry1>value1</entry1> infos in a
    table {entry1: value1}
    """

    def __init__(self, infos, selectable=False):
        GObject.GObject.__init__(self)
        self.infos = infos
        self.selectable = selectable
        self.entries = {}
        self._draw_table()

    def _draw_table(self):
        """
        Draw the table
        """
        nbrow = 0
        if 'instructions' in self.infos:
            nbrow = 1
            self.resize(rows=nbrow, columns=2)
            label = Gtk.Label(label=self.infos['instructions'])
            if self.selectable:
                label.set_selectable(True)
            self.attach(label, 0, 2, 0, 1, 0, 0, 0, 0)
        for name in self.infos.keys():
            if name in ('key', 'instructions', 'x', 'registered'):
                continue
            if not name:
                continue

            nbrow = nbrow + 1
            self.resize(rows=nbrow, columns=2)
            label = Gtk.Label(label=name.capitalize() + ':')
            self.attach(label, 0, 1, nbrow - 1, nbrow, 0, 0, 0, 0)
            entry = Gtk.Entry()
            entry.set_activates_default(True)
            if self.infos[name]:
                entry.set_text(self.infos[name])
            if name == 'password':
                entry.set_visibility(False)
            self.attach(entry, 1, 2, nbrow - 1, nbrow, 0, 0, 0, 0)
            self.entries[name] = entry
            if nbrow == 1:
                entry.grab_focus()

    def get_infos(self):
        for name in self.entries:
            self.infos[name] = self.entries[name].get_text()
        return self.infos

#---------- RemoveAccountWindow class -------------#
class RemoveAccountWindow:
    """
    Ask for removing from gajim only or from gajim and server too and do
    removing of the account given
    """

    def on_remove_account_window_destroy(self, widget):
        if self.account in app.interface.instances:
            del app.interface.instances[self.account]['remove_account']

    def on_cancel_button_clicked(self, widget):
        self.window.destroy()

    def __init__(self, account):
        self.account = account
        xml = get_builder('remove_account_window.ui')
        self.window = xml.get_object('remove_account_window')
        active_window = app.app.get_active_window()
        self.window.set_transient_for(active_window)
        self.remove_and_unregister_radiobutton = xml.get_object(
                'remove_and_unregister_radiobutton')
        self.window.set_title(_('Removing %s account') % self.account)
        xml.connect_signals(self)
        self.window.show_all()

    def on_remove_button_clicked(self, widget):
        def remove():
            if self.account in app.connections and \
            app.connections[self.account].connected and \
            not self.remove_and_unregister_radiobutton.get_active():
                # change status to offline only if we will not remove this JID from
                # server
                app.connections[self.account].change_status('offline', 'offline')
            if self.remove_and_unregister_radiobutton.get_active():
                if not self.account in app.connections:
                    ErrorDialog(
                        _('Account is disabled'),
                        _('To unregister from a server, account must be '
                        'enabled.'),
                        transient_for=self.window)
                    return
                if not app.connections[self.account].password:
                    def on_ok(passphrase, checked):
                        if passphrase == -1:
                            # We don't remove account cause we canceled pw window
                            return
                        app.connections[self.account].password = passphrase
                        app.connections[self.account].unregister_account(
                                self._on_remove_success)

                    dialogs.PassphraseDialog(
                            _('Password Required'),
                            _('Enter your password for account %s') % self.account,
                            _('Save password'), ok_handler=on_ok,
                            transient_for=self.window)
                    return
                app.connections[self.account].unregister_account(
                        self._on_remove_success)
            else:
                self._on_remove_success(True)

        if self.account in app.connections and \
        app.connections[self.account].connected:
            ConfirmationDialog(
                _('Account "%s" is connected to the server') % self.account,
                _('If you remove it, the connection will be lost.'),
                on_response_ok=remove,
                transient_for=self.window)
        else:
            remove()

    def on_remove_responce_ok(self, is_checked):
        if is_checked[0]:
            self._on_remove_success(True)

    def _on_remove_success(self, res):
        # action of unregistration has failed, we don't remove the account
        # Error message is send by connect_and_auth()
        if not res:
            ConfirmationDialogDoubleRadio(
                    _('Connection to server %s failed') % self.account,
                    _('What would you like to do?'),
                    _('Remove only from Gajim'),
                    _('Don\'t remove anything. I\'ll try again later'),
                    on_response_ok=self.on_remove_responce_ok, is_modal=False,
                    transient_for=self.window)
            return
        # Close all opened windows
        app.interface.roster.close_all(self.account, force=True)
        if self.account in app.connections:
            app.connections[self.account].disconnect(on_purpose=True)
            app.connections[self.account].cleanup()
            del app.connections[self.account]
        app.logger.remove_roster(app.get_jid_from_account(self.account))
        app.config.del_per('accounts', self.account)
        del app.interface.instances[self.account]
        if self.account in app.nicks:
            del app.interface.minimized_controls[self.account]
            del app.nicks[self.account]
            del app.block_signed_in_notifications[self.account]
            del app.groups[self.account]
            app.contacts.remove_account(self.account)
            del app.gc_connected[self.account]
            del app.automatic_rooms[self.account]
            del app.to_be_removed[self.account]
            del app.newly_added[self.account]
            del app.sleeper_state[self.account]
            del app.last_message_time[self.account]
            del app.status_before_autoaway[self.account]
            del app.gajim_optional_features[self.account]
            del app.caps_hash[self.account]
        if len(app.connections) >= 2: # Do not merge accounts if only one exists
            app.interface.roster.regroup = app.config.get('mergeaccounts')
        else:
            app.interface.roster.regroup = False
        app.interface.roster.setup_and_draw_roster()
        app.app.remove_account_actions(self.account)
        gui_menu_builder.build_accounts_menu()

        window = app.get_app_window('AccountsWindow')
        if window is not None:
            window.remove_account(self.account)
        self.window.destroy()
