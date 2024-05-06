# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.util.datetime import FIRST_LOCAL_DATETIME


class BaseRow(Gtk.ListBoxRow):
    def __init__(self, account: str, widget: str | None = None) -> None:
        Gtk.ListBoxRow.__init__(self)
        self._account = account
        self._client = app.get_client(account)

        self.type: str = ''
        self.timestamp = FIRST_LOCAL_DATETIME
        self.kind: str = ''
        self.direction = ChatDirection.INCOMING
        self.name: str = ''
        self.pk: int | None = None
        self.stanza_id: str | None = None
        self.text: str = ''
        self._merged: bool = False

        self.set_selectable(False)
        self.set_can_focus(False)
        self.get_style_context().add_class('conversation-row')

        self.grid = Gtk.Grid(row_spacing=3, column_spacing=12)
        self.add(self.grid)

        if widget == 'label':
            self.label = Gtk.Label()
            self.label.set_selectable(True)
            self.label.set_line_wrap(True)
            self.label.set_xalign(0)
            self.label.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)

        self.connect('destroy', self.__destroy)

    def enable_selection_mode(self) -> None:
        return

    def disable_selection_mode(self) -> None:
        return

    @property
    def is_merged(self) -> bool:
        return self._merged

    @staticmethod
    def __destroy(widget: Gtk.Widget) -> None:
        app.check_finalize(widget)
