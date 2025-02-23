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
        Gtk.ComboBoxText.__init__(self, visible=False)

        self._client: Client | None = None
        self._contact: ChatContactT | None = None

        text_renderer = self.get_cells()[0]
        text_renderer.set_property("ellipsize", Pango.EllipsizeMode.END)
        text_renderer.set_property("max-width-chars", 20)

        self.set_valign(Gtk.Align.CENTER)
        self.set_tooltip_text(_("Select a security label for your message…"))

        app.ged.register_event_handler(
            "sec-catalog-received", ged.GUI1, self._sec_labels_received
        )

    def switch_contact(self, contact: ChatContactT) -> None:
        self.clear()

        self._client = app.get_client(contact.account)
        self._contact = contact

        app.settings.connect_signal(
            "enable_security_labels",
            self._on_setting_changed,
            account=self._contact.account,
        )
        self._client.connect_signal("state-changed", self._on_client_state_changed)

        self._update_combo_box()

    def do_unroot(self) -> None:
        self.clear()
        app.ged.remove_event_handler(
            "sec-catalog-received", ged.GUI1, self._sec_labels_received
        )
        Gtk.ComboBoxText.do_unroot(self)
        app.check_finalize(self)

    def _on_client_state_changed(
        self, _client: Client, _signal_name: str, state: SimpleClientState
    ) -> None:

        if state == SimpleClientState.CONNECTED:
            self._update_combo_box()

    def _on_setting_changed(
        self, state: bool, _name: str, _account: str | None, _jid: JID | None
    ) -> None:

        if state:
            self._update_combo_box()
        else:
            self.set_visible(False)
            self.remove_all()

    def _sec_labels_received(self, event: SecCatalogReceived) -> None:
        if self._contact is None or self._contact.account != event.account:
            return

        if event.jid != self._contact.jid:
            return

        self._update_combo_box()

    def _update_combo_box(self) -> None:

        assert self._contact is not None
        assert self._client is not None

        if not app.settings.get_account_setting(
            self._contact.account, "enable_security_labels"
        ):
            return

        catalog = self._client.get_module("SecLabels").get_catalog(self._contact.jid)

        self.remove_all()

        if catalog is not None:
            for selector in catalog.get_label_names():
                self.append(selector, selector)
            self.set_active_id(catalog.default)

        self.set_visible(True)

    def get_seclabel(self) -> SecurityLabel | None:
        assert self._contact is not None
        if not app.settings.get_account_setting(
            self._contact.account, "enable_security_labels"
        ):
            return

        selector = self.get_active_text()
        if selector is None:
            return

        assert self._client is not None
        catalog = self._client.get_module("SecLabels").get_catalog(self._contact.jid)
        if catalog is None:
            return None
        return catalog.labels[selector]

    def set_seclabel(self, label_hash: str) -> None:
        assert self._contact is not None
        assert self._client is not None

        catalog = self._client.get_module("SecLabels").get_catalog(self._contact.jid)
        if catalog is None:
            return None

        for selector, label in catalog.labels.items():
            if label is None:
                continue
            if label.get_label_hash() == label_hash:
                self.set_active_id(selector)

    def clear(self) -> None:
        app.settings.disconnect_signals(self)
        if self._client is not None:
            self._client.disconnect_all_from_obj(self)

        self._client = None
        self._contact = None
