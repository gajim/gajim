# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk

from gajim.common import app
from gajim.common import types
from gajim.common.const import SimpleClientState
from gajim.common.i18n import _
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.builder import get_builder
from gajim.gtk.util.classes import SignalManager


class GroupchatState(Gtk.Box, SignalManager):
    def __init__(self) -> None:
        Gtk.Box.__init__(
            self, halign=Gtk.Align.CENTER, valign=Gtk.Align.END, visible=False
        )
        SignalManager.__init__(self)

        self._contact = None
        self._client = None

        self._ui = get_builder("groupchat_state.ui")
        self._connect(self._ui.join_button, "clicked", self._on_join_clicked)
        self._connect(self._ui.abort_join_button, "clicked", self._on_abort_clicked)
        self._connect(self._ui.close_button, "clicked", self._on_close_clicked)

        self.append(self._ui.groupchat_state)

    def do_unroot(self) -> None:
        self.clear()

        Gtk.Box.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self)

    def clear(self) -> None:
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        if self._client is not None:
            self._client.disconnect_all_from_obj(self)

        self._contact = None
        self._client = None
        self.hide()

    def switch_contact(self, contact: types.ChatContactT) -> None:
        self.clear()

        if not isinstance(contact, GroupchatContact):
            return

        self._contact = contact
        self._contact.connect("state-changed", self._on_muc_state_changed)
        self._contact.connect("mam-sync-started", self._on_mam_sync_changed)
        self._contact.connect("mam-sync-finished", self._on_mam_sync_changed)
        self._contact.connect("mam-sync-error", self._on_mam_sync_error)

        self._client = app.get_client(contact.account)
        self._client.connect_signal("state-changed", self._on_client_state_changed)

        self._update_state(contact)

    def _on_client_state_changed(
        self, client: types.Client, _signal_name: str, _state: SimpleClientState
    ) -> None:

        assert self._contact is not None
        self._update_state(self._contact)

    def _on_muc_state_changed(
        self, contact: GroupchatContact, _signal_name: str
    ) -> None:

        self._update_state(contact)

    def _update_state(self, contact: GroupchatContact) -> None:
        self._ui.joining_spinner.stop()
        self._ui.mam_sync_spinner.stop()

        if contact.is_joining:
            self._ui.groupchat_state.set_visible_child_name("joining")
            self._ui.joining_spinner.start()

        elif contact.is_not_joined:
            self._ui.groupchat_state.set_visible_child_name("not-joined")

        assert self._client is not None
        self.set_visible(self._client.state.is_available and not contact.is_joined)

    def _on_mam_sync_changed(
        self,
        _contact: GroupchatContact,
        signal_name: str,
    ) -> None:

        if signal_name == "mam-sync-started":
            self.set_visible(True)
            self._ui.groupchat_state.set_visible_child_name(signal_name)
            self._ui.mam_sync_spinner.start()
            return

        self.hide()

    def _on_mam_sync_error(
        self, _contact: GroupchatContact, signal_name: str, error_text: str
    ) -> None:

        self.set_visible(True)
        self._ui.groupchat_state.set_visible_child_name(signal_name)
        self._ui.mam_error_label.set_text(
            _("There has been an error while trying to fetch messages: %s") % error_text
        )
        self._ui.mam_sync_spinner.stop()

    def _on_close_clicked(self, _button: Gtk.Button) -> None:
        self.hide()

    def _on_join_clicked(self, _button: Gtk.Button) -> None:
        assert self._contact is not None
        client = app.get_client(self._contact.account)
        client.get_module("MUC").join(self._contact.jid)

    def _on_abort_clicked(self, _button: Gtk.Button) -> None:
        assert self._contact is not None
        client = app.get_client(self._contact.account)
        client.get_module("MUC").abort_join(self._contact.jid)
