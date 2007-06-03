## logger.py
##
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2005-2006 Yann Le Boulanger <asterix@lagaule.org>
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

import exceptions
import gajim

try:
	import sqlite3 as sqlite # python 2.5
except ImportError:
	try:
		from pysqlite2 import dbapi2 as sqlite
	except ImportError:
		raise exceptions.PysqliteNotAvailable

import configpaths
LOG_DB_PATH = configpaths.gajimpaths['LOG_DB']
LOG_DB_FOLDER, LOG_DB_FILE = os.path.split(LOG_DB_PATH)

class Constants:
	def __init__(self):
		(
			self.JID_NORMAL_TYPE,
			self.JID_ROOM_TYPE
		) = range(2)
		
		(
			self.KIND_STATUS,
			self.KIND_GCSTATUS,
			self.KIND_GC_MSG,
			self.KIND_SINGLE_MSG_RECV,
			self.KIND_CHAT_MSG_RECV,
			self.KIND_SINGLE_MSG_SENT,
			self.KIND_CHAT_MSG_SENT,
			self.KIND_ERROR
		) = range(8)
		
		(
			self.SHOW_ONLINE,
			self.SHOW_CHAT,
			self.SHOW_AWAY,
			self.SHOW_XA,
			self.SHOW_DND,
			self.SHOW_OFFLINE
		) = range(6)

		(
			self.TYPE_AIM,
			self.TYPE_GG,
			self.TYPE_HTTP_WS,
			self.TYPE_ICQ,
			self.TYPE_MSN,
			self.TYPE_QQ,
			self.TYPE_SMS,
			self.TYPE_SMTP,
			self.TYPE_TLEN,
			self.TYPE_YAHOO,
			self.TYPE_NEWMAIL,
			self.TYPE_RSS,
			self.TYPE_WEATHER,
		) = range(13)

constants = Constants()

class Logger:
	def __init__(self):
		self.jids_already_in = [] # holds jids that we already have in DB
		self.con = None

		if not os.path.exists(LOG_DB_PATH):
			# this can happen only the first time (the time we create the db)
			# db is not created here but in src/common/checks_paths.py
			return
		self.init_vars()

	def close_db(self):
		if self.con:
			self.con.close()
		self.con = None
		self.cur = None

	def open_db(self):
		self.close_db()

		# FIXME: sqlite3_open wants UTF8 strings. So a path with
		# non-ascii chars doesn't work. See #2812 and
		# http://lists.initd.org/pipermail/pysqlite/2005-August/000134.html
		back = os.getcwd()
		os.chdir(LOG_DB_FOLDER)

		# if locked, wait up to 20 sec to unlock
		# before raise (hopefully should be enough)

		self.con = sqlite.connect(LOG_DB_FILE, timeout = 20.0,
			isolation_level = 'IMMEDIATE')
		os.chdir(back)
		self.cur = self.con.cursor()
		self.set_synchronous(False)

	def set_synchronous(self, sync):
		try:
			if sync:
				self.cur.execute("PRAGMA synchronous = NORMAL")
			else:
				self.cur.execute("PRAGMA synchronous = OFF")
		except sqlite.Error, e:
			gajim.log.debug("Failed to set_synchronous(%s): %s" % (sync, str(e)))

	def init_vars(self):
		self.open_db()
		self.get_jids_already_in_db()

	def get_jids_already_in_db(self):
		self.cur.execute('SELECT jid FROM jids')
		rows = self.cur.fetchall() # list of tupples: [(u'aaa@bbb',), (u'cc@dd',)]
		self.jids_already_in = []
		for row in rows:
			# row[0] is first item of row (the only result here, the jid)
			self.jids_already_in.append(row[0])

	def jid_is_from_pm(self, jid):
		'''if jid is gajim@conf/nkour it's likely a pm one, how we know
		gajim@conf is not a normal guy and nkour is not his resource?
		we ask if gajim@conf is already in jids (with type room jid)
		this fails if user disables logging for room and only enables for
		pm (so higly unlikely) and if we fail we do not go chaos
		(user will see the first pm as if it was message in room's public chat)
		and after that all okay'''
		
		possible_room_jid, possible_nick = jid.split('/', 1)
		return self.jid_is_room_jid(possible_room_jid)

	def jid_is_room_jid(self, jid):
		self.cur.execute('SELECT jid_id FROM jids WHERE jid=?  AND type=?', 
			(jid, constants.JID_ROOM_TYPE))
		row = self.cur.fetchone()
		if row is None:
			return False
		else:
			return True
	
	def get_jid_id(self, jid, typestr = None):
		'''jids table has jid and jid_id
		logs table has log_id, jid_id, contact_name, time, kind, show, message
		so to ask logs we need jid_id that matches our jid in jids table
		this method wants jid and returns the jid_id for later sql-ing on logs
		typestr can be 'ROOM' or anything else depending on the type of JID
		and is only needed to be specified when the JID is new in DB
		'''
		if jid.find('/') != -1: # if it has a /
			jid_is_from_pm = self.jid_is_from_pm(jid)
			if not jid_is_from_pm: # it's normal jid with resource
				jid = jid.split('/', 1)[0] # remove the resource
		if jid in self.jids_already_in: # we already have jids in DB
			self.cur.execute('SELECT jid_id FROM jids WHERE jid=?', [jid])
			jid_id = self.cur.fetchone()[0]
		else: # oh! a new jid :), we add it now
			if typestr == 'ROOM':
				typ = constants.JID_ROOM_TYPE
			else:
				typ = constants.JID_NORMAL_TYPE
			self.cur.execute('INSERT INTO jids (jid, type) VALUES (?, ?)', (jid, typ))
			try:
				self.con.commit()
			except sqlite.OperationalError, e:
				print >> sys.stderr, str(e)
			jid_id = self.cur.lastrowid
			self.jids_already_in.append(jid)
		return jid_id
	
	def convert_human_values_to_db_api_values(self, kind, show):
		'''coverts from string style to constant ints for db'''
		if kind == 'status':
			kind_col = constants.KIND_STATUS
		elif kind == 'gcstatus':
			kind_col = constants.KIND_GCSTATUS
		elif kind == 'gc_msg':
			kind_col = constants.KIND_GC_MSG
		elif kind == 'single_msg_recv':
			kind_col = constants.KIND_SINGLE_MSG_RECV
		elif kind == 'single_msg_sent':
			kind_col = constants.KIND_SINGLE_MSG_SENT
		elif kind == 'chat_msg_recv':
			kind_col = constants.KIND_CHAT_MSG_RECV
		elif kind == 'chat_msg_sent':
			kind_col = constants.KIND_CHAT_MSG_SENT
		elif kind == 'error':
			kind_col = constants.KIND_ERROR

		if show == 'online':
			show_col = constants.SHOW_ONLINE
		elif show == 'chat':
			show_col = constants.SHOW_CHAT
		elif show == 'away':
			show_col = constants.SHOW_AWAY
		elif show == 'xa':
			show_col = constants.SHOW_XA
		elif show == 'dnd':
			show_col = constants.SHOW_DND
		elif show == 'offline':
			show_col = constants.SHOW_OFFLINE
		elif show is None:
			show_col = None
		else: # invisible in GC when someone goes invisible
			# it's a RFC violation .... but we should not crash
			show_col = 'UNKNOWN'
		
		return kind_col, show_col

	def convert_human_transport_type_to_db_api_values(self, type_):
		'''converts from string style to constant ints for db'''
		if type_ == 'aim':
			return constants.TYPE_AIM
		if type_ == 'gadu-gadu':
			return constants.TYPE_GG
		if type_ == 'http-ws':
			return constants.TYPE_HTTP_WS
		if type_ == 'icq':
			return constants.TYPE_ICQ
		if type_ == 'msn':
			return constants.TYPE_MSN
		if type_ == 'qq':
			return constants.TYPE_QQ
		if type_ == 'sms':
			return constants.TYPE_SMS
		if type_ == 'smtp':
			return constants.TYPE_SMTP
		if type_ in ('tlen', 'x-tlen'):
			return constants.TYPE_TLEN
		if type_ == 'yahoo':
			return constants.TYPE_YAHOO
		if type_ == 'newmail':
			return constants.TYPE_NEWMAIL
		if type_ == 'rss':
			return constants.TYPE_RSS
		if type_ == 'weather':
			return constants.TYPE_WEATHER
		return None

	def convert_api_values_to_human_transport_type(self, type_id):
		'''converts from constant ints for db to string style'''
		if type_id == constants.TYPE_AIM:
			return 'aim'
		if type_id == constants.TYPE_GG:
			return 'gadu-gadu'
		if type_id == constants.TYPE_HTTP_WS:
			return 'http-ws'
		if type_id == constants.TYPE_ICQ:
			return 'icq'
		if type_id == constants.TYPE_MSN:
			return 'msn'
		if type_id == constants.TYPE_QQ:
			return 'qq'
		if type_id == constants.TYPE_SMS:
			return 'sms'
		if type_id == constants.TYPE_SMTP:
			return 'smtp'
		if type_id == constants.TYPE_TLEN:
			return 'tlen'
		if type_id == constants.TYPE_YAHOO:
			return 'yahoo'
		if type_id == constants.TYPE_NEWMAIL:
			return 'newmail'
		if type_id == constants.TYPE_RSS:
			return 'rss'
		if type_id == constants.TYPE_WEATHER:
			return 'weather'

	def commit_to_db(self, values, write_unread = False):
		#print 'saving', values
		sql = 'INSERT INTO logs (jid_id, contact_name, time, kind, show, message, subject) VALUES (?, ?, ?, ?, ?, ?, ?)'
		self.cur.execute(sql, values)
		message_id = None
		try:
			self.con.commit()
			if write_unread:
				message_id = self.cur.lastrowid
		except sqlite.OperationalError, e:
			print >> sys.stderr, str(e)
		if message_id:
			self.insert_unread_events(message_id, values[0])
		return message_id
	
	def insert_unread_events(self, message_id, jid_id):
		''' add unread message with id: message_id'''
		sql = 'INSERT INTO unread_messages VALUES (%d, %d)' % (message_id, jid_id)
		self.cur.execute(sql)
		try:
			self.con.commit()
		except sqlite.OperationalError, e:
			print >> sys.stderr, str(e)
	
	def set_read_messages(self, message_ids):
		''' mark all messages with ids in message_ids as read'''
		ids = ','.join([str(i) for i in message_ids])
		sql = 'DELETE FROM unread_messages WHERE message_id IN (%s)' % ids
		self.cur.execute(sql)
		try:
			self.con.commit()
		except sqlite.OperationalError, e:
			print >> sys.stderr, str(e)
	
	def get_unread_msgs_for_jid(self, jid):
		''' get unread messages for jid '''
		if not jid:
			return
		jid = jid.lower()
		jid_id = self.get_jid_id(jid)
		all_messages = []
		try:
			self.cur.execute(
				'SELECT message_id from unread_messages WHERE jid_id = %d' % jid_id)
			results = self.cur.fetchall()
		except:
			pass

		for message in results:
			msg_id = message[0]
			self.cur.execute('''
				SELECT log_line_id, message, time, subject FROM logs
				WHERE jid_id = %d AND log_line_id = %d
				''' % (jid_id, msg_id)
				)
			results = self.cur.fetchall()
			all_messages.append(results[0])
		return all_messages
		
	def write(self, kind, jid, message = None, show = None, tim = None,
	subject = None):
		'''write a row (status, gcstatus, message etc) to logs database
		kind can be status, gcstatus, gc_msg, (we only recv for those 3),
		single_msg_recv, chat_msg_recv, chat_msg_sent, single_msg_sent
		we cannot know if it is pm or normal chat message, we try to guess
		see jid_is_from_pm() which is called by get_jid_id()
		
		we analyze jid and store it as follows:
		jids.jid text column will hold JID if TC-related, room_jid if GC-related,
		ROOM_JID/nick if pm-related.'''

		if self.jids_already_in == []: # only happens if we just created the db
			self.open_db()

		jid = jid.lower()
		contact_name_col = None # holds nickname for kinds gcstatus, gc_msg
		# message holds the message unless kind is status or gcstatus,
		# then it holds status message
		message_col = message
		subject_col = subject
		if tim:
			time_col = int(float(time.mktime(tim)))
		else:
			time_col = int(float(time.time()))
		
		kind_col, show_col = self.convert_human_values_to_db_api_values(kind,
			show)
		
		write_unread = False
		
		# now we may have need to do extra care for some values in columns
		if kind == 'status': # we store (not None) time, jid, show, msg
			# status for roster items
			jid_id = self.get_jid_id(jid)
			if show is None: # show is None (xmpp), but we say that 'online'
				show_col = constants.SHOW_ONLINE

		elif kind == 'gcstatus':
			# status in ROOM (for pm status see status)
			if show is None: # show is None (xmpp), but we say that 'online'
				show_col = constants.SHOW_ONLINE
			jid, nick = jid.split('/', 1)
			jid_id = self.get_jid_id(jid, 'ROOM') # re-get jid_id for the new jid
			contact_name_col = nick

		elif kind == 'gc_msg':
			if jid.find('/') != -1: # if it has a /
				jid, nick = jid.split('/', 1)
			else:
				# it's server message f.e. error message
				# when user tries to ban someone but he's not allowed to
				nick = None
			jid_id = self.get_jid_id(jid, 'ROOM') # re-get jid_id for the new jid
			contact_name_col = nick
		else:
			jid_id = self.get_jid_id(jid)
			if kind == 'chat_msg_recv':
				write_unread = True
		
		if show_col == 'UNKNOWN': # unknown show, do not log
			return
			
		values = (jid_id, contact_name_col, time_col, kind_col, show_col,
			message_col, subject_col)
		return self.commit_to_db(values, write_unread)
		
	def get_last_conversation_lines(self, jid, restore_how_many_rows,
		pending_how_many, timeout, account):
		'''accepts how many rows to restore and when to time them out (in minutes)
		(mark them as too old) and number of messages that are in queue
		and are already logged but pending to be viewed,
		returns a list of tupples containg time, kind, message,
		list with empty tupple if nothing found to meet our demands'''
		jid = jid.lower()
		jid_id = self.get_jid_id(jid)
		where_sql = self._build_contact_where(account, jid)
		
		now = int(float(time.time()))
		timed_out = now - (timeout * 60) # before that they are too old
		# so if we ask last 5 lines and we have 2 pending we get
		# 3 - 8 (we avoid the last 2 lines but we still return 5 asked)
		self.cur.execute('''
			SELECT time, kind, message FROM logs
			WHERE (%s) AND kind IN (%d, %d, %d, %d, %d) AND time > %d
			ORDER BY time DESC LIMIT %d OFFSET %d
			''' % (where_sql, constants.KIND_SINGLE_MSG_RECV,
				constants.KIND_CHAT_MSG_RECV, constants.KIND_SINGLE_MSG_SENT,
				constants.KIND_CHAT_MSG_SENT, constants.KIND_ERROR,
				timed_out, restore_how_many_rows, pending_how_many)
			)

		results = self.cur.fetchall()
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
	
	def get_conversation_for_date(self, jid, year, month, day, account):
		'''returns contact_name, time, kind, show, message
		for each row in a list of tupples,
		returns list with empty tupple if we found nothing to meet our demands'''
		jid = jid.lower()
		jid_id = self.get_jid_id(jid)
		where_sql = self._build_contact_where(account, jid)

		start_of_day = self.get_unix_time_from_date(year, month, day)
		seconds_in_a_day = 86400 # 60 * 60 * 24
		last_second_of_day = start_of_day + seconds_in_a_day - 1
		
		self.cur.execute('''
			SELECT contact_name, time, kind, show, message FROM logs
			WHERE (%s)
			AND time BETWEEN %d AND %d
			ORDER BY time
			''' % (where_sql, start_of_day, last_second_of_day))
		
		results = self.cur.fetchall()
		return results

	def get_search_results_for_query(self, jid, query, account):
		'''returns contact_name, time, kind, show, message
		for each row in a list of tupples,
		returns list with empty tupple if we found nothing to meet our demands'''
		jid = jid.lower()
		jid_id = self.get_jid_id(jid)

		if False: #query.startswith('SELECT '): # it's SQL query (FIXME)
			try:
				self.cur.execute(query)
			except sqlite.OperationalError, e:
				results = [('', '', '', '', str(e))]
				return results
			
		else: # user just typed something, we search in message column
			where_sql = self._build_contact_where(account, jid)
			like_sql = '%' + query.replace("'", "''") + '%'
			self.cur.execute('''
				SELECT contact_name, time, kind, show, message, subject FROM logs
				WHERE (%s) AND message LIKE '%s'
				ORDER BY time
				''' % (where_sql, like_sql))

		results = self.cur.fetchall()
		return results

	def get_days_with_logs(self, jid, year, month, max_day, account):
		'''returns the list of days that have logs (not status messages)'''
		jid = jid.lower()
		jid_id = self.get_jid_id(jid)
		days_with_logs = []
		where_sql = self._build_contact_where(account, jid)
		
		# First select all date of month whith logs we want
		start_of_month = self.get_unix_time_from_date(year, month, 1)
		seconds_in_a_day = 86400 # 60 * 60 * 24
		last_second_of_month = start_of_month + (seconds_in_a_day * max_day) - 1

		self.cur.execute('''
			SELECT time FROM logs
			WHERE (%s)
			AND time BETWEEN %d AND %d
			AND kind NOT IN (%d, %d)
			ORDER BY time
			''' % (where_sql, start_of_month, last_second_of_month,
			constants.KIND_STATUS, constants.KIND_GCSTATUS))
		result = self.cur.fetchall()

		# Copy all interesting times in a temporary table 
		self.cur.execute('CREATE TEMPORARY TABLE blabla(time,INTEGER)') 
		for line in result: 
			self.cur.execute(''' 
				INSERT INTO blabla (time) VALUES (%d) 
				''' % (line[0])) 

		# then search in this small temp table for each day 
		for day in xrange(1, max_day + 1):  # count from 1 to 28 or to 30 or to 31
			start_of_day = self.get_unix_time_from_date(year, month, day) 
			last_second_of_day = start_of_day + seconds_in_a_day - 1 

			# just ask one row to see if we have sth for this date 
			self.cur.execute(''' 
				SELECT time FROM blabla 
				WHERE time BETWEEN %d AND %d 
				LIMIT 1 
				''' % (start_of_day, last_second_of_day)) 
			result = self.cur.fetchone() 
			if result: 
				days_with_logs[0:0]=[day]

		# Delete temporary table 
		self.cur.execute('DROP TABLE blabla') 
		result = self.cur.fetchone()
		return days_with_logs

	def get_last_date_that_has_logs(self, jid, account = None, is_room = False):
		'''returns last time (in seconds since EPOCH) for which
		we had logs (excluding statuses)'''
		jid = jid.lower()
	
		where_sql = ''
		if not is_room:
			where_sql = self._build_contact_where(account, jid)
		else:
			jid_id = self.get_jid_id(jid, 'ROOM')
			where_sql = 'jid_id = %s' % jid_id	
		self.cur.execute('''
			SELECT MAX(time) FROM logs
			WHERE (%s) 
			AND kind NOT IN (%d, %d)
			''' % (where_sql, constants.KIND_STATUS, constants.KIND_GCSTATUS))

		results = self.cur.fetchone()
		if results is not None:
			result = results[0]
		else:
			result = None

		return result

	def _build_contact_where(self, account, jid):
		'''build the where clause for a jid, including metacontacts
		jid(s) if any'''
		where_sql = ''   
		# will return empty list if jid is not associated with 
		# any metacontacts 
		family = gajim.contacts.get_metacontacts_family(account, jid)
		if family:
			for user in family:
				jid_id = self.get_jid_id(user['jid'])
				where_sql += 'jid_id = %s' % jid_id 
				if user != family[-1]:
					where_sql += ' OR '
		else: # if jid was not associated with metacontacts 
			jid_id = self.get_jid_id(jid)
			where_sql = 'jid_id = %s' % jid_id
		return where_sql

	def save_transport_type(self, jid, type_):
		'''save the type of the transport in DB'''
		type_id = self.convert_human_transport_type_to_db_api_values(type_)
		if not type_id:
			# unknown type
			return
		self.cur.execute(
			'SELECT type from transports_cache WHERE transport = "%s"' % jid)
		results = self.cur.fetchall()
		if results:
			result = results[0][0]
			if result == type_id:
				return
			self.cur.execute(
				'UPDATE transports_cache SET type = %d WHERE transport = "%s"' % (type_id,
					jid))
			try:
				self.con.commit()
			except sqlite.OperationalError, e:
				print >> sys.stderr, str(e)
			return
		self.cur.execute(
			'INSERT INTO transports_cache VALUES ("%s", %d)' % (jid, type_id))
		try:
			self.con.commit()
		except sqlite.OperationalError, e:
			print >> sys.stderr, str(e)

	def get_transports_type(self):
		'''return all the type of the transports in DB'''
		self.cur.execute(
			'SELECT * from transports_cache')
		results = self.cur.fetchall()
		if not results:
			return {}
		answer = {}
		for result in results:
			answer[result[0]] = self.convert_api_values_to_human_transport_type(result[1])
		return answer
