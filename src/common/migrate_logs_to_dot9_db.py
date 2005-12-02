#!/usr/bin/env python
import os
import sre
import sys
import time
import signal

signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application

from pysqlite2 import dbapi2 as sqlite


class Constants:
	def __init__(self):
		(
			self.JID_NORMAL_TYPE,
			self.JID_ROOM_TYPE # image to show state (online, new message etc)
		) = range(2)
		
		(
			self.KIND_STATUS,
			self.KIND_GCSTATUS,
			self.KIND_GC_MSG,
			self.KIND_SINGLE_MSG_RECV,
			self.KIND_CHAT_MSG_RECV,
			self.KIND_SINGLE_MSG_SENT,
			self.KIND_CHAT_MSG_SENT
		) = range(7)
		
		(
			self.SHOW_ONLINE,
			self.SHOW_CHAT,
			self.SHOW_AWAY,
			self.SHOW_XA,
			self.SHOW_DND,
			self.SHOW_OFFLINE
		) = range(6)

constants = Constants()

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
	PATH_TO_DB = os.path.expanduser('~/.gajim/logs2.db') # database is called logs.db

if os.path.exists(PATH_TO_DB):
	print '%s already exists. Exiting..' % PATH_TO_DB
	sys.exit()

jids_already_in = [] # jid we already put in DB
con = sqlite.connect(PATH_TO_DB) 
os.chmod(PATH_TO_DB, 0600) # rw only for us
cur = con.cursor()
# create the tables
# kind can be
# status, gcstatus, gc_msg, (we only recv for those 3),
# single_msg_recv, chat_msg_recv, chat_msg_sent, single_msg_sent
# to meet all our needs
# logs.jid_id --> jids.jid_id but Sqlite doesn't do FK etc so it's done in python code
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

# (?<!\\) is a lookbehind assertion which asks anything but '\'
# to match the regexp that follows it
re = sre.compile(r'(?<!\\)\\n')

def from_one_line(msg):
	# So here match '\\n' but not if you have a '\' before that
	msg = re.sub('\n', msg)
	msg = msg.replace('\\\\', '\\')
	# s12 = 'test\\ntest\\\\ntest'
	# s13 = re.sub('\n', s12)
	# s14 s13.replace('\\\\', '\\')
	# s14
	# 'test\ntest\\ntest'
	return msg


def get_jid(dirname, filename):
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

def decode_jid(string):
	'''try to decode (to make it Unicode instance) given jid'''
	# by the time we go to iso15 it better be the one else we show bad characters
	encodings = (sys.getfilesystemencoding(), 'utf-8', 'iso-8859-15')
	for encoding in encodings:
		try:
			string = string.decode(encoding)
		except UnicodeError:
			continue
		return string

	return None

def visit(arg, dirname, filenames):
	print 'Visiting', dirname
	for filename in filenames:
		# Don't take this file into account, this is dup info
		# notifications are also in contact log file
		if filename in ('notify.log', 'readme'):
			continue
		path_to_text_file = os.path.join(dirname, filename)
		if os.path.isdir(path_to_text_file):
			continue

		jid = get_jid(dirname, filename)

		jid = decode_jid(jid)
		if not jid:
			continue

		if filename == os.path.basename(dirname): # gajim@conf/gajim@conf then gajim@conf is type room
			jid_type = constants.JID_ROOM_TYPE
			print 'Processing', jid.encode('utf-8'), 'of type room'
		else:
			jid_type = constants.JID_NORMAL_TYPE
			print 'Processing', jid.encode('utf-8'), 'of type normal'

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
					kind = constants.KIND_GC_MSG
				elif typ == 'gcstatus':
					contact_name = message_data[0]
					show = message_data[1]
					message = ':'.join(message_data[2:]) # status msg
					kind = constants.KIND_GCSTATUS
				elif typ == 'recv':
					message = ':'.join(message_data[0:])
					kind = constants.KIND_CHAT_MSG_RECV
				elif typ == 'sent':
					message = ':'.join(message_data[0:])
					kind = constants.KIND_CHAT_MSG_SENT
				else: # status
					kind = constants.KIND_STATUS
					show = message_data[0]
					message = ':'.join(message_data[1:]) # status msg

#				message = decode_string(message)
				message = message[:-1] # remove last \n
				if not message:
					continue

				# jid is already in the DB, don't create a new row, just get his jid_id
				if not JID_ID:
					if jid in jids_already_in:
						cur.execute('SELECT jid_id FROM jids WHERE jid = "%s"' % jid)
						JID_ID = cur.fetchone()[0]
					else:
						jids_already_in.append(jid)
						cur.execute('INSERT INTO jids (jid, type) VALUES (?, ?)',
							(jid, jid_type))
						con.commit()
						JID_ID = cur.lastrowid

				sql = 'INSERT INTO logs (jid_id, contact_name, time, kind, show, message) '\
					'VALUES (?, ?, ?, ?, ?, ?)'

				values = (JID_ID, contact_name, tim, kind, show, message)
				cur.execute(sql, values)
		con.commit()

def migrate():
	os.path.walk(PATH_TO_LOGS_BASE_DIR, visit, None)
	f = open(os.path.join(PATH_TO_LOGS_BASE_DIR, 'README'), 'w')
	f.write('We do not use plain-text files anymore, because they do not scale.\n')
	f.write('Those files here are logs for Gajim up until 0.8.2\n')
	f.write('We now use an sqlite database called logs.db found in ~/.gajim\n')
	f.write('You can always run the migration script to import your old logs to the database\n')
	f.write('Thank you\n')
	f.close()

if __name__ == '__main__':
	print 'IMPORTNANT: PLEASE READ http://trac.gajim.org/wiki/MigrateLogToDot9DB'
	print 'Migration will start in 40 seconds unless you press Ctrl+C'
	time.sleep(40) # give the user time to act
	print
	print 'Starting Logs Migration'
	print '======================='
	print 'Please do NOT run Gajim until this script is over'
	migrate()
