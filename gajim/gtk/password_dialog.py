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

from gi.repository import Gtk
from gi.repository import Gdk

from gajim.common import app
from gajim.common.events import PasswordRequired
from gajim.common.i18n import _
from gajim.common.passwords import save_password
from gajim.common.passwords import KEYRING_AVAILABLE

from .builder import get_builder

log = logging.getLogger('gajim.gui.pass_dialog')


class PasswordDialog(Gtk.ApplicationWindow):
    def __init__(self, account: str, event: PasswordRequired) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(400, -1)
        self.set_show_menubar(False)
        self.set_name('PasswordDialog')
        self.set_title(_('Password Required'))

        self._ui = get_builder('password_dialog.ui')
        self.add(self._ui.pass_box)

        self.account = account
        self._client = app.get_client(account)
        self._event = event

        self.connect('key-press-event', self._on_key_press)
        self._ui.connect_signals(self)
        self.show_all()
        self._ui.ok_button.grab_default()

        self._process_event()

    def _on_key_press(self, _widget: Gtk.Widget, event: Gdk.EventKey) -> None:
        if event.keyval == Gdk.KEY_Escape:
            self.destroy()

    def _process_event(self) -> None:
        own_jid = self._client.get_own_jid().bare
        account_name = app.settings.get_account_setting(
            self.account, 'name')

        if self._event.name == 'password-required':
            self._ui.header.set_text(_('Password Required'))
            self._ui.message_label.set_text(
                _('Please enter your password for\n'
                  '%(jid)s\n(Account: %(account)s)') % {
                    'jid': own_jid,
                    'account': account_name})
            self._ui.save_pass_checkbutton.show()
            self._ui.save_pass_checkbutton.set_sensitive(
                not app.settings.get('use_keyring') or KEYRING_AVAILABLE)
            if not KEYRING_AVAILABLE:
                self._ui.keyring_hint.show()

        if self._event.name == 'client-cert-passphrase':
            self._ui.header.set_text(_('Certificate Password Required'))
            self._ui.message_label.set_text(
                _('Please enter your certificate password for '
                  '%(jid)s (%(account)s)') % {
                    'jid': own_jid,
                    'account': account_name})

    def _on_ok(self, _button: Gtk.Button) -> None:
        password = self._ui.pass_entry.get_text()

        if self._event.name == 'password-required':
            app.settings.set_account_setting(
                self.account,
                'savepass',
                self._ui.save_pass_checkbutton.get_active())
            save_password(self.account, password)
            self._event.on_password(password)
            self.destroy()

        if self._event.name == 'client-cert-passphrase':
            self._event.conn.on_client_cert_passphrase(
                password,
                self._event.con,
                self._event.port,
                self._event.secure_tuple)
            self.destroy()

    def _on_cancel(self, _button: Gtk.Button) -> None:
        if self._event.name == 'client-cert-passphrase':
            self._event.conn.on_client_cert_passphrase(
                '',
                self._event.con,
                self._event.port,
                self._event.secure_tuple)

        self.destroy()
