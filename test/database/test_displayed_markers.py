from __future__ import annotations

import unittest
from datetime import datetime
from datetime import timezone

from nbxmpp.protocol import JID
from sqlalchemy.exc import IntegrityError

from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import DisplayedMarker
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import Occupant
from gajim.common.storage.archive.storage import MessageArchiveStorage


class DisplayedMarkersTest(unittest.TestCase):
    def setUp(self) -> None:
        self._archive = MessageArchiveStorage(in_memory=True)
        self._archive.init()

        self._account = 'testacc1'
        self._account_jid = JID.from_string('user@domain.org')
        self._remote_jid = JID.from_string('remote@jid.org')
        self._init_settings()

    def _init_settings(self) -> None:
        app.settings = Settings(in_memory=True)
        app.settings.init()
        app.settings.add_account('testacc1')
        app.settings.set_account_setting('testacc1', 'name', 'user')
        app.settings.set_account_setting('testacc1', 'hostname', 'domain.org')

    def test_markers_join(self):
        marker_data1 = DisplayedMarker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid1',
            timestamp=datetime.fromtimestamp(1, timezone.utc),
        )

        marker_data2 = DisplayedMarker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid1',
            timestamp=datetime.fromtimestamp(3, timezone.utc),
        )

        self._archive.insert_object(marker_data1)

        with self.assertRaises(IntegrityError):
            self._archive.insert_object(marker_data2, ignore_on_conflict=False)

        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.OUTGOING,
            timestamp=datetime.now(timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            resource='res',
            text='Some Message',
            id='messageid1',
            stanza_id=get_uuid(),
            occupant_=None,
        )

        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.markers

        self.assertTrue(len(message.markers), 1)

        self.assertEqual(
            message.markers[0].timestamp, datetime.fromtimestamp(1, timezone.utc)
        )

    def test_markers_join_groupchat(self):
        # Entries are stored per occupant

        occupant_data1 = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='occupantid1',
            nickname='nickname1',
            updated_at=datetime.fromtimestamp(0, timezone.utc),
        )

        occupant_data2 = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='occupantid2',
            nickname='nickname1',
            updated_at=datetime.fromtimestamp(0, timezone.utc),
        )

        uuid = get_uuid()

        marker_data1 = DisplayedMarker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data1,
            id=uuid,
            timestamp=datetime.fromtimestamp(1, timezone.utc),
        )

        marker_data2 = DisplayedMarker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data2,
            id=uuid,
            timestamp=datetime.fromtimestamp(2, timezone.utc),
        )

        marker_data3 = DisplayedMarker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data1,
            id=uuid,
            timestamp=datetime.fromtimestamp(4, timezone.utc),
        )

        pk1 = self._archive.insert_object(marker_data1, ignore_on_conflict=False)
        pk2 = self._archive.insert_object(marker_data2, ignore_on_conflict=False)

        with self.assertRaises(IntegrityError):
            self._archive.insert_object(marker_data3, ignore_on_conflict=False)

        self.assertNotEqual(pk1, pk2)

        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            resource='res',
            text='Some Message',
            id='messageid99',
            stanza_id=uuid,
            occupant_=None,
        )

        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.markers

        self.assertTrue(len(message.markers), 2)

        marker1, marker2 = message.markers
        assert marker1.occupant is not None
        assert marker2.occupant is not None

        self.assertEqual(marker1.occupant.id, 'occupantid1')
        self.assertEqual(marker1.timestamp, datetime.fromtimestamp(1, timezone.utc))
        self.assertEqual(marker2.occupant.id, 'occupantid2')
        self.assertEqual(marker2.timestamp, datetime.fromtimestamp(2, timezone.utc))


if __name__ == '__main__':
    unittest.main()
