# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import ResourceContact
from gajim.common.util.status import get_client_status

from gajim.gtk.util import iterate_listbox_children
from gajim.gtk.util import SignalManager


class AccountSideBar(Gtk.ListBox, SignalManager):
    def __init__(self) -> None:
        Gtk.ListBox.__init__(self)
        SignalManager.__init__(self)

        self.set_vexpand(True)
        self.set_valign(Gtk.Align.END)
        self.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.add_css_class("account-sidebar")
        self._connect(self, "row-activated", self._on_row_activated)

        for account in app.settings.get_active_accounts():
            self.add_account(account)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.ListBox.do_unroot(self)
        app.check_finalize(self)

    def add_account(self, account: str) -> None:
        self.append(Account(account))

    def remove_account(self, account: str) -> None:
        for row in cast(list[Account], iterate_listbox_children(self)):
            if row.account == account:
                self.remove(row)
                return

    @staticmethod
    def _on_row_activated(_listbox: AccountSideBar, row: Account) -> None:
        app.window.show_account_page(row.account)

    def activate_account_page(self, account: str) -> None:
        row = cast(Account | None, self.get_selected_row())
        if row is not None and row.account == account:
            return

        self.select_row(row)

    def update_unread_count(self, account: str, count: int) -> None:
        for row in cast(list[Account], iterate_listbox_children(self)):
            if row.account == account:
                row.set_unread_count(count)
                break


class Account(Gtk.ListBoxRow, EventHelper):
    def __init__(self, account: str) -> None:
        Gtk.ListBoxRow.__init__(self)
        EventHelper.__init__(self)
        self.add_css_class("account-sidebar-item")

        self.account = account
        self._account_class: str | None = None

        self.register_events(
            [
                ("account-enabled", ged.GUI1, self._update_account_color_visibility),
                ("account-disabled", ged.GUI1, self._update_account_color_visibility),
            ]
        )

        app.settings.connect_signal(
            "account_label", self._on_account_label_changed, account
        )

        selection_bar = Gtk.Box()
        selection_bar.set_size_request(6, -1)
        selection_bar.add_css_class("selection-bar")

        self._image = AccountAvatar(account)

        self._unread_label = Gtk.Label()
        self._unread_label.add_css_class("unread-counter")
        self._unread_label.set_visible(False)
        self._unread_label.set_halign(Gtk.Align.END)
        self._unread_label.set_valign(Gtk.Align.START)

        self._account_color_bar = Gtk.Box()
        self._account_color_bar.set_visible(False)
        self._account_color_bar.set_size_request(6, -1)
        self._account_color_bar.add_css_class("account-identifier-bar")
        self._update_account_color_visibility()

        self._account_box = Gtk.Box(spacing=3)
        self._account_box.set_tooltip_text(
            _("Account: %s") % app.get_account_label(account)
        )
        self._account_box.append(selection_bar)
        self._account_box.append(self._image)
        self._account_box.append(self._account_color_bar)
        self._set_account_color()

        overlay = Gtk.Overlay()
        overlay.set_child(self._account_box)
        overlay.add_overlay(self._unread_label)

        self.set_child(overlay)

    def do_unroot(self) -> None:
        self.unregister_events()
        app.settings.disconnect_signals(self)
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)

    def _on_account_label_changed(self, value: str, *args: Any) -> None:
        self._account_box.set_tooltip_text(_("Account: %s") % value)

    def _set_account_color(self) -> None:
        if self._account_class is not None:
            self._account_color_bar.remove_css_class(self._account_class)

        self._account_class = app.css_config.get_dynamic_class(self.account)
        self._account_color_bar.add_css_class(self._account_class)

    def set_unread_count(self, count: int) -> None:
        if count < 1000:
            self._unread_label.set_text(str(count))
        else:
            self._unread_label.set_text("999+")
        self._unread_label.set_visible(bool(count))

    def _update_account_color_visibility(self, *args: Any) -> None:
        visible = len(app.settings.get_active_accounts()) > 1
        self._account_color_bar.set_visible(visible)


class AccountAvatar(Gtk.Image):
    def __init__(self, account: str) -> None:
        Gtk.Image.__init__(self, pixel_size=AvatarSize.ACCOUNT_SIDE_BAR)

        self._account = account

        jid = app.get_jid_from_account(self._account)
        self._client = app.get_client(self._account)

        self._client.connect_signal("state-changed", self._on_event)

        self._contact = self._client.get_module("Contacts").get_contact(jid)
        self._contact.connect("avatar-update", self._on_event)
        self._contact.connect("presence-update", self._on_event)

        self._update_image()

    def do_unroot(self) -> None:
        self._contact.disconnect_all_from_obj(self)
        self._client.disconnect_all_from_obj(self)
        Gtk.Image.do_unroot(self)
        app.check_finalize(self)

    def _on_event(self, *args: Any) -> None:
        self._update_image()

    def _update_image(self) -> None:
        assert not isinstance(self._contact, ResourceContact)
        status = get_client_status(self._account)
        texture = app.app.avatar_storage.get_texture(
            self._contact, AvatarSize.ACCOUNT_SIDE_BAR, self.get_scale_factor(), status
        )
        self.set_pixel_size(AvatarSize.ACCOUNT_SIDE_BAR)
        self.set_from_paintable(texture)
