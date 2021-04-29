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

from gi.repository import Gtk
from gi.repository import Pango

from gajim.common.i18n import _
from gajim.common.const import AvatarSize

from .base import BaseRow


class MUCJoinLeft(BaseRow):
    def __init__(self, type_, account, nick, reason=None, error=False):
        BaseRow.__init__(self, account)

        self.type = type_
        timestamp = time.time()
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp

        self._label = Gtk.Label()
        self._label.set_selectable(True)
        self._label.set_line_wrap(True)
        self._label.set_xalign(0)
        self._label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        if type_ == 'muc-user-joined':
            text = self._make_join_message(nick)
        else:
            text = self._make_left_message(nick, reason, error)

        self._label.set_text(text)

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 2)
        timestamp_widget = self.create_timestamp_widget(self.timestamp)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 2, 0, 1, 1)

        self.grid.attach(self._label, 1, 0, 1, 1)
        self.show_all()

    @staticmethod
    def _make_left_message(nick, reason, error):
        reason = '' if reason is None else ': {reason}'.format(reason=reason)

        if error:
            #Group Chat: User was kicked because of an server error: reason
            message = _('{nick} has left due to '
                        'an error{reason}').format(nick=nick, reason=reason)

        else:
            message = _('{nick} has left{reason}').format(nick=nick,
                                                          reason=reason)
        return message

    @staticmethod
    def _make_join_message(nick):
        return _('%s has joined the group chat') % nick
