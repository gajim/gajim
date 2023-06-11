# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from datetime import datetime

from gi.repository import Gtk

from gajim.common.const import AvatarSize
from gajim.common.util.datetime import utc_now

from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import DateTimeLabel
from gajim.gtk.conversation.rows.widgets import SimpleLabel


class InfoMessage(BaseRow):
    def __init__(self,
                 account: str,
                 text: str,
                 timestamp: datetime | None
                 ) -> None:

        BaseRow.__init__(self, account)

        self.type = 'info'

        if timestamp is None:
            timestamp = utc_now()
        self.timestamp = timestamp.astimezone()
        self.db_timestamp = timestamp.timestamp()

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        icon = Gtk.Image.new_from_icon_name('feather-info-symbolic',
                                            Gtk.IconSize.MENU)
        icon.get_style_context().add_class('gajim-status-message')
        self.grid.attach(icon, 1, 0, 1, 1)

        self._label = SimpleLabel()
        self._label.get_style_context().add_class('gajim-status-message')
        self._label.set_text(text)
        self.grid.attach(self._label, 2, 0, 1, 1)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_halign(Gtk.Align.START)
        timestamp_widget.set_valign(Gtk.Align.END)
        self.grid.attach(timestamp_widget, 3, 0, 1, 1)

        self.show_all()
