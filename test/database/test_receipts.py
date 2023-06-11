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
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import Receipt
from gajim.common.storage.archive.storage import MessageArchiveStorage


class ReceiptTest(unittest.TestCase):
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

    def test_receipt_join(self):
        receipt_data1 = Receipt(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='messageid1',
            timestamp=datetime.fromtimestamp(1, timezone.utc),
        )

        receipt_data2 = Receipt(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id='messageid1',
            timestamp=datetime.fromtimestamp(3, timezone.utc),
        )

        self._archive.insert_object(receipt_data1)

        with self.assertRaises(IntegrityError):
            self._archive.insert_object(receipt_data2, ignore_on_conflict=False)

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
        assert message.receipt is not None

        self.assertIsNotNone(message.receipt)

        self.assertEqual(
            message.receipt.timestamp, datetime.fromtimestamp(1, timezone.utc)
        )


if __name__ == '__main__':
    unittest.main()
