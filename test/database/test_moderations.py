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
from gajim.common.storage.archive.models import Moderation
from gajim.common.storage.archive.storage import MessageArchiveStorage


class ModerationTest(unittest.TestCase):
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

    def test_insert_moderation(self) -> None:
        mod_data = Moderation(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            stanza_id='stanzaid1',
            by=JID.from_string('some@domain.com'),
            reason='some reason',
            timestamp=datetime.fromtimestamp(0, timezone.utc),
        )

        pk = self._archive.insert_row(mod_data, ignore_on_conflict=True)
        self.assertNotEqual(pk, -1)

        session = self._archive.get_session()
        moderation = session.scalar(select(Moderation).where(Moderation.pk == pk))
        assert moderation is not None

        self.assertEqual(moderation.by, 'some@domain.com')
        self.assertIsInstance(moderation.by, JID)
        self.assertEqual(moderation.reason, 'some reason')
        self.assertEqual(moderation.timestamp, datetime.fromtimestamp(0, timezone.utc))
        self.assertEqual(moderation.stanza_id, 'stanzaid1')
        self.assertEqual(moderation.occupant, None)

        mod_data = Moderation(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            stanza_id='stanzaid1',
            by=JID.from_string('someother@domain.com'),
            reason='some other reason',
            timestamp=datetime.fromtimestamp(1, timezone.utc),
        )

        pk = self._archive.insert_row(mod_data, ignore_on_conflict=True)
        self.assertEqual(pk, -1)

    def test_moderation_join(self) -> None:
        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            resource='someres1',
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=datetime.now(timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            id='1',
            stanza_id='stanzaid1',
            stable_id=True,
            message='message',
            user_delay_ts=None,
            correction_id=None,
        )

        pk = self._archive.insert_object(message_data)

        mod_data = Moderation(
            account_=self._account,
            remote_jid_=self._remote_jid,
            occupant_=None,
            stanza_id='stanzaid1',
            by=JID.from_string('some@domain.com'),
            reason='some reason',
            timestamp=datetime.fromtimestamp(0, timezone.utc),
        )

        self._archive.insert_row(mod_data, ignore_on_conflict=True)

        session = self._archive.get_session()
        session.expunge_all()
        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.moderation is not None
        self.assertEqual(message.moderation.by, 'some@domain.com')
        self.assertIsInstance(message.moderation.by, JID)
        self.assertEqual(message.moderation.reason, 'some reason')
        self.assertEqual(
            message.moderation.timestamp, datetime.fromtimestamp(0, timezone.utc)
        )
        self.assertEqual(message.moderation.stanza_id, 'stanzaid1')
        self.assertEqual(message.moderation.occupant, None)


if __name__ == '__main__':
    unittest.main()
