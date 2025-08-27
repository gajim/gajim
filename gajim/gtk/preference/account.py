# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common import passwords
from gajim.common import types
from gajim.common.const import ClientState
from gajim.common.events import AccountDisabled
from gajim.common.events import AccountEnabled
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.i18n import p_

from gajim.gtk.alert import AlertDialog
from gajim.gtk.alert import CancelDialogResponse
from gajim.gtk.alert import DialogResponse
from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.filechoosers import Filter
from gajim.gtk.omemo_trust_manager import OMEMOTrustManager
from gajim.gtk.settings import GajimPreferencePage
from gajim.gtk.settings import GajimPreferencesGroup
from gajim.gtk.settings import SignalManager
from gajim.gtk.sidebar_switcher import SideBarMenuItem
from gajim.gtk.structs import ExportHistoryParam
from gajim.gtk.util.window import open_window


class AccountGeneralGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(self, key="account-general", account=account)

        workspaces = self._get_workspaces()

        settings = [
            Setting(
                SettingKind.ENTRY,
                _("Label"),
                SettingType.ACCOUNT_CONFIG,
                "account_label",
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
                SettingKind.SUBPAGE,
                _("Login"),
                SettingType.DIALOG,
                desc=_("Change your account’s password, etc."),
                bind="account::anonymous_auth",
                inverted=True,
                props={"subpage": f"{self.account}-general-login"},
            ),
            # Currently not supported by nbxmpp
            #
            # Setting(SettingKind.DIALOG,
            #         _('Client Certificate'),
            #         SettingType.SUBPAGE,
            #         props={'subpage': f"{self.account}-general-certificate"}),
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

        for setting in settings:
            self.add_setting(setting)

    @staticmethod
    def _get_workspaces() -> dict[str, str]:
        workspaces: dict[str, str] = {"": _("Disabled")}
        for workspace_id in app.settings.get_workspaces():
            name = app.settings.get_workspace_setting(workspace_id, "name")
            workspaces[workspace_id] = name
        return workspaces


class AccountGeneralAdvancedGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="account-general-advanced",
            account=account,
            description=_(
                "Removing the account will delete most related data. "
                "If you want to disconnect the account for a short time, "
                "use the status selector."
            ),
            title=_("Danger Zone"),
        )

        self.add(AccountActiveSwitch(account))

        settings = [
            Setting(
                SettingKind.GENERIC,
                _("Remove Account"),
                SettingType.VALUE,
                None,
                desc=_("This will remove the account and delete all data"),
                props={
                    "button-text": _("Remove…"),
                    "button-style": "destructive-action",
                    "button-callback": self._on_remove_account,
                },
            ),
        ]

        for setting in settings:
            self.add_setting(setting)

    def _on_remove_account(self, button: Gtk.Button) -> None:
        open_window("RemoveAccount", account=self.account)


class AccountPrivacyGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(self, key="account-privacy", account=account)

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

        for setting in settings:
            self.add_setting(setting)

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
        assert self.account is not None
        app.settings.set_account_setting(self.account, "send_marker_default", state)
        app.settings.set_account_setting(
            self.account, "gc_send_marker_private_default", state
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


class AccountOmemoSettingsGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="account-omemo-settings", account=account
        )

        title_heading = _("Trust Management")
        wiki_url = "https://dev.gajim.org/gajim/gajim/-/wikis/help/OMEMO"
        link_text = _("Read more about blind trust")
        link_markup = f'<a href="{wiki_url}">{link_text}</a>'

        self.set_title(f"{title_heading}\n{link_markup}")

        settings = [
            Setting(
                SettingKind.SWITCH,
                _("Blind Trust"),
                SettingType.ACCOUNT_CONFIG,
                "omemo_blind_trust",
                desc=_("Blindly trust new devices until you verify them"),
            )
        ]

        for setting in settings:
            self.add_setting(setting)


class AccountOmemoTrustGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(self, key="account-omemo-trust", account=account)

        omemo_trust_manager = OMEMOTrustManager(account)
        self.add(omemo_trust_manager)


class AccountConnectionGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(self, key="account-connection", account=account)

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
                SettingKind.SUBPAGE,
                _("Hostname"),
                SettingType.ACCOUNT_CONFIG,
                "use_custom_host",
                desc=_("Manually set the hostname for the server"),
                props={"subpage": f"{self.account}-connection-hostname"},
            ),
            Setting(
                SettingKind.ENTRY, _("Resource"), SettingType.ACCOUNT_CONFIG, "resource"
            ),
            Setting(
                SettingKind.SUBPAGE,
                _("Priority"),
                SettingType.ACCOUNT_CONFIG,
                "priority",
                props={"subpage": f"{self.account}-connection-priority"},
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

        for setting in settings:
            self.add_setting(setting)

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
        raise NotImplementedError
        # dropdown_row = cast(DropDownSetting, self.listbox.get_setting("proxy"))
        # dropdown_row.update_entries(self._get_proxies())


class AccountAdvancedGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(self, key="account-advanced", account=account)

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

        for setting in settings:
            self.add_setting(setting)


class PriorityGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(self, key="priority", account=account)

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

        for setting in settings:
            self.add_setting(setting)


class LoginGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(self, key="login", account=account)

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
                callback=self._on_save_password,
            ),
            Setting(
                SettingKind.CHANGEPASSWORD,
                _("Change Password"),
                SettingType.DIALOG,
                callback=self._on_password_change,
                props={"dialog": None},
            ),
            Setting(
                SettingKind.SWITCH,
                _("Use GSSAPI"),
                SettingType.ACCOUNT_CONFIG,
                "enable_gssapi",
            ),
        ]

        for setting in settings:
            self.add_setting(setting)

    def _on_password_change(self, new_password: str, _data: Any) -> None:
        assert self.account is not None
        passwords.save_password(self.account, new_password)

    def _on_save_password(self, state: bool, _data: Any) -> None:
        if not state:
            assert self.account is not None
            passwords.delete_password(self.account)


class HostnameGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(self, key="hostname", account=account)

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

        for setting in settings:
            self.add_setting(setting)


class CertificateGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(self, key="certificate", account=account)

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

        for setting in settings:
            self.add_setting(setting)


class AccountGeneralPage(GajimPreferencePage):
    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            key=f"{account}-general",
            title=_("General | %(account)s") % {"account": account},
            groups=[],
            menu=SideBarMenuItem(
                f"{account}-general",
                _("General"),
                icon_name="lucide-user-symbolic",
            ),
        )

        self.add(AccountGeneralGroup(account))
        self.add(AccountGeneralAdvancedGroup(account))


class AccountPrivacyPage(GajimPreferencePage):
    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            key=f"{account}-privacy",
            title=_("Privacy | %(account)s") % {"account": account},
            groups=[],
            menu=SideBarMenuItem(
                f"{account}-privacy",
                _("Privacy"),
                icon_name="lucide-eye-symbolic",
            ),
        )

        self.add(AccountPrivacyGroup(account))


class AccountOmemoPage(GajimPreferencePage):
    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            key=f"{account}-encryption-omemo",
            title=_("Encryption (OMEMO) | %(account)s") % {"account": account},
            groups=[],
            menu=SideBarMenuItem(
                f"{account}-encryption-omemo",
                _("Encryption (OMEMO)"),
                icon_name="lucide-lock-symbolic",
            ),
        )

        self.add(AccountOmemoSettingsGroup(account))
        self.add(AccountOmemoTrustGroup(account))


class AccountConnectionPage(GajimPreferencePage):
    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            key=f"{account}-connection",
            title=_("Connection | %(account)s") % {"account": account},
            groups=[],
            menu=SideBarMenuItem(
                f"{account}-connection",
                _("Connection"),
                icon_name="lucide-globe-symbolic",
            ),
        )

        self.add(AccountConnectionGroup(account))


class LoginPage(GajimPreferencePage):
    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Login | %(account)s") % {"account": account},
            key=f"{account}-general-login",
            groups=[],
        )

        self.add(LoginGroup(account))


class PriorityPage(GajimPreferencePage):
    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Priority | %(account)s") % {"account": account},
            key=f"{account}-connection-priority",
            groups=[],
        )

        self.add(PriorityGroup(account))


class HostnamePage(GajimPreferencePage):
    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Hostname | %(account)s") % {"account": account},
            key=f"{account}-connection-hostname",
            groups=[],
        )

        self.add(HostnameGroup(account))


class AccountAdvancedPage(GajimPreferencePage):
    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Advanced | %(account)s") % {"account": account},
            key=f"{account}-advanced",
            groups=[],
            menu=SideBarMenuItem(
                f"{account}-advanced",
                _("Advanced"),
                icon_name="lucide-settings-symbolic",
            ),
        )

        self.add(AccountAdvancedGroup(account))


class AccountActiveSwitch(Adw.ActionRow, SignalManager, EventHelper):
    def __init__(self, account: str) -> None:
        Adw.ActionRow.__init__(self, title=_("Enable Account"))
        SignalManager.__init__(self)
        EventHelper.__init__(self)

        self._account = account

        active = app.settings.get_account_setting(account, "active")

        self._label = Gtk.Label(margin_end=12)
        self.add_suffix(self._label)

        self._switch = Gtk.Switch(active=active, valign=Gtk.Align.CENTER)
        self.add_suffix(self._switch)
        self.set_activatable_widget(self._switch)
        self._update_label()

        self.register_events(
            [
                ("account-enabled", ged.GUI2, self._on_account_state_changed),
                ("account-disabled", ged.GUI2, self._on_account_state_changed),
            ]
        )

        self._connect(self._switch, "state-set", self._on_state_set, account)

    def do_unroot(self) -> None:
        Adw.ActionRow.do_unroot(self)
        self._disconnect_all()
        self.unregister_events()
        app.check_finalize(self)

    def _update_label(self) -> None:
        if self._switch.get_active():
            self._label.set_text(p_("Switch", "On"))
        else:
            self._label.set_text(p_("Switch", "Off"))

    def _on_account_state_changed(
        self, event: AccountEnabled | AccountDisabled
    ) -> None:
        if event.account != self._account:
            return

        state = isinstance(event, AccountEnabled)
        self._switch.set_state(state)
        self._update_label()

    def _on_state_changed(
        self, client: types.Client, _signal_name: str, client_state: ClientState
    ) -> None:

        if client_state.is_disconnected:
            app.app.disable_account(client.account)

    def _on_state_set(self, switch: Gtk.Switch, state: bool, account: str) -> int:

        def _on_response(response_id: str) -> None:
            if response_id == "disable":
                client = app.get_client(account)
                client.connect_signal("state-changed", self._on_state_changed)
                client.change_status("offline", "offline")

            switch.set_state(state)

        account_is_active = app.settings.get_account_setting(account, "active")
        if account_is_active == state:
            return Gdk.EVENT_PROPAGATE

        if account_is_active and not app.get_client(account).state.is_disconnected:
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
            )
            return Gdk.EVENT_STOP

        if state:
            app.app.enable_account(account)
        else:
            app.app.disable_account(account)

        return Gdk.EVENT_PROPAGATE
