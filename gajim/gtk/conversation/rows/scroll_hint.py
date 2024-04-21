# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gtk

from gajim.common.i18n import _
from gajim.common.util.datetime import FIRST_LOCAL_DATETIME

from gajim.gtk.conversation.rows.base import BaseRow


class ScrollHintRow(BaseRow):
    def __init__(self, account: str) -> None:
        BaseRow.__init__(self, account, widget='label')
        self.set_selectable(False)
        self.set_activatable(False)

        self.type = 'system'
        self.timestamp = FIRST_LOCAL_DATETIME

        self.get_style_context().add_class('conversation-system-row')

        self.label.set_halign(Gtk.Align.CENTER)
        self.label.set_hexpand(True)
        self.label.get_style_context().add_class(
            'conversation-meta')
        self.grid.attach(self.label, 0, 1, 1, 1)

        self.set_history_complete(False)
        self.show_all()

    def set_history_complete(self, complete: bool) -> None:
        if complete:
            self.label.set_text(_('There is no more history'))
        else:
            self.label.set_text(_('Scroll up to load more chat history…'))
