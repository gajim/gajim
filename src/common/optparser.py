##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##  - Nikos Kouremenos <kourem@gmail.com>
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
				print _('error: cannot open %s for reading\n') % (self.__filename)
			return

		for line in fd.readlines():
			self.read_line(line)

		fd.close()

	def write_line(self, fd, opt, parents, value):
		s = ''
		if parents:
			if len(parents) == 1:
				return
			for p in parents:
				s += p + '.'
		if value == None:
			return
		s += opt
		fd.write(s + " = " + str(value[1]) + "\n")
	
	def write(self):
		(base_dir, filename) = os.path.split(self.__filename)
		self.__tempfile = os.path.join(base_dir, '.'+filename)
		try:
			fd = open(self.__tempfile, 'w')
		except:
			err_str = _('Unable to write file in %s\n') % (base_dir)
			print err_str
			return err_str
		try:
			gajim.config.foreach(self.write_line, fd)
		except IOError, e:
			print e, dir(e), e.errno
			if e.errno == 28:
				err_str = _('No space left on device')
			else:
				err_str = e
			print err_str
			fd.close()
			return err_str
		fd.close()
		if os.path.exists(self.__filename):
			# win32 needs this
			try:
				os.remove(self.__filename)
			except:
				pass
		try:
			os.rename(self.__tempfile, self.__filename)
		except:
			err_str = _('Unable to open %s for writing\n') % (self.__filename)
			return err_str
		return None
		
