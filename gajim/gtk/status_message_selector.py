# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import SimpleClientState
from gajim.common.ged import EventHelper
from gajim.common.util.text import to_one_line

from gajim.gtk.util.misc import get_ui_string


@Gtk.Template(string=get_ui_string("status_message_selector.ui"))
class StatusMessageSelector(Gtk.Box, EventHelper):
    __gtype_name__ = "StatusMessageSelector"

    _entry: Gtk.Entry = Gtk.Template.Child()
    _button: Gtk.Button = Gtk.Template.Child()

    def __init__(self) -> None:
        self._account: str | None = None

        Gtk.Box.__init__(self)
        EventHelper.__init__(self)

        self.register_events(
            [
                ("our-show", ged.GUI1, self._on_our_show),
            ]
        )

    @GObject.Property(type=str)
    def account(self) -> str | None:  # pyright: ignore
        return self._account

    @account.setter
    def account(self, account: str | None) -> None:
        if self._account == account:
            return

        self._disconnect_signals(self._account)
        self._connect_signals(account)

        self._button.set_sensitive(account is not None)
        self._entry.set_sensitive(account is not None)

        self._account = account
        self._update_status_message()

    def set_account(self, account: str | None) -> None:
        self.account = account

    def _connect_signals(self, account: str | None) -> None:
        if account is None:
            return
        client = app.get_client(account)
        client.connect_signal("state-changed", self._on_client_state_changed)

    def _disconnect_signals(self, account: str | None) -> None:
        if account is None:
            return
        client = app.get_client(account)
        client.disconnect_all_from_obj(self)

    def _on_our_show(self, event: events.ShowChanged) -> None:
        if event.account != self._account:
            return
        self._update_status_message()

    def _on_client_state_changed(
        self, client: Client, _signal_name: str, _state: SimpleClientState
    ) -> None:
        self._update_status_message()

    @Gtk.Template.Callback()
    def _on_changed(self, _entry: Gtk.Entry) -> None:
        self._button.set_sensitive(True)

    @Gtk.Template.Callback()
    def _set_status_message(self, *args: Any) -> None:
        self._button.set_sensitive(False)

        message = self._entry.get_text()
        message = to_one_line(message)

        assert self._account is not None

        for client in app.get_clients():
            sync = app.settings.get_account_setting(
                client.account, "sync_with_global_status"
            )
            if client.account != self._account and not sync:
                continue
            client.change_status(client.status, message)

    def _update_status_message(self) -> None:
        if self._account is None:
            self._entry.set_text("")
            return

        client = app.get_client(self._account)
        message = client.status_message

        self._entry.set_text(message)
        self._button.set_sensitive(False)
