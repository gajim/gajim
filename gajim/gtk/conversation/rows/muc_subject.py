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

import time
from datetime import datetime

from gi.repository import Gtk
from nbxmpp.structs import MucSubject

from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from gajim.gtk.conversation.message_widget import MessageWidget
from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import DateTimeLabel


class MUCSubject(BaseRow):

    type = 'muc-subject'

    def __init__(self,
                 account: str,
                 subject: MucSubject,
                 timestamp: float | None = None
                 ) -> None:

        BaseRow.__init__(self, account)

        current_timestamp = timestamp or time.time()
        self.timestamp = datetime.fromtimestamp(current_timestamp)
        self.db_timestamp = current_timestamp

        self.grid.set_halign(Gtk.Align.START)

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 2)

        subject_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        subject_box.set_halign(Gtk.Align.START)
        subject_box.get_style_context().add_class('conversation-subject-box')
        subject_box.get_style_context().add_class('gajim-subject-message')

        title = Gtk.Label(label=_('Subject'))
        title.set_halign(Gtk.Align.START)
        title.get_style_context().add_class('bold')
        subject_box.add(title)

        author = _('Changed by %s') % (subject.author or _('Unknown'))

        date = ''
        if subject.timestamp is not None:
            time_str = time.strftime('%c', time.localtime(subject.timestamp))
            date = f' ({time_str})'

        meta_str = f'{author}{date}'
        meta = Gtk.Label(label=meta_str)
        meta.set_halign(Gtk.Align.START)
        meta.set_selectable(True)
        meta.get_style_context().add_class('small-label')
        subject_box.add(meta)

        message_widget = MessageWidget(account)
        message_widget.add_with_styling(subject.text)
        subject_box.add(message_widget)
        self.grid.attach(subject_box, 1, 0, 1, 1)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 2, 0, 1, 1)

        self.show_all()
