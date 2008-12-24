# -*- coding:utf-8 -*-
## src/common/gajim.py
##
## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import sys
import logging
import locale

import config
from contacts import Contacts
from events import Events
import xmpp

try:
	import defs
except ImportError:
	print >> sys.stderr, '''defs.py is missing!

If you start gajim from svn:
 * Make sure you have GNU autotools installed.
   This includes the following packages:
    automake >= 1.8
    autoconf >= 2.59
    intltool-0.35
    libtool
 * Run
    $ sh autogen.sh
 * Optionally, install gajim
    $ make
    $ sudo make install

**** Note for translators ****
 You can get the latest string updates, by running:
    $ cd po/
    $ make update-po

'''
	sys.exit(1)

interface = None # The actual interface (the gtk one for the moment)
config = config.Config()
version = config.get('version')
connections = {} # 'account name': 'account (connection.Connection) instance'
verbose = False
ipython_window = None

h = logging.StreamHandler()
f = logging.Formatter('%(asctime)s %(name)s: %(message)s', '%d %b %Y %H:%M:%S')
h.setFormatter(f)
log = logging.getLogger('Gajim')
log.addHandler(h)
del h
del f

import logger
logger = logger.Logger() # init the logger

import configpaths
gajimpaths = configpaths.gajimpaths

LOGPATH = gajimpaths['LOG'] # deprecated
VCARD_PATH = gajimpaths['VCARD']
AVATAR_PATH = gajimpaths['AVATAR']
MY_EMOTS_PATH = gajimpaths['MY_EMOTS']
MY_ICONSETS_PATH = gajimpaths['MY_ICONSETS']
MY_MOOD_ICONSETS_PATH = gajimpaths['MY_MOOD_ICONSETS']
MY_ACTIVITY_ICONSETS_PATH = gajimpaths['MY_ACTIVITY_ICONSETS']
MY_CACERTS =  gajimpaths['MY_CACERTS']
TMP = gajimpaths['TMP']
DATA_DIR = gajimpaths['DATA']
HOME_DIR = gajimpaths['HOME']

try:
	LANG = locale.getdefaultlocale()[0] # en_US, fr_FR, el_GR etc..
except (ValueError, locale.Error):
	# unknown locale, use en is better than fail
	LANG = None
if LANG is None:
	LANG = 'en'
else:
	LANG = LANG[:2] # en, fr, el etc..

os_info = None # used to cache os information

gmail_domains = ['gmail.com', 'googlemail.com']

transport_type = {} # list the type of transport

last_message_time = {} # list of time of the latest incomming message
							# {acct1: {jid1: time1, jid2: time2}, }
encrypted_chats = {} # list of encrypted chats {acct1: [jid1, jid2], ..}

contacts = Contacts()
gc_connected = {} # tell if we are connected to the room or not {acct: {room_jid: True}}
gc_passwords = {} # list of the pass required to enter a room {room_jid: password}
automatic_rooms = {} # list of rooms that must be automaticaly configured and for which we have a list of invities {account: {room_jid: {'invities': []}}}

groups = {} # list of groups
newly_added = {} # list of contacts that has just signed in
to_be_removed = {} # list of contacts that has just signed out

events = Events()

nicks = {} # list of our nick names in each account
# should we block 'contact signed in' notifications for this account?
# this is only for the first 30 seconds after we change our show
# to something else than offline
# can also contain account/transport_jid to block notifications for contacts
# from this transport
block_signed_in_notifications = {}
con_types = {} # type of each connection (ssl, tls, tcp, ...)

sleeper_state = {} # whether we pass auto away / xa or not
#'off': don't use sleeper for this account
#'online': online and use sleeper
#'autoaway': autoaway and use sleeper
#'autoxa': autoxa and use sleeper
status_before_autoaway = {}

# jid of transport contacts for which we need to ask avatar when transport will
# be online
transport_avatar = {} # {transport_jid: [jid_list]}

# Is Gnome configured to activate on single click ?
single_click = False
SHOW_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
	'invisible', 'error']

# zeroconf account name
ZEROCONF_ACC_NAME = 'Local'

HAVE_PYCRYPTO = True
try:
	import Crypto
except ImportError:
	HAVE_PYCRYPTO = False

HAVE_PYSEXY = True
try:
	import sexy
except ImportError:
	HAVE_PYSEXY = False

HAVE_GPG = True
try:
	import GnuPGInterface
except ImportError:
	HAVE_GPG = False
else:
	from os import system
	if system('gpg -h >/dev/null 2>&1'):
		HAVE_GPG = False

gajim_identity = {'type': 'pc', 'category': 'client', 'name': 'Gajim'}
gajim_common_features = [xmpp.NS_BYTESTREAM, xmpp.NS_SI, xmpp.NS_FILE,
	xmpp.NS_MUC, xmpp.NS_MUC_USER, xmpp.NS_MUC_ADMIN, xmpp.NS_MUC_OWNER,
	xmpp.NS_MUC_CONFIG, xmpp.NS_COMMANDS, xmpp.NS_DISCO_INFO, 'ipv6',
	'jabber:iq:gateway', xmpp.NS_LAST, xmpp.NS_PRIVACY, xmpp.NS_PRIVATE,
	xmpp.NS_REGISTER, xmpp.NS_VERSION, xmpp.NS_DATA, xmpp.NS_ENCRYPTED, 'msglog',
	'sslc2s', 'stringprep', xmpp.NS_PING, xmpp.NS_TIME_REVISED, xmpp.NS_SSN,
	xmpp.NS_MOOD, xmpp.NS_ACTIVITY, xmpp.NS_NICK]

# Optional features gajim supports per account
gajim_optional_features = {}

# Capabilities hash per account
caps_hash = {}

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

def get_name_and_server_from_jid(jid):
	name = get_nick_from_jid(jid)
	server = get_server_from_jid(jid)
	return name, server

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
	if interface.msg_win_mgr.get_gc_control(room_jid, account):
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

# [15:34:28] <asterix> we should add contact.fake_jid I think
# [15:34:46] <asterix> so if we know real jid, it wil be in contact.jid, or we look in contact.fake_jid
# [15:32:54] <asterix> they can have resource if we know the real jid
# [15:33:07] <asterix> and that resource is in contact.resource

def get_number_of_accounts():
	'''returns the number of ALL accounts'''
	return len(connections.keys())

def get_number_of_connected_accounts(accounts_list = None):
	'''returns the number of CONNECTED accounts
	you can optionally pass an accounts_list
	and if you do those will be checked, else all will be checked'''
	connected_accounts = 0
	if accounts_list is None:
		accounts = connections.keys()
	else:
		accounts = accounts_list
	for account in accounts:
		if account_is_connected(account):
			connected_accounts = connected_accounts + 1
	return connected_accounts

def account_is_connected(account):
	if account not in connections:
		return False
	if connections[account].connected > 1: # 0 is offline, 1 is connecting
		return True
	else:
		return False

def account_is_disconnected(account):
	return not account_is_connected(account)

def zeroconf_is_connected():
	return account_is_connected(ZEROCONF_ACC_NAME) and \
		config.get_per('accounts', ZEROCONF_ACC_NAME, 'is_zeroconf')

def get_number_of_securely_connected_accounts():
	'''returns the number of the accounts that are SSL/TLS connected'''
	num_of_secured = 0
	for account in connections.keys():
		if account_is_securely_connected(account):
			num_of_secured += 1
	return num_of_secured

def account_is_securely_connected(account):
	if account_is_connected(account) and \
	account in con_types and con_types[account] in ('tls', 'ssl'):
		return True
	else:
		return False

def get_transport_name_from_jid(jid, use_config_setting = True):
	'''returns 'aim', 'gg', 'irc' etc
	if JID is not from transport returns None'''
	#FIXME: jid can be None! one TB I saw had this problem:
	# in the code block # it is a groupchat presence in handle_event_notify
	# jid was None. Yann why?
	if not jid or (use_config_setting and not config.get('use_transports_iconsets')):
		return

	host = get_server_from_jid(jid)
	if host in transport_type:
		return transport_type[host]

	# host is now f.e. icq.foo.org or just icq (sometimes on hacky transports)
	host_splitted = host.split('.')
	if len(host_splitted) != 0:
		# now we support both 'icq.' and 'icq' but not icqsucks.org
		host = host_splitted[0]

	if host in ('aim', 'irc', 'icq', 'msn', 'sms', 'tlen', 'weather', 'yahoo',
	'mrim'):
		return host
	elif host == 'gg':
		return 'gadu-gadu'
	elif host == 'jit':
		return 'icq'
	else:
		return None

def jid_is_transport(jid):
	# if not '@' or '@' starts the jid then it is transport
	if jid.find('@') <= 0:
		return True
	return False

def get_jid_from_account(account_name):
	'''return the jid we use in the given account'''
	name = config.get_per('accounts', account_name, 'name')
	hostname = config.get_per('accounts', account_name, 'hostname')
	jid = name + '@' + hostname
	return jid

def get_our_jids():
	'''returns a list of the jids we use in our accounts'''
	our_jids = list()
	for account in contacts.get_accounts():
		our_jids.append(get_jid_from_account(account))
	return our_jids

def get_hostname_from_account(account_name, use_srv = False):
	'''returns hostname (if custom hostname is used, that is returned)'''
	if use_srv and connections[account_name].connected_hostname:
		return connections[account_name].connected_hostname
	if config.get_per('accounts', account_name, 'use_custom_host'):
		return config.get_per('accounts', account_name, 'custom_host')
	return config.get_per('accounts', account_name, 'hostname')

def get_notification_image_prefix(jid):
	'''returns the prefix for the notification images'''
	transport_name = get_transport_name_from_jid(jid)
	if transport_name in ('aim', 'icq', 'msn', 'yahoo'):
		prefix = transport_name
	else:
		prefix = 'jabber'
	return prefix

def get_name_from_jid(account, jid):
	'''returns from JID's shown name and if no contact returns jids'''
	contact = contacts.get_first_contact_from_jid(account, jid)
	if contact:
		actor = contact.get_shown_name()
	else:
		actor = jid
	return actor

def get_priority(account, show):
	'''return the priority an account must have'''
	if not show:
		show = 'online'

	if show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible') and \
	config.get_per('accounts', account, 'adjust_priority_with_status'):
		return config.get_per('accounts', account, 'autopriority_' + show)
	return config.get_per('accounts', account, 'priority')

# vim: se ts=3:
