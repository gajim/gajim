# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.events import AccountCreated
from gajim.common.events import AccountRemoved
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.setting_values import AllSettingsT

from gajim.gtk.alert import AlertDialog
from gajim.gtk.alert import DialogResponse
from gajim.gtk.preference.account import AccountAdvancedPage
from gajim.gtk.preference.account import AccountArchivingPage
from gajim.gtk.preference.account import AccountBlockedContactsPage
from gajim.gtk.preference.account import AccountConnectionCertificatePage
from gajim.gtk.preference.account import AccountConnectionDetailsPage
from gajim.gtk.preference.account import AccountConnectionPage
from gajim.gtk.preference.account import AccountGeneralPage
from gajim.gtk.preference.account import AccountManageRosterPage
from gajim.gtk.preference.account import AccountOmemoPage
from gajim.gtk.preference.account import AccountPrivacyPage
from gajim.gtk.preference.account import HostnamePage
from gajim.gtk.preference.account import LoginPage
from gajim.gtk.preference.app import AdvancedPage
from gajim.gtk.preference.app import AudioVideoPage
from gajim.gtk.preference.app import AutoAwayPage
from gajim.gtk.preference.app import AutoExtendedAwayPage
from gajim.gtk.preference.app import ChatsPage
from gajim.gtk.preference.app import GeneralPage
from gajim.gtk.preference.app import MiscellaneousGroup
from gajim.gtk.preference.app import PluginsPage
from gajim.gtk.preference.app import StatusPage
from gajim.gtk.preference.app import StylePage
from gajim.gtk.preference.app import VisualNotificationsPage
from gajim.gtk.preference.server_info import AccountProviderContactsPage
from gajim.gtk.preference.server_info import AccountProviderPage
from gajim.gtk.preference.shortcuts import ShortcutsPage
from gajim.gtk.sidebar_switcher import SideBarMenuItem
from gajim.gtk.sidebar_switcher import SideBarSwitcher
from gajim.gtk.window import GajimAppWindow

log = logging.getLogger("gajim.gtk.preferences")


class Preferences(GajimAppWindow, EventHelper):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="Preferences",
            title=_("Preferences"),
            default_width=900,
            default_height=650,
        )
        EventHelper.__init__(self)

        self._need_relogin: dict[str, list[AllSettingsT]] = {}
        self._account_menu_items: dict[str, SideBarMenuItem] = {}

        self._side_bar_switcher = SideBarSwitcher()

        menu: list[SideBarMenuItem] = []
        self._nav_view = Adw.NavigationView()

        preferences = [
            GeneralPage(),
            ChatsPage(),
            VisualNotificationsPage(),
            StatusPage(),
            StylePage(),
            AudioVideoPage(),
            ShortcutsPage(),
            PluginsPage(),
            AdvancedPage(),
            # Subpages
            AutoAwayPage(),
            AutoExtendedAwayPage(),
        ]

        for page in preferences:
            if page.menu is not None:
                menu.append(page.menu)
            self._nav_view.add(page)

        menu.append(
            SideBarMenuItem(
                "add-account",
                _("Add Account…"),
                group=_("Accounts"),
                icon_name="lucide-plus-symbolic",
                action="add-account",
            )
        )

        self._side_bar_switcher.set_with_menu(self._nav_view, menu)

        for account in app.get_accounts_sorted():
            self._add_account(account)

        scrolled = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
        )
        scrolled.set_child(self._side_bar_switcher)

        toolbar = Adw.ToolbarView(content=scrolled)
        toolbar.add_top_bar(Adw.HeaderBar())

        sidebar_page = Adw.NavigationPage(
            title=_("Preferences"), tag="sidebar", child=toolbar
        )

        content_page = Adw.NavigationPage(
            title=" ", tag="content", child=self._nav_view
        )

        nav = Adw.NavigationSplitView(sidebar=sidebar_page, content=content_page)

        self.set_child(nav)

        self._connect(self, "close-request", self._on_close_request)

        self.register_events(
            [
                ("account-created", ged.GUI2, self._on_account_state_changed),
                ("account-removed", ged.GUI2, self._on_account_state_changed),
            ]
        )

    def _cleanup(self) -> None:
        self.unregister_events()
        self._need_relogin.clear()
        self._account_menu_items.clear()
        self._side_bar_switcher.run_destroy()
        del self._side_bar_switcher
        del self._nav_view

    def update_proxy_list(self) -> None:
        page = cast(AdvancedPage, self._nav_view.find_page("advanced"))
        group = page.get_group("miscellaneous")
        assert isinstance(group, MiscellaneousGroup)
        group.update_proxy_list()

    def show_page(self, name: str) -> None:
        self._side_bar_switcher.activate_item(name)

    def _add_account(self, account: str) -> None:
        label = app.get_account_label(account)
        account_menu = SideBarMenuItem(account, label, group=_("Accounts"))

        pages = [
            AccountGeneralPage(account),
            AccountPrivacyPage(account),
            AccountOmemoPage(account),
            AccountConnectionPage(account),
            AccountProviderPage(account),
            AccountManageRosterPage(account),
            AccountBlockedContactsPage(account),
            AccountArchivingPage(account),
            AccountAdvancedPage(account),
            # Subpages
            LoginPage(account),
            HostnamePage(account),
            AccountConnectionDetailsPage(account),
            AccountConnectionCertificatePage(account),
            AccountProviderContactsPage(account),
        ]

        for page in pages:
            if page.menu is not None:
                account_menu.append_menu(page.menu)
            self._nav_view.add(page)

        self._side_bar_switcher.append_menu(account_menu)
        self._account_menu_items[account] = account_menu

        app.settings.connect_signal(
            "account_label", self._on_account_label_changed, account
        )

        self._need_relogin[account] = self._get_relogin_settings(account)

    def _remove_account(self, account: str) -> None:
        del self._need_relogin[account]
        menu = self._account_menu_items.pop(account)
        self._side_bar_switcher.remove_menu(menu.key)

        tags = [
            "general",
            "privacy",
            "encryption-omemo",
            "connection",
            "advanced",
            "connection-priority",
        ]

        for tag in tags:
            page = self._nav_view.find_page(f"{account}-{tag}")
            assert page is not None
            self._nav_view.remove(page)

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

    def _on_account_label_changed(
        self, label: str, _setting: str, account: str | None, *args: Any
    ) -> None:
        assert account is not None
        self._account_menu_items[account].set_label(label)

    def _on_account_state_changed(self, event: AccountCreated | AccountRemoved) -> None:
        if isinstance(event, AccountCreated):
            self._add_account(event.account)
        else:
            self._remove_account(event.account)

    def _on_close_request(self, _widget: Gtk.ApplicationWindow) -> bool:
        if self._check_relogin():
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE
