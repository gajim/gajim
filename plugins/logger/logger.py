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

def usage():
	#TODO: use i18n
	print "usage :", sys.argv[0], ' [OPTION]'
	print "  -p\tport on whitch the sock plugin listen"
	print "  -h, --help\tdisplay this help and exit"

if __name__ == "__main__":
	import getopt, sys, pickle, socket
	try:
		opts, args = getopt.getopt(sys.argv[1:], "p:h", ["help"])
	except getopt.GetoptError:
		# print help information and exit:
		usage()
		sys.exit(2)
	port = 8255
	for o, a in opts:
		if o == '-p':
			port = a
		if o in ("-h", "--help"):
			usage()
			sys.exit()
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	try:
		sock.connect(('', 8255))
	except:
		#TODO: use i18n
		print "unable to connect to localhost on port "+str(port)
	else:
		evp = pickle.dumps(('EXEC_PLUGIN', '', 'logger'))
		sock.send('<'+evp+'>')
		sock.close()
	sys.exit()

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
						fic.write("%s:%s:%s:%s\n" % (tim, ev[2][0] + '/' + ev[2][3], \
							ev[2][1], status))
						fic.close()
					if lognotusr == 1:
						fic = open(LOGPATH + jid, "a")
						fic.write("%s:%s:%s:%s\n" % (tim, ev[2][0] + '/' + ev[2][3], \
							ev[2][1], status))
						fic.close()
				elif ev[0] == 'MSG':
					msg = string.replace(ev[2][1], '\n', '\\n')
					jid = string.split(ev[2][0], '/')[0]
					fic = open(LOGPATH + jid, "a")
					t = time.mktime(ev[2][2])
					fic.write("%s:recv:%s\n" % (t, msg))
					fic.close()
				elif ev[0] == 'MSGSENT':
					msg = string.replace(ev[2][1], '\n', '\\n')
					jid = string.split(ev[2][0], '/')[0]
					fic = open(LOGPATH + jid, "a")
					fic.write("%s:sent:%s\n" % (tim, msg))
					fic.close()
				elif ev[0] == 'GC_MSG':
					msg = string.replace(ev[2][1], '\n', '\\n')
					jids = string.split(ev[2][0], '/')
					jid = jids[0]
					nick = ''
					if len(jids) > 1:
						nick = string.split(ev[2][0], '/')[1]
					fic = open(LOGPATH + jid, "a")
					t = time.mktime(ev[2][2])
					fic.write("%s:recv:%s:%s\n" % (t, nick, msg))
					fic.close()
				elif ev[0] == 'CONFIG':
					if ev[2][0] == 'Logger':
						self.config = ev[2][1]
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
			'MSGSENT', 'GC_MSG', 'QUIT']))
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
		
print _("plugin logger loaded")
