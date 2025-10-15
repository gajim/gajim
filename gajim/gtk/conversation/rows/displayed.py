# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from gi.repository import Gtk

import gajim.common.storage.archive.models as mod
from gajim.common.i18n import _
from gajim.common.util.text import process_non_spacing_marks

from gajim.gtk.conversation.rows.base import BaseRow


class DisplayedRow(BaseRow):
    def __init__(
        self, account: str, timestamp: datetime, markers: list[mod.DisplayedMarker]
    ) -> None:
        BaseRow.__init__(self, account, widget="label")
        self.set_activatable(False)
        self.type = "read_marker"
        self.timestamp = timestamp + timedelta(microseconds=1)

        # Copy markers because we modify the list later
        self._markers = markers.copy()

        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_hexpand(True)
        self.label.set_sensitive(False)
        self.label.add_css_class("conversation-read-marker")
        self.grid.attach(self.label, 0, 0, 1, 1)

        self._update_state()

    def add_marker(self, marker: mod.DisplayedMarker) -> None:
        self._markers.append(marker)
        self._update_state()

    def remove_marker(self, marker: mod.DisplayedMarker) -> None:
        for m in self._markers:
            if m.occupant.id != marker.occupant.id:
                continue

            self._markers.remove(m)
            self._update_state()
            return

    def _update_state(self) -> None:
        text = _("Row read by ")
        text += ", ".join([m.occupant.nickname for m in self._markers])
        self.label.set_text(process_non_spacing_marks(text))
        self.set_visible(bool(self._markers))
