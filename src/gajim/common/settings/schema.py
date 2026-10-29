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
    BooleanSetting(key="ask_online_status", type=SettingType.APP, default=False),
    BooleanSetting(key="autoaway", type=SettingType.APP, default=True),
    BooleanSetting(key="autoxa", type=SettingType.APP, default=True),
    BooleanSetting(
        key="chat_merge_consecutive_nickname",
        type=SettingType.APP,
        desc=_(
            "Show message meta data (avatar, nickname, timestamp) only once, "
            "if there are multiple messages from the same sender within a "
            "specific timespan."
        ),
        default=True,
    ),
    BooleanSetting(key="check_for_update", type=SettingType.APP, default=True),
    BooleanSetting(
        key="confirm_close_muc",
        type=SettingType.APP,
        desc=_("Ask before closing a group chat tab/window."),
        default=True,
    ),
    BooleanSetting(
        key="confirm_on_window_delete",
        type=SettingType.APP,
        desc=_("Ask before quitting when Gajim’s window is closed"),
        default=True,
    ),
    BooleanSetting(
        key="dev_force_bookmark_2",
        type=SettingType.APP,
        desc=_("Force Bookmark 2 usage"),
        default=False,
    ),
    BooleanSetting(key="enable_emoji_shortcodes", type=SettingType.APP, default=True),
    BooleanSetting(
        key="enable_keepassxc_integration", type=SettingType.APP, default=False
    ),
    BooleanSetting(
        key="enable_link_preview_default", type=SettingType.APP, default=True
    ),
    BooleanSetting(key="escape_key_closes", type=SettingType.APP, default=False),
    BooleanSetting(
        key="gc_enable_link_preview_default", type=SettingType.APP, default=True
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
        key="gc_notify_on_reaction_default", type=SettingType.APP, default=True
    ),
    BooleanSetting(
        key="gc_print_join_left_default", type=SettingType.APP, default=False
    ),
    BooleanSetting(key="gc_print_status_default", type=SettingType.APP, default=False),
    BooleanSetting(
        key="hide_groupchat_occupants_list", type=SettingType.APP, default=False
    ),
    BooleanSetting(
        key="ignore_incoming_attention",
        type=SettingType.APP,
        desc=_('If enabled, Gajim will ignore incoming attention requests ("wizz").'),
        default=False,
    ),
    BooleanSetting(key="is_window_visible", type=SettingType.APP, default=True),
    BooleanSetting(key="muc_prefer_direct_msg", type=SettingType.APP, default=True),
    BooleanSetting(
        key="notification_preview_message",
        type=SettingType.APP,
        desc=_("Preview new messages in notification popup?"),
        default=True,
    ),
    BooleanSetting(
        key="notify_on_all_muc_messages", type=SettingType.APP, default=False
    ),
    BooleanSetting(key="notify_on_file_complete", type=SettingType.APP, default=True),
    BooleanSetting(
        key="notify_on_reaction_default", type=SettingType.APP, default=True
    ),
    BooleanSetting(key="plugins_auto_update", type=SettingType.APP, default=False),
    BooleanSetting(
        key="plugins_notify_after_update", type=SettingType.APP, default=True
    ),
    BooleanSetting(
        key="plugins_repository_enabled",
        type=SettingType.APP,
        desc=_("If enabled, Gajim offers to download plugins hosted on gajim.org"),
        default=True,
    ),
    BooleanSetting(key="plugins_update_check", type=SettingType.APP, default=True),
    BooleanSetting(key="positive_184_ack", type=SettingType.APP, default=False),
    BooleanSetting(key="preview_allow_all_images", type=SettingType.APP, default=False),
    BooleanSetting(key="preview_anonymous_muc", type=SettingType.APP, default=False),
    BooleanSetting(key="preview_verify_https", type=SettingType.APP, default=True),
    BooleanSetting(key="print_status_in_chats", type=SettingType.APP, default=False),
    BooleanSetting(key="remote_control", type=SettingType.APP, default=False),
    BooleanSetting(key="send_on_ctrl_enter", type=SettingType.APP, default=False),
    BooleanSetting(key="show_header_bar", type=SettingType.APP, default=True),
    BooleanSetting(key="show_help_start_chat", type=SettingType.APP, default=True),
    BooleanSetting(key="show_in_taskbar", type=SettingType.APP, default=True),
    BooleanSetting(key="show_notifications", type=SettingType.APP, default=True),
    BooleanSetting(key="show_notifications_away", type=SettingType.APP, default=False),
    BooleanSetting(key="show_send_message_button", type=SettingType.APP, default=False),
    BooleanSetting(
        key="show_status_msgs_in_roster", type=SettingType.APP, default=True
    ),
    BooleanSetting(key="show_subject_on_join", type=SettingType.APP, default=True),
    BooleanSetting(key="show_trayicon", type=SettingType.APP, default=True),
    BooleanSetting(key="show_voice_message_button", type=SettingType.APP, default=True),
    BooleanSetting(key="sort_by_show_in_muc", type=SettingType.APP, default=False),
    BooleanSetting(
        key="sort_by_show_in_start_chat", type=SettingType.APP, default=True
    ),
    BooleanSetting(key="sounddnd", type=SettingType.APP, default=False),
    BooleanSetting(key="sounds_on", type=SettingType.APP, default=True),
    BooleanSetting(
        key="trayicon_notification_on_events", type=SettingType.APP, default=True
    ),
    BooleanSetting(
        key="use_http2",
        type=SettingType.APP,
        desc=_("Use HTTP2 for requests if there is server support"),
        default=False,
    ),
    BooleanSetting(key="use_keyring", type=SettingType.APP, default=True),
    BooleanSetting(
        key="use_kib_mib",
        type=SettingType.APP,
        desc=_("IEC standard says KiB = 1024 bytes, KB = 1000 bytes."),
        default=False,
    ),
    BooleanSetting(key="use_speller", type=SettingType.APP, default=True),
    BooleanSetting(
        key="use_stun_server",
        type=SettingType.APP,
        desc=_(
            "If enabled, Gajim will try to use a STUN server when using Jingle."
            ' The one in "stun_server" option, or the one given by '
            "the XMPP server."
        ),
        default=False,
    ),
    BooleanSetting(
        key="use_urgency_hint",
        type=SettingType.APP,
        desc=_(
            "If enabled, Gajim makes the window flash (the default behaviour "
            "in most Window Managers) when holding pending events."
        ),
        default=True,
    ),
    BooleanSetting(key="video_see_self", type=SettingType.APP, default=True),
    FloatSetting(
        key="app_font_size",
        type=SettingType.APP,
        default=1.0,
        range=SettingRange(0.5, 3.0, 0.10, 2),
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
    IntSetting(key="autoawaytime", type=SettingType.APP, default=5),
    IntSetting(key="autoxatime", type=SettingType.APP, default=15),
    IntSetting(key="chat_handle_position", type=SettingType.APP, default=350),
    IntSetting(key="dark_theme", type=SettingType.APP, default=2),
    IntSetting(key="file_transfers_port", type=SettingType.APP, default=28011),
    IntSetting(
        key="gc_sync_threshold_private_default", type=SettingType.APP, default=0
    ),
    IntSetting(key="gc_sync_threshold_public_default", type=SettingType.APP, default=1),
    IntSetting(
        key="groupchat_roster_width",
        type=SettingType.APP,
        desc=_("Width of group chat roster in pixel"),
        default=250,
    ),
    IntSetting(key="mainwin_height", type=SettingType.APP, default=500),
    IntSetting(key="mainwin_width", type=SettingType.APP, default=1000),
    IntSetting(key="preview_max_file_size", type=SettingType.APP, default=10485760),
    IntSetting(key="preview_size", type=SettingType.APP, default=400),
    StringSetting(
        key="time_format",
        type=SettingType.APP,
        desc="https://docs.python.org/3/library/time.html#time.strftime",
        default="%H:%M",
    ),
    StringSetting(key="action_on_close", type=SettingType.APP, default="hide"),
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
    ),
    StringSetting(
        key="audio_output_device", type=SettingType.APP, default="autoaudiosink"
    ),
    StringSetting(key="autoaway_message", type=SettingType.APP),
    StringSetting(key="autoxa_message", type=SettingType.APP),
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
        desc="https://docs.python.org/3/library/time.html#time.strftime",
        default="%x",
    ),
    StringSetting(
        key="date_time_format",
        type=SettingType.APP,
        desc="https://docs.python.org/3/library/time.html#time.strftime",
        default="%c",
    ),
    StringSetting(
        key="dictionary_url",
        type=SettingType.APP,
        desc=_(
            "Either a custom URL with %%s in it (where %%s is the word/phrase)"
            ' or "WIKTIONARY" (which means use Wikitionary).'
        ),
        default="WIKTIONARY",
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
        desc=_(
            "Character to add after nickname when using nickname completion "
            "(tab) in group chat."
        ),
        default=",",
    ),
    StringSetting(key="global_proxy", type=SettingType.APP),
    StringSetting(key="last_save_dir", type=SettingType.APP),
    StringSetting(key="last_send_dir", type=SettingType.APP),
    StringSetting(key="last_sounds_dir", type=SettingType.APP),
    StringSetting(key="last_update_check", type=SettingType.APP),
    StringSetting(key="latest_disco_addresses", type=SettingType.APP),
    StringSetting(
        key="muc_highlight_words",
        desc=_(
            "A list of words (semicolon separated) that will be "
            "highlighted in group chats."
        ),
        type=SettingType.APP,
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
        desc=_('API Preferences. Possible values: "http", "iq"'),
        default="http",
    ),
    StringSetting(
        key="providers_list_url",
        type=SettingType.APP,
        desc=_("Endpoint for retrieving a list of providers for sign up"),
        default="https://data.xmpp.net/providers/v2/providers-B.json",
    ),
    StringSetting(
        key="quick_reaction_emojis",
        type=SettingType.APP,
        desc=_("Comma-separated list of emojis for quick reaction buttons"),
        default="👍,❤,😂",
    ),
    StringSetting(key="roster_theme", type=SettingType.APP, default="default"),
    StringSetting(
        key="search_engine",
        type=SettingType.APP,
        default="https://duckduckgo.com/?q=%s",
    ),
    StringSetting(
        key="show_main_window_on_startup", type=SettingType.APP, default="always"
    ),
    StringSetting(key="speller_language", type=SettingType.APP),
    StringSetting(
        key="stun_server",
        type=SettingType.APP,
        desc=_("STUN server to use when using Jingle"),
    ),
    StringSetting(key="video_framerate", type=SettingType.APP),
    StringSetting(
        key="video_input_device", type=SettingType.APP, default="autovideosrc"
    ),
    StringSetting(key="video_size", type=SettingType.APP),
    StringListSetting(key="workspace_order", type=SettingType.APP),
]

_ACCOUNT_SETTINGS: list[SettingT] = [
    BooleanSetting(key="active", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(key="anonymous_auth", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(key="answer_receipts", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(key="autoauth", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(key="autoconnect", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(key="autojoin_sync", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(
        key="client_cert_encrypted", type=SettingType.ACCOUNT, default=False
    ),
    BooleanSetting(
        key="confirm_unencrypted_connection", type=SettingType.ACCOUNT, default=True
    ),
    BooleanSetting(key="enable_gssapi", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(
        key="enable_security_labels", type=SettingType.ACCOUNT, default=False
    ),
    BooleanSetting(key="ft_send_local_ips", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(
        key="gc_send_marker_private_default", type=SettingType.ACCOUNT, default=True
    ),
    BooleanSetting(
        key="gc_send_marker_public_default", type=SettingType.ACCOUNT, default=False
    ),
    BooleanSetting(
        key="ignore_unknown_contacts", type=SettingType.ACCOUNT, default=False
    ),
    BooleanSetting(key="omemo_blind_trust", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(
        key="openpgp_backup_secret_key", type=SettingType.ACCOUNT, default=True
    ),
    BooleanSetting(key="openpgp_blind_trust", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(key="publish_location", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(key="publish_tune", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(key="request_user_data", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(key="restore_last_status", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(key="savepass", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(key="send_idle_time", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(key="send_marker_default", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(key="send_os_info", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(key="sync_muc_blocks", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(
        key="sync_with_global_status", type=SettingType.ACCOUNT, default=True
    ),
    BooleanSetting(
        key="test_ft_proxies_on_startup", type=SettingType.ACCOUNT, default=False
    ),
    BooleanSetting(key="update_timezone", type=SettingType.ACCOUNT, default=True),
    BooleanSetting(key="use_custom_host", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(key="use_ft_proxies", type=SettingType.ACCOUNT, default=False),
    BooleanSetting(key="use_plain_connection", type=SettingType.ACCOUNT, default=False),
    IntSetting(key="chat_history_max_age", type=SettingType.ACCOUNT, default=-1),
    IntSetting(key="custom_port", type=SettingType.ACCOUNT, default=5222),
    StringSetting(
        key="account_color", type=SettingType.ACCOUNT, default="rgb(85, 85, 85)"
    ),
    StringSetting(key="account_label", type=SettingType.ACCOUNT),
    StringSetting(key="address", type=SettingType.ACCOUNT),
    StringSetting(key="avatar_sha", type=SettingType.ACCOUNT),
    StringSetting(key="client_cert", type=SettingType.ACCOUNT),
    StringSetting(key="custom_host", type=SettingType.ACCOUNT),
    StringSetting(key="custom_type", type=SettingType.ACCOUNT, default="START TLS"),
    StringSetting(key="default_workspace", type=SettingType.ACCOUNT),
    StringSetting(key="encryption_default", type=SettingType.ACCOUNT),
    StringSetting(key="file_transfer_proxies", type=SettingType.ACCOUNT),
    StringSetting(
        key="filetransfer_preference", type=SettingType.ACCOUNT, default="httpupload"
    ),
    StringSetting(
        key="gc_send_chatstate_default",
        type=SettingType.ACCOUNT,
        default="composing_only",
    ),
    StringSetting(key="http_auth", type=SettingType.ACCOUNT, default="ask"),
    StringSetting(key="last_status", type=SettingType.ACCOUNT, default="online"),
    StringSetting(key="last_status_msg", type=SettingType.ACCOUNT),
    StringSetting(key="password", type=SettingType.ACCOUNT),
    StringSetting(key="proxy", type=SettingType.ACCOUNT),
    StringSetting(key="resource", type=SettingType.ACCOUNT, default="gajim.$rand"),
    StringSetting(key="roster_version", type=SettingType.ACCOUNT),
    StringSetting(
        key="send_chatstate_default", type=SettingType.ACCOUNT, default="composing_only"
    ),
    StringSetting(key="subscription_request_msg", type=SettingType.ACCOUNT),
]

_CONTACT_SETTINGS: list[SettingT] = [
    BooleanSetting(
        key="enable_link_preview",
        type=SettingType.CONTACT,
        default=False,
        context_default=True,
    ),
    BooleanSetting(
        key="send_marker", type=SettingType.CONTACT, default=False, context_default=True
    ),
    StringSetting(key="encryption", type=SettingType.CONTACT, context_default=True),
    StringSetting(key="mute_until", type=SettingType.CONTACT),
    StringSetting(key="send_chatstate", type=SettingType.CONTACT, context_default=True),
    StringSetting(key="speller_language", type=SettingType.CONTACT),
]

_GROUPCHAT_SETTINGS: list[SettingT] = [
    BooleanSetting(
        key="enable_link_preview",
        type=SettingType.GROUPCHAT,
        default=False,
        context_default=True,
    ),
    BooleanSetting(
        key="notify_on_all_messages",
        type=SettingType.GROUPCHAT,
        default=False,
        context_default=True,
    ),
    BooleanSetting(
        key="print_join_left",
        type=SettingType.GROUPCHAT,
        default=False,
        context_default=True,
    ),
    BooleanSetting(
        key="print_status",
        type=SettingType.GROUPCHAT,
        default=False,
        context_default=True,
    ),
    BooleanSetting(
        key="send_marker",
        type=SettingType.GROUPCHAT,
        default=False,
        context_default=True,
    ),
    IntSetting(
        key="sync_threshold",
        type=SettingType.GROUPCHAT,
        default=1,
        context_default=True,
    ),
    StringSetting(key="encryption", type=SettingType.GROUPCHAT, context_default=True),
    StringSetting(key="mute_until", type=SettingType.GROUPCHAT),
    StringSetting(
        key="send_chatstate", type=SettingType.GROUPCHAT, context_default=True
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
