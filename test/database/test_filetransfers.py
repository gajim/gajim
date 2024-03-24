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
from gajim.common.storage.archive.models import FileTransfer
from gajim.common.storage.archive.models import FileTransferSource
from gajim.common.storage.archive.models import JinglePub
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import UrlData
from gajim.common.storage.archive.storage import MessageArchiveStorage


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

    def test_filetransfer_join(self) -> None:
        now = datetime.now(timezone.utc)

        source1 = UrlData(
            type='urldata',
            target='http://target',
            scheme_data={'header': 'someheader'},
        )

        source2 = JinglePub(
            type='jinglepub',
            id='123',
        )

        ft_data1 = FileTransfer(
            date=now,
            desc='desc',
            hash='abc',
            hash_algo='sha-1',
            height=123,
            length=778272,
            media_type='image/png',
            name='filename1',
            size=6555,
            width=789,
            state=0,
            source=[source1, source2],
        )

        message_data = Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            resource='someres1',
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=now,
            state=MessageState.ACKNOWLEDGED,
            id='1',
            stanza_id=get_uuid(),
            text='message',
            filetransfers=[ft_data1],
        )

        pk = self._archive.insert_object(message_data)

        message = self._archive.get_message_with_pk(pk)

        assert message is not None
        assert message.filetransfers
        ft1 = message.filetransfers[0]
        self.assertEqual(ft1.date, now)
        self.assertEqual(ft1.desc, 'desc')
        self.assertEqual(ft1.hash, 'abc')
        self.assertEqual(ft1.hash_algo, 'sha-1')
        self.assertEqual(ft1.height, 123)
        self.assertEqual(ft1.length, 778272)
        self.assertEqual(ft1.media_type, 'image/png')
        self.assertEqual(ft1.name, 'filename1')
        self.assertEqual(ft1.size, 6555)
        self.assertEqual(ft1.width, 789)
        self.assertEqual(ft1.state, 0)

        assert ft1.source

        source1 = ft1.source[0]
        source2 = ft1.source[1]
        assert isinstance(source1, UrlData)
        assert isinstance(source2, JinglePub)

        self.assertEqual(source1.type, 'urldata')
        self.assertEqual(source1.target, 'http://target')
        self.assertEqual(source1.scheme_data, {'header': 'someheader'})

        self.assertEqual(source2.type, 'jinglepub')
        self.assertEqual(source2.id, '123')

        self._archive.delete_message(message.pk)

        stmts = [
            select(FileTransfer),
            select(UrlData),
            select(FileTransferSource),
        ]

        for stmt in stmts:
            with self._archive.get_session() as s:
                res = s.execute(stmt).one_or_none()
            assert res is None


if __name__ == '__main__':
    unittest.main()
