#!/usr/bin/env python
import os
import sre
import sys
import time
import signal

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

if os.path.exists(PATH_TO_DB):
	print '%s already exists. Exiting..' % PATH_TO_DB
	sys.exit()
	
jids_already_in = [] # jid we already put in DB
con = sqlite.connect(PATH_TO_DB) 
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
		jid TEXT UNIQUE
	);
	
	CREATE TABLE logs(
		log_line_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
		jid_id INTEGER,
		contact_name TEXT,
		time INTEGER,
		kind TEXT,
		show TEXT,
		message TEXT
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
		jid = jid[p:]
	jid = jid.lower()
	return jid

def decode_string(string):
	'''try to decode (to make it Unicode instance) given string'''
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
		if filename == 'notify.log':
			continue
		filename = decode_string(filename)
		if not filename:
			continue
		path_to_text_file = os.path.join(dirname, filename)
		if os.path.isdir(path_to_text_file):
			continue

		jid = get_jid(dirname, filename)
		print 'Processing', jid
		# jid is already in the DB, don't create the table, just get his jid_id
		if jid in jids_already_in:
			cur.execute('SELECT jid_id FROM jids WHERE jid = "%s"' % jid)
			JID_ID = cur.fetchone()[0]
		else:
			jids_already_in.append(jid)
			cur.execute('INSERT INTO jids (jid) VALUES (?)', (jid,))
			con.commit()

			JID_ID = cur.lastrowid
		
		
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
				type = splitted_line[1] # line[1] has type of logged message
				message_data = splitted_line[2:] # line[2:] has message data
				message_data = decode_string(message_data)
				if not message_data:
					continue
				# line[0] is date,

				# some lines can be fucked up, just drop them
				try:
					tim = int(float(splitted_line[0]))
				except:
					continue
				
				sql = 'INSERT INTO logs (jid_id, contact_name, time, kind, show, message) '\
					'VALUES (?, ?, ?, ?, ?, ?)'
		
				contact_name = None
				show = None
				if type == 'gc':
					contact_name = message_data[0]
					message = ':'.join(message_data[1:])
					kind = 'gc_msg'
				elif type == 'gcstatus':
					contact_name = message_data[0]
					show = message_data[1]
					message = ':'.join(message_data[2:]) # status msg
					kind = type
				elif type == 'recv':
					message = ':'.join(message_data[0:])
					kind = 'chat_msg_recv'
				elif type == 'sent':
					message = ':'.join(message_data[0:])
					kind = 'chat_msg_sent'
				else: # status
					kind = 'status'
					show = message_data[0]
					message = ':'.join(message_data[1:]) # status msg

				values = (JID_ID, contact_name, tim, kind, show, message)
				cur.execute(sql, values)
				con.commit()

if __name__ == '__main__':
	print 'IMPORTNANT: PLEASE READ http://trac.gajim.org/wiki/MigrateLogToDot9DB'
	print 'Migration will start in 40 seconds unless you press Ctrl+C'
	time.sleep(40) # give him time to act
	print
	print 'Starting Logs Migration'
	print '======================='
	print 'Please do NOT run Gajim until this script is over'
	os.path.walk(PATH_TO_LOGS_BASE_DIR, visit, None)
	f = open(os.path.join(PATH_TO_LOGS_BASE_DIR, 'README'), 'w')
	f.write('We do not use plain-text files anymore, because they do not scale.\n')
	f.write('Those files here are logs for Gajim up until 0.8.2\n')
	f.write('We now use an sqlite database called logs.db found in ~/.gajim\n')
	f.write('You can always run the migration script to import your old logs to the database\n')
	f.write('Thank you\n')
	f.close()
