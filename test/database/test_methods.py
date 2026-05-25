# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import datetime as dt
import unittest
from datetime import datetime
from datetime import timedelta
from datetime import UTC

import sqlalchemy.exc
from nbxmpp.protocol import JID
from sqlalchemy import select
from sqlalchemy.orm import selectinload

import gajim.common.storage.archive.models as mod
from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.storage import MessageArchiveStorage
from gajim.common.util.datetime import utc_now


class MethodsTest(unittest.TestCase):
    def setUp(self) -> None:
        self._archive = MessageArchiveStorage(in_memory=True)
        self._archive.init()

        self._account = "testacc1"
        self._occupant_id = "occupantid1"
        self._init_settings()

    def tearDown(self) -> None:
        self._archive.shutdown()

    def _init_settings(self) -> None:
        app.settings = Settings(in_memory=True)
        app.settings.init()
        app.settings.add_account("testacc1")
        app.settings.set_account_setting("testacc1", "address", "user@domain.org")
        app.settings.add_account("testacc2")
        app.settings.set_account_setting("testacc2", "address", "user2@domain.org")

    def _insert_messages(
        self,
        account: str = "testacc1",
        remote_jid: JID | None = None,
        resource: str | None = None,
        message: str = "test",
        message_id: str | None = None,
        type: int = MessageType.CHAT,  # noqa: A002
        timestamp: datetime | None = None,
        count: int = 10,
    ) -> None:
        for i in range(count):
            remote_jid_ = remote_jid
            if remote_jid_ is None:
                remote_jid_ = JID.from_string(f"remote{i}@jid.org")

            timestamp_ = timestamp
            if timestamp_ is None:
                timestamp_ = datetime.now(dt.UTC)

            message_id_ = message_id
            if message_id_ is None:
                message_id_ = f"messageid{i}"

            resource_ = resource
            if resource_ is None:
                resource_ = f"res{i}"

            m = mod.Message(
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
        m1 = mod.Message(
            account_="testacc1",
            remote_jid_=JID.from_string("remote1@jid.org"),
            resource=None,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=now,
            state=MessageState.ACKNOWLEDGED,
            id="1",
            stanza_id=uuid,
        )
        pk = self._archive.insert_object(m1)

        m2 = mod.Message(
            account_="testacc1",
            remote_jid_=JID.from_string("remote1@jid.org"),
            resource=None,
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=now,
            state=MessageState.ACKNOWLEDGED,
            id="1",
            stanza_id=uuid,
            encryption_=mod.Encryption(protocol="OMEMO", key="123", trust=1),
        )
        m2.pk = pk

        with self.assertRaises(sqlalchemy.exc.IntegrityError):
            self._archive.insert_object(m2, ignore_on_conflict=False)

        with self._archive.get_session() as s:
            result = s.scalar(select(mod.Encryption))
            self.assertIsNone(result)

    def test_get_conversation_jids(self) -> None:
        self._insert_messages("testacc1", count=10)
        self._insert_messages("testacc2", count=12)

        rows = self._archive.get_conversation_jids("testacc1")
        self.assertEqual(len(rows), 10)
        rows = self._archive.get_conversation_jids("testacc2")
        self.assertEqual(len(rows), 12)

    def test_get_conversation_before_after(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")
        self._insert_messages("testacc1", remote_jid=remote_jid, count=4)

        messages, complete = self._archive.get_conversation_before_after(
            "testacc1",
            remote_jid,
            datetime.now(dt.UTC),
            2,
            direction="before",
            order="desc",
        )

        messages = list(messages)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].id, "messageid3")
        self.assertEqual(messages[1].id, "messageid2")
        self.assertFalse(complete)

        messages, complete = self._archive.get_conversation_before_after(
            "testacc1",
            remote_jid,
            datetime(year=1970, month=1, day=1, tzinfo=dt.UTC),
            2,
            direction="after",
            order="desc",
        )

        messages = list(messages)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].id, "messageid1")
        self.assertEqual(messages[1].id, "messageid0")
        self.assertFalse(complete)

        messages, complete = self._archive.get_conversation_before_after(
            "testacc1",
            remote_jid,
            datetime.now(dt.UTC),
            2,
            direction="before",
            order="asc",
        )

        messages = list(messages)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].id, "messageid2")
        self.assertEqual(messages[1].id, "messageid3")
        self.assertFalse(complete)

        messages, complete = self._archive.get_conversation_before_after(
            "testacc1",
            remote_jid,
            datetime(year=1970, month=1, day=1, tzinfo=dt.UTC),
            2,
            direction="after",
            order="asc",
        )

        messages = list(messages)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0].id, "messageid0")
        self.assertEqual(messages[1].id, "messageid1")
        self.assertFalse(complete)

        # Test complete flag

        # Same amount returned as requested
        messages, complete = self._archive.get_conversation_before_after(
            "testacc1",
            remote_jid,
            datetime(year=1970, month=1, day=1, tzinfo=dt.UTC),
            4,
            direction="after",
            order="asc",
        )

        messages = list(messages)
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0].id, "messageid0")
        self.assertEqual(messages[1].id, "messageid1")
        self.assertFalse(complete)

        # Less returned than requested
        messages, complete = self._archive.get_conversation_before_after(
            "testacc1",
            remote_jid,
            datetime(year=1970, month=1, day=1, tzinfo=dt.UTC),
            5,
            direction="after",
            order="asc",
        )

        messages = list(messages)
        self.assertEqual(len(messages), 4)
        self.assertEqual(messages[0].id, "messageid0")
        self.assertEqual(messages[1].id, "messageid1")
        self.assertTrue(complete)

    def test_get_last_conversation_row(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")
        self._insert_messages(
            "testacc1",
            remote_jid=remote_jid,
            timestamp=datetime.now(dt.UTC),
            count=10,
        )

        message = self._archive.get_last_conversation_row(
            "testacc1", remote_jid, incl_related_data=True
        )
        assert message is not None

        self.assertEqual(message.id, "messageid9")

    def test_search_archive(self) -> None:
        # TODO
        return
        # remote_jid = JID.from_string(f'remote1@jid.org')
        # self._insert_messages(
        #     'testacc1', remote_jid=remote_jid, message='test', count=100)

        # iterator = self._archive.search_archive('testacc1', remote_jid, 'test')
        # messages = list(iterator)

    def test_get_days_containing_messages(self) -> None:
        localtime = datetime(2023, 12, 31, 23, 59, 59, tzinfo=dt.UTC).astimezone()
        offset = localtime.utcoffset()
        assert offset is not None
        offset_s = offset.total_seconds()

        remote_jid = JID.from_string("remote1@jid.org")

        timestamp = datetime(2023, 12, 30, 23, 59, 59, 0, tzinfo=dt.UTC)
        for day in range(1, 5):
            timestamp += timedelta(days=1)
            self._insert_messages(
                "testacc1",
                remote_jid=remote_jid,
                timestamp=timestamp,
                message_id=f"messageid{day}",
                count=1,
            )

        days = self._archive.get_days_containing_messages(
            "testacc1", remote_jid, 2024, 1
        )

        self.assertEqual(
            days,
            [1, 2, 3] if offset_s <= 0 else [1, 2, 3, 4],
            msg=f"Localtime: {localtime}, offset: {offset_s}",
        )

    def test_get_last_message_ts(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")

        timestamp = datetime(2024, 1, 1, tzinfo=dt.UTC)
        for day in range(2, 5):
            timestamp += timedelta(days=1)
            self._insert_messages(
                "testacc1",
                remote_jid=remote_jid,
                timestamp=timestamp,
                message_id=f"messageid{day}",
                count=1,
            )

        timestamp = self._archive.get_last_message_ts("testacc1", remote_jid)

        self.assertEqual(timestamp, datetime(2024, 1, 4, tzinfo=dt.UTC))

    def test_get_first_message_ts(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")

        timestamp = datetime(2024, 1, 1, tzinfo=dt.UTC)
        for day in range(2, 5):
            timestamp += timedelta(days=1)
            self._insert_messages(
                "testacc1",
                remote_jid=remote_jid,
                timestamp=timestamp,
                message_id=f"messageid{day}",
                count=1,
            )

        timestamp = self._archive.get_first_message_ts("testacc1", remote_jid)

        self.assertEqual(timestamp, datetime(2024, 1, 2, tzinfo=dt.UTC))

    def test_get_first_message_meta_for_date(self) -> None:
        localtime = datetime(2023, 12, 31, 23, 59, 59, tzinfo=dt.UTC).astimezone()
        offset = localtime.utcoffset()
        assert offset is not None
        offset_s = offset.total_seconds()

        remote_jid = JID.from_string("remote1@jid.org")

        timestamp = datetime(2023, 12, 30, 23, 59, 59, 0, tzinfo=dt.UTC)
        for day in range(1, 5):
            timestamp += timedelta(days=1)
            self._insert_messages(
                "testacc1",
                remote_jid=remote_jid,
                timestamp=timestamp,
                message_id=f"messageid{day}",
                count=1,
            )

        metadata = self._archive.get_first_message_meta_for_date(
            "testacc1", remote_jid, dt.date(2024, 1, 1)
        )
        assert metadata is not None
        pk, timestamp = metadata

        if offset_s > 0:
            self.assertEqual(pk, 1)
            self.assertEqual(
                timestamp, datetime(2023, 12, 31, 23, 59, 59, 0, tzinfo=dt.UTC)
            )
        else:
            self.assertEqual(pk, 2)
            self.assertEqual(
                timestamp, datetime(2024, 1, 1, 23, 59, 59, 0, tzinfo=dt.UTC)
            )

        metadata = self._archive.get_first_message_meta_for_date(
            "testacc1", remote_jid, dt.date(2024, 2, 1)
        )
        self.assertIsNone(metadata)

    def test_get_recent_muc_nicks(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")

        timestamp = datetime.now(dt.UTC) - timedelta(days=91)

        self._insert_messages(
            "testacc1",
            remote_jid=remote_jid,
            timestamp=timestamp,
            resource="res101",
            message_id="messageid101",
            count=1,
        )
        self._insert_messages(
            "testacc1", remote_jid=remote_jid, type=MessageType.GROUPCHAT, count=10
        )
        nicknames = self._archive.get_recent_muc_nicks("testacc1", remote_jid)
        self.assertEqual(len(nicknames), 10)
        self.assertNotIn("res101", nicknames)

    def test_get_mam_archive_state(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")
        state = mod.MAMArchiveState(
            account_="testacc1",
            remote_jid_=remote_jid,
            from_stanza_id="stanzaid1",
            from_stanza_ts=datetime.now(dt.UTC),
            to_stanza_id="stanzaid2",
            to_stanza_ts=datetime.now(dt.UTC),
        )
        self._archive.upsert_row(state)

        state = self._archive.get_mam_archive_state("testacc1", remote_jid)
        assert state is not None
        self.assertEqual(state.from_stanza_id, "stanzaid1")
        self.assertEqual(state.to_stanza_id, "stanzaid2")

    def test_reset_mam_archive_state(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")
        state = mod.MAMArchiveState(
            account_="testacc1",
            remote_jid_=remote_jid,
        )
        self._archive.upsert_row(state)

        state = self._archive.get_mam_archive_state("testacc1", remote_jid)
        assert state is not None
        self._archive.reset_mam_archive_state("testacc1", remote_jid)
        state = self._archive.get_mam_archive_state("testacc1", remote_jid)
        self.assertIsNone(state)

    def test_remove_history_for_jid(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")
        self._insert_messages("testacc1", remote_jid=remote_jid, count=10)

        # Moderation message should no match any message to
        # test if orphan data are removed
        m = mod.Moderation(
            account_="testacc1",
            remote_jid_=remote_jid,
            occupant_=None,
            stanza_id="DoNotMatchID",
            by=None,
            reason=None,
            timestamp=utc_now(),
        )
        self._archive.insert_object(m)

        error = mod.MessageError(
            account_="testacc1",
            remote_jid_=remote_jid,
            message_id="messageid1",
            by=None,
            type="modify",
            text="text",
            condition="somecond",
            condition_text="somecondtext",
            timestamp=utc_now(),
        )

        self._archive.insert_object(error)

        seclabel = mod.SecurityLabel(
            account_="testacc1",
            remote_jid_=remote_jid,
            label_hash="hash1",
            displaymarking="dm",
            bgcolor="red",
            fgcolor="blue",
            updated_at=utc_now(),
        )

        reaction = mod.Reaction(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="123",
            direction=ChatDirection.INCOMING,
            emojis="😁️;😘️;😇️",
            timestamp=utc_now(),
        )

        self._archive.upsert_row2(reaction)

        marker = mod.DisplayedMarker(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="123",
            timestamp=utc_now(),
        )

        self._archive.insert_object(marker)

        receipt = mod.Receipt(
            account_=self._account,
            remote_jid_=remote_jid,
            id="123",
            timestamp=utc_now(),
        )

        self._archive.insert_object(receipt)

        retraction_data = mod.Retraction(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="123",
            direction=ChatDirection.OUTGOING,
            timestamp=utc_now(),
        )

        self._archive.insert_row(retraction_data)

        m = mod.Message(
            account_="testacc1",
            remote_jid_=remote_jid,
            resource="test",
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            id="123",
            stanza_id="stanzaid123",
            text="testmessage",
            security_label_=seclabel,
            thread_id_="testthreadid",
            encryption_=mod.Encryption(protocol="OMEMO", key="somekey", trust=1),
            call=mod.Call(sid="somesid", state=1),
            oob=[mod.OOB(url="someurl", description="desc")],
            og=[mod.OpenGraph(about="about", title="title")],
            reply=mod.Reply(id="132", to=None),
        )
        self._archive.insert_object(m)

        jid_related_tables = [
            mod.OOB,
            mod.OpenGraph,
            mod.Reply,
            mod.Call,
            mod.MessageError,
            mod.Moderation,
            mod.Retraction,
            mod.Receipt,
            mod.DisplayedMarker,
            mod.Reaction,
            mod.Message,
            mod.SecurityLabel,
            mod.Thread,
        ]

        with self._archive.get_session() as s:
            for table in jid_related_tables:
                result = s.scalar(select(table))
                self.assertIsNotNone(result)

            result = s.scalar(select(mod.Encryption))
            self.assertIsNotNone(result)

        self._archive.remove_history_for_jid("testacc1", remote_jid)

        with self._archive.get_session() as s:
            for table in jid_related_tables:
                result = s.scalar(select(table))
                self.assertIsNone(result)

            result = s.scalar(select(mod.Encryption))
            self.assertIsNotNone(result)

    def test_delete_message(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")

        m = mod.Moderation(
            account_="testacc1",
            remote_jid_=remote_jid,
            occupant_=None,
            stanza_id="stanzaid123",
            by=None,
            reason=None,
            timestamp=utc_now(),
        )
        self._archive.insert_object(m)

        error = mod.MessageError(
            account_="testacc1",
            remote_jid_=remote_jid,
            message_id="123",
            by=None,
            type="modify",
            text="text",
            condition="somecond",
            condition_text="somecondtext",
            timestamp=utc_now(),
        )

        self._archive.insert_object(error)

        reaction = mod.Reaction(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="stanzaid123",
            direction=ChatDirection.INCOMING,
            emojis="😁️;😘️;😇️",
            timestamp=utc_now(),
        )

        self._archive.upsert_row2(reaction)

        marker = mod.DisplayedMarker(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="stanzaid123",
            timestamp=utc_now(),
        )

        self._archive.insert_object(marker)

        receipt = mod.Receipt(
            account_=self._account,
            remote_jid_=remote_jid,
            id="123",
            timestamp=utc_now(),
        )

        self._archive.insert_object(receipt)

        retraction_data = mod.Retraction(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="stanzaid123",
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
        )

        self._archive.insert_row(retraction_data)

        m = mod.Message(
            account_="testacc1",
            remote_jid_=remote_jid,
            resource="test",
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            id="123",
            stanza_id="stanzaid123",
            text="testmessage",
            security_label_=mod.SecurityLabel(
                account_="testacc1",
                remote_jid_=remote_jid,
                label_hash="hash1",
                displaymarking="dm",
                bgcolor="red",
                fgcolor="blue",
                updated_at=utc_now(),
            ),
            thread_id_="testthreadid",
            encryption_=mod.Encryption(protocol="OMEMO", key="somekey", trust=1),
            call=mod.Call(sid="somesid", state=1),
            oob=[mod.OOB(url="someurl", description="desc")],
            og=[mod.OpenGraph(about="about", title="title")],
            reply=mod.Reply(id="132", to=None),
        )
        m_pk = self._archive.insert_object(m)

        m = mod.Message(
            account_="testacc1",
            remote_jid_=remote_jid,
            resource="test",
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            id="124",
            stanza_id="stanzaid124",
            correction_id="123",
            text="corrected message",
            thread_id_="testthreadid",
            call=mod.Call(sid="somesid", state=1),
            oob=[mod.OOB(url="someurl", description="desc")],
            og=[mod.OpenGraph(about="about", title="title")],
            reply=mod.Reply(id="132", to=None),
        )

        self._archive.insert_object(m)

        reaction = mod.Reaction(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="stanzaid124",
            direction=ChatDirection.INCOMING,
            emojis="😁️",
            timestamp=utc_now(),
        )

        self._archive.upsert_row2(reaction)

        jid_related_tables = [
            mod.OOB,
            mod.OpenGraph,
            mod.Reply,
            mod.Call,
            mod.MessageError,
            mod.Retraction,
            mod.Receipt,
            mod.DisplayedMarker,
            mod.Reaction,
            mod.Moderation,
            mod.Message,
        ]

        many_to_one_tables = [
            mod.Encryption,
            mod.SecurityLabel,
            mod.Thread,
        ]

        with self._archive.get_session() as s:
            for table in jid_related_tables:
                result = s.scalar(select(table))
                self.assertIsNotNone(result)

            for table in many_to_one_tables:
                result = s.scalar(select(table))
                self.assertIsNotNone(result)

        self._archive.delete_message(m_pk)

        with self._archive.get_session() as s:
            for table in jid_related_tables:
                result = s.scalar(select(table))
                self.assertIsNone(result)

            for table in many_to_one_tables:
                result = s.scalar(select(table))
                self.assertIsNotNone(result)

    def test_get_message_with_pk(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")

        m = mod.Moderation(
            account_="testacc1",
            remote_jid_=remote_jid,
            occupant_=None,
            stanza_id="stanzaid123",
            by=None,
            reason=None,
            timestamp=utc_now(),
        )
        self._archive.insert_object(m)

        error = mod.MessageError(
            account_="testacc1",
            remote_jid_=remote_jid,
            message_id="123",
            by=None,
            type="modify",
            text="text",
            condition="somecond",
            condition_text="somecondtext",
            timestamp=utc_now(),
        )

        self._archive.insert_object(error)

        reaction = mod.Reaction(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="stanzaid123",
            direction=ChatDirection.INCOMING,
            emojis="😁️;😘️;😇️",
            timestamp=utc_now(),
        )

        self._archive.upsert_row2(reaction)

        marker = mod.DisplayedMarker(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="stanzaid123",
            timestamp=utc_now(),
        )

        self._archive.insert_object(marker)

        receipt = mod.Receipt(
            account_=self._account,
            remote_jid_=remote_jid,
            id="123",
            timestamp=utc_now(),
        )

        self._archive.insert_object(receipt)

        retraction_data = mod.Retraction(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="stanzaid123",
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
        )

        self._archive.insert_row(retraction_data)

        m = mod.Message(
            account_="testacc1",
            remote_jid_=remote_jid,
            resource="test",
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            id="123",
            stanza_id="stanzaid123",
            text="testmessage",
            security_label_=mod.SecurityLabel(
                account_="testacc1",
                remote_jid_=remote_jid,
                label_hash="hash1",
                displaymarking="dm",
                bgcolor="red",
                fgcolor="blue",
                updated_at=utc_now(),
            ),
            thread_id_="testthreadid",
            occupant_=mod.Occupant(
                account_="testacc1",
                remote_jid_=remote_jid,
                id="someoccid",
                real_remote_jid_=JID.from_string("real@remote.jid"),
                nickname="peter",
                avatar_sha="sha1",
                updated_at=utc_now(),
            ),
            encryption_=mod.Encryption(protocol="OMEMO", key="somekey", trust=1),
            call=mod.Call(sid="somesid", state=1),
            oob=[mod.OOB(url="someurl", description="desc")],
            og=[mod.OpenGraph(about="about", title="title")],
            reply=mod.Reply(id="132", to=None),
        )
        m_pk = self._archive.insert_object(m)

        # Correction

        m = mod.Message(
            account_="testacc1",
            remote_jid_=remote_jid,
            resource="test",
            type=MessageType.GROUPCHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            id="124",
            stanza_id="stanzaid124",
            correction_id="123",
            text="corrected message",
            security_label_=mod.SecurityLabel(
                account_="testacc1",
                remote_jid_=remote_jid,
                label_hash="hash2",
                displaymarking="dm",
                bgcolor="red",
                fgcolor="blue",
                updated_at=utc_now(),
            ),
            thread_id_="testthreadid",
            occupant_=mod.Occupant(
                account_="testacc1",
                remote_jid_=remote_jid,
                id="someoccid",
                real_remote_jid_=JID.from_string("real@remote.jid"),
                nickname="peter",
                avatar_sha="sha1",
                updated_at=utc_now(),
            ),
            encryption_=mod.Encryption(protocol="OMEMO", key="some_cor_key", trust=1),
            call=mod.Call(sid="some_cor_sid", state=1),
            oob=[mod.OOB(url="some_cor_url", description="desc")],
            og=[mod.OpenGraph(about="about_cor", title="title")],
            reply=mod.Reply(id="133", to=None),
        )

        self._archive.insert_object(m)

        m = mod.Moderation(
            account_="testacc1",
            remote_jid_=remote_jid,
            occupant_=None,
            stanza_id="stanzaid124",
            by=None,
            reason=None,
            timestamp=utc_now(),
        )
        self._archive.insert_object(m)

        error = mod.MessageError(
            account_="testacc1",
            remote_jid_=remote_jid,
            message_id="124",
            by=None,
            type="modify",
            text="cor_text",
            condition="somecond",
            condition_text="somecondtext",
            timestamp=utc_now(),
        )

        self._archive.insert_object(error)

        reaction = mod.Reaction(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="stanzaid124",
            direction=ChatDirection.INCOMING,
            emojis="😁️",
            timestamp=utc_now(),
        )

        self._archive.upsert_row2(reaction)

        marker = mod.DisplayedMarker(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="stanzaid124",
            timestamp=utc_now(),
        )

        self._archive.insert_object(marker)

        receipt = mod.Receipt(
            account_=self._account,
            remote_jid_=remote_jid,
            id="124",
            timestamp=utc_now(),
        )

        self._archive.insert_object(receipt)

        retraction_data = mod.Retraction(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=None,
            id="stanzaid124",
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
        )

        self._archive.insert_row(retraction_data)

        message = self._archive.get_message_with_pk(
            m_pk, options=[selectinload(mod.Message.markers)]
        )
        assert message is not None
        self.assertIsNotNone(message.account)
        self.assertIsNotNone(message.remote)
        self.assertIsNotNone(message.thread)
        self.assertIsNotNone(message.occupant)
        self.assertIsNotNone(message.encryption)
        self.assertIsNotNone(message.security_label)
        self.assertIsNotNone(message.receipt)
        self.assertIsNotNone(message.retraction)
        self.assertIsNotNone(message.moderation)
        self.assertIsNotNone(message.error)
        self.assertIsNotNone(message.call)
        self.assertIsNotNone(message.reply)
        self.assertEqual(len(message.oob), 1)
        self.assertEqual(len(message.reactions), 1)
        # self.assertEqual(len(message.filetransfers), 1)
        self.assertEqual(len(message.og), 1)
        self.assertEqual(len(message.markers), 1)
        self.assertEqual(len(message.corrections), 1)

        # Now check if the correction also has all the relationships loaded
        message = message.corrections[0]

        self.assertIsNotNone(message.account)
        self.assertIsNotNone(message.remote)
        self.assertIsNotNone(message.thread)
        self.assertIsNotNone(message.occupant)
        self.assertIsNotNone(message.encryption)
        assert message.encryption is not None
        self.assertEqual(message.encryption.key, "some_cor_key")
        self.assertIsNotNone(message.security_label)
        assert message.security_label is not None
        self.assertEqual(message.security_label.label_hash, "hash2")
        self.assertIsNotNone(message.receipt)
        self.assertIsNotNone(message.retraction)
        self.assertIsNotNone(message.moderation)
        self.assertIsNotNone(message.error)
        self.assertIsNotNone(message.call)
        self.assertIsNotNone(message.reply)
        self.assertEqual(len(message.oob), 1)
        self.assertEqual(len(message.reactions), 1)
        self.assertEqual(message.reactions[0].emojis, "😁️")
        # self.assertEqual(len(message.filetransfers), 1)
        self.assertEqual(len(message.og), 1)
        self.assertEqual(len(message.markers), 1)

    def test_check_if_stanza_id_exists(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")
        m = mod.Message(
            account_="testacc1",
            remote_jid_=remote_jid,
            resource="test",
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            id="123",
            stanza_id="stanzaid123",
            text="testmessage",
        )
        self._archive.insert_object(m)

        result = self._archive.check_if_stanza_id_exists(
            "testacc1", remote_jid, "stanzaid123"
        )
        self.assertTrue(result)

        result = self._archive.check_if_stanza_id_exists("testacc1", remote_jid, "xxx")
        self.assertFalse(result)

    def test_check_if_message_id_exists(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")
        m = mod.Message(
            account_="testacc1",
            remote_jid_=remote_jid,
            resource="test",
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=utc_now(),
            state=MessageState.ACKNOWLEDGED,
            id="123",
            stanza_id="stanzaid123",
            text="testmessage",
        )
        self._archive.insert_object(m)

        result = self._archive.check_if_message_id_exists("testacc1", remote_jid, "123")
        self.assertTrue(result)

        result = self._archive.check_if_message_id_exists("testacc1", remote_jid, "xxx")
        self.assertFalse(result)

    def test_block_occupants(self) -> None:
        remote_jid = JID.from_string("remote1@jid.org")
        pks: list[int] = []

        for i in range(10):
            occupant = mod.Occupant(
                account_="testacc1",
                remote_jid_=remote_jid,
                id=f"occupant{i}",
                nickname=f"nickname{i}",
                avatar_sha="sha1",
                blocked=i > 4,
                updated_at=utc_now(),
            )
            pk = self._archive.upsert_row(occupant)
            if i > 4:
                pks.append(pk)

        occupant = mod.Occupant(
            account_="testacc2",
            remote_jid_=remote_jid,
            id="occupant11",
            nickname="nickname11",
            avatar_sha="sha1",
            blocked=True,
            updated_at=utc_now(),
        )
        self._archive.upsert_row(occupant)

        occupants = self._archive.get_blocked_occupants("testacc1")
        res = [o.pk for o in occupants]
        self.assertEqual(res, pks)
        self.assertEqual(len(res), 5)

        # This should not raise an exception because the remote table
        # is joined when queried via get_blocked_occupants()
        for o in occupants:
            o.remote.jid  # noqa: B018

        occupants = self._archive.get_blocked_occupants("testacc2")
        self.assertEqual(len(occupants), 1)

        affected = self._archive.set_block_occupant("testacc1", None, [], True)
        occupants = self._archive.get_blocked_occupants(self._account)
        self.assertEqual(len(occupants), 10)
        self.assertEqual(affected, 5)

        occupant_ids = ["occupant1", "occupant2", "occupant3"]

        affected = self._archive.set_block_occupant(
            "testacc1", None, occupant_ids, False
        )
        occupants = self._archive.get_blocked_occupants(self._account)
        self.assertEqual(len(occupants), 7)
        self.assertEqual(affected, 3)

        affected = self._archive.set_block_occupant("testacc1", remote_jid, [], True)
        occupants = self._archive.get_blocked_occupants(self._account)
        self.assertEqual(len(occupants), 10)
        self.assertEqual(affected, 3)

        occupants = self._archive.get_blocked_occupants("testacc2")
        self.assertEqual(len(occupants), 1)

    def test_get_last_display_markers(self) -> None:
        remote_jid1 = JID.from_string("remote1@jid.org")
        remote_jid2 = JID.from_string("remote2@jid.org")

        for i in range(3):
            occupant = mod.Occupant(
                account_="testacc1",
                remote_jid_=remote_jid1,
                id=f"occupant{i}",
                nickname=f"nickname{i}",
                avatar_sha="sha1",
                blocked=False,
                updated_at=utc_now(),
            )

            for i in range(3):
                marker = mod.DisplayedMarker(
                    account_="testacc1",
                    remote_jid_=remote_jid1,
                    occupant_=occupant,
                    id=f"message{i}",
                    timestamp=utc_now() + timedelta(seconds=i),
                )
                self._archive.insert_object(marker)

                # Same markers but from different account received
                marker = mod.DisplayedMarker(
                    account_="testacc2",
                    remote_jid_=remote_jid1,
                    occupant_=occupant,
                    id=f"message{i}",
                    timestamp=utc_now() + timedelta(seconds=i),
                )
                self._archive.insert_object(marker)

            # Marker from different JID
            marker = mod.DisplayedMarker(
                account_="testacc1",
                remote_jid_=remote_jid2,
                occupant_=None,
                id="message99",
                timestamp=utc_now(),
            )
            self._archive.insert_object(marker)

        result = self._archive.get_last_display_markers("testacc1", remote_jid1)

        self.assertEqual(len(result), 3)

        res0, res1, res2 = result
        assert res0.occupant is not None
        assert res1.occupant is not None
        assert res2.occupant is not None

        self.assertEqual(res0.occupant.id, "occupant0")
        self.assertEqual(res0.id, "message2")

        self.assertEqual(res1.occupant.id, "occupant1")
        self.assertEqual(res1.id, "message2")

        self.assertEqual(res2.occupant.id, "occupant2")
        self.assertEqual(res2.id, "message2")

    def test_get_occupant_by_jids(self) -> None:
        remote_jid1 = JID.from_string("remote1@jid.org")

        real_remote_jid1 = JID.from_string("real1@remote.jid")
        real_remote_jid3 = JID.from_string("real3@remote.jid")

        occupant1 = mod.Occupant(
            account_=self._account,
            remote_jid_=remote_jid1,
            id="1",
            real_remote_jid_=real_remote_jid1,
            nickname="peter1",
            avatar_sha="sha1",
            updated_at=datetime.fromtimestamp(101, UTC),
        )

        occupant2 = mod.Occupant(
            account_=self._account,
            remote_jid_=remote_jid1,
            id="2",
            real_remote_jid_=real_remote_jid1,
            nickname="peter2",
            avatar_sha="sha1",
            updated_at=datetime.fromtimestamp(100, UTC),
        )

        occupant3 = mod.Occupant(
            account_=self._account,
            remote_jid_=remote_jid1,
            id="3",
            real_remote_jid_=real_remote_jid3,
            nickname="susi",
            avatar_sha="sha1",
            updated_at=datetime.fromtimestamp(102, UTC),
        )

        self._archive.upsert_row(occupant1)
        self._archive.upsert_row(occupant2)
        self._archive.upsert_row(occupant3)

        occupants = self._archive.get_occupant_by_jids(
            self._account,
            remote_jid1,
            [real_remote_jid1, real_remote_jid3],
            max_age=timedelta(minutes=60),
        )
        self.assertEqual(len(occupants), 2)

        occupant1 = occupants[real_remote_jid1]
        occupant3 = occupants[real_remote_jid3]

        assert occupant1.real_remote is not None
        assert occupant3.real_remote is not None

        self.assertEqual(occupant1.id, "1")
        self.assertEqual(occupant1.real_remote.jid, real_remote_jid1)
        self.assertEqual(occupant1.nickname, "peter1")
        self.assertEqual(occupant1.updated_at, datetime.fromtimestamp(101, UTC))

        self.assertEqual(occupant3.id, "3")
        self.assertEqual(occupant3.real_remote.jid, real_remote_jid3)
        self.assertEqual(occupant3.nickname, "susi")


if __name__ == "__main__":
    unittest.main()
