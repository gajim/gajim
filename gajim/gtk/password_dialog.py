# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import logging

from gi.repository import Gtk

from gajim.common import app
from gajim.common import passwords
from gajim.common.events import PasswordRequired
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.window import GajimAppWindow

log = logging.getLogger("gajim.gtk.password_dialog")


class PasswordDialog(GajimAppWindow):
    def __init__(self, account: str, event: PasswordRequired) -> None:
        GajimAppWindow.__init__(
            self,
            name="PasswordDialog",
            title=_("Password Required"),
            default_width=400,
            add_window_padding=True,
            header_bar=True,
        )

        self._ui = get_builder("password_dialog.ui")
        self.set_child(self._ui.pass_box)

        self._connect(self._ui.cancel_button, "clicked", self._on_cancel)
        self._connect(self._ui.ok_button, "clicked", self._on_ok)

        self.account = account
        self._client = app.get_client(event.client.account)
        self._event = event

        self.set_default_widget(self._ui.ok_button)

        self._process_event()

    def _cleanup(self) -> None:
        pass

    def _process_event(self) -> None:
        own_jid = self._client.get_own_jid().bare
        account_label = app.get_account_label(self.account)

        self._ui.header.set_text(_("Password Required"))
        self._ui.message_label.set_text(
            _("Please enter your password for\n%(jid)s\n(Account: %(account)s)")
            % {"jid": own_jid, "account": account_label}
        )
        self._ui.save_pass_checkbutton.set_visible(True)

        is_keyring_available = passwords.is_keyring_available()
        self._ui.save_pass_checkbutton.set_sensitive(
            not app.settings.get("use_keyring") or is_keyring_available
        )
        if not is_keyring_available:
            self._ui.keyring_hint.set_visible(True)

    def _on_ok(self, _button: Gtk.Button) -> None:
        password = self._ui.pass_entry.get_text()
        savepass = self._ui.save_pass_checkbutton.get_active()

        app.settings.set_account_setting(self.account, "savepass", savepass)
        passwords.save_password(self.account, password)

        self._event.on_password()
        self.close()

    def _on_cancel(self, _button: Gtk.Button) -> None:
        self.close()
