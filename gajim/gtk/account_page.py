# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.modules.contacts import BareContact

from gajim.gtk.menus import get_account_menu
from gajim.gtk.status_message_selector import StatusMessageSelector
from gajim.gtk.status_selector import StatusSelector
from gajim.gtk.util.misc import get_ui_string


@Gtk.Template(string=get_ui_string("account_page.ui"))
class AccountPage(Gtk.Box):
    __gtype_name__ = "AccountPage"

    _avatar_image: Gtk.Image = Gtk.Template.Child()
    _account_label: Gtk.Label = Gtk.Template.Child()
    _our_jid_label: Gtk.Label = Gtk.Template.Child()
    _menu_button: Gtk.MenuButton = Gtk.Template.Child()
    _status_selector: StatusSelector = Gtk.Template.Child()
    _status_message_selector: StatusMessageSelector = Gtk.Template.Child()

    def __init__(self) -> None:
        self._account: str | None = None

        Gtk.Box.__init__(self)

        self._contact: BareContact | None = None

        self._menu_button.set_create_popup_func(self._on_menu_popup)

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

    def _update_page(self) -> None:
        self._menu_button.set_sensitive(self._account is not None)

        if self._account is None:
            self._our_jid_label.set_text("")
            self._account_label.set_text("")
            self._avatar_image.set_from_paintable(None)
            self._status_selector.set_account(None)
            self._status_message_selector.set_account(None)
            return

        assert self._contact is not None

        account_label = app.settings.get_account_setting(self._account, "account_label")

        self._update_avatar()
        self._update_account_label(account_label)
        self._our_jid_label.set_text(str(self._contact.jid))
        self._status_selector.set_account(self._account)
        self._status_message_selector.set_account(self._account)
