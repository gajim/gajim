# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common import ged
from gajim.common.events import AccountCreated
from gajim.common.events import AccountRemoved
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.util.version import package_version

from gajim.gtk.const import SettingKind
from gajim.gtk.const import SettingType
from gajim.gtk.structs import ExportHistoryParam


@dataclass
class SpinRange:
    lower: float
    upper: float
    step: float
    digits: int = 0


class SettingGObj(GObject.Object):
    __gtype_name__ = "SettingGObj"

    kind: SettingKind | str = GObject.Property(type=object)  # type: ignore
    label: str = GObject.Property(type=str)  # type: ignore
    type: SettingType = GObject.Property(type=int)  # type: ignore
    account: str | None = GObject.Property(type=str)  # type: ignore
    value: Any | None = GObject.Property(type=object)
    name: str | None = GObject.Property(type=str)  # type: ignore
    callback: Callable[..., None] | None = GObject.Property(type=object)  # type: ignore
    data: Any | None = GObject.Property(type=object)
    desc: str | None = GObject.Property(type=str)  # type: ignore
    bind: str | None = GObject.Property(type=str)  # type: ignore
    inverted: bool | None = GObject.Property(type=bool, default=False)  # type: ignore
    enabled_func: Callable[..., bool] | None = GObject.Property(type=object)  # type: ignore
    props_: dict[str, Any] | None = GObject.Property(type=object)  # type: ignore

    def __init__(
        self,
        kind: SettingKind | str,
        label: str,
        type: SettingType,  # noqa: A002
        *,
        account: str | None = None,
        value: Any | None = None,
        name: str | None = None,
        callback: Callable[..., None] | None = None,
        data: Any | None = None,
        desc: str | None = None,
        bind: str | None = None,
        inverted: bool | None = None,
        enabled_func: Callable[..., bool] | None = None,
        props_: dict[str, Any] | None = None,
    ) -> None:

        super().__init__(
            kind=kind,
            label=label,
            type=type,
            account=account,
            value=value,
            name=name,
            callback=callback,
            data=data,
            desc=desc,
            bind=bind,
            inverted=inverted,
            enabled_func=enabled_func,
            props_=props_ or {},
        )


class SettingModels(EventHelper):
    def __init__(self) -> None:
        EventHelper.__init__(self)
        self._models = Gio.ListStore(item_type=Gio.ListStore)
        self._flattened_model = Gtk.FlattenListModel(model=self._models)

        self._app_models: dict[str, Gio.ListStore] = {}
        self._account_models: dict[str, dict[str, Gio.ListStore]] = defaultdict(dict)

        self._app_model_classes = [
            WindowBehaviourModel,
            PluginSettingsModel,
            GeneralModel,
            ChatsModel,
            GroupChatsModel,
            FilePreviewModel,
            SystemNotificationsModel,
            NotificationsChatsModel,
            NotificationsGroupChatsModel,
            SoundsModel,
            StatusMessageModel,
            AutomaticStatusModel,
            AutoAwayModel,
            AutoExtendedAwayModel,
            AudioModel,
            ThemesModel,
            MiscellaneousModel,
            AdvancedModel,
        ]

        self._account_model_classes = [
            AccountGeneralModel,
            AccountPrivacyModel,
            AccountOmemoModel,
            AccountOpenPGPModel,
            AccountOpenPGPSecretModel,
            AccountConnectionModel,
            AccountArchivingModel,
            AccountAdvancedModel,
            LoginModel,
            HostnameModel,
        ]

        self.register_events(
            [
                ("account-created", ged.GUI1, self._on_account_created),
                ("account-removed", ged.GUI1, self._on_account_removed),
            ]
        )

        self._add_app_models()

    def _on_account_created(self, event: AccountCreated) -> None:
        self.add_account(event.account)

    def _on_account_removed(self, event: AccountRemoved) -> None:
        self._account_models.pop(event.account, None)

        for i in reversed(range(len(self._models))):
            model = self._models.get_item(i)
            if model.account == event.account:  # type: ignore
                self._models.remove(i)

    def _add_app_models(self) -> None:
        for model_cls in self._app_model_classes:
            model = model_cls()
            self._app_models[model.name] = model
            self._models.append(model)

    def add_account(self, account: str) -> None:
        for model_cls in self._account_model_classes:
            model = model_cls(account)
            self._account_models[account][model.name] = model
            self._models.append(model)

    def get_flat_model(self) -> Gtk.FlattenListModel:
        return self._flattened_model

    def get_single_model(self, name: str, account: str | None = None) -> Gio.ListStore:
        if account is None:
            return self._app_models[name]
        return self._account_models[account][name]


class AccountGeneralModel(Gio.ListStore):
    name = "account-general"

    def __init__(self, account: str) -> None:
        super().__init__(item_type=SettingGObj)

        self.account = account

        settings = [
            SettingGObj(
                SettingKind.ENTRY,
                _("Label"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="account_label",
                desc=_("Add a label to distinguish accounts in Gajim"),
            ),
            SettingGObj(
                SettingKind.DROPDOWN,
                _("Default Workspace"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="default_workspace",
                desc=_("Chats from this account will use this workspace by default"),
            ),
            SettingGObj(
                SettingKind.COLOR,
                _("Color"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="account_color",
                desc=_("Recognize your account by color"),
            ),
            SettingGObj(
                SettingKind.SUBPAGE,
                _("Login"),
                SettingType.DIALOG,
                account=account,
                desc=_("Change your account’s password, etc."),
                bind="account::anonymous_auth",
                inverted=True,
                props_={"subpage": f"{account}-general-login"},
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Connect on startup"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="autoconnect",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Global Status"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="sync_with_global_status",
                desc=_("Synchronize the status of all accounts"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Remember Last Status"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="restore_last_status",
                desc=_("Restore status and status message of your last session"),
            ),
        ]
        for setting in settings:
            self.append(setting)


class AccountPrivacyModel(Gio.ListStore):
    name = "account-privacy"

    def __init__(self, account: str) -> None:
        super().__init__(item_type=SettingGObj)

        self.account = account

        param = ExportHistoryParam(account=account, jid=None)

        settings = [
            SettingGObj(
                SettingKind.DROPDOWN,
                _("Default Encryption"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="encryption_default",
                desc=_(
                    "Encryption method to use unless overridden on a per-contact basis"
                ),
            ),
            SettingGObj(
                "send-idle-time",
                _("Idle Time"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="send_idle_time",
                desc=_("Disclose the time of your last activity"),
            ),
            SettingGObj(
                "send-os-info",
                _("Operating System"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="send_os_info",
                desc=_(
                    "Disclose information about the operating system you currently use"
                ),
            ),
            SettingGObj(
                "publish-tune",
                _("Media Playback"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="publish_tune",
                desc=_(
                    "Disclose information about media that is "
                    "currently being played on your system."
                ),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Ignore Unknown Contacts"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="ignore_unknown_contacts",
                desc=_("Ignore everything from contacts not in your contact list"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Send Message Receipts"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="answer_receipts",
                desc=_("Tell your contacts if you received a message"),
            ),
            SettingGObj(
                "send-chat-state-indicator",
                _("Send Chat Indicators"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="send_chatstate_default",
                desc=_("Default for chats (e.g. Contact is typing)"),
            ),
            SettingGObj(
                "send-group-chat-state-indicator",
                _("Send Chat Indicators in Group Chats"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="gc_send_chatstate_default",
                desc=_("Default for group chats (e.g. Contact is typing)"),
            ),
            SettingGObj(
                "send-read-marker",
                _("Read Receipts"),
                SettingType.VALUE,
                account=account,
                value=app.settings.get_account_setting(account, "send_marker_default"),
                desc=_("Default for chats and private group chats"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Update Timezone"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="update_timezone",
                desc=_("Update your profile's timezone automatically"),
            ),
            SettingGObj(
                "sync-muc-blocks",
                _("Sync Group Chat Block List"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="sync_muc_blocks",
                desc=_("Synchronize group chat block list with other devices"),
            ),
            SettingGObj(
                SettingKind.DROPDOWN,
                _("Keep Chat History"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="chat_history_max_age",
                desc=_("How long Gajim should keep your chat history"),
            ),
            SettingGObj(
                SettingKind.ACTION,
                _("Export Chat History"),
                SettingType.ACTION,
                account=account,
                value="app.export-history",
                desc=_("Export your chat history from Gajim"),
                props_={"variant": param.to_variant()},
            ),
        ]

        for setting in settings:
            self.append(setting)


class AccountOmemoModel(Gio.ListStore):
    name = "account-omemo-settings"

    def __init__(self, account: str) -> None:
        super().__init__(item_type=SettingGObj)

        self.account = account

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Blind Trust"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="omemo_blind_trust",
                desc=_("Blindly trust new devices until you verify them"),
            )
        ]

        for setting in settings:
            self.append(setting)


class AccountOpenPGPModel(Gio.ListStore):
    name = "account-openpgp-settings"

    def __init__(self, account: str) -> None:
        super().__init__(item_type=SettingGObj)

        self.account = account

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Blind Trust"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="openpgp_blind_trust",
                desc=_("Blindly trust new devices"),
            ),
        ]

        for setting in settings:
            self.append(setting)


class AccountOpenPGPSecretModel(Gio.ListStore):
    name = "account-openpgp-secret"

    def __init__(self, account: str) -> None:
        super().__init__(item_type=SettingGObj)

        self.account = account

        settings = [
            SettingGObj(
                "backup-secret-key",
                _("Backup Secret Key"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="openpgp_backup_secret_key",
                desc=_("Stores the secret key encrypted on the server"),
            ),
            SettingGObj(
                SettingKind.DIALOG,
                _("Export & Share Secret Key"),
                SettingType.DIALOG,
                account=account,
                props_={"dialog": "OpenPGPSecret"},
            ),
        ]

        for setting in settings:
            self.append(setting)


class AccountConnectionModel(Gio.ListStore):
    name = "account-connection"

    def __init__(self, account: str) -> None:
        super().__init__(item_type=SettingGObj)

        self.account = account

        settings = [
            SettingGObj(
                SettingKind.SUBPAGE,
                _("Details"),
                SettingType.DIALOG,
                account=account,
                props_={"subpage": f"{self.account}-connection-details"},
            ),
            SettingGObj(
                SettingKind.SUBPAGE,
                _("Certificate"),
                SettingType.DIALOG,
                account=account,
                desc=_("Details about the certificate used by this connection"),
                props_={"subpage": f"{self.account}-connection-certificate"},
            ),
            SettingGObj(
                SettingKind.SUBPAGE,
                _("Hostname"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="use_custom_host",
                desc=_("Manually set the hostname for the server"),
                props_={"subpage": f"{self.account}-connection-hostname"},
            ),
            SettingGObj(
                "proxy",
                _("Proxy"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="proxy",
                name="proxy",
            ),
            SettingGObj(
                SettingKind.ENTRY,
                _("Resource"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="resource",
                desc=_(
                    "Identifier for this device. "
                    "Don’t change this unless you know what you are doing."
                ),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Use Unencrypted Connection"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="use_plain_connection",
                desc=_("Use an unencrypted connection to the server"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Confirm Unencrypted Connection"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="confirm_unencrypted_connection",
                desc=_("Ask before connecting unencrypted"),
            ),
        ]

        for setting in settings:
            self.append(setting)


class AccountArchivingModel(Gio.ListStore):
    name = "account-archiving"

    def __init__(self, account: str) -> None:
        super().__init__(item_type=SettingGObj)

        self.account = account

        settings = [
            SettingGObj(
                "sync-history",
                _("Synchronize History…"),
                SettingType.VALUE,
                account=account,
                value=None,
            ),
        ]

        for setting in settings:
            self.append(setting)


class AccountAdvancedModel(Gio.ListStore):
    name = "account-advanced"

    def __init__(self, account: str) -> None:
        super().__init__(item_type=SettingGObj)

        self.account = account

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Contact Information"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="request_user_data",
                desc=_("Request contact information (Tune, Location)"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Accept all Contact Requests"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="autoauth",
                desc=_("Automatically accept all contact requests"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Security Labels"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="enable_security_labels",
                desc=_(
                    "Show labels describing confidentiality of "
                    "messages, if the server supports XEP-0258"
                ),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Synchronize joined group chats"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="autojoin_sync",
                desc=_("Synchronize joined group chats with other devices."),
            ),
        ]

        for setting in settings:
            self.append(setting)


class LoginModel(Gio.ListStore):
    name = "login"

    def __init__(self, account: str) -> None:
        super().__init__(item_type=SettingGObj)

        self.account = account

        settings = [
            SettingGObj(
                "save-password",
                _("Save Password"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="savepass",
            ),
            SettingGObj(
                "change-password",
                _("Change Password"),
                SettingType.DIALOG,
                account=account,
                props_={"dialog": "ChangePassword"},
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Use GSSAPI"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="enable_gssapi",
            ),
        ]

        for setting in settings:
            self.append(setting)


class HostnameModel(Gio.ListStore):
    name = "hostname"

    def __init__(self, account: str) -> None:
        super().__init__(item_type=SettingGObj)

        self.account = account

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Enable"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="use_custom_host",
            ),
            SettingGObj(
                SettingKind.ENTRY,
                _("Hostname"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="custom_host",
                bind="account::use_custom_host",
            ),
            SettingGObj(
                SettingKind.SPIN,
                _("Port"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="custom_port",
                bind="account::use_custom_host",
                props_={"range_": SpinRange(0, 65535, 1, 0)},
            ),
            SettingGObj(
                SettingKind.DROPDOWN,
                _("Type"),
                SettingType.ACCOUNT_CONFIG,
                account=account,
                value="custom_type",
                bind="account::use_custom_host",
            ),
        ]

        for setting in settings:
            self.append(setting)


class WindowBehaviourModel(Gio.ListStore):
    name = "window-behaviour"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.DROPDOWN,
                _("Show on Startup"),
                SettingType.CONFIG,
                value="show_main_window_on_startup",
                desc=_("Show window when starting Gajim"),
            ),
            SettingGObj(
                SettingKind.DROPDOWN,
                _("Action on Close"),
                SettingType.CONFIG,
                value="action_on_close",
                desc=_("Action when closing Gajim’s window"),
            ),
            SettingGObj(
                "show-in-taskbar",
                _("Show in Taskbar"),
                SettingType.CONFIG,
                value="show_in_taskbar",
                desc=_("Show window in the taskbar"),
            ),
            SettingGObj(
                "show-header-bar",
                _("Show Title Bar"),
                SettingType.CONFIG,
                value="show_header_bar",
                desc=_("Show the window’s title bar"),
            ),
        ]

        for setting in settings:
            self.append(setting)


class PluginSettingsModel(Gio.ListStore):
    name = "plugin-settings"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Check for updates"),
                SettingType.CONFIG,
                value="plugins_update_check",
                desc=_("Check for updates periodically"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Update automatically"),
                SettingType.CONFIG,
                value="plugins_auto_update",
                desc=_("Update plugins automatically"),
                bind="plugins_update_check",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Notify after update"),
                SettingType.CONFIG,
                value="plugins_notify_after_update",
                desc=_("Notify me when the automatic update was successful"),
                bind="plugins_auto_update",
            ),
        ]

        for setting in settings:
            self.append(setting)


class GeneralModel(Gio.ListStore):
    name = "general"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        speller_desc = None
        if not app.is_installed("SPELLING"):
            speller_desc = _("Needs libspelling to be installed")

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Close with Escape"),
                SettingType.CONFIG,
                value="escape_key_closes",
                desc=_("Close a chat by pressing the Escape key"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Show Send Message Button"),
                SettingType.CONFIG,
                value="show_send_message_button",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Show Voice Message Button"),
                SettingType.CONFIG,
                value="show_voice_message_button",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Send Messages with Control+Enter"),
                SettingType.CONFIG,
                value="send_on_ctrl_enter",
            ),
            SettingGObj(
                "use-speller",
                _("Spell Checking"),
                SettingType.CONFIG,
                value="use_speller",
                desc=speller_desc,
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Emoji Shortcodes"),
                SettingType.CONFIG,
                value="enable_emoji_shortcodes",
                desc=_("Show suggestions for shortcodes, e.g. :+1:"),
            ),
        ]

        for setting in settings:
            self.append(setting)


class ChatsModel(Gio.ListStore):
    name = "chats"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Message Receipts (✔)"),
                SettingType.CONFIG,
                value="positive_184_ack",
                desc=_("Add a checkmark to received messages"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Show Status Changes"),
                SettingType.CONFIG,
                value="print_status_in_chats",
                desc=_('For example: "Julia is now online"'),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Show Link Preview"),
                SettingType.CONFIG,
                value="enable_link_preview_default",
                desc=_("Default for new chats"),
            ),
        ]

        for setting in settings:
            self.append(setting)


class GroupChatsModel(Gio.ListStore):
    name = "group-chats"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.DROPDOWN,
                _("Default Sync Threshold"),
                SettingType.CONFIG,
                value="gc_sync_threshold_public_default",
                desc=_("Default for new public group chats"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Direct Messages"),
                SettingType.CONFIG,
                value="muc_prefer_direct_msg",
                desc=_("Prefer direct messages in private group chats"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Sort Participant List by Status"),
                SettingType.CONFIG,
                value="sort_by_show_in_muc",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Status Messages in Participants List"),
                SettingType.CONFIG,
                value="show_status_msgs_in_roster",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Show Subject on Join"),
                SettingType.CONFIG,
                value="show_subject_on_join",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Show Joined / Left"),
                SettingType.CONFIG,
                value="gc_print_join_left_default",
                desc=_("Default for new group chats"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Show Status Changes"),
                SettingType.CONFIG,
                value="gc_print_status_default",
                desc=_("Default for new group chats"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Show Link Preview"),
                SettingType.CONFIG,
                value="gc_enable_link_preview_default",
                desc=_("Default for new group chats"),
            ),
        ]

        for setting in settings:
            self.append(setting)


class FilePreviewModel(Gio.ListStore):
    name = "file-preview"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.DROPDOWN,
                _("File Size Limit"),
                SettingType.CONFIG,
                value="preview_max_file_size",
                desc=_("Maximum file size for preview downloads"),
            ),
            SettingGObj(
                SettingKind.SPIN,
                _("Preview Size"),
                SettingType.CONFIG,
                value="preview_size",
                desc=_("Size of preview images in pixels"),
                props_={"range_": SpinRange(100, 1000, 50, 0)},
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Preview in Public Group Chats"),
                SettingType.CONFIG,
                value="preview_anonymous_muc",
                desc=_(
                    "Show previews automatically in public "
                    "group chats (may disclose your data)"
                ),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Preview all Image URLs"),
                SettingType.CONFIG,
                value="preview_allow_all_images",
                desc=_("Show previews for any URLs containing images (may be unsafe)"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("HTTPS Verification"),
                SettingType.CONFIG,
                value="preview_verify_https",
                desc=_(
                    "Whether to check for a valid certificate before "
                    "downloading (not safe to disable)"
                ),
            ),
        ]

        for setting in settings:
            self.append(setting)


class SystemNotificationsModel(Gio.ListStore):
    name = "system-notifications"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("System Tray Icon"),
                SettingType.CONFIG,
                value="show_trayicon",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("System Tray Notifications"),
                SettingType.CONFIG,
                value="trayicon_notification_on_events",
                desc=_("Show notifications on the system tray icon"),
                bind="show_trayicon",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("System Notifications"),
                SettingType.CONFIG,
                value="show_notifications",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("System Notifications When Away"),
                SettingType.CONFIG,
                value="show_notifications_away",
                desc=_("Show notifications even if you are Away, Busy, etc."),
                bind="show_notifications",
            ),
        ]

        for setting in settings:
            self.append(setting)


class NotificationsChatsModel(Gio.ListStore):
    name = "notifications-chats"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Reactions"),
                SettingType.CONFIG,
                value="notify_on_reaction_default",
                desc=_("Notify me when someone reacts to my message in a chat"),
            ),
        ]

        for setting in settings:
            self.append(setting)


class NotificationsGroupChatsModel(Gio.ListStore):
    name = "notifications-group-chats"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Reactions"),
                SettingType.CONFIG,
                value="gc_notify_on_reaction_default",
                desc=_("Notify me when someone reacts to my message in a group chat"),
            ),
        ]

        for setting in settings:
            self.append(setting)


class SoundsModel(Gio.ListStore):
    name = "sounds"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                "enable-sounds",
                _("Play Sounds"),
                SettingType.CONFIG,
                value="sounds_on",
                desc=_("Play sounds to notify about events"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Sounds When Away"),
                SettingType.CONFIG,
                value="sounddnd",
                desc=_("Play sounds even when you are Away, Busy, etc."),
                bind="sounds_on",
            ),
        ]

        for setting in settings:
            self.append(setting)


class StatusMessageModel(Gio.ListStore):
    name = "status-message"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Sign In"),
                SettingType.CONFIG,
                value="ask_online_status",
            ),
        ]

        for setting in settings:
            self.append(setting)


class AutomaticStatusModel(Gio.ListStore):
    name = "automatic-status"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.SUBPAGE,
                _("Auto Away"),
                SettingType.CONFIG,
                value="autoaway",
                desc=_('Change your status to "Away" after a certain amount of time'),
                props_={"subpage": "auto-away"},
            ),
            SettingGObj(
                SettingKind.SUBPAGE,
                _("Auto Not Available"),
                SettingType.CONFIG,
                value="autoxa",
                desc=_(
                    'Change your status to "Not Available" after a '
                    "certain amount of time"
                ),
                props_={"subpage": "auto-extended-away"},
            ),
        ]

        for setting in settings:
            self.append(setting)


class AutoAwayModel(Gio.ListStore):
    name = "auto-away"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.SWITCH, _("Auto Away"), SettingType.CONFIG, value="autoaway"
            ),
            SettingGObj(
                SettingKind.SPIN,
                _("Time Until Away"),
                SettingType.CONFIG,
                value="autoawaytime",
                desc=_("Minutes until your status gets changed"),
                props_={"range_": SpinRange(1, 720, 1, 0)},
                bind="autoaway",
            ),
            SettingGObj(
                SettingKind.ENTRY,
                _("Status Message"),
                SettingType.CONFIG,
                value="autoaway_message",
                bind="autoaway",
            ),
        ]

        for setting in settings:
            self.append(setting)


class AutoExtendedAwayModel(Gio.ListStore):
    name = "auto-extended-away"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.SWITCH,
                _("Auto Not Available"),
                SettingType.CONFIG,
                value="autoxa",
            ),
            SettingGObj(
                SettingKind.SPIN,
                _("Time Until Not Available"),
                SettingType.CONFIG,
                value="autoxatime",
                desc=_("Minutes until your status gets changed"),
                props_={"range_": SpinRange(1, 720, 1, 0)},
                bind="autoxa",
            ),
            SettingGObj(
                SettingKind.ENTRY,
                _("Status Message"),
                SettingType.CONFIG,
                value="autoxa_message",
                bind="autoxa",
            ),
        ]

        for setting in settings:
            self.append(setting)


class ThemesModel(Gio.ListStore):
    name = "themes"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                "app-font-size",
                _("User Interface Font Size"),
                SettingType.CONFIG,
                value="app_font_size",
                props_={"range_": SpinRange(0.5, 3.0, 0.10, 2)},
            ),
            SettingGObj(
                "dark-theme",
                _("Dark Theme"),
                SettingType.CONFIG,
                value="dark_theme",
            ),
            SettingGObj(
                "roster-theme",
                _("Theme"),
                SettingType.CONFIG,
                value="roster_theme",
                name="roster_theme",
            ),
        ]

        for setting in settings:
            self.append(setting)


class AudioModel(Gio.ListStore):
    name = "audio"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                SettingKind.DROPDOWN,
                _("Audio Input Device"),
                SettingType.CONFIG,
                value="audio_input_device",
                desc=_("Select your audio input (e.g. microphone)"),
            ),
        ]

        for setting in settings:
            self.append(setting)


class MiscellaneousModel(Gio.ListStore):
    name = "miscellaneous"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                "global-proxy",
                _("Global Proxy"),
                SettingType.CONFIG,
                value="global_proxy",
                name="global_proxy",
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("Use System Keyring"),
                SettingType.CONFIG,
                value="use_keyring",
                desc=_("Use your system’s keyring to store passwords"),
            ),
        ]

        if sys.platform not in ("win32", "darwin") and package_version(
            "keyring>=23.8.1"
        ):
            settings.append(
                SettingGObj(
                    SettingKind.SWITCH,
                    _("Enable KeepassXC Integration"),
                    SettingType.CONFIG,
                    value="enable_keepassxc_integration",
                )
            )

        if sys.platform in ("win32", "darwin"):
            settings.append(
                SettingGObj(
                    SettingKind.SWITCH,
                    _("Check For Updates"),
                    SettingType.CONFIG,
                    value="check_for_update",
                    desc=_("Check for Gajim updates periodically"),
                )
            )

        settings.append(
            SettingGObj(
                "reset-hints",
                _("Reset Hints"),
                SettingType.VALUE,
                value=None,
                desc=_("This will reset all introduction hints"),
            ),
        )

        settings.append(
            SettingGObj(
                "purge-chat-history",
                _("Purge Chat History"),
                SettingType.VALUE,
                value=None,
                desc=_("This will purge all locally stored chat history"),
            ),
        )

        for setting in settings:
            self.append(setting)


class AdvancedModel(Gio.ListStore):
    name = "advanced"

    def __init__(self) -> None:
        super().__init__(item_type=SettingGObj)

        settings = [
            SettingGObj(
                "debug-logging",
                _("Debug Logging"),
                SettingType.VALUE,
                value=app.get_debug_mode(),
                desc=_("Let Gajim generate a log to trace errors (restart required)"),
            ),
            SettingGObj(
                "debug-console",
                _("Debug Console"),
                SettingType.VALUE,
                value=None,
                desc=_("Show Gajim's internal logs and XML protocol data"),
            ),
            SettingGObj(
                SettingKind.SWITCH,
                _("D-Bus Interface"),
                SettingType.CONFIG,
                value="remote_control",
                desc=_(
                    "Allow Gajim to broadcast useful information via "
                    "D-Bus. It also allows other applications to "
                    "control Gajim remotely."
                ),
            ),
            SettingGObj(
                "advanced-config-editor",
                _("Advanced Configuration Editor"),
                SettingType.VALUE,
                value=None,
                desc=_("Please use these settings with caution!"),
            ),
        ]

        for setting in settings:
            self.append(setting)
