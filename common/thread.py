#!/usr/bin/env python
##	common/thread.py
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

import threading
import socket
import sys
import time
import plugins

class GajimThread(threading.Thread): 
	def __init__(self, name = None, queueIn = None, queueOut = None): 
		self.queueIn = queueIn
		self.queueOut = queueOut
		threading.Thread.__init__(self, target = self.run, \
			name = name, args = () ) 
		self.start() 
	# END __init__
 
	def run(self):
		if self.getName() == 'gtkgui':
			plugins.gtkgui.plugin(self.queueIn, self.queueOut)
	# END run
# END GajimThread
