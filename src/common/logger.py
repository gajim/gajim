## logger.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##
##      Copyright (C) 2003-2005 Gajim Team
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
import time
import common.gajim
from common import i18n
_ = i18n._

LOGPATH = os.path.expanduser('~/.gajim/logs')
if os.name == 'nt':
	try:
		LOGPATH = os.environ['appdata']
	except KeyError:
		pass

class Logger:
	def __init__(self):
		dot_gajim = os.path.expanduser('~/.gajim')
		if os.path.isfile(dot_gajim):
			print '~/.gajim is file but it should be a directory'
			print 'Gajim will now exit'
			sys.exit()
		if os.path.isdir(dot_gajim):
			if os.path.isfile(LOGPATH):
				print '~/.gajim/logs is file but it should be a directory'
				print 'Gajim will now exit'
				sys.exit()
		else: #create ~/.gajim/logs if it doesn't exist
			os.mkdir(dot_gajim)
			print 'creating ~/.gajim directory'
			os.mkdir(LOGPATH)
			print 'creating ~/.gajim/logs directory'

	def write(self, kind, msg, jid, show = None, tim = None):
		if not tim:
			tim = time.time()
		else:
			tim = time.mktime(tim)

		if not msg:
			msg = ''
		msg = msg.replace('\n', '\\n')
		ji = jid.split('/')[0]
		files = []
		if kind == 'status': #we save time:jid:show:msg
			if not show:
				show = 'online'
			if common.gajim.config.get('lognotusr'):
				files.append(ji)
			if common.gajim.config.get('lognotsep'):
				files.append('notify.log')
		elif kind == 'incoming': # we save time:recv:message
			files.append(ji)
			jid = 'recv'
			show = msg
			msg = ''
		elif kind == 'outgoing': # we save time:sent:message
			files.append(ji)
			jid = 'sent'
			show = msg
			msg = ''
		elif kind == 'gc':
			files.append(ji)
			jid = 'recv'
			jids = jid.split('/')
			nick = ''
			if len(jids) > 1:
				nick = jids[1]
			show = nick
		for f in files:
			path_to_file = os.path.join(LOGPATH, f)
			fic = open(path_to_file, 'a')
			fic.write('%s:%s:%s' % (tim, jid, show))
			if msg:
				fic.write(':' + msg)
			fic.write('\n')
			fic.close()

	def get_nb_line(self, jid):
		path_to_file = os.path.join(LOGPATH, jid.split('/')[0])
		fic = open(path_to_file, 'r')
		nb = 0
		while (fic.readline()):
			nb += 1
		fic.close()
		return nb

	def read(self, jid, begin_line, end_line):
		path_to_file = os.path.join(LOGPATH, jid.split('/')[0])
		fic = open(path_to_file, 'r')
		nb = 0
		lines = []
		while (nb < begin_line and fic.readline()):
			nb += 1
		while nb < end_line:
			line = fic.readline()
			if line:
				line = line.replace('\\n', '\n')
				lineSplited = line.split(':')
				if len(lineSplited) > 2:
					lines.append(lineSplited)
			nb += 1
		return nb, lines
