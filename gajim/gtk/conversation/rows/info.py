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

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from .base import BaseRow


class InfoMessageRow(BaseRow):
    def __init__(self,
                 account,
                 timestamp,
                 text,
                 other_text_tags,
                 kind,
                 subject,
                 graphics,
                 history_mode=False):
        BaseRow.__init__(self, account, widget='textview',
                         history_mode=history_mode)
        self.type = 'info'
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp
        self.kind = kind

        if subject:
            subject_title = _('Subject:')
            text = (f'{subject_title}\n'
                    f'{GLib.markup_escape_text(subject)}\n'
                    f'{GLib.markup_escape_text(text)}')
        else:
            text = GLib.markup_escape_text(text)

        other_text_tags.append('status')

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 2)
        timestamp_widget = self.create_timestamp_widget(self.timestamp)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 2, 0, 1, 1)

        self.textview.set_justification(Gtk.Justification.CENTER)
        self.textview.print_text(
            text,
            other_text_tags=other_text_tags,
            kind=kind,
            graphics=graphics)

        self.grid.attach(self.textview, 1, 0, 1, 1)
