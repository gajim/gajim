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
opt_one_window_types = ['never', 'always', 'always_with_roster', 'peracct', 'pertype']
opt_show_roster_on_startup = ['always', 'never', 'last_state']
opt_treat_incoming_messages = ['', 'chat', 'normal']


class Config:

    DEFAULT_ICONSET = 'dcraven'
    DEFAULT_MOOD_ICONSET = 'default'
    DEFAULT_ACTIVITY_ICONSET = 'default'
    DEFAULT_OPENWITH = 'xdg-open'
    DEFAULT_BROWSER = 'firefox'
    DEFAULT_MAILAPP = 'mozilla-thunderbird -compose'
    DEFAULT_FILE_MANAGER = 'xffm'

    __options = ({
        # name: [ type, default_value, help_string ]
        'verbose': [opt_bool, False, '', True],
        'autopopup': [opt_bool, False],
        'notify_on_signin': [opt_bool, False],
        'notify_on_signout': [opt_bool, False],
        'notify_on_new_message': [opt_bool, True],
        'autopopupaway': [opt_bool, False],
        'autopopup_chat_opened': [opt_bool, False, _('Show desktop notification even when a chat window is opened for this contact and does not have focus')],
        'sounddnd': [opt_bool, False, _('Play sound when user is busy')],
        'showoffline': [opt_bool, True],
        'show_only_chat_and_online': [opt_bool, False, _('Show only online and free for chat contacts in the contact list.')],
        'show_transports_group': [opt_bool, True],
        'autoaway': [opt_bool, True],
        'autoawaytime': [opt_int, 5, _('Time in minutes, after which your status changes to away.')],
        'autoaway_message': [opt_str, _('$S (Away as a result of being idle more than $T min)'), _('$S will be replaced by current status message, $T by autoawaytime.')],
        'autoxa': [opt_bool, True],
        'autoxatime': [opt_int, 15, _('Time in minutes, after which your status changes to not available.')],
        'autoxa_message': [opt_str, _('$S (Not available as a result of being idle more than $T min)'), _('$S will be replaced by current status message, $T by autoxatime.')],
        'ask_online_status': [opt_bool, False],
        'ask_offline_status': [opt_bool, False],
        'trayicon': [opt_str, 'always', _("When to show notification area icon. Can be 'never', 'on_event', 'always'."), False],
        'allow_hide_roster': [opt_bool, False, _("Allow to hide the contact list window even if the tray icon is not shown."), False],
        'iconset': [opt_str, DEFAULT_ICONSET, '', True],
        'use_transports_iconsets': [opt_bool, True, '', True],
        'notif_signin_color': [opt_color, '#32CD32', _('Contact signed in notification color.')], # limegreen
        'notif_signout_color': [opt_color, '#FF0000', _('Contact signout notification color')], # red
        'notif_message_color': [opt_color, '#1E90FF', _('New message notification color.')], # dodgerblue
        'notif_ftrequest_color': [opt_color, '#F0E68C', _('File transfer request notification color.')], # khaki
        'notif_fterror_color': [opt_color, '#B22222', _('File transfer error notification color.')], # firebrick
        'notif_ftcomplete_color': [opt_color, '#9ACD32', _('File transfer complete or stopped notification color.')], # yellowgreen
        'notif_invite_color': [opt_color, '#D2B48C', _('Group chat invitation notification color')], # tan1
        'notif_status_color': [opt_color, '#D8BFD8', _('Background color of status changed notification')], # thistle2
        'notif_other_color': [opt_color, '#FFFFFF', _('Other dialogs color.')], # white
        'collapsed_rows': [opt_str, '', _('List (space separated) of rows (accounts and groups) that are collapsed.'), True],
        'roster_theme': [opt_str, _('default'), '', True],
        'mergeaccounts': [opt_bool, False, '', True],
        'sort_by_show_in_roster': [opt_bool, True, '', True],
        'sort_by_show_in_muc': [opt_bool, False, '', True],
        'use_speller': [opt_bool, False, ],
        'ignore_incoming_xhtml': [opt_bool, False, ],
        'speller_language': [opt_str, '', _('Language used by speller')],
        'print_time': [opt_str, 'always', _('\'always\' - print time for every message.\n\'sometimes\' - print time every print_ichat_every_foo_minutes minute.\n\'never\' - never print time.')],
        'print_time_fuzzy': [opt_int, 0, _('Print time in chats using Fuzzy Clock. Value of fuzziness from 1 to 4, or 0 to disable fuzzyclock. 1 is the most precise clock, 4 the least precise one. This is used only if print_time is \'sometimes\'.')],
        'emoticons_theme': [opt_str, 'noto-emoticons', '', True],
        'ascii_emoticons': [opt_bool, True, _('When enabled, ASCII emojis will be converted to graphical emojis.'), True],
        'ascii_formatting': [opt_bool, True,
                _('Treat * / _ pairs as possible formatting characters.'), True],
        'show_ascii_formatting_chars': [opt_bool, True, _('If true, do not '
                'remove */_ . So *abc* will be bold but with * * not removed.')],
        'rst_formatting_outgoing_messages': [opt_bool, False,
                _('Uses ReStructured text markup to send HTML, plus ascii formatting if selected. For syntax, see http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html (If you want to use this, install docutils)')],
        'sounds_on': [opt_bool, True],
        # 'aplay', 'play', 'esdplay', 'artsplay' detected first time only
        'soundplayer': [opt_str, ''],
        'openwith': [opt_str, DEFAULT_OPENWITH],
        'custombrowser': [opt_str, DEFAULT_BROWSER],
        'custommailapp': [opt_str, DEFAULT_MAILAPP],
        'custom_file_manager': [opt_str, DEFAULT_FILE_MANAGER],
        'gc-hpaned-position': [opt_int, 430],
        'gc_refer_to_nick_char': [opt_str, ',', _('Character to add after nickname when using nick completion (tab) in group chat.')],
        'gc_proposed_nick_char': [opt_str, '_', _('Character to propose to add after desired nickname when desired nickname is used by someone else in group chat.')],
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
        'save-roster-position': [opt_bool, True, _('If true, Gajim will save the contact list window position when hiding it, and restore it when showing the contact list window again.')],
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
        'time_stamp': [opt_str, '[%X] ', _('This option let you customize timestamp that is printed in conversation. For example "[%H:%M] " will show "[hour:minute] ". See python doc on strftime for full documentation: http://docs.python.org/lib/module-time.html')],
        'before_nickname': [opt_str, '', _('Characters that are printed before the nickname in conversations')],
        'after_nickname': [opt_str, ':', _('Characters that are printed after the nickname in conversations')],
        'change_roster_title': [opt_bool, True, _('Add * and [n] in contact list window title?')],
        'restore_lines': [opt_int, 10, _('How many history messages should be restored when a chat tab/window is reopened?')],
        'restore_timeout': [opt_int, -1, _('How far back in time (minutes) history is restored. -1 means no limit.')],
        'muc_restore_lines': [opt_int, 100, _('How many lines to request from server when entering a group chat. -1 means no limit')],
        'muc_restore_timeout': [opt_int, -1, _('Minutes of backlog to request when entering a group chat. -1 means no limit')],
        'muc_autorejoin_timeout': [opt_int, 1, _('How many seconds to wait before trying to autorejoin to a conference you are being disconnected from. Set to 0 to disable autorejoining.')],
        'muc_autorejoin_on_kick': [opt_bool, False, _('Should autorejoin be activated when kicked from a conference?')],
        'send_on_ctrl_enter': [opt_bool, False, _('Send message on Ctrl+Enter and with Enter make new line (Mirabilis ICQ Client default behaviour).')],
        'last_roster_visible': [opt_bool, True],
        'key_up_lines': [opt_int, 25, _('How many lines to store for Ctrl+KeyUP.')],
        'version': [opt_str, gajim.__version__], # which version created the config
        'search_engine': [opt_str, 'https://duckduckgo.com/?q=%s'],
        'dictionary_url': [opt_str, 'WIKTIONARY', _("Either custom URL with %%s in it where %%s is the word/phrase or 'WIKTIONARY' which means use Wikitionary.")],
        'always_english_wikipedia': [opt_bool, False],
        'always_english_wiktionary': [opt_bool, True],
        'remote_control': [opt_bool, False, _('If checked, Gajim can be controlled remotely using gajim-remote.'), True],
        'autodetect_browser_mailer': [opt_bool, True, '', True],
        'print_ichat_every_foo_minutes': [opt_int, 5, _('When not printing time for every message (print_time==sometimes), print it every x minutes.')],
        'confirm_paste_image': [opt_bool, True, _('Ask before pasting an image.')],
        'confirm_close_muc': [opt_bool, True, _('Ask before closing a group chat tab/window.')],
        'confirm_close_muc_rooms': [opt_str, '', _('Always ask for confirmation before closing group chats with any of the XMPP Addresses on this space separated list.')],
        'noconfirm_close_muc_rooms': [opt_str, '', _('Never ask for confirmation before closing group chats with any of the XMPP Addresses on this space separated list.')],
        'confirm_close_multiple_tabs': [opt_bool, True, _('Ask before closing tabbed chat window if there are controls that can lose data (Chat, Private Chat, group chat that will not be minimized)')],
        'notify_on_file_complete': [opt_bool, True],
        'file_transfers_port': [opt_int, 28011],
        'ft_add_hosts_to_send': [opt_str, '', _('Comma separated list of sent hosts, in addition of local interfaces, for File Transfer in case of address translation/port forwarding.')],
        'use_kib_mib': [opt_bool, False, _('IEC standard says KiB = 1024 bytes, KB = 1000 bytes.')],
        'notify_on_all_muc_messages': [opt_bool, False],
        'trayicon_notification_on_events': [opt_bool, True, _('Notify of events in the notification area.')],
        'trayicon_blink': [opt_bool, True, _('If False, Gajim will display a static event icon instead of the blinking status icon in the notification area when notifying on event.')],
        'last_save_dir': [opt_str, ''],
        'last_send_dir': [opt_str, ''],
        'last_emoticons_dir': [opt_str, ''],
        'last_sounds_dir': [opt_str, ''],
        'tabs_position': [opt_str, 'top'],
        'tabs_always_visible': [opt_bool, False, _('Show tab when only one conversation?')],
        'tabs_border': [opt_bool, False, _('Show tabbed notebook border in chat windows?')],
        'tabs_close_button': [opt_bool, True, _('Show close button in tab?')],
        'tooltip_status_online_color': [opt_color, '#73D216'],
        'tooltip_status_free_for_chat_color': [opt_color, '#3465A4'],
        'tooltip_status_away_color': [opt_color, '#EDD400'],
        'tooltip_status_busy_color': [opt_color, '#F57900'],
        'tooltip_status_na_color': [opt_color, '#CC0000'],
        'tooltip_status_offline_color': [opt_color, '#555753'],
        'tooltip_affiliation_none_color': [opt_color, '#555753'],
        'tooltip_affiliation_member_color': [opt_color, '#73D216'],
        'tooltip_affiliation_administrator_color': [opt_color, '#F57900'],
        'tooltip_affiliation_owner_color': [opt_color, '#CC0000'],
        'tooltip_account_name_color': [opt_color, '#888A85'],
        'tooltip_idle_color': [opt_color, '#888A85'],
        'notification_preview_message': [opt_bool, True, _('Preview new messages in notification popup?')],
        'notification_position_x': [opt_int, -1],
        'notification_position_y': [opt_int, -1],
        'muc_highlight_words': [opt_str, '', _('A semicolon-separated list of words that will be highlighted in group chats.')],
        'quit_on_roster_x_button': [opt_bool, False, _('If true, quits Gajim when X button of Window Manager is clicked. This setting is taken into account only if notification icon is used.')],
        'hide_on_roster_x_button': [opt_bool, False, _('If true, Gajim hides the contact list window on pressing the X button instead of minimizing into the Dock.')],
        'show_unread_tab_icon': [opt_bool, False, _('If true, Gajim will display an icon on each tab containing unread messages. Depending on the theme, this icon may be animated.')],
        'show_status_msgs_in_roster': [opt_bool, True, _('If true, Gajim will display the status message, if not empty, for every contact under the contact name in the contact list window.'), True],
        'show_avatars_in_roster': [opt_bool, True, '', True],
        'show_mood_in_roster': [opt_bool, True, '', True],
        'show_activity_in_roster': [opt_bool, True, '', True],
        'show_tunes_in_roster': [opt_bool, True, '', True],
        'show_location_in_roster': [opt_bool, True, '', True],
        'avatar_position_in_roster': [opt_str, 'right', _('Define the position of the avatar in the contact list. Can be left or right'), True],
        'print_status_in_chats': [opt_bool, False, _('If False, Gajim will no longer print status line in chats when a contact changes their status and/or their status message.')],
        'print_join_left_default': [opt_bool, False, _('Default Setting: Show a status message for every join or leave in a group chat')],
        'print_status_muc_default': [opt_bool, False, _('Default Setting: Show a status message for all status (away, dnd, etc.) changes of users in a group chat')],
        'log_contact_status_changes': [opt_bool, False],
        'log_xhtml_messages': [opt_bool, False, _('Store XHTML messages in history instead of plain text messages.')],
        'hide_avatar_of_transport': [opt_bool, False, _('Don\'t show avatar for the transport itself.')],
        'roster_window_skip_taskbar': [opt_bool, False, _('Don\'t show the contact list window in the system taskbar.')],
        'use_urgency_hint': [opt_bool, True, _('If true, make the window flash (the default behaviour in most Window Managers) when holding pending events.')],
        'notification_timeout': [opt_int, 5],
        'one_message_window': [opt_str, 'always',
            #always, never, peracct, pertype should not be translated
                _('Controls the window where new messages are placed.\n\'always\' - All messages are sent to a single window.\n\'always_with_roster\' - Like \'always\' but the messages are in a single window along with the contact list.\n\'never\' - All messages get their own window.\n\'peracct\' - Messages for each account are sent to a specific window.\n\'pertype\' - Each message type (e.g. chats vs. group chats) is sent to a specific window.')],
        'show_roster_on_startup':[opt_str, 'always', _('Show the contact list window on startup.\n\'always\' - Always show the contact list window.\n\'never\' - Never show the contact list window.\n\'last_state\' - Restore last state of the contact list window.')],
        'show_avatar_in_chat': [opt_bool, True, _('If False, you will no longer see the avatar in the chat window.')],
        'escape_key_closes': [opt_bool, True, _('If true, pressing the escape key closes a tab/window.')],
        'hide_groupchat_banner': [opt_bool, False, _('Hides the banner in a group chat window')],
        'hide_chat_banner': [opt_bool, False, _('Hides the banner in two persons chat window')],
        'hide_groupchat_occupants_list': [opt_bool, False, _('Hides the group chat participants list in group chat window.')],
        'chat_merge_consecutive_nickname': [opt_bool, False, _('In a chat, show the nickname at the beginning of a line only when it\'s not the same person talking than in previous message.')],
        'chat_merge_consecutive_nickname_indent': [opt_str, '  ', _('Indentation when using merge consecutive nickname.')],
        'ctrl_tab_go_to_next_composing': [opt_bool, True, _('Ctrl-Tab go to next composing tab when none is unread.')],
        'confirm_metacontacts': [opt_str, '', _('Show the confirm metacontacts creation dialog or not? Empty string means never show the dialog.')],
        'confirm_block': [opt_str, '', _('Show the confirm block contact dialog or not? Empty string means never show the dialog.')],
        'confirm_custom_status': [opt_str, '', _('Show the confirm custom status dialog or not? Empty string means never show the dialog.')],
        'enable_negative_priority': [opt_bool, False, _('If true, you will be able to set a negative priority to your account in account modification window. BE CAREFUL, when you are logged in with a negative priority, you will NOT receive any message from your server.')],
        'show_contacts_number': [opt_bool, True, _('If true, Gajim will show number of online and total contacts in account and group rows.')],
        'treat_incoming_messages': [opt_str, 'chat', _('Can be empty, \'chat\' or \'normal\'. If not empty, treat all incoming messages as if they were of this type')],
        'scroll_roster_to_last_message': [opt_bool, True, _('If true, Gajim will scroll and select the contact who sent you the last message, if chat window is not already opened.')],
        'change_status_window_timeout': [opt_int, 15, _('Time of inactivity needed before the change status window closes down.')],
        'max_conversation_lines': [opt_int, 500, _('Maximum number of lines that are printed in conversations. Oldest lines are cleared.')],
        'attach_notifications_to_systray': [opt_bool, False, _('If true, notification windows from notification-daemon will be attached to notification icon.')],
        'check_idle_every_foo_seconds': [opt_int, 2, _('Choose interval between 2 checks of idleness.')],
        'uri_schemes': [opt_str, 'aaa:// aaas:// acap:// cap:// cid: crid:// data: dav: dict:// dns: fax: file:/ ftp:// geo: go: gopher:// h323: http:// https:// iax: icap:// im: imap:// info: ipp:// iris: iris.beep: iris.xpc: iris.xpcs: iris.lwz: ldap:// mid: modem: msrp:// msrps:// mtqp:// mupdate:// news: nfs:// nntp:// opaquelocktoken: pop:// pres: prospero:// rtsp:// service: shttp:// sip: sips: sms: snmp:// soap.beep:// soap.beeps:// tag: tel: telnet:// tftp:// thismessage:/ tip:// tv: urn:// vemmi:// xmlrpc.beep:// xmlrpc.beeps:// z39.50r:// z39.50s:// about: apt: cvs:// daap:// ed2k:// feed: fish:// git:// iax2: irc:// ircs:// ldaps:// magnet: mms:// rsync:// ssh:// svn:// sftp:// smb:// webcal:// aesgcm://', _('Valid uri schemes. Only schemes in this list will be accepted as "real" uri. (mailto and xmpp are handled separately)'), True],
        'shell_like_completion': [opt_bool, False, _('If true, completion in group chats will be like a shell auto-completion')],
        'audio_input_device': [opt_str, 'autoaudiosrc ! volume name=gajim_vol'],
        'audio_output_device': [opt_str, 'autoaudiosink'],
        'video_input_device': [opt_str, 'autovideosrc'],
        'video_output_device': [opt_str, 'autovideosink'],
        'video_framerate': [opt_str, '', _('Optionally fix jingle output video framerate. Example: 10/1 or 25/2')],
        'video_size': [opt_str, '', _('Optionally resize jingle output video. Example: 320x240')],
        'video_see_self': [opt_bool, True, _('If true, You will also see your webcam')],
        'audio_input_volume': [opt_int, 50],
        'audio_output_volume': [opt_int, 50],
        'use_stun_server': [opt_bool, False, _('If true, Gajim will try to use a STUN server when using Jingle. The one in "stun_server" option, or the one given by the XMPP server.')],
        'stun_server': [opt_str, '', _('STUN server to use when using Jingle')],
        'show_affiliation_in_groupchat': [opt_bool, True, _('If true, Gajim will show affiliation of group chat participants by adding a colored square to the status icon')],
        'global_proxy': [opt_str, '', _('Proxy used for all outgoing connections if the account does not have a specific proxy configured')],
        'ignore_incoming_attention': [opt_bool, False, _('If true, Gajim will ignore incoming attention requests ("wizz").')],
        'remember_opened_chat_controls': [opt_bool, True, _('If enabled, Gajim will reopen chat windows that were opened last time Gajim was closed.')],
        'positive_184_ack': [opt_bool, False, _('If enabled, Gajim will show an icon to show that sent message has been received by your contact')],
        'show_avatar_in_tabs': [opt_bool, False, _('Show a mini avatar in chat window tabs and in window icon')],
        'use_keyring': [opt_bool, True, _('If true, Gajim will use the Systems Keyring to store account passwords.')],
        'remote_commands': [opt_bool, False, _('If true, Gajim will execute XEP-0146 Commands.')],
        'dark_theme': [opt_int, 2, _('2: System, 1: Enabled, 0: Disabled')],
        'threshold_options': [opt_str, '1, 2, 4, 10, 0', _('Options in days which can be chosen in the sync threshold menu'), True],
        'public_room_sync_threshold': [opt_int, 1, _('Maximum history in days we request from a public room archive. 0: As much as possible')],
        'private_room_sync_threshold': [opt_int, 0, _('Maximum history in days we request from a private room archive. 0: As much as possible')],
        'show_subject_on_join': [opt_bool, True, _('If the room subject is shown in chat on join')],
        'show_chatstate_in_roster': [opt_bool, True, _('If the contact row is colored according to the current chatstate of the contact')],
        'show_chatstate_in_tabs': [opt_bool, True, _('If the tab is colored according to the current chatstate of the contact')],
        'show_chatstate_in_banner': [opt_bool, True, _('Shows a text in the banner that describes the current chatstate of the contact')],
        'send_chatstate_default': [opt_str, 'composing_only', _('Chat state notifications that are sent to contacts. Possible values: all, composing_only, disabled')],
        'send_chatstate_muc_default': [opt_str, 'composing_only', _('Chat state notifications that are sent to the group chat. Possible values: all, composing_only, disabled')],
        'muclumbus_api_jid': [opt_str, 'rodrigo.de.mucobedo@dreckshal.de'],
    }, {})  # type: Tuple[Dict[str, List[Any]], Dict[Any, Any]]

    __options_per_key = {
        'accounts': ({
            'name': [opt_str, '', '', True],
            'account_label': [opt_str, '', '', False],
            'hostname': [opt_str, '', '', True],
            'anonymous_auth': [opt_bool, False],
            'avatar_sha': [opt_str, '', '', False],
            'client_cert': [opt_str, '', '', True],
            'client_cert_encrypted': [opt_bool, False, '', False],
            'savepass': [opt_bool, False],
            'password': [opt_str, ''],
            'resource': [opt_str, 'gajim.$rand', '', True],
            'priority': [opt_int, 5, '', True],
            'adjust_priority_with_status': [opt_bool, True, _('Priority will change automatically according to your status. Priorities are defined in autopriority_* options.')],
            'autopriority_online': [opt_int, 50],
            'autopriority_chat': [opt_int, 50],
            'autopriority_away': [opt_int, 40],
            'autopriority_xa': [opt_int, 30],
            'autopriority_dnd': [opt_int, 20],
            'autopriority_invisible': [opt_int, 10],
            'autoconnect': [opt_bool, False, '', True],
            'autoconnect_as': [opt_str, 'online', _('Status used to autoconnect as. Can be online, chat, away, xa, dnd, invisible. NOTE: this option is used only if restore_last_status is disabled'), True],
            'restore_last_status': [opt_bool, False, _('If enabled, restore the last status that was used.')],
            'autoauth': [opt_bool, False, _('If true, Contacts requesting authorization will be automatically accepted.')],
            'active': [opt_bool, True, _('If False, this account will be disabled and will not appear in the contact list window.'), True],
            'proxy': [opt_str, '', '', True],
            'keyid': [opt_str, '', '', True],
            'keyname': [opt_str, '', '', True],
            'allow_plaintext_connection': [opt_bool, False, _('Allow plaintext connections')],
            'tls_version': [opt_str, '1.2', ''],
            'cipher_list': [opt_str, 'HIGH:!aNULL', ''],
            'authentication_mechanisms': [opt_str, '', _('List (space separated) of authentication mechanisms to try. Can contain ANONYMOUS, EXTERNAL, GSSAPI, SCRAM-SHA-1-PLUS, SCRAM-SHA-1, DIGEST-MD5, PLAIN, X-MESSENGER-OAUTH2 or XEP-0078')],
            'action_when_plaintext_connection': [opt_str, 'warn', _('Show a warning dialog before sending password on an plaintext connection. Can be \'warn\', \'connect\', \'disconnect\'')],
            'warn_when_insecure_ssl_connection': [opt_bool, True, _('Show a warning dialog before using standard SSL library.')],
            'warn_when_insecure_password': [opt_bool, True, _('Show a warning dialog before sending PLAIN password over a plain connection.')],
            'ignore_ssl_errors': [opt_str, '', _('Space separated list of ssl errors to ignore.')],
            'use_srv': [opt_bool, True, '', True],
            'use_custom_host': [opt_bool, False, '', True],
            'custom_port': [opt_int, 5222, '', True],
            'custom_host': [opt_str, '', '', True],
            'sync_with_global_status': [opt_bool, False, ],
            'no_log_for': [opt_str, '', _('Space separated list of XMPP Addresses for which you do not want to store chat history. You can also add account name to store no history for this account.')],
            'allow_no_log_for': [opt_str, '', _('Space separated list of XMPP Addresses for which you accept to not store chat history if the contact does not want to.')],
            'attached_gpg_keys': [opt_str, ''],
            'keep_alives_enabled': [opt_bool, True, _('Whitespace sent after inactivity')],
            'ping_alives_enabled': [opt_bool, True, _('XMPP ping sent after inactivity')],
            # send keepalive every N seconds of inactivity
            'keep_alive_every_foo_secs': [opt_int, 55],
            'ping_alive_every_foo_secs': [opt_int, 120],
            'time_for_ping_alive_answer': [opt_int, 60, _('How many seconds to wait for the answer of ping alive packet before trying to reconnect?')],
            # try for 1 minutes before giving up (aka. timeout after those seconds)
            'try_connecting_for_foo_secs': [opt_int, 60],
            'http_auth': [opt_str, 'ask'], # yes, no, ask
            'dont_ack_subscription': [opt_bool, False, _('Jabberd2 workaround')],
            # proxy65 for FT
            'file_transfer_proxies': [opt_str, ''],
            'use_ft_proxies': [opt_bool, False, _('If checked, Gajim will use your IP and proxies defined in file_transfer_proxies option for file transfer.'), True],
            'test_ft_proxies_on_startup': [opt_bool, False, _('If true, Gajim will test file transfer proxies on startup to be sure it works. Openfire\'s proxies are known to fail this test even if they work.')],
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
            'use_env_http_proxy': [opt_bool, False],
            'answer_receipts': [opt_bool, True, _('Answer to receipt requests')],
            'request_receipt': [opt_bool, True, _('Sent receipt requests')],
            'publish_tune': [opt_bool, False],
            'publish_location': [opt_bool, False],
            'subscribe_mood': [opt_bool, True],
            'subscribe_activity': [opt_bool, True],
            'subscribe_tune': [opt_bool, True],
            'subscribe_nick': [opt_bool, True],
            'subscribe_location': [opt_bool, True],
            'ignore_unknown_contacts': [opt_bool, False],
            'send_os_info': [opt_bool, True, _("Allow Gajim to send information about the operating system you are running.")],
            'send_time_info': [opt_bool, True, _("Allow Gajim to send your local time.")],
            'send_idle_time': [opt_bool, True],
            'roster_version': [opt_str, ''],
            'subscription_request_msg': [opt_str, '', _('Message that is sent to contacts you want to add')],
            'ft_send_local_ips': [opt_bool, True, _('If enabled, Gajim will send your local IPs so your contact can connect to your machine to transfer files.')],
            'opened_chat_controls': [opt_str, '', _('Space separated list of XMPP Addresses for which chat window will be re-opened on next startup.')],
            'recent_groupchats': [opt_str, ''],
            'httpupload_verify': [opt_bool, True, _('HTTP Upload: Enable HTTPS Verification')],
            'filetransfer_preference' : [opt_str, 'httpupload', _('Preferred file transfer mechanism for file drag&drop on chat window. Can be \'httpupload\' (default) or \'jingle\'')],
            'allow_posh': [opt_bool, True, _('Allow cert verification with POSH')],
        }, {}),
        'statusmsg': ({
            'message': [opt_str, ''],
            'activity': [opt_str, ''],
            'subactivity': [opt_str, ''],
            'activity_text': [opt_str, ''],
            'mood': [opt_str, ''],
            'mood_text': [opt_str, ''],
        }, {}),
        'defaultstatusmsg': ({
            'enabled': [opt_bool, False],
            'message': [opt_str, ''],
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
            'bosh_uri': [opt_str, ''],
            'bosh_useproxy': [opt_bool, False],
            'bosh_wait': [opt_int, 30],
            'bosh_hold': [opt_int, 2],
            'bosh_content': [opt_str, 'text/xml; charset=utf-8'],
            'bosh_http_pipelining': [opt_bool, False],
            'bosh_wait_for_restart_response': [opt_bool, False],
        }, {}),
        'contacts': ({
            'speller_language': [opt_str, '', _('Language for which misspelled words will be checked')],
            'send_chatstate': [opt_str, 'composing_only', _('Chat state notifications that are sent to contacts. Possible values: all, composing_only, disabled')],
        }, {}),
        'encryption': ({
            'encryption': [opt_str, '', _('The currently active encryption for that contact')],
        }, {}),
        'rooms': ({
            'speller_language': [opt_str, '', _('Language for which misspelled words will be checked')],
            'muc_restore_lines': [opt_int, -2, _('How many lines to request from server when entering a group chat. -1 means no limit, -2 means global value')],
            'muc_restore_timeout': [opt_int, -2, _('Minutes of backlog to request when entering a group chat. -1 means no limit, -2 means global value')],
            'notify_on_all_messages': [opt_bool, False, _('State whether a notification is created for every message in this room')],
            'print_status': [opt_bool, False, _('Show a status message for all status (away, dnd, etc.) changes of users in a group chat')],
            'print_join_left': [opt_bool, False, _('Show a status message for every join or leave in a group chat')],
            'minimize_on_autojoin': [opt_bool, True, _('If the group chat is minimized into the contact list on autojoin')],
            'minimize_on_close': [opt_bool, True, _('If the group chat is minimized into the contact list on close')],
            'send_chatstate': [opt_str, 'composing_only', _('Chat state notifications that are sent to the group chat. Possible values: all, composing_only, disabled')],
        }, {}),
        'plugins': ({
            'active': [opt_bool, False, _('State whether plugins should be activated on startup (this is saved on Gajim exit). This option SHOULD NOT be used to (de)activate plug-ins. Use GUI instead.')],
        }, {}),
    }  # type: Dict[str, Tuple[Dict[str, List[Any]], Dict[Any, Any]]]

    statusmsg_default = {
        _('Sleeping'): ['ZZZZzzzzzZZZZZ', 'inactive', 'sleeping', '', 'sleepy', ''],
        _('Back soon'): [_('Back in some minutes.'), '', '', '', '', ''],
        _('Eating'): [_("I'm eating, so leave me a message."), 'eating', 'other', '', '', ''],
        _('Movie'): [_("I'm watching a movie."), 'relaxing', 'watching_a_movie', '', '', ''],
        _('Working'): [_("I'm working."), 'working', 'other', '', '', ''],
        _('Phone'): [_("I'm on the phone."), 'talking', 'on_the_phone', '', '', ''],
        _('Out'): [_("I'm out enjoying life."), 'relaxing', 'going_out', '', '', ''],
        '_last_online': ['', '', '', '', '', ''],
        '_last_chat': ['', '', '', '', '', ''],
        '_last_away': ['', '', '', '', '', ''],
        '_last_xa': ['', '', '', '', '', ''],
        '_last_dnd': ['', '', '', '', '', ''],
        '_last_invisible': ['', '', '', '', '', ''],
        '_last_offline': ['', '', '', '', '', ''],
    }

    defaultstatusmsg_default = {
        'online': [False, _("I'm available.")],
        'chat': [False, _("I'm free for chat.")],
        'away': [False, _('Be right back.')],
        'xa': [False, _("I'm not available.")],
        'dnd': [False, _('Do not disturb.')],
        'invisible': [False, _('Bye!')],
        'offline': [False, _('Bye!')],
    }

    soundevents_default = {
        'attention_received': [True, 'attention.wav'],
        'first_message_received': [True, 'message1.wav'],
        'next_message_received_focused': [True, 'message2.wav'],
        'next_message_received_unfocused': [True, 'message2.wav'],
        'contact_connected': [False, 'connected.wav'],
        'contact_disconnected': [False, 'disconnected.wav'],
        'message_sent': [False, 'sent.wav'],
        'muc_message_highlight': [True, 'gc_message1.wav', _('Sound to play when a group chat message contains one of the words in muc_highlight_words, or when a group chat message contains your nickname.')],
        'muc_message_received': [True, 'gc_message2.wav', _('Sound to play when any MUC message arrives.')],
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

    def should_log(self, account, jid):
        """
        Should conversations between a local account and a remote jid be logged?
        """
        no_log_for = self.get_per('accounts', account, 'no_log_for')

        if not no_log_for:
            no_log_for = ''

        no_log_for = no_log_for.split()

        return (account not in no_log_for) and (jid not in no_log_for)

    def notify_for_muc(self, room):
        all_ = self.get('notify_on_all_muc_messages')
        room = self.get_per('rooms', room, 'notify_on_all_messages')
        return all_ or room

    def get_options(self, optname, return_type=str):
        options = self.get(optname).split(',')
        options = [return_type(option.strip()) for option in options]
        return options

    def _init_options(self):
        for opt in self.__options[0]:
            self.__options[1][opt] = self.__options[0][opt][Option.VAL]

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

        for status in self.defaultstatusmsg_default:
            default = self.defaultstatusmsg_default[status]
            self.add_per('defaultstatusmsg', status)
            self.set_per('defaultstatusmsg', status, 'enabled', default[0])
            self.set_per('defaultstatusmsg', status, 'message', default[1])
