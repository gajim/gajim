from __future__ import annotations

import unittest
from datetime import datetime
from datetime import timezone

from nbxmpp.protocol import JID
from sqlalchemy import select

from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Encryption
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.storage import MessageArchiveStorage


class EncryptionTest(unittest.TestCase):
    def setUp(self) -> None:
        self._archive = MessageArchiveStorage(in_memory=True)
        self._archive.init()

        self._account_jid = JID.from_string('user@domain.org')
        self._account = 'testacc1'
        self._remote_jid = JID.from_string('remote@jid.org')
        self._init_settings()

    def _init_settings(self) -> None:
        app.settings = Settings(in_memory=True)
        app.settings.init()
        app.settings.add_account('testacc1')
        app.settings.set_account_setting('testacc1', 'name', 'user')
        app.settings.set_account_setting('testacc1', 'hostname', 'domain.org')

    def test_encryption_join(self):
        enc_data1 = Encryption(protocol=1, key='testkey', trust=2)

        enc_data2 = Encryption(protocol=1, key='testkey', trust=2)

        message_data1 = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            resource='res',
            text='Some Message',
            id='1',
            stanza_id=get_uuid(),
            encryption_=enc_data1,
        )

        message_data2 = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(1, timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            resource='res',
            text='Some other Message',
            id='2',
            stanza_id=get_uuid(),
            encryption_=enc_data2,
        )

        message_pk1 = self._archive.insert_object(message_data1)
        message_pk2 = self._archive.insert_object(message_data2)

        message1 = self._archive.get_message_with_pk(message_pk1)
        message2 = self._archive.get_message_with_pk(message_pk2)

        assert message1 is not None
        assert message1.encryption is not None

        assert message2 is not None
        assert message2.encryption is not None

        self.assertEqual(message1.encryption.pk, message2.encryption.pk)
        self.assertEqual(message1.encryption.protocol, 1)
        self.assertEqual(message1.encryption.key, 'testkey')
        self.assertEqual(message1.encryption.trust, 2)

    def test_encryption_update(self):
        enc_data1 = Encryption(protocol=1, key='testkey1', trust=2)

        enc_data2 = Encryption(protocol=1, key='testkey1', trust=2)

        pk1 = self._archive.insert_row(enc_data1, return_pk_on_conflict=True)
        pk2 = self._archive.insert_row(enc_data2, return_pk_on_conflict=True)

        self.assertEqual(pk1, pk2)

        with self._archive.get_session() as s:
            res = s.scalar(select(Encryption).where(Encryption.pk == pk1))
        assert res is not None


if __name__ == '__main__':
    unittest.main()
