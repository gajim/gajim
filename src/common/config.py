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


import re
import copy

OPT_TYPE = 0
OPT_VAL = 1

opt_int = [ 'integer', 0 ]
opt_str = [ 'string', 0 ]
opt_bool = [ 'boolean', 0 ]
opt_color = [ 'color', '^#[0-9a-fA-F]{6}$' ]

class Config:

	__options = {
		# name: [ type, value ]
		'log': [ opt_bool, True ],
		'delauth': [ opt_bool, True ],
		'delroster': [ opt_bool, True ],
		'alwaysauth': [ opt_bool, False ],
		'autopopup': [ opt_bool, False ],
		'autopopupaway': [ opt_bool, False ],
		'ignore_unknown_contacts': [ opt_bool, False ],
		'showoffline': [ opt_bool, False ],
		'autoaway': [ opt_bool, True ],
		'autoawaytime': [ opt_int, 10 ],
		'autoxa': [ opt_bool, True ],
		'autoxatime': [ opt_int, 20 ],
		'ask_online_status': [ opt_bool, False ],
		'ask_offline_status': [ opt_bool, False ],
		'last_msg': [ opt_str, '' ],
		'trayicon': [ opt_bool, True ],
		'iconset': [ opt_str, 'sun' ],
		'inmsgcolor': [ opt_color, '#ff0000' ],
		'outmsgcolor': [ opt_color, '#0000ff' ],
		'statusmsgcolor': [ opt_color, '#1eaa1e' ],
		'hiddenlines': [ opt_str, '' ],
		'accounttextcolor': [ opt_color, '#ffffff' ],
		'accountbgcolor': [ opt_color, '#94aa8c' ],
		'accountfont': [ opt_str, 'Sans Bold 10' ],
		'grouptextcolor': [ opt_color, '#0000ff' ],
		'groupbgcolor': [ opt_color, '#eff3e7' ],
		'groupfont': [ opt_str, 'Sans Italic 10' ],
		'usertextcolor': [ opt_color, '#000000' ],
		'userbgcolor': [ opt_color, '#ffffff' ],
		'userfont': [ opt_str, 'Sans 10' ],
		'saveposition': [ opt_bool, True ],
		'mergeaccounts': [ opt_bool, False ],
		'usetabbedchat': [ opt_bool, True ],
		'print_time': [ opt_str, 'always' ],
		'useemoticons': [ opt_bool, True ],
		'sounds_on': [ opt_bool, True ],
		'soundplayer': [ opt_str, 'play' ],
		'openwith': [ opt_str, 'gnome-open' ],
		'custombrowser': [ opt_str, 'firefox' ],
		'custommailapp': [ opt_str, 'mozilla-thunderbird -compose' ],
		'x-position': [ opt_int, 0 ],
		'y-position': [ opt_int, 0 ],
		'width': [ opt_int, 150 ],
		'height': [ opt_int, 400 ],
		'latest_disco_addresses': [ opt_str, '' ],
		'recently_groupchat': [ opt_str, '' ],
		'before_time': [ opt_str, '[' ],
		'after_time': [ opt_str, ']' ],
		'before_nickname': [ opt_str, '<' ],
		'after_nickname': [ opt_str, '>' ],
		'do_not_send_os_info': [ opt_bool, False ],
		'usegpg': [ opt_bool, False ],
		'lognotusr': [ opt_bool, True ],
		'lognotsep': [ opt_bool, True ],
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
			'use_proxy': [ opt_bool, False ],
			'proxyhost': [ opt_str, '' ],
			'proxyport': [ opt_int, 3128 ],
			'keyid': [ opt_str, '' ],
			'keyname': [ opt_str, '' ],
			'savegpgpass': [ opt_bool, False ],
			'gpgpassword': [ opt_str, '' ],
			'sync_with_global_status': [ opt_bool, True ],
			'no_log_for': [ opt_str, '' ],
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
	}

	emoticons_default = {
		':-)': 'plugins/gtkgui/emoticons/smile.png',
		'(@)': 'plugins/gtkgui/emoticons/pussy.png',
		'8)': 'plugins/gtkgui/emoticons/coolglasses.png',
		':(': 'plugins/gtkgui/emoticons/unhappy.png',
		':)': 'plugins/gtkgui/emoticons/smile.png',
		'(})': 'plugins/gtkgui/emoticons/hugleft.png',
		':$': 'plugins/gtkgui/emoticons/blush.png',
		'(Y)': 'plugins/gtkgui/emoticons/yes.png',
		':-@': 'plugins/gtkgui/emoticons/angry.png',
		':-D': 'plugins/gtkgui/emoticons/biggrin.png',
		'(U)': 'plugins/gtkgui/emoticons/brheart.png',
		'(F)': 'plugins/gtkgui/emoticons/flower.png',
		':-[': 'plugins/gtkgui/emoticons/bat.png',
		':>': 'plugins/gtkgui/emoticons/biggrin.png',
		'(T)': 'plugins/gtkgui/emoticons/phone.png',
		':-S': 'plugins/gtkgui/emoticons/frowing.png',
		':-P': 'plugins/gtkgui/emoticons/tongue.png',
		'(H)': 'plugins/gtkgui/emoticons/coolglasses.png',
		'(D)': 'plugins/gtkgui/emoticons/drink.png',
		':-O': 'plugins/gtkgui/emoticons/oh.png',
		'(C)': 'plugins/gtkgui/emoticons/coffee.png',
		'({)': 'plugins/gtkgui/emoticons/hugright.png',
		'(*)': 'plugins/gtkgui/emoticons/star.png',
		'B-)': 'plugins/gtkgui/emoticons/coolglasses.png',
		'(Z)': 'plugins/gtkgui/emoticons/boy.png',
		'(E)': 'plugins/gtkgui/emoticons/mail.png',
		'(N)': 'plugins/gtkgui/emoticons/no.png',
		'(P)': 'plugins/gtkgui/emoticons/photo.png',
		'(K)': 'plugins/gtkgui/emoticons/kiss.png',
		'(R)': 'plugins/gtkgui/emoticons/rainbow.png',
		':-|': 'plugins/gtkgui/emoticons/stare.png',
		';-)': 'plugins/gtkgui/emoticons/wink.png',
		';-(': 'plugins/gtkgui/emoticons/cry.png',
		'(6)': 'plugins/gtkgui/emoticons/devil.png',
		'(L)': 'plugins/gtkgui/emoticons/heart.png',
		'(W)': 'plugins/gtkgui/emoticons/brflower.png',
		':|': 'plugins/gtkgui/emoticons/stare.png',
		':O': 'plugins/gtkgui/emoticons/oh.png',
		';)': 'plugins/gtkgui/emoticons/wink.png',
		';(': 'plugins/gtkgui/emoticons/cry.png',
		':S': 'plugins/gtkgui/emoticons/frowing.png',
		';\'-(': 'plugins/gtkgui/emoticons/cry.png',
		':-(': 'plugins/gtkgui/emoticons/unhappy.png',
		'8-)': 'plugins/gtkgui/emoticons/coolglasses.png',
		'(B)': 'plugins/gtkgui/emoticons/beer.png',
		':D': 'plugins/gtkgui/emoticons/biggrin.png',
		'(8)': 'plugins/gtkgui/emoticons/music.png',
		':@': 'plugins/gtkgui/emoticons/angry.png',
		'B)': 'plugins/gtkgui/emoticons/coolglasses.png',
		':-$': 'plugins/gtkgui/emoticons/blush.png',
		':\'(': 'plugins/gtkgui/emoticons/cry.png',
		':->': 'plugins/gtkgui/emoticons/biggrin.png',
		':[': 'plugins/gtkgui/emoticons/bat.png',
		'(I)': 'plugins/gtkgui/emoticons/lamp.png',
		':P': 'plugins/gtkgui/emoticons/tongue.png',
		'(%)': 'plugins/gtkgui/emoticons/cuffs.png',
		'(S)': 'plugins/gtkgui/emoticons/moon.png',
	}

	statusmsg_default = {
		'Nap': 'I\'m taking a nap.'
		'Brb': 'Back in some minutes.'
		'Eating': 'so leave me a message.'
		'Movie' : 'I\'m watching a movie.' 
		'Working': 'I\'m working.'
	}

	soundevents_default = {
		'first_message_received': [ True, 'sounds/message1.wav' ],
		'next_message_received': [ True, 'sounds/message2.wav' ],
		'contact_connected': [ True, 'sounds/connected.wav' ],
		'contact_disconnected': [ True, 'sounds/disconnected.wav' ],
		'message_sent': [ True, 'sounds/sent.wav' ],
	}

	def foreach(self, func):
		for opt in self.__options:
			func(opt, None, self.__options[opt])
		for opt in self.__options_per_key:
			func(opt, None, None)
			dict = self.__options_per_key[opt][1]
			for opt2 in dict.keys():
				func(opt2, [opt], None)
				for opt3 in dict[opt2]:
					func(opt3, [opt, opt2], dict[opt2][opt3])

	def is_valid_int(self, val):
		try:
			ival = int(val)
		except:
			return 0
		return 1

	def is_valid_bool(self, val):
		if self.is_valid_int(val):
			if int(val) == 0 or int(val) == 1:
				return 1
			return 0
		return 0

	def is_valid_string(self, val):
		return 1
		
	def is_valid(self, type, val):
		if type[0] == 'boolean':
			return self.is_valid_bool(val)
		elif type[0] == 'integer':
			return self.is_valid_int(val)
		elif type[0] == 'string':
			return self.is_valid_string(val)
		else:
			return re.match(type[1], val)

	def set(self, optname, value):
		if not self.__options.has_key(optname):
			print 'error: option %s doesn\'t exist' % (optname)
			return -1
		opt = self.__options[optname]

		if not self.is_valid(opt[OPT_TYPE], value):
			return -1
		opt[OPT_VAL] = value
		return 0
	
	def get(self, optname):
		if not self.__options.has_key(optname):
			return None
		return self.__options[optname][OPT_VAL]

	def add_per(self, typename, name):
		if not self.__options_per_key.has_key(typename):
			print 'error: option %s doesn\'t exist' % (typename)
			return -1
		
		opt = self.__options_per_key[typename]
		
		opt[1][name] = copy.deepcopy(opt[0])

	def del_per(self, typename, name):
		if not self.__options_per_key.has_key(typename):
			print 'error: option %s doesn\'t exist' % (typename)
			return -1
		
		opt = self.__options_per_key[typename]
		del opt[1][name]

	def set_per(self, optname, key, subname, value):
		if not self.__options_per_key.has_key(optname):
			print 'error: option %s doesn\'t exist' % (optname)
			return -1
		dict = self.__options_per_key[optname][1]
		if not dict.has_key(key):
			return -1
		obj = dict[key]
		if not obj.has_key(subname):
			return -1
		subobj = obj[subname]
		if not self.is_valid(subobj[OPT_TYPE], value):
			return -1
		subobj[OPT_VAL] = value
		return 0
		
	def get_per(self, optname, key = None, subname = None):
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
		for event in soundevents_default:
			default = soundevents_default[o]
			config.add_per('soundevents', event)
			config.set_per('soundevents', event, 'enable', default[0])
			config.set_per('soundevents', event, 'path', default[1])
		for emot in emoticons_default:
			config.add_per('emoticons', emot)
			config.set_per('emoticons', emot, 'path', emoticons_default[emot])
		for msg in statusmsg_default:
			config.add_per('statusmsg', msg)
			config.set_per('statusmsg', msg, 'message', statusmsg_default[msg])
		return
