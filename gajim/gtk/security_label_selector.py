# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.modules.security_labels import SecurityLabel
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import SimpleClientState
from gajim.common.events import SecCatalogReceived
from gajim.common.i18n import _
from gajim.common.types import ChatContactT


class SecurityLabelSelector(Gtk.ComboBoxText):
    def __init__(self) -> None:
        Gtk.ComboBoxText.__init__(self, no_show_all=True)

        self._account: str | None = None
        self._client: Client | None = None
        self._contact: ChatContactT | None = None

        text_renderer = self.get_cells()[0]
        text_renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        text_renderer.set_property('max-width-chars', 20)

        self.set_valign(Gtk.Align.CENTER)
        self.set_tooltip_text(_('Select a security label for your message…'))

        app.ged.register_event_handler(
            'sec-catalog-received', ged.GUI1, self._sec_labels_received)

        self.connect('destroy', self._on_destroy)

    def switch_contact(self, contact: ChatContactT) -> None:
        app.settings.disconnect_signals(self)
        if self._client is not None:
            self._client.disconnect_all_from_obj(self)

        self._account = contact.account
        self._client = app.get_client(contact.account)
        self._contact = contact

        app.settings.connect_signal(
            'enable_security_labels',
            self._on_setting_changed,
            account=self._account)
        self._client.connect_signal(
            'state-changed', self._on_client_state_changed)
        self._update()

    def _on_destroy(self, _widget: SecurityLabelSelector) -> None:
        app.ged.remove_event_handler('sec-catalog-received',
                                     ged.GUI1,
                                     self._sec_labels_received)
        app.check_finalize(self)

    def _on_client_state_changed(self,
                                 _client: Client,
                                 _signal_name: str,
                                 _state: SimpleClientState
                                 ) -> None:
        self._update()

    def _on_setting_changed(self,
                            state: bool,
                            _name: str,
                            _account: str | None,
                            _jid: JID | None
                            ) -> None:
        self.set_no_show_all(not state)
        if state:
            self.show_all()
        else:
            self.hide()
        self._update()

    def _sec_labels_received(self, event: SecCatalogReceived) -> None:
        if self._account is None or self._account != event.account:
            return

        if self._contact is None:
            return

        if event.jid != self._contact.jid.bare:
            return

        if not app.settings.get_account_setting(
                self._account, 'enable_security_labels'):
            return

        self.remove_all()

        for selector in event.catalog.get_label_names():
            self.append(selector, selector)

        self.set_active_id(event.catalog.default)
        self.set_no_show_all(False)
        self.show_all()

    def get_seclabel(self) -> SecurityLabel | None:
        selector = self.get_active_text()
        if selector is None:
            return

        assert self._contact is not None
        assert self._client is not None
        jid = self._contact.jid.bare
        catalog = self._client.get_module('SecLabels').get_catalog(jid)
        if catalog is None:
            return None
        return catalog.labels[selector]

    def set_seclabel(self, label_hash: str) -> None:
        assert self._contact is not None
        assert self._client is not None
        jid = self._contact.jid.bare
        catalog = self._client.get_module('SecLabels').get_catalog(jid)
        if catalog is None:
            return None

        for selector, label in catalog.labels.items():
            if label.get_label_hash() == label_hash:
                self.set_active_id(selector)

    def _update(self) -> None:
        assert self._account is not None
        assert self._client is not None
        assert self._contact is not None

        chat_active = app.window.is_chat_active(
            self._account, self._contact.jid)
        if chat_active:
            self._client.get_module('SecLabels').get_catalog(
                self._contact.jid.bare)
