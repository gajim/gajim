# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.events import AccountDisabled
from gajim.common.events import AccountEnabled
from gajim.common.events import ShowChanged
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.util.status import get_uf_show

from gajim.gtk.avatar import convert_surface_to_texture
from gajim.gtk.avatar import get_show_circle
from gajim.gtk.util.classes import SignalManager


class AccountSideBar(Gtk.Box, SignalManager):
    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self.add_css_class("account-sidebar")

        gesture_primary_click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        self._connect(gesture_primary_click, "pressed", self._on_button_press)
        self.add_controller(gesture_primary_click)

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_secondary_click, "pressed", self._on_button_press)
        self.add_controller(gesture_secondary_click)

        hover_controller = Gtk.EventControllerMotion()
        self._connect(hover_controller, "enter", self._on_cursor_enter)
        self._connect(hover_controller, "leave", self._on_cursor_leave)
        self.add_controller(hover_controller)

        container = Gtk.Box()
        self.append(container)

        self._selection_bar = Gtk.Box(width_request=6, margin_start=1)
        self._selection_bar.add_css_class("selection-bar")
        container.append(self._selection_bar)

        self._account_avatar = AccountAvatar()
        container.append(self._account_avatar)

        self._accounts_popover = Gtk.Popover()
        self.append(self._accounts_popover)

        self._status_popover = self._create_status_popover()
        self.append(self._status_popover)

    def do_unroot(self, *args: Any) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def select(self) -> None:
        self._selection_bar.add_css_class("selection-bar-selected")

    def unselect(self) -> None:
        self._selection_bar.remove_css_class("selection-bar-selected")

    def _on_cursor_enter(
        self,
        _controller: Gtk.EventControllerMotion,
        _x: int,
        _y: int,
    ) -> None:
        self._selection_bar.add_css_class("selection-bar-hover")

    def _on_cursor_leave(self, _controller: Gtk.EventControllerMotion) -> None:
        self._selection_bar.remove_css_class("selection-bar-hover")

    def _on_button_press(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> int:
        accounts = app.settings.get_active_accounts()

        if gesture_click.get_current_button() == Gdk.BUTTON_PRIMARY:
            # Left click
            # Show current account's page if only one account is active
            # If more than one account is active, a popover containing
            # all accounts is shown (clicking one opens the account's page)
            if len(accounts) == 1:
                app.window.show_account_page(accounts[0])
                return True

            self._display_accounts_menu()

        elif gesture_click.get_current_button() == Gdk.BUTTON_SECONDARY:
            # Right click
            # Show account context menu containing account status selector
            # Global status selector if multiple accounts are active
            self._accounts_popover.popdown()
            self._status_popover.popup()

        return True

    def _display_accounts_menu(self):
        popover_scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER, propagate_natural_height=True
        )

        self._accounts_popover.set_child(popover_scrolled)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        box.add_css_class("p-3")
        popover_scrolled.set_child(box)

        for account in app.settings.get_active_accounts():
            account_color_bar = Gtk.Box(width_request=6)
            color_class = app.css_config.get_dynamic_class(account)
            account_color_bar.add_css_class("account-identifier-bar")
            account_color_bar.add_css_class(color_class)

            avatar = Gtk.Image(pixel_size=AvatarSize.ACCOUNT_SIDE_BAR)
            label = Gtk.Label(
                halign=Gtk.Align.START,
                label=app.settings.get_account_setting(account, "account_label"),
            )

            texture = app.app.avatar_storage.get_account_button_texture(
                account, AvatarSize.ACCOUNT_SIDE_BAR, self.get_scale_factor()
            )
            avatar.set_from_paintable(texture)

            account_box = Gtk.Box(spacing=6)
            account_box.append(account_color_bar)
            account_box.append(avatar)
            account_box.append(label)

            button = Gtk.Button()
            button.add_css_class("flat")
            button.set_child(account_box)
            button.connect(
                "clicked",
                self._on_account_clicked,
                account,
            )
            box.append(button)

        self._status_popover.popdown()
        self._accounts_popover.popup()

    def _on_account_clicked(
        self,
        _button: Gtk.MenuButton,
        account: str,
    ) -> None:

        self._accounts_popover.popdown()
        app.window.show_account_page(account)

    def _create_status_popover(self) -> Gtk.Popover:
        popover_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        popover_box.add_css_class("m-3")
        popover_items = [
            "online",
            "away",
            "xa",
            "dnd",
            "separator",
            "offline",
        ]

        for item in popover_items:
            if item == "separator":
                popover_box.append(Gtk.Separator())
                continue

            show_icon = Gtk.Image(pixel_size=AvatarSize.SHOW_CIRCLE)
            show_label = Gtk.Label()
            show_label.set_halign(Gtk.Align.START)

            surface = get_show_circle(
                item, AvatarSize.SHOW_CIRCLE, self.get_scale_factor()
            )
            show_icon.set_from_paintable(convert_surface_to_texture(surface))
            show_label.set_text_with_mnemonic(get_uf_show(item, use_mnemonic=True))

            show_box = Gtk.Box(spacing=6)
            show_box.append(show_icon)
            show_box.append(show_label)

            button = Gtk.Button()
            button.add_css_class("flat")
            button.set_child(show_box)
            self._connect(button, "clicked", self._on_change_status, item)
            popover_box.append(button)

        status_popover = Gtk.Popover()
        status_popover.set_child(popover_box)
        return status_popover

    def _on_change_status(
        self,
        _button: Gtk.Button,
        new_status: str,
    ) -> None:

        self._status_popover.popdown()

        accounts = app.get_connected_accounts()
        account = accounts[0] if len(accounts) > 1 else None
        app.app.change_status(status=new_status, account=account)


class AccountAvatar(Gtk.Image, EventHelper):
    def __init__(self) -> None:
        Gtk.Image.__init__(self, pixel_size=AvatarSize.ACCOUNT_SIDE_BAR)
        EventHelper.__init__(self)

        self._client: Client | None = None
        self._contact: BareContact | None = None

        self.register_event("account-enabled", ged.GUI1, self._on_account_changed)
        self.register_event("account-disabled", ged.GUI1, self._on_account_changed)
        self.register_event("our-show", ged.GUI1, self._on_our_show)

        self._update_image()

    def _on_account_changed(self, _event: AccountEnabled | AccountDisabled) -> None:

        if self._client is not None:
            self._client.disconnect_all_from_obj(self)
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        accounts = app.settings.get_active_accounts()

        if len(accounts) == 1:
            account = accounts[0]
            self._client = app.get_client(account)
            self._client.connect_signal("state-changed", self._on_event)

            jid = app.get_jid_from_account(account)
            contact = self._client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            self._contact = contact
            self._contact.connect("avatar-update", self._on_event)
            self._contact.connect("presence-update", self._on_event)

        self._update_image()

    def _on_our_show(self, _event: ShowChanged) -> None:
        self._update_image()

    def do_unroot(self) -> None:
        if self._client is not None:
            self._client.disconnect_all_from_obj(self)
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        Gtk.Image.do_unroot(self)
        app.check_finalize(self)

    def _on_event(self, *args: Any) -> None:
        self._update_image()

    def _update_image(self) -> None:
        accounts = app.settings.get_active_accounts()

        if len(accounts) == 1:
            account = accounts[0]
            account_label = app.settings.get_account_setting(account, "account_label")
            self.set_tooltip_text(_("Account: %s") % account_label)
        else:
            account = None
            self.set_tooltip_text(_("Accounts"))

        texture = app.app.avatar_storage.get_account_button_texture(
            account, AvatarSize.ACCOUNT_SIDE_BAR, self.get_scale_factor()
        )
        self.set_from_paintable(texture)
