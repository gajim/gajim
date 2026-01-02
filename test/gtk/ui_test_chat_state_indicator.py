# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock

from gi.repository import GLib
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.const import Chatstate

from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.util.user_strings import chatstate_to_string

from gajim.gtk.chat_state_indicator import ChatStateIndicator
from gajim.gtk.window import GajimAppWindow

from . import util

ACCOUNT = "account"


class TestChatStateIndicator(GajimAppWindow):
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

        box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )
        self.set_child(box)

        self._chat_state_indicator = ChatStateIndicator()
        box.append(self._chat_state_indicator)

        self._participants_count = 3
        contact = self._get_groupchat_contact()
        self._chat_state_indicator.switch_contact(contact)

        GLib.timeout_add_seconds(3, self._decrease_participants_count)
        GLib.timeout_add_seconds(3, self._chat_state_indicator.switch_contact, contact)

        GLib.timeout_add_seconds(6, self._decrease_participants_count)
        GLib.timeout_add_seconds(6, self._chat_state_indicator.switch_contact, contact)

        contact = self._get_bare_contact()
        GLib.timeout_add_seconds(9, self._chat_state_indicator.switch_contact, contact)

        contact = self._get_bare_contact(composing=False)
        GLib.timeout_add_seconds(12, self._chat_state_indicator.switch_contact, contact)

    def _decrease_participants_count(self) -> None:
        self._participants_count -= 1

    def _get_bare_contact(self, composing: bool = True) -> BareContact:
        contact = MagicMock(spec_set=BareContact)
        contact.connect = MagicMock()
        contact.account = ACCOUNT
        contact.jid = JID.from_string("user@example.org")
        contact.name = "Test Contact"
        if composing:
            contact.chatstate = Chatstate.COMPOSING
            contact.chatstate_string = chatstate_to_string(Chatstate.COMPOSING)
        else:
            contact.chatstate = Chatstate.PAUSED
            contact.chatstate_string = chatstate_to_string(Chatstate.PAUSED)
        return contact

    def _get_groupchat_contact(self) -> GroupchatContact:
        contact = MagicMock(spec_set=GroupchatContact)
        contact.connect = MagicMock()
        contact.account = ACCOUNT
        contact.jid = JID.from_string("groupchat@conference.example.org")
        contact.name = "Test Group Chat"
        contact.is_groupchat = True
        contact.get_composers = MagicMock(side_effect=self._get_composers)
        return contact

    def _get_groupchat_participant(self, name: str) -> GroupchatParticipant:
        contact = MagicMock(spec_set=GroupchatParticipant)
        contact.connect = MagicMock()
        contact.account = ACCOUNT
        contact.jid = JID.from_string(f"groupchat@conferece.example.org/{name}")
        contact.name = name
        return contact

    def _get_composers(self) -> list[GroupchatParticipant]:
        participants: list[GroupchatParticipant] = []
        for name in [f"user{count + 1}" for count in range(self._participants_count)]:
            participants.append(self._get_groupchat_participant(name))
        return participants

    def _cleanup(self) -> None:
        pass


util.init_settings()

window = TestChatStateIndicator()
window.show()

util.run_app()
