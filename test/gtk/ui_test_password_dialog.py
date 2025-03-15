# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from unittest.mock import MagicMock

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.events import PasswordRequired

from gajim.gtk.password_dialog import PasswordDialog

from . import util

ACCOUNT = "test"
FROM_JID = "contact@example.org"

util.init_settings()
app.settings.add_account(ACCOUNT)
app.settings.set_account_setting(ACCOUNT, "account_label", "Test")


def on_password(*args: Any) -> None:
    pass


class TestClient:
    def __init__(self, account: str) -> None:
        self.account = account

    def get_own_jid(self) -> JID:
        return JID.from_string(FROM_JID)


app.get_client = MagicMock(side_effect=TestClient)
app.get_account_label = MagicMock(return_value="Test Account")

client = app.get_client(ACCOUNT)

event = PasswordRequired(client, on_password)

window = PasswordDialog(ACCOUNT, event)
window.show()

util.run_app()
