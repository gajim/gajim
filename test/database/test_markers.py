from __future__ import annotations

import unittest
from datetime import datetime
from datetime import timezone

from nbxmpp.protocol import JID
from sqlalchemy import select

from gajim.common import app
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import ChatMarkerType
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Marker
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import Occupant
from gajim.common.storage.archive.storage import MessageArchiveStorage


class MarkersTest(unittest.TestCase):
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
        marker_data1 = Marker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid1',
            type=ChatMarkerType.RECEIVED,
            timestamp=datetime.fromtimestamp(1, timezone.utc),
        )

        marker_data2 = Marker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid1',
            type=ChatMarkerType.DISPLAYED,
            timestamp=datetime.fromtimestamp(3, timezone.utc),
        )

        marker_ek1 = self._archive.upsert_row(marker_data1)
        marker_ek2 = self._archive.upsert_row(marker_data2)

        self.assertNotEqual(marker_ek1, marker_ek2)

        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.OUTGOING,
            timestamp=datetime.now(timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            resource='res',
            message='Some Message',
            id='messageid1',
            stanza_id='1a',
            stable_id=True,
            occupant_=None,
            user_delay_ts=None,
            correction_id=None,
        )

        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.markers

        self.assertTrue(len(message.markers), 2)

        self.assertEqual(message.markers[0].type, ChatMarkerType.RECEIVED)
        self.assertEqual(
            message.markers[0].timestamp, datetime.fromtimestamp(1, timezone.utc)
        )
        self.assertEqual(message.markers[1].type, ChatMarkerType.DISPLAYED)
        self.assertEqual(
            message.markers[1].timestamp, datetime.fromtimestamp(3, timezone.utc)
        )

        latest_marker = message.get_latest_marker()
        assert latest_marker is not None
        self.assertEqual(latest_marker.pk, message.markers[1].pk)

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

        marker_data1 = Marker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data1,
            id='messageid1',
            type=ChatMarkerType.RECEIVED,
            timestamp=datetime.fromtimestamp(1, timezone.utc),
        )

        marker_data2 = Marker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data2,
            id='messageid1',
            type=ChatMarkerType.DISPLAYED,
            timestamp=datetime.fromtimestamp(2, timezone.utc),
        )

        pk1 = self._archive.upsert_row(marker_data1)
        pk2 = self._archive.upsert_row(marker_data2)

        self.assertNotEqual(pk1, pk2)

        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            resource='res',
            message='Some Message',
            id='messageid99',
            stanza_id='messageid1',
            stable_id=True,
            occupant_=None,
            user_delay_ts=None,
            correction_id=None,
        )

        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.markers

        marker1, marker2 = message.markers
        assert marker1.occupant is not None
        assert marker2.occupant is not None

        self.assertEqual(marker1.occupant.id, 'occupantid1')
        self.assertEqual(marker1.type, ChatMarkerType.RECEIVED)
        self.assertEqual(marker1.timestamp, datetime.fromtimestamp(1, timezone.utc))
        self.assertEqual(marker2.occupant.id, 'occupantid2')
        self.assertEqual(marker2.type, ChatMarkerType.DISPLAYED)
        self.assertEqual(marker2.timestamp, datetime.fromtimestamp(2, timezone.utc))

        latest_marker = message.get_latest_marker()
        assert latest_marker is not None
        self.assertEqual(latest_marker.pk, marker2.pk)

    def test_markers_update(self):
        # Don’t update the same marker id with a later timestamp

        marker_data1 = Marker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid1',
            type=ChatMarkerType.RECEIVED,
            timestamp=datetime.fromtimestamp(1, timezone.utc),
        )

        marker_data2 = Marker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid1',
            type=ChatMarkerType.RECEIVED,
            timestamp=datetime.fromtimestamp(3, timezone.utc),
        )

        pk1 = self._archive.upsert_row(marker_data1)
        pk2 = self._archive.upsert_row(marker_data2)

        session = self._archive.get_session()

        self.assertEqual(pk1, pk2)
        marker = session.scalar(select(Marker))
        assert marker is not None

        self.assertEqual(marker.type, ChatMarkerType.RECEIVED)
        self.assertEqual(marker.id, "messageid1")
        self.assertEqual(marker.timestamp, datetime.fromtimestamp(1, timezone.utc))

        # Don’t Update marker with different id and earlier timestamp

        marker_data3 = Marker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid2',
            type=ChatMarkerType.RECEIVED,
            timestamp=datetime.fromtimestamp(0, timezone.utc),
        )

        pk3 = self._archive.upsert_row(marker_data3)
        self.assertEqual(pk1, pk3)
        marker = session.scalar(select(Marker))
        assert marker is not None

        self.assertEqual(marker.type, ChatMarkerType.RECEIVED)
        self.assertEqual(marker.id, "messageid1")
        self.assertEqual(marker.timestamp, datetime.fromtimestamp(1, timezone.utc))

        # Update marker with different id and later timestamp

        marker_data4 = Marker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid2',
            type=ChatMarkerType.RECEIVED,
            timestamp=datetime.fromtimestamp(5, timezone.utc),
        )

        pk4 = self._archive.upsert_row(marker_data4)
        self.assertEqual(pk1, pk4)
        marker = session.scalar(select(Marker))
        assert marker is not None

        self.assertEqual(marker.type, ChatMarkerType.RECEIVED)
        self.assertEqual(marker.id, "messageid2")
        self.assertEqual(marker.timestamp, datetime.fromtimestamp(5, timezone.utc))

        # Markers with different types don’t have same pk

        marker_data5 = Marker(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid2',
            type=ChatMarkerType.DISPLAYED,
            timestamp=datetime.fromtimestamp(4, timezone.utc),
        )

        pk5 = self._archive.upsert_row(marker_data5)
        self.assertNotEqual(pk1, pk5)


if __name__ == '__main__':
    unittest.main()
