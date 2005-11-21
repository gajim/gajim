#!/usr/bin/env python
import os
import sre

from pysqlite2 import dbapi2 as sqlite

PATH_TO_LOGS_BASE_DIR = os.path.expanduser('~/.gajim/logs')

path_to_db = os.path.expanduser('~/.gajim/logs.db') # database is called logs.db
con = sqlite.connect(path_to_db) 
cur = con.cursor()
# create the tables
# type can be 'gc', 'gcstatus', 'recv', 'sent', 'status'
# logs --> jids.jid_id but Sqlite doesn't do FK etc so it's done in python code
cur.executescript(
	'''
	CREATE TABLE jids(
		jid_id INTEGER PRIMARY KEY AUTOINCREMENT,
		jid TEXT UNIQUE
	);
	
	CREATE TABLE logs(
		log_line_id INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE,
		jid_id INTEGER,
		contact_name TEXT,
		time INTEGER,
		type TEXT,
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
	# TABLE NAME will be JID if TC-related, room_jid if GC-related,
	# ROOM_JID/nick if pm-related
	if dirname.endswith('logs/'): # basename(gajim.LOGPATH)
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

def visit(arg, dirname, filenames):
	for filename in filenames:
		path_to_text_file = os.path.join(dirname, filename)
		if os.path.isdir(path_to_text_file):
			continue

		jid = get_jid(dirname, filename)
		cur.execute('INSERT INTO jids (jid) VALUES (?)', (jid,))
		con.commit()
		
		cur.execute('SELECT COUNT(*) FROM jids')
		JID_ID = cur.fetchone()[0]
		
		f = open(path_to_text_file, 'r')
		lines = f.readlines()
		for line in lines:
			line = from_one_line(line)
			splitted_line = line.split(':')
			# 'gc', 'gcstatus', 'recv', 'sent' and if nothing of those
			# it is status
			type = splitted_line[1] # line[1] has type of logged message
			message_data = splitted_line[2:] # line[2:] has message data
			if len(splitted_line) > 2:
				# line[0] is date,
				tim = int(float(splitted_line[0]))
				
				sql = 'INSERT INTO logs (jid_id, contact_name, time, type, show, message) '\
					'VALUES (?, ?, ?, ?, ?, ?)'
		
				contact_name = None
				show = None
				if type == 'gc':
					contact_name = message_data[0]
					message = ':'.join(message_data[1:])
				elif type == 'gcstatus':
					contact_name = message_data[0]
					show = message_data[1]
					message = ':'.join(message_data[2:]) # status msg
				elif type in ('recv', 'sent'):
					message = ':'.join(message_data[0:])
				else: # status
					type = 'status'
					show = message_data[0]
					message = ':'.join(message_data[1:]) # status msg

				values = (JID_ID, contact_name, tim, type, show, message)
				cur.execute(sql, values)
				con.commit()

if __name__ == '__main__':
	os.path.walk(PATH_TO_LOGS_BASE_DIR, visit, None)
	f = open(os.path.join(PATH_TO_LOGS_BASE_DIR, 'README'), 'w')
	f.write('We do not use plain-text files anymore, because they do not scale.\n')
	f.write('Those files here are logs for Gajim up until 0.8.2\n')
	f.write('We now use an sqlite database called logs.db found in ~/.gajim\n')
	f.write('You can always run the migration script to import your old logs to the database\n')
	f.write('Thank you\n')
	f.close()
	# after huge import create the indices (they are slow on massive insert)
	cur.executescript(
		'''
		CREATE UNIQUE INDEX JID_Index ON jids (jid);
		CREATE INDEX JID_ID_Index ON logs (jid_id);
		'''
	)
