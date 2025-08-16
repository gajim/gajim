# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.events import AccountDisabled
from gajim.common.events import AccountEnabled
from gajim.common.events import RegisterActions
from gajim.common.ged import EventHelper
from gajim.common.i18n import _

from gajim.gtk.chat_page import ChatPage
from gajim.gtk.sidebar_listbox import SideBarListBox
from gajim.gtk.sidebar_listbox import SideBarListBoxRow
from gajim.gtk.status_selector import StatusSelectorPopover
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.workspace_listbox import WorkspaceListBox


@Gtk.Template(string=get_ui_string("app_side_bar.ui"))
class AppSideBar(Gtk.Box, EventHelper):
    __gtype_name__ = "AppSideBar"

    _top_listbox: SideBarListBox = Gtk.Template.Child()
    _activity_row: SideBarListBoxRow = Gtk.Template.Child()
    _workspace_listbox: WorkspaceListBox = Gtk.Template.Child()
    _bottom_listbox: SideBarListBox = Gtk.Template.Child()
    _toggle_row: SideBarListBoxRow = Gtk.Template.Child()
    _account_row: SideBarListBoxRow = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        EventHelper.__init__(self)

        self._account_popover = AccountPopover()
        self._account_popover.set_parent(self._account_row)
        self._account_popover.connect("clicked", self._on_account_clicked)

        self._status_popover = StatusSelectorPopover()
        self._status_popover.set_parent(self._account_row)
        self._status_popover.connect("clicked", self._on_status_clicked)

        accounts = app.settings.get_active_accounts()
        for account in reversed(accounts):
            client = app.get_client(account)
            contact = client.get_own_contact()

            client.connect_signal("state-changed", self._update_account_row)
            contact.connect("avatar-update", self._update_account_row)

        self._update_account_row()

        self.register_events(
            [
                ("account-enabled", ged.GUI1, self._on_account_enabled),
                ("account-disabled", ged.GUI1, self._on_account_disabled),
                ("our-show", ged.GUI1, self._update_account_row),
                ("register-actions", ged.GUI1, self._on_register_actions),
            ]
        )

    def _on_register_actions(self, _event: RegisterActions) -> None:
        action = app.window.lookup_action("chat-list-visible")
        assert action is not None
        action.bind_property(
            "state",
            self._toggle_row,
            "icon-name",
            GObject.BindingFlags.SYNC_CREATE,
            transform_to=self._transform_to_icon_name,
        )
        action.bind_property(
            "state",
            self._toggle_row,
            "tooltip-text",
            GObject.BindingFlags.SYNC_CREATE,
            transform_to=self._transform_to_tooltip_text,
        )

    def _on_account_enabled(self, event: AccountEnabled) -> None:
        client = app.get_client(event.account)
        contact = client.get_own_contact()

        client.connect_signal("state-changed", self._update_account_row)
        contact.connect("avatar-update", self._update_account_row)

        self._update_account_row()

    def _on_account_disabled(self, event: AccountDisabled) -> None:
        client = app.get_client(event.account)
        contact = client.get_own_contact()

        client.disconnect_all_from_obj(self)
        contact.disconnect_all_from_obj(self)

        self._update_account_row()

    def _update_account_row(self, *args: Any) -> None:
        accounts = app.settings.get_active_accounts()
        if len(accounts) == 1:
            account = accounts[0]
        else:
            account = None

        texture = app.app.avatar_storage.get_account_button_texture(
            account,
            AvatarSize.ACCOUNT_SIDE_BAR,
            self.get_scale_factor(),
            self._has_connectivity_issues(),
        )
        self._account_row.set_from_paintable(texture)

    @staticmethod
    def _has_connectivity_issues() -> bool:
        for account in app.settings.get_active_accounts():
            client = app.get_client(account)
            if client.state.is_disconnected or client.state.is_reconnect_scheduled:
                return True
        return False

    def _on_account_clicked(
        self,
        _popover: AccountPopover,
        account: str,
    ) -> None:
        if not account:
            app.app.activate_action("accounts", GLib.Variant("s", ""))
            return

        app.window.show_account_page(account)
        self._bottom_listbox.select_row(self._account_row)

    def _on_status_clicked(self, _button: Gtk.Button, status: str) -> None:
        accounts = app.get_connected_accounts()
        account = accounts[0] if len(accounts) == 1 else None
        app.app.change_status(status=status, account=account)

    @Gtk.Template.Callback()
    def _on_account_button_press(
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
            return Gdk.EVENT_PROPAGATE

        if current_button == Gdk.BUTTON_SECONDARY:
            # Right click
            self._status_popover.popup()
            self._account_popover.popdown()
            return Gdk.EVENT_PROPAGATE

        return Gdk.EVENT_PROPAGATE

    @Gtk.Template.Callback()
    def _on_row_activated(
        self, listbox: SideBarListBox, row: SideBarListBoxRow
    ) -> None:
        if row.item_id == "activity":
            app.window.show_activity_page()

    @staticmethod
    def _transform_to_icon_name(
        binding: GObject.Binding, is_visible: GLib.Variant
    ) -> str:
        direction = "left" if is_visible.unpack() else "right"
        return f"lucide-chevron-{direction}-symbolic"

    @staticmethod
    def _transform_to_tooltip_text(
        binding: GObject.Binding, is_visible: GLib.Variant
    ) -> str:
        if is_visible.unpack():
            return _("Hide Chat List")
        return _("Show Chat List")

    def set_chat_page(self, chat_page: ChatPage) -> None:
        self._activity_row.set_unread_notify(chat_page.get_activity_list())
        self._workspace_listbox.set_chat_page(chat_page)

    def select_chat(self) -> None:
        self._top_listbox.unselect_all()
        self._bottom_listbox.unselect_all()

    def show_account_page(self) -> None:
        self._top_listbox.unselect_all()
        self._workspace_listbox.unselect_all()

    def show_activity_page(self) -> None:
        self._bottom_listbox.unselect_all()
        self._workspace_listbox.unselect_all()

    def activate_workspace(self, workspace_id: str) -> None:
        self._top_listbox.unselect_all()
        self._bottom_listbox.unselect_all()
        self._workspace_listbox.activate_workspace(workspace_id)

    def get_active_workspace(self) -> str | None:
        return self._workspace_listbox.get_active_workspace()

    def highlight_dnd_targets(self, highlight: bool) -> None:
        if highlight:
            self._workspace_listbox.add_css_class("dnd-target")
        else:
            self._workspace_listbox.remove_css_class("dnd-target")

    def add_workspace(self, workspace_id: str) -> None:
        self._workspace_listbox.add_workspace(workspace_id)

    def remove_workspace(self, workspace_id: str) -> None:
        self._workspace_listbox.remove_workspace(workspace_id)

    def get_other_workspace(self, workspace_id: str) -> str | None:
        return self._workspace_listbox.get_other_workspace(workspace_id)

    def store_workspace_order(self) -> None:
        self._workspace_listbox.store_workspace_order()

    def update_workspace(self, workspace_id: str) -> None:
        self._workspace_listbox.update_avatar(workspace_id)

    def get_first_workspace(self) -> str:
        return self._workspace_listbox.get_first_workspace()

    def activate_workspace_number(self, number: int) -> None:
        self._workspace_listbox.activate_workspace_number(number)


@Gtk.Template(string=get_ui_string("account_popover.ui"))
class AccountPopover(Gtk.Popover):
    __gtype_name__ = "AccountPopover"

    __gsignals__ = {
        "clicked": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (str,),
        )
    }

    _listbox: Gtk.ListBox = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Popover.__init__(self)
        self._rows: list[AccountPopoverRow] = []

        self.connect("closed", self._on_closed)

    def popup(self) -> None:
        for account in app.settings.get_active_accounts():
            row = AccountPopoverRow(account=account)
            self._listbox.append(row)
            self._rows.append(row)

        Gtk.Popover.popup(self)

    def _on_closed(self, popover: Gtk.Popover) -> None:
        for row in self._rows:
            self._listbox.remove(row)
        self._rows.clear()

    @Gtk.Template.Callback()
    def _on_row_activated(
        self, _listbox: Gtk.ListBox, row: AccountPopoverRow | Gtk.ListBoxRow
    ) -> None:
        account = ""
        if isinstance(row, AccountPopoverRow):
            account = row.get_account()

        self.emit("clicked", account)
        self.popdown()


@Gtk.Template(string=get_ui_string("account_popover_row.ui"))
class AccountPopoverRow(Gtk.ListBoxRow):
    __gtype_name__ = "AccountPopoverRow"

    _color_bar: Gtk.Box = Gtk.Template.Child()
    _avatar: Gtk.Image = Gtk.Template.Child()
    _label: Gtk.Label = Gtk.Template.Child()

    def __init__(self, account: str = "") -> None:
        Gtk.ListBoxRow.__init__(self)

        self._account = account

        color_class = app.css_config.get_dynamic_class(account)
        self._color_bar.add_css_class(color_class)

        label = app.settings.get_account_setting(account, "account_label")
        self._label.set_text(label)

        client = app.get_client(account)
        connectivity_issues = bool(
            client.state.is_disconnected or client.state.is_reconnect_scheduled
        )
        texture = app.app.avatar_storage.get_account_button_texture(
            account,
            AvatarSize.ACCOUNT_SIDE_BAR,
            self.get_scale_factor(),
            connectivity_issues,
        )
        self._avatar.set_from_paintable(texture)
        if connectivity_issues:
            self._avatar.set_tooltip_text(_("There are connectivity issues"))
        else:
            self._avatar.set_tooltip_text("")

    def do_unroot(self) -> None:
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)

    def get_account(self) -> str:
        return self._account
