# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest
from datetime import datetime
from datetime import UTC

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

        self._account_jid = JID.from_string("user@domain.org")
        self._account = "testacc1"
        self._remote_jid = JID.from_string("remote@jid.org")
        self._init_settings()

    def tearDown(self) -> None:
        self._archive.shutdown()

    def _init_settings(self) -> None:
        app.settings = Settings(in_memory=True)
        app.settings.init()
        app.settings.add_account("testacc1")
        app.settings.set_account_setting("testacc1", "address", "user@domain.org")

    def test_encryption_join(self):
        enc_data1 = Encryption(protocol="OMEMO", key="testkey", trust=2)

        enc_data2 = Encryption(protocol="OMEMO", key="testkey", trust=2)

        message_data1 = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, UTC),
            state=MessageState.ACKNOWLEDGED,
            resource="res",
            text="Some Message",
            id="1",
            stanza_id=get_uuid(),
            encryption_=enc_data1,
        )

        message_data2 = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(1, UTC),
            state=MessageState.ACKNOWLEDGED,
            resource="res",
            text="Some other Message",
            id="2",
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
        self.assertEqual(message1.encryption.protocol, "OMEMO")
        self.assertEqual(message1.encryption.key, "testkey")
        self.assertEqual(message1.encryption.trust, 2)

    def test_encryption_update(self):
        enc_data1 = Encryption(protocol="OMEMO", key="testkey1", trust=2)

        enc_data2 = Encryption(protocol="OMEMO", key="testkey1", trust=2)

        pk1 = self._archive.insert_row(enc_data1, return_pk_on_conflict=True)
        pk2 = self._archive.insert_row(enc_data2, return_pk_on_conflict=True)

        self.assertEqual(pk1, pk2)

        with self._archive.get_session() as s:
            res = s.scalar(select(Encryption).where(Encryption.pk == pk1))
        assert res is not None

    def test_decryption_failure_metadata_is_per_message(self):
        message = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, UTC),
            state=MessageState.ACKNOWLEDGED,
            resource="conversation-resource",
            text="Could not decrypt",
            id="failure",
            stanza_id=get_uuid(),
            encryption_=Encryption(protocol="OMEMO", key="stored-key", trust=0),
            encryption_error_condition="missing-session",
            encryption_device_id=23,
            encryption_sender_jid=JID.from_string("sender@example.test"),
            encryption_sender_resource="sender-resource",
            encryption_identity_authenticated=False,
        )

        pk = self._archive.insert_object(message)
        stored = self._archive.get_message_with_pk(pk)

        assert stored is not None
        self.assertEqual(stored.encryption_error_condition, "missing-session")
        self.assertEqual(stored.encryption_device_id, 23)
        self.assertEqual(
            stored.encryption_sender_jid, JID.from_string("sender@example.test")
        )
        self.assertEqual(stored.encryption_sender_resource, "sender-resource")
        self.assertFalse(stored.encryption_identity_authenticated)


if __name__ == "__main__":
    unittest.main()
