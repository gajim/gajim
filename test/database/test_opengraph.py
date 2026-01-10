# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest
from datetime import datetime
from datetime import UTC

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import OpenGraph
from gajim.common.storage.archive.storage import MessageArchiveStorage


class OpenGraphTest(unittest.TestCase):
    def setUp(self) -> None:
        self._archive = MessageArchiveStorage(in_memory=True)
        self._archive.init()

        self._account = "testacc1"
        self._account_jid = JID.from_string("user@domain.org")
        self._remote_jid = JID.from_string("remote@jid.org")
        self._occupant_id = "occupantid1"
        self._init_settings()

    def tearDown(self) -> None:
        self._archive.shutdown()

    def _init_settings(self) -> None:
        app.settings = Settings(in_memory=True)
        app.settings.init()
        app.settings.add_account("testacc1")
        app.settings.set_account_setting("testacc1", "address", "user@domain.org")

    def test_insert_opengraph(self):
        og_data1 = OpenGraph(
            url="http://testurl1",
            title="Page Title",
            description="Page Description",
            image="https://link.to.example.com/image.png",
            type="website",
            site_name="Some Website",
        )

        og_data2 = OpenGraph(
            url="http://testurl2",
            title="Page Title2",
            description="Page Description2",
            image="https://link.to.example.com/image2.png",
            type="website2",
            site_name="Some Website2",
        )

        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.now(UTC),
            state=MessageState.ACKNOWLEDGED,
            resource="res",
            text="Some Message",
            id="messageid1",
            stanza_id=get_uuid(),
            occupant_=None,
            og=[og_data1, og_data2],
        )

        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None

        self.assertTrue(len(message.og), 2)

        og1 = message.og[0]
        og2 = message.og[1]

        self.assertEqual(og1.url, "http://testurl1")
        self.assertEqual(og1.type, "website")

        self.assertEqual(og2.url, "http://testurl2")
        self.assertEqual(og2.type, "website2")


if __name__ == "__main__":
    unittest.main()
