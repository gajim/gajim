# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest
from datetime import datetime
from datetime import UTC
from test.database.util import mk_utc_dt

from nbxmpp.protocol import JID
from sqlalchemy import select

from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import Occupant
from gajim.common.storage.archive.models import Retraction
from gajim.common.storage.archive.storage import MessageArchiveStorage


class RetractionTest(unittest.TestCase):
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

    def test_insert_retraction(self) -> None:
        # Test unique index without occupant id

        uuid = get_uuid()
        retraction_data = Retraction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id=uuid,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, UTC),
        )

        pk = self._archive.insert_row(retraction_data, ignore_on_conflict=True)
        self.assertNotEqual(pk, -1)

        with self._archive.get_session() as s:
            retraction = s.scalar(select(Retraction).where(Retraction.pk == pk))
        assert retraction is not None

        self.assertEqual(retraction.timestamp, datetime.fromtimestamp(0, UTC))
        self.assertEqual(retraction.id, uuid)
        self.assertEqual(retraction.occupant, None)

        retraction_data = Retraction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id=uuid,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(1, UTC),
        )

        pk = self._archive.insert_row(retraction_data, ignore_on_conflict=True)
        self.assertEqual(pk, -1)

        # Test unique index with occupant id

        occupant_data = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id="occupantid1",
            nickname="nickname1",
            updated_at=mk_utc_dt(0),
        )

        uuid = get_uuid()
        retraction_data = Retraction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data,
            id=uuid,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, UTC),
        )

        pk = self._archive.insert_row(retraction_data, ignore_on_conflict=True)
        self.assertNotEqual(pk, -1)

        with self._archive.get_session() as s:
            retraction = s.scalar(select(Retraction).where(Retraction.pk == pk))
        assert retraction is not None
        assert retraction.occupant is not None

        self.assertEqual(retraction.timestamp, datetime.fromtimestamp(0, UTC))
        self.assertEqual(retraction.id, uuid)
        self.assertEqual(retraction.occupant.id, "occupantid1")

        retraction_data = Retraction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data,
            id=uuid,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(1, UTC),
        )

        pk = self._archive.insert_row(retraction_data, ignore_on_conflict=True)
        self.assertEqual(pk, -1)

    def test_retraction_join(self) -> None:
        uuid = get_uuid()
        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            resource="someres1",
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.now(UTC),
            state=MessageState.ACKNOWLEDGED,
            id="1",
            stanza_id=uuid,
            text="message",
        )

        pk = self._archive.insert_object(message_data)

        retraction_data = Retraction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id="1",
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, UTC),
        )

        self._archive.insert_row(retraction_data, ignore_on_conflict=True)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.retraction is not None
        self.assertEqual(message.retraction.timestamp, datetime.fromtimestamp(0, UTC))
        self.assertEqual(message.retraction.id, "1")
        self.assertEqual(message.retraction.occupant, None)

        # Test incorrect direction does not get joined

        uuid = get_uuid()
        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            resource="someres1",
            type=MessageType.CHAT,
            direction=ChatDirection.OUTGOING,
            timestamp=datetime.now(UTC),
            state=MessageState.ACKNOWLEDGED,
            id="2",
            stanza_id=uuid,
            text="message",
        )

        pk = self._archive.insert_object(message_data)

        retraction_data = Retraction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id="2",
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, UTC),
        )

        self._archive.insert_row(retraction_data, ignore_on_conflict=True)

        message = self._archive.get_message_with_pk(pk)
        assert message is not None
        self.assertIsNone(message.retraction)

    def test_retractions_join_groupchat(self) -> None:
        occupant_data1 = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id="occupantid1",
            nickname="nickname1",
            updated_at=mk_utc_dt(0),
        )

        occupant_data2 = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id="occupantid2",
            nickname="nickname2",
            updated_at=mk_utc_dt(0),
        )

        uuid1 = get_uuid()
        message_data1 = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            resource="someres1",
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.now(UTC),
            state=MessageState.ACKNOWLEDGED,
            id="1",
            stanza_id=uuid1,
            text="message",
            occupant_=occupant_data1,
        )

        uuid2 = get_uuid()
        message_data2 = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            resource="someres1",
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.now(UTC),
            state=MessageState.ACKNOWLEDGED,
            id="1",
            stanza_id=uuid2,
            text="message",
            occupant_=occupant_data2,
        )

        pk1 = self._archive.insert_object(message_data1)
        pk2 = self._archive.insert_object(message_data2)

        retraction_data1 = Retraction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data1,
            id=uuid1,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, UTC),
        )

        retraction_data2 = Retraction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data2,
            id=uuid2,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, UTC),
        )

        self._archive.insert_row(retraction_data1, ignore_on_conflict=True)
        self._archive.insert_row(retraction_data2, ignore_on_conflict=True)

        message1 = self._archive.get_message_with_pk(pk1)
        message2 = self._archive.get_message_with_pk(pk2)

        assert message1 is not None
        assert message1.retraction is not None
        assert message1.retraction.occupant is not None
        self.assertEqual(message1.retraction.timestamp, datetime.fromtimestamp(0, UTC))
        self.assertEqual(message1.retraction.id, uuid1)
        self.assertEqual(message1.retraction.occupant.id, "occupantid1")

        assert message2 is not None
        assert message2.retraction is not None
        assert message2.retraction.occupant is not None
        self.assertEqual(message2.retraction.timestamp, datetime.fromtimestamp(0, UTC))
        self.assertEqual(message2.retraction.id, uuid2)
        self.assertEqual(message2.retraction.occupant.id, "occupantid2")


if __name__ == "__main__":
    unittest.main()
