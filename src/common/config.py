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

OPT_TYPE = 0
OPT_VAL = 1

opt_int = [ 'integer', 0 ]
opt_str = [ 'string', 0 ]
opt_bool = [ 'boolean', 0 ]
opt_color = [ 'color', '^#[0-9a-fA-F]{6}$' ]

class Config:

	__options = {
		# name: [ type, value ]
		'verbose': [ opt_bool, True ],
		'delauth': [ opt_bool, True ],
		'delroster': [ opt_bool, True ],
		'alwaysauth': [ opt_bool, False ],
		'autopopup': [ opt_bool, False ],
		'notify_on_online': [ opt_bool, True ],
		'notify_on_offline': [ opt_bool, False ],
		'notify_on_new_message': [ opt_bool, False ],
		'autopopupaway': [ opt_bool, False ],
		'ignore_unknown_contacts': [ opt_bool, False ],
		'showoffline': [ opt_bool, False ],
		'autoaway': [ opt_bool, True ],
		'autoawaytime': [ opt_int, 10 ],
		'autoxa': [ opt_bool, True ],
		'autoxatime': [ opt_int, 20 ],
		'ask_online_status': [ opt_bool, False ],
		'ask_offline_status': [ opt_bool, False ],
		'last_status_msg': [ opt_str, '' ],
		'trayicon': [ opt_bool, True ],
		'iconset': [ opt_str, 'sun' ],
		'inmsgcolor': [ opt_color, '#ff0000' ],
		'outmsgcolor': [ opt_color, '#0000ff' ],
		'statusmsgcolor': [ opt_color, '#1eaa1e' ],
		'hidden_rows': [ opt_str, '' ],
		'roster_theme': [ opt_str, 'green' ],
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
		'send_os_info': [ opt_bool, True ],
		'check_for_new_version': [ opt_bool, True ],
		'usegpg': [ opt_bool, False ],
		'log_notif_in_user_file': [ opt_bool, True ],
		'log_notif_in_sep_file': [ opt_bool, True ],
		'change_roster_title': [ opt_bool, True ],
		'version': [ None, '0.7' ],
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
			'proxyuser': [ opt_str, '' ],
			'proxypass': [ opt_str, '' ],
			'keyid': [ opt_str, '' ],
			'keyname': [ opt_str, '' ],
			'usetls': [ opt_bool, False ],
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
		'Nap': 'I\'m taking a nap.',
		'Brb': 'Back in some minutes.',
		'Eating': 'I\'m eating, so leave me a message.',
		'Movie' : 'I\'m watching a movie.' ,
		'Working': 'I\'m working.',
		'Phone': 'I\'m on the phone.',
	}

	soundevents_default = {
		'first_message_received': [ True, '../data/sounds/message1.wav' ],
		'next_message_received': [ True, '../data/sounds/message2.wav' ],
		'contact_connected': [ True, '../data/sounds/connected.wav' ],
		'contact_disconnected': [ True, '../data/sounds/disconnected.wav' ],
		'message_sent': [ True, '../data/sounds/sent.wav' ],
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
#			print 'error: option %s doesn\'t exist' % (optname)
			return -1
		opt = self.__options[optname]
		value = self.is_valid(opt[OPT_TYPE], value)
		if value == None:
			return -1
		
		opt[OPT_VAL] = value
		return 0
	
	def get(self, optname = None):
		if not optname:
			return self.__options.keys()
		if not self.__options.has_key(optname):
			return None
		return self.__options[optname][OPT_VAL]

	def add_per(self, typename, name): # per_group_of_option
		if not self.__options_per_key.has_key(typename):
#			print 'error: option %s doesn\'t exist' % (typename)
			return -1
		
		opt = self.__options_per_key[typename]
		if opt[1].has_key(name):
			return -2
		opt[1][name] = copy.deepcopy(opt[0])
		return 0

	def del_per(self, typename, name): # per_group_of_option
		if not self.__options_per_key.has_key(typename):
#			print 'error: option %s doesn\'t exist' % (typename)
			return -1
		
		opt = self.__options_per_key[typename]
		del opt[1][name]

	def set_per(self, optname, key, subname, value): # per_group_of_option
		if not self.__options_per_key.has_key(optname):
#			print 'error: option %s doesn\'t exist' % (optname)
			return -1
		dict = self.__options_per_key[optname][1]
		if not dict.has_key(key):
			return -1
		obj = dict[key]
		if not obj.has_key(subname):
			return -1
		subobj = obj[subname]
		value = self.is_valid(subobj[OPT_TYPE], value)
		if value == None:
			return -1
		subobj[OPT_VAL] = value
		return 0
		
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
			self.set_per('soundevents', event, 'enable', default[0])
			self.set_per('soundevents', event, 'path', default[1])
		for emot in self.emoticons_default:
			self.add_per('emoticons', emot)
			self.set_per('emoticons', emot, 'path', self.emoticons_default[emot])
		for msg in self.statusmsg_default:
			self.add_per('statusmsg', msg)
			self.set_per('statusmsg', msg, 'message', self.statusmsg_default[msg])
		return
