# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from gi.repository import Gtk

from gajim.common.i18n import _
from gajim.common.types import ChatContactT
from gajim.common.util.datetime import FIRST_LOCAL_DATETIME
from gajim.common.util.text import process_non_spacing_marks

from gajim.gtk.conversation.rows.base import BaseRow


class ReadMarkerRow(BaseRow):
    def __init__(self, contact: ChatContactT) -> None:
        BaseRow.__init__(self, contact.account, widget="label")
        self.set_activatable(False)
        self.type = "read_marker"
        self.timestamp = FIRST_LOCAL_DATETIME
        self._last_incoming_timestamp = FIRST_LOCAL_DATETIME

        self._contact = contact
        self._contact.connect("nickname-update", self._on_nickname_update)

        text = _("%s has read up to this point") % contact.name
        self.label.set_text(process_non_spacing_marks(text))
        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_hexpand(True)
        self.label.set_sensitive(False)
        self.label.add_css_class("conversation-read-marker")
        self.grid.attach(self.label, 0, 0, 1, 1)
        self.set_visible(False)

    def _on_nickname_update(self, contact: ChatContactT, _signal_name: str) -> None:
        text = _("%s has read up to this point") % contact.name
        self.label.set_text(process_non_spacing_marks(text))

    def set_timestamp(self, timestamp: datetime, force: bool = False) -> None:
        if timestamp <= self._last_incoming_timestamp and not force:
            return

        self.timestamp = timestamp

        self.changed()
        self.show()

    def set_last_incoming_timestamp(self, timestamp: datetime) -> None:
        if timestamp > self._last_incoming_timestamp:
            self._last_incoming_timestamp = timestamp + timedelta(microseconds=1)

    def do_unroot(self) -> None:
        self._contact.disconnect_all_from_obj(self)
        BaseRow.do_unroot(self)
