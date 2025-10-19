# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from gi.repository import Gtk

import gajim.common.storage.archive.models as mod

from gajim.gtk.conversation.avatar_stack import AvatarStack
from gajim.gtk.conversation.rows.base import BaseRow


class DisplayedRow(BaseRow):
    def __init__(
        self, account: str, timestamp: datetime, markers: list[mod.DisplayedMarker]
    ) -> None:
        BaseRow.__init__(self, account)
        self.remove_css_class("conversation-row")
        self.set_activatable(False)
        self.type = "read_marker"
        self.timestamp = timestamp + timedelta(microseconds=1)

        # Copy markers because we modify the list later
        self._markers = markers.copy()
        self._avatar_stack = AvatarStack()
        self.grid.attach(self._avatar_stack, 0, 0, 1, 1)
        self.grid.set_halign(Gtk.Align.END)

        self._update_state()

    def add_marker(self, marker: mod.DisplayedMarker) -> None:
        self._markers.append(marker)
        self._update_state()

    def remove_marker(self, marker: mod.DisplayedMarker) -> None:
        for m in self._markers:
            assert m.occupant is not None
            assert marker.occupant is not None
            if m.occupant.id != marker.occupant.id:
                continue

            self._markers.remove(m)
            self._update_state()
            return

    def _update_state(self) -> None:
        self._avatar_stack.set_data(self._markers)
        self.set_visible(bool(self._markers))
