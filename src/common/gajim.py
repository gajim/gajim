##	common/gajim.py
##
## Contributors for this file:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Nikos Kouremenos <kourem@gmail.com>
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
import logging
import mutex

import config
from contacts import Contacts

interface = None # The actual interface (the gtk one for the moment)
version = '0.10'
config = config.Config()
connections = {}
verbose = False

h = logging.StreamHandler()
f = logging.Formatter('%(asctime)s %(name)s: %(message)s', '%d %b %Y %H:%M:%S')
h.setFormatter(f)
log = logging.getLogger('Gajim')
log.addHandler(h)

import logger
logger = logger.Logger() # init the logger

if os.name == 'nt':
	DATA_DIR = os.path.join('..', 'data')
	try:
		# Documents and Settings\[User Name]\Application Data\Gajim
		LOGPATH = os.path.join(os.environ['appdata'], 'Gajim', 'Logs') # deprecated
		VCARDPATH = os.path.join(os.environ['appdata'], 'Gajim', 'Vcards')
	except KeyError:
		# win9x, in cwd
		LOGPATH = 'Logs' # deprecated
		VCARDPATH = 'Vcards'
else: # Unices
	DATA_DIR = '../data'
	LOGPATH = os.path.expanduser('~/.gajim/logs') # deprecated
	VCARDPATH = os.path.expanduser('~/.gajim/vcards')

try:
	LOGPATH = LOGPATH.decode(sys.getfilesystemencoding())
	VCARDPATH = VCARDPATH.decode(sys.getfilesystemencoding())
except:
	pass

LANG = os.getenv('LANG') # en_US, fr_FR, el_GR etc..
if LANG:
	LANG = LANG[:2] # en, fr, el etc..
else:
	LANG = 'en'

last_message_time = {} # list of time of the latest incomming message
							# {acct1: {jid1: time1, jid2: time2}, }
encrypted_chats = {} # list of encrypted chats {acct1: [jid1, jid2], ..}

contacts = Contacts()
gc_connected = {} # tell if we are connected to the room or not {acct: {room_jid: True}}
gc_passwords = {} # list of the pass required to enter a room {room_jid: password}

groups = {} # list of groups
newly_added = {} # list of contacts that has just signed in
to_be_removed = {} # list of contacts that has just signed out

awaiting_events = {} # list of messages/FT reveived but not printed
	# awaiting_events[jid] = (type, (data1, data2, ...))
	# if type in ('chat', 'normal'): data = (message, subject, kind, time,
		# encrypted, resource)
		# kind can be (incoming, error)
	# if type in file-request, file-request-error, file-send-error, file-error,
	# file-completed, file-stopped:
		# data = file_props
nicks = {} # list of our nick names in each account
allow_notifications = {} # do we allow notifications for each account ?
con_types = {} # type of each connection (ssl, tls, tcp, ...)

sleeper_state = {} # whether we pass auto away / xa or not
#'off': don't use sleeper for this account
#'online': online and use sleeper
#'autoaway': autoaway and use sleeper
#'autoxa': autoxa and use sleeper
status_before_autoaway = {}
#queues of events from connections...
events_for_ui = {}
#... and its mutex
mutex_events_for_ui = mutex.mutex()

SHOW_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
	'invisible']

def get_nick_from_jid(jid):
	pos = jid.find('@')
	return jid[:pos]

def get_server_from_jid(jid):
	pos = jid.find('@') + 1 # after @
	return jid[pos:]

def get_nick_from_fjid(jid):
	# fake jid is the jid for a contact in a room
	# gaim@conference.jabber.no/nick/nick-continued
	return jid.split('/', 1)[1]

def get_room_name_and_server_from_room_jid(jid):
	room_name = get_nick_from_jid(jid)
	server = get_server_from_jid(jid)
	return room_name, server

def get_room_and_nick_from_fjid(jid):
	# fake jid is the jid for a contact in a room
	# gaim@conference.jabber.no/nick/nick-continued
	# return ('gaim@conference.jabber.no', 'nick/nick-continued')
	l = jid.split('/', 1)
	if len(l) == 1: # No nick
		l.append('')
	return l

def get_real_jid_from_fjid(account, fjid):
	'''returns real jid or returns None
	if we don't know the real jid'''
	room_jid, nick = get_room_and_nick_from_fjid(fjid)
	if not nick: # It's not a fake_jid, it is a real jid
		return fjid # we return the real jid
	real_jid = fjid
	if interface.msg_win_mgr.get_control(room_jid):
		# It's a pm, so if we have real jid it's in contact.jid
		gc_contact = contacts.get_gc_contact(account, room_jid, nick)
		if not gc_contact:
			return
		# gc_contact.jid is None when it's not a real jid (we don't know real jid)
		real_jid = gc_contact.jid
	return real_jid

def get_room_from_fjid(jid):
	return get_room_and_nick_from_fjid(jid)[0]

def get_contact_name_from_jid(account, jid):
	c = contacts.get_first_contact_from_jid(account, jid)
	return c.name

def get_jid_without_resource(jid):
	return jid.split('/')[0]

def construct_fjid(room_jid, nick):
	''' nick is in utf8 (taken from treeview); room_jid is in unicode'''
	# fake jid is the jid for a contact in a room
	# gaim@conference.jabber.org/nick
	if isinstance(nick, str):
		nick = unicode(nick, 'utf-8')
	return room_jid + '/' + nick

def get_resource_from_jid(jid):
	jids = jid.split('/', 1)
	if len(jids) > 1:
		return jids[1] # abc@doremi.org/res/res-continued
	else:
		return ''
	'''\
[15:34:28] <asterix> we should add contact.fake_jid I think
[15:34:46] <asterix> so if we know real jid, it wil be in contact.jid, or we look in contact.fake_jid
[15:32:54] <asterix> they can have resource if we know the real jid
[15:33:07] <asterix> and that resource is in contact.resource
'''

def get_number_of_accounts():
	return len(connections.keys())

def get_transport_name_from_jid(jid, use_config_setting = True):
	'''returns 'aim', 'gg', 'irc' etc
	if JID is not from transport returns None'''
	#FIXME: jid can be None! one TB I saw had this problem:
	# in the code block # it is a groupchat presence in handle_event_notify
	# jid was None. Yann why?
	if not jid or (use_config_setting and not config.get('use_transports_iconsets')):
		return
	host = jid.split('@')[-1]
	if host.startswith('aim'):
		return 'aim'
	elif host.startswith('gg'):
		return 'gadugadu'
	elif host.startswith('irc'):
		return 'irc'
	# abc@icqsucks.org will match as ICQ, but what to do..
	elif host.startswith('icq'):
		return 'icq'
	elif host.startswith('msn'):
		return 'msn'
	elif host.startswith('sms'):
		return 'sms'
	elif host.startswith('tlen'):
		return 'tlen'
	elif host.startswith('weather'):
		return 'weather'
	elif host.startswith('yahoo'):
		return 'yahoo'
	else:
		return None

def jid_is_transport(jid):
	aim = jid.startswith('aim')
	gg = jid.startswith('gg') # gadugadu
	irc = jid.startswith('irc')
	icq = jid.startswith('icq')
	msn = jid.startswith('msn')
	sms = jid.startswith('sms')
	tlen = jid.startswith('tlen')
	yahoo = jid.startswith('yahoo')

	if aim or gg or irc or icq or msn or sms or yahoo or tlen:
		is_transport = True
	else:
		is_transport = False

	return is_transport

def get_jid_from_account(account_name):
	name = config.get_per('accounts', account_name, 'name')
	hostname = config.get_per('accounts', account_name, 'hostname')
	jid = name + '@' + hostname
	return jid

def get_hostname_from_account(account_name, use_srv = False):
	'''returns hostname (if custom hostname is used, that is returned)'''
	if use_srv and connections[account_name].connected_hostname:
		return connections[account_name].connected_hostname
	if config.get_per('accounts', account_name, 'use_custom_host'):
		return config.get_per('accounts', account_name, 'custom_host')
	return config.get_per('accounts', account_name, 'hostname')

def get_first_event(account, jid, typ = None):
	'''returns the first event of the given type from the awaiting_events queue'''
	if not awaiting_events[account].has_key(jid):
		return None
	q = awaiting_events[account][jid]
	if not typ:
		return q[0]
	for ev in q:
		if ev[0] == typ:
			return ev
	return None

def popup_window(account):
	autopopup = config.get('autopopup')
	autopopupaway = config.get('autopopupaway')
	if autopopup and (autopopupaway or connections[account].connected > 3):
		return True
	return False

def show_notification(account):
	if config.get('notify_on_new_message'):
		# check OUR status and if we allow notifications for that status
		if config.get('autopopupaway'): # always show notification
			return True
		if connections[account].connected in (2, 3): # we're online or chat
			return True
	return False
