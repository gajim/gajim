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

import time
from datetime import datetime

from gi.repository import Gtk

from gajim.common.i18n import _
from gajim.common.const import AvatarSize

from .widgets import SimpleLabel
from .base import BaseRow


class MUCJoinLeft(BaseRow):
    def __init__(self, type_: str, account: str, nick: str,
                 reason: Optional[str] = None,
                 error: bool = False):
        BaseRow.__init__(self, account)

        self.type = type_
        timestamp = time.time()
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        if type_ == 'muc-user-joined':
            text = self._make_join_message(nick)
            icon_name = 'feather-log-in-symbolic'
            icon_class = 'gajim-user-connected'
        else:
            text = self._make_left_message(nick, reason, error)
            icon_name = 'feather-log-out-symbolic'
            icon_class = 'gajim-user-disconnected'

        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        icon.get_style_context().add_class(icon_class)
        self.grid.attach(icon, 1, 0, 1, 1)

        self._label = SimpleLabel()
        self._label.set_text(text)
        self._label.get_style_context().add_class('gajim-status-message')
        self.grid.attach(self._label, 2, 0, 1, 1)

        timestamp_widget = self.create_timestamp_widget(self.timestamp)
        timestamp_widget.set_halign(Gtk.Align.START)
        timestamp_widget.set_valign(Gtk.Align.FILL)
        self.grid.attach(timestamp_widget, 3, 0, 1, 1)

        self.show_all()

    @staticmethod
    def _make_left_message(nick: str, reason: Optional[str],
                           error: bool) -> str:
        reason = '' if reason is None else f': {reason}'

        if error:
            # Group Chat: User was kicked because of an server error: reason
            message = _('{nick} has left due to an error{reason}').format(
                nick=nick, reason=reason)

        else:
            message = _('{nick} has left{reason}').format(nick=nick,
                                                          reason=reason)
        return message

    @staticmethod
    def _make_join_message(nick: str) -> str:
        return _('%s has joined') % nick
