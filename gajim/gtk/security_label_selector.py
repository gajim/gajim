# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

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


class SecurityLabelSelector(Gtk.ComboBox):
    def __init__(self) -> None:
        Gtk.ComboBox.__init__(self, no_show_all=True)
        self._account: str | None = None
        self._client: Client | None = None
        self._contact: ChatContactT | None = None

        self.set_valign(Gtk.Align.CENTER)
        self.set_tooltip_text(_('Select a security label for your message…'))

        label_store = Gtk.ListStore(str)
        self.set_model(label_store)
        label_cell_renderer = Gtk.CellRendererText()
        label_cell_renderer.set_property('ellipsize', Pango.EllipsizeMode.END)
        label_cell_renderer.set_property('max-width-chars', 14)
        self.pack_start(label_cell_renderer, True)
        self.add_attribute(label_cell_renderer, 'text', 0)

        app.ged.register_event_handler(
            'sec-catalog-received', ged.GUI1, self._sec_labels_received)

        self.connect('changed', self._on_changed)
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

    def _on_changed(self, _combo: Gtk.ComboBox) -> None:
        iter_ = self.get_active_iter()
        if iter_ is None:
            return

        model = self.get_model()
        label_text = model.get_value(iter_, 0)
        self.set_tooltip_text(
            _('Selected security label: %s') % f'\n{label_text}')

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

        model = cast(Gtk.ListStore, self.get_model())
        model.clear()

        selection = 0
        label_list = event.catalog.get_label_names()
        default = event.catalog.default
        for index, label in enumerate(label_list):
            model.append([label])
            if label == default:
                selection = index

        self.set_active(selection)
        self.set_no_show_all(False)
        self.show_all()

    def get_seclabel(self) -> SecurityLabel | None:
        index = self.get_active()
        if index == -1:
            return None

        assert self._contact is not None
        assert self._client is not None
        jid = self._contact.jid.bare
        catalog = self._client.get_module('SecLabels').get_catalog(jid)
        if catalog is None:
            return None

        labels, label_list = catalog.labels, catalog.get_label_names()
        label_name = label_list[index]
        return labels[label_name]

    def _update(self) -> None:
        assert self._account is not None
        assert self._client is not None
        assert self._contact is not None

        chat_active = app.window.is_chat_active(
            self._account, self._contact.jid)
        if chat_active:
            self._client.get_module('SecLabels').get_catalog(
                self._contact.jid.bare)
