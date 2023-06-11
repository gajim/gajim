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
from gajim.common.storage.archive.models import MessageError
from gajim.common.storage.archive.storage import MessageArchiveStorage
from gajim.common.util.datetime import utc_now


class ErrorTest(unittest.TestCase):
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

    def test_insert_error(self) -> None:
        error_data1 = MessageError(
            account_=self._account,
            remote_jid_=self._remote_jid,
            message_id='1',
            by=JID.from_string('some@domain.com'),
            type='modify',
            text='Text 1',
            condition='not-acceptable',
            condition_text='Condition Data 1',
            timestamp=utc_now(),
        )

        pk = self._archive.insert_row(error_data1)

        with self._archive.get_session() as s:
            error = s.scalar(select(MessageError).where(MessageError.pk == pk))
        assert error is not None

        self.assertEqual(error.by, 'some@domain.com')
        self.assertIsInstance(error.by, JID)
        self.assertEqual(error.text, 'Text 1')
        self.assertEqual(error.condition, 'not-acceptable')
        self.assertEqual(error.condition_text, 'Condition Data 1')
        self.assertEqual(error.type, 'modify')

        error_data2 = MessageError(
            account_=self._account,
            remote_jid_=self._remote_jid,
            message_id='1',
            by=JID.from_string('some@domain.com'),
            type='cancel',
            text='Text 2',
            condition='not-acceptable',
            condition_text='Condition Data 2',
            timestamp=utc_now(),
        )

        pk = self._archive.insert_row(error_data2, ignore_on_conflict=True)
        self.assertEqual(pk, -1)

    def test_error_join(self) -> None:
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
        )

        pk = self._archive.insert_object(message_data)

        error_data1 = MessageError(
            account_=self._account,
            remote_jid_=self._remote_jid,
            message_id='1',
            by=JID.from_string('some@domain.com'),
            type='modify',
            text='Text 1',
            condition='not-acceptable',
            condition_text='Condition Data 1',
            timestamp=utc_now(),
        )
        self._archive.insert_row(error_data1)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.error is not None
        self.assertEqual(message.error.by, 'some@domain.com')
        self.assertIsInstance(message.error.by, JID)
        self.assertEqual(message.error.text, 'Text 1')
        self.assertEqual(message.error.condition, 'not-acceptable')
        self.assertEqual(message.error.condition_text, 'Condition Data 1')
        self.assertEqual(message.error.type, 'modify')


if __name__ == '__main__':
    unittest.main()
