# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import typing

from unittest.mock import MagicMock

from gajim.common import app

from gajim.gtk.groupchat_creation import CreateGroupchatWindow

from . import util

accounts: list[list[str]] = []
for i in range(2):
    accounts.append(
        [f"testacc{i}", f"Account {i}"],
    )

util.init_settings()

app.get_enabled_accounts_with_labels = MagicMock(return_value=accounts)
app.get_number_of_connected_accounts = MagicMock(return_value=2)
app.account_is_available = MagicMock(return_value=True)


class TestModule(MagicMock):
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        super().__init__()
        self.service_jid = "conference.test.example"


class TestClient(MagicMock):
    def __init__(self):
        super().__init__()

    def get_module(self) -> TestModule:
        return TestModule()


app.get_client = MagicMock(return_value=TestClient)


window = CreateGroupchatWindow(accounts[0][0])
window.show()

util.run_app()
