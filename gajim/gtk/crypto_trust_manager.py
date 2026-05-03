# Copyright (C) 2019 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal

import locale
import logging

from gi.repository import Adw
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common import types
from gajim.common.const import Trust
from gajim.common.events import AccountConnected
from gajim.common.events import AccountDisconnected
from gajim.common.ged import EventHelper
from gajim.common.helpers import generate_qr_code
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.omemo import OMEMO
from gajim.common.modules.openpgp import OpenPGP
from gajim.common.modules.util import PublicKeyData

from gajim.gtk.alert import ConfirmationAlertDialog
from gajim.gtk.builder import get_builder
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import clear_listbox
from gajim.gtk.util.misc import remove_css_class
from gajim.gtk.util.window import open_window

log = logging.getLogger("gajim.gtk.crypto_trust_manager")


TRUST_DATA = {
    Trust.UNTRUSTED: (
        "lucide-shield-x-symbolic",
        _("Untrusted"),
        "crypto-untrusted-color",
    ),
    Trust.UNDECIDED: (
        "lucide-shield-question-mark-symbolic",
        _("Not Decided"),
        "crypto-undecided-color",
    ),
    Trust.VERIFIED: (
        "lucide-shield-check-symbolic",
        _("Verified"),
        "crypto-verified-color",
    ),
    Trust.BLIND: (
        "lucide-shield-symbolic",
        _("Blind Trust"),
        "crypto-blind-color",
    ),
}


class CryptoTrustManager(Gtk.Box, EventHelper, SignalManager):
    def __init__(
        self,
        encryption: Literal["OMEMO", "OpenPGP"],
        account: str,
        contact: types.ChatContactT | None = None,
    ) -> None:
        Gtk.Box.__init__(self)
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self._account = account
        self._contact = contact
        self._encryption: Literal["OMEMO", "OpenPGP"] = encryption

        self._ui = get_builder("crypto_trust_manager.ui")
        self.append(self._ui.stack)

        self._connect(
            self._ui.manage_trust_button, "clicked", self._on_manage_trust_clicked
        )
        self._connect(
            self._ui.show_inactive_switch, "state-set", self._on_show_inactive
        )
        self._connect(
            self._ui.remove_public_keys_button,
            "clicked",
            self._on_remove_public_keys_clicked,
        )
        self._connect(self._ui.copy_button, "clicked", self._on_copy_button_clicked)

        self._ui.list.set_sort_func(self._sort_func, None)
        self._ui.list.set_filter_func(self._filter_func)

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
        self._crypto_module = client.get_module(self._encryption)

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

        self._our_public_key = self._crypto_module.get_our_public_key()
        if self._our_public_key is None:
            fingerprint = _("No key found")
        else:
            fingerprint = self._our_public_key.pretty_fingerprint()

        self._ui.our_fingerprint_row.set_title(fingerprint)
        self._ui.our_fingerprint_2.set_text(fingerprint)

        self.update()
        self._load_qrcode()

    def update(self) -> None:
        assert self._contact is not None
        clear_listbox(self._ui.list)

        if isinstance(self._contact, BareContact) and self._contact.is_self:
            self._ui.remove_public_keys_button.set_visible(True)
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
    def _filter_func(row: DeviceRow) -> bool:
        return row.active

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
        public_key_data = self._crypto_module.get_public_keys(
            contact.jid, is_groupchat=contact.is_groupchat
        )

        for key in public_key_data:
            self._ui.list.append(DeviceRow(contact, key, self._crypto_module))

        assert self._contact is not None
        if self._contact.is_groupchat:
            self._ui.list.set_visible(bool(public_key_data))
            self._ui.undecided_placeholder.set_visible(not bool(public_key_data))

    def _load_qrcode(self) -> None:
        client = app.get_client(self._account)
        uri = self._crypto_module.compose_trust_uri(client.get_own_jid())
        log.debug("Trust URI: %s", uri)
        self._ui.qr_code_image.set_from_paintable(
            generate_qr_code(uri) if uri else None
        )
        self._ui.qr_menu_button.set_visible(bool(uri))

    def _on_show_inactive(self, _switch: Gtk.Switch, state: bool) -> None:
        self._ui.list.set_filter_func(None if state else self._filter_func)
        self._ui.list.invalidate_filter()

    def _on_remove_public_keys_clicked(self, _button: Gtk.Button) -> None:
        def _on_response() -> None:
            self._crypto_module.clear_keylist()

        ConfirmationAlertDialog(
            _("Remove Public Keys?"),
            _("This will remove all published public keys from your account."),
            confirm_label=_("_Remove Public Keys"),
            callback=_on_response,
        )

    def _on_manage_trust_clicked(self, _button: Gtk.Button) -> None:
        assert self._contact is not None
        window = open_window("Preferences")
        window.show_page(
            f"{self._contact.account}-encryption-{self._encryption.lower()}"
        )

    def _on_copy_button_clicked(self, _button: Gtk.Button) -> None:
        if self._our_public_key is None:
            return
        app.window.get_clipboard().set(self._our_public_key.pretty_fingerprint())


class DeviceRow(Adw.ActionRow, SignalManager):
    def __init__(
        self,
        contact: types.ChatContactT,
        public_key_data: PublicKeyData,
        crypto_module: OMEMO | OpenPGP,
    ) -> None:
        Adw.ActionRow.__init__(self)
        SignalManager.__init__(self)
        self.add_css_class("crypto-device-row")

        self._contact = contact
        self._client = app.get_client(contact.account)

        self._crypto_module = crypto_module

        self._public_key_data = public_key_data
        self._trust = public_key_data.trust

        subtitle_entries: list[str] = []
        if contact.is_groupchat:
            subtitle_entries.append(str(self._public_key_data.address))

        if self._public_key_data.last_seen is not None and not contact.is_groupchat:
            datetime = self._public_key_data.last_seen.astimezone()
            last_seen_data = datetime.strftime(app.settings.get("date_time_format"))
        else:
            last_seen_data = _("Never")
        subtitle_entries.append(_("Last seen: %s") % last_seen_data)

        if not self._public_key_data.active:
            subtitle_entries.append(_("(inactive)"))

        self.set_title(self._public_key_data.pretty_fingerprint())
        self.set_subtitle(" ".join(subtitle_entries))

        self._trust_label = TrustLabel(public_key_data.trust)
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
            self._crypto_module.remove_public_key(self._public_key_data)
            listbox = cast(Gtk.ListBox, self.get_parent())
            listbox.remove(self)

        ConfirmationAlertDialog(
            _("Delete Fingerprint?"),
            _("Doing so will permanently delete this Fingerprint"),
            confirm_label=_("_Delete"),
            appearance="destructive",
            callback=_on_response,
        )

    def set_trust(self, trust: Trust) -> None:
        self._trust = trust
        self._trust_label.set_trust(trust)
        self._crypto_module.set_public_key_trust(self._public_key_data, trust)

    @property
    def trust(self) -> Trust:
        return self._trust

    @property
    def active(self) -> bool:
        return self._public_key_data.active

    @property
    def address(self) -> str:
        return str(self._public_key_data.address)

    def _on_copy_button_clicked(self, _button: Gtk.Button) -> None:
        app.window.get_clipboard().set(self._public_key_data.pretty_fingerprint())


class TrustLabel(Gtk.Box):
    def __init__(self, trust: Trust) -> None:
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

    def set_trust(self, trust: Trust) -> None:
        remove_css_class(self._label, "crypto-")
        remove_css_class(self._image, "crypto-")

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

        if self._row.trust != Trust.VERIFIED:
            self._listbox.append(VerifiedOption())
        if self._row.trust != Trust.BLIND:
            self._listbox.append(BlindOption())
        if self._row.trust != Trust.UNTRUSTED:
            self._listbox.append(NotTrustedOption())
        self._listbox.append(DeleteOption())


class MenuOption(Gtk.ListBoxRow):
    def __init__(
        self, icon: str, label_text: str, color: str, type_: Trust | None = None
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
            Trust.BLIND,
        )


class VerifiedOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(
            self,
            "lucide-shield-check-symbolic",
            _("Verified"),
            "encrypted-color",
            Trust.VERIFIED,
        )


class NotTrustedOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(
            self,
            "lucide-circle-x-symbolic",
            _("Untrusted"),
            "error",
            Trust.UNTRUSTED,
        )


class DeleteOption(MenuOption):
    def __init__(self) -> None:
        MenuOption.__init__(self, "lucide-trash-symbolic", _("Delete"), "")
