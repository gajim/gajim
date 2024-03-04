# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Gtk

from gajim.common import app
from gajim.common import events
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import SimpleClientState
from gajim.common.helpers import get_global_status_message
from gajim.common.helpers import to_one_line
from gajim.common.i18n import _

from gajim.gtk.util import EventHelper


class StatusMessageSelector(Gtk.Box, EventHelper):
    def __init__(self, account: str | None = None) -> None:
        Gtk.Box.__init__(self)
        EventHelper.__init__(self)
        self.get_style_context().add_class('linked')
        self._account = account

        self._entry = Gtk.Entry()
        self._entry.set_size_request(200, -1)
        self._entry.set_property('show-emoji-icon', True)
        self._entry.set_property('enable-emoji-completion', True)
        self._entry.set_placeholder_text(_('Status message…'))
        self._entry.connect('activate', self._set_status_message)
        self._entry.connect('changed', self._on_changed)

        self._button = Gtk.Button.new_from_icon_name(
            'object-select-symbolic', Gtk.IconSize.BUTTON)
        self._button.set_tooltip_text(_('Set status message'))
        self._button.connect('clicked', self._set_status_message)
        self.add(self._entry)
        self.add(self._button)

        self.connect('destroy', self._on_destroy)

        self.show_all()

        self.register_event('our-show', ged.GUI1, self._on_our_show)
        self.register_event('account-enabled',
                            ged.GUI1,
                            self._on_account_enabled)

        for client in app.get_clients():
            client.connect_signal('state-changed',
                                  self._on_client_state_changed)

    def _on_our_show(self, event: events.ShowChanged) -> None:
        self.update()

    def _on_account_enabled(self, event: events.AccountEnabled) -> None:
        client = app.get_client(event.account)
        client.connect_signal('state-changed', self._on_client_state_changed)

    def _on_client_state_changed(self,
                                 client: Client,
                                 _signal_name: str,
                                 state: SimpleClientState) -> None:
        self.update()

    def _on_changed(self, _entry: Gtk.Entry) -> None:
        self._button.set_sensitive(True)

    def _set_status_message(self, *args: Any) -> None:
        self._button.set_sensitive(False)
        message = self._entry.get_text()
        message = to_one_line(message)
        if self._account is not None:
            client = app.get_client(self._account)
            client.change_status(client.status, message)
        else:
            for client in app.get_clients():
                if not app.settings.get_account_setting(
                        client.account, 'sync_with_global_status'):
                    continue
                client.change_status(client.status, message)

    def update(self) -> None:
        if self._account is None:
            message = get_global_status_message()
        else:
            try:
                client = app.get_client(self._account)
            except KeyError:
                return
            message = client.status_message

        self._entry.set_text(message)

    def _on_destroy(self, widget: StatusMessageSelector) -> None:
        app.check_finalize(self)
