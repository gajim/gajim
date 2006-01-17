## Contributors for this file:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Nikos Kouremenos <kourem@gmail.com>
## - Travis Shirk <travis@pobox.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
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
import stat

from common import gajim
import logger
import i18n

_ = i18n._
Q_ = i18n.Q_

from pysqlite2 import dbapi2 as sqlite # DO NOT MOVE ABOVE OF import gajim

def create_log_db():
	print _('creating logs database')
	con = sqlite.connect(logger.LOG_DB_PATH) 
	os.chmod(logger.LOG_DB_PATH, 0600) # rw only for us
	cur = con.cursor()
	# create the tables
	# kind can be
	# status, gcstatus, gc_msg, (we only recv for those 3),
	# single_msg_recv, chat_msg_recv, chat_msg_sent, single_msg_sent
	# to meet all our needs
	# logs.jid_id --> jids.jid_id but Sqlite doesn't do FK etc so it's done in python code
	# jids.jid text column will be JID if TC-related, room_jid if GC-related,
	# ROOM_JID/nick if pm-related.
	cur.executescript(
		'''
		CREATE TABLE jids(
			jid_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
			jid TEXT UNIQUE,
			type INTEGER
		);
		
		CREATE TABLE logs(
			log_line_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
			jid_id INTEGER,
			contact_name TEXT,
			time INTEGER,
			kind INTEGER,
			show INTEGER,
			message TEXT,
			subject TEXT
		);
		'''
		)

	con.commit()

def check_and_possibly_create_paths():
	LOG_DB_PATH = logger.LOG_DB_PATH
	VCARDPATH = gajim.VCARDPATH
	AVATAR_PATH = gajim.AVATAR_PATH
	dot_gajim = os.path.dirname(VCARDPATH)
	if os.path.isfile(dot_gajim):
		print _('%s is file but it should be a directory') % dot_gajim
		print _('Gajim will now exit')
		sys.exit()
	elif os.path.isdir(dot_gajim):
		s = os.stat(dot_gajim)
		if s.st_mode & stat.S_IROTH: # others have read permission!
			os.chmod(dot_gajim, 0700) # rwx------

		if not os.path.exists(VCARDPATH):
			print _('creating %s directory') % VCARDPATH
			os.mkdir(VCARDPATH, 0700)
		elif os.path.isfile(VCARDPATH):
			print _('%s is file but it should be a directory') % VCARDPATH
			print _('Gajim will now exit')
			sys.exit()
			
		if not os.path.exists(AVATAR_PATH):
			print _('creating %s directory') % AVATAR_PATH
			os.mkdir(AVATAR_PATH, 0700)
		elif os.path.isfile(AVATAR_PATH):
			print _('%s is file but it should be a directory') % AVATAR_PATH
			print _('Gajim will now exit')
			sys.exit()
		
		if not os.path.exists(LOG_DB_PATH):
			create_log_db()
		elif os.path.isdir(LOG_DB_PATH):
			print _('%s is directory but should be file') % LOG_DB_PATH
			print _('Gajim will now exit')
			sys.exit()
			
	else: # dot_gajim doesn't exist
		if dot_gajim: # is '' on win9x so avoid that
			print _('creating %s directory') % dot_gajim
			os.mkdir(dot_gajim, 0700)
		if not os.path.isdir(VCARDPATH):
			print _('creating %s directory') % VCARDPATH
			os.mkdir(VCARDPATH, 0700)
		if not os.path.isfile(LOG_DB_PATH):
			create_log_db()
			gajim.logger.init_vars()
