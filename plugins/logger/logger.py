#!/usr/bin/env python
##      plugins/logger.py
##
## Gajim Team:
##      - Yann Le Boulanger <asterix@crans.org>
##      - Vincent Hanquez <tab@snarc.org>
##
##      Copyright (C) 2003 Gajim Team
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
import string
import time
import common.optparser
from common import i18n
LOGPATH = os.path.expanduser("~/.gajim/logs/")
_ = i18n._

class plugin:
	def read_queue(self):
		while 1:
			while self.queueIN.empty() == 0:
				if self.config.has_key('lognotsep'):
					lognotsep = self.config['lognotsep']
				else:
					lognotsep = 1
				if self.config.has_key('lognotusr'):
					lognotusr = self.config['lognotusr']
				else:
					lognotusr = 1
				tim = time.time()
				
				ev = self.queueIN.get()
				if ev[0] == 'QUIT':
					print _("plugin logger stopped")
					return
				elif ev[0] == 'NOTIFY':
					status = ev[2][2]
					jid = string.split(ev[2][0], '/')[0]
					if not status:
						status = ""
					status = string.replace(status, '\n', '\\n')
					if lognotsep == 1:
						fic = open(LOGPATH + "notify.log", "a")
						fic.write("%s:%s:%s:%s\n" % (tim, ev[2][0], \
							ev[2][1], status))
						fic.close()
					if lognotusr == 1:
						fic = open(LOGPATH + jid, "a")
						fic.write("%s:%s:%s:%s\n" % (tim, jid, \
							ev[2][1], status))
						fic.close()
				elif ev[0] == 'MSG':
					msg = string.replace(ev[2][1], '\n', '\\n')
					jid = string.split(ev[2][0], '/')[0]
					fic = open(LOGPATH + jid, "a")
					fic.write("%s:recv:%s\n" % (tim, msg))
					fic.close()
				elif ev[0] == 'MSGSENT':
					msg = string.replace(ev[2][1], '\n', '\\n')
					jid = string.split(ev[2][0], '/')[0]
					fic = open(LOGPATH + jid, "a")
					fic.write("%s:sent:%s\n" % (tim, msg))
					fic.close()
			time.sleep(0.1)

	def wait(self, what):
		"""Wait for a message from Core"""
		#TODO: timeout, save messages that don't fit
		while 1:
			if not self.queueIN.empty():
				ev = self.queueIN.get()
				if ev[0] == what and ev[2][0] == 'Logger':
					return ev[2][1]
			time.sleep(0.1)

	def __init__(self, quIN, quOUT):
		self.queueIN = quIN
		self.queueOUT = quOUT
		quOUT.put(('REG_MESSAGE', 'logger', ['CONFIG', 'NOTIFY', 'MSG', \
			'MSGSENT', 'QUIT']))
		quOUT.put(('ASK_CONFIG', None, ('Logger', 'Logger', {\
			'lognotsep':1, 'lognotusr':1})))
		self.config = self.wait('CONFIG')
		#create ~/.gajim/logs/ if it doesn't exist
		try:
			os.stat(os.path.expanduser("~/.gajim"))
		except OSError:
			os.mkdir(os.path.expanduser("~/.gajim"))
			print _("creating ~/.gajim/")
		try:
			os.stat(LOGPATH)
		except OSError:
			os.mkdir(LOGPATH)
			print _("creating ~/.gajim/logs/")
		self.read_queue()
		

if __name__ == "__main__":
	plugin(None, None)

print _("plugin logger loaded")
