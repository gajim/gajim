# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import locale
import logging
import time

from gi.repository import Gtk
from omemo_dr.const import OMEMOTrust
from omemo_dr.structs import IdentityInfo

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.events import AccountConnected
from gajim.common.events import AccountDisconnected
from gajim.common.ged import EventHelper
from gajim.common.helpers import generate_qr_code
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.omemo import compose_trust_uri

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import clear_listbox
from gajim.gtk.util.window import open_window

log = logging.getLogger("gajim.gtk.omemo_trust_manager")


TRUST_DATA = {
    OMEMOTrust.UNTRUSTED: ("dialog-error-symbolic", _("Untrusted"), "error-color"),
    OMEMOTrust.UNDECIDED: ("security-low-symbolic", _("Not Decided"), "warning-color"),
    OMEMOTrust.VERIFIED: ("security-high-symbolic", _("Verified"), "encrypted-color"),
    OMEMOTrust.BLIND: ("security-medium-symbolic", _("Blind Trust"), "encrypted-color"),
}


class OMEMOTrustManager(Gtk.Box, EventHelper, SignalManager):
    def __init__(self, account: str, contact: types.ChatContactT | None = None) -> None:
        Gtk.Box.__init__(self)
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self._account = account
        self._contact = contact

        self._ui = get_builder("omemo_trust_manager.ui")
        self.append(self._ui.stack)

        self._connect(self._ui.search, "search-changed", self._on_search_changed)
        self._connect(
            self._ui.manage_trust_button, "clicked", self._on_manage_trust_clicked
        )
        self._connect(
            self._ui.show_inactive_switch, "notify::active", self._on_show_inactive
        )
        self._connect(
            self._ui.clear_devices_button, "clicked", self._on_clear_devices_clicked
        )

        self._ui.list.set_filter_func(self._filter_func, None)
        self._ui.list.set_sort_func(self._sort_func, None)

        self.register_events(
            [
                ("account-connected", ged.GUI2, self._on_account_state),
                ("account-disconnected", ged.GUI2, self._on_account_state),
            ]
        )

        if not app.account_is_connected(account):
            self._ui.stack.set_visible_child_name("no-connection")
            return

        self._update()

    def do_unroot(self) -> None:
        self.unregister_events()
        self._disconnect_all()
        self._ui.list.set_filter_func(None)
        self._ui.list.set_sort_func(None)

        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _update(self) -> None:
        client = app.get_client(self._account)
        if self._contact is None:
            self._contact = client.get_module("Contacts").get_contact(
                client.get_own_jid().bare
            )

        if isinstance(self._contact, BareContact) and self._contact.is_self:
            header_text = _("Other devices connected with your account")
            popover_qr_text = _(
                "Compare this code with the one shown on your "
                "contact’s screen to ensure the safety of "
                "your end-to-end encrypted chat."
            )
        else:
            assert isinstance(
                self._contact, BareContact | GroupchatContact | GroupchatParticipant
            )
            header_text = _('Devices connected with "%s"') % self._contact.name
            popover_qr_text = (
                _(
                    "Compare this code with the one shown on your "
                    "contact’s screen to ensure the safety of "
                    "your end-to-end encrypted chat "
                    "with %s."
                )
                % self._contact.name
            )

        self._ui.list_heading.set_text(header_text)
        self._ui.comparing_instructions.set_text(popover_qr_text)

        our_fpr_formatted = client.get_module("OMEMO").backend.get_our_fingerprint(
            formatted=True
        )
        self._ui.our_fingerprint_1.set_text(our_fpr_formatted)
        self._ui.our_fingerprint_2.set_text(our_fpr_formatted)

        self.update()
        self._load_qrcode()

    def update(self) -> None:
        assert self._contact is not None
        clear_listbox(self._ui.list)

        if isinstance(self._contact, BareContact) and self._contact.is_self:
            self._ui.clear_devices_button.set_visible(True)
            self._ui.list_heading_box.set_halign(Gtk.Align.START)
        else:
            self._ui.manage_trust_button.set_visible(True)
            if self._contact.is_groupchat:
                self._ui.search_button.set_visible(True)
            else:
                self._ui.list_heading_box.set_halign(Gtk.Align.START)

        assert isinstance(
            self._contact, BareContact | GroupchatContact | GroupchatParticipant
        )
        self._load_fingerprints(self._contact)

    def _on_account_state(self, event: AccountConnected | AccountDisconnected) -> None:

        if event.account != self._account:
            return

        if isinstance(event, AccountConnected):
            self._update()
            self._ui.stack.set_visible_child_name("manage-keys")
        else:
            self._ui.stack.set_visible_child_name("no-connection")

    def _filter_func(self, row: KeyRow, _user_data: Any) -> bool:
        search_text = self._ui.search.get_text()
        if search_text and search_text.lower() not in row.address:
            return False
        if self._ui.show_inactive_switch.get_active():
            return True
        return row.active

    @staticmethod
    def _sort_func(row1: KeyRow, row2: KeyRow, _user_data: Any) -> int:
        result = locale.strcoll(row1.address, row2.address)
        if result != 0:
            return result

        if row1.active != row2.active:
            return -1 if row1.active else 1

        if row1.trust != row2.trust:
            return -1 if row1.trust > row2.trust else 1
        return 0

    def _on_search_changed(self, _entry: Gtk.SearchEntry) -> None:
        self._ui.list.invalidate_filter()

    def _load_fingerprints(self, contact: types.ChatContactT) -> None:
        client = app.get_client(self._account)
        for identity_info in client.get_module("OMEMO").backend.get_identity_infos(
            str(contact.jid)
        ):
            self._ui.list.append(KeyRow(contact, identity_info))

    def _load_qrcode(self) -> None:
        client = app.get_client(self._account)
        uri = compose_trust_uri(
            client.get_own_jid(),
            [client.get_module("OMEMO").backend.get_our_identity()],
        )
        log.debug("Trust URI: %s", uri)
        self._ui.qr_code_image.set_from_paintable(generate_qr_code(uri))

    def _on_show_inactive(self, switch: Gtk.Switch, _param: Any) -> None:
        self._ui.list.invalidate_filter()

    def _on_clear_devices_clicked(self, _button: Gtk.Button) -> None:
        def _clear():
            client = app.get_client(self._account)
            client.get_module("OMEMO").clear_devicelist()

        ConfirmationDialog(
            _("Clear Devices?"),
            _("This will clear the devices store for your account."),
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Accept", text=_("_Clear Devices"), callback=_clear),
            ],
        ).set_visible(True)

    def _on_manage_trust_clicked(self, _button: Gtk.Button) -> None:
        assert self._contact is not None
        window = open_window("AccountsWindow")
        window.select_account(self._contact.account, "encryption-omemo")


class KeyRow(Gtk.ListBoxRow):
    def __init__(
        self, contact: types.ChatContactT, identity_info: IdentityInfo
    ) -> None:

        Gtk.ListBoxRow.__init__(self)
        self.set_activatable(False)

        self._contact = contact
        self._client = app.get_client(contact.account)

        self._address = identity_info.address
        self._identity_info = identity_info
        self._trust = identity_info.trust

        grid = Gtk.Grid()
        grid.set_column_spacing(12)

        self._trust_button = TrustButton(self)
        grid.attach(self._trust_button, 1, 1, 1, 3)

        if contact.is_groupchat:
            jid_label = Gtk.Label(label=self._address)
            jid_label.set_selectable(False)
            jid_label.set_halign(Gtk.Align.START)
            jid_label.set_valign(Gtk.Align.START)
            jid_label.set_hexpand(True)
            jid_label.add_css_class("bold")
            grid.attach(jid_label, 2, 1, 1, 1)

        self.fingerprint = Gtk.Label(
            label=self._identity_info.public_key.get_fingerprint(formatted=True)
        )
        self.fingerprint.add_css_class("monospace")
        self.fingerprint.add_css_class("small-label")
        self.fingerprint.set_selectable(True)
        self.fingerprint.set_halign(Gtk.Align.START)
        self.fingerprint.set_valign(Gtk.Align.START)
        self.fingerprint.set_hexpand(True)
        grid.attach(self.fingerprint, 2, 2, 1, 1)

        if self._identity_info.last_seen is not None:
            last_seen_str = time.strftime(
                app.settings.get("date_time_format"),
                time.localtime(self._identity_info.last_seen),
            )
        else:
            last_seen_str = _("Never")
        last_seen_label = Gtk.Label(label=_("Last seen: %s") % last_seen_str)
        last_seen_label.set_halign(Gtk.Align.START)
        last_seen_label.set_valign(Gtk.Align.START)
        last_seen_label.set_hexpand(True)
        last_seen_label.add_css_class("small-label")
        last_seen_label.add_css_class("dim-label")
        grid.attach(last_seen_label, 2, 3, 1, 1)

        self.set_child(grid)

    def do_unroot(self) -> None:
        del self._trust_button

        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)

    def delete_fingerprint(self, *args: Any) -> None:

        def _remove():
            self._client.get_module("OMEMO").backend.delete_session(
                self._address, self._identity_info.device_id, delete_identity=True
            )

            listbox = cast(Gtk.ListBox, self.get_parent())
            listbox.remove(self)

        ConfirmationDialog(
            _("Delete Fingerprint?"),
            _("Doing so will permanently delete this Fingerprint"),
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Remove", text=_("Delete"), callback=_remove),
            ],
        ).set_visible(True)

    def set_trust(self, trust: OMEMOTrust) -> None:
        self._trust = trust
        icon_name, tooltip, css_class = TRUST_DATA[trust]
        image = cast(Gtk.Image, self._trust_button.get_child())
        image.set_from_icon_name(icon_name)
        image.add_css_class(css_class)
        image.set_tooltip_text(tooltip)

        self._client.get_module("OMEMO").backend.set_trust(
            self._address, self._identity_info.public_key, trust
        )

    @property
    def trust(self) -> OMEMOTrust:
        return self._trust

    @property
    def active(self) -> bool:
        return self._identity_info.active

    @property
    def address(self) -> str:
        return self._address


class TrustButton(Gtk.MenuButton):
    def __init__(self, row: KeyRow) -> None:
        Gtk.MenuButton.__init__(self)
        self._row = row
        self._css_class = ""
        self._trust_popover = TrustPopver(row, self)
        self.set_popover(self._trust_popover)
        self.set_valign(Gtk.Align.CENTER)
        self.update()

    def do_unroot(self) -> None:
        del self._trust_popover
        del self._row

        Gtk.MenuButton.do_unroot(self)
        app.check_finalize(self)

    def update(self) -> None:
        icon_name, tooltip, css_class = TRUST_DATA[self._row.trust]
        image = Gtk.Image.new_from_icon_name(icon_name)
        self.set_child(image)

        if not self._row.active:
            css_class = "omemo-inactive-color"
            tooltip = f'{_("Inactive")} - {tooltip}'

        image.add_css_class(css_class)
        self._css_class = css_class
        self.set_tooltip_text(tooltip)


class TrustPopver(Gtk.Popover, SignalManager):
    def __init__(self, row: KeyRow, trust_button: TrustButton) -> None:
        Gtk.Popover.__init__(self)
        SignalManager.__init__(self)
        self._row = row
        self._trust_button = trust_button

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.update()
        self.set_child(self._listbox)
        self._connect(self._listbox, "row-activated", self._activated)
        self.add_css_class("omemo-trust-popover")

    def do_unroot(self) -> None:
        Gtk.Popover.do_unroot(self)
        self._disconnect_all()
        del self._listbox
        del self._row
        del self._trust_button
        app.check_finalize(self)

    def _activated(self, _listbox: Gtk.ListBox, row: MenuOption) -> None:
        self.popdown()
        if row.type_ is None:
            self._row.delete_fingerprint()
        else:
            self._row.set_trust(row.type_)
            self._trust_button.update()
            self.update()

    def update(self) -> None:
        clear_listbox(self._listbox)

        if self._row.trust != OMEMOTrust.VERIFIED:
            self._listbox.append(VerifiedOption())
        if self._row.trust != OMEMOTrust.BLIND:
            self._listbox.append(BlindOption())
        if self._row.trust != OMEMOTrust.UNTRUSTED:
            self._listbox.append(NotTrustedOption())
        self._listbox.append(DeleteOption())


class MenuOption(Gtk.ListBoxRow):
    def __init__(
        self, icon: str, label_text: str, color: str, type_: OMEMOTrust | None = None
    ) -> None:

        Gtk.ListBoxRow.__init__(self)

        self.type_ = type_
        self.icon = icon
        self.label = label_text
        self.color = color

        box = Gtk.Box()
        box.set_spacing(6)

        image = Gtk.Image.new_from_icon_name(icon)
        if color:
            image.add_css_class(color)

        label = Gtk.Label(label=label_text)

        box.append(image)
        box.append(label)
        self.set_child(box)


class BlindOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(
            self,
            "security-medium-symbolic",
            _("Blind Trust"),
            "encrypted-color",
            OMEMOTrust.BLIND,
        )


class VerifiedOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(
            self,
            "security-high-symbolic",
            _("Verified"),
            "encrypted-color",
            OMEMOTrust.VERIFIED,
        )


class NotTrustedOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(
            self,
            "dialog-error-symbolic",
            _("Untrusted"),
            "error-color",
            OMEMOTrust.UNTRUSTED,
        )


class DeleteOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(self, "user-trash-symbolic", _("Delete"), "")
