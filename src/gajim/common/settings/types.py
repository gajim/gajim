# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Literal
from typing import TypedDict

from nbxmpp import JID

AppBoolSettings = Literal[
    "always_english_wikipedia",
    "always_english_wiktionary",
    "ask_online_status",
    "autoaway",
    "autoxa",
    "chat_merge_consecutive_nickname",
    "check_for_update",
    "confirm_close_muc",
    "confirm_on_window_delete",
    "dev_force_bookmark_2",
    "enable_emoji_shortcodes",
    "enable_keepassxc_integration",
    "escape_key_closes",
    "enable_link_preview_default",
    "gc_enable_link_preview_default",
    "gc_notify_on_all_messages_private_default",
    "gc_notify_on_all_messages_public_default",
    "gc_notify_on_reaction_default",
    "gc_print_join_left_default",
    "gc_print_status_default",
    "hide_groupchat_occupants_list",
    "ignore_incoming_attention",
    "is_window_visible",
    "muc_prefer_direct_msg",
    "notification_preview_message",
    "notify_on_all_muc_messages",
    "notify_on_file_complete",
    "notify_on_reaction_default",
    "plugins_auto_update",
    "plugins_notify_after_update",
    "plugins_repository_enabled",
    "plugins_update_check",
    "positive_184_ack",
    "preview_allow_all_images",
    "preview_anonymous_muc",
    "preview_verify_https",
    "print_status_in_chats",
    "remote_control",
    "send_on_ctrl_enter",
    "show_help_start_chat",
    "show_in_taskbar",
    "show_notifications",
    "show_notifications_away",
    "show_send_message_button",
    "show_voice_message_button",
    "show_status_msgs_in_roster",
    "show_subject_on_join",
    "show_trayicon",
    "sort_by_show_in_muc",
    "sort_by_show_in_start_chat",
    "sounddnd",
    "sounds_on",
    "trayicon_notification_on_events",
    "use_http2",
    "use_keyring",
    "use_kib_mib",
    "use_speller",
    "use_stun_server",
    "use_urgency_hint",
    "video_see_self",
    "show_header_bar",
]

AppIntSettings = Literal[
    "audio_input_volume",
    "audio_output_volume",
    "autoawaytime",
    "autoxatime",
    "chat_handle_position",
    "dark_theme",
    "file_transfers_port",
    "gc_sync_threshold_private_default",
    "gc_sync_threshold_public_default",
    "groupchat_roster_width",
    "mainwin_height",
    "mainwin_width",
    "preview_max_file_size",
    "preview_size",
]

AppFloatSettings = Literal["app_font_size",]

AppStringSettings = Literal[
    "action_on_close",
    "additional_uri_schemes",
    "audio_input_device",
    "audio_output_device",
    "autoaway_message",
    "autoxa_message",
    "confirm_block",
    "date_format",
    "date_time_format",
    "dictionary_url",
    "gc_refer_to_nick_char",
    "global_proxy",
    "last_save_dir",
    "last_send_dir",
    "last_sounds_dir",
    "last_update_check",
    "latest_disco_addresses",
    "muc_highlight_words",
    "muclumbus_api_http_uri",
    "muclumbus_api_jid",
    "muclumbus_api_pref",
    "providers_list_url",
    "quick_reaction_emojis",
    "roster_theme",
    "search_engine",
    "show_main_window_on_startup",
    "speller_language",
    "stun_server",
    "time_format",
    "video_framerate",
    "video_input_device",
    "video_size",
]

AccountBoolSettings = Literal[
    "active",
    "anonymous_auth",
    "answer_receipts",
    "autoauth",
    "autoconnect",
    "autojoin_sync",
    "client_cert_encrypted",
    "confirm_unencrypted_connection",
    "enable_gssapi",
    "enable_security_labels",
    "ft_send_local_ips",
    "gc_send_marker_private_default",
    "gc_send_marker_public_default",
    "ignore_unknown_contacts",
    "publish_location",
    "publish_tune",
    "request_user_data",
    "restore_last_status",
    "savepass",
    "send_idle_time",
    "send_marker_default",
    "send_os_info",
    "sync_muc_blocks",
    "sync_with_global_status",
    "test_ft_proxies_on_startup",
    "update_timezone",
    "use_custom_host",
    "use_ft_proxies",
    "use_plain_connection",
    "omemo_blind_trust",
    "openpgp_blind_trust",
    "openpgp_backup_secret_key",
]


AccountStringSettings = Literal[
    "account_color",
    "account_label",
    "address",
    "avatar_sha",
    "client_cert",
    "custom_host",
    "custom_type",
    "default_workspace",
    "file_transfer_proxies",
    "filetransfer_preference",
    "gc_send_chatstate_default",
    "http_auth",
    "last_status",
    "last_status_msg",
    "password",
    "proxy",
    "resource",
    "roster_version",
    "send_chatstate_default",
    "subscription_request_msg",
]

AccountIntSettings = Literal[
    "chat_history_max_age",
    "custom_port",
]

GroupChatBoolSettings = Literal[
    "notify_on_all_messages",
    "print_join_left",
    "print_status",
    "send_marker",
    "enable_link_preview",
]

GroupChatStringSettings = Literal[
    "encryption",
    "mute_until",
    "speller_language",
    "send_chatstate",
]

GroupChatIntSettings = Literal["sync_threshold",]

AllGroupChatSettings = (
    GroupChatBoolSettings | GroupChatStringSettings | GroupChatIntSettings
)

ContactBoolSettings = Literal[
    "send_marker",
    "enable_link_preview",
]

ContactStringSettings = Literal[
    "encryption",
    "mute_until",
    "speller_language",
    "send_chatstate",
]

AllContactSettings = ContactBoolSettings | ContactStringSettings

PluginBoolSettings = Literal["active",]

ProxyBoolSettings = Literal["useauth",]

ProxyStringSettings = Literal[
    "type",
    "host",
    "user",
    "pass",
]

ProxyIntSettings = Literal["port",]

WorkspaceStringSettings = Literal[
    "name",
    "color",
    "avatar_sha",
]

WorkspaceStringListSettings = Literal["chats"]


class OpenChatSettingDetails(TypedDict):
    account: str
    jid: JID
    type: Literal["chat", "groupchat", "pm"]
    pinned: bool
    position: int


class WorkspaceSettings(TypedDict):
    name: str
    color: str
    avatar_sha: str
    chats: list[OpenChatSettingDetails]
