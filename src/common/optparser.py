#!/usr/bin/python
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
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

class OptionsParser:
	def __init__(self, filename):
		self.__filename = os.path.expanduser(filename)

	def read_line(self, line):
		index = line.find(" = ")
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
			print "error: cannot open %s for reading\n" % (self.__filename)
			return

		for line in fd.readlines():
			self.read_line(line)

		fd.close()

	def write_line(self, fd, opt, parents, value):
		s = ""
		if parents:
			if len(parents) == 1:
				return
			for p in parents:
				s += p + "."
		if value == None:
			return
		s += opt
		fd.write(s + " = " + str(value[1]) + "\n")
	
	def write(self):
		try:
			fd = open(self.__filename, 'w')
		except:
			print "error: cannot open %s for writing\n" % (self.__filename)
			return
		gajim.config.foreach(self.write_line, fd)
		fd.close()
