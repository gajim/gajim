# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import time
from datetime import datetime

from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.structs import MucSubject

from gajim.common.const import AvatarSize
from gajim.common.i18n import _

from gajim.gtk.conversation.message_widget import MessageWidget
from gajim.gtk.conversation.rows.base import BaseRow
from gajim.gtk.conversation.rows.widgets import DateTimeLabel


class MUCSubject(BaseRow):

    type = "muc-subject"

    def __init__(
        self, account: str, subject: MucSubject, timestamp: float | None = None
    ) -> None:

        BaseRow.__init__(self, account)

        current_timestamp = timestamp or time.time()
        self.timestamp = datetime.fromtimestamp(current_timestamp).astimezone()
        self.db_timestamp = current_timestamp

        self.grid.set_halign(Gtk.Align.START)

        avatar_placeholder = Gtk.Box()
        avatar_placeholder.set_size_request(AvatarSize.ROSTER, -1)
        self.grid.attach(avatar_placeholder, 0, 0, 1, 2)

        subject_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        subject_box.set_halign(Gtk.Align.START)
        subject_box.add_css_class("conversation-subject-box")
        subject_box.add_css_class("gajim-subject-message")

        title = Gtk.Label(label=_("Subject"))
        title.set_halign(Gtk.Align.START)
        title.add_css_class("bold")
        subject_box.append(title)

        author = _("Changed by %s") % (subject.author or _("Unknown"))

        date = ""
        if subject.timestamp is not None:
            time_str = time.strftime("%c", time.localtime(subject.timestamp))
            date = f"{time_str}\n"

        meta_str = f"{author}\n{date}"
        meta = Gtk.Label(
            halign=Gtk.Align.START,
            label=meta_str,
            selectable=True,
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
            xalign=0,
        )
        meta.add_css_class("small-label")
        subject_box.append(meta)

        message_widget = MessageWidget(account)
        message_widget.add_with_styling(subject.text)
        subject_box.append(message_widget)
        self.grid.attach(subject_box, 1, 0, 1, 1)

        timestamp_widget = DateTimeLabel(self.timestamp)
        timestamp_widget.set_valign(Gtk.Align.START)
        self.grid.attach(timestamp_widget, 2, 0, 1, 1)

    def do_unroot(self) -> None:
        BaseRow.do_unroot(self)
