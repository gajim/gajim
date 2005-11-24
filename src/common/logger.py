## logger.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
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
import datetime

from common import i18n
_ = i18n._

try:
	from pysqlite2 import dbapi2 as sqlite
except ImportError:
	error = _('pysqlite2 (aka python-pysqlite2) dependency is missing. '\
		'After you install pysqlite3, if you want to migrate your logs '\
		'to the new database, please read: http://trac.gajim.org/wiki/MigrateLogToDot9DB '
		'Exiting...'
		)
	print >> sys.stderr, error
	sys.exit()
	
GOT_JIDS_ALREADY_IN_DB = False # see get_jids_already_in_db()

if os.name == 'nt':
	try:
		# Documents and Settings\[User Name]\Application Data\Gajim\logs.db
		LOG_DB_PATH = os.path.join(os.environ['appdata'], 'Gajim', 'logs.db')
	except KeyError:
		# win9x, ./logs.db
		LOG_DB_PATH = 'logs.db'
else: # Unices
	LOG_DB_PATH = os.path.expanduser('~/.gajim/logs.db')

try:
	LOG_DB_PATH = LOG_DB_PATH.decode(sys.getfilesystemencoding())
except:
	pass

con = sqlite.connect(LOG_DB_PATH)
cur = con.cursor()

class Logger:
	def __init__(self):
		if not os.path.exists(LOG_DB_PATH):
			# this can happen only the first time (the time we create the db)
			# db is created in src/common/checks_paths.py
			return
		
		self.get_jids_already_in_db()

	def get_jids_already_in_db(self):
		cur.execute('SELECT jid FROM jids')
		rows = cur.fetchall() # list of tupples: (u'aaa@bbb',), (u'cc@dd',)]
		self.jids_already_in = []
		for row in rows:
			# row[0] is first item of row (the only result here, the jid)
			self.jids_already_in.append(row[0])
		GOT_JIDS_ALREADY_IN_DB = True

	def jid_is_from_pm(cur, jid):
		'''if jid is gajim@conf/nkour it's likely a pm one, how we know
		gajim@conf is not a normal guy and nkour is not his resource?
		we ask if gajim@conf is already in jids (as room)
		this fails if user disable logging for room and only enables for
		pm (so higly unlikely) and if we fail we do not force chaos
		(user will see the first pm as if it was message in room's public chat)'''
		
		possible_room_jid, possible_nick = jid.split('/', 1)
		
		cur.execute('SELECT jid_id FROM jids WHERE jid="%s"' % possible_room_jid)
		jid_id = cur.fetchone()[0]
		if jid_id:
			return True
		else:
			return False
	
	def get_jid_id(self, jid):
		'''jids table has jid and jid_id
		logs table has log_id, jid_id, contact_name, time, kind, show, message
		so to ask logs we need jid_id that matches our jid in jids table
		this method asks jid and returns the jid_id for later sql-ing on logs
		'''
		if jid.find('/') != -1: # if it has a /
				jid = jid.split('/', 1)[0] # remove the resource
		if jid in self.jids_already_in: # we already have jids in DB
			cur.execute('SELECT jid_id FROM jids WHERE jid="%s"' % jid)
			jid_id = cur.fetchone()[0]
		else: # oh! a new jid :), we add him now
			cur.execute('INSERT INTO jids (jid) VALUES (?)', (jid,))
			con.commit()
			jid_id = cur.lastrowid
			self.jids_already_in.append(jid)
		return jid_id
	
	def write(self, kind, jid, message = None, show = None, tim = None):
		'''write a row (status, gcstatus, message etc) to logs database
		kind can be status, gcstatus, gc_msg, (we only recv for those 3),
		single_msg_recv, chat_msg_recv, chat_msg_sent, single_msg_sent
		we cannot know if it is pm or normal chat message, we try to guess
		see jid_is_from_pm()
		
		we analyze jid and store it as follows:
		jids.jid text column will hold JID if TC-related, room_jid if GC-related,
		ROOM_JID/nick if pm-related.'''

		if not GOT_JIDS_ALREADY_IN_DB:
			self.get_jids_already_in_db()
			
		jid = jid.lower()
		contact_name_col = None # holds nickname for kinds gcstatus, gc_msg
		# message holds the message unless kind is status or gcstatus,
		# then it holds status message
		message_col = message
		show_col = show
		if tim:
			time_col = int(float(time.mktime(tim)))
		else:
			time_col = int(float(time.time()))

		def commit_to_db(values):
			sql = 'INSERT INTO logs (jid_id, contact_name, time, kind, show, message) '\
					'VALUES (?, ?, ?, ?, ?, ?)'
			cur.execute(sql, values)
			con.commit()
			#print 'saved', values
		
		jid_id = self.get_jid_id(jid)
		#print 'jid', jid, 'gets jid_id', jid_id
					
		if kind == 'status': # we store (not None) time, jid, show, msg
			# status for roster items
			if show is None:
				show_col = 'online'

			values = (jid_id, contact_name_col, time_col, kind, show_col, message_col)
			commit_to_db(values)
		elif kind == 'gcstatus':
			# status in ROOM (for pm status see status)
			if show is None:
				show_col = 'online'
			
			jid, nick = jid.split('/', 1)
			
			jid_id = self.get_jid_id(jid) # re-get jid_id for the new jid
			contact_name_col = nick
			values = (jid_id, contact_name_col, time_col, kind, show_col, message_col)
			commit_to_db(values)
		elif kind == 'gc_msg':
			if jid.find('/') != -1: # if it has a /
				jid, nick = jid.split('/', 1)
			else:
				# it's server message f.e. error message
				# when user tries to ban someone but he's not allowed to
				nick = None
			jid_id = self.get_jid_id(jid) # re-get jid_id for the new jid
			contact_name_col = nick
			
			values = (jid_id, contact_name_col, time_col, kind, show_col, message_col)
			commit_to_db(values)
		elif kind in ('single_msg_recv', 'chat_msg_recv', 'chat_msg_sent', 'single_msg_sent'):
			values = (jid_id, contact_name_col, time_col, kind, show_col, message_col)
			commit_to_db(values)

	def get_last_conversation_lines(self, jid, restore_how_many_rows,
		pending_how_many, timeout):
		'''accepts how many rows to restore and when to time them out (in minutes)
		(mark them as too old) and number of messages that are in queue
		and are already logged but pending to be viewed,
		returns a list of tupples containg time, kind, message,
		list with empty tupple if nothing found to meet our demands'''
		now = int(float(time.time()))
		jid = jid.lower()
		jid_id = self.get_jid_id(jid)
		# so if we ask last 5 lines and we have 2 pending we get
		# 3 - 8 (we avoid the last 2 lines but we still return 5 asked)
		cur.execute('''
			SELECT time, kind, message FROM logs
			WHERE jid_id = %d AND kind IN
			('single_msg_recv', 'chat_msg_recv', 'chat_msg_sent', 'single_msg_sent')
			ORDER BY time DESC LIMIT %d OFFSET %d
			''' % (jid_id, restore_how_many_rows, pending_how_many)
			)

		results = cur.fetchall()
		results.reverse()
		return results
	
	def get_unix_time_from_date(self, year, month, day):
		# year (fe 2005), month (fe 11), day (fe 25)
		# returns time in seconds for the second that starts that date since epoch
		# gimme unixtime from year month day:
		d = datetime.date(year, month, day)
		local_time = d.timetuple() # time tupple (compat with time.localtime())
		start_of_day = int(time.mktime(local_time)) # we have time since epoch baby :)
		return start_of_day
	
	def get_conversation_for_date(self, jid, year, month, day):
		'''returns contact_name, time, kind, show, message
		for each row in a list of tupples,
		returns list with empty tupple if we found nothing to meet our demands'''
		jid = jid.lower()
		jid_id = self.get_jid_id(jid)
		
		start_of_day = self.get_unix_time_from_date(year, month, day)
		
		now = int(time.time())
		
		cur.execute('''
			SELECT contact_name, time, kind, show, message FROM logs
			WHERE jid_id = %d
			AND time BETWEEN %d AND %d
			ORDER BY time
			''' % (jid_id, start_of_day, now))
		
		results = cur.fetchall()
		return results

	def date_has_logs(self, jid, year, month, day):
		'''returns True if we have logs for given day, else False'''
		jid = jid.lower()
		jid_id = self.get_jid_id(jid)
		
		start_of_day = self.get_unix_time_from_date(year, month, day)
		seconds_in_a_day = 86400 # 60 * 60 * 24
		last_second_of_day = start_of_day + seconds_in_a_day - 1
		
		# just ask one row to see if we have sth for this date
		cur.execute('''
			SELECT log_line_id FROM logs
			WHERE jid_id = %d
			AND time BETWEEN %d AND %d
			ORDER BY time LIMIT 1
			''' % (jid_id, start_of_day, last_second_of_day))
		
		results = cur.fetchone()
		if results:
			return True
		else:
			return False
