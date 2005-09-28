##	common/config.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##
## Copyright (C) 2003-2005 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##


import sre
import copy
from common import i18n
_ = i18n._

OPT_TYPE = 0
OPT_VAL = 1
OPT_DESC = 2

opt_int = [ 'integer', 0 ]
opt_str = [ 'string', 0 ]
opt_bool = [ 'boolean', 0 ]
opt_color = [ 'color', '^(#[0-9a-fA-F]{6})|()$' ]

class Config:

	__options = {
		# name: [ type, value ]
		'verbose': [ opt_bool, False ],
		'alwaysauth': [ opt_bool, False ],
		'autopopup': [ opt_bool, False ],
		'notify_on_signin': [ opt_bool, True ],
		'notify_on_signout': [ opt_bool, False ],
		'notify_on_new_message': [ opt_bool, True ],
		'autopopupaway': [ opt_bool, False ],
		'ignore_unknown_contacts': [ opt_bool, False ],
		'showoffline': [ opt_bool, False ],
		'autoaway': [ opt_bool, True ],
		'autoawaytime': [ opt_int, 5, _('Time in minutes, after which your status changes to away.') ],
		'autoaway_message': [ opt_str, _('Away as a result of being idle') ],
		'autoxa': [ opt_bool, True ],
		'autoxatime': [ opt_int, 15, _('Time in minutes, after which your status changes to not available.') ],
		'autoxa_message': [ opt_str, _('Not available as a result of being idle') ],
		'ask_online_status': [ opt_bool, False ],
		'ask_offline_status': [ opt_bool, False ],
		'last_status_msg_online': [ opt_str, '' ],
		'last_status_msg_chat': [ opt_str, '' ],
		'last_status_msg_away': [ opt_str, '' ],
		'last_status_msg_xa': [ opt_str, '' ],
		'last_status_msg_dnd': [ opt_str, '' ],
		'last_status_msg_invisible': [ opt_str, '' ],
		'last_status_msg_offline': [ opt_str, '' ],
		'trayicon': [ opt_bool, True ],
		'iconset': [ opt_str, 'sun' ],
		'use_transports_iconsets': [ opt_bool, True ],
		'inmsgcolor': [ opt_color, '#a34526' ],
		'outmsgcolor': [ opt_color, '#164e6f' ],
		'statusmsgcolor': [ opt_color, '#1eaa1e' ],
		'markedmsgcolor': [ opt_color, '#ff8080' ],
		'collapsed_rows': [ opt_str, '' ],
		'roster_theme': [ opt_str, 'GTK+' ],
		'saveposition': [ opt_bool, True ],
		'mergeaccounts': [ opt_bool, False ],
		'sort_by_show': [ opt_bool, True ],
		'usetabbedchat': [ opt_bool, True ],
		'use_speller': [ opt_bool, False ],
		'print_time': [ opt_str, 'always' ],
		'useemoticons': [ opt_bool, True ],
		'show_ascii_formatting_chars': [ opt_bool, False , _('If True, do not remove */_ . So *abc* will be bold but with * * not removed.')],
		'sounds_on': [ opt_bool, True ],
		# 'aplay', 'play', 'esdplay', 'artsplay' detected first time only
		'soundplayer': [ opt_str, '' ],
		'openwith': [ opt_str, 'gnome-open' ],
		'custombrowser': [ opt_str, 'firefox' ],
		'custommailapp': [ opt_str, 'mozilla-thunderbird -compose' ],
		'custom_file_manager': [ opt_str, 'xffm' ],
		'gc-x-position': [opt_int, 0],
		'gc-y-position': [opt_int, 0],
		'gc-width': [opt_int, 675],
		'gc-height': [opt_int, 400],
		'gc-hpaned-position': [opt_int, 540],
		'gc_refer_to_nick_char': [opt_str, ','],
		'chat-x-position': [opt_int, 0],
		'chat-y-position': [opt_int, 0],
		'chat-width': [opt_int, 480],
		'chat-height': [opt_int, 440],
		'roster_x-position': [ opt_int, 0 ],
		'roster_y-position': [ opt_int, 0 ],
		'roster_width': [ opt_int, 150 ],
		'roster_height': [ opt_int, 400 ],
		'latest_disco_addresses': [ opt_str, '' ],
		'recently_groupchat': [ opt_str, '' ],
		'before_time': [ opt_str, '[' ],
		'after_time': [ opt_str, ']' ],
		'before_nickname': [ opt_str, '' ],
		'after_nickname': [ opt_str, ':' ],
		'send_os_info': [ opt_bool, True ],
		'check_for_new_version': [ opt_bool, False ],
		'usegpg': [ opt_bool, False ],
		'use_gpg_agent': [ opt_bool, False ],
		'log_notif_in_user_file': [ opt_bool, True ],
		'log_notif_in_sep_file': [ opt_bool, True ],
		'change_roster_title': [ opt_bool, True, _('Add * and [n] in roster title?')],
		'restore_lines': [opt_int, 4, _('How many lines to remember from previous conversation when a chat tab/window is reopened.')],
		'restore_timeout': [opt_int, 60, _('How many minutes should last lines from previous conversation last.')],
		'send_on_ctrl_enter': [opt_bool, False, _('Send message on Ctrl+Enter and with Enter make new line (Mirabilis ICQ Client default behaviour).')],
		'show_roster_on_startup': [opt_bool, True],
		'key_up_lines': [opt_int, 25, _('How many lines to store for key up.')],
		'version': [ opt_str, '0.9' ], # which version created the config
		'always_compact_view_chat': [opt_bool, False, _('Use compact view when you open a chat window')],
		'always_compact_view_gc': [opt_bool, False, _('Use compact view when you open a group chat window')],
		'search_engine': [opt_str, 'http://www.google.com/search?&q=%s&sourceid=gajim'],
		'dictionary_url': [opt_str, 'WIKTIONARY', _("Either custom url with %s in it where %s is the word/phrase or 'WIKTIONARY' which means use wiktionary.")],
		'always_english_wikipedia': [opt_bool, False],
		'always_english_wiktionary': [opt_bool, False],
		'use_dbus': [opt_bool, True, _('Allow controlling Gajim via D-Bus service.')],
		'chat_state_notifications': [opt_str, 'all'], # 'all', 'composing_only', 'disabled'
		'autodetect_browser_mailer': [opt_bool, True],
		'print_ichat_every_foo_minutes': [opt_int, 5],
		'confirm_close_muc': [opt_bool, True, _('Ask before closing a group chat tab/window.')],
		'notify_on_file_complete': [opt_bool, True], # notif. on file complete
		'file_transfers_port': [opt_int, 28011],  # port, used for file transfers
		'ft_override_host_to_send': [opt_str, '', _('Overrides the host we send for File Transfer in case of address translation/port forwarding.')], 
		'conversation_font': [opt_str, ''],
		'use_kib_mib': [opt_bool, False, _('IEC standard says KiB = 1024 bytes, KB = 1000 bytes.')],
		'notify_on_all_muc_messages': [opt_bool, False],
		'trayicon_notification_on_new_messages': [opt_bool, True],
		'last_save_dir': [opt_str, ''],
		'last_send_dir': [opt_str, ''],
		'last_emoticons_dir': [opt_str, ''],
		'last_sounds_dir': [opt_str, ''],
		'tabs_position': [opt_str, 'top'],
		'tabs_always_visible': [opt_bool, False, _('Show tab when only one conversation?')],
		'tabs_border': [opt_bool, False, _('Show tab border if one conversation?')],
		'tabs_close_button': [opt_bool, True, _('Show close button in tab?')],
		'avatar_width': [opt_int, 52],
		'avatar_height': [opt_int, 52],
		'quit_on_roster_x_button': [opt_bool, False, _('If True, quits Gajim when X button of Window Manager is clicked. This option make sense only if trayicon is used.')],
		'set_xmpp://_handler_everytime': [opt_bool, False, _('If True, Gajim registers for xmpp:// on each startup.')],
		'show_unread_tab_icon': [opt_bool, False, _('If True, Gajim will display an icon on each tab containing unread messages. Depending on the theme, this icon may be animated.')],
	}

	__options_per_key = {
		'accounts': ({
			'name': [ opt_str, '' ],
			'hostname': [ opt_str, '' ],
			'savepass': [ opt_bool, False ],
			'password': [ opt_str, '' ],
			'resource': [ opt_str, 'gajim' ],
			'priority': [ opt_int, 5 ],
			'autoconnect': [ opt_bool, False ],
			'autoreconnect': [ opt_bool, True ],
			'active': [ opt_bool, True],
			'proxy': [ opt_str, '' ],
			'keyid': [ opt_str, '' ],
			'keyname': [ opt_str, '' ],
			'usessl': [ opt_bool, False ],
			'use_srv': [ opt_bool, True ],
			'use_custom_host': [ opt_bool, False ],
			'custom_port': [ opt_int, 5222 ],
			'custom_host': [ opt_str, '' ],
			'savegpgpass': [ opt_bool, False ],
			'gpgpassword': [ opt_str, '' ],
			'sync_with_global_status': [ opt_bool, False ],
			'no_log_for': [ opt_str, '' ],
			'attached_gpg_keys': [ opt_str, '' ],
			'keep_alives_enabled': [ opt_bool, True],
			# send keepalive every N seconds of inactivity
			'keep_alive_every_foo_secs': [ opt_int, 55 ],
			# try for 2 minutes before giving up (aka. timeout after those seconds)
			'try_connecting_for_foo_secs': [ opt_int, 60 ],
			'max_stanza_per_sec': [ opt_int, 5],
			'http_auth': [opt_str, 'ask'], # yes, no, ask
			# proxy65 for FT
			'file_transfer_proxies': [opt_str, 
			'proxy.jabber.org, proxy65.jabber.autocom.pl, proxy.jabber.cd.chalmers.se, proxy.netlab.cz', 'proxy65.jabber.ccc.de','proxy65.unstable.nl'] 
		}, {}),
		'statusmsg': ({
			'message': [ opt_str, '' ],
		}, {}),
		'emoticons': ({
			'path': [ opt_str, '' ],
		}, {}),
		'soundevents': ({
			'enabled': [ opt_bool, True ],
			'path': [ opt_str, '' ],
		}, {}),
		'proxies': ({
			'type': [ opt_str, 'http' ],
			'host': [ opt_str, '' ],
			'port': [ opt_int, 3128 ],
			'user': [ opt_str, '' ],
			'pass': [ opt_str, '' ],
		}, {}),
		'ft_proxies65_cache': ({
			'host': [ opt_str, ''],
			'port': [ opt_str, '7777'],
			'jid': [ opt_str, ''],
		}, {}),
		'themes': ({
			'accounttextcolor': [ opt_color, 'black' ],
			'accountbgcolor': [ opt_color, 'white' ],
			'accountfont': [ opt_str, '' ],
			'accountfontattrs': [ opt_str, 'B' ],
			'grouptextcolor': [ opt_color, 'black' ],
			'groupbgcolor': [ opt_color, 'white' ],
			'groupfont': [ opt_str, '' ],
			'groupfontattrs': [ opt_str, 'I' ],
			'contacttextcolor': [ opt_color, 'black' ],
			'contactbgcolor': [ opt_color, 'white' ],
			'contactfont': [ opt_str, '' ],
			'contactfontattrs': [ opt_str, '' ],
			'bannertextcolor': [ opt_color, 'black' ],
			'bannerbgcolor': [ opt_color, '' ],

			# http://www.pitt.edu/~nisg/cis/web/cgi/rgb.html
			# FIXME: not black but the default color from gtk+ theme
			'state_unread_color': [ opt_color, 'black' ],
			'state_active_color': [ opt_color, 'black' ],
			'state_inactive_color': [ opt_color, 'grey62' ],
			'state_composing_color': [ opt_color, 'green4' ],
			'state_paused_color': [ opt_color, 'mediumblue' ],
			'state_gone_color': [ opt_color, 'grey' ],

			# MUC chat states
			'state_muc_msg': [ opt_color, 'mediumblue' ],
			'state_muc_directed_msg': [ opt_color, 'red2' ],
		}, {}),
	}

	emoticons_default = {
		':-)': '../data/emoticons/smile.png',
		'(@)': '../data/emoticons/pussy.png',
		'8)': '../data/emoticons/coolglasses.png',
		':(': '../data/emoticons/unhappy.png',
		':)': '../data/emoticons/smile.png',
		':/': '../data/emoticons/frowning.png',
		'(})': '../data/emoticons/hugleft.png',
		':$': '../data/emoticons/blush.png',
		'(Y)': '../data/emoticons/yes.png',
		':-@': '../data/emoticons/angry.png',
		':-D': '../data/emoticons/biggrin.png',
		'(U)': '../data/emoticons/brheart.png',
		'(F)': '../data/emoticons/flower.png',
		':-[': '../data/emoticons/bat.png',
		':>': '../data/emoticons/biggrin.png',
		'(T)': '../data/emoticons/phone.png',
		':-S': '../data/emoticons/frowning.png',
		':-P': '../data/emoticons/tongue.png',
		'(H)': '../data/emoticons/coolglasses.png',
		'(D)': '../data/emoticons/drink.png',
		':-O': '../data/emoticons/oh.png',
		'(C)': '../data/emoticons/coffee.png',
		'({)': '../data/emoticons/hugright.png',
		'(*)': '../data/emoticons/star.png',
		'B-)': '../data/emoticons/coolglasses.png',
		'(Z)': '../data/emoticons/boy.png',
		'(E)': '../data/emoticons/mail.png',
		'(N)': '../data/emoticons/no.png',
		'(P)': '../data/emoticons/photo.png',
		'(K)': '../data/emoticons/kiss.png',
		'(R)': '../data/emoticons/rainbow.png',
		':-|': '../data/emoticons/stare.png',
		';-)': '../data/emoticons/wink.png',
		';-(': '../data/emoticons/cry.png',
		'(6)': '../data/emoticons/devil.png',
		'(L)': '../data/emoticons/heart.png',
		'(W)': '../data/emoticons/brflower.png',
		':|': '../data/emoticons/stare.png',
		':O': '../data/emoticons/oh.png',
		';)': '../data/emoticons/wink.png',
		';(': '../data/emoticons/cry.png',
		':S': '../data/emoticons/frowning.png',
		';\'-(': '../data/emoticons/cry.png',
		':-(': '../data/emoticons/unhappy.png',
		'8-)': '../data/emoticons/coolglasses.png',
		'(B)': '../data/emoticons/beer.png',
		':D': '../data/emoticons/biggrin.png',
		'(8)': '../data/emoticons/music.png',
		':@': '../data/emoticons/angry.png',
		'B)': '../data/emoticons/coolglasses.png',
		':-$': '../data/emoticons/blush.png',
		':\'(': '../data/emoticons/cry.png',
		':->': '../data/emoticons/biggrin.png',
		':[': '../data/emoticons/bat.png',
		'(I)': '../data/emoticons/lamp.png',
		':P': '../data/emoticons/tongue.png',
		'(%)': '../data/emoticons/cuffs.png',
		'(S)': '../data/emoticons/moon.png',
	}

	statusmsg_default = {
		_('Sleeping'): 'ZZZZzzzzzZZZZZ',
		_('Back soon'): _('Back in some minutes.'),
		_('Eating'): _("I'm eating, so leave me a message."),
		_('Movie'): _("I'm watching a movie."),
		_('Working'): _("I'm working."),
		_('Phone'): _("I'm on the phone."),
		_('Out'): _("I'm out enjoying life"),
	}

	soundevents_default = {
		'first_message_received': [ True, '../data/sounds/message1.wav' ],
		'next_message_received': [ True, '../data/sounds/message2.wav' ],
		'contact_connected': [ True, '../data/sounds/connected.wav' ],
		'contact_disconnected': [ True, '../data/sounds/disconnected.wav' ],
		'message_sent': [ True, '../data/sounds/sent.wav' ],
	}

	themes_default = {
		'GTK+': [ '', '', '', 'B', '', '','', 'I', '', '', '', '', '','' ],
		'green': [ '#ffffff', '#94aa8c', '', 'B', '#0000ff', '#eff3e7',
					'', 'I', '#000000', '#ffffff', '', '', '#ffffff',
					'#94aa8c' ],
		'cyan': [ '#ff0000', '#9fdfff', '', 'B', '#0000ff', '#ffffff',
					'', 'I', '#000000', '#ffffff', '', '', '#ffffff',
					'#9fdfff' ],
		'marine': [ '#ffffff', '#918caa', '', 'B', '#0000ff', '#e9e7f3',
					'', 'I', '#000000', '#ffffff', '', '', '#ffffff',
					'#918caa' ],
		'human': [ '#ffffff', '#996442', '', 'B', '#ab5920', '#e3ca94',
					'', 'I', '#000000', '#ffffff', '', '', '#ffffff',
					'#996442' ],
	}
	
	ft_proxies65_default = {
		'proxy.jabber.org': [ '208.245.212.98', '7777', 'proxy.jabber.org' ],
		'proxy65.jabber.autocom.pl': ['213.134.161.52', '7777', 'proxy65.jabber.autocom.pl'],
		'proxy.jabber.cd.chalmers.se': ['129.16.79.37', '7777', 'proxy.jabber.cd.chalmers.se'],
		'proxy.netlab.cz': ['82.119.241.3', '7777', 'proxy.netlab.cz'],
		'proxy65.jabber.ccc.de': ['217.10.10.196', '7777', 'proxy65.jabber.ccc.de'],
		'proxy65.unstable.nl': ['84.107.143.192', '7777', 'proxy65.unstable.nl'],
	}

	def foreach(self, cb, data = None):
		for opt in self.__options:
			cb(data, opt, None, self.__options[opt])
		for opt in self.__options_per_key:
			cb(data, opt, None, None)
			dict = self.__options_per_key[opt][1]
			for opt2 in dict.keys():
				cb(data, opt2, [opt], None)
				for opt3 in dict[opt2]:
					cb(data, opt3, [opt, opt2], dict[opt2][opt3])

	def is_valid_int(self, val):
		try:
			ival = int(val)
		except:
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

	def is_valid(self, type, val):
		if not type:
			return None
		if type[0] == 'boolean':
			return self.is_valid_bool(val)
		elif type[0] == 'integer':
			return self.is_valid_int(val)
		elif type[0] == 'string':
			return self.is_valid_string(val)
		else:
			if sre.match(type[1], val):
				return val
			else:
				return None

	def set(self, optname, value):
		if not self.__options.has_key(optname):
#			raise RuntimeError, 'option %s does not exist' % optname
			return
		opt = self.__options[optname]
		value = self.is_valid(opt[OPT_TYPE], value)
		if value is None:
#			raise RuntimeError, 'value of %s cannot be None' % optname
			return

		opt[OPT_VAL] = value

	def get(self, optname = None):
		if not optname:
			return self.__options.keys()
		if not self.__options.has_key(optname):
			return None
		return self.__options[optname][OPT_VAL]
		
	def get_desc(self, optname):
		if not self.__options.has_key(optname):
			return None
		if len(self.__options[optname]) > OPT_DESC:
			return self.__options[optname][OPT_DESC]

	def add_per(self, typename, name): # per_group_of_option
		if not self.__options_per_key.has_key(typename):
#			raise RuntimeError, 'option %s does not exist' % typename
			return
		
		opt = self.__options_per_key[typename]
		if opt[1].has_key(name):
			# we already have added group name before
			return 'you already have added %s before' % name
		opt[1][name] = copy.deepcopy(opt[0])

	def del_per(self, typename, name, subname = None): # per_group_of_option
		if not self.__options_per_key.has_key(typename):
#			raise RuntimeError, 'option %s does not exist' % typename
			return

		opt = self.__options_per_key[typename]
		if subname is None:
			del opt[1][name]
		# if subname is specified, delete the item in the group.	
		elif opt[1][name].has_key(subname):
			del opt[1][name][subname]

	def set_per(self, optname, key, subname, value): # per_group_of_option
		if not self.__options_per_key.has_key(optname):
#			raise RuntimeError, 'option %s does not exist' % optname
			return
		dict = self.__options_per_key[optname][1]
		if not dict.has_key(key):
#			raise RuntimeError, '%s is not a key of %s' % (key, dict)
			return
		obj = dict[key]
		if not obj.has_key(subname):
#			raise RuntimeError, '%s is not a key of %s' % (subname, obj)
			return
		subobj = obj[subname]
		value = self.is_valid(subobj[OPT_TYPE], value)
		if value is None:
#			raise RuntimeError, '%s of %s cannot be None' % optname
			return
		subobj[OPT_VAL] = value

	def get_per(self, optname, key = None, subname = None): # per_group_of_option
		if not self.__options_per_key.has_key(optname):
			return None
		dict = self.__options_per_key[optname][1]
		if not key:
			return dict.keys()
		if not dict.has_key(key):
			return None
		obj = dict[key]
		if not subname:
			return obj
		if not obj.has_key(subname):
			return None
		return obj[subname][OPT_VAL]

	def __init__(self):
		#init default values
		for event in self.soundevents_default:
			default = self.soundevents_default[event]
			self.add_per('soundevents', event)
			self.set_per('soundevents', event, 'enabled', default[0])
			self.set_per('soundevents', event, 'path', default[1])

		# set initial cache values for proxie65 hosts
		for proxy in self.ft_proxies65_default:
			default = self.ft_proxies65_default[proxy]
			self.add_per('ft_proxies65_cache', proxy)
			self.set_per('ft_proxies65_cache', proxy, 'host', default[0])
			self.set_per('ft_proxies65_cache', proxy, 'port', default[1])
			self.set_per('ft_proxies65_cache', proxy, 'jid', default[2])
		return
