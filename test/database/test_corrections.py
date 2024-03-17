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
from gajim.common.storage.archive.models import Occupant
from gajim.common.storage.archive.models import OOB
from gajim.common.storage.archive.storage import MessageArchiveStorage


class CorrectionsTest(unittest.TestCase):
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

        app.settings.add_account('testacc2')
        app.settings.set_account_setting('testacc2', 'name', 'user2')
        app.settings.set_account_setting('testacc2', 'hostname', 'domain.org')

    def _create_base_occupant(self, occupant_id: str) -> Occupant:
        return Occupant(
            account_=self._account,
            remote_jid_=self._remote_jid,
            id=occupant_id,
            nickname='peter',
            updated_at=datetime.fromtimestamp(50, timezone.utc),
        )

    def _create_base_message(self) -> Message:
        return Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            state=MessageState.ACKNOWLEDGED,
            timestamp=datetime.fromtimestamp(0, timezone.utc),
            resource='res1',
            text='Some Message',
            id='messageid1',
            stanza_id=get_uuid(),
            correction_id=None,
            occupant_=self._create_base_occupant('occupantid1'),
            oob=[OOB(url='https://www.test.com', description='desc')],
        )

    def test_join_correction_groupchat_occupant_id(self) -> None:
        # Order corrections by timestamp
        # Join with occupant id

        m = self._create_base_message()
        message_pk = self._archive.insert_object(m)

        # Insert in not ascending order to test ordering

        m = self._create_base_message()
        m.text = 'second correction'
        m.id = 'messageid3'
        m.timestamp = datetime.fromtimestamp(2, timezone.utc)
        m.correction_id = 'messageid1'
        assert m.oob
        m.oob[0].description = 'second corrected desc'

        self._archive.insert_object(m)

        # Change resource, but leave occupant id the same
        # this message should be still joined

        m = self._create_base_message()
        m.text = 'first correction'
        m.resource = 'otherres'
        m.id = 'messageid2'
        m.timestamp = datetime.fromtimestamp(1, timezone.utc)
        m.correction_id = 'messageid1'

        self._archive.insert_object(m)

        # Add correction from unrelated occupant, should not be joined

        m = self._create_base_message()
        m.occupant_ = self._create_base_occupant('occupantid2')
        m.text = 'third correction'
        m.id = 'messageid4'
        m.timestamp = datetime.fromtimestamp(3, timezone.utc)
        m.correction_id = 'messageid1'

        self._archive.insert_object(m)

        # Add correction with no occupant id, should not be joined

        m = self._create_base_message()
        m.occupant_ = None
        m.text = 'third correction'
        m.id = 'messageid5'
        m.timestamp = datetime.fromtimestamp(4, timezone.utc)
        m.correction_id = 'messageid1'

        self._archive.insert_object(m)

        message = self._archive.get_message_with_pk(message_pk)

        assert message is not None
        assert message.corrections

        self.assertEqual(len(message.corrections), 2)
        self.assertEqual(message.corrections[0].text, 'first correction')
        self.assertEqual(message.corrections[1].text, 'second correction')
        assert message.corrections[1].oob is not None
        self.assertEqual(
            message.corrections[1].oob[0].description, 'second corrected desc'
        )

    def test_join_correction_groupchat_resource(self) -> None:
        # Join only with resource, when occupant id is not supported

        m = self._create_base_message()
        m.occupant_ = None
        message_pk = self._archive.insert_object(m)

        m = self._create_base_message()
        m.occupant_ = None
        m.text = 'first correction'
        m.id = 'messageid2'
        m.timestamp = datetime.fromtimestamp(1, timezone.utc)
        m.correction_id = 'messageid1'

        self._archive.insert_object(m)

        # Add correction from unrelated resource, should not be joined

        m = self._create_base_message()
        m.occupant_ = None
        m.resource = 'unrelatedres'
        m.text = 'second correction'
        m.id = 'messageid3'
        m.timestamp = datetime.fromtimestamp(2, timezone.utc)
        m.correction_id = 'messageid1'

        self._archive.insert_object(m)

        message = self._archive.get_message_with_pk(message_pk)

        assert message is not None
        assert message.corrections

        self.assertEqual(len(message.corrections), 1)
        self.assertEqual(message.corrections[0].text, 'first correction')

    def test_join_correction_single_chat(self) -> None:
        # Order corrections by timestamp
        # Join with occupant id

        m = self._create_base_message()
        m.type = MessageType.CHAT
        message_pk = self._archive.insert_object(m)

        m = self._create_base_message()
        m.type = MessageType.CHAT
        m.text = 'first correction'
        m.id = 'messageid2'
        m.timestamp = datetime.fromtimestamp(1, timezone.utc)
        m.correction_id = 'messageid1'

        self._archive.insert_object(m)

        # Change resource, should still be joined because
        # resource does not matter in single chat

        m = self._create_base_message()
        m.type = MessageType.CHAT
        m.text = 'second correction'
        m.resource = 'otherres'
        m.id = 'messageid3'
        m.timestamp = datetime.fromtimestamp(2, timezone.utc)
        m.correction_id = 'messageid1'

        self._archive.insert_object(m)

        # Change remote jid, should not be joined

        m = self._create_base_message()
        m.type = MessageType.CHAT
        m.remote_jid_ = JID.from_string('other@remote.jid')
        m.text = 'third correction'
        m.id = 'messageid4'
        m.timestamp = datetime.fromtimestamp(3, timezone.utc)
        m.correction_id = 'messageid1'

        self._archive.insert_object(m)

        # Change account, should not be joined

        m = self._create_base_message()
        m.type = MessageType.CHAT
        m.account_ = 'testacc2'
        m.text = 'fourth correction'
        m.id = 'messageid5'
        m.timestamp = datetime.fromtimestamp(4, timezone.utc)
        m.correction_id = 'messageid1'

        self._archive.insert_object(m)

        # Change direction, should not be joined

        m = self._create_base_message()
        m.type = MessageType.CHAT
        m.direction = ChatDirection.OUTGOING
        m.text = 'fifth correction'
        m.id = 'messageid6'
        m.timestamp = datetime.fromtimestamp(5, timezone.utc)
        m.correction_id = 'messageid1'

        self._archive.insert_object(m)

        message = self._archive.get_message_with_pk(message_pk)

        assert message is not None
        assert message.corrections

        self.assertEqual(len(message.corrections), 2)
        self.assertEqual(message.corrections[0].text, 'first correction')
        self.assertEqual(message.corrections[1].text, 'second correction')


if __name__ == '__main__':
    unittest.main()
