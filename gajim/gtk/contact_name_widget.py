# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import types
from gajim.common.const import SimpleClientState
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant


class ContactNameWidget(Gtk.Box):

    __gsignals__ = {
        'name-updated': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(
        self,
        contact: BareContact | GroupchatContact | GroupchatParticipant | None = None,
        edit_mode: bool = False,
    ) -> None:
        Gtk.Box.__init__(self, spacing=18)

        self._contact = contact

        name = '' if self._contact is None else self._contact.name

        self._entry = Gtk.Entry(
            activates_default=True,
            name='ContactNameEntry',
            sensitive=False,
            text=name,
            xalign=1.0,
        )
        self._entry.connect('activate', self._on_entry_activated)
        self.add(self._entry)

        self.update_displayed_name(name)

        button_box = Gtk.Box(spacing=12, valign=Gtk.Align.CENTER)
        self.add(button_box)

        self._edit_button = Gtk.Button.new_from_icon_name(
            'document-edit-symbolic', Gtk.IconSize.BUTTON
        )
        self._edit_button.set_tooltip_text(_('Edit display name…'))
        self._edit_button.connect('clicked', self._on_edit_clicked)

        if isinstance(self._contact, GroupchatParticipant) or not edit_mode:
            self._edit_button.set_no_show_all(True)

        button_box.add(self._edit_button)

        self._clear_button = Gtk.Button.new_from_icon_name(
            'edit-clear-symbolic', Gtk.IconSize.BUTTON
        )
        self._clear_button.set_tooltip_text(_('Reset to original name'))
        self._clear_button.set_no_show_all(True)
        self._clear_button.connect('clicked', self._on_clear_button_clicked)
        button_box.add(self._clear_button)

        if self._contact is not None:
            client = app.get_client(self._contact.account)
            client.connect_signal('state-changed', self._on_client_state_changed)

        self.show_all()

    def _on_client_state_changed(
        self, _client: types.Client, _signal_name: str, state: SimpleClientState
    ) -> None:

        self._edit_button.set_sensitive(state.is_connected)
        self._clear_button.set_sensitive(state.is_connected)

    def _on_entry_activated(self, _entry: Gtk.Entry) -> None:
        self._save_name()
        self._disable_edit_mode()

    def _on_edit_clicked(self, _button: Gtk.Button) -> None:
        editing = self._entry.get_sensitive()
        if editing:
            self._save_name()
            self._disable_edit_mode()
        else:
            self.enable_edit_mode()

    def _on_clear_button_clicked(self, _button: Gtk.Button) -> None:
        self._entry.set_text('')
        self._save_name()
        self._disable_edit_mode()

    def _save_name(self) -> None:
        assert isinstance(self._contact, BareContact | GroupchatContact)

        name = self._entry.get_text()
        client = app.get_client(self._contact.account)

        if isinstance(self._contact, BareContact):
            client.get_module('Roster').set_item(
                self._contact.jid, name, self._contact.groups
            )
        else:
            client.get_module('Bookmarks').modify(self._contact.jid, name=name)

        self.update_displayed_name(name)

    def _disable_edit_mode(self) -> None:
        self._entry.set_sensitive(False)

        self._edit_button.set_tooltip_text(_('Edit display name…'))
        self._edit_button.set_image(
            Gtk.Image.new_from_icon_name('document-edit-symbolic', Gtk.IconSize.BUTTON)
        )
        self._clear_button.hide()

    def set_contact(
        self, contact: BareContact | GroupchatContact | GroupchatParticipant
    ) -> None:
        self._contact = contact
        self.update_displayed_name(self._contact.name)

    def enable_edit_mode(self) -> None:
        if self._contact is None:
            return

        client = app.get_client(self._contact.account)
        if not client.state.is_connected and not client.state.is_available:
            return

        self._entry.set_sensitive(True)
        self._entry.set_text(self._contact.name)
        self._entry.grab_focus()

        self._edit_button.set_tooltip_text(_('Save display name'))
        self._edit_button.set_image(
            Gtk.Image.new_from_icon_name('document-save-symbolic', Gtk.IconSize.BUTTON)
        )
        self._clear_button.show()

    def update_displayed_name(self, name: str) -> None:
        if self._contact is not None:
            if isinstance(self._contact, BareContact | GroupchatContact):
                # Name editing is not possible for GroupchatParticipant
                if name == '':
                    name = self._contact.original_name

                if name != self._contact.original_name:
                    name = f'{name} ({self._contact.original_name})'
            else:
                name = self._contact.name

        self._entry.set_text(name)

        width_chars = len(name) if len(name) <= 20 else 20
        self._entry.set_width_chars(width_chars)

        self.emit('name-updated', name)
