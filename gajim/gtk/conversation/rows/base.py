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

from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.helpers import from_one_line


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

    @property
    def is_merged(self) -> bool:
        return self._merged

    def update_text_tags(self) -> None:
        pass

    @staticmethod
    def create_timestamp_widget(timestamp: datetime) -> Gtk.Label:
        time_format = from_one_line(app.settings.get('chat_timestamp_format'))
        timestamp_formatted = timestamp.strftime(time_format)
        label = Gtk.Label(label=timestamp_formatted)
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.END)
        label.set_margin_end(6)
        label.get_style_context().add_class('conversation-meta')
        label.set_tooltip_text(timestamp.strftime('%a, %d %b %Y - %X'))
        return label

    @staticmethod
    def create_name_widget(name: str, is_self: bool) -> Gtk.Label:
        label = Gtk.Label()
        label.set_selectable(True)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.get_style_context().add_class('conversation-nickname')
        label.set_markup(GLib.markup_escape_text(name))

        if is_self:
            label.get_style_context().add_class('gajim-outgoing-nickname')
        else:
            label.get_style_context().add_class('gajim-incoming-nickname')
        return label

    @staticmethod
    def __destroy(widget: Gtk.Widget) -> None:
        app.check_finalize(widget)
