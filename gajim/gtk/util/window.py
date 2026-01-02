# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import overload
from typing import TYPE_CHECKING

import logging
from importlib import import_module

from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app

from gajim.gtk.const import WINDOW_MODULES

if TYPE_CHECKING:
    from gajim.gtk.account_wizard import AccountWizard
    from gajim.gtk.add_contact import AddContact
    from gajim.gtk.adhoc import AdHocCommands
    from gajim.gtk.advanced_config import AdvancedConfig
    from gajim.gtk.call_window import CallWindow
    from gajim.gtk.certificate_dialog import CertificateDialog
    from gajim.gtk.change_password import ChangePassword
    from gajim.gtk.contact_info import ContactInfo
    from gajim.gtk.db_migration import DBMigration
    from gajim.gtk.debug_console import DebugConsoleWindow
    from gajim.gtk.discovery import ServiceDiscoveryWindow
    from gajim.gtk.features import Features
    from gajim.gtk.groupchat_creation import CreateGroupchatWindow
    from gajim.gtk.groupchat_details import GroupchatDetails
    from gajim.gtk.groupchat_join import GroupchatJoin
    from gajim.gtk.history_export import HistoryExport
    from gajim.gtk.history_sync import HistorySyncAssistant
    from gajim.gtk.manage_proxies import ManageProxies
    from gajim.gtk.manage_sounds import ManageSounds
    from gajim.gtk.password_dialog import PasswordDialog
    from gajim.gtk.pep_config import PEPConfig
    from gajim.gtk.preference.dialog import Preferences
    from gajim.gtk.profile import ProfileWindow
    from gajim.gtk.quit import QuitDialog
    from gajim.gtk.remove_account import RemoveAccount
    from gajim.gtk.roster_item_exchange import RosterItemExchange
    from gajim.gtk.service_registration import ServiceRegistration
    from gajim.gtk.ssl_error_dialog import SSLErrorDialog
    from gajim.gtk.start_chat import StartChatDialog
    from gajim.gtk.themes import Themes
    from gajim.gtk.workspace_dialog import WorkspaceDialog

    GajimWindowT = (
        AccountWizard
        | AddContact
        | AdHocCommands
        | AdvancedConfig
        | DBMigration
        | DebugConsoleWindow
        | CallWindow
        | CertificateDialog
        | ChangePassword
        | ContactInfo
        | CreateGroupchatWindow
        | Features
        | GroupchatDetails
        | GroupchatJoin
        | HistoryExport
        | HistorySyncAssistant
        | ManageProxies
        | ManageSounds
        | PasswordDialog
        | PEPConfig
        | Preferences
        | ProfileWindow
        | QuitDialog
        | RemoveAccount
        | RosterItemExchange
        | ServiceDiscoveryWindow
        | ServiceRegistration
        | SSLErrorDialog
        | StartChatDialog
        | Themes
        | WorkspaceDialog
    )
    GajimWindowNameT = (
        Literal["AccountWizard"]
        | Literal["AddContact"]
        | Literal["AdHocCommands"]
        | Literal["AdvancedConfig"]
        | Literal["DBMigration"]
        | Literal["DebugConsoleWindow"]
        | Literal["CallWindow"]
        | Literal["CertificateDialog"]
        | Literal["ChangePassword"]
        | Literal["ContactInfo"]
        | Literal["CreateGroupchatWindow"]
        | Literal["Features"]
        | Literal["GroupchatDetails"]
        | Literal["GroupchatJoin"]
        | Literal["HistoryExport"]
        | Literal["HistorySyncAssistant"]
        | Literal["ManageProxies"]
        | Literal["ManageSounds"]
        | Literal["PasswordDialog"]
        | Literal["PEPConfig"]
        | Literal["Preferences"]
        | Literal["ProfileWindow"]
        | Literal["QuitDialog"]
        | Literal["RemoveAccount"]
        | Literal["RosterItemExchange"]
        | Literal["ServiceDiscoveryWindow"]
        | Literal["ServiceRegistration"]
        | Literal["SSLErrorDialog"]
        | Literal["StartChatDialog"]
        | Literal["Themes"]
        | Literal["WorkspaceDialog"]
    )

log = logging.getLogger("gajim.gtk.util.window")


def get_total_screen_geometry() -> tuple[int, int]:
    total_width = 0
    total_height = 0
    display = Gdk.Display.get_default()
    assert display is not None
    monitors = display.get_monitors()
    for num in range(monitors.get_n_items()):
        monitor = monitors.get_item(num)
        assert isinstance(monitor, Gdk.Monitor)
        geometry = monitor.get_geometry()
        total_width += geometry.width
        total_height = max(total_height, geometry.height)
    log.debug("Get screen geometry: %s %s", total_width, total_height)
    return total_width, total_height


def resize_window(window: Gtk.Window, width: int, height: int) -> None:
    """
    Resize window, but also checks if huge window or negative values
    """
    screen_w, screen_h = get_total_screen_geometry()
    if not width or not height:
        return

    width = min(width, screen_w)
    height = min(height, screen_h)
    window.set_default_size(abs(width), abs(height))


def get_app_windows(account: str) -> list[Gtk.Window]:
    windows: list[Gtk.Window] = []
    for win in app.app.get_windows():
        if hasattr(win, "wrapper"):
            win = win.wrapper  # pyright: ignore

        if hasattr(win, "account"):  # pyright: ignore
            if win.account == account:  # pyright: ignore
                windows.append(win)  # pyright: ignore
    return windows


@overload
def get_app_window(
    name: Literal["AccountWizard"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> AccountWizard | None: ...


@overload
def get_app_window(
    name: Literal["AddContact"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> AddContact | None: ...


@overload
def get_app_window(
    name: Literal["AdHocCommands"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> AdHocCommands | None: ...


@overload
def get_app_window(
    name: Literal["AdvancedConfig"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> AdvancedConfig | None: ...


@overload
def get_app_window(
    name: Literal["DBMigration"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> DBMigration | None: ...


@overload
def get_app_window(
    name: Literal["DebugConsoleWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> DebugConsoleWindow | None: ...


@overload
def get_app_window(
    name: Literal["CallWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> CallWindow | None: ...


@overload
def get_app_window(
    name: Literal["CertificateDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> CertificateDialog | None: ...


@overload
def get_app_window(
    name: Literal["ChangePassword"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ChangePassword | None: ...


@overload
def get_app_window(
    name: Literal["ContactInfo"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ContactInfo | None: ...


@overload
def get_app_window(
    name: Literal["CreateGroupchatWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> CreateGroupchatWindow | None: ...


@overload
def get_app_window(
    name: Literal["Features"], account: str | None = None, jid: str | JID | None = None
) -> Features | None: ...


@overload
def get_app_window(
    name: Literal["GroupchatDetails"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> GroupchatDetails | None: ...


@overload
def get_app_window(
    name: Literal["GroupchatJoin"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> GroupchatJoin | None: ...


@overload
def get_app_window(
    name: Literal["HistoryExport"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> HistoryExport | None: ...


@overload
def get_app_window(
    name: Literal["HistorySyncAssistant"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> HistorySyncAssistant | None: ...


@overload
def get_app_window(
    name: Literal["ManageProxies"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ManageProxies | None: ...


@overload
def get_app_window(
    name: Literal["ManageSounds"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ManageSounds | None: ...


@overload
def get_app_window(
    name: Literal["PasswordDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> PasswordDialog | None: ...


@overload
def get_app_window(
    name: Literal["PEPConfig"], account: str | None = None, jid: str | JID | None = None
) -> PEPConfig | None: ...


@overload
def get_app_window(
    name: Literal["Preferences"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> Preferences | None: ...


@overload
def get_app_window(
    name: Literal["ProfileWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ProfileWindow | None: ...


@overload
def get_app_window(
    name: Literal["QuitDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> QuitDialog | None: ...


@overload
def get_app_window(
    name: Literal["RemoveAccount"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> RemoveAccount | None: ...


@overload
def get_app_window(
    name: Literal["RosterItemExchange"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> RosterItemExchange | None: ...


@overload
def get_app_window(
    name: Literal["ServiceDiscoveryWindow"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ServiceDiscoveryWindow | None: ...


@overload
def get_app_window(
    name: Literal["ServiceRegistration"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> ServiceRegistration | None: ...


@overload
def get_app_window(
    name: Literal["SSLErrorDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> SSLErrorDialog | None: ...


@overload
def get_app_window(
    name: Literal["StartChatDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> StartChatDialog | None: ...


@overload
def get_app_window(
    name: Literal["Themes"], account: str | None = None, jid: str | JID | None = None
) -> Themes | None: ...


@overload
def get_app_window(
    name: Literal["WorkspaceDialog"],
    account: str | None = None,
    jid: str | JID | None = None,
) -> WorkspaceDialog | None: ...


def get_app_window(
    name: str, account: str | None = None, jid: str | JID | None = None
) -> GajimWindowT | None:
    for win in app.app.get_windows():
        if win.get_name() != name:
            continue

        if hasattr(win, "wrapper"):
            win = win.wrapper  # pyright: ignore

        if account is not None:
            if account != win.account:  # pyright: ignore
                continue

        if jid is not None:
            if jid != win.jid:  # pyright: ignore
                continue

        return win  # pyright: ignore

    return None


@overload
def open_window(name: Literal["AccountWizard"], **kwargs: Any) -> AccountWizard: ...
@overload
def open_window(name: Literal["AddContact"], **kwargs: Any) -> AddContact: ...
@overload
def open_window(name: Literal["AdHocCommands"], **kwargs: Any) -> AdHocCommands: ...
@overload
def open_window(name: Literal["AdvancedConfig"], **kwargs: Any) -> AdvancedConfig: ...
@overload
def open_window(name: Literal["DBMigration"], **kwargs: Any) -> DBMigration: ...
@overload
def open_window(
    name: Literal["DebugConsoleWindow"], **kwargs: Any
) -> DebugConsoleWindow: ...
@overload
def open_window(name: Literal["CallWindow"], **kwargs: Any) -> CallWindow: ...
@overload
def open_window(
    name: Literal["CertificateDialog"], **kwargs: Any
) -> CertificateDialog: ...
@overload
def open_window(name: Literal["ChangePassword"], **kwargs: Any) -> ChangePassword: ...
@overload
def open_window(name: Literal["ContactInfo"], **kwargs: Any) -> ContactInfo: ...
@overload
def open_window(
    name: Literal["CreateGroupchatWindow"], **kwargs: Any
) -> CreateGroupchatWindow: ...
@overload
def open_window(name: Literal["Features"], **kwargs: Any) -> Features: ...
@overload
def open_window(
    name: Literal["GroupchatDetails"], **kwargs: Any
) -> GroupchatDetails: ...
@overload
def open_window(name: Literal["GroupchatJoin"], **kwargs: Any) -> GroupchatJoin: ...
@overload
def open_window(name: Literal["HistoryExport"], **kwargs: Any) -> HistoryExport: ...
@overload
def open_window(
    name: Literal["HistorySyncAssistant"], **kwargs: Any
) -> HistorySyncAssistant: ...
@overload
def open_window(name: Literal["ManageProxies"], **kwargs: Any) -> ManageProxies: ...
@overload
def open_window(name: Literal["ManageSounds"], **kwargs: Any) -> ManageSounds: ...
@overload
def open_window(name: Literal["PasswordDialog"], **kwargs: Any) -> PasswordDialog: ...
@overload
def open_window(name: Literal["PEPConfig"], **kwargs: Any) -> PEPConfig: ...
@overload
def open_window(name: Literal["Preferences"], **kwargs: Any) -> Preferences: ...
@overload
def open_window(name: Literal["ProfileWindow"], **kwargs: Any) -> ProfileWindow: ...
@overload
def open_window(name: Literal["QuitDialog"], **kwargs: Any) -> QuitDialog: ...
@overload
def open_window(name: Literal["RemoveAccount"], **kwargs: Any) -> RemoveAccount: ...
@overload
def open_window(
    name: Literal["RosterItemExchange"], **kwargs: Any
) -> RosterItemExchange: ...
@overload
def open_window(
    name: Literal["ServiceDiscoveryWindow"], **kwargs: Any
) -> ServiceDiscoveryWindow: ...
@overload
def open_window(
    name: Literal["ServiceRegistration"], **kwargs: Any
) -> ServiceRegistration: ...
@overload
def open_window(name: Literal["SSLErrorDialog"], **kwargs: Any) -> SSLErrorDialog: ...
@overload
def open_window(name: Literal["StartChatDialog"], **kwargs: Any) -> StartChatDialog: ...
@overload
def open_window(name: Literal["Themes"], **kwargs: Any) -> Themes: ...
@overload
def open_window(name: Literal["WorkspaceDialog"], **kwargs: Any) -> WorkspaceDialog: ...


def open_window(name: GajimWindowNameT, **kwargs: Any) -> GajimWindowT:
    window = get_app_window(name, kwargs.get("account"), kwargs.get("jid"))
    if window is None:
        module = import_module(WINDOW_MODULES[name])
        window_cls = getattr(module, name)
        window = window_cls(**kwargs)

    window.present()
    return window
