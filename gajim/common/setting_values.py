# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from typing import Literal
from typing import TypedDict
from typing import Union

import uuid

from nbxmpp.protocol import JID

from gajim.common.i18n import _


class _DEFAULT:
    pass


class _ACCOUNTDEFAULT:
    pass


HAS_APP_DEFAULT = _DEFAULT()
HAS_ACCOUNT_DEFAULT = _ACCOUNTDEFAULT()


BoolSettings = Literal[
    'allow_open_file_uris',
    'always_english_wikipedia',
    'always_english_wiktionary',
    'ascii_formatting',
    'ask_online_status',
    'autoaway',
    'autoxa',
    'chat_merge_consecutive_nickname',
    'check_for_update',
    'confirm_close_muc',
    'confirm_on_window_delete',
    'dev_force_bookmark_2',
    'developer_modus',
    'enable_emoji_shortcodes',
    'enable_keepassxc_integration',
    'enable_negative_priority',
    'enable_file_preview',
    'escape_key_closes',
    'gc_notify_on_all_messages_private_default',
    'gc_notify_on_all_messages_public_default',
    'gc_print_join_left_default',
    'gc_print_status_default',
    'hide_groupchat_occupants_list',
    'ignore_incoming_attention',
    'is_window_visible',
    'muc_prefer_direct_msg',
    'notification_preview_message',
    'notify_on_all_muc_messages',
    'notify_on_file_complete',
    'plugins_auto_update',
    'plugins_notify_after_update',
    'plugins_repository_enabled',
    'plugins_update_check',
    'positive_184_ack',
    'preview_allow_all_images',
    'preview_anonymous_muc',
    'preview_verify_https',
    'print_status_in_chats',
    'remote_control',
    'save_main_window_position',
    'send_on_ctrl_enter',
    'show_chatstate_in_banner',
    'show_help_start_chat',
    'show_in_taskbar',
    'show_notifications',
    'show_notifications_away',
    'show_only_chat_and_online',
    'show_send_message_button',
    'show_status_msgs_in_roster',
    'show_subject_on_join',
    'show_transports_group',
    'show_trayicon',
    'show_xhtml',
    'showoffline',
    'sort_by_show_in_muc',
    'sort_by_show_in_roster',
    'sounddnd',
    'sounds_on',
    'trayicon_notification_on_events',
    'use_keyring',
    'use_kib_mib',
    'use_libappindicator',
    'use_speller',
    'use_stun_server',
    'use_urgency_hint',
    'video_see_self',
]

IntSettings = Literal[
    'audio_input_volume',
    'audio_output_volume',
    'autoawaytime',
    'autoxatime',
    'chat_handle_position',
    'dark_theme',
    'file_transfers_port',
    'gc_sync_threshold_private_default',
    'gc_sync_threshold_public_default',
    'groupchat_roster_width',
    'mainwin_height',
    'mainwin_width',
    'mainwin_x_position',
    'mainwin_y_position',
    'notification_position_x',
    'notification_position_y',
    'notification_timeout',
    'preview_max_file_size',
    'preview_size',
]

StringSettings = Literal[
    'action_on_close',
    'additional_uri_schemes',
    'audio_input_device',
    'audio_output_device',
    'autoaway_message',
    'autoxa_message',
    'confirm_block',
    'date_format',
    'date_time_format',
    'dictionary_url',
    'gc_refer_to_nick_char',
    'global_proxy',
    'last_save_dir',
    'last_send_dir',
    'last_sounds_dir',
    'last_update_check',
    'latest_disco_addresses',
    'muc_highlight_words',
    'muclumbus_api_http_uri',
    'muclumbus_api_jid',
    'muclumbus_api_pref',
    'preview_leftclick_action',
    'roster_theme',
    'search_engine',
    'show_main_window_on_startup',
    'speller_language',
    'stun_server',
    'time_format',
    'video_framerate',
    'video_input_device',
    'video_size',
]

AllSettings = Literal[BoolSettings, IntSettings, StringSettings]
AllSettingsT = Union[str, int, bool, list[str]]

APP_SETTINGS = {
    'additional_uri_schemes': '',
    'allow_open_file_uris': False,
    'always_english_wikipedia': False,
    'always_english_wiktionary': True,
    'ascii_formatting': True,
    'ask_online_status': False,
    'audio_input_device': 'autoaudiosrc ! volume name=gajim_vol',
    'audio_input_volume': 50,
    'audio_output_device': 'autoaudiosink',
    'audio_output_volume': 50,
    'autoaway': True,
    'autoaway_message': '',
    'autoawaytime': 5,
    'autoxa': True,
    'autoxa_message': '',
    'autoxatime': 15,
    'chat_handle_position': 350,
    'chat_merge_consecutive_nickname': True,
    'check_for_update': True,
    'confirm_block': '',
    'confirm_close_muc': True,
    'confirm_on_window_delete': True,
    'dark_theme': 2,
    'date_format': '%x',
    'date_time_format': '%c',
    'dev_force_bookmark_2': False,
    'dev_use_message_label': True,
    'developer_modus': False,
    'dictionary_url': 'WIKTIONARY',
    'enable_emoji_shortcodes': True,
    'enable_keepassxc_integration': False,
    'enable_negative_priority': False,
    'enable_file_preview': True,
    'escape_key_closes': False,
    'file_transfers_port': 28011,
    'ft_add_hosts_to_send': '',
    'gc_notify_on_all_messages_private_default': True,
    'gc_notify_on_all_messages_public_default': False,
    'gc_print_join_left_default': False,
    'gc_print_status_default': False,
    'gc_refer_to_nick_char': ',',
    'gc_sync_threshold_private_default': 0,
    'gc_sync_threshold_public_default': 1,
    'global_proxy': '',
    'groupchat_roster_width': 210,
    'hide_groupchat_occupants_list': False,
    'ignore_incoming_attention': False,
    'is_window_visible': True,
    'last_save_dir': '',
    'last_send_dir': '',
    'last_sounds_dir': '',
    'last_update_check': '',
    'latest_disco_addresses': '',
    'mainwin_height': 500,
    'mainwin_width': 1000,
    'mainwin_x_position': 0,
    'mainwin_y_position': 0,
    'action_on_close': 'hide',
    'muc_highlight_words': '',
    'muc_prefer_direct_msg': True,
    'muclumbus_api_http_uri': 'https://search.jabber.network/api/1.0/search',
    'muclumbus_api_jid': 'api@search.jabber.network',
    'muclumbus_api_pref': 'http',
    'notification_position_x': -1,
    'notification_position_y': -1,
    'notification_preview_message': True,
    'notification_timeout': 5,
    'notify_on_all_muc_messages': False,
    'notify_on_file_complete': True,
    'plugins_auto_update': False,
    'plugins_notify_after_update': True,
    'plugins_repository_enabled': True,
    'plugins_update_check': True,
    'positive_184_ack': False,
    'preview_allow_all_images': False,
    'preview_anonymous_muc': False,
    'preview_leftclick_action': 'open',
    'preview_max_file_size': 10485760,
    'preview_size': 300,
    'preview_verify_https': True,
    'print_status_in_chats': False,
    'remote_control': False,
    'roster_theme': 'default',
    'save_main_window_position': True,
    'search_engine': 'https://duckduckgo.com/?q=%s',
    'send_on_ctrl_enter': False,
    'show_chatstate_in_banner': True,
    'show_help_start_chat': True,
    'show_in_taskbar': True,
    'show_main_window_on_startup': 'always',
    'show_notifications': True,
    'show_notifications_away': False,
    'show_only_chat_and_online': False,
    'show_send_message_button': False,
    'show_status_msgs_in_roster': True,
    'show_subject_on_join': True,
    'show_transports_group': True,
    'show_trayicon': True,
    'show_xhtml': True,
    'showoffline': True,
    'sort_by_show_in_muc': False,
    'sort_by_show_in_roster': True,
    'sounddnd': False,
    'sounds_on': True,
    'speller_language': '',
    'stun_server': '',
    'time_format': '%H:%M',
    'trayicon_notification_on_events': True,
    'use_keyring': True,
    'use_kib_mib': False,
    'use_libappindicator': True,
    'use_speller': False,
    'use_stun_server': False,
    'use_urgency_hint': True,
    'video_framerate': '',
    'video_input_device': 'autovideosrc',
    'video_see_self': True,
    'video_size': '',
    'workspace_order': [],
}

BoolAccountSettings = Literal[
    'active',
    'adjust_priority_with_status',
    'anonymous_auth',
    'answer_receipts',
    'autoauth',
    'autoconnect',
    'client_cert_encrypted',
    'confirm_unencrypted_connection',
    'enable_gssapi',
    'enable_security_labels',
    'ft_send_local_ips',
    'gc_send_marker_private_default',
    'gc_send_marker_public_default',
    'ignore_unknown_contacts',
    'is_zeroconf',
    'publish_location',
    'publish_tune',
    'request_user_data',
    'restore_last_status',
    'savepass',
    'send_idle_time',
    'send_marker_default',
    'send_os_info',
    'send_time_info',
    'sync_with_global_status',
    'test_ft_proxies_on_startup',
    'use_custom_host',
    'use_ft_proxies',
    'use_plain_connection'
]


StringAccountSettings = Literal[
    'account_color',
    'account_label',
    'attached_gpg_keys',
    'avatar_sha',
    'client_cert',
    'custom_host',
    'custom_type',
    'default_workspace',
    'file_transfer_proxies',
    'filetransfer_preference',
    'gc_send_chatstate_default',
    'hostname',
    'http_auth',
    'keyid',
    'keyname',
    'last_status',
    'last_status_msg',
    'name',
    'password',
    'proxy',
    'resource',
    'roster_version',
    'send_chatstate_default',
    'subscription_request_msg',
    'zeroconf_email',
    'zeroconf_first_name',
    'zeroconf_jabber_id',
    'zeroconf_last_name',
]

IntAccountSettings = Literal[
    'autopriority_away',
    'autopriority_chat',
    'autopriority_dnd',
    'autopriority_online',
    'autopriority_xa',
    'chat_history_max_age',
    'custom_port',
    'priority',
]


AllAccountSettings = Literal[BoolAccountSettings,
                             IntAccountSettings,
                             StringAccountSettings]


BoolGroupChatSettings = Literal[
    'notify_on_all_messages',
    'print_join_left',
    'print_status',
    'send_marker',
]

StringGroupChatSettings = Literal[
    'encryption',
    'speller_language',
    'send_chatstate',
]

IntGroupChatSettings = Literal[
    'sync_threshold',
]


AllGroupChatSettings = Literal[BoolGroupChatSettings,
                               IntGroupChatSettings,
                               StringGroupChatSettings]

AllGroupChatSettingsT = Union[str, int, bool]


BoolContactSettings = Literal[
    'send_marker',
]

StringContactSettings = Literal[
    'encryption',
    'speller_language',
    'send_chatstate',
]

AllContactSettings = Literal[BoolContactSettings,
                             StringContactSettings]

AllContactSettingsT = Union[str, bool]


ACCOUNT_SETTINGS = {
    'account': {
        'account_color': 'rgb(85, 85, 85)',
        'account_label': '',
        'active': False,
        'adjust_priority_with_status': False,
        'anonymous_auth': False,
        'answer_receipts': True,
        'attached_gpg_keys': '',
        'autoauth': False,
        'autoconnect': True,
        'autopriority_away': 40,
        'autopriority_chat': 50,
        'autopriority_dnd': 20,
        'autopriority_online': 50,
        'autopriority_xa': 30,
        'avatar_sha': '',
        'chat_history_max_age': -1,
        'client_cert': '',
        'client_cert_encrypted': False,
        'confirm_unencrypted_connection': True,
        'custom_host': '',
        'custom_port': 5222,
        'custom_type': 'START TLS',
        'default_workspace': '',
        'enable_gssapi': False,
        'enable_security_labels': False,
        'file_transfer_proxies': '',
        'filetransfer_preference': 'httpupload',
        'ft_send_local_ips': True,
        'gc_send_chatstate_default': 'composing_only',
        'gc_send_marker_private_default': True,
        'gc_send_marker_public_default': False,
        'hostname': '',
        'http_auth': 'ask',
        'ignore_unknown_contacts': False,
        'is_zeroconf': False,
        'keyid': '',
        'keyname': '',
        'last_status': 'online',
        'last_status_msg': '',
        'name': '',
        'password': '',
        'priority': 0,
        'proxy': '',
        'publish_location': False,
        'publish_tune': False,
        'request_user_data': True,
        'resource': 'gajim.$rand',
        'restore_last_status': False,
        'roster_version': '',
        'savepass': True,
        'send_chatstate_default': 'composing_only',
        'send_idle_time': True,
        'send_marker_default': True,
        'send_os_info': True,
        'send_time_info': True,
        'subscription_request_msg': '',
        'sync_with_global_status': True,
        'test_ft_proxies_on_startup': False,
        'use_custom_host': False,
        'use_ft_proxies': False,
        'use_plain_connection': False,
        'zeroconf_email': '',
        'zeroconf_first_name': '',
        'zeroconf_jabber_id': '',
        'zeroconf_last_name': '',
    },

    'contact': {
        'encryption': '',
        'send_chatstate': HAS_ACCOUNT_DEFAULT,
        'send_marker': HAS_ACCOUNT_DEFAULT,
        'speller_language': '',
    },

    'group_chat': {
        'encryption': '',
        'notify_on_all_messages': HAS_APP_DEFAULT,
        'print_join_left': HAS_APP_DEFAULT,
        'print_status': HAS_APP_DEFAULT,
        'send_chatstate': HAS_ACCOUNT_DEFAULT,
        'send_marker': HAS_ACCOUNT_DEFAULT,
        'speller_language': '',
        'sync_threshold': HAS_APP_DEFAULT,
    },
}

StringWorkspaceSettings = Literal[
    'avatar_sha',
    'color',
    'name',
]

AllWorkspaceSettings = Literal[StringWorkspaceSettings, 'chats']


class OpenChatSettingDetails(TypedDict):
    account: str
    jid: JID
    type: str
    pinned: bool
    position: int


OpenChatsSettingT = list[OpenChatSettingDetails]
AllWorkspaceSettingsT = Union[str, OpenChatsSettingT]


class WorkspaceSettings(TypedDict):
    name: str
    color: str
    avatar_sha: str
    chats: OpenChatsSettingT


WORKSPACE_SETTINGS: WorkspaceSettings = {
    'name': _('My Workspace'),
    'color': '',
    'avatar_sha': '',
    'chats': [],
}


INITAL_WORKSPACE: dict[str, dict[str, WorkspaceSettings]] = {
    str(uuid.uuid4()): {}
}


PLUGIN_SETTINGS = {
    'active': False
}


STATUS_PRESET_SETTINGS = {
    'message': '',
}


STATUS_PRESET_EXAMPLES = {
    _('Sleeping'): {
        'message': _('ZZZZzzzzzZZZZZ')
    },
    _('Back soon'): {
        'message': _('Back in some minutes.')
    },
    _('Eating'): {
        'message': _('I’m eating.')
    },
    _('Movie'): {
        'message': _('I’m watching a movie.')
    },
    _('Working'): {
        'message': _('I’m working.')
    },
    _('Out'): {
        'message': _('I’m out enjoying life.')
    }
}


PROXY_SETTINGS = {
    'type': 'socks5',
    'host': '',
    'port': 0,
    'useauth': False,
    'user': '',
    'pass': '',
}


PROXY_EXAMPLES = {
    'Tor': {
        'type': 'socks5',
        'host': 'localhost',
        'port': 9050
    },
    'Tor (Browser)': {
        'type': 'socks5',
        'host': 'localhost',
        'port': 9150
    },
}


DEFAULT_SOUNDEVENT_SETTINGS = {
    'attention_received': {
        'enabled': True,
        'path': 'attention.wav'
    },
    'first_message_received': {
        'enabled': True,
        'path': 'message1.wav'
    },
    'contact_connected': {
        'enabled': False,
        'path': 'connected.wav'
    },
    'contact_disconnected': {
        'enabled': False,
        'path': 'disconnected.wav'
    },
    'message_sent': {
        'enabled': False,
        'path': 'sent.wav'
    },
    'muc_message_highlight': {
        'enabled': True,
        'path': 'gc_message1.wav'
    },
    'muc_message_received': {
        'enabled': True,
        'path': 'message2.wav'
    },
    'incoming-call-sound': {
        'enabled': True,
        'path': 'call_incoming.wav'
    },
    'outgoing-call-sound': {
        'enabled': True,
        'path': 'call_outgoing.wav'
    }
}


ADVANCED_SETTINGS = {
    'app': {
        'additional_uri_schemes': _(
            'Clickable schemes in addition to the hard-coded list of '
            'IANA-registered ones. Space-separated, lower-case, no colons.'),
        'allow_open_file_uris': _('Allows opening file:/ URIs when clicked.'),
        'always_english_wikipedia': '',
        'always_english_wiktionary': '',
        'ascii_formatting': _(
            'Treat * / _ pairs as possible formatting characters.'),
        'chat_merge_consecutive_nickname': _(
            'Show message meta data (avatar, nickname, timestamp) only once, '
            'if there are multiple messages from the same sender within a '
            'specific timespan.'),
        'confirm_block': _(
            'Show a confirmation dialog to block a contact? Empty string '
            'means never show the dialog.'),
        'confirm_close_muc': _('Ask before closing a group chat tab/window.'),
        'confirm_on_window_delete': _(
            'Ask before quitting when Gajim’s window is closed'),
        'date_format': 'https://docs.python.org/3/library/time.html#time.strftime',  # noqa: E501
        'date_time_format': 'https://docs.python.org/3/library/time.html#time.strftime',  # noqa: E501
        'dev_force_bookmark_2': _('Force Bookmark 2 usage'),
        'dev_use_message_label': '',
        'developer_modus': '',
        'dictionary_url': _(
            'Either a custom URL with %%s in it (where %%s is the word/phrase)'
            ' or "WIKTIONARY" (which means use Wikitionary).'),
        'enable_negative_priority': _(
            'If enabled, you will be able to set a negative priority to your '
            'account in the Accounts window. BE CAREFUL, when you are logged '
            'in with a negative priority, you will NOT receive any message '
            'from your server.'),
        'escape_key_closes': _('Close a chat by pressing the Escape key'),
        'file_transfers_port': '',
        'ft_add_hosts_to_send': _(
            'List of send hosts (comma separated) in '
            'addition to local interfaces for file transfers (in case of '
            'address translation/port forwarding).'),
        'gc_notify_on_all_messages_private_default': '',
        'gc_notify_on_all_messages_public_default': '',
        'gc_refer_to_nick_char': _(
            'Character to add after nickname when using nickname completion '
            '(tab) in group chat.'),
        'groupchat_roster_width': _('Width of group chat roster in pixel'),
        'ignore_incoming_attention': _(
            'If enabled, Gajim will ignore incoming attention '
            'requests ("wizz").'),
        'muc_highlight_words': _(
            'A list of words (semicolon separated) that will be '
            'highlighted in group chats.'),
        'muclumbus_api_http_uri': '',
        'muclumbus_api_jid': '',
        'muclumbus_api_pref': _(
            'API Preferences. Possible values: "http", "iq"'),
        'notification_preview_message': _(
            'Preview new messages in notification popup?'),
        'notification_timeout': '',
        'notify_on_all_muc_messages': '',
        'plugins_repository_enabled': _(
            'If enabled, Gajim offers to download plugins hosted on gajim.org'),
        'save_main_window_position': _(
            'If enabled, Gajim will save the main window position when hiding '
            'it, and restore it when showing the window again.'),
        'search_engine': '',
        'send_on_ctrl_enter': _(
            'Send message on Ctrl+Enter and make a new line with Enter.'),
        'show_chatstate_in_banner': _(
            'Show chat state (e.g. "is typing…") next to your contact’s name'),
        'stun_server': _('STUN server to use when using Jingle'),
        'time_format': 'https://docs.python.org/3/library/time.html#time.strftime',  # noqa: E501
        'trayicon_notification_on_events': _(
            'Notify of events in the notification area.'),
        'use_kib_mib': _(
            'IEC standard says KiB = 1024 bytes, KB = 1000 bytes.'),
        'use_libappindicator': _(
            'Enables libappindicator, an alternative tray icon provider'),
        'use_stun_server': _(
            'If enabled, Gajim will try to use a STUN server when using Jingle.'
            ' The one in "stun_server" option, or the one given by '
            'the XMPP server.'),
        'use_urgency_hint': _(
            'If enabled, Gajim makes the window flash (the default behaviour '
            'in most Window Managers) when holding pending events.'),
    },
}
