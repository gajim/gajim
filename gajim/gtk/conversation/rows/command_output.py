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

import time
from datetime import datetime

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common.const import AvatarSize

from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import DateTimeLabel
from gajim.gtk.conversation.rows.widgets import SimpleLabel


class CommandOutputRow(BaseRow):
    def __init__(self, account: str, text: str, is_error: bool) -> None:
        BaseRow.__init__(self, account)

        self.type = 'command_output'
        timestamp = time.time()
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp

        self.get_style_context().add_class('conversation-command-row')

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        icon = Gtk.Image.new_from_icon_name('utilities-terminal-symbolic',
                                            Gtk.IconSize.LARGE_TOOLBAR)
        icon.get_style_context().add_class('dim-label')
        avatar_placeholder.add(icon)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_valign(Gtk.Align.START)
        timestamp_widget.set_margin_start(0)
        self.grid.attach(timestamp_widget, 1, 0, 1, 1)

        text = GLib.markup_escape_text(text)
        markup = f'<tt>{text}</tt>'
        self._label = SimpleLabel()
        if is_error:
            self._label.get_style_context().add_class('gajim-command-error')
        else:
            self._label.get_style_context().add_class('gajim-command-output')
        self._label.set_markup(markup)
        self.grid.attach(self._label, 1, 1, 1, 1)

        self.show_all()
