# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from datetime import datetime

from gi.repository import Gtk

from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.util.datetime import utc_now
from gajim.common.util.text import process_non_spacing_marks

from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import DateTimeLabel
from gajim.gtk.conversation.rows.widgets import SimpleLabel


class MUCJoinLeft(BaseRow):
    def __init__(
        self,
        type_: str,
        account: str,
        nick: str,
        reason: str | None = None,
        error: bool = False,
        timestamp: datetime | None = None,
    ) -> None:

        BaseRow.__init__(self, account)

        self.type = type_
        if timestamp is None:
            timestamp = utc_now()
        self.timestamp = timestamp.astimezone()
        self.db_timestamp = timestamp.timestamp()

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 1)

        if type_ == "muc-user-joined":
            text = self._make_join_message(nick)
            icon_name = "lucide-log-in-symbolic"
            icon_class = "gajim-user-connected"
        else:
            text = self._make_left_message(nick, reason, error)
            icon_name = "lucide-log-out-symbolic"
            icon_class = "gajim-user-disconnected"

        icon = Gtk.Image.new_from_icon_name(icon_name)
        icon.add_css_class(icon_class)
        self.grid.attach(icon, 1, 0, 1, 1)

        self._label = SimpleLabel()
        self._label.set_text(process_non_spacing_marks(text))
        self._label.add_css_class("gajim-status-message")
        self.grid.attach(self._label, 2, 0, 1, 1)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_halign(Gtk.Align.START)
        timestamp_widget.set_valign(Gtk.Align.FILL)
        self.grid.attach(timestamp_widget, 3, 0, 1, 1)

    def do_unroot(self) -> None:
        BaseRow.do_unroot(self)

    @staticmethod
    def _make_left_message(nick: str, reason: str | None, error: bool) -> str:
        reason = "" if reason is None else f": {reason}"

        if error:
            # Group Chat: User was kicked because of an server error: reason
            message = _("{nick} has left due to an error{reason}").format(
                nick=nick, reason=reason
            )

        else:
            message = _("{nick} has left{reason}").format(nick=nick, reason=reason)
        return message

    @staticmethod
    def _make_join_message(nick: str) -> str:
        return _("%s has joined") % nick
