# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from unittest.mock import MagicMock

from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.chat_filter import ChatFilter
from gajim.gtk.widgets import GajimAppWindow

from . import util

ACCOUNT1 = "account1"
ACCOUNT2 = "account2"

class TestRosterModule:
    def __init__(self, account: str) -> None:
        self._account = account

    def get_groups(self) -> set[str]:
        if self._account == ACCOUNT1:
            return {"Group A", "Group B"}
        if self._account == ACCOUNT2:
            return {"Group B", "Group C"}
        return set()


class TestClient:
    def __init__(self, account: str) -> None:
        self._account = account

        self._roster_module = TestRosterModule(self._account)

    def get_module(self, module: str) -> Any:
        if module == 'Roster':
            return self._roster_module
        return MagicMock()


class TestChatFilter(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name='',
            title=__class__.__name__,
            default_width=600,
            default_height=600,
        )

        box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )
        self.set_child(box)

        self._chat_filter = ChatFilter()
        self._chat_filter.connect('filter-changed', self._on_filter_changed)
        box.append(self._chat_filter)

        reset_button = Gtk.Button(label="Reset")
        reset_button.connect("clicked", self._on_reset_clicked)
        box.append(reset_button)

    def _on_filter_changed(self, chat_filter: ChatFilter) -> None:
        print("Filters:", chat_filter.get_filters())

    def _on_reset_clicked(self, _button: Gtk.Button) -> None:
        self._chat_filter.reset()


app.get_client = MagicMock(side_effect=TestClient)
app.get_connected_accounts = MagicMock(return_value=[ACCOUNT1, ACCOUNT2])

window = TestChatFilter()
window.show()

util.run_app()
