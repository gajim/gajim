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
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import SecurityLabel
from gajim.common.storage.archive.storage import MessageArchiveStorage


class SecurityLabelsTest(unittest.TestCase):
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

    def test_security_labels_join(self):
        sec_data = SecurityLabel(
            account_=self._account,
            remote_jid_=self._remote_jid,
            updated_at=datetime.fromtimestamp(0, timezone.utc),
            label_hash='label1hash',
            displaymarking='SECRET',
            fgcolor='black',
            bgcolor='red',
        )

        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.fromtimestamp(0, timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            resource='res',
            text='Some Message',
            id='messageid1',
            stanza_id=get_uuid(),
            security_label_=sec_data,
        )

        message_pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(message_pk)

        assert message is not None
        assert message.security_label is not None

        self.assertEqual(message.security_label.displaymarking, 'SECRET')
        self.assertEqual(message.security_label.fgcolor, 'black')
        self.assertEqual(message.security_label.bgcolor, 'red')

    def test_security_labels_update(self):
        sec_data1 = SecurityLabel(
            account_=self._account,
            remote_jid_=self._remote_jid,
            updated_at=datetime.fromtimestamp(0, timezone.utc),
            label_hash='label1hash',
            displaymarking='SECRET',
            fgcolor='black',
            bgcolor='red',
        )

        sec_data2 = SecurityLabel(
            account_=self._account,
            remote_jid_=self._remote_jid,
            updated_at=datetime.fromtimestamp(1, timezone.utc),
            label_hash='label1hash',
            displaymarking='NOT SECRET',
            fgcolor='white',
            bgcolor='blue',
        )

        pk1 = self._archive.upsert_row(sec_data1)
        pk2 = self._archive.upsert_row(sec_data2)
        pk3 = self._archive.upsert_row(sec_data1)

        self.assertEqual(pk1, pk2)
        self.assertEqual(pk2, pk3)

        with self._archive.get_session() as s:
            res = s.scalar(select(SecurityLabel).where(SecurityLabel.pk == pk3))
        assert res is not None

        self.assertEqual(res.displaymarking, 'NOT SECRET')
        self.assertEqual(res.fgcolor, 'white')
        self.assertEqual(res.bgcolor, 'blue')
        self.assertEqual(res.updated_at, datetime.fromtimestamp(1, timezone.utc))


if __name__ == '__main__':
    unittest.main()
