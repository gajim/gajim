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
from gajim.common.i18n import _
from gajim.common.styling import process

from .base import BaseRow
from ..message_widget import MessageWidget


class MUCSubject(BaseRow):

    type = 'muc-subject'

    def __init__(self, account, text, nick, date):
        BaseRow.__init__(self, account)

        timestamp = time.time()
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp

        text = GLib.markup_escape_text(text)

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 2)

        subject_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        subject_box.get_style_context().add_class('conversation-subject-box')
        subject_box.get_style_context().add_class('gajim-status-message')

        title = Gtk.Label(label=_('Subject'))
        title.set_halign(Gtk.Align.START)
        title.get_style_context().add_class('bold')
        subject_box.add(title)

        meta_str = _('Changed by %s') % nick
        if date is not None:
            meta_str = f'{meta_str} ({date})'
        meta = Gtk.Label(label=meta_str)
        meta.set_halign(Gtk.Align.START)
        meta.get_style_context().add_class('small-label')
        subject_box.add(meta)

        result = process(text)
        message_widget = MessageWidget(account)
        message_widget.add_content(result)
        subject_box.add(message_widget)
        self.grid.attach(subject_box, 1, 0, 1, 1)

        timestamp_widget = self.create_timestamp_widget(self.timestamp)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 2, 0, 1, 1)

        self.show_all()
