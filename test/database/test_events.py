# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from nbxmpp.protocol import JID

from gajim.common import app  # type: ignore # noqa: F401
from gajim.common import events
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.storage.events.storage import EventStorage
from gajim.common.util.datetime import utc_now


class EventsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._event_storage = EventStorage()
        self._event_storage.init()

        self._account = "testacc1"

        self._group_chat_contact = MagicMock(spec_set=GroupchatContact)
        self._group_chat_contact.account = self._account
        self._group_chat_contact.jid = JID.from_string("groupchat@example.org")

    def test_insert_muc_room_destroyed(self) -> None:
        event_data = events.MUCRoomDestroyed(
            timestamp=utc_now(),
            reason="Reason",
            alternate=JID.from_string("some-alternate@example.org"),
        )

        self._event_storage.store(self._group_chat_contact, event_data)

        events_list = self._event_storage.load(
            self._group_chat_contact, True, utc_now().timestamp(), 1
        )
        first_event = events_list[0]
        assert isinstance(first_event, events.MUCRoomDestroyed)
        self.assertEqual(
            first_event.alternate, JID.from_string("some-alternate@example.org")
        )


if __name__ == "__main__":
    unittest.main()
