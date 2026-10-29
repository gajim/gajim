# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import Literal
from typing import overload

import itertools
import uuid
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from dataclasses import field
from enum import IntEnum

from gajim.common.i18n import _
from gajim.common.settings.types import AccountBoolSettings
from gajim.common.settings.types import AccountIntSettings
from gajim.common.settings.types import AccountStringSettings
from gajim.common.settings.types import AppBoolSettings
from gajim.common.settings.types import AppFloatSettings
from gajim.common.settings.types import AppIntSettings
from gajim.common.settings.types import AppStringSettings
from gajim.common.settings.types import ContactBoolSettings
from gajim.common.settings.types import ContactStringSettings
from gajim.common.settings.types import GroupChatBoolSettings
from gajim.common.settings.types import GroupChatStringSettings
from gajim.common.settings.types import PluginBoolSettings
from gajim.common.settings.types import ProxyBoolSettings
from gajim.common.settings.types import ProxyIntSettings
from gajim.common.settings.types import ProxyStringSettings
from gajim.common.settings.types import WorkspaceSettings
from gajim.common.settings.types import WorkspaceStringListSettings
from gajim.common.settings.types import WorkspaceStringSettings

DarkThemeEnum = {
    0: _("Disabled"),
    1: _("Enabled"),
    2: _("System"),
}

SyncThresholdEnum = {
    -1: _("No Sync"),
    1: _("1 Day"),
    2: _("2 Days"),
    7: _("1 Week"),
    30: _("1 Month"),
    0: _("No Threshold"),
}

PreviewMaxFileSizeEnum = {
    0: _("No automatic preview"),
    262144: "256 KiB",
    524288: "512 KiB",
    1048576: "1 MiB",
    5242880: "5 MiB",
    10485760: "10 MiB",
    26214400: "25 MiB",
}


WindowStartupEnum = {
    "always": _("Always"),
    "never": _("Never"),
    "last_state": _("Restore last state"),
}


CloseActionEnum = {
    "hide": _("Hide"),
    "minimize": _("Minimize"),
    "quit": _("Quit"),
}


MaxHistoryAgeEnum = {
    -1: _("Forever"),
    0: _("Until Gajim is Closed"),
    86400: _("1 Day"),
    604800: _("1 Week"),
    2629743: _("1 Month"),
    7889229: _("3 Months"),
    15778458: _("6 Months"),
    31556926: _("1 Year"),
}

ConnectionTypeEnum = {
    "START TLS": "START TLS",
    "DIRECT TLS": "DIRECT TLS",
    "PLAIN": "PLAIN",
}


EncryptionEnum = {
    "": _("Unencrypted"),
    "OMEMO": "OMEMO",
    "OpenPGP": "OpenPGP",
    "PGP": "PGP",
}

FileTransferMethodEnum = {
    "httpupload": _("Upload Files"),
    "jingle": _("Send Files Directly"),
}


SendChatStateEnum = {
    "disabled": _("Disabled"),
    "composing_only": _("Composing Only"),
    "all": _("All Chat States"),
}


class SettingType(IntEnum):
    APP = 0
    ACCOUNT = 1
    CONTACT = 2
    GROUPCHAT = 3
    PLUGIN = 4
    PROXY = 5
    WORKSPACE = 6


@dataclass(slots=True, frozen=True)
class SettingRange:
    lower: float
    upper: float
    step: float
    digit: int

    def contains(self, value: float | int) -> bool:
        return self.lower <= value <= self.upper


@dataclass(kw_only=True)
class BaseSetting:
    key: str
    type: SettingType
    label: str = ""
    desc: str = ""
    bind: str = ""
    default: Any
    context_default: bool = False
    enum: dict[Any, str] | None = None

    def validate_value(self, value: Any) -> Any:
        if self.enum is not None:
            if value not in self.enum:
                raise ValueError(f"Value {value} not allowed for {self.key}")

        if type(self.default) is not type(value):
            raise ValueError(f"Invalid type {type(self.default)}")

        return value


@dataclass(kw_only=True)
class IntSetting(BaseSetting):
    default: int
    range: SettingRange | None = None

    def validate_value(self, value: Any) -> int:
        BaseSetting.validate_value(self, value)
        if self.range is not None:
            if not self.range.contains(value):
                raise ValueError(f"{value} not in allowed range")

        return value


@dataclass(kw_only=True)
class FloatSetting(BaseSetting):
    default: float
    range: SettingRange | None = None

    def validate_value(self, value: Any) -> float:
        BaseSetting.validate_value(self, value)
        if self.range is not None:
            if not self.range.contains(value):
                raise ValueError(f"{value} not in allowed range")

        return value


@dataclass(kw_only=True)
class BooleanSetting(BaseSetting):
    default: int
    inverted: bool = False


@dataclass(kw_only=True)
class StringSetting(BaseSetting):
    default: str = ""


@dataclass(kw_only=True)
class StringListSetting(BaseSetting):
    default: list[str] = field(default_factory=list[str])


SettingT = (
    BooleanSetting | IntSetting | FloatSetting | StringSetting | StringListSetting
)


_APP_SETTINGS: list[SettingT] = [
    BooleanSetting(key="always_english_wikipedia", type=SettingType.APP, default=False),
    BooleanSetting(key="always_english_wiktionary", type=SettingType.APP, default=True),
    BooleanSetting(
        key="ask_online_status", type=SettingType.APP, default=False, label=_("Sign In")
    ),
    BooleanSetting(
        key="autoaway",
        type=SettingType.APP,
        default=True,
        label=_("Auto Away"),
        desc=_('Change your status to "Away" after a certain amount of time'),
    ),
    BooleanSetting(
        key="autoxa",
        type=SettingType.APP,
        default=True,
        label=_("Auto Not Available"),
        desc=_('Change your status to "Not Available" after a certain amount of time'),
    ),
    BooleanSetting(
        key="chat_merge_consecutive_nickname",
        type=SettingType.APP,
        default=True,
        desc=_(
            "Show message meta data (avatar, nickname, timestamp) only once, "
            "if there are multiple messages from the same sender within a "
            "specific timespan."
        ),
    ),
    BooleanSetting(
        key="check_for_update",
        type=SettingType.APP,
        default=True,
        label=_("Check For Updates"),
        desc=_("Check for Gajim updates periodically"),
    ),
    BooleanSetting(
        key="confirm_close_muc",
        type=SettingType.APP,
        default=True,
        desc=_("Ask before closing a group chat tab/window."),
    ),
    BooleanSetting(
        key="confirm_on_window_delete",
        type=SettingType.APP,
        default=True,
        desc=_("Ask before quitting when Gajim’s window is closed"),
    ),
    BooleanSetting(
        key="dev_force_bookmark_2",
        type=SettingType.APP,
        default=False,
        desc=_("Force Bookmark 2 usage"),
    ),
    BooleanSetting(
        key="enable_emoji_shortcodes",
        type=SettingType.APP,
        default=True,
        label=_("Emoji Shortcodes"),
        desc=_("Show suggestions for shortcodes, e.g. :+1:"),
    ),
    BooleanSetting(
        key="enable_keepassxc_integration",
        type=SettingType.APP,
        default=False,
        label=_("Enable KeepassXC Integration"),
    ),
    BooleanSetting(
        key="enable_link_preview_default",
        type=SettingType.APP,
        default=True,
        label=_("Show Link Preview"),
        desc=_("Default for new chats"),
    ),
    BooleanSetting(
        key="escape_key_closes",
        type=SettingType.APP,
        default=False,
        label=_("Close with Escape"),
        desc=_("Close a chat by pressing the Escape key"),
    ),
    BooleanSetting(
        key="gc_enable_link_preview_default",
        type=SettingType.APP,
        default=True,
        label=_("Show Link Preview"),
        desc=_("Default for new group chats"),
    ),
    BooleanSetting(
        key="gc_notify_on_all_messages_private_default",
        type=SettingType.APP,
        default=True,
    ),
    BooleanSetting(
        key="gc_notify_on_all_messages_public_default",
        type=SettingType.APP,
        default=False,
    ),
    BooleanSetting(
        key="gc_notify_on_reaction_default",
        type=SettingType.APP,
        default=True,
        label=_("Reactions"),
        desc=_("Notify me when someone reacts to my message in a group chat"),
    ),
    BooleanSetting(
        key="gc_print_join_left_default",
        type=SettingType.APP,
        default=False,
        label=_("Show Joined / Left"),
        desc=_("Default for new group chats"),
    ),
    BooleanSetting(
        key="gc_print_status_default",
        type=SettingType.APP,
        default=False,
        label=_("Show Status Changes"),
        desc=_("Default for new group chats"),
    ),
    BooleanSetting(
        key="hide_groupchat_occupants_list", type=SettingType.APP, default=False
    ),
    BooleanSetting(
        key="ignore_incoming_attention",
        type=SettingType.APP,
        default=False,
        desc=_('If enabled, Gajim will ignore incoming attention requests ("wizz").'),
    ),
    BooleanSetting(key="is_window_visible", type=SettingType.APP, default=True),
    BooleanSetting(
        key="muc_prefer_direct_msg",
        type=SettingType.APP,
        default=True,
        label=_("Direct Messages"),
        desc=_("Prefer direct messages in private group chats"),
    ),
    BooleanSetting(
        key="notification_preview_message",
        type=SettingType.APP,
        default=True,
        desc=_("Preview new messages in notification popup?"),
    ),
    BooleanSetting(
        key="notify_on_all_muc_messages", type=SettingType.APP, default=False
    ),
    BooleanSetting(key="notify_on_file_complete", type=SettingType.APP, default=True),
    BooleanSetting(
        key="notify_on_reaction_default",
        type=SettingType.APP,
        default=True,
        label=_("Reactions"),
        desc=_("Notify me when someone reacts to my message in a chat"),
    ),
    BooleanSetting(
        key="plugins_auto_update",
        type=SettingType.APP,
        default=False,
        label=_("Update automatically"),
        desc=_("Update plugins automatically"),
    ),
    BooleanSetting(
        key="plugins_notify_after_update",
        type=SettingType.APP,
        default=True,
        label=_("Notify after update"),
        desc=_("Notify me when the automatic update was successful"),
    ),
    BooleanSetting(
        key="plugins_repository_enabled",
        type=SettingType.APP,
        default=True,
        desc=_("If enabled, Gajim offers to download plugins hosted on gajim.org"),
    ),
    BooleanSetting(
        key="plugins_update_check",
        type=SettingType.APP,
        default=True,
        label=_("Check for updates"),
        desc=_("Check for updates periodically"),
    ),
    BooleanSetting(
        key="positive_184_ack",
        type=SettingType.APP,
        default=False,
        label=_("Message Receipts (✔)"),
        desc=_("Add a checkmark to received messages"),
    ),
    BooleanSetting(
        key="preview_allow_all_images",
        type=SettingType.APP,
        default=False,
        label=_("Preview all Image URLs"),
        desc=_("Show previews for any URLs containing images (may be unsafe)"),
    ),
    BooleanSetting(
        key="preview_anonymous_muc",
        type=SettingType.APP,
        default=False,
        label=_("Preview in Public Group Chats"),
        desc=_(
            "Show previews automatically in public group chats (may disclose your data)"
        ),
    ),
    BooleanSetting(
        key="preview_verify_https",
        type=SettingType.APP,
        default=True,
        label=_("HTTPS Verification"),
        desc=_(
            "Whether to check for a valid certificate before "
            "downloading (not safe to disable)"
        ),
    ),
    BooleanSetting(
        key="print_status_in_chats",
        type=SettingType.APP,
        default=False,
        label=_("Show Status Changes"),
        desc=_('For example: "Julia is now online"'),
    ),
    BooleanSetting(
        key="remote_control",
        type=SettingType.APP,
        default=False,
        label=_("D-Bus Interface"),
        desc=_(
            "Allow Gajim to broadcast useful information via "
            "D-Bus. It also allows other applications to "
            "control Gajim remotely."
        ),
    ),
    BooleanSetting(
        key="send_on_ctrl_enter",
        type=SettingType.APP,
        default=False,
        label=_("Send Messages with Control+Enter"),
    ),
    BooleanSetting(
        key="show_header_bar",
        type=SettingType.APP,
        default=True,
        label=_("Show Title Bar"),
        desc=_("Show the window’s title bar"),
    ),
    BooleanSetting(key="show_help_start_chat", type=SettingType.APP, default=True),
    BooleanSetting(
        key="show_in_taskbar",
        type=SettingType.APP,
        default=True,
        label=_("Show in Taskbar"),
        desc=_("Show window in the taskbar"),
    ),
    BooleanSetting(
        key="show_notifications",
        type=SettingType.APP,
        default=True,
        label=_("System Notifications"),
    ),
    BooleanSetting(
        key="show_notifications_away",
        type=SettingType.APP,
        default=False,
        label=_("System Notifications When Away"),
        desc=_("Show notifications even if you are Away, Busy, etc."),
    ),
    BooleanSetting(
        key="show_send_message_button",
        type=SettingType.APP,
        default=False,
        label=_("Show Send Message Button"),
    ),
    BooleanSetting(
        key="show_status_msgs_in_roster",
        type=SettingType.APP,
        default=True,
        label=_("Status Messages in Participants List"),
    ),
    BooleanSetting(
        key="show_subject_on_join",
        type=SettingType.APP,
        default=True,
        label=_("Show Subject on Join"),
    ),
    BooleanSetting(
        key="show_trayicon",
        type=SettingType.APP,
        default=True,
        label=_("System Tray Icon"),
    ),
    BooleanSetting(
        key="show_voice_message_button",
        type=SettingType.APP,
        default=True,
        label=_("Show Voice Message Button"),
    ),
    BooleanSetting(
        key="sort_by_show_in_muc",
        type=SettingType.APP,
        default=False,
        label=_("Sort Participant List by Status"),
    ),
    BooleanSetting(
        key="sort_by_show_in_start_chat", type=SettingType.APP, default=True
    ),
    BooleanSetting(
        key="sounddnd",
        type=SettingType.APP,
        default=False,
        label=_("Sounds When Away"),
        desc=_("Play sounds even when you are Away, Busy, etc."),
    ),
    BooleanSetting(
        key="sounds_on",
        type=SettingType.APP,
        default=True,
        label=_("Play Sounds"),
        desc=_("Play sounds to notify about events"),
    ),
    BooleanSetting(
        key="trayicon_notification_on_events",
        type=SettingType.APP,
        default=True,
        label=_("System Tray Notifications"),
        desc=_("Show notifications on the system tray icon"),
    ),
    BooleanSetting(
        key="use_http2",
        type=SettingType.APP,
        desc=_("Use HTTP2 for requests if there is server support"),
        default=False,
    ),
    BooleanSetting(
        key="use_keyring",
        type=SettingType.APP,
        default=True,
        label=_("Use System Keyring"),
        desc=_("Use your system’s keyring to store passwords"),
    ),
    BooleanSetting(
        key="use_kib_mib",
        type=SettingType.APP,
        default=False,
        desc=_("IEC standard says KiB = 1024 bytes, KB = 1000 bytes."),
    ),
    BooleanSetting(
        key="use_speller", type=SettingType.APP, default=True, label=_("Spell Checking")
    ),
    BooleanSetting(
        key="use_stun_server",
        type=SettingType.APP,
        default=False,
        desc=_(
            "If enabled, Gajim will try to use a STUN server when using Jingle."
            ' The one in "stun_server" option, or the one given by '
            "the XMPP server."
        ),
    ),
    BooleanSetting(
        key="use_urgency_hint",
        type=SettingType.APP,
        default=True,
        desc=_(
            "If enabled, Gajim makes the window flash (the default behaviour "
            "in most Window Managers) when holding pending events."
        ),
    ),
    BooleanSetting(key="video_see_self", type=SettingType.APP, default=True),
    FloatSetting(
        key="app_font_size",
        type=SettingType.APP,
        default=1.0,
        range=SettingRange(0.5, 3.0, 0.10, 2),
        label=_("User Interface Font Size"),
    ),
    IntSetting(
        key="audio_input_volume",
        type=SettingType.APP,
        default=50,
        range=SettingRange(0, 100, 1, 0),
    ),
    IntSetting(
        key="audio_output_volume",
        type=SettingType.APP,
        default=50,
        range=SettingRange(0, 100, 1, 0),
    ),
    IntSetting(
        key="autoawaytime",
        type=SettingType.APP,
        default=5,
        label=_("Time Until Away"),
        desc=_("Minutes until your status gets changed"),
    ),
    IntSetting(
        key="autoxatime",
        type=SettingType.APP,
        default=15,
        label=_("Time Until Not Available"),
        desc=_("Minutes until your status gets changed"),
    ),
    IntSetting(key="chat_handle_position", type=SettingType.APP, default=350),
    IntSetting(
        key="dark_theme",
        type=SettingType.APP,
        default=2,
        enum=DarkThemeEnum,
        label=_("Dark Theme"),
    ),
    IntSetting(
        key="file_transfers_port",
        type=SettingType.APP,
        default=28011,
        range=SettingRange(1, 65535, 1, 0),
    ),
    IntSetting(
        key="gc_sync_threshold_private_default",
        type=SettingType.APP,
        default=0,
        enum=SyncThresholdEnum,
    ),
    IntSetting(
        key="gc_sync_threshold_public_default",
        type=SettingType.APP,
        default=1,
        enum=SyncThresholdEnum,
        label=_("Default Sync Threshold"),
        desc=_("Default for new public group chats"),
    ),
    IntSetting(
        key="groupchat_roster_width",
        type=SettingType.APP,
        default=250,
        desc=_("Width of group chat roster in pixel"),
    ),
    IntSetting(key="mainwin_height", type=SettingType.APP, default=500),
    IntSetting(key="mainwin_width", type=SettingType.APP, default=1000),
    IntSetting(
        key="preview_max_file_size",
        type=SettingType.APP,
        default=10485760,
        enum=PreviewMaxFileSizeEnum,
        label=_("File Size Limit"),
        desc=_("Maximum file size for preview downloads"),
    ),
    IntSetting(
        key="preview_size",
        type=SettingType.APP,
        default=400,
        label=_("Preview Size"),
        desc=_("Size of preview images in pixels"),
    ),
    StringSetting(
        key="time_format",
        type=SettingType.APP,
        default="%H:%M",
        desc="https://docs.python.org/3/library/time.html#time.strftime",
    ),
    StringSetting(
        key="action_on_close",
        type=SettingType.APP,
        default="hide",
        enum=CloseActionEnum,
        label=_("Action on Close"),
        desc=_("Action when closing Gajim’s window"),
    ),
    StringSetting(
        key="additional_uri_schemes",
        type=SettingType.APP,
        desc=_(
            "Clickable schemes in addition to the hard-coded list of "
            "IANA-registered ones. Space-separated, lower-case, no colons."
        ),
    ),
    StringSetting(
        key="audio_input_device",
        type=SettingType.APP,
        default="autoaudiosrc ! volume name=gajim_vol",
        label=_("Audio Input Device"),
        desc=_("Select your audio input (e.g. microphone)"),
    ),
    StringSetting(
        key="audio_output_device",
        type=SettingType.APP,
        default="autoaudiosink",
        label=_("Audio Output Device"),
        desc=_("Select an audio output (e.g. speakers, headphones)"),
    ),
    StringSetting(
        key="autoaway_message", type=SettingType.APP, label=_("Status Message")
    ),
    StringSetting(
        key="autoxa_message", type=SettingType.APP, label=_("Status Message")
    ),
    StringSetting(
        key="confirm_block",
        type=SettingType.APP,
        desc=_(
            "Show a confirmation dialog to block a contact? Empty string "
            "means never show the dialog."
        ),
    ),
    StringSetting(
        key="date_format",
        type=SettingType.APP,
        default="%x",
        desc="https://docs.python.org/3/library/time.html#time.strftime",
    ),
    StringSetting(
        key="date_time_format",
        type=SettingType.APP,
        default="%c",
        desc="https://docs.python.org/3/library/time.html#time.strftime",
    ),
    StringSetting(
        key="dictionary_url",
        type=SettingType.APP,
        default="WIKTIONARY",
        desc=_(
            "Either a custom URL with %%s in it (where %%s is the word/phrase)"
            ' or "WIKTIONARY" (which means use Wikitionary).'
        ),
    ),
    StringSetting(
        key="ft_add_hosts_to_send",
        type=SettingType.APP,
        desc=_(
            "List of send hosts (comma separated) in "
            "addition to local interfaces for file transfers (in case of "
            "address translation/port forwarding)."
        ),
    ),
    StringSetting(
        key="gc_refer_to_nick_char",
        type=SettingType.APP,
        default=",",
        desc=_(
            "Character to add after nickname when using nickname completion "
            "(tab) in group chat."
        ),
    ),
    StringSetting(key="global_proxy", type=SettingType.APP, label=_("Global Proxy")),
    StringSetting(key="last_save_dir", type=SettingType.APP),
    StringSetting(key="last_send_dir", type=SettingType.APP),
    StringSetting(key="last_sounds_dir", type=SettingType.APP),
    StringSetting(key="last_update_check", type=SettingType.APP),
    StringSetting(key="latest_disco_addresses", type=SettingType.APP),
    StringSetting(
        key="muc_highlight_words",
        type=SettingType.APP,
        desc=_(
            "A list of words (semicolon separated) that will be "
            "highlighted in group chats."
        ),
    ),
    StringSetting(
        key="muclumbus_api_http_uri",
        type=SettingType.APP,
        default="https://search.jabber.network/api/1.0/search",
    ),
    StringSetting(
        key="muclumbus_api_jid",
        type=SettingType.APP,
        default="api@search.jabber.network",
    ),
    StringSetting(
        key="muclumbus_api_pref",
        type=SettingType.APP,
        default="http",
        desc=_('API Preferences. Possible values: "http", "iq"'),
    ),
    StringSetting(
        key="providers_list_url",
        type=SettingType.APP,
        default="https://data.xmpp.net/providers/v2/providers-B.json",
        desc=_("Endpoint for retrieving a list of providers for sign up"),
    ),
    StringSetting(
        key="quick_reaction_emojis",
        type=SettingType.APP,
        default="👍,❤,😂",
        desc=_("Comma-separated list of emojis for quick reaction buttons"),
    ),
    StringSetting(
        key="roster_theme", type=SettingType.APP, default="default", label=_("Theme")
    ),
    StringSetting(
        key="search_engine",
        type=SettingType.APP,
        default="https://duckduckgo.com/?q=%s",
    ),
    StringSetting(
        key="show_main_window_on_startup",
        type=SettingType.APP,
        default="always",
        enum=WindowStartupEnum,
        label=_("Show on Startup"),
        desc=_("Show window when starting Gajim"),
    ),
    StringSetting(key="speller_language", type=SettingType.APP),
    StringSetting(
        key="stun_server",
        type=SettingType.APP,
        desc=_("STUN server to use when using Jingle"),
    ),
    StringSetting(key="video_framerate", type=SettingType.APP),
    StringSetting(
        key="video_input_device",
        type=SettingType.APP,
        default="autovideosrc",
        label=_("Video Input Device"),
        desc=_("Select your video input device (e.g. webcam, screen capture)"),
    ),
    StringSetting(key="video_size", type=SettingType.APP, label=_("Video Resolution")),
    StringListSetting(key="workspace_order", type=SettingType.APP),
]

_ACCOUNT_SETTINGS: list[SettingT] = [
    BooleanSetting(
        key="active", type=SettingType.ACCOUNT, default=False, label=_("Enable Account")
    ),
    BooleanSetting(key="anonymous_auth", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(
        key="answer_receipts",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Send Message Receipts"),
        desc=_("Tell your contacts if you received a message"),
    ),
    BooleanSetting(
        key="autoauth",
        type=SettingType.ACCOUNT,
        default=False,
        label=_("Accept all Contact Requests"),
        desc=_("Automatically accept all contact requests"),
    ),
    BooleanSetting(
        key="autoconnect",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Connect on startup"),
    ),
    BooleanSetting(
        key="autojoin_sync",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Synchronize joined group chats"),
        desc=_("Synchronize joined group chats with other devices."),
    ),
    BooleanSetting(
        key="client_cert_encrypted", type=SettingType.ACCOUNT, default=False
    ),
    BooleanSetting(
        key="confirm_unencrypted_connection",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Confirm Unencrypted Connection"),
        desc=_("Ask before connecting unencrypted"),
    ),
    BooleanSetting(
        key="enable_gssapi",
        type=SettingType.ACCOUNT,
        default=False,
        label=_("Use GSSAPI"),
    ),
    BooleanSetting(
        key="enable_security_labels",
        type=SettingType.ACCOUNT,
        default=False,
        label=_("Security Labels"),
        desc=_(
            "Show labels describing confidentiality of "
            "messages, if the server supports XEP-0258"
        ),
    ),
    BooleanSetting(key="ft_send_local_ips", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(
        key="gc_send_marker_private_default", type=SettingType.ACCOUNT, default=True
    ),
    BooleanSetting(
        key="gc_send_marker_public_default", type=SettingType.ACCOUNT, default=False
    ),
    BooleanSetting(
        key="ignore_unknown_contacts",
        type=SettingType.ACCOUNT,
        default=False,
        label=_("Ignore Unknown Contacts"),
        desc=_("Ignore everything from contacts not in your contact list"),
    ),
    BooleanSetting(
        key="omemo_blind_trust",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Blind Trust"),
        desc=_("Blindly trust new devices until you verify them"),
    ),
    BooleanSetting(
        key="openpgp_backup_secret_key",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Backup Secret Key"),
        desc=_("Stores the secret key encrypted on the server"),
    ),
    BooleanSetting(
        key="openpgp_blind_trust",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Blind Trust"),
        desc=_("Blindly trust new devices"),
    ),
    BooleanSetting(key="publish_location", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(
        key="publish_tune",
        type=SettingType.ACCOUNT,
        default=False,
        label=_("Media Playback"),
        desc=_(
            "Disclose information about media that is "
            "currently being played on your system."
        ),
    ),
    BooleanSetting(
        key="request_user_data",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Contact Information"),
        desc=_("Request contact information (Tune, Location)"),
    ),
    BooleanSetting(
        key="restore_last_status",
        type=SettingType.ACCOUNT,
        default=False,
        label=_("Remember Last Status"),
        desc=_("Restore status and status message of your last session"),
    ),
    BooleanSetting(
        key="savepass", type=SettingType.ACCOUNT, default=True, label=_("Save Password")
    ),
    BooleanSetting(
        key="send_idle_time",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Idle Time"),
        desc=_("Disclose the time of your last activity"),
    ),
    BooleanSetting(
        key="send_marker_default",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Read Receipts"),
        desc=_("Default for chats and private group chats"),
    ),
    BooleanSetting(
        key="send_os_info",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Operating System"),
        desc=_("Disclose information about the operating system you currently use"),
    ),
    BooleanSetting(
        key="sync_muc_blocks",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Sync Group Chat Block List"),
        desc=_("Synchronize group chat block list with other devices"),
    ),
    BooleanSetting(
        key="sync_with_global_status",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Global Status"),
        desc=_("Synchronize the status of all accounts"),
    ),
    BooleanSetting(
        key="test_ft_proxies_on_startup", type=SettingType.ACCOUNT, default=False
    ),
    BooleanSetting(
        key="update_timezone",
        type=SettingType.ACCOUNT,
        default=True,
        label=_("Update Timezone"),
        desc=_("Update your profile's timezone automatically"),
    ),
    BooleanSetting(
        key="use_custom_host",
        type=SettingType.ACCOUNT,
        default=False,
        label=_("Enable"),
    ),
    BooleanSetting(key="use_ft_proxies", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(
        key="use_plain_connection",
        type=SettingType.ACCOUNT,
        default=False,
        label=_("Use Unencrypted Connection"),
        desc=_("Use an unencrypted connection to the server"),
    ),
    IntSetting(
        key="chat_history_max_age",
        type=SettingType.ACCOUNT,
        default=-1,
        enum=MaxHistoryAgeEnum,
        label=_("Keep Chat History"),
        desc=_("How long Gajim should keep your chat history"),
    ),
    IntSetting(
        key="custom_port",
        type=SettingType.ACCOUNT,
        default=5222,
        range=SettingRange(1, 65535, 1, 0),
        label=_("Port"),
    ),
    StringSetting(
        key="account_color",
        type=SettingType.ACCOUNT,
        default="rgb(85, 85, 85)",
        label=_("Color"),
        desc=_("Recognize your account by color"),
    ),
    StringSetting(
        key="account_label",
        type=SettingType.ACCOUNT,
        label=_("Label"),
        desc=_("Add a label to distinguish accounts in Gajim"),
    ),
    StringSetting(key="address", type=SettingType.ACCOUNT),
    StringSetting(key="avatar_sha", type=SettingType.ACCOUNT),
    StringSetting(key="client_cert", type=SettingType.ACCOUNT),
    StringSetting(
        key="custom_host",
        type=SettingType.ACCOUNT,
        label=_("Hostname"),
        desc=_("Manually set the hostname for the server"),
    ),
    StringSetting(
        key="custom_type",
        type=SettingType.ACCOUNT,
        enum=ConnectionTypeEnum,
        default="START TLS",
    ),
    StringSetting(
        key="default_workspace",
        type=SettingType.ACCOUNT,
        label=_("Default Workspace"),
        desc=_("Chats from this account will use this workspace by default"),
    ),
    StringSetting(
        key="encryption_default",
        type=SettingType.ACCOUNT,
        enum=EncryptionEnum,
        label=_("Default Encryption"),
        desc=_("Encryption method to use unless overridden on a per-contact basis"),
    ),
    StringSetting(key="file_transfer_proxies", type=SettingType.ACCOUNT),
    StringSetting(
        key="filetransfer_preference",
        type=SettingType.ACCOUNT,
        default="httpupload",
        enum=FileTransferMethodEnum,
        label=_("Filetransfer Preference"),
        desc=_("Preferred file transfer mechanism for file drag&drop on a chat window"),
    ),
    StringSetting(
        key="gc_send_chatstate_default",
        type=SettingType.ACCOUNT,
        default="composing_only",
        enum=SendChatStateEnum,
        label=_("Send Chat Indicators in Group Chats"),
        desc=_("Default for group chats (e.g. Contact is typing)"),
    ),
    StringSetting(key="http_auth", type=SettingType.ACCOUNT, default="ask"),
    StringSetting(key="last_status", type=SettingType.ACCOUNT, default="online"),
    StringSetting(key="last_status_msg", type=SettingType.ACCOUNT),
    StringSetting(key="password", type=SettingType.ACCOUNT),
    StringSetting(key="proxy", type=SettingType.ACCOUNT, label=_("Proxy")),
    StringSetting(key="resource", type=SettingType.ACCOUNT, default="gajim.$rand"),
    StringSetting(key="roster_version", type=SettingType.ACCOUNT),
    StringSetting(
        key="send_chatstate_default",
        type=SettingType.ACCOUNT,
        default="composing_only",
        enum=SendChatStateEnum,
        label=_("Send Chat Indicators"),
        desc=_("Default for chats (e.g. Contact is typing)"),
    ),
    StringSetting(key="subscription_request_msg", type=SettingType.ACCOUNT),
]

_CONTACT_SETTINGS: list[SettingT] = [
    BooleanSetting(
        key="enable_link_preview",
        type=SettingType.CONTACT,
        default=False,
        context_default=True,
        label=_("Show Link Preview"),
    ),
    BooleanSetting(
        key="send_marker",
        type=SettingType.CONTACT,
        default=False,
        context_default=True,
        label=_("Read Receipts"),
        desc=_("Send and receive read receipts"),
    ),
    StringSetting(
        key="encryption",
        type=SettingType.CONTACT,
        context_default=True,
        enum=EncryptionEnum,
    ),
    StringSetting(key="mute_until", type=SettingType.CONTACT),
    StringSetting(
        key="send_chatstate",
        type=SettingType.CONTACT,
        context_default=True,
        enum=SendChatStateEnum,
        label=_("Send Chat State"),
    ),
    StringSetting(key="speller_language", type=SettingType.CONTACT),
]

_GROUPCHAT_SETTINGS: list[SettingT] = [
    BooleanSetting(
        key="enable_link_preview",
        type=SettingType.GROUPCHAT,
        default=False,
        context_default=True,
        label=_("Show Link Preview"),
    ),
    BooleanSetting(
        key="notify_on_all_messages",
        type=SettingType.GROUPCHAT,
        default=False,
        context_default=True,
        label=_("Notify on all Messages"),
    ),
    BooleanSetting(
        key="print_join_left",
        type=SettingType.GROUPCHAT,
        default=False,
        context_default=True,
        label=_("Show Join/Leave"),
    ),
    BooleanSetting(
        key="print_status",
        type=SettingType.GROUPCHAT,
        default=False,
        context_default=True,
        label=_("Show Status Changes"),
        desc=_('For example: "Julia is now online"'),
    ),
    BooleanSetting(
        key="send_marker",
        type=SettingType.GROUPCHAT,
        default=False,
        context_default=True,
        label=_("Read Receipts"),
        desc=_("Send and receive read receipts"),
    ),
    IntSetting(
        key="sync_threshold",
        type=SettingType.GROUPCHAT,
        default=1,
        context_default=True,
        enum=SyncThresholdEnum,
        label=_("Sync Threshold"),
    ),
    StringSetting(
        key="encryption",
        type=SettingType.GROUPCHAT,
        context_default=True,
        enum=EncryptionEnum,
    ),
    StringSetting(key="mute_until", type=SettingType.GROUPCHAT),
    StringSetting(
        key="send_chatstate",
        type=SettingType.GROUPCHAT,
        context_default=True,
        enum=SendChatStateEnum,
        label=_("Send Chat State"),
    ),
    StringSetting(key="speller_language", type=SettingType.GROUPCHAT),
]

_PLUGIN_SETTINGS = [
    BooleanSetting(key="active", type=SettingType.PLUGIN, default=False)
]

_PROXY_SETTINGS = [
    StringSetting(key="type", type=SettingType.PROXY, default="socks5"),
    StringSetting(key="host", type=SettingType.PROXY),
    IntSetting(key="port", type=SettingType.PROXY, default=0),
    BooleanSetting(key="useauth", type=SettingType.PROXY, default=False),
    StringSetting(key="user", type=SettingType.PROXY),
    StringSetting(key="pass", type=SettingType.PROXY),
]

_WORKSPACE_SETTINGS = [
    StringSetting(key="name", type=SettingType.WORKSPACE, default=_("My Workspace")),
    StringSetting(key="color", type=SettingType.WORKSPACE),
    StringSetting(key="avatar_sha", type=SettingType.WORKSPACE),
    StringListSetting(key="chats", type=SettingType.WORKSPACE),
]


_ALL_SETTINGS = [
    _APP_SETTINGS,
    _ACCOUNT_SETTINGS,
    _CONTACT_SETTINGS,
    _GROUPCHAT_SETTINGS,
    _PLUGIN_SETTINGS,
    _PROXY_SETTINGS,
    _WORKSPACE_SETTINGS,
]


# fmt: off
class SettingSchema:

    _default_instance: SettingSchema | None = None

    def __init__(self, definition: Iterable[SettingT]) -> None:
        self._schema: dict[SettingType, dict[str, SettingT]] = defaultdict(dict)
        for setting in definition:
            self._schema[setting.type][setting.key] = setting

    @classmethod
    def get_default(cls) -> SettingSchema:
        if cls._default_instance is None:
            definition = itertools.chain.from_iterable(_ALL_SETTINGS)
            cls._default_instance = SettingSchema(definition)
        return cls._default_instance

    def get_type_default_settings(self, type_: SettingType) -> dict[str, Any]:
        return {key: setting.default for key, setting in self._schema[type_].items()}

    @overload
    def get_setting(self, type_: Literal[SettingType.APP], key: AppBoolSettings) -> BooleanSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.APP], key: AppStringSettings) -> StringSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.APP], key: AppFloatSettings) -> FloatSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.APP], key: AppIntSettings) -> IntSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.APP], key: str) -> SettingT | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.ACCOUNT], key: AccountBoolSettings) -> BooleanSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.ACCOUNT], key: AccountStringSettings) -> StringSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.ACCOUNT], key: AccountIntSettings) -> IntSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.ACCOUNT], key: str) -> SettingT | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.CONTACT], key: ContactBoolSettings) -> BooleanSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.CONTACT], key: ContactStringSettings) -> StringSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.CONTACT], key: str) -> SettingT | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.GROUPCHAT], key: GroupChatBoolSettings) -> BooleanSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.GROUPCHAT], key: GroupChatStringSettings) -> StringSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.GROUPCHAT], key: str) -> SettingT | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.PLUGIN], key: PluginBoolSettings) -> BooleanSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.PLUGIN], key: str) -> SettingT | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.PROXY], key: ProxyBoolSettings) -> BooleanSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.PROXY], key: ProxyStringSettings) -> StringSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.PROXY], key: ProxyIntSettings) -> IntSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.PROXY], key: str) -> SettingT | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.WORKSPACE], key: WorkspaceStringSettings) -> StringSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.WORKSPACE], key: WorkspaceStringListSettings) -> StringListSetting | None: ...
    @overload
    def get_setting(self, type_: Literal[SettingType.WORKSPACE], key: str) -> SettingT | None: ...
    def get_setting(self, type_: SettingType, key: str) -> Any:
        try:
            return self._schema[type_][key]
        except KeyError:
            return None
# fmt: on

INITIAL_WORKSPACE: dict[str, dict[str, WorkspaceSettings]] = {str(uuid.uuid4()): {}}

PROXY_EXAMPLES = {
    "Tor": {"type": "socks5", "host": "localhost", "port": 9050},
    "Tor (Browser)": {"type": "socks5", "host": "localhost", "port": 9150},
}


DEFAULT_SOUNDEVENT_SETTINGS = {
    "attention_received": {"enabled": True, "path": "attention.wav"},
    "first_message_received": {"enabled": True, "path": "message1.wav"},
    "contact_connected": {"enabled": False, "path": "connected.wav"},
    "contact_disconnected": {"enabled": False, "path": "disconnected.wav"},
    "message_sent": {"enabled": False, "path": "sent.wav"},
    "muc_message_highlight": {"enabled": True, "path": "gc_message1.wav"},
    "muc_message_received": {"enabled": True, "path": "message2.wav"},
    "incoming-call-sound": {"enabled": True, "path": "call_incoming.wav"},
    "outgoing-call-sound": {"enabled": True, "path": "call_outgoing.wav"},
}
