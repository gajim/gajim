#!/usr/bin/env python
##	common/optparser.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@tuxfamily.org>
## 	- David Ferlier <david@yazzy.org>
##
##	Copyright (C) 2003 Gajim Team
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

import ConfigParser 
import logging
import os

log = logging.getLogger('common.options')

class OptionsParser(ConfigParser.ConfigParser):
	def __init__(self, fname):
		ConfigParser.ConfigParser.__init__(self)
		self.__fname = os.path.expanduser(fname)
	# END __init__

	def parseCfgFile(self):
		try:
			self.__fd = open(self.__fname)
		except:
			print 'error cannot open file %s\n' % (self.__fname);
			return
    
		self.readfp(self.__fd)
		self.__sections = self.sections()

		for section in self.__sections:
			for option in self.options(section):
				value = self.get(section, option, 1)
				setattr(self, str(section) + '_' + \
					str(option), value)
	# END parseCfgFile

	def __str__(self):
		return "OptionsParser"
	# END __str__

	def __getattr__(self, attr):
		if attr.startswith('__') and attr in self.__dict__.keys():
			return self.__dict__[attr]
		else:
			for key in self.__dict__.keys():
				if key == attr:
					return self.__dict__[attr]
			return None
	# END __getattr__

	def writeCfgFile(self):
		try:
			self.write(open(self.__fname, 'w'))
		except:
			log.debug("Can't write config %s" % self.__fname)
			return 0
		return 1
	# END writeCfgFile

	def stop(self):
		return self.writeCfgFile()
	# END stop
# END OptionsParser
