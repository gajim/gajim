from __future__ import annotations

import unittest
from datetime import datetime
from datetime import timezone

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.storage import MessageArchiveStorage


class ThreadsTest(unittest.TestCase):
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

    def _create_base_message(self, message_id: str, thread_id: str) -> Message:
        return Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            resource='someres1',
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.now(timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            id=message_id,
            stanza_id=get_uuid(),
            thread_id_=thread_id,
            text='message',
        )

    def test_insert_thread(self) -> None:
        # Insert thread and join afterwards

        message_data = self._create_base_message(message_id='1', thread_id='t1')
        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.thread is not None

        self.assertEqual(message.thread.pk, 1)
        self.assertEqual(message.thread.fk_account_pk, 1)
        self.assertEqual(message.thread.fk_remote_pk, 1)
        self.assertEqual(message.thread.id, 't1')

        # Same thread yields same thread pk

        message_data = self._create_base_message(message_id='2', thread_id='t1')
        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.thread is not None

        self.assertEqual(message.thread.pk, 1)
        self.assertEqual(message.thread.fk_account_pk, 1)
        self.assertEqual(message.thread.fk_remote_pk, 1)
        self.assertEqual(message.thread.id, 't1')

        # Different thread yield different thread pk

        message_data = self._create_base_message(message_id='3', thread_id='t2')
        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.thread is not None

        self.assertEqual(message.thread.pk, 2)
        self.assertEqual(message.thread.fk_account_pk, 1)
        self.assertEqual(message.thread.fk_remote_pk, 1)
        self.assertEqual(message.thread.id, 't2')

        # Different remote jid with same thread id yields new thread pk

        message_data = self._create_base_message(message_id='4', thread_id='t2')
        message_data.remote_jid_ = JID.from_string('remote2@jid.org')
        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.thread is not None

        self.assertEqual(message.thread.pk, 3)
        self.assertEqual(message.thread.fk_account_pk, 1)
        self.assertEqual(message.thread.fk_remote_pk, 2)
        self.assertEqual(message.thread.id, 't2')


if __name__ == '__main__':
    unittest.main()
