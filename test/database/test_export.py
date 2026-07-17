# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import unittest
from datetime import datetime
from datetime import UTC

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.helpers import get_uuid
from gajim.common.settings import Settings
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message
from gajim.common.storage.archive.models import Moderation
from gajim.common.storage.archive.models import OOB
from gajim.common.storage.archive.models import Retraction
from gajim.common.storage.archive.storage import MessageArchiveStorage


def _mk_dt(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, UTC)


class ExportStorageTest(unittest.TestCase):
    def setUp(self) -> None:
        self._account = "testacc1"
        self._remote_jid = JID.from_string("remote@jid.org")
        app.settings = Settings(in_memory=True)
        app.settings.init()
        app.settings.add_account(self._account)
        app.settings.set_account_setting(self._account, "address", "user@domain.org")
        self._archive = MessageArchiveStorage(in_memory=True)
        self._archive.init()

    def tearDown(self) -> None:
        self._archive.shutdown()

    def _make_message(
        self,
        msg_id: str,
        ts: int,
        text: str = "hello",
        correction_id: str | None = None,
    ) -> Message:
        return Message(
            account_=self._account,
            remote_jid_=self._remote_jid,
            resource="res",
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=_mk_dt(ts),
            state=MessageState.ACKNOWLEDGED,
            id=msg_id,
            stanza_id=msg_id,
            text=text,
            correction_id=correction_id,
        )

    def _export(self) -> list[Message]:
        return list(
            self._archive.get_messages_for_export(self._account, self._remote_jid)
        )

    def test_returns_messages_in_timestamp_order(self) -> None:
        self._archive.insert_object(self._make_message("m3", ts=30, text="third"))
        self._archive.insert_object(self._make_message("m1", ts=10, text="first"))
        self._archive.insert_object(self._make_message("m2", ts=20, text="second"))

        msgs = self._export()
        self.assertEqual(len(msgs), 3)
        self.assertEqual(msgs[0].text, "first")
        self.assertEqual(msgs[1].text, "second")
        self.assertEqual(msgs[2].text, "third")

    def test_excludes_correction_entries(self) -> None:
        # The original message must appear; the correction entry must not.
        self._archive.insert_object(self._make_message("orig", ts=1, text="original"))
        self._archive.insert_object(
            self._make_message("corr", ts=2, text="edited", correction_id="orig")
        )

        msgs = self._export()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].id, "orig")

    def test_excludes_moderated_messages(self) -> None:
        self._archive.insert_object(self._make_message("m1", ts=1, text="keep"))
        self._archive.insert_object(self._make_message("m2", ts=2, text="moderated"))

        self._archive.insert_row(
            Moderation(
                account_=self._account,
                remote_jid_=self._remote_jid,
                occupant_=None,
                stanza_id="m2",
                by=JID.from_string("mod@jid.org"),
                reason="spam",
                timestamp=_mk_dt(3),
            ),
            ignore_on_conflict=True,
        )

        msgs = self._export()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].id, "m1")

    def test_excludes_retracted_messages(self) -> None:
        self._archive.insert_object(self._make_message("m1", ts=1, text="keep"))
        self._archive.insert_object(self._make_message("m2", ts=2, text="retracted"))

        self._archive.insert_row(
            Retraction(
                account_=self._account,
                remote_jid_=self._remote_jid,
                occupant_=None,
                id="m2",
                direction=ChatDirection.INCOMING,
                timestamp=_mk_dt(3),
            ),
            ignore_on_conflict=True,
        )

        msgs = self._export()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].id, "m1")

    def test_eager_loads_oob(self) -> None:
        # OOB must be accessible after the session closes (no lazy-load).
        msg = self._make_message("m1", ts=1)
        msg.oob = [OOB(url="https://example.com/file.jpg", description="img")]
        self._archive.insert_object(msg)

        msgs = self._export()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(len(msgs[0].oob), 1)
        self.assertEqual(msgs[0].oob[0].url, "https://example.com/file.jpg")

    def test_scoped_to_jid(self) -> None:
        # Messages for a different JID must not appear.
        other_jid = JID.from_string("other@jid.org")

        self._archive.insert_object(self._make_message("m1", ts=1, text="mine"))

        other_msg = Message(
            account_=self._account,
            remote_jid_=other_jid,
            resource="res",
            type=MessageType.CHAT,
            direction=ChatDirection.INCOMING,
            timestamp=_mk_dt(2),
            state=MessageState.ACKNOWLEDGED,
            id="m2",
            stanza_id="m2",
            text="other",
        )
        self._archive.insert_object(other_msg)

        msgs = self._export()
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].id, "m1")

    def test_empty_when_no_messages(self) -> None:
        self.assertEqual(self._export(), [])

    def test_get_uuid_uniqueness(self) -> None:
        # Inserting multiple messages each with a unique id should all appear.
        for i in range(5):
            self._archive.insert_object(
                self._make_message(get_uuid(), ts=i, text=f"msg{i}")
            )

        msgs = self._export()
        self.assertEqual(len(msgs), 5)


if __name__ == "__main__":
    unittest.main()
