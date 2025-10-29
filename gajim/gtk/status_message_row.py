# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Adw
from gi.repository import GLib
from gi.repository import GObject

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import SimpleClientState
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.util.text import to_one_line


class StatusMessageSelectorRow(Adw.EntryRow, EventHelper):
    __gtype_name__ = "StatusMessageSelectorRow"

    def __init__(self) -> None:
        Adw.EntryRow.__init__(self)
        EventHelper.__init__(self)

        # These need to be set after init (Adw issue)
        self.set_title(_("Status Message"))
        self.set_show_apply_button(True)
        self.set_enable_emoji_completion(True)

        self.connect("apply", self._on_apply_clicked)

        self._account: str | None = None

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

        self.set_sensitive(account is not None)

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

    def _on_apply_clicked(self, *args: Any) -> None:
        self.set_show_apply_button(False)
        message = self.get_text()
        message = to_one_line(message)

        assert self._account is not None

        for client in app.get_clients():
            sync = app.settings.get_account_setting(
                client.account, "sync_with_global_status"
            )
            if client.account != self._account and not sync:
                continue
            client.change_status(client.status, message)

        self.set_show_apply_button(False)
        GLib.timeout_add_seconds(3, self._show_apply_button)

    def _show_apply_button(self) -> None:
        self.set_show_apply_button(True)

    def _update_status_message(self) -> None:
        if self._account is None:
            self.set_text("")
            return

        client = app.get_client(self._account)
        self.set_text(client.status_message)
