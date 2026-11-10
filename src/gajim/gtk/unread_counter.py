# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
from collections import defaultdict

from gi.repository import GLib

from gajim.common import app
from gajim.common.helpers import timeout_add_once

log = logging.getLogger("gajim.gtk.unread_counter")


class Counter:
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
        return updated


class UnreadCounter:
    def __init__(self) -> None:
        self._workspaces: dict[str, Counter] = defaultdict(Counter)
        self._global = Counter()

        self._signal_id: int | None = None
        self._signal_data: dict[str, int] = {}

    @property
    def total(self) -> int:
        return self._global.count

    def shutdown(self) -> None:
        if self._signal_id is not None:
            GLib.source_remove(self._signal_id)

    def workspace_count(self, workspace_id: str) -> int:
        return self._workspaces[workspace_id].count

    def apply(self, workspace_id: str, delta: int) -> int:
        workspace = self._workspaces[workspace_id]
        before = workspace.count
        after = workspace.apply(delta)
        # Apply the clamped change. Passing the requested delta would
        # desync the global total when a workspace count hits zero.
        self._global.apply(after - before)
        if after == 0:
            del self._workspaces[workspace_id]
        return after

    def update(self, workspace_id: str, count: int) -> None:
        self._count_message(workspace_id, count)

    def _emit_delayed(self, workspace_id: str, count: int) -> None:
        if self._signal_id is not None:
            self._signal_data[workspace_id] = count
            return

        self._signal_id = timeout_add_once(1_000, self._emit)

    def _emit(self) -> None:
        self._signal_id = None
        for workspace_id, count in self._signal_data.items():
            log.debug("Emit unread-count-changed for %s %s", workspace_id, count)
            app.window.emit("unread-count-changed", workspace_id, count)

        self._signal_data.clear()

    def _count_message(self, workspace_id: str, delta: int) -> None:
        count = self.apply(workspace_id, delta)
        log.debug(
            "Unread %s %+d -> %d (global %d)",
            workspace_id,
            delta,
            count,
            self.total,
        )
        self._emit_delayed(workspace_id, count)
