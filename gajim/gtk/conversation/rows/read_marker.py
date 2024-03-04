# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from gi.repository import Gtk

from gajim.common.i18n import _
from gajim.common.types import ChatContactT

from gajim.gtk.conversation.rows.base import BaseRow


class ReadMarkerRow(BaseRow):
    def __init__(self, contact: ChatContactT) -> None:
        BaseRow.__init__(self, contact.account, widget='label')
        self.set_activatable(False)
        self.type = 'read_marker'
        self.timestamp = datetime.fromtimestamp(0)
        self._last_incoming_timestamp = datetime.fromtimestamp(0)

        contact.connect('nickname-update', self._on_nickname_update)

        text = _('%s has read up to this point') % contact.name
        self.label.set_text(text)
        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_hexpand(True)
        self.label.set_sensitive(False)
        self.label.get_style_context().add_class(
            'conversation-read-marker')
        self.grid.attach(self.label, 0, 0, 1, 1)
        self.set_no_show_all(True)

    def _on_nickname_update(self,
                            contact: ChatContactT,
                            _signal_name: str
                            ) -> None:
        text = _('%s has read up to this point') % contact.name
        self.label.set_text(text)

    def set_timestamp(self, timestamp: datetime) -> None:
        if timestamp <= self._last_incoming_timestamp:
            return

        self.timestamp = timestamp

        self.changed()
        self.set_no_show_all(False)
        self.show_all()

    def set_last_incoming_timestamp(self, timestamp: datetime) -> None:
        if timestamp > self._last_incoming_timestamp:
            self._last_incoming_timestamp = timestamp + timedelta(
                microseconds=1)
