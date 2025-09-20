# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from gi.repository import Gtk

from gajim.common.modules.chat_markers import DisplayedMarkerData

from gajim.gtk.conversation.avatar_stack import AvatarStack
from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.widgets import TimeLabel


class DisplayedRow(BaseRow):
    def __init__(
        self, account: str, timestamp: datetime, markers: list[DisplayedMarkerData]
    ) -> None:
        BaseRow.__init__(self, account)
        self.remove_css_class("conversation-row")
        self.set_activatable(False)
        self.type = "displayed_marker"
        self.timestamp = timestamp + timedelta(microseconds=1)

        # Copy markers because we modify the list later
        self._markers = markers.copy()
        self._avatar_stack = AvatarStack(self._account)

        self._timestamp_label = TimeLabel()
        self._timestamp_label.add_css_class("caption")
        self._timestamp_label.add_css_class("dimmed")

        self.grid.attach(self._timestamp_label, 0, 0, 1, 1)
        self.grid.attach(self._avatar_stack, 1, 0, 1, 1)
        self.grid.set_halign(Gtk.Align.END)
        self.grid.set_column_spacing(6)

        self._update_state()

    def do_unroot(self) -> None:
        BaseRow.do_unroot(self)
        del self._timestamp_label
        del self._avatar_stack

    def has_markers(self) -> bool:
        return bool(self._markers)

    def add_markers(self, markers: list[DisplayedMarkerData]) -> None:
        for marker in markers:
            self._markers.append(marker)
        self._update_state()

    def remove_marker(self, marker: DisplayedMarkerData) -> None:
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
        single_marker = len(self._markers) == 1
        if single_marker:
            marker = self._markers[0]
            self._timestamp_label.set_timestamp(marker.timestamp)

        self._timestamp_label.set_visible(single_marker)
        self.set_visible(bool(self._markers))
