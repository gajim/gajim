# -*- coding:utf-8 -*-
## src/common/config.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2004-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005 Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Alex Mauer <hawke AT hawkesnest.net>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
## Copyright (C) 2006 Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 James Newton <redshodan AT gmail.com>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##


import sys
import re
import copy
from common import defs
from gi.repository import GLib

(
OPT_TYPE,
OPT_VAL,
OPT_DESC,
# If OPT_RESTART is True - we need restart to use our changed option
# OPT_DESC also should be there
OPT_RESTART,
) = range(4)

opt_int = [ 'integer', 0 ]
opt_str = [ 'string', 0 ]
opt_bool = [ 'boolean', 0 ]
opt_color = [ 'color', '^(#[0-9a-fA-F]{6})|()$' ]
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
            'verbose': [ opt_bool, False, '', True ],
            'autopopup': [ opt_bool, False ],
            'notify_on_signin': [ opt_bool, True ],
            'notify_on_signout': [ opt_bool, False ],
            'notify_on_new_message': [ opt_bool, True ],
            'autopopupaway': [ opt_bool, False ],
            'sounddnd': [ opt_bool, False, _('Play sound when user is busy')],
            'use_notif_daemon': [ opt_bool, True, _('Use D-Bus and Notification-Daemon to show notifications') ],
            'showoffline': [ opt_bool, False ],
            'show_only_chat_and_online': [ opt_bool, False, _('Show only online and free for chat contacts in roster.')],
            'show_transports_group': [ opt_bool, True ],
            'autoaway': [ opt_bool, True ],
            'autoawaytime': [ opt_int, 5, _('Time in minutes, after which your status changes to away.') ],
            'autoaway_message': [ opt_str, _('$S (Away as a result of being idle more than $T min)'), _('$S will be replaced by current status message, $T by autoawaytime.') ],
            'autoxa': [ opt_bool, True ],
            'autoxatime': [ opt_int, 15, _('Time in minutes, after which your status changes to not available.') ],
            'autoxa_message': [ opt_str, _('$S (Not available as a result of being idle more than $T min)'), _('$S will be replaced by current status message, $T by autoxatime.') ],
            'ask_online_status': [ opt_bool, False ],
            'ask_offline_status': [ opt_bool, False ],
            'trayicon': [opt_str, 'always', _("When to show notification area icon. Can be 'never', 'on_event', 'always'."), False],
            'allow_hide_roster': [opt_bool, False, _("Allow to hide the roster window even if the tray icon is not shown."), False],
            'iconset': [ opt_str, DEFAULT_ICONSET, '', True ],
            'mood_iconset': [ opt_str, DEFAULT_MOOD_ICONSET, '', True ],
            'activity_iconset': [ opt_str, DEFAULT_ACTIVITY_ICONSET, '', True ],
            'use_transports_iconsets': [ opt_bool, True, '', True ],
            'inmsgcolor': [ opt_color, '#a40000', _('Incoming nickname color.'), True ],
            'outmsgcolor': [ opt_color, '#3465a4', _('Outgoing nickname color.'), True ],
            'inmsgtxtcolor': [ opt_color, '', _('Incoming text color.'), True ],
            'outmsgtxtcolor': [ opt_color, '#555753', _('Outgoing text color.'), True ],
            'statusmsgcolor': [ opt_color, '#4e9a06', _('Status message text color.'), True ],
            'markedmsgcolor': [ opt_color, '#ff8080', '', True ],
            'urlmsgcolor': [ opt_color, '#204a87', '', True ],
            'notif_signin_color': [ opt_color, '#32CD32', _('Contact signed in notification color.') ], # limegreen
            'notif_signout_color': [ opt_color, '#FF0000', _('Contact signout notification color') ], # red
            'notif_message_color': [ opt_color, '#1E90FF', _('New message/email notification color.') ], # dodgerblue
            'notif_ftrequest_color': [ opt_color, '#F0E68C', _('File transfer request notification color.') ], # khaki
            'notif_fterror_color': [ opt_color, '#B22222', _('File transfer error notification color.') ], # firebrick
            'notif_ftcomplete_color': [ opt_color, '#9ACD32', _('File transfer complete or stopped notification color.') ], # yellowgreen
            'notif_invite_color': [ opt_color, '#D2B48C', _('Groupchat invitation notification color') ], # tan1
            'notif_status_color': [ opt_color, '#D8BFD8', _('Status changed notification background color') ], # thistle2
            'notif_other_color': [ opt_color, '#FFFFFF', _('Other dialogs color.') ], # white
            'inmsgfont': [ opt_str, '', _('Incoming nickname font.'), True ],
            'outmsgfont': [ opt_str, '', _('Outgoing nickname font.'), True ],
            'inmsgtxtfont': [ opt_str, '', _('Incoming text font.'), True ],
            'outmsgtxtfont': [ opt_str, '', _('Outgoing text font.'), True ],
            'statusmsgfont': [ opt_str, '', _('Status message text font.'), True ],
            'collapsed_rows': [ opt_str, '', _('List (space separated) of rows (accounts and groups) that are collapsed.'), True ],
            'roster_theme': [ opt_str, _('default'), '', True ],
            'mergeaccounts': [ opt_bool, False, '', True ],
            'sort_by_show_in_roster': [ opt_bool, True, '', True ],
            'sort_by_show_in_muc': [ opt_bool, False, '', True ],
            'use_speller': [ opt_bool, False, ],
            'ignore_incoming_xhtml': [ opt_bool, False, ],
            'speller_language': [ opt_str, '', _('Language used by speller')],
            'print_time': [ opt_str, 'always',  _('\'always\' - print time for every message.\n\'sometimes\' - print time every print_ichat_every_foo_minutes minute.\n\'never\' - never print time.')],
            'print_time_fuzzy': [ opt_int, 0, _('Print time in chats using Fuzzy Clock. Value of fuzziness from 1 to 4, or 0 to disable fuzzyclock. 1 is the most precise clock, 4 the least precise one. This is used only if print_time is \'sometimes\'.') ],
            'emoticons_theme': [opt_str, 'static', '', True ],
            'ascii_formatting': [ opt_bool, True,
                    _('Treat * / _ pairs as possible formatting characters.'), True],
            'show_ascii_formatting_chars': [ opt_bool, True, _('If True, do not '
                    'remove */_ . So *abc* will be bold but with * * not removed.')],
            'rst_formatting_outgoing_messages': [ opt_bool, False,
                    _('Uses ReStructured text markup to send HTML, plus ascii formatting if selected. For syntax, see http://docutils.sourceforge.net/docs/ref/rst/restructuredtext.html (If you want to use this, install docutils)')],
            'sounds_on': [ opt_bool, True ],
            # 'aplay', 'play', 'esdplay', 'artsplay' detected first time only
            'soundplayer': [ opt_str, '' ],
            'openwith': [ opt_str, DEFAULT_OPENWITH ],
            'custombrowser': [ opt_str, DEFAULT_BROWSER ],
            'custommailapp': [ opt_str, DEFAULT_MAILAPP ],
            'custom_file_manager': [ opt_str, DEFAULT_FILE_MANAGER ],
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
            'single-msg-x-position': [opt_int, 0],
            'single-msg-y-position': [opt_int, 0],
            'single-msg-width': [opt_int, 400],
            'single-msg-height': [opt_int, 280],
            'save-roster-position': [opt_bool, True, _('If True, Gajim will save roster position when hiding roster, and restore it when showing roster.')],
            'roster_x-position': [ opt_int, 0 ],
            'roster_y-position': [ opt_int, 0 ],
            'roster_width': [ opt_int, 200 ],
            'roster_height': [ opt_int, 400 ],
            'roster_hpaned_position': [opt_int, 200],
            'history_window_width': [ opt_int, 650 ],
            'history_window_height': [ opt_int, 450 ],
            'history_window_x-position': [ opt_int, 0 ],
            'history_window_y-position': [ opt_int, 0 ],
            'latest_disco_addresses': [ opt_str, '' ],
            'recently_groupchat': [ opt_str, '' ],
            'time_stamp': [ opt_str, '[%X] ', _('This option let you customize timestamp that is printed in conversation. For exemple "[%H:%M] " will show "[hour:minute] ". See python doc on strftime for full documentation: http://docs.python.org/lib/module-time.html') ],
            'before_nickname': [ opt_str, '', _('Characters that are printed before the nickname in conversations') ],
            'after_nickname': [ opt_str, ':', _('Characters that are printed after the nickname in conversations') ],
            'notify_on_new_gmail_email': [ opt_bool, True ],
            'notify_on_new_gmail_email_extra': [ opt_bool, False ],
            'notify_on_new_gmail_email_command': [ opt_str, '', _('Specify the command to run when new mail arrives, e.g.: /usr/bin/getmail -q') ],
            'use_gpg_agent': [ opt_bool, False ],
            'change_roster_title': [ opt_bool, True, _('Add * and [n] in roster title?')],
            'restore_lines': [opt_int, 4, _('How many lines to remember from previous conversation when a chat tab/window is reopened?')],
            'restore_timeout': [opt_int, 60, _('How many minutes should last lines from previous conversation last.')],
            'muc_restore_lines': [opt_int, 20, _('How many lines to request from server when entering a groupchat. -1 means no limit')],
            'muc_restore_timeout': [opt_int, 60, _('How many minutes back to request logs when entering a groupchat. -1 means no limit')],
            'muc_autorejoin_timeout': [opt_int, 1, _('How many seconds to wait before trying to autorejoin to a conference you are being disconnected from. Set to 0 to disable autorejoining.')],
            'muc_autorejoin_on_kick': [opt_bool, False, _('Should autorejoin be activated when we are being kicked from a conference?')],
            'send_on_ctrl_enter': [opt_bool, False, _('Send message on Ctrl+Enter and with Enter make new line (Mirabilis ICQ Client default behaviour).')],
            'last_roster_visible': [opt_bool, True],
            'key_up_lines': [opt_int, 25, _('How many lines to store for Ctrl+KeyUP.')],
            'version': [ opt_str, defs.version ], # which version created the config
            'search_engine': [opt_str, 'https://www.google.com/search?&q=%s&sourceid=gajim'],
            'dictionary_url': [opt_str, 'WIKTIONARY', _("Either custom url with %s in it where %s is the word/phrase or 'WIKTIONARY' which means use wiktionary.")],
            'always_english_wikipedia': [opt_bool, False],
            'always_english_wiktionary': [opt_bool, True],
            'remote_control': [opt_bool, False, _('If checked, Gajim can be controlled remotely using gajim-remote.'), True],
            'networkmanager_support': [opt_bool, True, _('If True, listen to D-Bus signals from NetworkManager and change the status of accounts (provided they do not have listen_to_network_manager set to False and they sync with global status) based upon the status of the network connection.'), True],
            'outgoing_chat_state_notifications': [opt_str, 'all', _('Sent chat state notifications. Can be one of all, composing_only, disabled.')],
            'displayed_chat_state_notifications': [opt_str, 'all', _('Displayed chat state notifications in chat windows. Can be one of all, composing_only, disabled.')],
            'autodetect_browser_mailer': [opt_bool, True, '', True],
            'print_ichat_every_foo_minutes': [opt_int, 5, _('When not printing time for every message (print_time==sometimes), print it every x minutes.')],
            'confirm_close_muc': [opt_bool, True, _('Ask before closing a group chat tab/window.')],
            'confirm_close_muc_rooms': [opt_str, '', _('Always ask before closing group chat tab/window in this space separated list of group chat JIDs.')],
            'noconfirm_close_muc_rooms': [opt_str, '', _('Never ask before closing group chat tab/window in this space separated list of group chat JIDs.')],
            'confirm_close_multiple_tabs': [opt_bool, True, _('Ask before closing tabbed chat window if there are controls that can lose data (chat, private chat, groupchat that will not be minimized)')],
            'notify_on_file_complete': [opt_bool, True],
            'file_transfers_port': [opt_int, 28011],
            'ft_add_hosts_to_send': [opt_str, '', _('Comma separated list of hosts that we send, in addition of local interfaces, for File Transfer in case of address translation/port forwarding.')],
            'conversation_font': [opt_str, ''],
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
            'esession_modp': [opt_str, '15,16,14', _('A list of modp groups to use in a Diffie-Hellman, highest preference first, separated by commas. Valid groups are 1, 2, 5, 14, 15, 16, 17 and 18. Higher numbers are more secure, but take longer to calculate when you start a session.')],
            'chat_avatar_width': [opt_int, 52],
            'chat_avatar_height': [opt_int, 52],
            'roster_avatar_width': [opt_int, 32],
            'roster_avatar_height': [opt_int, 32],
            'tooltip_avatar_width': [opt_int, 125],
            'tooltip_avatar_height': [opt_int, 125],
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
            'vcard_avatar_width': [opt_int, 200],
            'vcard_avatar_height': [opt_int, 200],
            'notification_preview_message': [opt_bool, True, _('Preview new messages in notification popup?')],
            'notification_position_x': [opt_int, -1],
            'notification_position_y': [opt_int, -1],
            'notification_avatar_width': [opt_int, 48],
            'notification_avatar_height': [opt_int, 48],
            'muc_highlight_words': [opt_str, '', _('A semicolon-separated list of words that will be highlighted in group chats.')],
            'quit_on_roster_x_button': [opt_bool, False, _('If True, quits Gajim when X button of Window Manager is clicked. This setting is taken into account only if notification icon is used.')],
            'check_if_gajim_is_default': [opt_bool, True, _('If True, Gajim will check if it\'s the default jabber client on each startup.')],
            'show_unread_tab_icon': [opt_bool, False, _('If True, Gajim will display an icon on each tab containing unread messages. Depending on the theme, this icon may be animated.')],
            'show_status_msgs_in_roster': [opt_bool, True, _('If True, Gajim will display the status message, if not empty, for every contact under the contact name in roster window.'), True],
            'show_avatars_in_roster': [opt_bool, True, '', True],
            'show_mood_in_roster': [opt_bool, True, '', True],
            'show_activity_in_roster': [opt_bool, True, '', True],
            'show_tunes_in_roster': [opt_bool, True, '', True],
            'show_location_in_roster': [opt_bool, True, '', True],
            'avatar_position_in_roster': [opt_str, 'right', _('Define the position of the avatar in roster. Can be left or right'), True],
            'ask_avatars_on_startup': [opt_bool, True, _('If True, Gajim will ask for avatar each contact that did not have an avatar last time or has one cached that is too old.')],
            'print_status_in_chats': [opt_bool, True, _('If False, Gajim will no longer print status line in chats when a contact changes his or her status and/or his or her status message.')],
            'print_status_in_muc': [opt_str, 'in_and_out', _('Can be "none", "all" or "in_and_out". If "none", Gajim will no longer print status line in groupchats when a member changes his or her status and/or his or her status message. If "all" Gajim will print all status messages. If "in_and_out", Gajim will only print FOO enters/leaves group chat.')],
            'log_contact_status_changes': [opt_bool, False],
            'log_xhtml_messages': [opt_bool, False, _('Log XHTML messages instead of plain text messages.')],
            'just_connected_bg_color': [opt_str, '#adc3c6', _('Background color of contacts when they just signed in.')],
            'just_disconnected_bg_color': [opt_str, '#ab6161', _('Background color of contacts when they just signed out.')],
            'restored_messages_color': [opt_color, '#555753'],
            'restored_messages_small': [opt_bool, True, _('If True, restored messages will use a smaller font than the default one.')],
            'hide_avatar_of_transport': [opt_bool, False, _('Don\'t show avatar for the transport itself.')],
            'roster_window_skip_taskbar': [opt_bool, False, _('Don\'t show roster in the system taskbar.')],
            'use_urgency_hint': [opt_bool, True, _('If True and installed GTK+ and PyGTK versions are at least 2.8, make the window flash (the default behaviour in most Window Managers) when holding pending events.')],
            'notification_timeout': [opt_int, 5],
            'send_sha_in_gc_presence': [opt_bool, True, _('Jabberd1.4 does not like sha info when one join a password protected group chat. Turn this option to False to stop sending sha info in group chat presences.')],
            'one_message_window': [opt_str, 'always',
#always, never, peracct, pertype should not be translated
                    _('Controls the window where new messages are placed.\n\'always\' - All messages are sent to a single window.\n\'always_with_roster\' - Like \'always\' but the messages are in a single window along with the roster.\n\'never\' - All messages get their own window.\n\'peracct\' - Messages for each account are sent to a specific window.\n\'pertype\' - Each message type (e.g. chats vs. groupchats) is sent to a specific window.')],
            'show_roster_on_startup':[opt_str, 'always', _('Show roster on startup.\n\'always\' - Always show roster.\n\'never\' - Never show roster.\n\'last_state\' - Restore the last state roster.')],
            'show_avatar_in_chat': [opt_bool, True, _('If False, you will no longer see the avatar in the chat window.')],
            'escape_key_closes': [opt_bool, True, _('If True, pressing the escape key closes a tab/window.')],
            'compact_view': [opt_bool, False, _('Hides the buttons in chat windows.')],
            'hide_groupchat_banner': [opt_bool, False, _('Hides the banner in a group chat window')],
            'hide_chat_banner': [opt_bool, False, _('Hides the banner in two persons chat window')],
            'hide_groupchat_occupants_list': [opt_bool, False, _('Hides the group chat occupants list in group chat window.')],
            'chat_merge_consecutive_nickname': [opt_bool, False, _('In a chat, show the nickname at the beginning of a line only when it\'s not the same person talking than in previous message.')],
            'chat_merge_consecutive_nickname_indent': [opt_str, '  ', _('Indentation when using merge consecutive nickname.')],
            'use_smooth_scrolling': [opt_bool, True, _('Smooth scroll message in conversation window')],
            'gc_nicknames_colors': [ opt_str, '#4e9a06:#f57900:#ce5c00:#3465a4:#204a87:#75507b:#5c3566:#c17d11:#8f5902:#ef2929:#cc0000:#a40000', _('List of colors, separated by ":", that will be used to color nicknames in group chats.'), True ],
            'ctrl_tab_go_to_next_composing': [opt_bool, True, _('Ctrl-Tab go to next composing tab when none is unread.')],
            'confirm_metacontacts': [ opt_str, '', _('Should we show the confirm metacontacts creation dialog or not? Empty string means we never show the dialog.')],
            'confirm_block': [ opt_str, '', _('Should we show the confirm block contact dialog or not? Empty string means we never show the dialog.')],
            'confirm_custom_status': [ opt_str, '', _('Should we show the confirm custom status dialog or not? Empty string means we never show the dialog.')],
            'enable_negative_priority': [ opt_bool, False, _('If True, you will be able to set a negative priority to your account in account modification window. BE CAREFUL, when you are logged in with a negative priority, you will NOT receive any message from your server.')],
            'use_gnomekeyring': [opt_bool, True, _('If True, Gajim will use Gnome Keyring (if available) to store account passwords.')],
            'use_kwalletcli': [opt_bool, True, _('If True, Gajim will use KDE Wallet (if kwalletcli is available) to store account passwords.')],
            'show_contacts_number': [opt_bool, True, _('If True, Gajim will show number of online and total contacts in account and group rows.')],
            'treat_incoming_messages': [ opt_str, '', _('Can be empty, \'chat\' or \'normal\'. If not empty, treat all incoming messages as if they were of this type')],
            'scroll_roster_to_last_message': [opt_bool, True, _('If True, Gajim will scroll and select the contact who sent you the last message, if chat window is not already opened.')],
            'change_status_window_timeout': [opt_int, 15, _('Time of inactivity needed before the change status window closes down.')],
            'max_conversation_lines': [opt_int, 500, _('Maximum number of lines that are printed in conversations. Oldest lines are cleared.')],
            'attach_notifications_to_systray': [opt_bool, False, _('If True, notification windows from notification-daemon will be attached to notification icon.')],
            'check_idle_every_foo_seconds': [opt_int, 2, _('Choose interval between 2 checks of idleness.')],
            'uri_schemes': [opt_str, 'aaa:// aaas:// acap:// cap:// cid: crid:// data: dav: dict:// dns: fax: file:/ ftp:// geo: go: gopher:// h323: http:// https:// iax: icap:// im: imap:// info: ipp:// iris: iris.beep: iris.xpc: iris.xpcs: iris.lwz: ldap:// mid: modem: msrp:// msrps:// mtqp:// mupdate:// news: nfs:// nntp:// opaquelocktoken: pop:// pres: prospero:// rtsp:// service: shttp:// sip: sips: sms: snmp:// soap.beep:// soap.beeps:// tag: tel: telnet:// tftp:// thismessage:/ tip:// tv: urn:// vemmi:// xmlrpc.beep:// xmlrpc.beeps:// z39.50r:// z39.50s:// about: apt: cvs:// daap:// ed2k:// feed: fish:// git:// iax2: irc:// ircs:// ldaps:// magnet: mms:// rsync:// ssh:// svn:// sftp:// smb:// webcal://', _('Valid uri schemes. Only schemes in this list will be accepted as "real" uri. (mailto and xmpp are handled separately)'), True],
            'ask_offline_status_on_connection': [ opt_bool, False, _('Ask offline status message to all offline contacts when connection to an account is established. WARNING: This causes a lot of requests to be sent!') ],
            'shell_like_completion': [ opt_bool, False, _('If True, completion in groupchats will be like a shell auto-completion')],
            'show_self_contact': [opt_str, 'when_other_resource', _('When is self contact row displayed. Can be "always", "when_other_resource" or "never"'), True],
            'audio_input_device': [opt_str, 'autoaudiosrc ! volume name=gajim_vol'],
            'audio_output_device': [opt_str, 'autoaudiosink'],
            'video_input_device': [opt_str, 'autovideosrc ! videoscale ! ffmpegcolorspace'],
            'video_output_device': [opt_str, 'autovideosink'],
            'video_framerate': [opt_str, '', _('Optionally fix jingle output video framerate. Example: 10/1 or 25/2')],
            'video_size': [opt_str, '', _('Optionally resize jingle output video. Example: 320x240')],
            'video_see_self': [opt_bool, True, _('If True, You will also see your webcam')],
            'audio_input_volume': [opt_int, 50],
            'audio_output_volume': [opt_int, 50],
            'use_stun_server': [opt_bool, False, _('If True, Gajim will try to use a STUN server when using jingle. The one in "stun_server" option, or the one given by the jabber server.')],
            'stun_server': [opt_str, '', _('STUN server to use when using jingle')],
            'show_affiliation_in_groupchat': [opt_bool, True, _('If True, Gajim will show affiliation of groupchat occupants by adding a colored square to the status icon')],
            'global_proxy': [opt_str, '', _('Proxy used for all outgoing connections if the account does not have a specific proxy configured')],
            'ignore_incoming_attention': [opt_bool, False, _('If True, Gajim will ignore incoming attention requestd ("wizz").')],
            'remember_opened_chat_controls': [ opt_bool, True, _('If enabled, Gajim will reopen chat windows that were opened last time Gajim was closed.')],
            'positive_184_ack': [ opt_bool, False, _('If enabled, Gajim will show an icon to show that sent message has been received by your contact')],
    }, {})

    __options_per_key = {
            'accounts': ({
                    'name': [ opt_str, '', '', True ],
                    'hostname': [ opt_str, '', '', True ],
                    'anonymous_auth': [ opt_bool, False ],
                    'client_cert': [ opt_str, '', '', True ],
                    'client_cert_encrypted': [ opt_bool, False, '', False ],
                    'savepass': [ opt_bool, False ],
                    'password': [ opt_str, '' ],
                    'resource': [ opt_str, 'gajim', '', True ],
                    'priority': [ opt_int, 5, '', True ],
                    'adjust_priority_with_status': [ opt_bool, True, _('Priority will change automatically according to your status. Priorities are defined in autopriority_* options.') ],
                    'autopriority_online': [ opt_int, 50],
                    'autopriority_chat': [ opt_int, 50],
                    'autopriority_away': [ opt_int, 40],
                    'autopriority_xa': [ opt_int, 30],
                    'autopriority_dnd': [ opt_int, 20],
                    'autopriority_invisible': [ opt_int, 10],
                    'autoconnect': [ opt_bool, False, '', True ],
                    'autoconnect_as': [ opt_str, 'online', _('Status used to autoconnect as. Can be online, chat, away, xa, dnd, invisible. NOTE: this option is used only if restore_last_status is disabled'), True ],
                    'restore_last_status': [ opt_bool, False, _('If enabled, restore the last status that was used.') ],
                    'autoreconnect': [ opt_bool, True ],
                    'autoauth': [ opt_bool, False, _('If True, Contacts requesting authorization will be automatically accepted.')],
                    'active': [ opt_bool, True, _('If False, this account will be disabled and will not appear in roster window.'), True],
                    'proxy': [ opt_str, '', '', True ],
                    'keyid': [ opt_str, '', '', True ],
                    'gpg_sign_presence': [ opt_bool, True, _('If disabled, don\'t sign presences with GPG key, even if GPG is configured.') ],
                    'keyname': [ opt_str, '', '', True ],
                    'enable_esessions': [opt_bool, True, _('Enable ESessions encryption for this account.')],
                    'autonegotiate_esessions': [opt_bool, True, _('Should Gajim automatically start an encrypted session when possible?')],
                    'connection_types': [ opt_str, 'tls ssl plain', _('Ordered list (space separated) of connection type to try. Can contain tls, ssl or plain')],
                    'tls_version': [ opt_str, '1.0', '' ],
                    'cipher_list': [ opt_str, 'HIGH:!aNULL:RC4-SHA', '' ],
                    'authentication_mechanisms': [ opt_str, '', _('List (space separated) of authentication mechanisms to try. Can contain ANONYMOUS, EXTERNAL, GSSAPI, SCRAM-SHA-1-PLUS, SCRAM-SHA-1, DIGEST-MD5, PLAIN, X-MESSENGER-OAUTH2 or XEP-0078') ],
                    'action_when_plaintext_connection': [ opt_str, 'warn', _('Show a warning dialog before sending password on an plaintext connection. Can be \'warn\', \'connect\', \'disconnect\'') ],
                    'warn_when_insecure_ssl_connection': [ opt_bool, True, _('Show a warning dialog before using standard SSL library.') ],
                    'warn_when_insecure_password': [ opt_bool, True, _('Show a warning dialog before sending PLAIN password over a plain connection.') ],
                    'ssl_fingerprint_sha1': [ opt_str, '', '', True ],
                    'ssl_fingerprint_sha256': [ opt_str, '', '', True ],
                    'ignore_ssl_errors': [ opt_str, '', _('Space separated list of ssl errors to ignore.') ],
                    'use_srv': [ opt_bool, True, '', True ],
                    'use_custom_host': [ opt_bool, False, '', True ],
                    'custom_port': [ opt_int, 5222, '', True ],
                    'custom_host': [ opt_str, '', '', True ],
                    'sync_with_global_status': [ opt_bool, False, ],
                    'no_log_for': [ opt_str, '', _('Space separated list of JIDs for which you do not want to store logs. You can also add account name to log nothing for this account.')],
                    'allow_no_log_for': [ opt_str, '', _('Space separated list of JIDs for which you accept to not log conversations if he does not want to.')],
                    'minimized_gc': [ opt_str, '' ],
                    'attached_gpg_keys': [ opt_str, '' ],
                    'keep_alives_enabled': [ opt_bool, True, _('Whitespace sent after inactivity')],
                    'ping_alives_enabled': [ opt_bool, True, _('XMPP ping sent after inactivity')],
                    # send keepalive every N seconds of inactivity
                    'keep_alive_every_foo_secs': [ opt_int, 55 ],
                    'ping_alive_every_foo_secs': [ opt_int, 120 ],
                    'time_for_ping_alive_answer': [ opt_int, 60, _('How many seconds to wait for the answer of ping alive packet before we try to reconnect?') ],
                    # try for 1 minutes before giving up (aka. timeout after those seconds)
                    'try_connecting_for_foo_secs': [ opt_int, 60 ],
                    'http_auth': [opt_str, 'ask'], # yes, no, ask
                    'dont_ack_subscription': [opt_bool, False, _('Jabberd2 workaround')],
                    # proxy65 for FT
                    'file_transfer_proxies': [opt_str, 'proxy.eu.jabber.org, proxy.jabber.ru, proxy.jabbim.cz'],
                    'use_ft_proxies': [opt_bool, True, _('If checked, Gajim will use your IP and proxies defined in file_transfer_proxies option for file transfer.'), True],
                    'test_ft_proxies_on_startup': [opt_bool, True, _('If True, Gajim will test file transfer proxies on startup to be sure it works. Openfire\'s proxies are known to fail this test even if they work.')],
                    'msgwin-x-position': [opt_int, -1], # Default is to let the wm decide
                    'msgwin-y-position': [opt_int, -1], # Default is to let the wm decide
                    'msgwin-width': [opt_int, 480],
                    'msgwin-height': [opt_int, 440],
                    'listen_to_network_manager': [opt_bool, True],
                    'is_zeroconf': [opt_bool, False],
                    'last_status': [opt_str, 'online'],
                    'last_status_msg': [opt_str, ''],
                    'zeroconf_first_name': [ opt_str, '', '', True ],
                    'zeroconf_last_name': [ opt_str, '', '', True ],
                    'zeroconf_jabber_id': [ opt_str, '', '', True ],
                    'zeroconf_email': [ opt_str, '', '', True ],
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
                    'ignore_unknown_contacts': [ opt_bool, False ],
                    'send_os_info': [ opt_bool, True, _("Allow Gajim to send information about the operating system you are running.") ],
                    'send_time_info': [ opt_bool, True, _("Allow Gajim to send your local time.") ],
                    'log_encrypted_sessions': [opt_bool, True, _('When negotiating an encrypted session, should Gajim assume you want your messages to be logged?')],
                    'send_idle_time': [ opt_bool, True ],
                    'roster_version': [opt_str, ''],
                    'subscription_request_msg': [opt_str, '', _('Message that is sent to contacts you want to add')],
                    'last_archiving_time': [opt_str, '1970-01-01T00:00:00Z', _('Last time we syncronized with logs from server.')],
                    'enable_message_carbons': [ opt_bool, False, _('If enabled and if server supports this feature, Gajim will receive messages sent and received by other resources.')],
                    'ft_send_local_ips': [ opt_bool, True, _('If enabled, Gajim will send your local IPs so your contact can connect to your machine to transfer files.')],
                    'oauth2_refresh_token': [ opt_str, '', _('Latest token for Oauth2 authentication.')],
                    'oauth2_client_id': [ opt_str, '0000000044077801', _('client_id for Oauth2 authentication.')],
                    'oauth2_redirect_url': [ opt_str, 'https%3A%2F%2Fgajim.org%2Fmsnauth%2Findex.cgi', _('redirect_url for Oauth2 authentication.')],
                    'opened_chat_controls': [opt_str, '', _('Space separated list of JIDs for which we want to re-open a chat window on next startup.')],
            }, {}),
            'statusmsg': ({
                    'message': [ opt_str, '' ],
                    'activity': [ opt_str, '' ],
                    'subactivity': [ opt_str, '' ],
                    'activity_text': [ opt_str, '' ],
                    'mood': [ opt_str, '' ],
                    'mood_text': [ opt_str, '' ],
            }, {}),
            'defaultstatusmsg': ({
                    'enabled': [ opt_bool, False ],
                    'message': [ opt_str, '' ],
            }, {}),
            'soundevents': ({
                    'enabled': [ opt_bool, True ],
                    'path': [ opt_str, '' ],
            }, {}),
            'proxies': ({
                    'type': [ opt_str, 'http' ],
                    'host': [ opt_str, '' ],
                    'port': [ opt_int, 3128 ],
                    'useauth': [ opt_bool, False ],
                    'user': [ opt_str, '' ],
                    'pass': [ opt_str, '' ],
                    'bosh_uri': [ opt_str, '' ],
                    'bosh_useproxy': [ opt_bool, False ],
                    'bosh_wait': [ opt_int, 30 ],
                    'bosh_hold': [ opt_int, 2 ],
                    'bosh_content': [ opt_str, 'text/xml; charset=utf-8' ],
                    'bosh_http_pipelining': [ opt_bool, False ],
                    'bosh_wait_for_restart_response': [ opt_bool, False ],
            }, {}),
            'themes': ({
                    'accounttextcolor': [ opt_color, 'black', '', True ],
                    'accountbgcolor': [ opt_color, 'white', '', True ],
                    'accountfont': [ opt_str, '', '', True ],
                    'accountfontattrs': [ opt_str, 'B', '', True ],
                    'grouptextcolor': [ opt_color, 'black', '', True ],
                    'groupbgcolor': [ opt_color, 'white', '', True ],
                    'groupfont': [ opt_str, '', '', True ],
                    'groupfontattrs': [ opt_str, 'I', '', True ],
                    'contacttextcolor': [ opt_color, 'black', '', True ],
                    'contactbgcolor': [ opt_color, 'white', '', True ],
                    'contactfont': [ opt_str, '', '', True ],
                    'contactfontattrs': [ opt_str, '', '', True ],
                    'bannertextcolor': [ opt_color, 'black', '', True ],
                    'bannerbgcolor': [ opt_color, '', '', True ],
                    'bannerfont': [ opt_str, '', '', True ],
                    'bannerfontattrs': [ opt_str, 'B', '', True ],

                    # http://www.pitt.edu/~nisg/cis/web/cgi/rgb.html
                    'state_inactive_color': [ opt_color, 'grey62' ],
                    'state_composing_color': [ opt_color, 'green4' ],
                    'state_paused_color': [ opt_color, 'mediumblue' ],
                    'state_gone_color': [ opt_color, 'grey' ],

                    # MUC chat states
                    'state_muc_msg_color': [ opt_color, 'mediumblue' ],
                    'state_muc_directed_msg_color': [ opt_color, 'red2' ],
            }, {}),
            'contacts': ({
                    'gpg_enabled': [ opt_bool, False, _('Is OpenPGP enabled for this contact?')],
                    'autonegotiate_esessions': [opt_bool, True, _('Should Gajim automatically start an encrypted session with this contact when possible?')],
                    'speller_language': [ opt_str, '', _('Language for which we want to check misspelled words')],
            }, {}),
            'rooms': ({
                    'speller_language': [ opt_str, '', _('Language for which we want to check misspelled words')],
                    'muc_restore_lines': [opt_int, -2, _('How many lines to request from server when entering a groupchat. -1 means no limit, -2 means global value')],
                    'muc_restore_timeout': [opt_int, -2, _('How many minutes back to request logs when entering a groupchat. -1 means no limit, -2 means global value')],
            }, {}),
            'plugins': ({
                'active': [opt_bool, False, _('State whether plugins should be activated on startup (this is saved on Gajim exit). This option SHOULD NOT be used to (de)activate plug-ins. Use GUI instead.')],
            },{}),
    }

    statusmsg_default = {
            _('Sleeping'): [ 'ZZZZzzzzzZZZZZ', 'inactive', 'sleeping', '', 'sleepy', '' ],
            _('Back soon'): [ _('Back in some minutes.'), '', '', '', '', '' ],
            _('Eating'): [ _("I'm eating, so leave me a message."), 'eating', 'other', '', '', '' ],
            _('Movie'): [ _("I'm watching a movie."), 'relaxing', 'watching_a_movie', '', '', '' ],
            _('Working'): [ _("I'm working."), 'working', 'other', '', '', '' ],
            _('Phone'): [ _("I'm on the phone."), 'talking', 'on_the_phone', '', '', '' ],
            _('Out'): [ _("I'm out enjoying life."), 'relaxing', 'going_out', '', '', '' ],
            '_last_online': ['', '', '', '', '', ''],
            '_last_chat': ['', '', '', '', '', ''],
            '_last_away': ['', '', '', '', '', ''],
            '_last_xa': ['', '', '', '', '', ''],
            '_last_dnd': ['', '', '', '', '', ''],
            '_last_invisible': ['', '', '', '', '', ''],
            '_last_offline': ['', '', '', '', '', ''],
    }

    defaultstatusmsg_default = {
            'online': [ False, _("I'm available.") ],
            'chat': [ False, _("I'm free for chat.") ],
            'away': [ False, _('Be right back.') ],
            'xa': [ False, _("I'm not available.") ],
            'dnd': [ False, _('Do not disturb.') ],
            'invisible': [ False, _('Bye!') ],
            'offline': [ False, _('Bye!') ],
    }

    soundevents_default = {
            'attention_received': [True, 'attention.wav'],
            'first_message_received': [ True, 'message1.wav' ],
            'next_message_received_focused': [ True, 'message2.wav' ],
            'next_message_received_unfocused': [ True, 'message2.wav' ],
            'contact_connected': [ True, 'connected.wav' ],
            'contact_disconnected': [ True, 'disconnected.wav' ],
            'message_sent': [ True, 'sent.wav' ],
            'muc_message_highlight': [ True, 'gc_message1.wav', _('Sound to play when a group chat message contains one of the words in muc_highlight_words, or when a group chat message contains your nickname.')],
            'muc_message_received': [ False, 'gc_message2.wav', _('Sound to play when any MUC message arrives.') ],
            'gmail_received': [ False, 'message1.wav' ],
    }

    themes_default = {
            # sorted alphanum
            _('default'): [ '', '', '', 'B', '', '', '', 'I', '', '', '', '', '', '',
                    '', 'B' ],

            _('green'): [ '', '#94aa8c', '', 'B', '#0000ff', '#eff3e7',
                                    '', 'I', '#000000', '', '', '', '',
                                    '#94aa8c', '', 'B' ],

            _('grocery'): [ '', '#6bbe18', '', 'B', '#12125a', '#ceefad',
                                    '', 'I', '#000000', '#efb26b', '', '', '',
                                    '#108abd', '', 'B' ],

            _('human'): [ '', '#996442', '', 'B', '#ab5920', '#e3ca94',
                                    '', 'I', '#000000', '', '', '', '',
                                    '#996442', '', 'B' ],

            _('marine'): [ '', '#918caa', '', 'B', '', '#e9e7f3',
                                    '', 'I', '#000000', '', '', '', '',
                                    '#918caa', '', 'B' ],

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
        elif val == 'False':
            return False
        else:
            ival = self.is_valid_int(val)
            if ival:
                return True
            elif ival is None:
                return None
            return False
        return None

    def is_valid_string(self, val):
        return val

    def is_valid(self, type_, val):
        if not type_:
            return None
        if type_[0] == 'boolean':
            return self.is_valid_bool(val)
        elif type_[0] == 'integer':
            return self.is_valid_int(val)
        elif type_[0] == 'string':
            return self.is_valid_string(val)
        else:
            if re.match(type_[1], val):
                return val
            else:
                return None

    def set(self, optname, value):
        if optname not in self.__options[1]:
            return
        value = self.is_valid(self.__options[0][optname][OPT_TYPE], value)
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
        return self.__options[0][optname][OPT_VAL]

    def get_type(self, optname):
        if optname not in self.__options[0]:
            return None
        return self.__options[0][optname][OPT_TYPE][0]

    def get_desc(self, optname):
        if optname not in self.__options[0]:
            return None
        if len(self.__options[0][optname]) > OPT_DESC:
            return self.__options[0][optname][OPT_DESC]

    def get_restart(self, optname):
        if optname not in self.__options[0]:
            return None
        if len(self.__options[0][optname]) > OPT_RESTART:
            return self.__options[0][optname][OPT_RESTART]

    def add_per(self, typename, name): # per_group_of_option
        if typename not in self.__options_per_key:
            return

        opt = self.__options_per_key[typename]
        if name in opt[1]:
            # we already have added group name before
            return 'you already have added %s before' % name
        opt[1][name] = {}
        for o in opt[0]:
            opt[1][name][o] = opt[0][o][OPT_VAL]
        self._timeout_save()

    def del_per(self, typename, name, subname = None): # per_group_of_option
        if typename not in self.__options_per_key:
            return

        opt = self.__options_per_key[typename]
        if subname is None:
            del opt[1][name]
        # if subname is specified, delete the item in the group.
        elif subname in opt[1][name]:
            del opt[1][name][subname]
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
        typ = self.__options_per_key[optname][0][subname][OPT_TYPE]
        value = self.is_valid(typ, value)
        if value is None:
            return
        obj[subname] = value
        self._timeout_save()

    def get_per(self, optname, key=None, subname=None): # per_group_of_option
        if optname not in self.__options_per_key:
            return None
        dict_ = self.__options_per_key[optname][1]
        if not key:
            return list(dict_.keys())
        if key not in dict_:
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
        return dict_[subname][OPT_VAL]

    def get_type_per(self, optname, subname):
        if optname not in self.__options_per_key:
            return None
        dict_ = self.__options_per_key[optname][0]
        if subname not in dict_:
            return None
        return dict_[subname][OPT_TYPE][0]

    def get_desc_per(self, optname, key=None, subname=None):
        if optname not in self.__options_per_key:
            return None
        dict_ = self.__options_per_key[optname][0]
        if not key:
            return None
        if key not in dict_:
            return None
        obj = dict_[key]
        if not subname:
            return None
        if subname not in obj:
            return None
        if len(obj[subname]) > OPT_DESC:
            return obj[subname][OPT_DESC]
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
        if len(obj[subname]) > OPT_RESTART:
            return obj[subname][OPT_RESTART]
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

    def _init_options(self):
        for opt in self.__options[0]:
            self.__options[1][opt] = self.__options[0][opt][OPT_VAL]

    def _really_save(self):
        from common import gajim
        if gajim.interface:
            gajim.interface.save_config()
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
