#!/usr/bin/env python
import os
import sre
import sys
import time
import signal
import logger
import i18n
_ = i18n._
from helpers import from_one_line, decode_string

signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application

from pysqlite2 import dbapi2 as sqlite

if os.name == 'nt':
	try:
		PATH_TO_LOGS_BASE_DIR = os.path.join(os.environ['appdata'], 'Gajim', 'Logs')
		PATH_TO_DB = os.path.join(os.environ['appdata'], 'Gajim', 'logs.db') # database is called logs.db
	except KeyError:
		# win9x
		PATH_TO_LOGS_BASE_DIR = '../src/Logs'
		PATH_TO_DB = '../src/logs.db'
else:
	PATH_TO_LOGS_BASE_DIR = os.path.expanduser('~/.gajim/logs')
	PATH_TO_DB = os.path.expanduser('~/.gajim/logs.db') # database is called logs.db

class Migration:
	def __init__(self):
		self.constants = logger.Constants()
		self.DONE = False
		self.PROCESSING = False

		if os.path.exists(PATH_TO_DB):
			print '%s already exists. Exiting..' % PATH_TO_DB
			sys.exit()

		self.jids_already_in = [] # jid we already put in DB

	def get_jid(self, dirname, filename):
		# jids.jid text column will be JID if TC-related, room_jid if GC-related,
		# ROOM_JID/nick if pm-related. Here I get names from filenames
		if dirname.endswith('logs') or dirname.endswith('Logs'):
			# we have file (not dir) in logs base dir, so it's TC
			jid = filename # file is JID
		else:
			# we are in a room folder (so it can be either pm or message in room)
			if filename == os.path.basename(dirname): # room/room
				jid = dirname # filename is ROOM_JID
			else: #room/nick it's pm
				jid = dirname + '/' + filename

		if jid.startswith('/'):
			p = len(PATH_TO_LOGS_BASE_DIR)
			jid = jid[p+1:]
		jid = jid.lower()
		return jid

	def decode_jid(self, string):
		'''try to decode (to make it Unicode instance) given jid'''
		string = decode_string(string)
		if isinstance(string, str):
			return None # decode failed
		return string

	def visit(self, arg, dirname, filenames):
		s = _('Visiting %s') % dirname
		if self.queue:
			self.queue.put(s)
		else:
			print s
		for filename in filenames:
			# Don't take this file into account, this is dup info
			# notifications are also in contact log file
			if filename in ('notify.log', 'README'):
				continue
			path_to_text_file = os.path.join(dirname, filename)
			if os.path.isdir(path_to_text_file):
				continue

			jid = self.get_jid(dirname, filename)

			jid = self.decode_jid(jid)
			if not jid:
				continue

			if filename == os.path.basename(dirname): # gajim@conf/gajim@conf then gajim@conf is type room
				jid_type = self.constants.JID_ROOM_TYPE
				#Type of log
				typ = 'room'
			else:
				jid_type = self.constants.JID_NORMAL_TYPE
				#Type of log
				typ = _('normal')
			s = _('Processing %s of type %s') % (jid.encode('utf-8'), typ)
			if self.queue:
				self.queue.put(s)
			else:
				print s

			JID_ID = None
			f = open(path_to_text_file, 'r')
			lines = f.readlines()
			for line in lines:
				line = from_one_line(line)
				splitted_line = line.split(':')
				if len(splitted_line) > 2:
					# type in logs is one of 
					# 'gc', 'gcstatus', 'recv', 'sent' and if nothing of those
					# it is status
					# new db has:
					# status, gcstatus, gc_msg, (we only recv those 3),
					# single_msg_recv, chat_msg_recv, chat_msg_sent, single_msg_sent
					# to meet all our needs
					# here I convert
					# gc ==> gc_msg, gcstatus ==> gcstatus, recv ==> chat_msg_recv
					# sent ==> chat_msg_sent, status ==> status
					typ = splitted_line[1] # line[1] has type of logged message
					message_data = splitted_line[2:] # line[2:] has message data
					# line[0] is date,
					# some lines can be fucked up, just drop them
					try:
						tim = int(float(splitted_line[0]))
					except:
						continue

					contact_name = None
					show = None
					if typ == 'gc':
						contact_name = message_data[0]
						message = ':'.join(message_data[1:])
						kind = self.constants.KIND_GC_MSG
					elif typ == 'gcstatus':
						contact_name = message_data[0]
						show = message_data[1]
						message = ':'.join(message_data[2:]) # status msg
						kind = self.constants.KIND_GCSTATUS
					elif typ == 'recv':
						message = ':'.join(message_data[0:])
						kind = self.constants.KIND_CHAT_MSG_RECV
					elif typ == 'sent':
						message = ':'.join(message_data[0:])
						kind = self.constants.KIND_CHAT_MSG_SENT
					else: # status
						kind = self.constants.KIND_STATUS
						show = message_data[0]
						message = ':'.join(message_data[1:]) # status msg

					message = message[:-1] # remove last \n
					if not message:
						continue

					# jid is already in the DB, don't create a new row, just get his jid_id
					if not JID_ID:
						if jid in self.jids_already_in:
							self.cur.execute('SELECT jid_id FROM jids WHERE jid = "%s"' % jid)
							JID_ID = self.cur.fetchone()[0]
						else:
							self.jids_already_in.append(jid)
							self.cur.execute('INSERT INTO jids (jid, type) VALUES (?, ?)',
								(jid, jid_type))
							self.con.commit()
							JID_ID = self.cur.lastrowid

					sql = 'INSERT INTO logs (jid_id, contact_name, time, kind, show, message) '\
						'VALUES (?, ?, ?, ?, ?, ?)'

					values = (JID_ID, contact_name, tim, kind, show, message)
					self.cur.execute(sql, values)
			self.con.commit()

	def migrate(self, queue = None):
		self.queue = queue
		self.con = sqlite.connect(PATH_TO_DB) 
		os.chmod(PATH_TO_DB, 0600) # rw only for us
		self.cur = self.con.cursor()
		# create the tables
		# kind can be
		# status, gcstatus, gc_msg, (we only recv for those 3),
		# single_msg_recv, chat_msg_recv, chat_msg_sent, single_msg_sent
		# to meet all our needs
		# logs.jid_id --> jids.jid_id but Sqlite doesn't do FK etc so it's done in python code
		self.cur.executescript(
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

		self.con.commit()

		self.PROCESSING = True
		os.path.walk(PATH_TO_LOGS_BASE_DIR, self.visit, None)
		s = '''

We do not use plain-text files anymore, because they do not meet our needs.
Those files here are logs for Gajim up until 0.8.2
We now use an sqlite database called logs.db found in %s
You can now safely remove your %s folder
Thank you''' % (os.path.dirname(PATH_TO_LOGS_BASE_DIR), PATH_TO_LOGS_BASE_DIR)
		f = open(os.path.join(PATH_TO_LOGS_BASE_DIR, 'README'), 'w')
		f.write(s)
		f.close()
		if queue:
			queue.put(s)
		self.DONE = True

if __name__ == '__main__':
	print 'IMPORTNANT: PLEASE READ http://trac.gajim.org/wiki/MigrateLogToDot9DB'
	print 'Migration will start in 40 seconds unless you press Ctrl+C'
	time.sleep(40) # give the user time to act
	print
	print 'Starting Logs Migration'
	print '======================='
	print 'Please do NOT run Gajim until this script is over'
	m = Migration()
	m.migrate()
