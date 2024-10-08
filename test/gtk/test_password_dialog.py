# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from unittest.mock import MagicMock

from gajim.common import app
from gajim.common.events import PasswordRequired
from gajim.common.settings import Settings

from gajim.gtk.password_dialog import PasswordDialog

from . import util


def on_password(*args: Any) -> None:
    print(args)


ACCOUNT = 'test'

app.settings = Settings(in_memory=True)
app.settings.init()
app.settings.add_account(ACCOUNT)
app.settings.set_account_setting(ACCOUNT, 'account_label', 'Test')
app.get_client = MagicMock()

client = MagicMock()
client.account = ACCOUNT
event = PasswordRequired(client, on_password)

window = PasswordDialog(event)
window.show()

util.run_app()
