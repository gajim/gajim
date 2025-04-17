# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.util.datetime import FIRST_LOCAL_DATETIME

from gajim.gtk.util.classes import SignalManager


class BaseRow(Gtk.ListBoxRow, SignalManager):
    def __init__(self, account: str, widget: str | None = None) -> None:
        Gtk.ListBoxRow.__init__(self, selectable=False)
        SignalManager.__init__(self)

        self._account = account
        self._client = app.get_client(account)

        self.type: str = ""
        self.timestamp = FIRST_LOCAL_DATETIME
        self.kind: str = ""
        self.direction = ChatDirection.INCOMING
        self.name: str = ""
        self.pk: int | None = None
        self.stanza_id: str | None = None
        self.text: str = ""
        self._merged: bool = False

        self.add_css_class("conversation-row")

        self.grid = Gtk.Grid(
            row_spacing=3,
            column_spacing=12,
            halign=Gtk.Align.START,
            valign=Gtk.Align.START,
        )
        self.set_child(self.grid)

        if widget == "label":
            self.label = Gtk.Label(
                selectable=True, wrap=True, xalign=0, wrap_mode=Pango.WrapMode.WORD_CHAR
            )

    def enable_selection_mode(self) -> None:
        return

    def disable_selection_mode(self) -> None:
        return

    @property
    def is_merged(self) -> bool:
        return self._merged

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)
