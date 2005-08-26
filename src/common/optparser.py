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
from common import gajim
from common import i18n
_ = i18n._

class OptionsParser:
	def __init__(self, filename):
		self.__filename = filename

	def read_line(self, line):
		index = line.find(' = ')
		var_str = line[0:index]
		value_str = line[index + 3:-1]
		
		i_start = var_str.find('.')
		i_end = var_str.rfind('.')
		
		if i_start == -1:
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

		for line in fd.readlines():
			line = line.decode('utf-8')
			self.read_line(line)

		fd.close()

	def write_line(self, fd, opt, parents, value):
		if value == None:
			return
		value = value[1]
		if type(value) == unicode:
			value = value.encode('utf-8')
		else:
			value = str(value)
		if type(opt) == unicode:
			opt = opt.encode('utf-8')
		s = ''
		if parents:
			if len(parents) == 1:
				return
			for p in parents:
				if type(p) == unicode:
					p = p.encode('utf-8')
				s += p + '.'
		s += opt
		fd.write(s + ' = ' + value + '\n')
	
	def write(self):
		(base_dir, filename) = os.path.split(self.__filename)
		self.__tempfile = os.path.join(base_dir, '.' + filename)
		try:
			fd = open(self.__tempfile, 'w')
		except:
			#chances are we cannot write file in a directory
			err_str = _('Unable to write file in %s') % base_dir
			print err_str
			return err_str
		try:
			gajim.config.foreach(self.write_line, fd)
		except IOError, e:
			fd.close()
			return e.errno
		fd.close()
		if os.path.exists(self.__filename):
			# win32 needs this
			try:
				os.remove(self.__filename)
			except:
				pass
		try:
			os.rename(self.__tempfile, self.__filename)
		except IOError, e:
			return e.errno
		os.chmod(self.__filename, 0600)
