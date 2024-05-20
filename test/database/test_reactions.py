from __future__ import annotations

import unittest

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import Occupant
from gajim.common.storage.archive.models import Reaction
from gajim.common.storage.archive.storage import MessageArchiveStorage
from gajim.common.util.datetime import utc_now

from .util import mk_utc_dt


class ReactionsTest(unittest.TestCase):
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

    def test_reactions_join(self):
        r_data1 = Reaction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid1',
            direction=ChatDirection.INCOMING,
            emojis='😁️',
            timestamp=mk_utc_dt(10),
        )

        r_data2 = Reaction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid1',
            direction=ChatDirection.INCOMING,
            emojis='😁️;😘️;😇️',
            timestamp=mk_utc_dt(11),
        )

        r_data3 = Reaction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid1',
            direction=ChatDirection.INCOMING,
            emojis='😘️',
            timestamp=mk_utc_dt(9),
        )

        r_data4 = Reaction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            id='messageid1',
            direction=ChatDirection.OUTGOING,
            emojis='😘️',
            timestamp=mk_utc_dt(9),
        )

        pk = self._archive.upsert_row2(r_data1)
        self.assertIsNotNone(pk)
        pk = self._archive.upsert_row2(r_data2)
        self.assertIsNotNone(pk)
        pk = self._archive.upsert_row2(r_data3)
        self.assertIsNone(pk)
        pk = self._archive.upsert_row2(r_data4)
        self.assertIsNotNone(pk)

        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.OUTGOING,
            timestamp=utc_now(),
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

        self.assertTrue(len(message.reactions), 2)

        self.assertEqual(message.reactions[0].emojis, '😁️;😘️;😇️')
        self.assertEqual(message.reactions[1].emojis, '😘️')

    def test_reactions_join_groupchat(self):
        occupant_data1 = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='occupantid1',
            nickname='nickname1',
            updated_at=mk_utc_dt(0),
        )

        occupant_data2 = Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='occupantid2',
            nickname='nickname2',
            updated_at=mk_utc_dt(0),
        )

        uuid = get_uuid()

        r_data1 = Reaction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data1,
            id=uuid,
            direction=ChatDirection.INCOMING,
            emojis='😁️',
            timestamp=mk_utc_dt(1),
        )

        r_data2 = Reaction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data2,
            id=uuid,
            direction=ChatDirection.INCOMING,
            emojis='😘️',
            timestamp=mk_utc_dt(2),
        )

        r_data3 = Reaction(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=occupant_data1,
            id=uuid,
            direction=ChatDirection.INCOMING,
            emojis='😇️;😁️',
            timestamp=mk_utc_dt(3),
        )

        pk = self._archive.upsert_row2(r_data1)
        self.assertIsNotNone(pk)
        pk = self._archive.upsert_row2(r_data2)
        self.assertIsNotNone(pk)
        pk = self._archive.upsert_row2(r_data3)
        self.assertIsNotNone(pk)

        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            timestamp=mk_utc_dt(0),
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

        self.assertTrue(len(message.reactions), 2)

        r1, r2 = message.reactions

        assert r1.occupant is not None
        assert r2.occupant is not None

        self.assertEqual(r1.occupant.id, 'occupantid1')
        self.assertEqual(r1.timestamp, mk_utc_dt(3))
        self.assertEqual(r1.emojis, '😇️;😁️')
        self.assertEqual(r2.occupant.id, 'occupantid2')
        self.assertEqual(r2.timestamp, mk_utc_dt(2))
        self.assertEqual(r2.emojis, '😘️')


if __name__ == '__main__':
    unittest.main()
