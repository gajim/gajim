# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.ged import EventHelper

log = logging.getLogger("gajim.gtk.unread_counter")


class UnreadCounter:
    """Running total of unread messages that count toward a badge."""

    def __init__(self) -> None:
        self.count = 0

    def apply(self, delta: int) -> int:
        updated = self.count + delta
        if updated < 0:
            log.warning(
                "Unread counter went negative (%s%+d); clamping to zero",
                self.count,
                delta,
            )
            updated = 0
        self.count = updated
        return self.count


class UnreadCounters(EventHelper):
    """Per-workspace unread counters and the global counter.

    A chat emits ``message-unread`` or ``message-read`` for each message that
    starts or stops counting. These counters add or subtract one. They do not
    scan the chat list.
    """

    def __init__(self) -> None:
        EventHelper.__init__(self)

        self._workspaces: dict[str, UnreadCounter] = {}
        self._global = UnreadCounter()

        self.register_events(
            [
                ("message-unread", ged.GUI1, self._on_message_unread),
                ("message-read", ged.GUI1, self._on_message_read),
            ]
        )

    @property
    def total(self) -> int:
        return self._global.count

    def workspace_count(self, workspace_id: str) -> int:
        counter = self._workspaces.get(workspace_id)
        if counter is None:
            return 0
        return counter.count

    def apply(self, workspace_id: str, delta: int) -> int:
        workspace = self._workspaces.get(workspace_id)
        if workspace is None:
            workspace = UnreadCounter()
            self._workspaces[workspace_id] = workspace

        before = workspace.count
        after = workspace.apply(delta)
        # Use the applied change so clamping cannot desync the global total.
        self._global.apply(after - before)
        if after == 0:
            self._workspaces.pop(workspace_id, None)
        return after

    def _on_message_unread(self, event: events.MessageUnread) -> None:
        self._count_message(event.workspace_id, event.jid, 1)

    def _on_message_read(self, event: events.MessageRead) -> None:
        self._count_message(event.workspace_id, event.jid, -1)

    def _count_message(self, workspace_id: str, jid: JID, delta: int) -> None:
        count = self.apply(workspace_id, delta)
        log.debug(
            "Unread %s %+d -> %d (global %d) from %s",
            workspace_id,
            delta,
            count,
            self.total,
            jid,
        )
        app.window.emit("unread-count-changed", workspace_id, count)
