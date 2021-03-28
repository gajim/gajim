# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.


from gi.repository import Gtk

from .base import BaseRow


class DateRow(BaseRow):
    def __init__(self, account, date_string, timestamp):
        BaseRow.__init__(self, account)
        self.type = 'date'
        self.timestamp = timestamp
        self.get_style_context().add_class('conversation-date-row')

        self.label.set_text(date_string)
        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_hexpand(True)
        self.label.get_style_context().add_class('conversation-meta')
        self.grid.attach(self.label, 0, 0, 1, 1)
