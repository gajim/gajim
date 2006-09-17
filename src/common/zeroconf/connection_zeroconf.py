##	common/zeroconf/connection_zeroconf.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##	- Travis Shirk <travis@pobox.com>
##  - Stefan Bethge <stefan@lanpartei.de>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2006 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
##                    Stefan Bethge <stefan@lanpartei.de>
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
import random
random.seed()

import signal
if os.name != 'nt':
	signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import getpass
import gobject

from common import helpers
from common import gajim
from common import GnuPG
from common.zeroconf import zeroconf
from common.zeroconf import connection_handlers_zeroconf
from common.zeroconf import client_zeroconf
from connection_handlers_zeroconf import *

USE_GPG = GnuPG.USE_GPG

class ConnectionZeroconf(ConnectionHandlersZeroconf):
	'''Connection class'''
	def __init__(self, name):
		ConnectionHandlersZeroconf.__init__(self)
		self.name = name
		self.connected = 0 # offline
		self.connection = None
		self.gpg = None
		self.is_zeroconf = True
		self.status = ''
		self.old_show = ''
	
		self.call_resolve_timeout = False
		
		#self.time_to_reconnect = None
		#self.new_account_info = None
		self.bookmarks = []

		self.on_purpose = False
		#self.last_io = gajim.idlequeue.current_time()
		#self.last_sent = []
		#self.last_history_line = {}

		#we don't need a password, but must be non-empty
		self.password = 'zeroconf'

		self.privacy_rules_supported = False
		# Do we continue connection when we get roster (send presence,get vcard...)
		self.continue_connect_info = None
		if USE_GPG:
			self.gpg = GnuPG.GnuPG()
			gajim.config.set('usegpg', True)
		else:
			gajim.config.set('usegpg', False)
		
		self.on_connect_success = None
		self.on_connect_failure = None
		self.retrycount = 0
		self.jids_for_auto_auth = [] # list of jid to auto-authorize
		self.get_config_values_or_default()
		self.muc_jid = {} # jid of muc server for each transport type
		self.vcard_supported = False

	def get_config_values_or_default(self):
		''' get name, host, port from config, or 
		create zeroconf account with default values'''
		if not gajim.config.get_per('accounts', 'zeroconf', 'name'):
			print 'Creating zeroconf account'
			gajim.config.add_per('accounts', 'zeroconf')
			gajim.config.set_per('accounts', 'zeroconf', 'autoconnect', True)
			gajim.config.set_per('accounts', 'zeroconf', 'password', 'zeroconf')
			gajim.config.set_per('accounts', 'zeroconf', 'sync_with_global_status', True)
			username = unicode(getpass.getuser())
			gajim.config.set_per('accounts', 'zeroconf', 'name', username)
			#XXX make sure host is US-ASCII
			host = unicode(socket.gethostname())
			gajim.config.set_per('accounts', 'zeroconf', 'hostname', host)
			port = 5298
			gajim.config.set_per('accounts', 'zeroconf', 'custom_port', 5298)
		else:
			username = gajim.config.get_per('accounts', 'zeroconf', 'name')
			host = gajim.config.get_per('accounts', 'zeroconf', 'hostname')
			port = gajim.config.get_per('accounts', 'zeroconf', 'custom_port')
		self.zeroconf = zeroconf.Zeroconf(self._on_new_service, self._on_remove_service, username, host, port)

	# END __init__
	def put_event(self, ev):
		if gajim.handlers.has_key(ev[0]):
			gajim.handlers[ev[0]](self.name, ev[1])

	def dispatch(self, event, data):
		'''always passes account name as first param'''
		self.put_event((event, data))

	def _reconnect(self):
		gajim.log.debug('reconnect')

		signed = self.get_signed_msg(self.status)
			
	def quit(self, kill_core):
	
		if kill_core and self.connected > 1:
			self.disconnect(on_purpose = True)
	
	def test_gpg_passphrase(self, password):
		self.gpg.passphrase = password
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		signed = self.gpg.sign('test', keyID)
		self.gpg.password = None
		return signed != 'BAD_PASSPHRASE'

	def get_signed_msg(self, msg):
		signed = ''
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		if keyID and USE_GPG:
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			if self.connected < 2 and self.gpg.passphrase is None and \
				not use_gpg_agent:
				# We didn't set a passphrase
				self.dispatch('ERROR', (_('OpenPGP passphrase was not given'),
					#%s is the account name here
					_('You will be connected to %s without OpenPGP.') % self.name))
			elif self.gpg.passphrase is not None or use_gpg_agent:
				signed = self.gpg.sign(msg, keyID)
				if signed == 'BAD_PASSPHRASE':
					signed = ''
					if self.connected < 2:
						self.dispatch('BAD_PASSPHRASE', ())
		return signed

	def _on_resolve_timeout(self):
		if self.connected:
			self.zeroconf.resolve_all()
			diffs = self.roster.getDiffs()
			for key in diffs:
				self.roster.setItem(key)
				self.dispatch('NOTIFY', (key, self.roster.getStatus(key), self.roster.getMessage(key), 'local', 0, None, 0))
		return self.call_resolve_timeout

	# callbacks called from zeroconf	
	def _on_new_service(self,jid):
		self.roster.setItem(jid)
		self.dispatch('ROSTER_INFO', (jid, self.roster.getName(jid), 'both', 'no', self.roster.getGroups(jid)))
		self.dispatch('NOTIFY', (jid, self.roster.getStatus(jid), self.roster.getMessage(jid), 'local', 0, None, 0))
		
	
	def _on_remove_service(self,jid):
		self.roster.delItem(jid)
		# 'NOTIFY' (account, (jid, status, status message, resource, priority,
		# keyID, timestamp))
		self.dispatch('NOTIFY', (jid, 'offline', '', 'local', 0, None, 0))


	def connect(self, data = None, show = 'online'):
		if self.connection:
			return self.connection, ''
		
		if self.zeroconf.connect():
			self.connection = client_zeroconf.ClientZeroconf(self.zeroconf)
			self.roster = self.connection.getRoster()
			self.dispatch('ROSTER', self.roster)

			#display contacts already detected and resolved
			for jid in self.roster.keys():
				self.dispatch('ROSTER_INFO', (jid, self.roster.getName(jid), 'both', 'no', self.roster.getGroups(jid)))
				self.dispatch('NOTIFY', (jid, self.roster.getStatus(jid), self.roster.getMessage(jid), 'local', 0, None, 0))

			self.connected = STATUS_LIST.index(show)

			# refresh all contacts data every second
			self.call_resolve_timeout = True
			gobject.timeout_add(1000, self._on_resolve_timeout)
		else:
			pass
			#TODO: display visual notification that we could not connect to avahi

	def connect_and_init(self, show, msg, signed):
		self.continue_connect_info = [show, msg, signed]
		
		self.zeroconf.txt['status'] = show
		self.zeroconf.txt['msg'] = msg
		self.connect('',show)


	def disconnect(self, on_purpose = False):
		self.on_purpose = on_purpose
		self.connected = 0
		self.time_to_reconnect = None
		if self.connection:
			# make sure previous connection is completely closed
			self.last_connection = None
			self.connection = None
			# stop calling the timeout
			self.call_resolve_timeout = False
			self.zeroconf.disconnect()

	def change_status(self, show, msg, sync = False, auto = False):
		if not show in STATUS_LIST:
			return -1

		check = True		#to check for errors from zeroconf

		# 'connect'
		if show != 'offline' and not self.connected:
			self.on_purpose = False
			self.connect_and_init(show, msg, '')
			if show != 'invisible':
					check = self.zeroconf.announce()
			else:
					self.connected = STATUS_LIST.index(show)

		# 'disconnect'
		elif show == 'offline' and self.connected:
			self.disconnect()
			self.dispatch('STATUS', 'offline')
			
		# update status
		elif show != 'offline' and self.connected:
			was_invisible = self.connected == STATUS_LIST.index('invisible')
			self.connected = STATUS_LIST.index(show)
			if show == 'invisible':
				check = check and self.zeroconf.remove_announce()
			elif was_invisible:
				check = check and self.zeroconf.announce()
			if self.connection and not show == 'invisible':
				txt = {}
				txt['status'] = show
				txt['msg'] = msg
				check = check and self.zeroconf.update_txt(txt)

		#stay offline when zeroconf does something wrong
		if check:
			self.dispatch('STATUS', show)
		else:
			self.dispatch('STATUS', 'offline')

	def get_status(self):
		return STATUS_LIST[self.connected]

	def send_message(self, jid, msg, keyID, type = 'chat', subject='',
	chatstate = None, msg_id = None, composing_jep = None, resource = None, 
	user_nick = None):
		print 'connection_zeroconf.py: send_message'

		fjid = jid

		if not self.connection:
			return
		if not msg and chatstate is None:
			return
		
		msgtxt = msg
		msgenc = ''
		if keyID and USE_GPG:
			#encrypt
			msgenc = self.gpg.encrypt(msg, [keyID])
			if msgenc:
				msgtxt = '[This message is encrypted]'
				lang = os.getenv('LANG')
				if lang is not None or lang != 'en': # we're not english
					msgtxt = _('[This message is encrypted]') +\
						' ([This message is encrypted])' # one  in locale and one en

		
		if type == 'chat':
			msg_iq = common.xmpp.Message(to = fjid, body = msgtxt, typ = type)
			
		else:
			if subject:
				msg_iq = common.xmpp.Message(to = fjid, body = msgtxt,
					typ = 'normal', subject = subject)
			else:
				msg_iq = common.xmpp.Message(to = fjid, body = msgtxt,
					typ = 'normal')

		if msgenc:
			msg_iq.setTag(common.xmpp.NS_ENCRYPTED + ' x').setData(msgenc)
		
		# chatstates - if peer supports jep85 or jep22, send chatstates
		# please note that the only valid tag inside a message containing a <body>
		# tag is the active event
		if chatstate is not None:
			if composing_jep == 'JEP-0085' or not composing_jep:
				# JEP-0085
				msg_iq.setTag(chatstate, namespace = common.xmpp.NS_CHATSTATES)
			if composing_jep == 'JEP-0022' or not composing_jep:
				# JEP-0022
				chatstate_node = msg_iq.setTag('x', namespace = common.xmpp.NS_EVENT)
				if not msgtxt: # when no <body>, add <id>
					if not msg_id: # avoid putting 'None' in <id> tag
						msg_id = ''
					chatstate_node.setTagData('id', msg_id)
				# when msgtxt, requests JEP-0022 composing notification
				if chatstate is 'composing' or msgtxt: 
					chatstate_node.addChild(name = 'composing') 

		no_log_for = gajim.config.get_per('accounts', self.name, 'no_log_for')
		ji = gajim.get_jid_without_resource(jid)
		if self.name not in no_log_for and ji not in no_log_for:
			log_msg = msg
			if subject:
				log_msg = _('Subject: %s\n%s') % (subject, msg)
			if log_msg:
				if type == 'chat':
					kind = 'chat_msg_sent'
				else:
					kind = 'single_msg_sent'
				gajim.logger.write(kind, jid, log_msg)
		
		self.zeroconf.send_message(jid, msgtxt, type)
		
		self.dispatch('MSGSENT', (jid, msg, keyID))
		
	def send_stanza(self, stanza):
		# send a stanza untouched
		print 'connection_zeroconf.py: send_stanza'
		if not self.connection:
			return
		#self.connection.send(stanza)
		pass
	
	def ack_subscribed(self, jid):
		gajim.log.debug('This should not happen (ack_subscribed)')

	def ack_unsubscribed(self, jid):
		gajim.log.debug('This should not happen (ack_unsubscribed)')

	def request_subscription(self, jid, msg = '', name = '', groups = [],
	auto_auth = False):
		gajim.log.debug('This should not happen (request_subscription)')

	def send_authorization(self, jid):
		gajim.log.debug('This should not happen (send_authorization)')

	def refuse_authorization(self, jid):
		gajim.log.debug('This should not happen (refuse_authorization)')

	def unsubscribe(self, jid, remove_auth = True):
		gajim.log.debug('This should not happen (unsubscribe)')

	def unsubscribe_agent(self, agent):
		gajim.log.debug('This should not happen (unsubscribe_agent)')

	def update_contact(self, jid, name, groups):	
		if self.connection:
			self.connection.getRoster().setItem(jid = jid, name = name,
				groups = groups)
	
	def new_account(self, name, config, sync = False):
		gajim.log.debug('This should not happen (new_account)')

	def _on_new_account(self, con = None, con_type = None):
		gajim.log.debug('This should not happen (_on_new_account)')

	def account_changed(self, new_name):
		self.name = new_name

	def request_last_status_time(self, jid, resource):
		gajim.log.debug('This should not happen (request_last_status_time)')
		
	def request_os_info(self, jid, resource):
		'''
		if not self.connection:
			return
		to_whom_jid = jid
		if resource:
			to_whom_jid += '/' + resource
		iq = common.xmpp.Iq(to = to_whom_jid, typ = 'get', queryNS =\
			common.xmpp.NS_VERSION)
		self.connection.send(iq)
		'''
		pass

	def get_settings(self):
		gajim.log.debug('This should not happen (get_settings)')

	def get_bookmarks(self):
		gajim.log.debug('This should not happen (get_bookmarks)')
		
	def store_bookmarks(self):
		gajim.log.debug('This should not happen (store_bookmarks)')
		
	def get_metacontacts(self):
		gajim.log.debug('This should not happen (get_metacontacts)')
		
	def send_agent_status(self, agent, ptype):
		gajim.log.debug('This should not happen (send_agent_status)')

	def join_gc(self, nick, room, server, password):
		gajim.log.debug('This should not happen (join_gc)')
		
	def send_gc_message(self, jid, msg):
		gajim.log.debug('This should not happen (send_gc_message)')
		
	def send_gc_subject(self, jid, subject):
		gajim.log.debug('This should not happen (send_gc_subject)')
		
	def request_gc_config(self, room_jid):
		gajim.log.debug('This should not happen (request_gc_config)')
		
	def change_gc_nick(self, room_jid, nick):
		gajim.log.debug('This should not happen (change_gc_nick)')
		
	def send_gc_status(self, nick, jid, show, status):
		gajim.log.debug('This should not happen (send_gc_status)')
		
	def gc_set_role(self, room_jid, nick, role, reason = ''):
		gajim.log.debug('This should not happen (gc_set_role)')
		
	def gc_set_affiliation(self, room_jid, jid, affiliation, reason = ''):
		gajim.log.debug('This should not happen (gc_set_affiliation)')
		
	def send_gc_affiliation_list(self, room_jid, list):
		gajim.log.debug('This should not happen (send_gc_affiliation_list)')
		
	def get_affiliation_list(self, room_jid, affiliation):
		gajim.log.debug('This should not happen (get_affiliation_list)')
		
	def send_gc_config(self, room_jid, config):
		gajim.log.debug('This should not happen (send_gc_config)')
		
	def gpg_passphrase(self, passphrase):
		if USE_GPG:
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			if use_gpg_agent:
				self.gpg.passphrase = None
			else:
				self.gpg.passphrase = passphrase

	def ask_gpg_keys(self):
		if USE_GPG:
			keys = self.gpg.get_keys()
			return keys
		return None

	def ask_gpg_secrete_keys(self):
		if USE_GPG:
			keys = self.gpg.get_secret_keys()
			return keys
		return None

	def change_password(self, password):
		if not self.connection:
			return
		'''
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		username = gajim.config.get_per('accounts', self.name, 'name')
		iq = common.xmpp.Iq(typ = 'set', to = hostname)
		q = iq.setTag(common.xmpp.NS_REGISTER + ' query')
		q.setTagData('username',username)
		q.setTagData('password',password)
		self.connection.send(iq)
		'''
		pass
		
	def unregister_account(self, on_remove_success):
		gajim.log.debug('This should not happen (unregister_account)')
		
	def send_invite(self, room, to, reason=''):
		gajim.log.debug('This should not happen (send_invite)')
		
	def send_keepalive(self):
		# nothing received for the last foo seconds (60 secs by default)
		if self.connection:
			self.connection.send(' ')
		
# END ConnectionZeroconf
