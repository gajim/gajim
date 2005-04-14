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
		'log': [ opt_bool, 'True' ],
		'delauth': [ opt_bool, 'True' ],
		'delroster': [ opt_bool, 'True' ],
		'alwaysauth': [ opt_bool, 'False' ],
		'autopopup': [ opt_bool, 'False' ],
		'autopopupaway': [ opt_bool, 'False' ],
		'ignore_unknown_contacts': [ opt_bool, 'False' ],
		'showoffline': [ opt_bool, 'False' ],
		'autoaway': [ opt_bool, 'True' ],
		'autoawaytime': [ opt_int, 10 ],
		'autoxa': [ opt_bool, 'True' ],
		'autoxatime': [ opt_int, 20 ],
		'ask_online_status': [ opt_bool, 'False' ],
		'ask_offline_status': [ opt_bool, 'False' ],
		'last_msg': [ opt_str, '' ],
		'msg0_name': [ opt_str, 'Nap' ],
		'msg0': [ opt_str, 'I\'m taking a nap.' ],
		'msg1_name': [ opt_str, 'Brb' ],
		'msg1': [ opt_str, 'Back in some minutes.' ],
		'msg2_name': [ opt_str, 'Eating' ],
		'msg2': [ opt_str, 'I\'m eating, so leave me a message.' ],
		'msg3_name': [ opt_str, 'Movie' ],
		'msg3': [ opt_str, 'I\'m watching a movie.' ],
		'msg4_name': [ opt_str, 'Working' ],
		'msg4': [ opt_str, 'I\'m working.' ],
		'trayicon': [ opt_bool, 'True' ],
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
		'saveposition': [ opt_bool, 'True' ],
		'mergeaccounts': [ opt_bool, 'False' ],
		'usetabbedchat': [ opt_bool, 'True' ],
		'print_time': [ opt_str, 'always' ],
		'useemoticons': [ opt_bool, 'True' ],
		'emoticons': [ opt_str, ':-)\tplugins/gtkgui/emoticons/smile.png\t(@)\tplugins/gtkgui/emoticons/pussy.png\t8)\tplugins/gtkgui/emoticons/coolglasses.png\t:(\tplugins/gtkgui/emoticons/unhappy.png\t:)\tplugins/gtkgui/emoticons/smile.png\t(})\tplugins/gtkgui/emoticons/hugleft.png\t:$\tplugins/gtkgui/emoticons/blush.png\t(Y)\tplugins/gtkgui/emoticons/yes.png\t:-@\tplugins/gtkgui/emoticons/angry.png\t:-D\tplugins/gtkgui/emoticons/biggrin.png\t(U)\tplugins/gtkgui/emoticons/brheart.png\t(F)\tplugins/gtkgui/emoticons/flower.png\t:-[\tplugins/gtkgui/emoticons/bat.png\t:>\tplugins/gtkgui/emoticons/biggrin.png\t(T)\tplugins/gtkgui/emoticons/phone.png\t:-S\tplugins/gtkgui/emoticons/frowing.png\t:-P\tplugins/gtkgui/emoticons/tongue.png\t(H)\tplugins/gtkgui/emoticons/coolglasses.png\t(D)\tplugins/gtkgui/emoticons/drink.png\t:-O\tplugins/gtkgui/emoticons/oh.png\t(C)\tplugins/gtkgui/emoticons/coffee.png\t({)\tplugins/gtkgui/emoticons/hugright.png\t(*)\tplugins/gtkgui/emoticons/star.png\tB-)\tplugins/gtkgui/emoticons/coolglasses.png\t(Z)\tplugins/gtkgui/emoticons/boy.png\t(E)\tplugins/gtkgui/emoticons/mail.png\t(N)\tplugins/gtkgui/emoticons/no.png\t(P)\tplugins/gtkgui/emoticons/photo.png\t(K)\tplugins/gtkgui/emoticons/kiss.png\t(R)\tplugins/gtkgui/emoticons/rainbow.png\t:-|\tplugins/gtkgui/emoticons/stare.png\t;-)\tplugins/gtkgui/emoticons/wink.png\t;-(\tplugins/gtkgui/emoticons/cry.png\t(6)\tplugins/gtkgui/emoticons/devil.png\t(L)\tplugins/gtkgui/emoticons/heart.png\t(W)\tplugins/gtkgui/emoticons/brflower.png\t:|\tplugins/gtkgui/emoticons/stare.png\t:O\tplugins/gtkgui/emoticons/oh.png\t;)\tplugins/gtkgui/emoticons/wink.png\t;(\tplugins/gtkgui/emoticons/cry.png\t:S\tplugins/gtkgui/emoticons/frowing.png\t;\'-(\tplugins/gtkgui/emoticons/cry.png\t:-(\tplugins/gtkgui/emoticons/unhappy.png\t8-)\tplugins/gtkgui/emoticons/coolglasses.png\t(B)\tplugins/gtkgui/emoticons/beer.png\t:D\tplugins/gtkgui/emoticons/biggrin.png\t(8)\tplugins/gtkgui/emoticons/music.png\t:@\tplugins/gtkgui/emoticons/angry.png\tB)\tplugins/gtkgui/emoticons/coolglasses.png\t:-$\tplugins/gtkgui/emoticons/blush.png\t:\'(\tplugins/gtkgui/emoticons/cry.png\t:->\tplugins/gtkgui/emoticons/biggrin.png\t:[\tplugins/gtkgui/emoticons/bat.png\t(I)\tplugins/gtkgui/emoticons/lamp.png\t:P\tplugins/gtkgui/emoticons/tongue.png\t(%)\tplugins/gtkgui/emoticons/cuffs.png\t(S)\tplugins/gtkgui/emoticons/moon.png' ],
		'sounds_on': [ opt_bool, 'True' ],
		'soundplayer': [ opt_str, 'play' ],
		'sound_first_message_received': [ opt_bool, 'True' ],
		'sound_first_message_received_file': [ opt_str, 'sounds/message1.wav' ],
		'sound_next_message_received': [ opt_bool, 'True' ],
		'sound_next_message_received_file': [ opt_str, 'sounds/message2.wav' ],
		'sound_contact_connected': [ opt_bool, 'True' ],
		'sound_contact_connected_file': [ opt_str, 'sounds/connected.wav' ],
		'sound_contact_disconnected': [ opt_bool, 'True' ],
		'sound_contact_disconnected_file': [ opt_str, 'sounds/disconnected.wav' ],
		'sound_message_sent': [ opt_bool, 'True' ],
		'sound_message_sent_file': [ opt_str, 'sounds/sent.wav' ],
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
		'do_not_send_os_info': [ opt_bool, 'False' ],
		'usegpg': [ opt_bool, 'False' ],
		'lognotusr': [ opt_bool, 'True' ],
		'lognotsep': [ opt_bool, 'True' ],
	}

	__options_per_key = {
		'accounts': ({
			'name':		[ opt_str, '' ],
			'hostname':	[ opt_str, '' ],
			'savepass': [ opt_bool, 'False' ],
			'password': [ opt_str, '' ],
			'resource':	[ opt_str, 'gajim' ],
			'priority': [ opt_int, 5 ],
			'autoconnect': [ opt_bool, 'False' ],
			'use_proxy': [ opt_bool, 'False' ],
			'proxyhost': [ opt_str, '' ],
			'proxyport': [ opt_int, 3128 ],
			'keyid': [ opt_str, '' ],
			'keyname': [ opt_str, '' ],
			'savegpgpass': [ opt_bool, 'False' ],
			'gpgpassword': [ opt_str, '' ],
			'sync_with_global_status': [ opt_bool, 'True' ],
			'no_log_for': [ opt_str, '' ],
			} , {}),
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
		if val == 'True' or val == 'False':
			return 1
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
		if not self.exist(optname):
			return None
		val = self.__options[optname][OPT_VAL]
		if val == 'True': return True
		if val == 'False': return False
		try:
			val = int(val)
		except ValueError:
			pass
		return val

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
		return obj[subname]

	def exist(self, optname):
		return self.__options.has_key(optname)

	def __init__(self):
		return
