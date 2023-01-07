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

from datetime import datetime

from gi.repository import Gtk

from gajim.common.i18n import _

from gajim.gtk.conversation.rows.base import BaseRow


class ScrollHintRow(BaseRow):
    def __init__(self, account: str) -> None:
        BaseRow.__init__(self, account, widget='label')
        self.set_selectable(False)
        self.set_activatable(False)

        self.type = 'system'
        self.timestamp = datetime.fromtimestamp(0)

        self.get_style_context().add_class('conversation-system-row')

        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_hexpand(True)
        self.label.get_style_context().add_class(
            'conversation-meta')
        self.grid.attach(self.label, 0, 1, 1, 1)

        self.set_history_complete(False)
        self.show_all()

    def set_history_complete(self, complete: bool) -> None:
        if complete:
            self.label.set_text(_('There is no more history'))
        else:
            self.label.set_text(_('Scroll up to load more chat history…'))
