# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import locale
import logging
from collections import defaultdict

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango
from nbxmpp.stringprep import saslprep

from gajim.common import app
from gajim.common import passwords
from gajim.common import types
from gajim.common.const import ClientState
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.setting_values import AllSettingsT

from gajim.gtk.alert import AlertDialog
from gajim.gtk.alert import CancelDialogResponse
from gajim.gtk.alert import DialogResponse
from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.filechoosers import Filter
from gajim.gtk.omemo_trust_manager import OMEMOTrustManager
from gajim.gtk.settings import DropDownSetting
from gajim.gtk.settings import SettingsBox
from gajim.gtk.settings import SettingsDialog
from gajim.gtk.structs import ExportHistoryParam
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import iterate_listbox_children
from gajim.gtk.util.window import get_app_window
from gajim.gtk.util.window import open_window
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.accounts")


class AccountsWindow(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="AccountsWindow",
            title=_("Accounts"),
            default_width=700,
            default_height=550,
            add_window_padding=False,
        )

        self._need_relogin: dict[str, list[AllSettingsT]] = {}
        self._accounts: dict[str, Account] = {}

        self._menu = AccountMenu()
        self._settings = Settings()

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        box.append(self._menu)
        box.append(self._settings)
        self.set_child(box)

        for account in app.get_accounts_sorted():
            self.add_account(account, initial=True)

        self._connect(self._menu, "menu-activated", self._on_menu_activated)
        self._connect(self.window, "close-request", self._on_close_request)

    def _cleanup(self) -> None:
        pass

    def _on_menu_activated(
        self, _listbox: Gtk.ListBox, account: str, name: str
    ) -> None:
        if name == "back":
            self._settings.set_page("add-account")
        elif name == "remove":
            self.on_remove_account(account)
        else:
            self._settings.set_page(name)

    def update_account_label(self, account: str) -> None:
        self._accounts[account].update_account_label()

    def update_proxy_list(self) -> None:
        for account in self._accounts:
            self._settings.update_proxy_list(account)

    def _check_relogin(self) -> bool:
        for account, r_settings in self._need_relogin.items():
            settings = self._get_relogin_settings(account)
            active = app.settings.get_account_setting(account, "active")
            if settings != r_settings:
                self._need_relogin[account] = settings
                if active:
                    self._relog(account)
                    return True
                break

        return False

    def _relog(self, account: str) -> None:

        def _on_response(response_id: str) -> None:
            if response_id == "accept":
                client = app.get_client(account)
                client.disconnect(gracefully=True, reconnect=True, destroy_client=True)

            self.close()

        AlertDialog(
            _("Re-Login Now?"),
            _("To apply all changes instantly, you have to re-login."),
            responses=[
                DialogResponse("cancel", _("_Later")),
                DialogResponse(
                    "accept", _("_Re-Login"), is_default=True, appearance="suggested"
                ),
            ],
            callback=_on_response,
        )

    @staticmethod
    def _get_relogin_settings(account: str) -> list[AllSettingsT]:
        values: list[AllSettingsT] = []
        values.append(app.settings.get_account_setting(account, "client_cert"))
        values.append(app.settings.get_account_setting(account, "proxy"))
        values.append(app.settings.get_account_setting(account, "resource"))
        values.append(app.settings.get_account_setting(account, "use_custom_host"))
        values.append(app.settings.get_account_setting(account, "custom_host"))
        values.append(app.settings.get_account_setting(account, "custom_port"))
        return values

    @staticmethod
    def on_remove_account(account: str) -> None:
        open_window("RemoveAccount", account=account)

    def remove_account(self, account: str) -> None:
        del self._need_relogin[account]
        self._accounts[account].remove()

    def add_account(self, account: str, initial: bool = False) -> None:
        self._need_relogin[account] = self._get_relogin_settings(account)
        self._accounts[account] = Account(account, self._menu, self._settings)
        if not initial:
            self._accounts[account].show()

    def select_account(self, account: str, page: str | None = None) -> None:
        try:
            self._accounts[account].select(page)
        except KeyError:
            log.warning("select_account() failed, account %s not found", account)

    def enable_account(self, account: str, state: bool) -> None:
        self._accounts[account].enable_account(state)

    def _on_close_request(self, _widget: Gtk.ApplicationWindow) -> bool:
        if self._check_relogin():
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE


class Settings(Gtk.ScrolledWindow):
    def __init__(self):
        Gtk.ScrolledWindow.__init__(self)
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self._stack = Gtk.Stack(vhomogeneous=False)
        self._stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self._stack.add_css_class("settings-stack")
        self._stack.add_named(AddNewAccountPage(), "add-account")

        self.set_child(self._stack)
        self._page_signal_ids: dict[GenericSettingPage, int] = {}
        self._pages: dict[str, list[GenericSettingPage]] = defaultdict(list)

    def add_page(self, page: GenericSettingPage) -> None:
        self._pages[page.account].append(page)
        self._stack.add_named(page, f"{page.account}-{page.name}")
        self._page_signal_ids[page] = page.connect_signal(self._stack)

    def set_page(self, name: str) -> None:
        self._stack.set_visible_child_name(name)

    def remove_account(self, account: str) -> None:
        for page in self._pages[account]:
            signal_id = self._page_signal_ids[page]
            del self._page_signal_ids[page]
            self._stack.disconnect(signal_id)
            self._stack.remove(page)
        del self._pages[account]

    def update_proxy_list(self, account: str) -> None:
        for page in self._pages[account]:
            if page.name != "connection":
                continue
            assert isinstance(page, ConnectionPage)
            page.update_proxy_entries()


class AccountMenu(Gtk.Box, SignalManager):

    __gsignals__ = {
        "menu-activated": (GObject.SignalFlags.RUN_FIRST, None, (str, str)),
    }

    def __init__(self) -> None:
        Gtk.Box.__init__(self, hexpand=False, width_request=160)
        SignalManager.__init__(self)

        self.add_css_class("accounts-menu")

        self._stack = Gtk.Stack()
        self._stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT)

        self._accounts_listbox = Gtk.ListBox()
        self._accounts_listbox.set_sort_func(self._sort_func)
        self._accounts_listbox.add_css_class("accounts-menu-listbox")
        self._connect(
            self._accounts_listbox, "row-activated", self._on_account_row_activated
        )

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self._accounts_listbox)
        self._stack.add_named(scrolled, "accounts")
        self.append(self._stack)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    @staticmethod
    def _sort_func(row1: AccountRow, row2: AccountRow) -> int:
        return locale.strcoll(row1.label.lower(), row2.label.lower())

    def add_account(self, row: AccountRow) -> None:
        self._accounts_listbox.append(row)
        sub_menu = AccountSubMenu(row.account)
        self._stack.add_named(sub_menu, f"{row.account}-menu")

        self._connect(sub_menu, "row-activated", self._on_sub_menu_row_activated)

    def remove_account(self, row: AccountRow) -> None:
        if self._stack.get_visible_child_name() != "accounts":
            # activate 'back' button
            listbox = cast(Gtk.ListBox, self._stack.get_visible_child())
            back_row = cast(Gtk.ListBoxRow, listbox.get_row_at_index(1))
            back_row.emit("activate")
        self._accounts_listbox.remove(row)
        sub_menu = self._stack.get_child_by_name(f"{row.account}-menu")
        assert sub_menu is not None
        self._stack.remove(sub_menu)

    def _on_account_row_activated(self, _listbox: Gtk.ListBox, row: AccountRow) -> None:
        self._stack.set_visible_child_name(f"{row.account}-menu")
        listbox = cast(Gtk.ListBox, self._stack.get_visible_child())
        listbox_row = cast(Gtk.ListBoxRow, listbox.get_row_at_index(2))
        listbox_row.emit("activate")

    def _on_sub_menu_row_activated(
        self, listbox: AccountSubMenu, row: MenuItem
    ) -> None:
        if row.name == "back":
            self._stack.set_visible_child_full(
                "accounts", Gtk.StackTransitionType.OVER_RIGHT
            )

        if row.name in ("back", "remove"):
            self.emit("menu-activated", listbox.account, row.name)

        else:
            self.emit(
                "menu-activated", listbox.account, f"{listbox.account}-{row.name}"
            )

    def set_page(self, account: str, page_name: str) -> None:
        sub_menu = cast(
            AccountSubMenu, self._stack.get_child_by_name(f"{account}-menu")
        )
        sub_menu.select_row_by_name(page_name)
        self.emit("menu-activated", account, f"{account}-{page_name}")

    def update_account_label(self, account: str) -> None:
        self._accounts_listbox.invalidate_sort()
        sub_menu = cast(
            AccountSubMenu, self._stack.get_child_by_name(f"{account}-menu")
        )
        sub_menu.update()


class AccountSubMenu(Gtk.ListBox):

    __gsignals__ = {"update": (GObject.SignalFlags.RUN_FIRST, None, (str,))}

    def __init__(self, account: str) -> None:
        Gtk.ListBox.__init__(self)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.add_css_class("accounts-menu-listbox")

        self._account = account

        self.append(AccountLabelMenuItem(self, self._account))
        self.append(BackMenuItem())
        self.append(PageMenuItem("general", _("General")))
        self.append(PageMenuItem("privacy", _("Privacy")))
        self.append(PageMenuItem("encryption-omemo", _("Encryption (OMEMO)")))
        self.append(PageMenuItem("connection", _("Connection")))
        self.append(PageMenuItem("advanced", _("Advanced")))
        self.append(RemoveMenuItem())

    @property
    def account(self) -> str:
        return self._account

    def select_row_by_name(self, row_name: str) -> None:
        for row in iterate_listbox_children(self):
            if not isinstance(row, PageMenuItem):
                continue
            if row.name == row_name:
                self.select_row(row)
                return

    def update(self) -> None:
        self.emit("update", self._account)


class MenuItem(Gtk.ListBoxRow, SignalManager):
    def __init__(self, name: str) -> None:
        Gtk.ListBoxRow.__init__(self)
        SignalManager.__init__(self)
        self._name = name
        self._box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        self._label = Gtk.Label()

        self.set_child(self._box)

    @property
    def name(self) -> str:
        return self._name

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)


class RemoveMenuItem(MenuItem):
    def __init__(self) -> None:
        super().__init__("remove")
        self._label.set_text(_("Remove"))
        image = Gtk.Image.new_from_icon_name("user-trash-symbolic")

        self.set_selectable(False)
        image.add_css_class("error")

        self._box.append(image)
        self._box.append(self._label)


class AccountLabelMenuItem(MenuItem):
    def __init__(self, parent: AccountSubMenu, account: str) -> None:
        super().__init__("account-label")
        self._update_account_label(parent, account)

        self.set_selectable(False)
        self.set_sensitive(False)
        self.set_activatable(False)

        image = Gtk.Image.new_from_icon_name("avatar-default-symbolic")

        self._label.add_css_class("accounts-label-row")
        self._label.set_ellipsize(Pango.EllipsizeMode.END)
        self._label.set_xalign(0)

        self._box.append(image)
        self._box.append(self._label)

        self._connect(parent, "update", self._update_account_label)

    def _update_account_label(self, _listbox: Gtk.ListBox, account: str) -> None:
        account_label = app.get_account_label(account)
        self._label.set_text(account_label)


class BackMenuItem(MenuItem):
    def __init__(self) -> None:
        super().__init__("back")
        self.set_selectable(False)

        self._label.set_text(_("Back"))

        image = Gtk.Image.new_from_icon_name("lucide-chevron-left-symbolic")

        self._box.append(image)
        self._box.append(self._label)


class PageMenuItem(MenuItem):
    def __init__(self, name: str, label: str) -> None:
        super().__init__(name)

        if name == "general":
            icon = "avatar-default-symbolic"
        elif name == "privacy":
            icon = "feather-eye-symbolic"
        elif name == "encryption-omemo":
            icon = "channel-secure-symbolic"
        elif name == "connection":
            icon = "feather-globe-symbolic"
        elif name == "advanced":
            icon = "lucide-settings-symbolic"
        else:
            icon = "dialog-error-symbolic"

        image = Gtk.Image.new_from_icon_name(icon)
        self._label.set_text(label)

        self._box.append(image)
        self._box.append(self._label)


class Account:
    def __init__(self, account: str, menu: AccountMenu, settings: Settings) -> None:
        self._account = account
        self._menu = menu
        self._settings = settings

        self._settings.add_page(GeneralPage(account))
        self._settings.add_page(PrivacyPage(account))
        self._settings.add_page(EncryptionOMEMOPage(account))
        self._settings.add_page(ConnectionPage(account))
        self._settings.add_page(AdvancedPage(account))

        self._account_row = AccountRow(account)
        self._menu.add_account(self._account_row)

    def select(self, page_name: str | None = None) -> None:
        self._account_row.emit("activate")
        if page_name is not None:
            self._menu.set_page(self._account, page_name)

    def show(self) -> None:
        self.select()

    def remove(self) -> None:
        self._menu.remove_account(self._account_row)
        self._settings.remove_account(self._account)

    def update_account_label(self) -> None:
        self._account_row.update_account_label()
        self._menu.update_account_label(self._account)

    def enable_account(self, state: bool) -> None:
        self._account_row.enable_account(state)

    @property
    def menu(self) -> AccountMenu:
        return self._menu

    @property
    def account(self) -> str:
        return self._account

    @property
    def settings(self) -> str:
        return self._account


class AccountRow(Gtk.ListBoxRow, SignalManager):
    def __init__(self, account: str) -> None:
        Gtk.ListBoxRow.__init__(self, selectable=False)
        SignalManager.__init__(self)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

        self._account = account

        self._label = Gtk.Label(label=app.get_account_label(account))
        self._label.set_halign(Gtk.Align.START)
        self._label.set_hexpand(True)
        self._label.set_ellipsize(Pango.EllipsizeMode.END)
        self._label.set_xalign(0)
        self._label.set_width_chars(18)

        next_icon = Gtk.Image.new_from_icon_name("lucide-chevron-right-symbolic")

        account_enabled = app.settings.get_account_setting(self._account, "active")
        self._switch = Gtk.Switch()
        self._switch.set_active(account_enabled)
        self._switch.set_vexpand(False)

        self._switch_state_label = Gtk.Label()
        self._switch_state_label.set_xalign(0)
        self._switch_state_label.set_valign(Gtk.Align.CENTER)
        label_width = max(len(p_("Switch", "On")), len(p_("Switch", "Off")))
        self._switch_state_label.set_width_chars(label_width)
        self._set_label(account_enabled)

        self._connect(self._switch, "state-set", self._on_enable_switch, self._account)

        box.append(self._switch)
        box.append(self._switch_state_label)
        box.append(Gtk.Separator())
        box.append(self._label)
        box.append(next_icon)
        self.set_child(box)

    @property
    def account(self) -> str:
        return self._account

    @property
    def label(self) -> str:
        return self._label.get_text()

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)

    def update_account_label(self) -> None:
        self._label.set_text(app.get_account_label(self._account))

    def enable_account(self, state: bool) -> None:
        self._switch.set_state(state)
        self._set_label(state)

    def _set_label(self, active: bool) -> None:
        text = p_("Switch", "On") if active else p_("Switch", "Off")
        self._switch_state_label.set_text(text)

    def _on_enable_switch(self, switch: Gtk.Switch, state: bool, account: str) -> int:

        def _on_response(response_id: str) -> None:
            if response_id == "disable":
                client = app.get_client(account)
                client.connect_signal("state-changed", self._on_state_changed)
                client.change_status("offline", "offline")
                switch.set_state(state)
                self._set_label(state)
            else:
                switch.set_active(True)

        account_is_active = app.settings.get_account_setting(account, "active")
        if account_is_active == state:
            return Gdk.EVENT_PROPAGATE

        if account_is_active and not app.get_client(account).state.is_disconnected:
            # Connecting or connected
            window = get_app_window("AccountsWindow")
            assert window is not None

            account_label = app.get_account_label(account)
            AlertDialog(
                _("Disable Account?"),
                _(
                    "Account %(name)s is still connected\n"
                    "All chat and group chat windows will be closed."
                )
                % {"name": account_label},
                responses=[
                    CancelDialogResponse(),
                    DialogResponse(
                        "disable", _("_Disable Account"), appearance="destructive"
                    ),
                ],
                callback=_on_response,
                parent=window.window,
            )
            return Gdk.EVENT_STOP

        if state:
            app.app.enable_account(account)
        else:
            app.app.disable_account(account)

        return Gdk.EVENT_PROPAGATE

    def _on_state_changed(
        self, client: types.Client, _signal_name: str, client_state: ClientState
    ) -> None:

        if client_state.is_disconnected:
            app.app.disable_account(client.account)


class AddNewAccountPage(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=18)
        self.set_vexpand(True)
        self.set_hexpand(True)
        self.set_margin_top(24)
        image = Gtk.Image.new_from_icon_name("gajim-symbolic")
        image.set_pixel_size(100)
        image.set_opacity(0.2)
        self.append(image)

        button = Gtk.Button(label=_("Add Account"))
        button.add_css_class("suggested-action")
        button.set_action_name("app.add-account")
        button.set_halign(Gtk.Align.CENTER)
        self.append(button)


class GenericSettingPage(Gtk.Box):

    name = ""

    def __init__(self, account: str, settings: list[Setting]) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        self.set_valign(Gtk.Align.START)
        self.set_vexpand(True)
        self.account = account

        self.listbox = SettingsBox(account)
        self.listbox.add_css_class("mt-18")
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.listbox.set_vexpand(False)
        self.listbox.set_valign(Gtk.Align.END)

        for setting in settings:
            self.listbox.add_setting(setting)
        self.listbox.update_states()

        clamp = Adw.Clamp(child=self.listbox)
        self.append(clamp)

    def connect_signal(self, stack: Gtk.Stack) -> int:
        return stack.connect("notify::visible-child", self._on_visible_child_changed)

    def _on_visible_child_changed(self, stack: Gtk.Stack, _param: Any) -> None:
        if self == stack.get_visible_child():
            self.listbox.update_states()


class GeneralPage(GenericSettingPage):

    name = "general"

    def __init__(self, account: str) -> None:

        workspaces = self._get_workspaces()

        settings = [
            Setting(
                SettingKind.ENTRY,
                _("Label"),
                SettingType.ACCOUNT_CONFIG,
                "account_label",
                callback=self._on_account_name_change,
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Default Workspace"),
                SettingType.ACCOUNT_CONFIG,
                "default_workspace",
                props={"data": workspaces},
                desc=_("Chats from this account will use this workspace by default"),
            ),
            Setting(
                SettingKind.COLOR,
                _("Color"),
                SettingType.ACCOUNT_CONFIG,
                "account_color",
                desc=_("Recognize your account by color"),
            ),
            Setting(
                SettingKind.LOGIN,
                _("Login"),
                SettingType.DIALOG,
                desc=_("Change your account’s password, etc."),
                bind="account::anonymous_auth",
                inverted=True,
                props={"dialog": LoginDialog},
            ),
            # Currently not supported by nbxmpp
            #
            # Setting(SettingKind.DIALOG,
            #         _('Client Certificate'),
            #         SettingType.DIALOG,
            #         props={'dialog': CertificateDialog}),
            Setting(
                SettingKind.SWITCH,
                _("Connect on startup"),
                SettingType.ACCOUNT_CONFIG,
                "autoconnect",
            ),
            Setting(
                SettingKind.SWITCH,
                _("Global Status"),
                SettingType.ACCOUNT_CONFIG,
                "sync_with_global_status",
                desc=_("Synchronize the status of all accounts"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Remember Last Status"),
                SettingType.ACCOUNT_CONFIG,
                "restore_last_status",
                desc=_("Restore status and status message of your last session"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Use file transfer proxies"),
                SettingType.ACCOUNT_CONFIG,
                "use_ft_proxies",
            ),
        ]
        GenericSettingPage.__init__(self, account, settings)

    @staticmethod
    def _get_workspaces() -> dict[str, str]:
        workspaces: dict[str, str] = {"": _("Disabled")}
        for workspace_id in app.settings.get_workspaces():
            name = app.settings.get_workspace_setting(workspace_id, "name")
            workspaces[workspace_id] = name
        return workspaces

    def _on_account_name_change(self, *args: Any) -> None:
        window = get_app_window("AccountsWindow")
        assert window is not None
        window.update_account_label(self.account)


class PrivacyPage(GenericSettingPage):

    name = "privacy"

    def __init__(self, account: str) -> None:
        self._account = account
        self._client: types.Client | None = None
        if app.account_is_connected(account):
            self._client = app.get_client(account)

        history_max_age = {
            -1: _("Forever"),
            0: _("Until Gajim is Closed"),
            86400: _("1 Day"),
            604800: _("1 Week"),
            2629743: _("1 Month"),
            7889229: _("3 Months"),
            15778458: _("6 Months"),
            31556926: _("1 Year"),
        }

        chatstate_entries = {
            "disabled": _("Disabled"),
            "composing_only": _("Composing Only"),
            "all": _("All Chat States"),
        }

        encryption_entries = {
            "": _("Unencrypted"),
            "OMEMO": "OMEMO",
            "OpenPGP": "OpenPGP",
            "PGP": "PGP",
        }

        param = ExportHistoryParam(account=account, jid=None)

        settings = [
            Setting(
                SettingKind.DROPDOWN,
                _("Default Encryption"),
                SettingType.ACCOUNT_CONFIG,
                "encryption_default",
                desc=_(
                    "Encryption method to use "
                    "unless overridden on a per-contact basis"
                ),
                props={"data": encryption_entries},
            ),
            Setting(
                SettingKind.SWITCH,
                _("Idle Time"),
                SettingType.ACCOUNT_CONFIG,
                "send_idle_time",
                callback=self._send_idle_time,
                desc=_("Disclose the time of your last activity"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Local System Time"),
                SettingType.ACCOUNT_CONFIG,
                "send_time_info",
                callback=self._send_time_info,
                desc=_("Disclose the local system time of the device Gajim runs on"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Operating System"),
                SettingType.ACCOUNT_CONFIG,
                "send_os_info",
                callback=self._send_os_info,
                desc=_(
                    "Disclose information about the "
                    "operating system you currently use"
                ),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Media Playback"),
                SettingType.ACCOUNT_CONFIG,
                "publish_tune",
                callback=self._publish_tune,
                desc=_(
                    "Disclose information about media that is "
                    "currently being played on your system."
                ),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Ignore Unknown Contacts"),
                SettingType.ACCOUNT_CONFIG,
                "ignore_unknown_contacts",
                desc=_("Ignore everything from contacts not in your contact list"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Send Message Receipts"),
                SettingType.ACCOUNT_CONFIG,
                "answer_receipts",
                desc=_("Tell your contacts if you received a message"),
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Send Chatstate"),
                SettingType.ACCOUNT_CONFIG,
                "send_chatstate_default",
                desc=_("Default for chats"),
                props={
                    "data": chatstate_entries,
                    "button-text": _("Reset"),
                    "button-tooltip": _("Reset all chats to the current default value"),
                    "button-style": "destructive-action",
                    "button-callback": self._reset_send_chatstate,
                },
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Send Chatstate in Group Chats"),
                SettingType.ACCOUNT_CONFIG,
                "gc_send_chatstate_default",
                desc=_("Default for group chats"),
                props={
                    "data": chatstate_entries,
                    "button-text": _("Reset"),
                    "button-tooltip": _(
                        "Reset all group chats to the current default value"
                    ),
                    "button-style": "destructive-action",
                    "button-callback": self._reset_gc_send_chatstate,
                },
            ),
            Setting(
                SettingKind.SWITCH,
                _("Send Read Markers"),
                SettingType.VALUE,
                app.settings.get_account_setting(account, "send_marker_default"),
                callback=self._send_read_marker,
                desc=_("Default for chats and private group chats"),
                props={
                    "button-text": _("Reset"),
                    "button-tooltip": _("Reset all chats to the current default value"),
                    "button-style": "destructive-action",
                    "button-callback": self._reset_send_read_marker,
                },
            ),
            Setting(
                SettingKind.SWITCH,
                _("Sync Group Chat Blocklist"),
                SettingType.ACCOUNT_CONFIG,
                "sync_muc_blocks",
                callback=self._sync_blocks,
                enabled_func=self._get_sync_blocks_enabled,
                desc=_("Sync group chat blocklist with other devices"),
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Keep Chat History"),
                SettingType.ACCOUNT_CONFIG,
                "chat_history_max_age",
                props={"data": history_max_age},
                desc=_("How long Gajim should keep your chat history"),
            ),
            Setting(
                SettingKind.ACTION,
                _("Export Chat History"),
                SettingType.ACTION,
                "app.export-history",
                props={"variant": param.to_variant()},
                desc=_("Export your chat history from Gajim"),
            ),
        ]
        GenericSettingPage.__init__(self, account, settings)

    @staticmethod
    def _reset_send_chatstate(button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_contact_settings("send_chatstate", None)

    @staticmethod
    def _reset_gc_send_chatstate(button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_group_chat_settings("send_chatstate", None)

    def _send_idle_time(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module("LastActivity").set_enabled(state)

    def _send_time_info(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module("EntityTime").set_enabled(state)

    def _send_os_info(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module("SoftwareVersion").set_enabled(state)

    def _publish_tune(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module("UserTune").set_enabled(state)

    def _send_read_marker(self, state: bool, _data: Any) -> None:
        app.settings.set_account_setting(self._account, "send_marker_default", state)
        app.settings.set_account_setting(
            self._account, "gc_send_marker_private_default", state
        )

    def _reset_send_read_marker(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_contact_settings("send_marker", None)
        app.settings.set_group_chat_settings("send_marker", None, context="private")

    def _get_sync_blocks_enabled(self) -> bool:
        if self._client is None:
            return False

        if not self._client.state.is_available:
            return False

        return self._client.get_module("Bookmarks").nativ_bookmarks_used

    def _sync_blocks(self, state: bool, _data: Any) -> None:
        if self._client is not None and state:
            self._client.get_module("MucBlocking").merge_blocks()


class EncryptionOMEMOPage(GenericSettingPage):

    name = "encryption-omemo"

    def __init__(self, account: str) -> None:
        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Blind Trust"),
                SettingType.ACCOUNT_CONFIG,
                "omemo_blind_trust",
                desc=_("Blindly trust new devices until you verify them"),
            )
        ]
        GenericSettingPage.__init__(self, account, settings)

        title_heading = _("Trust Management")
        wiki_url = "https://dev.gajim.org/gajim/gajim/-/wikis/help/OMEMO"
        link_text = _("Read more about blind trust")
        link_markup = f'<a href="{wiki_url}">{link_text}</a>'

        preferences_group = Adw.PreferencesGroup(
            title=f"{title_heading}\n{link_markup}"
        )
        preferences_group.add_css_class("mt-18")
        clamp = Adw.Clamp(child=preferences_group)
        self.prepend(clamp)

        omemo_trust_manager = OMEMOTrustManager(account)
        omemo_trust_manager.add_css_class("mt-18")
        self.append(omemo_trust_manager)


class ConnectionPage(GenericSettingPage):

    name = "connection"

    def __init__(self, account: str) -> None:

        settings = [
            Setting(
                SettingKind.DROPDOWN,
                _("Proxy"),
                SettingType.ACCOUNT_CONFIG,
                "proxy",
                name="proxy",
                props={
                    "data": self._get_proxies(),
                    "button-icon-name": "lucide-settings-symbolic",
                    "button-callback": self._on_proxy_edit,
                },
            ),
            Setting(
                SettingKind.HOSTNAME,
                _("Hostname"),
                SettingType.DIALOG,
                desc=_("Manually set the hostname for the server"),
                props={"dialog": CutstomHostnameDialog},
            ),
            Setting(
                SettingKind.ENTRY, _("Resource"), SettingType.ACCOUNT_CONFIG, "resource"
            ),
            Setting(
                SettingKind.PRIORITY,
                _("Priority"),
                SettingType.DIALOG,
                props={"dialog": PriorityDialog},
            ),
            Setting(
                SettingKind.SWITCH,
                _("Use Unencrypted Connection"),
                SettingType.ACCOUNT_CONFIG,
                "use_plain_connection",
                desc=_("Use an unencrypted connection to the server"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Confirm Unencrypted Connection"),
                SettingType.ACCOUNT_CONFIG,
                "confirm_unencrypted_connection",
                desc=_("Show a confirmation dialog before connecting unencrypted"),
            ),
        ]
        GenericSettingPage.__init__(self, account, settings)

    @staticmethod
    def _get_proxies() -> dict[str, str]:
        proxies = {"": _("System")}
        proxies.update({proxy: proxy for proxy in app.settings.get_proxies()})
        proxies["no-proxy"] = _("No Proxy")
        return proxies

    @staticmethod
    def _on_proxy_edit(*args: Any) -> None:
        open_window("ManageProxies")

    def update_proxy_entries(self) -> None:
        dropdown_row = cast(DropDownSetting, self.listbox.get_setting("proxy"))
        dropdown_row.update_entries(self._get_proxies())


class AdvancedPage(GenericSettingPage):

    name = "advanced"

    def __init__(self, account: str) -> None:

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Contact Information"),
                SettingType.ACCOUNT_CONFIG,
                "request_user_data",
                desc=_("Request contact information (Tune, Location)"),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Accept all Contact Requests"),
                SettingType.ACCOUNT_CONFIG,
                "autoauth",
                desc=_("Automatically accept all contact requests"),
            ),
            # TODO Jingle FT
            # Setting(SettingKind.DROPDOWN,
            #         _('Filetransfer Preference'),
            #         SettingType.ACCOUNT_CONFIG,
            #         'filetransfer_preference',
            #         props={'data': {'httpupload': _('Upload Files'),
            #                         'jingle': _('Send Files Directly')}},
            #         desc=_('Preferred file transfer mechanism for '
            #                'file drag&drop on a chat window')),
            Setting(
                SettingKind.SWITCH,
                _("Security Labels"),
                SettingType.ACCOUNT_CONFIG,
                "enable_security_labels",
                desc=_(
                    "Show labels describing confidentiality of "
                    "messages, if the server supports XEP-0258"
                ),
            ),
            Setting(
                SettingKind.SWITCH,
                _("Synchronize joined group chats"),
                SettingType.ACCOUNT_CONFIG,
                "autojoin_sync",
                desc=_("Synchronize joined group chats with other devices."),
            ),
        ]
        GenericSettingPage.__init__(self, account, settings)


class PriorityDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        neg_priority = app.settings.get("enable_negative_priority")
        if neg_priority:
            range_ = (-128, 127, 1)
        else:
            range_ = (0, 127, 1)

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Adjust to status"),
                SettingType.ACCOUNT_CONFIG,
                "adjust_priority_with_status",
            ),
            Setting(
                SettingKind.SPIN,
                _("Priority"),
                SettingType.ACCOUNT_CONFIG,
                "priority",
                bind="account::adjust_priority_with_status",
                inverted=True,
                props={"range_": range_},
            ),
        ]

        SettingsDialog.__init__(
            self, parent, _("Priority"), Gtk.DialogFlags.MODAL, settings, account
        )

    def _cleanup(self) -> None:
        # Update priority
        if self.account not in app.settings.get_active_accounts():
            return
        client = app.get_client(self.account)
        show = client.status
        status = client.status_message
        client.change_status(show, status)


class CutstomHostnameDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        type_values = ["START TLS", "DIRECT TLS", "PLAIN"]

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Enable"),
                SettingType.ACCOUNT_CONFIG,
                "use_custom_host",
            ),
            Setting(
                SettingKind.ENTRY,
                _("Hostname"),
                SettingType.ACCOUNT_CONFIG,
                "custom_host",
                bind="account::use_custom_host",
            ),
            Setting(
                SettingKind.SPIN,
                _("Port"),
                SettingType.ACCOUNT_CONFIG,
                "custom_port",
                bind="account::use_custom_host",
                props={"range_": (0, 65535, 1)},
            ),
            Setting(
                SettingKind.DROPDOWN,
                _("Type"),
                SettingType.ACCOUNT_CONFIG,
                "custom_type",
                bind="account::use_custom_host",
                props={"data": type_values},
            ),
        ]

        SettingsDialog.__init__(
            self,
            parent,
            _("Connection Settings"),
            Gtk.DialogFlags.MODAL,
            settings,
            account,
        )


class CertificateDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        settings = [
            Setting(
                SettingKind.FILECHOOSER,
                _("Client Certificate"),
                SettingType.ACCOUNT_CONFIG,
                "client_cert",
                props={
                    "filefilter": [
                        Filter(name=_("All files"), patterns=["*"]),
                        Filter(name=_("PKCS12 Files"), patterns=["*.p12"]),
                    ]
                },
            ),
            Setting(
                SettingKind.SWITCH,
                _("Encrypted Certificate"),
                SettingType.ACCOUNT_CONFIG,
                "client_cert_encrypted",
            ),
        ]

        SettingsDialog.__init__(
            self,
            parent,
            _("Certificate Settings"),
            Gtk.DialogFlags.MODAL,
            settings,
            account,
        )


class LoginDialog(SettingsDialog):
    def __init__(self, account: str, parent: Gtk.Window) -> None:

        settings = [
            Setting(
                SettingKind.ENTRY,
                _("Password"),
                SettingType.ACCOUNT_CONFIG,
                "password",
                bind="account::savepass",
            ),
            Setting(
                SettingKind.SWITCH,
                _("Save Password"),
                SettingType.ACCOUNT_CONFIG,
                "savepass",
                enabled_func=(
                    lambda: not app.settings.get("use_keyring")
                    or passwords.is_keyring_available()
                ),
            ),
            Setting(
                SettingKind.CHANGEPASSWORD,
                _("Change Password"),
                SettingType.DIALOG,
                callback=self.on_password_change,
                props={"dialog": None},
            ),
            Setting(
                SettingKind.SWITCH,
                _("Use GSSAPI"),
                SettingType.ACCOUNT_CONFIG,
                "enable_gssapi",
            ),
        ]

        SettingsDialog.__init__(
            self, parent, _("Login Settings"), Gtk.DialogFlags.MODAL, settings, account
        )

    def on_password_change(self, new_password: str, _data: Any) -> None:
        try:
            new_password = saslprep(new_password)
        except Exception:
            # TODO: Show warning for invalid passwords
            return

        passwords.save_password(self.account, new_password)

    def _cleanup(self) -> None:
        savepass = app.settings.get_account_setting(self.account, "savepass")
        if not savepass:
            passwords.delete_password(self.account)
