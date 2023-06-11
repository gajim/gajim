from __future__ import annotations

import unittest
from datetime import datetime
from datetime import timezone

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.storage import MessageArchiveStorage


class MessagesTest(unittest.TestCase):
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

    def _create_base_message(
        self,
        message_id: str,
        stanza_id: str | None,
        direction: ChatDirection = ChatDirection.INCOMING,
    ) -> Message:
        return Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            resource='someres1',
            type=MessageType.CHAT,
            direction=direction,
            timestamp=datetime.now(timezone.utc),
            state=MessageState.ACKNOWLEDGED,
            id=message_id,
            stanza_id=stanza_id,
            text='message',
        )

if __name__ == '__main__':
    unittest.main()
