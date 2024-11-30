# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from unittest.mock import MagicMock

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.call_manager import CallManager
from gajim.common.const import AvatarSize
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ResourceContact

from gajim.gtk.avatar import convert_surface_to_texture
from gajim.gtk.avatar import generate_default_avatar
from gajim.gtk.call_window import CallWindow

from . import util

ACCOUNT = "testacc1"
BARE_JID = JID.from_string("contact@test.tld")
RESOURCE_JID = JID.from_string("contact@test.tld/test")


class TestContactsModule:
    def __init__(self) -> None:
        pass

    @staticmethod
    def get_contact(jid: str | JID) -> BareContact | ResourceContact:
        if jid == RESOURCE_JID:
            contact = MagicMock(spec_set=ResourceContact)
            contact.jid = RESOURCE_JID
        else:
            contact = MagicMock(spec_set=BareContact)
            contact.jid = BARE_JID
            contact.name = "Test Contact"
            avatar = convert_surface_to_texture(
                generate_default_avatar("T", (0.2, 0.1, 0.7), AvatarSize.CALL_BIG, 1)
            )
            contact.get_avatar = MagicMock(return_value=avatar)

        contact.account = ACCOUNT
        contact.is_groupchat = False

        return contact


class TestClient:
    def __init__(self, account: str) -> None:
        self.account = account

    def get_module(self, module: str) -> Any:
        if module == "Contacts":
            return TestContactsModule()
        return MagicMock()


app.get_client = MagicMock(side_effect=TestClient)
app.call_manager = CallManager()

window = CallWindow(ACCOUNT, RESOURCE_JID)

# Enable popover buttons for debugging
window._ui.audio_buttons_box.set_sensitive(True)  # pyright: ignore
window.show()

util.run_app()
