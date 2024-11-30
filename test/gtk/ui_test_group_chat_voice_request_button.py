# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock

from gi.repository import Gtk
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.groupchat_voice_requests_button import VoiceRequestsButton
from gajim.gtk.widgets import GajimAppWindow

from . import util

ACCOUNT = "testacc1"
FROM_JID = "groupchat@conference.example.org"


class TestGroupChatVoiceRequestButton(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
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


app.get_client = MagicMock()

window = TestGroupChatVoiceRequestButton()
window.show()

util.run_app()
