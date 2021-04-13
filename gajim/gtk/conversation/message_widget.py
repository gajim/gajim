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

from .code_widget import CodeWidget
from .quote_widget import QuoteWidget
from .plain_widget import PlainWidget


class MessageWidget(Gtk.Box):
    def __init__(self, account):
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self._account = account

    def add_content(self, blocks):
        for block in blocks:
            if block.name == 'plain':
                widget = PlainWidget(self._account)
                widget.add_content(block)
                self.add(widget)
                continue

            if block.name == 'pre':
                widget = CodeWidget(self._account)
                widget.add_content(block)
                self.add(widget)
                continue

            if block.name == 'quote':
                message_widget = MessageWidget(self._account)
                message_widget.add_content(block.blocks)
                widget = QuoteWidget(self._account)
                widget.attach_message_widget(message_widget)
                self.add(widget)
                continue
