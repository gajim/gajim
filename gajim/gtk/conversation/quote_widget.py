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

from typing import Optional

from gi.repository import Gtk

from .message_widget import MessageWidget


class QuoteWidget(Gtk.Box):
    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self)
        self.set_vexpand(True)
        self.get_style_context().add_class('conversation-quote')
        quote_bar = Gtk.Box()
        quote_bar.set_size_request(3, -1)
        quote_bar.set_margin_end(6)
        quote_bar.get_style_context().add_class('conversation-quote-bar')
        self.add(quote_bar)

        self._account = account

        self._message_widget: Optional[MessageWidget] = None

    def attach_message_widget(self, message_widget: MessageWidget) -> None:
        # Purpose of this method is to prevent circular imports
        if self._message_widget is not None:
            raise ValueError(
                'QuoteWidget already has a MessageWidget attached')
        self._message_widget = message_widget
        self.add(message_widget)
