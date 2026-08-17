# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common import ged
from gajim.common import passwords
from gajim.common import types
from gajim.common.const import ClientState
from gajim.common.const import GAJIM_OMEMO_WIKI_URI
from gajim.common.const import TLS_VERSION_STRINGS
from gajim.common.events import AccountDisabled
from gajim.common.events import AccountEnabled
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.i18n import p_
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.alert import AlertDialog
from gajim.gtk.alert import CancelDialogResponse
from gajim.gtk.alert import DialogResponse
from gajim.gtk.certificate_dialog import CertificatePage
from gajim.gtk.const import Setting
from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.crypto_trust_manager import CryptoTrustManager
from gajim.gtk.preference.archiving import ArchivingPreferences
from gajim.gtk.preference.blocked_contacts import BlockedContacts
from gajim.gtk.preference.manage_roster import ManageRoster
from gajim.gtk.preference.widgets import CopyButton
from gajim.gtk.preference.widgets import PlaceholderBox
from gajim.gtk.settings.group import GajimPreferencesGroup
from gajim.gtk.settings.page import GajimPreferencePage
from gajim.gtk.settings.row import DialogSetting
from gajim.gtk.settings.row import DropDownSetting
from gajim.gtk.settings.row import GenericSetting
from gajim.gtk.settings.row import register_rows
from gajim.gtk.settings.row import SwitchSetting
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.util.window import open_window


class AccountGeneralGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="account-general", account=account, title=_("General")
        )

        self.bind_settings_model(
            app.app.settings.get_single_model("account-general", account)
        )


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


class SendIdleTime(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = self._send_idle_time

    def _send_idle_time(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module("LastActivity").set_enabled(state)


class SendOsInfo(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = self._send_os_info

    def _send_os_info(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module("SoftwareVersion").set_enabled(state)


class PublishTune(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = self._publish_tune

    def _publish_tune(self, state: bool, _data: Any) -> None:
        if self._client is not None:
            self._client.get_module("UserTune").set_enabled(state)


class SendChatStateIndicators(DropDownSetting):
    def __post_init__(self) -> None:
        props = {
            "button-text": _("Reset"),
            "button-tooltip": _("Reset all chats to the current default value"),
            "button-style": "destructive-action",
            "button-callback": self._reset_send_chatstate,
        }
        self._add_action_button(props)

    def _reset_send_chatstate(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_contact_settings(self.account, "send_chatstate", None)


class SendGroupChatStateIndicators(DropDownSetting):
    def __post_init__(self) -> None:
        props = {
            "button-text": _("Reset"),
            "button-tooltip": _("Reset all group chats to the current default value"),
            "button-style": "destructive-action",
            "button-callback": self._reset_gc_send_chatstate,
        }
        self._add_action_button(props)

    def _reset_gc_send_chatstate(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)

        def _context_match_func(account: str, jid: JID) -> Literal["public"]:
            # send_chatstate has no context dependent setting
            # so the context does not matter
            return "public"

        app.settings.set_group_chat_settings(
            self.account, "send_chatstate", None, _context_match_func
        )


class SendReadMarker(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = self._send_read_marker
        props = {
            "button-text": _("Reset"),
            "button-tooltip": _("Reset all chats to the current default value"),
            "button-style": "destructive-action",
            "button-callback": self._reset_send_read_marker,
        }
        self._add_action_button(props)

    def _send_read_marker(self, state: bool, _data: Any) -> None:
        assert self.account is not None
        app.settings.set_account_setting(self.account, "send_marker_default", state)
        app.settings.set_account_setting(
            self.account, "gc_send_marker_private_default", state
        )

    def _reset_send_read_marker(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        app.settings.set_contact_settings(self.account, "send_marker", None)

        def _context_match_func(account: str, jid: JID) -> Literal["private"] | None:
            client = app.get_client(account)
            contact = client.get_module("Contacts").get_contact(jid, groupchat=True)
            if not isinstance(contact, GroupchatContact):
                return None

            if contact.muc_context == "private":
                return "private"
            return None

        app.settings.set_group_chat_settings(
            self.account, "send_marker", None, _context_match_func
        )


class SyncMucBlocks(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = self._sync_blocks
        self.enabled_func = self._get_sync_blocks_enabled

    def _get_sync_blocks_enabled(self) -> bool:
        if self._client is None:
            return False

        if not self._client.is_available():
            return False

        return self._client.get_module("Bookmarks").native_bookmarks_used

    def _sync_blocks(self, state: bool, _data: Any) -> None:
        if self._client is not None and state:
            self._client.get_module("MucBlocking").merge_blocks()


class AccountPrivacyGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="account-privacy", account=account, title=_("Privacy")
        )

        self.bind_settings_model(
            app.app.settings.get_single_model("account-privacy", account)
        )


class AccountOmemoSettingsGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="account-omemo-settings", account=account
        )

        self.set_title(_("Trust Management"))
        link_text = _("Read more about blind trust")
        self.set_description(f'<a href="{GAJIM_OMEMO_WIKI_URI}">{link_text}</a>')

        self.bind_settings_model(
            app.app.settings.get_single_model("account-omemo-settings", account)
        )


class AccountOmemoTrustGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(self, key="account-omemo-trust", account=account)

        crypto_trust_manager = CryptoTrustManager("OMEMO", account)
        self.add(crypto_trust_manager)


class AccountOpenPGPSettingsGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="account-openpgp-settings", account=account
        )

        self.set_title(_("Trust Management"))

        self.bind_settings_model(
            app.app.settings.get_single_model("account-openpgp-settings", account)
        )


class BackupSecretKey(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = self._on_backup
        self.enabled_func = lambda: app.account_is_connected(self.account)

    def _on_backup(self, state: bool, _data: Any) -> None:
        if state:
            return

        def _on_response() -> None:
            assert self.account is not None
            client = app.get_client(self.account)
            client.get_module("OpenPGP").remove_backup_from_server()

        AlertDialog(
            _("Remove Backup"),
            _("Do you want to remove the backup from your server?"),
            responses=[
                CancelDialogResponse(label=_("Keep Backup")),
                DialogResponse("confirm", _("Remove from Server"), "destructive"),
            ],
            emit_responses=["confirm"],
            callback=_on_response,
        )


class AccountOpenPGPSecretGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="account-openpgp-secret", account=account
        )

        self.set_title(_("Secret Key Management"))
        self.bind_settings_model(
            app.app.settings.get_single_model("account-openpgp-secret", account)
        )


class AccountOpenPGPTrustGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="account-openpgp-trust", account=account
        )

        crypto_trust_manager = CryptoTrustManager("OpenPGP", account)
        self.add(crypto_trust_manager)


class Proxy(DropDownSetting):
    def __post_init__(self) -> None:
        props = {
            "button-icon-name": "lucide-settings-symbolic",
            "button-callback": self._on_proxy_edit,
        }
        self._add_action_button(props)

    @staticmethod
    def _on_proxy_edit(*args: Any) -> None:
        open_window("ManageProxies")


class AccountConnectionGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="account-connection", account=account, title=_("Connection")
        )
        self.bind_settings_model(
            app.app.settings.get_single_model("account-connection", account)
        )


@Gtk.Template(string=get_ui_string("preference/connection_details.ui"))
class AccountConnectionDetailsGroup(Adw.PreferencesGroup, SignalManager):
    __gtype_name__ = "AccountConnectionDetailsGroup"

    _clipboard_button: CopyButton = Gtk.Template.Child()
    _domain: Adw.ActionRow = Gtk.Template.Child()
    _dns: Adw.ActionRow = Gtk.Template.Child()
    _ip_port: Adw.ActionRow = Gtk.Template.Child()
    _websocket: Adw.ActionRow = Gtk.Template.Child()
    _connection_type: Adw.ActionRow = Gtk.Template.Child()
    _tls_version: Adw.ActionRow = Gtk.Template.Child()
    _cipher_suite: Adw.ActionRow = Gtk.Template.Child()
    _proxy_type: Adw.ActionRow = Gtk.Template.Child()
    _proxy_host: Adw.ActionRow = Gtk.Template.Child()

    def __init__(self, account: str) -> None:
        Adw.PreferencesGroup.__init__(self)
        SignalManager.__init__(self)

        client = app.get_client(account)
        nbxmpp_client = client.connection
        address = nbxmpp_client.current_address

        assert address is not None
        assert address.domain is not None
        self._domain.set_subtitle(address.domain)

        visible = address.service is not None
        self._dns.set_visible(visible)
        self._dns.set_subtitle(address.service or "")

        visible = nbxmpp_client.remote_address is not None
        self._ip_port.set_visible(visible)
        self._ip_port.set_subtitle(nbxmpp_client.remote_address or "")

        visible = address.uri is not None
        self._websocket.set_visible(visible)
        self._websocket.set_subtitle(address.uri or "")

        self._connection_type.set_subtitle(address.type.value)
        if address.type.is_plain:
            self._connection_type.add_css_class("error")

        assert nbxmpp_client is not None
        tls_version = TLS_VERSION_STRINGS.get(nbxmpp_client.tls_version or -1)
        self._tls_version.set_subtitle(tls_version or _("Not available"))

        self._cipher_suite.set_subtitle(nbxmpp_client.ciphersuite or _("Not available"))

        # Connection proxy
        proxy = address.proxy
        if proxy is not None:
            self._proxy_type.set_subtitle(proxy.type)
            self._proxy_host.set_subtitle(proxy.host or "-")

        self._connect(
            self._clipboard_button, "clicked", self._on_clipboard_button_clicked
        )

    def _on_clipboard_button_clicked(self, _widget: Gtk.Button) -> None:
        string = f"Domain: {self._domain.get_subtitle()}\n"
        if self._dns.is_visible():
            string += f"DNS: {self._dns.get_subtitle()}\n"
        if self._ip_port.is_visible():
            string += f"IP/Port: {self._ip_port.get_subtitle()}\n"
        if self._websocket.is_visible():
            string += f"WebSocket URL: {self._websocket.get_subtitle()}\n"

        string += (
            f"Type: {self._connection_type.get_subtitle()}\n"
            f"TLS Version: {self._tls_version.get_subtitle()}\n"
            f"Cipher Suite: {self._cipher_suite.get_subtitle()}\n"
            f"Proxy Type: {self._proxy_type.get_subtitle()}\n"
            f"Proxy Host: {self._proxy_host.get_subtitle()}\n"
        )
        app.window.get_clipboard().set(string)

    def do_unroot(self) -> None:
        Adw.PreferencesGroup.do_unroot(self)
        self._disconnect_all()


class AccountManageRosterGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="account-manage-roster",
            account=account,
            title=_("Contact List"),
        )

        self.add(ManageRoster(account))


class AccountBlockedContactsGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="account-blocked-contacts",
            account=account,
            title=_("Blocked Contacts"),
        )

        self.add(BlockedContacts(account))


class SyncHistory(GenericSetting):
    def __post_init__(self) -> None:
        props = {
            "button-text": _("Open"),
            "button-callback": self._on_sync,
        }
        self._add_action_button(props)

    def _on_sync(self, _button: Gtk.Button) -> None:
        open_window("HistorySyncAssistant", account=self.account)


class AccountArchivingGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="account-archiving", account=account, title=_("Archive")
        )

        self.bind_settings_model(
            app.app.settings.get_single_model("account-archiving", account)
        )


class AccountArchivingPreferencesGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self,
            key="account-archiving-preferences",
            account=account,
            description=_(
                "Configure which messages will be archived on the server. "
                "Not archiving messages on the server may prevent them from "
                "synchronizing between your devices."
            ),
            title=_("Preferences"),
        )

        self.add(ArchivingPreferences(account))


class AccountAdvancedGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="account-advanced", account=account, title=_("Advanced")
        )

        self.bind_settings_model(
            app.app.settings.get_single_model("account-advanced", account)
        )


class SavePassword(SwitchSetting):
    def __post_init__(self) -> None:
        self.callback = self._on_save_password
        self.enabled_func = lambda: (
            not app.settings.get("use_keyring") or passwords.is_keyring_available()
        )

    def _on_save_password(self, state: bool, _data: Any) -> None:
        if not state:
            assert self.account is not None
            passwords.delete_password(self.account)


class ChangePassword(DialogSetting):
    def __post_init__(self) -> None:
        self.enabled_func = lambda: app.account_is_connected(self.account)


class LoginGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="login", account=account, title=_("Login")
        )

        self.bind_settings_model(app.app.settings.get_single_model("login", account))


class HostnameGroup(GajimPreferencesGroup):
    def __init__(self, account: str) -> None:
        GajimPreferencesGroup.__init__(
            self, key="hostname", account=account, title=_("Hostname")
        )

        self.bind_settings_model(app.app.settings.get_single_model("hostname", account))


class AccountGeneralPage(GajimPreferencePage):
    key = "general"
    icon_name = "lucide-user-symbolic"
    label = _("General")

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("General – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        self.add(AccountGeneralGroup(account))
        self.add(AccountGeneralAdvancedGroup(account))


class AccountPrivacyPage(GajimPreferencePage):
    key = "privacy"
    icon_name = "lucide-eye-symbolic"
    label = _("Privacy")

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Privacy – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        self.add(AccountPrivacyGroup(account))


class AccountOmemoPage(GajimPreferencePage):
    key = "encryption-omemo"
    icon_name = "lucide-lock-symbolic"
    label = _("Encryption (OMEMO)")

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Encryption (OMEMO) – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        self.add(AccountOmemoSettingsGroup(account))
        self.add(AccountOmemoTrustGroup(account))


class AccountOpenPGPPage(GajimPreferencePage):
    key = "encryption-openpgp"
    icon_name = "lucide-lock-symbolic"
    label = _("Encryption (OpenPGP)")

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Encryption (OpenPGP) – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        self.add(AccountOpenPGPSettingsGroup(account))
        self.add(AccountOpenPGPSecretGroup(account))
        self.add(AccountOpenPGPTrustGroup(account))


class AccountConnectionDetailsPage(GajimPreferencePage):
    key = "connection-details"

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Details - %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        if not app.account_is_available(account):
            self.set_content(PlaceholderBox(valign=Gtk.Align.CENTER))
            return

        self.add(AccountConnectionDetailsGroup(account))


class AccountConnectionCertificatePage(GajimPreferencePage):
    key = "connection-certificate"

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Certificate - %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        if not app.account_is_available(account):
            self.set_content(PlaceholderBox(valign=Gtk.Align.CENTER))
            return

        client = app.get_client(account)
        if client.certificate is None:
            self.set_content(
                Gtk.Label(label=_("No certificate available"), valign=Gtk.Align.CENTER)
            )
            return

        self.set_content(CertificatePage(account, client.certificate))


class AccountConnectionPage(GajimPreferencePage):
    key = "connection"
    icon_name = "lucide-globe-symbolic"
    label = _("Connection")

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Connection – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        self.add(AccountConnectionGroup(account))


class AccountManageRosterPage(GajimPreferencePage):
    key = "manage-roster"
    icon_name = "lucide-users-symbolic"
    label = _("Contact List")

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Contact List – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        if not app.account_is_available(account):
            self.set_content(PlaceholderBox(valign=Gtk.Align.CENTER))
            return

        self.add(AccountManageRosterGroup(account))


class AccountBlockedContactsPage(GajimPreferencePage):
    key = "blocked-contacts"
    icon_name = "lucide-user-round-x-symbolic"
    label = _("Blocked Contacts")

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Blocked Contacts – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        if not app.account_is_available(account):
            self.set_content(PlaceholderBox(valign=Gtk.Align.CENTER))
            return

        self.add(AccountBlockedContactsGroup(account))


class AccountArchivingPage(GajimPreferencePage):
    key = "archiving"
    icon_name = "lucide-database-backup-symbolic"
    label = _("Archiving")

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Archiving – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        if not app.account_is_available(account):
            self.set_content(PlaceholderBox(valign=Gtk.Align.CENTER))
            return

        self.add(AccountArchivingGroup(account))
        self.add(AccountArchivingPreferencesGroup(account))


class LoginPage(GajimPreferencePage):
    key = "general-login"

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Login – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        self.add(LoginGroup(account))


class HostnamePage(GajimPreferencePage):
    key = "connection-hostname"

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Hostname – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
        )

        self.add(HostnameGroup(account))


class AccountAdvancedPage(GajimPreferencePage):
    key = "advanced"
    icon_name = "lucide-settings-symbolic"
    label = _("Advanced")

    def __init__(self, account: str) -> None:
        GajimPreferencePage.__init__(
            self,
            title=_("Advanced – %(account)s") % {"account": account},
            groups=[],
            tag_prefix=f"{account}-",
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
                client.connect("state-changed", self._on_state_changed)
                client.disconnect_immediate()

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


register_rows(
    {
        "send-idle-time": SendIdleTime,
        "send-os-info": SendOsInfo,
        "publish-tune": PublishTune,
        "send-chat-state-indicator": SendChatStateIndicators,
        "send-group-chat-state-indicator": SendGroupChatStateIndicators,
        "send-read-marker": SendReadMarker,
        "sync-muc-blocks": SyncMucBlocks,
        "backup-secret-key": BackupSecretKey,
        "proxy": Proxy,
        "sync-history": SyncHistory,
        "save-password": SavePassword,
        "change-password": ChangePassword,
    }
)
