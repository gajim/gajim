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

from __future__ import annotations

from typing import Optional

from datetime import datetime

from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app


class BaseRow(Gtk.ListBoxRow):
    def __init__(self, account: str, widget: Optional[str] = None) -> None:
        Gtk.ListBoxRow.__init__(self)
        self._account = account
        self._client = app.get_client(account)
        self.type: str = ''
        self.timestamp: datetime = datetime.fromtimestamp(0)
        self.kind: str = ''
        self.name: str = ''
        self.message_id: Optional[str] = None
        self.log_line_id: Optional[int] = None
        self.stanza_id: Optional[str] = None
        self.text: str = ''
        self._merged: bool = False

        self.set_selectable(False)
        self.set_can_focus(False)
        self.get_style_context().add_class('conversation-row')

        self.grid = Gtk.Grid(row_spacing=3, column_spacing=12)
        self.add(self.grid)

        if widget == 'label':
            self.label = Gtk.Label()
            self.label.set_selectable(True)
            self.label.set_line_wrap(True)
            self.label.set_xalign(0)
            self.label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        self.connect('destroy', self.__destroy)

    def enable_selection_mode(self) -> None:
        return

    def disable_selection_mode(self) -> None:
        return

    @property
    def is_merged(self) -> bool:
        return self._merged

    @staticmethod
    def __destroy(widget: Gtk.Widget) -> None:
        app.check_finalize(widget)
