# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.ged import EventHelper

log = logging.getLogger("gajim.gtk.unread_counter")


class UnreadCounter:
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
        return counter.count if counter is not None else 0

    def apply(self, workspace_id: str, delta: int) -> int:
        workspace = self._workspaces.setdefault(workspace_id, UnreadCounter())
        before = workspace.count
        after = workspace.apply(delta)
        # Apply the clamped change. Passing the requested delta would
        # desync the global total when a workspace count hits zero.
        self._global.apply(after - before)
        if after == 0:
            del self._workspaces[workspace_id]
        return after

    def _on_message_unread(self, event: events.MessageUnread) -> None:
        self._count_message(event.workspace_id, 1)

    def _on_message_read(self, event: events.MessageRead) -> None:
        self._count_message(event.workspace_id, -1)

    def _count_message(self, workspace_id: str, delta: int) -> None:
        count = self.apply(workspace_id, delta)
        log.debug(
            "Unread %s %+d -> %d (global %d)",
            workspace_id,
            delta,
            count,
            self.total,
        )
        app.window.emit("unread-count-changed", workspace_id, count)
