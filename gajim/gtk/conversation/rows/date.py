# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from datetime import datetime

from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.conversation.rows.base import BaseRow


class DateRow(BaseRow):
    def __init__(self, account: str, timestamp: datetime) -> None:
        BaseRow.__init__(self, account, widget='label')

        self.set_selectable(False)
        self.set_activatable(False)

        self.type = 'date'
        self.timestamp = timestamp
        self.get_style_context().add_class('conversation-date-row')

        format_string = app.settings.get('date_format')
        self.label.set_text(timestamp.strftime('%a ' + format_string))
        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_hexpand(True)
        self.label.get_style_context().add_class('conversation-meta')
        self.grid.attach(self.label, 0, 0, 1, 1)

        self.show_all()
