# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk

from gajim.common.const import AvatarSize
from gajim.common.helpers import get_uf_show
from gajim.common.i18n import _
from gajim.common.util.datetime import utc_now

from gajim.gtk.avatar import get_show_circle
from gajim.gtk.conversation.message_widget import MessageWidget
from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import DateTimeLabel
from gajim.gtk.conversation.rows.widgets import SimpleLabel


class UserStatus(BaseRow):
    def __init__(self,
                 account: str,
                 name: str,
                 show: str,
                 status: str | None) -> None:

        BaseRow.__init__(self, account)

        self.type = 'muc-user-status'
        timestamp = utc_now()
        self.timestamp = timestamp.astimezone()
        self.db_timestamp = timestamp.timestamp()

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        show_icon = Gtk.Image()
        show_icon.set_opacity(0.6)
        surface = get_show_circle(show, 16, self.get_scale_factor())
        show_icon.set_from_surface(surface)
        self.grid.attach(show_icon, 1, 0, 1, 1)

        show = get_uf_show(show)

        message = _('{nick} is now {show}').format(nick=name, show=show)

        self._label = SimpleLabel()
        self._label.set_text(message)
        self._label.get_style_context().add_class('gajim-status-message')
        self.grid.attach(self._label, 2, 0, 1, 1)

        if status is not None:
            message_widget = MessageWidget(account)
            message_widget.get_style_context().add_class('gajim-status-message')
            message_widget.add_with_styling(status)
            self.grid.attach(message_widget, 2, 1, 1, 1)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_halign(Gtk.Align.START)
        timestamp_widget.set_valign(Gtk.Align.END)
        self.grid.attach(timestamp_widget, 3, 0, 1, 1)

        self.show_all()
