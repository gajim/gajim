# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.events import MessageRead
from gajim.common.events import MessageUnread

from gajim.gtk.unread_counter import UnreadCounter
from gajim.gtk.unread_counter import UnreadCounters


class UnreadCounterTest(unittest.TestCase):
    def test_apply_and_clamp(self) -> None:
        counter = UnreadCounter()
        self.assertEqual(counter.apply(2), 2)
        self.assertEqual(counter.apply(-1), 1)
        self.assertEqual(counter.apply(-5), 0)
        self.assertEqual(counter.count, 0)

    def test_workspace_and_global_counters(self) -> None:
        window = MagicMock()
        app.window = window
        counters = UnreadCounters()
        jid = JID.from_string("room@conference.example")
        try:
            for _ in range(3):
                app.ged.raise_event(
                    MessageUnread(
                        account="test",
                        jid=jid,
                        workspace_id="workspace-a",
                    )
                )
            for _ in range(4):
                app.ged.raise_event(
                    MessageUnread(
                        account="test",
                        jid=jid,
                        workspace_id="workspace-b",
                    )
                )

            self.assertEqual(counters.workspace_count("workspace-a"), 3)
            self.assertEqual(counters.workspace_count("workspace-b"), 4)
            self.assertEqual(counters.total, 7)

            for _ in range(3):
                app.ged.raise_event(
                    MessageRead(
                        account="test",
                        jid=jid,
                        workspace_id="workspace-a",
                    )
                )
            self.assertEqual(counters.workspace_count("workspace-a"), 0)
            self.assertEqual(counters.total, 4)
            window.emit.assert_called_with("unread-count-changed", "workspace-a", 0)
        finally:
            counters.unregister_events()
            del app.window
