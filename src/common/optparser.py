##	common/optparser.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@lagaule.org>
## 	- Vincent Hanquez <tab@snarc.org>
##
##	Copyright (C) 2003-2005 Gajim Team
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

import os
from common import connection
from common import gajim

class OptionsParser:
	def __init__(self, fname):
		self.__fname = os.path.expanduser(fname)
		self.tab = {}
	# END __init__

	def parseCfgFile(self):
		try:
			fd = open(self.__fname)
		except:
			print 'error cannot open file %s\n' % (self.__fname);
			return
    
		section = ''
		for line in fd.readlines():
			if line[0] in "#;":
				continue
			if line[0] == '[':
				section = line[1:line.find(']')]
				self.tab[section] = {}
				continue
			index = line.find('=')
			if index == -1:
				continue
			option = line[0:index]
			option = option.strip()
			value = line[index+2:-1]
			if option.find('password') == -1:
				if value == 'False':
					self.tab[section][option] = False
				elif value == 'True':
					self.tab[section][option] = True
				else:
					try:
						i = int(value)
					except ValueError:
						self.tab[section][option] = value
					else:
						self.tab[section][option] = i
			else:
				self.tab[section][option] = value
		fd.close()
	# END parseCfgFile

	def _fill_config_key(self, section, option, key):
		if not self.tab.has_key(section):
			return
		if not self.tab[section].has_key(option):
			return
		gajim.config.set(key, self.tab[section][option])

	def fill_config(self):
		self._fill_config_key('Profile', 'log', 'log')
		self._fill_config_key('Core', 'delauth', 'delauth')
		self._fill_config_key('Core', 'delroster', 'delroster')
		self._fill_config_key('Logger', 'lognotsep', 'lognotsep')
		self._fill_config_key('Logger', 'lognotusr', 'lognotusr')

		if self.tab.has_key('GtkGui'):
			for k in self.tab['GtkGui']:
				self._fill_config_key('GtkGui', k, k)
			# status messages
			for msg in gajim.config.get_per('statusmsg'):
				gajim.config.del_per('statusmsg', msg)
			i = 0
			while self.tab['GtkGui'].has_key('msg%s_name' % i):
				gajim.config.add_per('statusmsg', self.tab['GtkGui']['msg%s_name' \
					% i])
				gajim.config.set_per('statusmsg', self.tab['GtkGui']['msg%s_name' \
					% i], 'message', self.tab['GtkGui']['msg%s' % i])
				i += 1
			# emoticons
			if self.tab['GtkGui'].has_key('emoticons'):
				for emot in gajim.config.get_per('emoticons'):
					gajim.config.del_per('emoticons', emot)
				emots = self.tab['GtkGui']['emoticons'].split('\t')
				for i in range(0, len(emots)/2):
					gajim.config.add_per('emoticons', emots[2*i])
					gajim.config.set_per('emoticons', emots[2*i], 'path', \
						emots[2*i+1])
			# sound events
			for event in gajim.config.get_per('soundevents'):
				gajim.config.del_per('soundevents', event)
			for key in self.tab['GtkGui']:
				if key.find('sound_'):
					continue
				if not self.tab['GtkGui'].has_key(key + '_file'):
					continue
				event = key[6:]
				gajim.config.add_per('soundevents', event)
				gajim.config.set_per('soundevents', event, 'enabled', \
					self.tab['GtkGui'][key])
				gajim.config.set_per('soundevents', event, 'path', \
					self.tab['GtkGui'][key + '_file'])
					
		# accounts
		if self.tab.has_key('Profile'):
			if self.tab['Profile'].has_key('accounts'):
				accounts = self.tab['Profile']['accounts'].split()
		for account in accounts:
			if not self.tab.has_key(account):
				continue
			gajim.connections[account] = connection.connection(account)
			gajim.config.add_per('accounts', account)
			for key in self.tab[account]:	
				gajim.config.set_per('accounts', account, key, \
					self.tab[account][key])
			if gajim.config.get_per('accounts', account, 'savepass'):
				gajim.connections[account].password = gajim.config.get_per( \
					'accounts', account, 'password')

	def __getattr__(self, attr):
		if attr.startswith('__') and attr in self.__dict__.keys():
			return self.__dict__[attr]
		elif self.tab.has_key(attr):
			return self.tab[attr]
		else:
#			for key in self.__dict__.keys():
#				if key == attr:
#					return self.__dict__[attr]
			return None
	# END __getattr__

	def writeCfgFile(self):
		try:
			fd = open(self.__fname, 'w')
		except:
			log.debug("Can't write config %s" % self.__fname)
			return 0
		index = 0
		for s in self.tab.keys():
			if index == 0:
				fd.write('[' + s + ']\n')
			else:
				fd.write('\n[' + s + ']\n')
			for o in self.tab[s].keys():
				fd.write(o + ' = ' + str(self.tab[s][o]) + '\n')
			index += 1
		return 1
	# END writeCfgFile

# END OptionsParser
