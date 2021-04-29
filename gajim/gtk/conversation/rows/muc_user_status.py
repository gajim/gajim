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

from gajim.common.i18n import _
from gajim.common.const import AvatarSize
from gajim.common import helpers

from .widgets import SimpleLabel
from .base import BaseRow


class MUCUserStatus(BaseRow):
    def __init__(self, account, user_contact, is_self):
        BaseRow.__init__(self, account)

        self.type = 'muc-user-status'
        timestamp = time.time()
        self.timestamp = datetime.fromtimestamp(timestamp)
        self.db_timestamp = timestamp

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        icon_name = 'feather-info-symbolic'
        icon = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        self.grid.attach(icon, 1, 0, 1, 1)

        self._label = SimpleLabel()
        self._label.set_text(self._make_text(user_contact, is_self))
        self._label.get_style_context().add_class('gajim-status-message')
        self.grid.attach(self._label, 2, 0, 1, 1)

        timestamp_widget = self.create_timestamp_widget(self.timestamp)
        timestamp_widget.set_hexpand(True)
        timestamp_widget.set_halign(Gtk.Align.END)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 3, 0, 1, 1)

        self.show_all()

    @staticmethod
    def _make_text(user_contact, is_self):
        nick = user_contact.name
        status = user_contact.status
        status = '' if status is None else ' - %s' % status
        show = helpers.get_uf_show(user_contact.show.value)

        if is_self:
            message = _('You are now {show}{status}').format(show=show,
                                                             status=status)

        else:
            message = _('{nick} is now {show}{status}').format(nick=nick,
                                                               show=show,
                                                               status=status)
        return message
