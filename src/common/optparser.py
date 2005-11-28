##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
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
import sys
import locale
from common import gajim
from common import i18n
_ = i18n._

class OptionsParser:
	def __init__(self, filename):
		self.__filename = filename
		self.old_values = {} # values that are saved in the file and maybe
									# no longer valid

	def read_line(self, line):
		index = line.find(' = ')
		var_str = line[0:index]
		value_str = line[index + 3:-1]
		
		i_start = var_str.find('.')
		i_end = var_str.rfind('.')
		
		if i_start == -1:
			self.old_values[var_str] = value_str
			gajim.config.set(var_str, value_str)
		else:
			optname = var_str[0:i_start]
			key = var_str[i_start + 1:i_end]
			subname = var_str[i_end + 1:]
			gajim.config.add_per(optname, key)
			gajim.config.set_per(optname, key, subname, value_str)
		
	def read(self):
		try:
			fd = open(self.__filename)
		except:
			if os.path.exists(self.__filename):
				#we talk about a file
				print _('error: cannot open %s for reading') % self.__filename
			return

		new_version = gajim.config.get('version')
		for line in fd.readlines():
			try:
				line = line.decode('utf-8')
			except UnicodeDecodeError:
				line = line.decode(locale.getpreferredencoding())
			self.read_line(line)
		old_version = gajim.config.get('version')

		self.update_config(old_version, new_version)
		self.old_values = {} # clean mem

		fd.close()

	def write_line(self, fd, opt, parents, value):
		if value == None:
			return
		value = value[1]
		# convert to utf8 before writing to file if needed
		if isinstance(value, unicode):
			value = value.encode('utf-8')
		else:
			value = str(value)
		if isinstance(opt, unicode):
			opt = opt.encode('utf-8')
		s = ''
		if parents:
			if len(parents) == 1:
				return
			for p in parents:
				if isinstance(p, unicode):
					p = p.encode('utf-8')
				s += p + '.'
		s += opt
		fd.write(s + ' = ' + value + '\n')
	
	def write(self):
		(base_dir, filename) = os.path.split(self.__filename)
		try:
			base_dir = base_dir.decode(sys.getfilesystemencoding())
			filename = filename.decode(sys.getfilesystemencoding())
		except:
			pass
		self.__tempfile = os.path.join(base_dir, '.' + filename)
		try:
			f = open(self.__tempfile, 'w')
		except IOError, e:
			return str(e)
		try:
			gajim.config.foreach(self.write_line, f)
		except IOError, e:
			return str(e)
		f.close()
		if os.path.exists(self.__filename):
			# win32 needs this
			try:
				os.remove(self.__filename)
			except:
				pass
		try:
			os.rename(self.__tempfile, self.__filename)
		except IOError, e:
			return str(e)
		os.chmod(self.__filename, 0600)

	def update_config(self, old_version, new_version):
		if old_version < '0.9' and new_version == '0.9':
			self.update_config_x_to_09()
	
	def update_config_x_to_09(self):
		# Var name that changed:
		# avatar_width /height -> chat_avatar_width / height
		if self.old_values.has_key('avatar_width'):
			gajim.config.set('chat_avatar_width', self.old_values['avatar_width'])
		if self.old_values.has_key('avatar_height'):
			gajim.config.set('chat_avatar_height', self.old_values['avatar_height'])
		if self.old_values.has_key('use_dbus'):
			gajim.config.set('remote_control', self.old_values['use_dbus'])
		# always_compact_view -> always_compact_view_chat / _gc
		if self.old_values.has_key('always_compact_view'):
			gajim.config.set('always_compact_view_chat',
				self.old_values['always_compact_view'])
			gajim.config.set('always_compact_view_gc',
				self.old_values['always_compact_view'])
		# new theme: grocery, plain
		d = ['accounttextcolor', 'accountbgcolor', 'accountfont',
			'accountfontattrs', 'grouptextcolor', 'groupbgcolor', 'groupfont',
			'groupfontattrs', 'contacttextcolor', 'contactbgcolor', 'contactfont',
			'contactfontattrs', 'bannertextcolor', 'bannerbgcolor']
		for theme_name in (_('grocery'), _('plain')):
			if theme_name not in gajim.config.get_per('themes'):
				gajim.config.add_per('themes', theme_name)
				theme = gajim.config.themes_default[theme_name]
				for o in d:
					gajim.config.set_per('themes', theme_name, o, theme[d.index(o)])
		# Remove cyan theme if it's not the current theme
		if 'cyan' in gajim.config.get_per('themes'):
			gajim.config.del_per('themes', 'cyan')
		if _('cyan') in gajim.config.get_per('themes'):
			gajim.config.del_per('themes', _('cyan'))
		# If we removed our roster_theme, choose the default green one or another
		# one if doesn't exists in config
		if gajim.config.get('roster_theme') not in gajim.config.get_per('themes'):
			theme = _('green')
			if theme not in gajim.config.get_per('themes'):
				theme = gajim.config.get_per('themes')[0]
			gajim.config.set('roster_theme', theme)
		# new proxies in accounts.name.file_transfer_proxies
		for account in gajim.config.get_per('accounts'):
			proxies = gajim.config.get_per('accounts', account,
				'file_transfer_proxies')
			for new in ('proxy.netlab.cz', 'proxy65.jabber.ccc.de',
				'proxy65.unstable.nl'):
				if proxies.find(new) < 0:
					proxies += ', ' + new
			gajim.config.set_per('accounts', account, 'file_transfer_proxies',
				proxies)
		# Add some emots :-* :* >:) >:-) <3
		for emot in [':-*', ':*', '>:)', '>:-)', '<3']:
			if emot not in gajim.config.get_per('emoticons'):
				gajim.config.add_per('emoticons', emot)
				gajim.config.set_per('emoticons', emot, 'path',
					gajim.config.emoticons_default[emot])
		
		gajim.config.set('version', '0.9')
