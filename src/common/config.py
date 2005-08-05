##	common/config.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <nkour@jabber.org>
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

opt_int = [ 'integer', 0 ]
opt_str = [ 'string', 0 ]
opt_bool = [ 'boolean', 0 ]
opt_color = [ 'color', '^#[0-9a-fA-F]{6}$' ]

class Config:

	__options = {
		# name: [ type, value ]
		'verbose': [ opt_bool, False ],
		'delauth': [ opt_bool, True ],
		'delroster': [ opt_bool, True ],
		'alwaysauth': [ opt_bool, False ],
		'autopopup': [ opt_bool, False ],
		'notify_on_signin': [ opt_bool, True ],
		'notify_on_signout': [ opt_bool, False ],
		'notify_on_new_message': [ opt_bool, True ],
		'autopopupaway': [ opt_bool, False ],
		'ignore_unknown_contacts': [ opt_bool, False ],
		'showoffline': [ opt_bool, False ],
		'autoaway': [ opt_bool, True ],
		'autoawaytime': [ opt_int, 5 ],
		'autoxa': [ opt_bool, True ],
		'autoxatime': [ opt_int, 15 ],
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
		'roster_theme': [ opt_str, 'green' ],
		'saveposition': [ opt_bool, True ],
		'mergeaccounts': [ opt_bool, False ],
		'sort_by_show': [ opt_bool, True ],
		'usetabbedchat': [ opt_bool, True ],
		'use_speller': [ opt_bool, False ],
		'print_time': [ opt_str, 'always' ],
		'useemoticons': [ opt_bool, True ],
		'sounds_on': [ opt_bool, True ],
		'soundplayer': [ opt_str, 'play' ],
		'openwith': [ opt_str, 'gnome-open' ],
		'custombrowser': [ opt_str, 'firefox' ],
		'custommailapp': [ opt_str, 'mozilla-thunderbird -compose' ],
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
		'log_notif_in_user_file': [ opt_bool, True ],
		'log_notif_in_sep_file': [ opt_bool, True ],
		'change_roster_title': [ opt_bool, True ],
		'restore_lines': [opt_int, 4],
		'restore_timeout': [opt_int, 60],
		'send_on_ctrl_enter': [opt_bool, False], # send on ctrl+enter
		'show_roster_on_startup': [opt_bool, True],
		'key_up_lines': [opt_int, 25],  # how many lines to store for key up
		'version': [ opt_str, '0.8' ],
		'always_compact_view': [opt_bool, False], # initial compact view state
		'search_engine': [opt_str, 'http://www.google.com/search?&q='],
		'dictionary_url': [opt_str, 'http://dictionary.reference.com/search?q='],
		'always_english_wikipedia': [opt_bool, False],
		'use_dbus': [opt_bool, True], # allow control via dbus service
		'send_receive_chat_state_notifications': [opt_bool, True],
		'autodetect_browser_mailer': [opt_bool, True],
		'print_ichat_every_foo_minutes': [opt_int, 5],
		'confirm_close_muc': [opt_bool, True], # confirm closing MUC window
		'notify_on_file_complete': [opt_bool, True], # notif. on file complete
		'file_transfers_port': [opt_int, 28011],  # port, used for file transfers
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
			'proxy': [ opt_str, '' ],
			'keyid': [ opt_str, '' ],
			'keyname': [ opt_str, '' ],
			'usessl': [ opt_bool, False ],
			'use_custom_host': [ opt_bool, False ],
			'custom_port': [ opt_int, 5222 ],
			'custom_host': [ opt_str, '' ],
			'savegpgpass': [ opt_bool, False ],
			'gpgpassword': [ opt_str, '' ],
			'sync_with_global_status': [ opt_bool, False ],
			'no_log_for': [ opt_str, '' ],
			'attached_gpg_keys': [ opt_str, '' ],
			'keep_alives_enabled': [ opt_bool, True],
			# send keepalive every 60 seconds of inactivity
			'keep_alive_every_foo_secs': [ opt_int, 55 ],
			# disconnect if 2 minutes have passed and server didn't reply
			'keep_alive_disconnect_after_foo_secs': [ opt_int, 120 ],
			# try for 2 minutes before giving up (aka. timeout after those seconds)
			'try_connecting_for_foo_secs': [ opt_int, 60 ],
			'max_stanza_per_sec': [ opt_int, 5],
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
		'themes': ({
			'accounttextcolor': [ opt_color, '' ],
			'accountbgcolor': [ opt_color, '' ],
			'accountfont': [ opt_str, '' ],
			'grouptextcolor': [ opt_color, '' ],
			'groupbgcolor': [ opt_color, '' ],
			'groupfont': [ opt_str, '' ],
			'contacttextcolor': [ opt_color, '' ],
			'contactbgcolor': [ opt_color, '' ],
			'contactfont': [ opt_str, '' ],
			'bannertextcolor': [ opt_color, '' ],
			'bannerbgcolor': [ opt_color, '' ],
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
		'green': [ '#ffffff', '#94aa8c', 'Sans Bold 10', '#0000ff', '#eff3e7',
					'Sans Italic 10', '#000000', '#ffffff', 'Sans 10', '#ffffff',
					'#94aa8c' ],
		'cyan': [ '#ff0000', '#9fdfff', 'Sans Bold 10', '#0000ff', '#ffffff',
					'Sans Italic 10', '#000000', '#ffffff', 'Sans 10', '#ffffff',
					'#9fdfff' ],
		'marine': [ '#ffffff', '#918caa', 'Sans Bold 10', '#0000ff', '#e9e7f3',
					'Sans Italic 10', '#000000', '#ffffff', 'Sans 10', '#ffffff',
					'#918caa' ],
		'human': [ '#ffffff', '#996442', 'Sans Bold 10', '#ab5920', '#e3ca94',
					'Sans Italic 10', '#000000', '#ffffff', 'Sans 10', '#ffffff',
					'#996442' ],
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
			raise RuntimeError, 'option %s does not exist' % optname
		opt = self.__options[optname]
		value = self.is_valid(opt[OPT_TYPE], value)
		if value is None:
			raise RuntimeError, 'value of %s cannot be None' % optname

		opt[OPT_VAL] = value

	def get(self, optname = None):
		if not optname:
			return self.__options.keys()
		if not self.__options.has_key(optname):
			return None
		return self.__options[optname][OPT_VAL]

	def add_per(self, typename, name): # per_group_of_option
		if not self.__options_per_key.has_key(typename):
			raise RuntimeError, 'option %s does not exist' % typename
		
		opt = self.__options_per_key[typename]
		if opt[1].has_key(name):
			# we already have added group name before
			return 'you already have added %s before' % name
		opt[1][name] = copy.deepcopy(opt[0])

	def del_per(self, typename, name): # per_group_of_option
		if not self.__options_per_key.has_key(typename):
			raise RuntimeError, 'option %s does not exist' % typename
		
		opt = self.__options_per_key[typename]
		del opt[1][name]

	def set_per(self, optname, key, subname, value): # per_group_of_option
		if not self.__options_per_key.has_key(optname):
			raise RuntimeError, 'option %s does not exist' % optname
		dict = self.__options_per_key[optname][1]
		if not dict.has_key(key):
			raise RuntimeError, '%s is not a key of %s' % (key, dict)
		obj = dict[key]
		if not obj.has_key(subname):
			raise RuntimeError, '%s is not a key of %s' % (subname, obj)
		subobj = obj[subname]
		value = self.is_valid(subobj[OPT_TYPE], value)
		if value is None:
			raise RuntimeError, '%s of %s cannot be None' % optname
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
		return
