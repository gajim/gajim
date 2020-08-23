# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005 Stéphan Kochen <stephan AT kochen.nl>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Alex Mauer <hawke AT hawkesnest.net>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
# Copyright (C) 2006 Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 James Newton <redshodan AT gmail.com>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
#                         Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
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

from typing import Any  # pylint: disable=unused-import
from typing import Dict  # pylint: disable=unused-import
from typing import List  # pylint: disable=unused-import
from typing import Tuple  # pylint: disable=unused-import

import re
from enum import IntEnum, unique

from gi.repository import GLib

import gajim
from gajim.common.i18n import _


@unique
class Option(IntEnum):
    TYPE = 0
    VAL = 1
    DESC = 2
    # If Option.RESTART is True - we need restart to use our changed option
    # Option.DESC also should be there
    RESTART = 3

opt_int = ['integer', 0]
opt_str = ['string', 0]
opt_bool = ['boolean', 0]
opt_color = ['color', r'(#[0-9a-fA-F]{6})|rgb\(\d+,\d+,\d+\)|rgba\(\d+,\d+,\d+,[01]\.?\d*\)']


class Config:

    DEFAULT_ICONSET = 'dcraven'
    DEFAULT_MOOD_ICONSET = 'default'
    DEFAULT_ACTIVITY_ICONSET = 'default'

    __options = ({
        # name: [ type, default_value, help_string, restart ]
        'verbose': [opt_bool, False, '', True],
        'autopopup': [opt_bool, False],
        'notify_on_signin': [opt_bool, False],
        'notify_on_signout': [opt_bool, False],
        'notify_on_new_message': [opt_bool, True],
        'autopopupaway': [opt_bool, False],
        'autopopup_chat_opened': [opt_bool, False, _('Show desktop notification even when a chat window is opened for this contact and does not have focus.')],
        'sounddnd': [opt_bool, False, _('Play sound even when being busy.')],
        'showoffline': [opt_bool, True],
        'show_only_chat_and_online': [opt_bool, False, _('Show only online and free for chat contacts in the contact list.')],
        'show_transports_group': [opt_bool, True],
        'autoaway': [opt_bool, True],
        'autoawaytime': [opt_int, 5, _('Time in minutes, after which your status changes to away.')],
        'autoaway_message': [opt_str, _('$S (Away: Idle more than $T min)'), _('$S will be replaced by current status message, $T by the \'autoawaytime\' value.')],
        'autoxa': [opt_bool, True],
        'autoxatime': [opt_int, 15, _('Time in minutes, after which your status changes to not available.')],
        'autoxa_message': [opt_str, _('$S (Not available: Idle more than $T min)'), _('$S will be replaced by current status message, $T by the \'autoxatime\' value.')],
        'ask_online_status': [opt_bool, False],
        'ask_offline_status': [opt_bool, False],
        'trayicon': [opt_str, 'always', _('When to show the notification area icon. Can be \'never\', \'on_event\', and \'always\'.'), False],
        'allow_hide_roster': [opt_bool, False, _('Allow to hide the contact list window even if the notification area icon is not shown.'), False],
        'iconset': [opt_str, DEFAULT_ICONSET, '', True],
        'use_transports_iconsets': [opt_bool, True, '', True],
        'collapsed_rows': [opt_str, '', _('List of rows (accounts and groups) that are collapsed (space separated).'), True],
        'roster_theme': [opt_str, 'default', '', True],
        'mergeaccounts': [opt_bool, False, '', True],
        'sort_by_show_in_roster': [opt_bool, True, '', True],
        'sort_by_show_in_muc': [opt_bool, False, '', True],
        'use_speller': [opt_bool, False, ],
        'show_xhtml': [opt_bool, True, ],
        'speller_language': [opt_str, '', _('Language used for spell checking.')],
        'print_time': [opt_str, 'always', _('\'always\' - print time for every message.\n\'sometimes\' - print time every print_ichat_every_foo_minutes minute.\n\'never\' - never print time.')],
        'emoticons_theme': [opt_str, 'noto-emoticons', '', True],
        'ascii_emoticons': [opt_bool, True, _('When enabled, ASCII emojis will be converted to graphical emojis.'), True],
        'ascii_formatting': [opt_bool, True,
                _('Treat * / _ pairs as possible formatting characters.'), True],
        'show_ascii_formatting_chars': [opt_bool, True, _('If enabled, do not '
                'remove */_ . So *abc* will be bold but with * * not removed.')],
        'sounds_on': [opt_bool, True],
        'gc_refer_to_nick_char': [opt_str, ',', _('Character to add after nickname when using nickname completion (tab) in group chat.')],
        'msgwin-max-state': [opt_bool, False],
        'msgwin-x-position': [opt_int, -1], # Default is to let the window manager decide
        'msgwin-y-position': [opt_int, -1], # Default is to let the window manager decide
        'msgwin-width': [opt_int, 500],
        'msgwin-height': [opt_int, 440],
        'chat-msgwin-x-position': [opt_int, -1], # Default is to let the window manager decide
        'chat-msgwin-y-position': [opt_int, -1], # Default is to let the window manager decide
        'chat-msgwin-width': [opt_int, 480],
        'chat-msgwin-height': [opt_int, 440],
        'gc-msgwin-x-position': [opt_int, -1], # Default is to let the window manager decide
        'gc-msgwin-y-position': [opt_int, -1], # Default is to let the window manager decide
        'gc-msgwin-width': [opt_int, 600],
        'gc-msgwin-height': [opt_int, 440],
        'pm-msgwin-x-position': [opt_int, -1], # Default is to let the window manager decide
        'pm-msgwin-y-position': [opt_int, -1], # Default is to let the window manager decide
        'pm-msgwin-width': [opt_int, 480],
        'pm-msgwin-height': [opt_int, 440],
        'single-msg-x-position': [opt_int, 0],
        'single-msg-y-position': [opt_int, 0],
        'single-msg-width': [opt_int, 400],
        'single-msg-height': [opt_int, 280],
        'save-roster-position': [opt_bool, True, _('If enabled, Gajim will save the contact list window position when hiding it, and restore it when showing the contact list window again.')],
        'roster_x-position': [opt_int, 0],
        'roster_y-position': [opt_int, 0],
        'roster_width': [opt_int, 200],
        'roster_height': [opt_int, 400],
        'roster_hpaned_position': [opt_int, 200],
        'roster_on_the_right': [opt_bool, False, _('Place the contact list on the right in single window mode'), True],
        'history_window_width': [opt_int, -1],
        'history_window_height': [opt_int, 450],
        'history_window_x-position': [opt_int, 0],
        'history_window_y-position': [opt_int, 0],
        'latest_disco_addresses': [opt_str, ''],
        'time_stamp': [opt_str, '%x | %X  ', _('This option lets you customize the timestamp that is printed in conversation. For example \'[%H:%M] \' will show \'[hour:minute] \'. See python doc on strftime for full documentation (https://docs.python.org/3/library/time.html#time.strftime).')],
        'before_nickname': [opt_str, '', _('Characters that are printed before the nickname in conversations.')],
        'after_nickname': [opt_str, ':', _('Characters that are printed after the nickname in conversations.')],
        'change_roster_title': [opt_bool, True, _('If enabled, Gajim will add * and [n] in contact list window title.')],
        'restore_lines': [opt_int, 10, _('Number of messages from chat history to be restored when a chat tab/window is reopened.')],
        'restore_timeout': [opt_int, -1, _('How far back in time (minutes) chat history is restored. -1 means no limit.')],
        'send_on_ctrl_enter': [opt_bool, False, _('Send message on Ctrl+Enter and make a new line with Enter.')],
        'last_roster_visible': [opt_bool, True],
        'key_up_lines': [opt_int, 25, _('How many lines to store for Ctrl+KeyUP (previously sent messages).')],
        'version': [opt_str, gajim.__version__], # which version created the config
        'search_engine': [opt_str, 'https://duckduckgo.com/?q=%s'],
        'dictionary_url': [opt_str, 'WIKTIONARY', _('Either a custom URL with %%s in it (where %%s is the word/phrase) or \'WIKTIONARY\' (which means use Wikitionary).')],
        'always_english_wikipedia': [opt_bool, False],
        'always_english_wiktionary': [opt_bool, True],
        'remote_control': [opt_bool, False, _('If checked, Gajim can be controlled remotely using gajim-remote.'), True],
        'print_ichat_every_foo_minutes': [opt_int, 5, _('When not printing time for every message (\'print_time\'==sometimes), print it every x minutes.')],
        'confirm_paste_image': [opt_bool, True, _('Ask before pasting an image.')],
        'confirm_close_muc': [opt_bool, True, _('Ask before closing a group chat tab/window.')],
        'confirm_close_multiple_tabs': [opt_bool, True, _('Ask before closing tabbed chat window if there are chats that can lose data (chat, private chat, group chat that will not be minimized).')],
        'notify_on_file_complete': [opt_bool, True],
        'file_transfers_port': [opt_int, 28011],
        'ft_add_hosts_to_send': [opt_str, '', _('List of send hosts (comma separated) in addition to local interfaces for file transfers (in case of address translation/port forwarding).')],
        'use_kib_mib': [opt_bool, False, _('IEC standard says KiB = 1024 bytes, KB = 1000 bytes.')],
        'notify_on_all_muc_messages': [opt_bool, False],
        'trayicon_notification_on_events': [opt_bool, True, _('Notify of events in the notification area.')],
        'last_save_dir': [opt_str, ''],
        'last_send_dir': [opt_str, ''],
        'last_sounds_dir': [opt_str, ''],
        'tabs_position': [opt_str, 'left'],
        'tabs_always_visible': [opt_bool, False, _('Show tab when only one conversation?')],
        'tabs_border': [opt_bool, False, _('Show tabbed notebook border in chat windows?')],
        'tabs_close_button': [opt_bool, True, _('Show close button in tab?')],
        'notification_preview_message': [opt_bool, True, _('Preview new messages in notification popup?')],
        'notification_position_x': [opt_int, -1],
        'notification_position_y': [opt_int, -1],
        'muc_highlight_words': [opt_str, '', _('A list of words (semicolon separated) that will be highlighted in group chats.')],
        'quit_on_roster_x_button': [opt_bool, False, _('If enabled, Gajim quits when clicking the X button of your Window Manager. This setting is taken into account only if the notification area icon is used.')],
        'hide_on_roster_x_button': [opt_bool, False, _('If enabled, Gajim hides the contact list window when pressing the X button instead of minimizing into the notification area.')],
        'show_status_msgs_in_roster': [opt_bool, True, _('If enabled, Gajim will display the status message (if not empty) underneath the contact name in the contact list window.'), True],
        'show_avatars_in_roster': [opt_bool, True, '', True],
        'show_mood_in_roster': [opt_bool, True, '', True],
        'show_activity_in_roster': [opt_bool, True, '', True],
        'show_tunes_in_roster': [opt_bool, True, '', True],
        'show_location_in_roster': [opt_bool, True, '', True],
        'avatar_position_in_roster': [opt_str, 'right', _('Define the position of avatars in the contact list. Can be \'left\' or \'right\'.'), True],
        'print_status_in_chats': [opt_bool, False, _('If disabled, Gajim will no longer print status messages in chats when a contact changes their status (and/or their status message).')],
        'print_join_left_default': [opt_bool, False, _('Default Setting: Show a status message for every join or leave in a group chat.')],
        'print_status_muc_default': [opt_bool, False, _('Default Setting: Show a status message for all status changes (away, dnd, etc.) of users in a group chat.')],
        'log_contact_status_changes': [opt_bool, False],
        'roster_window_skip_taskbar': [opt_bool, False, _('Don\'t show contact list window in the system taskbar.')],
        'use_urgency_hint': [opt_bool, True, _('If enabled, Gajim makes the window flash (the default behaviour in most Window Managers) when holding pending events.')],
        'notification_timeout': [opt_int, 5],
        'one_message_window': [opt_str, 'always',
            #always, never, peracct, pertype should not be translated
                _('Controls the window where new messages are placed.\n\'always\' - All messages are sent to a single window.\n\'always_with_roster\' - Like \'always\' but the messages are in a single window along with the contact list.\n\'never\' - All messages get their own window.\n\'peracct\' - Messages for each account are sent to a specific window.\n\'pertype\' - Each message type (e.g. chats vs. group chats) is sent to a specific window.')],
        'show_roster_on_startup':[opt_str, 'always', _('Show contact list window on startup.\n\'always\' - Always show contact list window.\n\'never\' - Never show contact list window.\n\'last_state\' - Restore last state of the contact list window.')],
        'show_avatar_in_chat': [opt_bool, True, _('If enabled, Gajim displays the avatar in the chat window.')],
        'escape_key_closes': [opt_bool, True, _('If enabled, pressing Esc closes a tab/window.')],
        'hide_groupchat_banner': [opt_bool, False, _('Hides the banner in a group chat window.')],
        'hide_chat_banner': [opt_bool, False, _('Hides the banner in a 1:1 chat window.')],
        'hide_groupchat_occupants_list': [opt_bool, False, _('Hides the group chat participants list in a group chat window.')],
        'chat_merge_consecutive_nickname': [opt_bool, False, _('In a chat, show the nickname at the beginning of a line only when it\'s not the same person talking as in the previous message.')],
        'chat_merge_consecutive_nickname_indent': [opt_str, '  ', _('Indentation when using merge consecutive nickname.')],
        'ctrl_tab_go_to_next_composing': [opt_bool, True, _('Ctrl+Tab switches to the next composing tab when there are no tabs with messages pending.')],
        'confirm_metacontacts': [opt_str, '', _('Show a confirmation dialog to create metacontacts? Empty string means never show the dialog.')],
        'confirm_block': [opt_str, '', _('Show a confirmation dialog to block a contact? Empty string means never show the dialog.')],
        'enable_negative_priority': [opt_bool, False, _('If enabled, you will be able to set a negative priority to your account in the Accounts window. BE CAREFUL, when you are logged in with a negative priority, you will NOT receive any message from your server.')],
        'show_contacts_number': [opt_bool, True, _('If enabled, Gajim will show both the number of online and total contacts in account rows as well as in group rows.')],
        'scroll_roster_to_last_message': [opt_bool, True, _('If enabled, Gajim will scroll and select the contact who sent you the last message, if the chat window is not already opened.')],
        'change_status_window_timeout': [opt_int, 15, _('Time of inactivity needed before the change status window closes down.')],
        'max_conversation_lines': [opt_int, 500, _('Maximum number of lines that are printed in conversations. Oldest lines are cleared.')],
        'uri_schemes': [opt_str, 'aaa:// aaas:// acap:// cap:// cid: crid:// data: dav: dict:// dns: fax: file:/ ftp:// geo: go: gopher:// h323: http:// https:// iax: icap:// im: imap:// info: ipp:// iris: iris.beep: iris.xpc: iris.xpcs: iris.lwz: ldap:// mid: modem: msrp:// msrps:// mtqp:// mupdate:// news: nfs:// nntp:// opaquelocktoken: pop:// pres: prospero:// rtsp:// service: sip: sips: sms: snmp:// soap.beep:// soap.beeps:// tag: tel: telnet:// tftp:// thismessage:/ tip:// tv: urn:// vemmi:// xmlrpc.beep:// xmlrpc.beeps:// z39.50r:// z39.50s:// about: apt: cvs:// daap:// ed2k:// feed: fish:// git:// iax2: irc:// ircs:// ldaps:// magnet: mms:// rsync:// ssh:// svn:// sftp:// smb:// webcal:// aesgcm://', _('Valid URI schemes. Only schemes in this list will be accepted as \'real\' URI (mailto and xmpp are handled separately).'), True],
        'shell_like_completion': [opt_bool, False, _('If enabled, completion in group chats will be like a shell auto-completion.')],
        'audio_input_device': [opt_str, 'autoaudiosrc ! volume name=gajim_vol'],
        'audio_output_device': [opt_str, 'autoaudiosink'],
        'video_input_device': [opt_str, 'autovideosrc'],
        'video_framerate': [opt_str, '', _('Optionally fix Jingle output video framerate. Example: 10/1 or 25/2.')],
        'video_size': [opt_str, '', _('Optionally resize Jingle output video. Example: 320x240.')],
        'video_see_self': [opt_bool, True, _('If enabled, you will see your webcam\'s video stream as well.')],
        'audio_input_volume': [opt_int, 50],
        'audio_output_volume': [opt_int, 50],
        'use_stun_server': [opt_bool, False, _('If enabled, Gajim will try to use a STUN server when using Jingle. The one in \'stun_server\' option, or the one given by the XMPP server.')],
        'stun_server': [opt_str, '', _('STUN server to use when using Jingle')],
        'global_proxy': [opt_str, '', _('Proxy used for all outgoing connections if the account does not have a specific proxy configured.')],
        'ignore_incoming_attention': [opt_bool, False, _('If enabled, Gajim will ignore incoming attention requests (\'wizz\').')],
        'remember_opened_chat_controls': [opt_bool, True, _('If enabled, Gajim will reopen chat windows that were opened last time Gajim was closed.')],
        'positive_184_ack': [opt_bool, False, _('If enabled, Gajim will display an icon to show that sent messages have been received by your contact.')],
        'use_keyring': [opt_bool, True, _('If enabled, Gajim will use the System\'s Keyring to store account passwords.')],
        'remote_commands': [opt_bool, False, _('If enabled, Gajim will execute XEP-0146 Commands.')],
        'dark_theme': [opt_int, 2, _('2: System, 1: Enabled, 0: Disabled')],
        'threshold_options': [opt_str, '1, 2, 4, 10, 0', _('Options in days which can be chosen in the sync threshold menu'), True],
        'public_room_sync_threshold': [opt_int, 1, _('Maximum history in days we request from a public group chat archive. 0: As much as possible.')],
        'private_room_sync_threshold': [opt_int, 0, _('Maximum history in days we request from a private group chat archive. 0: As much as possible.')],
        'show_subject_on_join': [opt_bool, True, _('If enabled, Gajim shows the group chat subject in the chat window when joining.')],
        'show_chatstate_in_roster': [opt_bool, True, _('If enabled, the contact row is colored according to the current chat state of the contact.')],
        'show_chatstate_in_tabs': [opt_bool, True, _('If enabled, the tab is colored according to the current chat state of the contact.')],
        'show_chatstate_in_banner': [opt_bool, True, _('Shows a text in the banner that describes the current chat state of the contact.')],
        'send_chatstate_default': [opt_str, 'composing_only', _('Chat state notifications that are sent to contacts. Possible values: all, composing_only, disabled')],
        'send_chatstate_muc_default': [opt_str, 'composing_only', _('Chat state notifications that are sent to the group chat. Possible values: \'all\', \'composing_only\', \'disabled\'')],
        'muclumbus_api_jid': [opt_str, 'rodrigo.de.mucobedo@dreckshal.de'],
        'muclumbus_api_http_uri': [opt_str, 'https://search.jabbercat.org/api/1.0/search'],
        'muclumbus_api_pref': [opt_str, 'http', _('API Preferences. Possible values: \'http\', \'iq\'')],
        'auto_copy': [opt_bool, True, _('Selecting text will copy it to the clipboard')],
        'command_system_execute': [opt_bool, False, _('If enabled, Gajim will execute commands (/show, /sh, /execute, /exec).')],
        'groupchat_roster_width': [opt_int, 210, _('Width of group chat roster in pixel')],
        'dev_force_bookmark_2': [opt_bool, False, _('Force Bookmark 2 usage')],
        'show_help_start_chat': [opt_bool, True, _('Shows an info bar with helpful hints in the Start / Join Chat dialog')],
        'check_for_update': [opt_bool, True, _('Check for Gajim updates periodically')],
        'last_update_check': [opt_str, '', _('Date of the last update check')],
        'always_ask_for_status_message': [opt_bool, False],
    }, {})  # type: Tuple[Dict[str, List[Any]], Dict[Any, Any]]

    __options_per_key = {
        'accounts': ({
            'name': [opt_str, '', '', True],
            'account_label': [opt_str, '', '', False],
            'account_color': [opt_color, 'rgb(85, 85, 85)'],
            'hostname': [opt_str, '', '', True],
            'anonymous_auth': [opt_bool, False],
            'avatar_sha': [opt_str, '', '', False],
            'client_cert': [opt_str, '', '', True],
            'client_cert_encrypted': [opt_bool, False, '', False],
            'savepass': [opt_bool, False],
            'password': [opt_str, ''],
            'resource': [opt_str, 'gajim.$rand', '', True],
            'priority': [opt_int, 0, '', True],
            'adjust_priority_with_status': [opt_bool, False, _('Priority will change automatically according to your status. Priorities are defined in \'autopriority_*\' options.')],
            'autopriority_online': [opt_int, 50],
            'autopriority_chat': [opt_int, 50],
            'autopriority_away': [opt_int, 40],
            'autopriority_xa': [opt_int, 30],
            'autopriority_dnd': [opt_int, 20],
            'autoconnect': [opt_bool, False, '', True],
            'restore_last_status': [opt_bool, False, _('If enabled, the last status will be restored.')],
            'autoauth': [opt_bool, False, _('If enabled, contacts requesting authorization will be accepted automatically.')],
            'active': [opt_bool, True, _('If disabled, this account will be disabled and will not appear in the contact list window.'), True],
            'proxy': [opt_str, '', '', True],
            'keyid': [opt_str, '', '', True],
            'keyname': [opt_str, '', '', True],
            'use_plain_connection': [opt_bool, False, _('Use an unencrypted connection to the server')],
            'action_when_plain_connection': [opt_str, 'warn', _('Show a warning dialog before sending password on an plaintext connection. Can be \'warn\', or \'none\'.')],
            'use_custom_host': [opt_bool, False, '', True],
            'custom_port': [opt_int, 5222, '', True],
            'custom_host': [opt_str, '', '', True],
            'custom_type': [opt_str, 'START TLS', _('ConnectionType: START TLS, DIRECT TLS or PLAIN'), True],
            'sync_with_global_status': [opt_bool, False, ],
            'no_log_for': [opt_str, '', _('List of XMPP Addresses (space separated) for which you do not want to store chat history. You can also add the name of an account to disable storing chat history for this account.')],
            'attached_gpg_keys': [opt_str, ''],
            'http_auth': [opt_str, 'ask'], # yes, no, ask
            # proxy65 for FT
            'file_transfer_proxies': [opt_str, ''],
            'use_ft_proxies': [opt_bool, False, _('If enabled, Gajim will use your IP and proxies defined in \'file_transfer_proxies\' option for file transfers.'), True],
            'test_ft_proxies_on_startup': [opt_bool, False, _('If enabled, Gajim will test file transfer proxies on startup to be sure they work. Openfire\'s proxies are known to fail this test even if they work.')],
            'msgwin-x-position': [opt_int, -1], # Default is to let the wm decide
            'msgwin-y-position': [opt_int, -1], # Default is to let the wm decide
            'msgwin-width': [opt_int, 480],
            'msgwin-height': [opt_int, 440],
            'is_zeroconf': [opt_bool, False],
            'last_status': [opt_str, 'online'],
            'last_status_msg': [opt_str, ''],
            'zeroconf_first_name': [opt_str, '', '', True],
            'zeroconf_last_name': [opt_str, '', '', True],
            'zeroconf_jabber_id': [opt_str, '', '', True],
            'zeroconf_email': [opt_str, '', '', True],
            'answer_receipts': [opt_bool, True, _('If enabled, Gajim will answer to message receipt requests.')],
            'publish_tune': [opt_bool, False],
            'publish_location': [opt_bool, False],
            'subscribe_mood': [opt_bool, True],
            'subscribe_activity': [opt_bool, True],
            'subscribe_tune': [opt_bool, True],
            'subscribe_location': [opt_bool, True],
            'ignore_unknown_contacts': [opt_bool, False],
            'send_os_info': [opt_bool, True, _('Allow Gajim to send information about the operating system you are running.')],
            'send_time_info': [opt_bool, True, _('Allow Gajim to send your local time.')],
            'send_idle_time': [opt_bool, True],
            'roster_version': [opt_str, ''],
            'subscription_request_msg': [opt_str, '', _('Message that is sent to contacts you want to add.')],
            'ft_send_local_ips': [opt_bool, True, _('If enabled, Gajim will send your local IP so your contact can connect to your machine for file transfers.')],
            'opened_chat_controls': [opt_str, '', _('List of XMPP Addresses (space separated) for which the chat window will be re-opened on next startup.')],
            'recent_groupchats': [opt_str, ''],
            'filetransfer_preference' : [opt_str, 'httpupload', _('Preferred file transfer mechanism for file drag&drop on a chat window. Can be \'httpupload\' (default) or \'jingle\'.')],
            'allow_posh': [opt_bool, True, _('Allow certificate verification with POSH.')],
        }, {}),
        'statusmsg': ({
            'message': [opt_str, ''],
            'activity': [opt_str, ''],
            'subactivity': [opt_str, ''],
            'activity_text': [opt_str, ''],
            'mood': [opt_str, ''],
            'mood_text': [opt_str, ''],
        }, {}),
        'soundevents': ({
            'enabled': [opt_bool, True],
            'path': [opt_str, ''],
        }, {}),
        'proxies': ({
            'type': [opt_str, 'http'],
            'host': [opt_str, ''],
            'port': [opt_int, 3128],
            'useauth': [opt_bool, False],
            'user': [opt_str, ''],
            'pass': [opt_str, ''],
        }, {}),
        'contacts': ({
            'speller_language': [opt_str, '', _('Language used for spell checking.')],
            'send_chatstate': [opt_str, 'composing_only', _('Chat state notifications that are sent to contacts. Possible values: \'all\', \'composing_only\', \'disabled\'')],
        }, {}),
        'encryption': ({
            'encryption': [opt_str, '', _('The currently active encryption for that contact.')],
        }, {}),
        'rooms': ({
            'speller_language': [opt_str, '', _('Language used for spell checking.')],
            'notify_on_all_messages': [opt_bool, False, _('If enabled, a notification is created for every message in this group chat.')],
            'print_status': [opt_bool, False, _('Show a status message for all status changes (away, dnd, etc.) of users in a group chat.')],
            'print_join_left': [opt_bool, False, _('Show a status message for every join or leave in a group chat.')],
            'minimize_on_autojoin': [opt_bool, True, _('If enabled, the group chat is minimized into the contact list when joining automatically.')],
            'minimize_on_close': [opt_bool, True, _('If enabled, the group chat is minimized into the contact list when closing it.')],
            'send_chatstate': [opt_str, 'composing_only', _('Chat state notifications that are sent to the group chat. Possible values: \'all\', \'composing_only\' or \'disabled\'.')],
        }, {}),
        'plugins': ({
            'active': [opt_bool, False, _('If enabled, plugins will be activated on startup (this is saved when exiting Gajim). This option SHOULD NOT be used to (de)activate plugins. Use the plugin window instead.')],
        }, {}),
    }  # type: Dict[str, Tuple[Dict[str, List[Any]], Dict[Any, Any]]]

    statusmsg_default = {
        _('Sleeping'): ['ZZZZzzzzzZZZZZ', 'inactive', 'sleeping', '', 'sleepy', ''],
        _('Back soon'): [_('Back in some minutes.'), '', '', '', '', ''],
        _('Eating'): [_('I\'m eating.'), 'eating', 'other', '', '', ''],
        _('Movie'): [_('I\'m watching a movie.'), 'relaxing', 'watching_a_movie', '', '', ''],
        _('Working'): [_('I\'m working.'), 'working', 'other', '', '', ''],
        _('Phone'): [_('I\'m on the phone.'), 'talking', 'on_the_phone', '', '', ''],
        _('Out'): [_('I\'m out enjoying life.'), 'relaxing', 'going_out', '', '', ''],
    }

    soundevents_default = {
        'attention_received': [True, 'attention.wav'],
        'first_message_received': [True, 'message1.wav'],
        'next_message_received_focused': [True, 'message2.wav'],
        'next_message_received_unfocused': [True, 'message2.wav'],
        'contact_connected': [False, 'connected.wav'],
        'contact_disconnected': [False, 'disconnected.wav'],
        'message_sent': [False, 'sent.wav'],
        'muc_message_highlight': [True, 'gc_message1.wav', _('Sound to play when a group chat message contains one of the words in \'muc_highlight_words\' or your nickname is mentioned.')],
        'muc_message_received': [True, 'gc_message2.wav', _('Sound to play when any group chat message arrives.')],
    }

    proxies_default = {
        _('Tor'): ['socks5', 'localhost', 9050],
    }

    def foreach(self, cb, data=None):
        for opt in self.__options[1]:
            cb(data, opt, None, self.__options[1][opt])
        for opt in self.__options_per_key:
            cb(data, opt, None, None)
            dict_ = self.__options_per_key[opt][1]
            for opt2 in dict_.keys():
                cb(data, opt2, [opt], None)
                for opt3 in dict_[opt2]:
                    cb(data, opt3, [opt, opt2], dict_[opt2][opt3])

    def get_children(self, node=None):
        """
        Tree-like interface
        """
        if node is None:
            for child, option in self.__options[1].items():
                yield (child, ), option
            for grandparent in self.__options_per_key:
                yield (grandparent, ), None
        elif len(node) == 1:
            grandparent, = node
            for parent in self.__options_per_key[grandparent][1]:
                yield (grandparent, parent), None
        elif len(node) == 2:
            grandparent, parent = node
            children = self.__options_per_key[grandparent][1][parent]
            for child, option in children.items():
                yield (grandparent, parent, child), option
        else:
            raise ValueError('Invalid node')

    def is_valid_int(self, val):
        try:
            ival = int(val)
        except Exception:
            return None
        return ival

    def is_valid_bool(self, val):
        if val == 'True':
            return True
        if val == 'False':
            return False
        ival = self.is_valid_int(val)
        if ival:
            return True
        if ival is None:
            return None
        return False

    def is_valid_string(self, val):
        return val

    def is_valid(self, type_, val):
        if not type_:
            return None
        if type_[0] == 'boolean':
            return self.is_valid_bool(val)
        if type_[0] == 'integer':
            return self.is_valid_int(val)
        if type_[0] == 'string':
            return self.is_valid_string(val)
        if re.match(type_[1], val):
            return val
        return None

    def set(self, optname, value):
        if optname not in self.__options[1]:
            return
        value = self.is_valid(self.__options[0][optname][Option.TYPE], value)
        if value is None:
            return

        self.__options[1][optname] = value
        self._timeout_save()

    def get(self, optname=None):
        if not optname:
            return list(self.__options[1].keys())
        if optname not in self.__options[1]:
            return None
        return self.__options[1][optname]

    def get_default(self, optname):
        if optname not in self.__options[0]:
            return None
        return self.__options[0][optname][Option.VAL]

    def get_type(self, optname):
        if optname not in self.__options[0]:
            return None
        return self.__options[0][optname][Option.TYPE][0]

    def get_desc(self, optname):
        if optname not in self.__options[0]:
            return None
        if len(self.__options[0][optname]) > Option.DESC:
            return self.__options[0][optname][Option.DESC]

    def get_restart(self, optname):
        if optname not in self.__options[0]:
            return None
        if len(self.__options[0][optname]) > Option.RESTART:
            return self.__options[0][optname][Option.RESTART]

    def add_per(self, typename, name): # per_group_of_option
        if typename not in self.__options_per_key:
            return

        opt = self.__options_per_key[typename]
        if name in opt[1]:
            # we already have added group name before
            return 'you already have added %s before' % name
        opt[1][name] = {}
        for o in opt[0]:
            opt[1][name][o] = opt[0][o][Option.VAL]
        self._timeout_save()

    def del_per(self, typename, name, subname=None): # per_group_of_option
        if typename not in self.__options_per_key:
            return

        opt = self.__options_per_key[typename]
        if subname is None:
            del opt[1][name]
        # if subname is specified, delete the item in the group.
        elif subname in opt[1][name]:
            del opt[1][name][subname]
        self._timeout_save()

    def del_all_per(self, typename, subname):
        # Deletes all settings per typename
        # Example: Delete `account_label` for all accounts
        if typename not in self.__options_per_key:
            raise ValueError('typename %s does not exist' % typename)

        opt = self.__options_per_key[typename]
        for name in opt[1]:
            try:
                del opt[1][name][subname]
            except KeyError:
                pass
        self._timeout_save()

    def set_per(self, optname, key, subname, value): # per_group_of_option
        if optname not in self.__options_per_key:
            return
        if not key:
            return
        dict_ = self.__options_per_key[optname][1]
        if key not in dict_:
            self.add_per(optname, key)
        obj = dict_[key]
        if subname not in obj:
            return
        typ = self.__options_per_key[optname][0][subname][Option.TYPE]
        value = self.is_valid(typ, value)
        if value is None:
            return
        obj[subname] = value
        self._timeout_save()

    def get_per(self, optname, key=None, subname=None, default=None): # per_group_of_option
        if optname not in self.__options_per_key:
            return None
        dict_ = self.__options_per_key[optname][1]
        if not key:
            return list(dict_.keys())
        if key not in dict_:
            if default is not None:
                return default
            if subname in self.__options_per_key[optname][0]:
                return self.__options_per_key[optname][0][subname][1]
            return None
        obj = dict_[key]
        if not subname:
            return obj
        if subname not in obj:
            return None
        return obj[subname]

    def get_default_per(self, optname, subname):
        if optname not in self.__options_per_key:
            return None
        dict_ = self.__options_per_key[optname][0]
        if subname not in dict_:
            return None
        return dict_[subname][Option.VAL]

    def get_type_per(self, optname, subname):
        if optname not in self.__options_per_key:
            return None
        dict_ = self.__options_per_key[optname][0]
        if subname not in dict_:
            return None
        return dict_[subname][Option.TYPE][0]

    def get_desc_per(self, optname, subname=None):
        if optname not in self.__options_per_key:
            return None
        dict_ = self.__options_per_key[optname][0]
        if subname not in dict_:
            return None
        obj = dict_[subname]
        if len(obj) > Option.DESC:
            return obj[Option.DESC]
        return None

    def get_restart_per(self, optname, key=None, subname=None):
        if optname not in self.__options_per_key:
            return False
        dict_ = self.__options_per_key[optname][0]
        if not key:
            return False
        if key not in dict_:
            return False
        obj = dict_[key]
        if not subname:
            return False
        if subname not in obj:
            return False
        if len(obj[subname]) > Option.RESTART:
            return obj[subname][Option.RESTART]
        return False

    def get_options(self, optname, return_type=str):
        options = self.get(optname).split(',')
        options = [return_type(option.strip()) for option in options]
        return options

    def _init_options(self):
        for opt in self.__options[0]:
            self.__options[1][opt] = self.__options[0][opt][Option.VAL]

        if gajim.IS_PORTABLE:
            self.__options[1]['use_keyring'] = False

    def _really_save(self):
        from gajim.common import app
        if app.interface:
            app.interface.save_config()
        self.save_timeout_id = None
        return False

    def _timeout_save(self):
        if self.save_timeout_id:
            return
        self.save_timeout_id = GLib.timeout_add(1000, self._really_save)

    def __init__(self):
        #init default values
        self._init_options()
        self.save_timeout_id = None
        for event in self.soundevents_default:
            default = self.soundevents_default[event]
            self.add_per('soundevents', event)
            self.set_per('soundevents', event, 'enabled', default[0])
            self.set_per('soundevents', event, 'path', default[1])
