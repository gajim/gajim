##	common/gajim.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
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
import logging
import mutex

import common.config
import common.logger

version = '0.9'
config = common.config.Config()
connections = {}
verbose = False

h = logging.StreamHandler()
f = logging.Formatter('%(asctime)s %(name)s: %(message)s', '%d %b %Y %H:%M:%S')
h.setFormatter(f)
log = logging.getLogger('Gajim')
log.addHandler(h)

logger = common.logger.Logger()
DATA_DIR = '../data'
LANG = os.getenv('LANG') # en_US, fr_FR, el_GR etc..
if LANG:
	LANG = LANG[:2] # en, fr, el etc..
else:
	LANG = 'en'

last_message_time = {} # list of time of the latest incomming message
							# {acct1: {jid1: time1, jid2: time2}, }
encrypted_chats = {} # list of encrypted chats {acct1: [jid1, jid2], ..}

contacts = {} # list of contacts {acct: {jid1: [C1, C2]}, } one Contact per resource
gc_contacts = {} # list of contacts that are in gc {acct: {room_jid: {nick: C}}}
gc_connected = {} # tell if we are connected to the room or not {room_jid: True}

groups = {} # list of groups
newly_added = {} # list of contacts that has just signed in
to_be_removed = {} # list of contacts that has just signed out
awaiting_messages = {} # list of messages reveived but not printed
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
	if len(l) == 1: #No nick
		l.append('')
	return l

def get_contact_instances_from_jid(account, jid):
	''' we may have two or more resources on that jid '''
	if jid in contacts[account]:
		contacts_instances = contacts[account][jid]
		return contacts_instances

def get_first_contact_instance_from_jid(account, jid):
	contact = None
	if jid in contacts[account]:
		contact = contacts[account][jid][0]
	else: # it's fake jid
		#FIXME: problem see comment in next line
		room, nick = \
			get_room_and_nick_from_fjid(jid) # if we ban/kick we now real jid
		if gc_contacts[account].has_key(room) and \
		nick in gc_contacts[account][room]:
			contact = gc_contacts[account][room][nick] 
	return contact

def get_contact_instance_with_highest_priority(account, jid):
	contact_instances = contacts[account][jid]
	return get_highest_prio_contact_from_contacts(contact_instances)

def get_contact_name_from_jid(account, jid):
	return contacts[account][jid][0].name
	
def get_highest_prio_contact_from_contacts(contacts):
	prim_contact = None # primary contact
	for contact in contacts:
		if prim_contact == None or int(contact.priority) > \
			int(prim_contact.priority):
			prim_contact = contact
	return prim_contact

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
	return jid.split('/', 1)[1] # abc@doremi.org/res/res-continued
	'''\
[15:34:28] <asterix> we should add contact.fake_jid I think
[15:34:46] <asterix> so if we know real jid, it wil be in contact.jid, or we look in contact.fake_jid
[15:32:54] <asterix> they can have resource if we know the real jid
[15:33:07] <asterix> and that resource is in contact.resource
'''

def get_number_of_accounts():
	return len(connections.keys())

def get_transport_name_from_jid(jid, use_config_setting = True):
	'''returns 'aim', 'gg', 'irc' etc'''
	#FIXME: jid can be None! one TB I saw had this problem:
	# in the code block # it is a groupchat presence in handle_event_notify
	# jid was None. Yann why?
	if not jid or (use_config_setting and not config.get('use_transports_iconsets')):
		return
	host = jid.split('@')[-1]
	if host.startswith('aim'):
		return 'aim'
	elif host.startswith('gadugadu'):
		return 'gadugadu'
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

def jid_is_transport(jid):
	is_transport = jid.startswith('aim') or jid.startswith('gadugadu') or\
			jid.startswith('irc') or jid.startswith('icq') or\
			jid.startswith('msn') or jid.startswith('sms') or\
			jid.startswith('yahoo')

def get_jid_from_account(account_name):
	name = config.get_per('accounts', account_name, 'name')
	hostname = config.get_per('accounts', account_name, 'hostname')
	jid = name + '@' + hostname
	return jid

def get_hostname_from_account(account_name):
	'''returns hostname (if custom hostname is used, that is returned)'''
	if config.get_per('accounts', account_name, 'use_custom_host'):
		return config.get_per('accounts', account_name, 'custom_host')
	return config.get_per('accounts', account_name, 'hostname')
	
