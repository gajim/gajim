# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import logging

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common import passwords
from gajim.common.events import PasswordRequired
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder

log = logging.getLogger('gajim.gtk.pass_dialog')


class PasswordDialog(Gtk.ApplicationWindow):
    def __init__(self, event: PasswordRequired) -> None:
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

        self.account = event.client.account
        self._client = app.get_client(event.client.account)
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

        self._ui.header.set_text(_('Password Required'))
        self._ui.message_label.set_text(
            _('Please enter your password for\n'
              '%(jid)s\n(Account: %(account)s)') % {
                'jid': own_jid,
                'account': account_name})
        self._ui.save_pass_checkbutton.show()

        is_keyring_available = passwords.is_keyring_available()
        self._ui.save_pass_checkbutton.set_sensitive(
            not app.settings.get('use_keyring') or
            is_keyring_available)
        if not is_keyring_available:
            self._ui.keyring_hint.show()

    def _on_ok(self, _button: Gtk.Button) -> None:
        password = self._ui.pass_entry.get_text()
        savepass = self._ui.save_pass_checkbutton.get_active()

        app.settings.set_account_setting(self.account, 'savepass', savepass)
        passwords.save_password(self.account, password)

        self._event.on_password()
        self.destroy()

    def _on_cancel(self, _button: Gtk.Button) -> None:
        self.destroy()
