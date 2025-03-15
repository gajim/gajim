# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from functools import partial
from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.client import Client as NBXMPPClient

from gajim.common import app

from gajim.gtk.account_wizard import AccountWizard
from gajim.gtk.account_wizard import Success

from . import util

ACCOUNT = "testacc1"


def _on_login_successful(
    self: AccountWizard, client: NBXMPPClient, _signal_name: str
) -> None:
    account = self._generate_account_name(client.domain)  # type: ignore
    app.settings.add_account(account)
    self.get_page("success").set_account(account)
    self.show_page("success", Gtk.StackTransitionType.SLIDE_LEFT)
    self._disconnect()  # type: ignore


def _save_config(self: Success) -> None:
    assert self._account is not None  # type: ignore
    app.settings.set_account_setting(self._account, "account_color", self._color)  # type: ignore
    if self._label:  # type: ignore
        app.settings.set_account_setting(self._account, "account_label", self._label)  # type: ignore
    app.css_config.refresh()


util.init_settings()

app.get_client = MagicMock()

app.get_jid_from_account = MagicMock(return_value="testjid")

app.cert_store = MagicMock()

app.css_config = MagicMock()
app.css_config.prefer_dark = MagicMock(return_value=False)

window = AccountWizard()
window._on_login_successful = partial(_on_login_successful, window)  # type: ignore

success_page = window.get_page("success")
success_page._save_config = partial(_save_config, success_page)  # type: ignore
window.show()

util.run_app()
