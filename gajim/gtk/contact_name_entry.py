# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import types
from gajim.common.const import SimpleClientState
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string


@Gtk.Template.from_string(string=get_ui_string("contact_name_entry.ui"))
class ContactNameEntry(Gtk.Box, SignalManager):
    __gtype_name__ = "ContactNameEntry"

    __gsignals__ = {
        "name-updated": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    _name_label: Gtk.Label = Gtk.Template.Child()
    _edit_button: Gtk.Button = Gtk.Template.Child()

    _name_entry_box: Gtk.Box = Gtk.Template.Child()
    _name_entry: Gtk.Entry = Gtk.Template.Child()
    _apply_button: Gtk.Button = Gtk.Template.Child()
    _cancel_button: Gtk.Button = Gtk.Template.Child()
    _reset_button: Gtk.Button = Gtk.Template.Child()

    def __init__(
        self,
        contact: BareContact | GroupchatContact | GroupchatParticipant | None = None,
        editable: bool = False,
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._contact = contact

        name = "" if self._contact is None else self._contact.name

        self.update_displayed_name(name)

        self._edit_button.set_visible(editable)
        self._connect(self._edit_button, "clicked", self._on_edit_clicked)
        if (
            isinstance(self._contact, GroupchatParticipant)
            or (
                isinstance(self._contact, BareContact)
                and not self._contact.is_in_roster
            )
            or not editable
        ):
            self._edit_button.set_visible(False)

        self._connect(self._name_entry, "activate", self._on_entry_activated)
        self._connect(self._apply_button, "clicked", self._on_apply_clicked)
        self._connect(self._cancel_button, "clicked", self._on_cancel_clicked)
        self._connect(self._reset_button, "clicked", self._on_reset_clicked)

        if self._contact is not None:
            client = app.get_client(self._contact.account)
            client.connect_signal("state-changed", self._on_client_state_changed)

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self)

    def _on_client_state_changed(
        self, _client: types.Client, _signal_name: str, state: SimpleClientState
    ) -> None:
        self._edit_button.set_sensitive(state.is_connected)
        self._apply_button.set_sensitive(state.is_connected)
        self._reset_button.set_sensitive(state.is_connected)

    def _on_edit_clicked(self, _button: Gtk.Button) -> None:
        self.enable_edit_mode()

    def _on_entry_activated(self, _entry: Gtk.Entry) -> None:
        self._save_name()
        self._disable_edit_mode()

    def _on_apply_clicked(self, _button: Gtk.Button) -> None:
        self._save_name()
        self._disable_edit_mode()

    def _on_cancel_clicked(self, _button: Gtk.Button) -> None:
        self._disable_edit_mode()

    def _on_reset_clicked(self, _button: Gtk.Button) -> None:
        self._name_entry.set_text("")
        self._save_name()
        self._disable_edit_mode()

    def _save_name(self) -> None:
        assert isinstance(self._contact, BareContact | GroupchatContact)

        name = self._name_entry.get_text()
        client = app.get_client(self._contact.account)

        if isinstance(self._contact, BareContact):
            client.get_module("Roster").change_name(self._contact.jid, name)
        else:
            client.get_module("Bookmarks").modify(self._contact.jid, name=name)

        self.update_displayed_name(name)

    def _disable_edit_mode(self) -> None:
        self._name_entry_box.set_visible(False)
        self._cancel_button.set_visible(False)
        self._reset_button.set_visible(False)

        self._name_label.set_visible(True)
        self._edit_button.set_visible(True)

    def enable_edit_mode(self) -> None:
        if self._contact is None:
            return

        client = app.get_client(self._contact.account)
        if not client.state.is_connected and not client.state.is_available:
            return

        self._name_label.set_visible(False)
        self._edit_button.set_visible(False)

        self._name_entry_box.set_visible(True)

        self._name_entry.set_text(self._contact.name)
        self._name_entry.grab_focus()

        self._cancel_button.set_visible(True)
        self._reset_button.set_visible(True)

    def update_displayed_name(self, name: str) -> None:
        if self._contact is not None:
            if isinstance(self._contact, BareContact | GroupchatContact):
                # Name editing is not possible for GroupchatParticipant
                if name == "":
                    name = self._contact.original_name

                if name != self._contact.original_name:
                    name = f"{name} ({self._contact.original_name})"
            else:
                name = self._contact.name

        self._name_label.set_label(name)
        self._name_entry.set_text(name)

        self.emit("name-updated", name)

    def set_contact(
        self, contact: BareContact | GroupchatContact | GroupchatParticipant
    ) -> None:
        self._contact = contact
        self.update_displayed_name(self._contact.name)
