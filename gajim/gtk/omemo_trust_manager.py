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

from gi.repository import Adw
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

from gajim.gtk.alert import ConfirmationAlertDialog
from gajim.gtk.builder import get_builder
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import clear_listbox
from gajim.gtk.util.misc import remove_css_class
from gajim.gtk.util.window import open_window

log = logging.getLogger("gajim.gtk.omemo_trust_manager")


TRUST_DATA = {
    OMEMOTrust.UNTRUSTED: (
        "lucide-shield-x-symbolic",
        _("Untrusted"),
        "omemo-untrusted-color",
    ),
    OMEMOTrust.UNDECIDED: (
        "lucide-shield-question-mark-symbolic",
        _("Not Decided"),
        "omemo-undecided-color",
    ),
    OMEMOTrust.VERIFIED: (
        "lucide-shield-check-symbolic",
        _("Verified"),
        "omemo-verified-color",
    ),
    OMEMOTrust.BLIND: (
        "lucide-shield-symbolic",
        _("Blind Trust"),
        "omemo-blind-color",
    ),
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

        self._connect(
            self._ui.manage_trust_button, "clicked", self._on_manage_trust_clicked
        )
        self._connect(
            self._ui.show_inactive_switch, "state-set", self._on_show_inactive
        )
        self._connect(
            self._ui.clear_devices_button, "clicked", self._on_clear_devices_clicked
        )
        self._connect(self._ui.copy_button, "clicked", self._on_copy_button_clicked)

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
            if self._contact.is_groupchat:
                header_text = (
                    _('Undecided fingerprints of devices connected with "%s"')
                    % self._contact.name
                )
            else:
                header_text = (
                    _('Fingerprints of devices connected with "%s"')
                    % self._contact.name
                )
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

        self._our_fpr_formatted = client.get_module(
            "OMEMO"
        ).backend.get_our_fingerprint(formatted=True)
        self._ui.our_fingerprint_row.set_title(self._our_fpr_formatted)
        self._ui.our_fingerprint_2.set_text(self._our_fpr_formatted)

        self.update()
        self._load_qrcode()

    def update(self) -> None:
        assert self._contact is not None
        clear_listbox(self._ui.list)

        if isinstance(self._contact, BareContact) and self._contact.is_self:
            self._ui.clear_devices_button.set_visible(True)
        else:
            self._ui.manage_trust_button.set_visible(True)
            if self._contact.is_groupchat:
                self._ui.list_heading_box.set_visible(False)

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

    @staticmethod
    def _sort_func(row1: DeviceRow, row2: DeviceRow, _user_data: Any) -> int:
        result = locale.strcoll(row1.address, row2.address)
        if result != 0:
            return result

        if row1.active != row2.active:
            return -1 if row1.active else 1

        if row1.trust != row2.trust:
            return -1 if row1.trust > row2.trust else 1
        return 0

    def _load_fingerprints(self, contact: types.ChatContactT) -> None:
        client = app.get_client(self._account)

        identity_info = client.get_module("OMEMO").backend.get_identity_infos(
            str(contact.jid),
            only_active=contact.is_groupchat,
            trust=OMEMOTrust.UNDECIDED if contact.is_groupchat else None,
        )

        for info in identity_info:
            self._ui.list.append(DeviceRow(contact, info))

        assert self._contact is not None
        if self._contact.is_groupchat:
            self._ui.list.set_visible(bool(identity_info))
            self._ui.undecided_placeholder.set_visible(not bool(identity_info))

    def _load_qrcode(self) -> None:
        client = app.get_client(self._account)
        uri = compose_trust_uri(
            client.get_own_jid(),
            [client.get_module("OMEMO").backend.get_our_identity()],
        )
        log.debug("Trust URI: %s", uri)
        self._ui.qr_code_image.set_from_paintable(generate_qr_code(uri))

    def _on_show_inactive(self, _switch: Gtk.Switch, _state: bool) -> None:
        self._ui.list.invalidate_filter()

    def _on_clear_devices_clicked(self, _button: Gtk.Button) -> None:
        def _on_response() -> None:
            client = app.get_client(self._account)
            client.get_module("OMEMO").clear_devicelist()

        ConfirmationAlertDialog(
            _("Clear Devices?"),
            _("This will clear the devices store for your account."),
            confirm_label=_("_Clear Devices"),
            callback=_on_response,
        )

    def _on_manage_trust_clicked(self, _button: Gtk.Button) -> None:
        assert self._contact is not None
        window = open_window("Preferences")
        window.show_page(f"{self._contact.account}-encryption-omemo")

    def _on_copy_button_clicked(self, _button: Gtk.Button) -> None:
        app.window.get_clipboard().set(self._our_fpr_formatted)


class DeviceRow(Adw.ActionRow, SignalManager):
    def __init__(
        self, contact: types.ChatContactT, identity_info: IdentityInfo
    ) -> None:
        Adw.ActionRow.__init__(self)
        SignalManager.__init__(self)
        self.add_css_class("omemo-device-row")

        self._contact = contact
        self._client = app.get_client(contact.account)

        self._address = identity_info.address
        self._identity_info = identity_info
        self._trust = identity_info.trust

        subtitle_entries: list[str] = []
        if contact.is_groupchat:
            subtitle_entries.append(self._address)

        self._formatted_fingerprint = self._identity_info.public_key.get_fingerprint(
            formatted=True
        )

        if self._identity_info.last_seen is not None and not contact.is_groupchat:
            last_seen_data = time.strftime(
                app.settings.get("date_time_format"),
                time.localtime(self._identity_info.last_seen),
            )
        else:
            last_seen_data = _("Never")
        subtitle_entries.append(_("Last seen: %s") % last_seen_data)

        if not self._identity_info.active:
            subtitle_entries.append(_("(inactive)"))

        self.set_title(self._formatted_fingerprint)
        self.set_subtitle(" ".join(subtitle_entries))

        self._trust_label = TrustLabel(identity_info.trust)
        self.add_suffix(self._trust_label)

        self._trust_button = TrustButton(self)
        self.add_suffix(self._trust_button)

        self._copy_button = Gtk.Button(
            icon_name="lucide-copy-symbolic",
            tooltip_text=_("Copy to Clipboard"),
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.END,
        )
        self._connect(self._copy_button, "clicked", self._on_copy_button_clicked)
        self.add_suffix(self._copy_button)

    def do_unroot(self) -> None:
        del self._trust_button
        self._disconnect_all()
        Adw.ActionRow.do_unroot(self)
        app.check_finalize(self)

    def delete_fingerprint(self, *args: Any) -> None:
        def _on_response() -> None:
            self._client.get_module("OMEMO").backend.delete_session(
                self._address, self._identity_info.device_id, delete_identity=True
            )

            listbox = cast(Gtk.ListBox, self.get_parent())
            listbox.remove(self)

        ConfirmationAlertDialog(
            _("Delete Fingerprint?"),
            _("Doing so will permanently delete this Fingerprint"),
            confirm_label=_("_Delete"),
            appearance="destructive",
            callback=_on_response,
        )

    def set_trust(self, trust: OMEMOTrust) -> None:
        self._trust = trust
        self._trust_label.set_trust(trust)

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

    def _on_copy_button_clicked(self, _button: Gtk.Button) -> None:
        app.window.get_clipboard().set(self._formatted_fingerprint)


class TrustLabel(Gtk.Box):
    def __init__(self, trust: OMEMOTrust) -> None:
        Gtk.Box.__init__(
            self,
            margin_end=12,
            spacing=6,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            halign=Gtk.Align.END,
        )

        self._label = Gtk.Label()
        self._image = Gtk.Image()

        self.append(self._image)
        self.append(self._label)

        self.set_trust(trust)

    def set_trust(self, trust: OMEMOTrust) -> None:
        remove_css_class(self._label, "omemo-")
        remove_css_class(self._image, "omemo-")

        icon_name, text, css_class = TRUST_DATA[trust]

        self._label.set_text(text)
        self._label.add_css_class(css_class)

        self._image.set_from_icon_name(icon_name)
        self._image.add_css_class(css_class)


class TrustButton(Gtk.MenuButton):
    def __init__(self, row: DeviceRow) -> None:
        Gtk.MenuButton.__init__(self, halign=Gtk.Align.END, valign=Gtk.Align.CENTER)
        self._row = row
        self._trust_popover = TrustPopver(row, self)

        image = Gtk.Image.new_from_icon_name("lucide-shield-symbolic")
        self.set_child(image)
        self.set_popover(self._trust_popover)
        self.set_tooltip_text(_("Set Trust"))

    def do_unroot(self) -> None:
        del self._trust_popover
        del self._row

        Gtk.MenuButton.do_unroot(self)
        app.check_finalize(self)


class TrustPopver(Gtk.Popover, SignalManager):
    def __init__(self, row: DeviceRow, trust_button: TrustButton) -> None:
        Gtk.Popover.__init__(self)
        SignalManager.__init__(self)
        self._row = row
        self._trust_button = trust_button

        self._listbox = Gtk.ListBox()
        self._listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.update()
        self.set_child(self._listbox)
        self._connect(self._listbox, "row-activated", self._activated)
        self.add_css_class("menu")

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
            self.update()

    def update(self) -> None:
        self._listbox.remove_all()

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
            "lucide-shield-symbolic",
            _("Blind Trust"),
            "encrypted-color",
            OMEMOTrust.BLIND,
        )


class VerifiedOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(
            self,
            "lucide-shield-check-symbolic",
            _("Verified"),
            "encrypted-color",
            OMEMOTrust.VERIFIED,
        )


class NotTrustedOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(
            self,
            "lucide-circle-x-symbolic",
            _("Untrusted"),
            "error",
            OMEMOTrust.UNTRUSTED,
        )


class DeleteOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(self, "lucide-trash-symbolic", _("Delete"), "")
