# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.protocol import JID
from nbxmpp.structs import VoiceRequest

from gajim.common import app
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.groupchat_voice_requests_button import VoiceRequestsButton
from gajim.gtk.window import GajimAppWindow

from . import util

ACCOUNT = "testacc1"
FROM_JID = "groupchat@conference.example.org"


class TestMUCModule:
    def __init__(self, account: str) -> None:
        self._account = account

        self._requests: list[VoiceRequest] = []
        for item in range(15):
            self._requests.append(
                VoiceRequest(
                    JID.from_string(f"user{item}@conference.example.org/user"),
                    f"Nick #{item}",
                    None,
                )
            )
        self._requests.append(
            VoiceRequest(
                JID.from_string(
                    "extralongjid_with_many_characters@conference.example.org/with_resource"
                ),
                "Nickname with many characters very very looooooooong",
                None,
            )
        )

    def get_voice_requests(self, _contact: GroupchatContact) -> list[VoiceRequest]:
        return self._requests

    def approve_voice_request(
        self, _contact: GroupchatContact, request: VoiceRequest
    ) -> None:
        self._requests.remove(request)

    def decline_voice_request(
        self, _contact: GroupchatContact, request: VoiceRequest
    ) -> None:
        self._requests.remove(request)


class TestClient:
    def __init__(self, account: str) -> None:
        self._account = account

        self._muc_module = TestMUCModule(self._account)

    def get_module(self, module: str) -> Any:
        if module == "MUC":
            return self._muc_module
        return MagicMock()


class TestGroupChatVoiceRequestButton(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
            add_window_padding=True,
            header_bar=True,
        )

        self._box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )
        self.set_child(self._box)

        button = VoiceRequestsButton()
        self._box.append(button)

        contact = self._get_contact()
        button.switch_contact(contact)

    def _get_contact(self) -> GroupchatContact:
        contact = MagicMock(spec_set=GroupchatContact)
        contact.account = ACCOUNT
        contact.jid = JID.from_string(FROM_JID)
        contact.name = "Test Contact"
        contact.is_groupchat = True
        return contact

    def _cleanup(self) -> None:
        pass


test_client = TestClient(ACCOUNT)
app.get_client = MagicMock(return_value=test_client)

util.init_settings()

window = TestGroupChatVoiceRequestButton()
window.show()

util.run_app()
