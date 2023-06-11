from __future__ import annotations

import unittest
from datetime import datetime
from datetime import timezone

from nbxmpp.protocol import JID
from sqlalchemy import select

from gajim.common import app
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import Occupant
from gajim.common.storage.archive.storage import MessageArchiveStorage


class OccupantTest(unittest.TestCase):
    def setUp(self) -> None:
        self._archive = MessageArchiveStorage(in_memory=True)
        self._archive.init()

        self._account = 'testacc1'
        self._account_jid = JID.from_string('user@domain.org')
        self._remote_jid = JID.from_string('remote@jid.org')
        self._occupant_id = 'occupantid1'
        self._init_settings()

    def _init_settings(self) -> None:
        app.settings = Settings(in_memory=True)
        app.settings.init()
        app.settings.add_account('testacc1')
        app.settings.set_account_setting('testacc1', 'name', 'user')
        app.settings.set_account_setting('testacc1', 'hostname', 'domain.org')

    def test_insert_occupant(self) -> None:
        occupant_data = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='someid',
            nickname='peter',
            updated_at=datetime.fromtimestamp(50, timezone.utc),
        )

        pk = self._archive.upsert_row(occupant_data)

        with self._archive.get_session() as s:
            occupant = s.scalar(select(Occupant).where(Occupant.pk == pk))
        assert occupant is not None

        self.assertEqual(occupant.id, 'someid')
        self.assertEqual(occupant.real_remote, None)
        self.assertEqual(occupant.nickname, 'peter')
        self.assertEqual(occupant.avatar_sha, None)
        self.assertEqual(occupant.updated_at, datetime.fromtimestamp(50, timezone.utc))

        occupant_data = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='someid',
            real_remote_jid_=JID.from_string('real@remote.jid'),
            nickname='peter',
            avatar_sha='sha1',
            updated_at=datetime.fromtimestamp(100, timezone.utc),
        )

        pk = self._archive.upsert_row(occupant_data)

        with self._archive.get_session() as s:
            occupant = s.scalar(select(Occupant).where(Occupant.pk == pk))
        assert occupant is not None
        assert occupant.real_remote is not None

        self.assertEqual(occupant.id, 'someid')
        self.assertEqual(occupant.real_remote.jid, 'real@remote.jid')
        self.assertIsInstance(occupant.real_remote.jid, JID)
        self.assertEqual(occupant.nickname, 'peter')
        self.assertEqual(occupant.avatar_sha, 'sha1')
        self.assertEqual(occupant.updated_at, datetime.fromtimestamp(100, timezone.utc))

        # Update with old data should be ignored

        occupant_data = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='someid',
            real_remote_jid_=JID.from_string('real2@remote.jid'),
            nickname='peter2',
            avatar_sha='sha2',
            updated_at=datetime.fromtimestamp(50, timezone.utc),
        )

        pk = self._archive.upsert_row(occupant_data)
        self.assertEqual(pk, 1)

        with self._archive.get_session() as s:
            occupant = s.scalar(select(Occupant).where(Occupant.pk == pk))
        assert occupant is not None
        assert occupant.real_remote is not None

        self.assertEqual(occupant.id, 'someid')
        self.assertEqual(occupant.real_remote.jid, 'real@remote.jid')
        self.assertIsInstance(occupant.real_remote.jid, JID)
        self.assertEqual(occupant.nickname, 'peter')
        self.assertEqual(occupant.avatar_sha, 'sha1')
        self.assertEqual(occupant.updated_at, datetime.fromtimestamp(100, timezone.utc))

        # Update with new data
        # Remote JID should not be overwritten

        occupant_data = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='someid',
            real_remote_jid_=JID.from_string('real2@remote.jid'),
            nickname='peter2',
            avatar_sha='sha2',
            updated_at=datetime.fromtimestamp(200, timezone.utc),
        )

        pk = self._archive.upsert_row(occupant_data)
        self.assertEqual(pk, 1)

        with self._archive.get_session() as s:
            occupant = s.scalar(select(Occupant).where(Occupant.pk == pk))
        assert occupant is not None
        assert occupant.real_remote is not None

        self.assertEqual(occupant.id, 'someid')
        self.assertEqual(occupant.real_remote.jid, 'real@remote.jid')
        self.assertIsInstance(occupant.real_remote.jid, JID)
        self.assertEqual(occupant.nickname, 'peter2')
        self.assertEqual(occupant.avatar_sha, 'sha2')
        self.assertEqual(occupant.updated_at, datetime.fromtimestamp(200, timezone.utc))

        # Set avatar_sha None
        # Passing None to for nickname should be ignored

        occupant_data = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='someid',
            nickname=None,
            avatar_sha=None,
            updated_at=datetime.fromtimestamp(300, timezone.utc),
        )

        pk = self._archive.upsert_row(occupant_data)
        self.assertEqual(pk, 1)

        with self._archive.get_session() as s:
            occupant = s.scalar(select(Occupant).where(Occupant.pk == pk))
        assert occupant is not None
        assert occupant.real_remote is not None

        self.assertEqual(occupant.id, 'someid')
        self.assertEqual(occupant.real_remote.jid, 'real@remote.jid')
        self.assertIsInstance(occupant.real_remote.jid, JID)
        self.assertEqual(occupant.nickname, 'peter2')
        self.assertEqual(occupant.avatar_sha, None)
        self.assertEqual(occupant.updated_at, datetime.fromtimestamp(300, timezone.utc))

    def test_occupant_join(self) -> None:
        occupant_data = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='someid',
            real_remote_jid_=JID.from_string('real@remote.jid'),
            nickname='peter3',
            avatar_sha='sha1',
            updated_at=datetime.fromtimestamp(300, timezone.utc),
        )

        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            resource='someres1',
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.now(timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            id='1',
            text='message',
            occupant_=occupant_data,
        )

        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.occupant is not None
        assert message.occupant.real_remote is not None

        self.assertEqual(message.occupant.nickname, 'peter3')
        self.assertEqual(message.occupant.avatar_sha, 'sha1')
        self.assertEqual(message.occupant.real_remote.jid, 'real@remote.jid')
        self.assertIsInstance(message.occupant.real_remote.jid, JID)


if __name__ == '__main__':
    unittest.main()
