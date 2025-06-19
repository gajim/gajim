# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.configpaths import get_ui_path
from gajim.common.const import AvatarSize
from gajim.common.events import AccountDisabled
from gajim.common.events import AccountEnabled
from gajim.common.events import ShowChanged
from gajim.common.ged import EventHelper
from gajim.common.i18n import _

from gajim.gtk.status_selector import StatusSelectorPopover
from gajim.gtk.util.classes import SignalManager


@Gtk.Template(filename=get_ui_path("account_side_bar.ui"))
class AccountSideBar(Gtk.Box, EventHelper, SignalManager):
    __gtype_name__ = "AccountSideBar"

    _selection_bar: Gtk.Box = Gtk.Template.Child()
    _avatar: AccountAvatar = Gtk.Template.Child()
    _account_popover: AccountPopover = Gtk.Template.Child()
    _status_popover: StatusSelectorPopover = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)
        EventHelper.__init__(self)

        gesture_primary_click = Gtk.GestureClick(button=0)
        self._connect(gesture_primary_click, "pressed", self._on_button_press)
        self.add_controller(gesture_primary_click)

        hover_controller = Gtk.EventControllerMotion()
        self._connect(hover_controller, "enter", self._on_cursor_enter)
        self._connect(hover_controller, "leave", self._on_cursor_leave)
        self.add_controller(hover_controller)

        accounts = app.settings.get_active_accounts()
        for account in accounts:
            self._account_popover.add_account(account)
            self._avatar.add_account(account)

            client = app.get_client(account)
            contact = client.get_own_contact()

            client.connect_signal("state-changed", self._on_client_state_changed)
            contact.connect("avatar-update", self._on_avatar_update)

        self.register_event("account-enabled", ged.GUI1, self._on_account_enabled)
        self.register_event("account-disabled", ged.GUI1, self._on_account_disabled)
        self.register_event("our-show", ged.GUI1, self._on_our_show)

    def do_unroot(self, *args: Any) -> None:
        raise NotImplementedError

    def select(self) -> None:
        self._selection_bar.add_css_class("selection-bar-selected")

    def unselect(self) -> None:
        self._selection_bar.remove_css_class("selection-bar-selected")

    def _on_account_enabled(self, event: AccountEnabled) -> None:
        client = app.get_client(event.account)
        contact = client.get_own_contact()

        client.connect_signal("state-changed", self._on_client_state_changed)
        contact.connect("avatar-update", self._on_avatar_update)

        self._account_popover.add_account(event.account)
        self._avatar.add_account(event.account)

    def _on_account_disabled(self, event: AccountDisabled) -> None:
        client = app.get_client(event.account)
        contact = client.get_own_contact()

        client.disconnect_all_from_obj(self)
        contact.disconnect_all_from_obj(self)

        self._account_popover.remove_account(event.account)
        self._avatar.remove_account(event.account)

    def _on_our_show(self, _event: ShowChanged) -> None:
        self._avatar.update()

    def _on_avatar_update(self, *args: Any) -> None:
        self._avatar.update()

    def _on_client_state_changed(self, *args: Any) -> None:
        self._avatar.update()

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

        current_button = gesture_click.get_current_button()
        if current_button == Gdk.BUTTON_PRIMARY:
            # Left click
            self._status_popover.popdown()
            self._account_popover.popup()
            return Gdk.EVENT_STOP

        if current_button == Gdk.BUTTON_SECONDARY:
            # Right click
            self._status_popover.popup()
            self._account_popover.popdown()
            return Gdk.EVENT_STOP

        return Gdk.EVENT_STOP

    @Gtk.Template.Callback()
    def _on_account_clicked(
        self,
        _popover: AccountPopover,
        account: str,
    ) -> None:
        app.window.show_account_page(account)

    @Gtk.Template.Callback()
    def _on_status_clicked(self, _button: Gtk.Button, status: str) -> None:
        accounts = app.get_connected_accounts()
        account = accounts[0] if len(accounts) == 1 else None
        app.app.change_status(status=status, account=account)


class AccountAvatar(Gtk.Widget, EventHelper):
    __gtype_name__ = "AccountAvatar"

    def __init__(self) -> None:
        Gtk.Widget.__init__(self)
        EventHelper.__init__(self)

        self._accounts: set[str] = set()

        self.set_layout_manager(Gtk.BinLayout())
        self.add_css_class("account-sidebar-image")

        self._avatar_image = Gtk.Image(pixel_size=AvatarSize.ACCOUNT_SIDE_BAR)
        self._avatar_image.set_parent(self)

        self._connectivity_image = Gtk.Image(
            icon_name="dialog-warning-symbolic",
            pixel_size=AvatarSize.ACCOUNT_SIDE_BAR_WARNING,
            halign=Gtk.Align.END,
            valign=Gtk.Align.END,
            visible=False,
        )
        self._connectivity_image.set_parent(self)
        self._connectivity_image.add_css_class("warning")

        self.update()

    def do_unroot(self) -> None:
        raise NotImplementedError

    def add_account(self, account: str) -> None:
        self._accounts.add(account)
        self.update()

    def remove_account(self, account: str) -> None:
        self._accounts.discard(account)
        self.update()

    def update(self) -> None:
        self._update_image()
        self._update_tooltip()

    def _update_tooltip(self) -> None:
        tooltip_text = _("Accounts")
        if self._has_connectivity_issues():
            tooltip_text += "\n" + _("There are connectivity issues")

        self.set_tooltip_text(tooltip_text)

    def _update_image(self) -> None:
        self._connectivity_image.set_visible(self._has_connectivity_issues())

        account = None
        if len(self._accounts) == 1:
            account = next(iter(self._accounts))

        texture = app.app.avatar_storage.get_account_button_texture(
            account, AvatarSize.ACCOUNT_SIDE_BAR, self.get_scale_factor()
        )
        self._avatar_image.set_from_paintable(texture)

    def _has_connectivity_issues(self) -> bool:
        for account in self._accounts:
            client = app.get_client(account)
            if client.state.is_disconnected or client.state.is_reconnect_scheduled:
                return True
        return False


@Gtk.Template(filename=get_ui_path("account_popover.ui"))
class AccountPopover(Gtk.Popover):
    __gtype_name__ = "AccountPopover"

    __gsignals__ = {
        "clicked": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),
        )
    }

    _box: Gtk.Box = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Popover.__init__(self)
        self._buttons: dict[str, AccountPopoverButton] = {}

    def _on_clicked(self, button: AccountPopoverButton) -> None:
        self.emit("clicked", button.get_account())
        self.popdown()

    @Gtk.Template.Callback()
    def on_manage_clicked(self, button: Gtk.Button) -> None:
        self.popdown()

    def add_account(self, account: str) -> None:
        if account in self._buttons:
            raise ValueError("Account cannot be added multiple times")

        button = AccountPopoverButton(account=account)
        button.connect("clicked", self._on_clicked)
        self._buttons[account] = button
        self._box.append(button)

    def remove_account(self, account: str) -> None:
        button = self._buttons.get(account)
        if button is None:
            raise ValueError("Account button for %s not found" % account)

        self._box.remove(button)
        del self._buttons[account]


@Gtk.Template(filename=get_ui_path("account_popover_button.ui"))
class AccountPopoverButton(Gtk.Button):
    __gtype_name__ = "AccountPopoverButton"

    _color_bar: Gtk.Box = Gtk.Template.Child()
    _avatar: Gtk.Image = Gtk.Template.Child()
    _label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, account: str = "") -> None:
        Gtk.Button.__init__(self)

        self._account = ""
        self.set_account(account)

    def do_unroot(self) -> None:
        Gtk.Button.do_unroot(self)
        app.check_finalize(self)

    def get_account(self) -> str:
        return self._account

    def set_account(self, account: str) -> None:
        if not account or self._account == account:
            return

        if self._account:
            self._clear_widgets()

        color_class = app.css_config.get_dynamic_class(account)
        self._color_bar.add_css_class(color_class)

        label = app.settings.get_account_setting(account, "account_label")
        self._label.set_text(label)

        texture = app.app.avatar_storage.get_account_button_texture(
            account, AvatarSize.ACCOUNT_SIDE_BAR, self.get_scale_factor()
        )
        self._avatar.set_from_paintable(texture)

        self._account = account

    def _clear_widgets(self) -> None:
        assert self._account is not None
        color_class = app.css_config.get_dynamic_class(self._account)
        self._color_bar.remove_css_class(color_class)
        self._label.set_text("")
        self._avatar.set_from_paintable(None)
