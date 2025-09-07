# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Adw
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID
from nbxmpp.modules.vcard4 import EmailProperty
from nbxmpp.modules.vcard4 import OrgProperty
from nbxmpp.modules.vcard4 import RoleProperty
from nbxmpp.modules.vcard4 import TelProperty
from nbxmpp.modules.vcard4 import TzProperty
from nbxmpp.modules.vcard4 import VCard

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.modules.contacts import BareContact
from gajim.common.util.user_strings import get_time_zone_string

from gajim.gtk.menus import get_account_menu
from gajim.gtk.preference.widgets import CopyButton
from gajim.gtk.status_message_row import StatusMessageSelectorRow
from gajim.gtk.status_selector import StatusSelector
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string


@Gtk.Template(string=get_ui_string("account_page.ui"))
class AccountPage(Gtk.Box, SignalManager):
    __gtype_name__ = "AccountPage"

    _avatar_image: Gtk.Image = Gtk.Template.Child()
    _name_label: Gtk.Label = Gtk.Template.Child()
    _account_label: Gtk.Label = Gtk.Template.Child()

    _settings_button: Gtk.Button = Gtk.Template.Child()
    _menu_button: Gtk.MenuButton = Gtk.Template.Child()

    _our_jid_row: Adw.ActionRow = Gtk.Template.Child()

    _status_selector: StatusSelector = Gtk.Template.Child()
    _status_message_row: StatusMessageSelectorRow = Gtk.Template.Child()

    _profile_button: Gtk.Button = Gtk.Template.Child()
    _profile_name_row: Adw.ActionRow = Gtk.Template.Child()
    _profile_org_row: Adw.ActionRow = Gtk.Template.Child()
    _profile_role_row: Adw.ActionRow = Gtk.Template.Child()
    _profile_email_row: Adw.ActionRow = Gtk.Template.Child()
    _profile_email_clipboard_button: CopyButton = Gtk.Template.Child()
    _profile_tel_row: Adw.ActionRow = Gtk.Template.Child()
    _profile_tel_clipboard_button: CopyButton = Gtk.Template.Child()
    _profile_timezone_row: Adw.ActionRow = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._account: str | None = None
        self._contact: BareContact | None = None

        self._menu_button.set_create_popup_func(self._on_menu_popup)

        self._profile_email = None
        self._profile_tel = None

        self._connect(
            self._profile_email_clipboard_button,
            "clicked",
            self._on_profile_email_copy_clicked,
        )
        self._connect(
            self._profile_tel_clipboard_button,
            "clicked",
            self._on_profile_tel_copy_clicked,
        )

    @GObject.Property(type=str)
    def account(self) -> str | None:  # pyright: ignore
        return self._account

    @account.setter
    def account(self, account: str | None) -> None:
        if self._account == account:
            return

        self._disconnect_signals()

        self._account = account
        self._contact = None
        if account is not None:
            client = app.get_client(account)
            jid = client.get_own_jid().bare
            contact = client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            self._contact = contact

            self._settings_button.set_action_target_value(GLib.Variant("s", account))

            self._profile_button.set_action_target_value(GLib.Variant("s", account))
            self._profile_button.set_action_name(f"app.{account}-profile")

            vcard = client.get_module("VCard4").request_vcard(
                jid=self._contact.jid, callback=self._on_vcard_received, use_cache=True
            )
            if vcard is not None:
                self._set_vcard_rows(vcard)

        self._connect_signals()

        self._update_page()

    def _connect_signals(self) -> None:
        if self._account is None:
            return

        assert self._contact is not None

        self._contact.connect("avatar-update", self._on_avatar_update)
        app.settings.connect_signal(
            "account_label", self._on_account_label_changed, self._account
        )

    def _disconnect_signals(self) -> None:
        if self._account is None:
            return

        assert self._contact is not None

        self._contact.disconnect_all_from_obj(self)
        app.settings.disconnect_signals(self)

    def _on_profile_email_copy_clicked(self, _button: CopyButton) -> None:
        app.window.get_clipboard().set(self._profile_email)

    def _on_profile_tel_copy_clicked(self, _button: CopyButton) -> None:
        app.window.get_clipboard().set(self._profile_tel)

    def set_account(self, account: str | None) -> None:
        self.account = account

    def get_account(self) -> str | None:
        return self._account

    def _on_menu_popup(self, menu_button: Gtk.MenuButton) -> None:
        assert self._account is not None
        menu_button.set_menu_model(get_account_menu(self._account))

    def _on_account_label_changed(self, value: str, *args: Any) -> None:
        self._update_account_label(value)

    def _on_avatar_update(self, *args: Any) -> None:
        self._update_avatar()

    def _update_account_label(self, label: str) -> None:
        self._account_label.set_text(label)

    def _update_avatar(self) -> None:
        assert self._contact is not None
        texture = self._contact.get_avatar(
            AvatarSize.ACCOUNT_PAGE, self.get_scale_factor(), add_show=False
        )
        self._avatar_image.set_from_paintable(texture)

    def _on_vcard_received(self, _jid: JID, vcard: VCard) -> None:
        self._set_vcard_rows(vcard)

    def _set_vcard_rows(self, vcard: VCard) -> None:
        for prop in vcard.get_properties():
            match prop:
                case OrgProperty():
                    self._profile_org_row.set_subtitle(prop.values[0])
                    self._profile_org_row.set_visible(True)
                case RoleProperty():
                    self._profile_role_row.set_subtitle(prop.value)
                    self._profile_role_row.set_visible(True)
                case EmailProperty():
                    self._profile_email_row.set_subtitle(prop.value)
                    self._profile_email_row.set_action_target_value(
                        GLib.Variant("s", f"mailto:{prop.value}")
                    )
                    self._profile_email_row.set_visible(True)
                    self._profile_email = prop.value
                case TelProperty():
                    self._profile_tel_row.set_subtitle(prop.value)
                    self._profile_tel_row.set_action_target_value(
                        GLib.Variant("s", f"tel:{prop.value}")
                    )
                    self._profile_tel_row.set_visible(True)
                    self._profile_tel = prop.value
                case TzProperty():
                    self._profile_timezone_row.set_subtitle(get_time_zone_string(prop))
                    self._profile_timezone_row.set_visible(True)
                case _:
                    pass

    def _update_page(self) -> None:
        self._menu_button.set_sensitive(self._account is not None)

        if self._account is None:
            self._our_jid_row.set_subtitle("")
            self._account_label.set_text("")
            self._avatar_image.set_from_paintable(None)
            self._status_selector.set_account(None)
            self._status_message_row.set_account(None)
            return

        assert self._contact is not None

        account_label = app.settings.get_account_setting(self._account, "account_label")

        self._update_avatar()
        self._update_account_label(account_label)
        self._name_label.set_label(app.nicks[self._account])

        self._our_jid_row.set_subtitle(str(self._contact.jid))
        self._status_selector.set_account(self._account)
        self._status_message_row.set_account(self._account)

        self._profile_name_row.set_subtitle(app.nicks[self._account])
