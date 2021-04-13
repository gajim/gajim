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


class QuoteWidget(Gtk.Box):
    def __init__(self, account):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_vexpand(True)

        self._account = account

        self._message_widget = None

    def attach_message_widget(self, message_widget):
        # Purpose of this method is to prevent circular imports
        if self._message_widget is not None:
            raise ValueError('QuoteWidget already has a MessageWidget attached')
        self._message_widget = message_widget
        self.add(message_widget)
