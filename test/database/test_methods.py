from __future__ import annotations

import datetime as dt
import unittest
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import sqlalchemy.exc
from nbxmpp.protocol import JID
from sqlalchemy import select

from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Encryption
from gajim.common.storage.archive.models import MAMArchiveState
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import MessageError
from gajim.common.storage.archive.models import Moderation
from gajim.common.storage.archive.storage import MessageArchiveStorage
from gajim.common.util.datetime import utc_now


class ThreadsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._archive = MessageArchiveStorage(in_memory=True)
        self._archive.init()

        self._account = 'testacc1'
        self._occupant_id = 'occupantid1'
        self._init_settings()

    def _init_settings(self) -> None:
        app.settings = Settings(in_memory=True)
        app.settings.init()
        app.settings.add_account('testacc1')
        app.settings.set_account_setting('testacc1', 'name', 'user1')
        app.settings.set_account_setting('testacc1', 'hostname', 'domain.org')
        app.settings.add_account('testacc2')
        app.settings.set_account_setting('testacc2', 'name', 'user2')
        app.settings.set_account_setting('testacc2', 'hostname', 'domain.org')

    def _insert_messages(
        self,
        account: str = 'testacc1',
        remote_jid: JID | None = None,
        resource: str | None = None,
        message: str = 'test',
        message_id: str | None = None,
        type: int = MessageType.CHAT,  # noqa: A002
        timestamp: datetime | None = None,
        count: int = 10,
    ) -> None:
        for i in range(count):
            remote_jid_ = remote_jid
            if remote_jid_ is None:
                remote_jid_ = JID.from_string(f'remote{i}@jid.org')

            timestamp_ = timestamp
            if timestamp_ is None:
                timestamp_ = datetime.now(timezone.utc)

            message_id_ = message_id
            if message_id_ is None:
                message_id_ = f'messageid{i}'

            resource_ = resource
            if resource_ is None:
                resource_ = f'res{i}'

            m = Message(
                account_=account,
                remote_jid_=remote_jid_,
                resource=resource_,
                type=type,
                direction=ChatDirection.INCOMING,
                timestamp=timestamp_,
                state=MessageState.ACKNOWLEDGED,
                id=message_id_,
                text=message,
            )
            self._archive.insert_object(m)

    def test_rollback(self) -> None:
        now = utc_now()
        uuid = get_uuid()
        m1 = Message(
            account_='testacc1',
            remote_jid_=JID.from_string('remote1@jid.org'),
            resource=None,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=now,
            state=MessageState.ACKNOWLEDGED,
            id='1',
            stanza_id=uuid,
        )
        pk = self._archive.insert_object(m1)

        m2 = Message(
            account_='testacc1',
            remote_jid_=JID.from_string('remote1@jid.org'),
            resource=None,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=now,
            state=MessageState.ACKNOWLEDGED,
            id='1',
            stanza_id=uuid,
            encryption_=Encryption(protocol=1, key='123', trust=1),
        )
        m2.pk = pk

        with self.assertRaises(sqlalchemy.exc.IntegrityError):
            self._archive.insert_object(m2, ignore_on_conflict=False)

        with self._archive.get_session() as s:
            result = s.scalar(select(Encryption))
            self.assertIsNone(result)

    def test_get_conversation_jids(self) -> None:
        self._insert_messages('testacc1', count=10)
        self._insert_messages('testacc2', count=12)

        jids = self._archive.get_conversation_jids('testacc1')
        self.assertEqual(len(jids), 10)
        jids = self._archive.get_conversation_jids('testacc2')
        self.assertEqual(len(jids), 12)

    def test_get_conversation_before_after(self) -> None:
        remote_jid = JID.from_string('remote1@jid.org')
        self._insert_messages('testacc1', remote_jid=remote_jid, count=10)

        messages = self._archive.get_conversation_before_after(
            'testacc1', remote_jid, True, datetime.now(timezone.utc), 10
        )

        self.assertEqual(messages[0].id, 'messageid9')
        self.assertEqual(messages[1].id, 'messageid8')

        messages = self._archive.get_conversation_before_after(
            'testacc1', remote_jid, False, datetime.fromtimestamp(0, timezone.utc), 10
        )

        self.assertEqual(messages[0].id, 'messageid0')
        self.assertEqual(messages[1].id, 'messageid1')

    def test_get_last_conversation_row(self) -> None:
        remote_jid = JID.from_string('remote1@jid.org')
        self._insert_messages(
            'testacc1',
            remote_jid=remote_jid,
            timestamp=datetime.now(timezone.utc),
            count=10,
        )

        message = self._archive.get_last_conversation_row('testacc1', remote_jid)
        assert message is not None

        self.assertEqual(message.id, 'messageid9')

    def test_get_last_correctable_message(self) -> None:
        # TODO
        pass

    def test_search_archive(self) -> None:
        # TODO
        return
        # remote_jid = JID.from_string(f'remote1@jid.org')
        # self._insert_messages(
        #     'testacc1', remote_jid=remote_jid, message='test', count=100)

        # iterator = self._archive.search_archive('testacc1', remote_jid, 'test')
        # messages = list(iterator)

    def test_get_days_containing_messages(self) -> None:
        localtime = datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc).astimezone()
        offset = localtime.utcoffset()
        assert offset is not None
        offset_s = offset.total_seconds()

        remote_jid = JID.from_string('remote1@jid.org')

        timestamp = datetime(2023, 12, 30, 23, 59, 59, 0, tzinfo=timezone.utc)
        for day in range(1, 5):
            timestamp += timedelta(days=1)
            self._insert_messages(
                'testacc1',
                remote_jid=remote_jid,
                timestamp=timestamp,
                message_id=f'messageid{day}',
                count=1,
            )

        days = self._archive.get_days_containing_messages(
            'testacc1', remote_jid, 2024, 1
        )

        self.assertEqual(
            days,
            [1, 2, 3] if offset_s <= 0 else [1, 2, 3, 4],
            msg=f'Localtime: {localtime}, offset: {offset_s}',
        )

    def test_get_last_message_ts(self) -> None:
        remote_jid = JID.from_string('remote1@jid.org')

        timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for day in range(2, 5):
            timestamp += timedelta(days=1)
            self._insert_messages(
                'testacc1',
                remote_jid=remote_jid,
                timestamp=timestamp,
                message_id=f'messageid{day}',
                count=1,
            )

        timestamp = self._archive.get_last_message_ts('testacc1', remote_jid)

        self.assertEqual(timestamp, datetime(2024, 1, 4, tzinfo=timezone.utc))

    def test_get_first_message_ts(self) -> None:
        remote_jid = JID.from_string('remote1@jid.org')

        timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
        for day in range(2, 5):
            timestamp += timedelta(days=1)
            self._insert_messages(
                'testacc1',
                remote_jid=remote_jid,
                timestamp=timestamp,
                message_id=f'messageid{day}',
                count=1,
            )

        timestamp = self._archive.get_first_message_ts('testacc1', remote_jid)

        self.assertEqual(timestamp, datetime(2024, 1, 2, tzinfo=timezone.utc))

    def test_get_first_message_meta_for_date(self) -> None:
        localtime = datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc).astimezone()
        offset = localtime.utcoffset()
        assert offset is not None
        offset_s = offset.total_seconds()

        remote_jid = JID.from_string('remote1@jid.org')

        timestamp = datetime(2023, 12, 30, 23, 59, 59, 0, tzinfo=timezone.utc)
        for day in range(1, 5):
            timestamp += timedelta(days=1)
            self._insert_messages(
                'testacc1',
                remote_jid=remote_jid,
                timestamp=timestamp,
                message_id=f'messageid{day}',
                count=1,
            )

        metadata = self._archive.get_first_message_meta_for_date(
            'testacc1', remote_jid, dt.date(2024, 1, 1)
        )
        assert metadata is not None
        pk, timestamp = metadata

        if offset_s > 0:
            self.assertEqual(pk, 1)
            self.assertEqual(
                timestamp, datetime(2023, 12, 31, 23, 59, 59, 0, tzinfo=timezone.utc)
            )
        else:
            self.assertEqual(pk, 2)
            self.assertEqual(
                timestamp, datetime(2024, 1, 1, 23, 59, 59, 0, tzinfo=timezone.utc)
            )

        metadata = self._archive.get_first_message_meta_for_date(
            'testacc1', remote_jid, dt.date(2024, 2, 1)
        )
        self.assertIsNone(metadata)

    def test_get_recent_muc_nicks(self) -> None:
        remote_jid = JID.from_string('remote1@jid.org')

        timestamp = datetime.now(timezone.utc) - timedelta(days=91)

        self._insert_messages(
            'testacc1',
            remote_jid=remote_jid,
            timestamp=timestamp,
            resource='res101',
            message_id='messageid101',
            count=1,
        )
        self._insert_messages(
            'testacc1', remote_jid=remote_jid, type=MessageType.GROUPCHAT, count=10
        )
        nicknames = self._archive.get_recent_muc_nicks('testacc1', remote_jid)
        self.assertEqual(len(nicknames), 10)
        self.assertNotIn('res101', nicknames)

    def test_get_mam_archive_state(self) -> None:
        remote_jid = JID.from_string('remote1@jid.org')
        state = MAMArchiveState(
            account_='testacc1',
            remote_jid_=remote_jid,
            from_stanza_id='stanzaid1',
            from_stanza_ts=datetime.now(timezone.utc),
            to_stanza_id='stanzaid2',
            to_stanza_ts=datetime.now(timezone.utc),
        )
        self._archive.upsert_row(state)

        state = self._archive.get_mam_archive_state('testacc1', remote_jid)
        assert state is not None
        self.assertEqual(state.from_stanza_id, 'stanzaid1')
        self.assertEqual(state.to_stanza_id, 'stanzaid2')

    def test_reset_mam_archive_state(self) -> None:
        remote_jid = JID.from_string('remote1@jid.org')
        state = MAMArchiveState(
            account_='testacc1',
            remote_jid_=remote_jid,
        )
        self._archive.upsert_row(state)

        state = self._archive.get_mam_archive_state('testacc1', remote_jid)
        assert state is not None
        self._archive.reset_mam_archive_state('testacc1', remote_jid)
        state = self._archive.get_mam_archive_state('testacc1', remote_jid)
        self.assertIsNone(state)

    def test_remove_history(self) -> None:
        remote_jid = JID.from_string('remote1@jid.org')
        self._insert_messages('testacc1', remote_jid=remote_jid, count=10)

        mod = Moderation(
            account_='testacc1',
            remote_jid_=remote_jid,
            occupant_=None,
            stanza_id='stanzaid1',
            by=None,
            reason=None,
            timestamp=utc_now(),
        )
        self._archive.insert_object(mod)

        error = MessageError(
            account_='testacc1',
            remote_jid_=remote_jid,
            message_id='messageid1',
            by=None,
            type='modify',
            text='text',
            condition='somecond',
            condition_text='somecondtext',
            timestamp=utc_now(),
        )

        self._archive.insert_object(error)

        with self._archive.get_session() as s:
            result = s.scalar(select(MessageError))
            self.assertIsNotNone(result)

            result = s.scalar(select(Moderation))
            self.assertIsNotNone(result)

            result = s.scalar(select(Message))
            self.assertIsNotNone(result)

        self._archive.remove_history_for_jid('testacc1', remote_jid)

        with self._archive.get_session() as s:
            result = s.scalar(select(MessageError))
            self.assertIsNone(result)

            result = s.scalar(select(Moderation))
            self.assertIsNone(result)

            result = s.scalar(select(Message))
            self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
