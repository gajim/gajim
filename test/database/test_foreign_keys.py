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
from gajim.common.storage.archive.models import MessageError
from gajim.common.storage.archive.models import OOB
from gajim.common.storage.archive.models import Reply
from gajim.common.storage.archive.models import SecurityLabel
from gajim.common.storage.archive.storage import MessageArchiveStorage
from gajim.common.util.datetime import utc_now


class ForeignKeyTest(unittest.TestCase):
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

    def test_message_delete_cascade(self) -> None:
        oob_data1 = OOB(url='https://www.test.com', description='somedesc')
        oob_data2 = OOB(url='https://www.othertest.com', description='otherdesc')

        reply_data = Reply(
            id='123',
            to=JID.from_string('somejid@jid.com'),
        )

        enc_data = Encryption(protocol=1, key='testkey', trust=2)

        sec_data = SecurityLabel(
            account_=self._account,
            remote_jid_=self._remote_jid,
            updated_at=datetime.fromtimestamp(0, timezone.utc),
            label_hash='somehash',
            displaymarking='SECRET',
            fgcolor='black',
            bgcolor='red',
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
            stanza_id=get_uuid(),
            text='message',
            encryption_=enc_data,
            security_label_=sec_data,
            oob=[oob_data1, oob_data2],
            reply=reply_data,
        )

        pk = self._archive.insert_object(message_data)

        error_data = MessageError(
            account_=self._account,
            remote_jid_=self._remote_jid,
            message_id='1',
            by=JID.from_string('some@jid.com'),
            type='modify',
            text='Some error text',
            condition='not-acceptable',
            condition_text='Some Application Text',
            timestamp=utc_now(),
        )

        self._archive.insert_row(error_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.oob is not None
        self.assertEqual(message.oob[0].description, 'somedesc')
        self.assertEqual(message.oob[1].description, 'otherdesc')

        assert message.reply is not None
        self.assertEqual(message.reply.id, '123')
        self.assertEqual(message.reply.to, JID.from_string('somejid@jid.com'))
        self.assertIsInstance(message.reply.to, JID)

        self.assertEqual(message.account.jid, self._account_jid)
        self.assertEqual(message.remote.jid, self._remote_jid)

        assert message.encryption is not None
        self.assertEqual(message.encryption.key, 'testkey')

        assert message.security_label is not None
        self.assertEqual(message.security_label.displaymarking, 'SECRET')

        assert message.error is not None
        self.assertEqual(message.error.by, 'some@jid.com')
        self.assertIsInstance(message.error.by, JID)
        self.assertEqual(message.error.text, 'Some error text')
        self.assertEqual(message.error.condition, 'not-acceptable')
        self.assertEqual(message.error.condition_text, 'Some Application Text')
        self.assertEqual(message.error.type, 'modify')

        self._archive.delete_message(message.pk)

        stmts = [
            select(Reply),
            select(OOB),
            select(Message),
        ]

        for stmt in stmts:
            with self._archive.get_session() as s:
                res = s.execute(stmt).one_or_none()
            assert res is None


if __name__ == '__main__':
    unittest.main()
