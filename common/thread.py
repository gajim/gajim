#!/usr/bin/env python
##	common/thread.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@snarc.org>
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

import threading
import socket
import time
import sys
from common import i18n
_ = i18n._

class GajimThread(threading.Thread): 
	def __init__(self, name = None, queueIn = None, queueOut = None): 
		self.queueIn = queueIn
		self.queueOut = queueOut
		threading.Thread.__init__(self, target = self.run, \
			name = name) 
		self.start() 
	# END __init__
 
	def run(self):
		mod = compile("import plugins.%s" % self.getName(), \
			self.getName(), "exec")
		try:
			res = eval(mod)
			mod = compile("plugins.%s.%s.plugin(self.queueIn, self.queueOut)" % (self.getName(),self.getName()), self.getName(), "exec")
			res = eval(mod)
		except:
			print _("plugin %s cannot be launched : ") % self.getName() + \
				sys.exc_info()[1][0]
	# END run
# END GajimThread
