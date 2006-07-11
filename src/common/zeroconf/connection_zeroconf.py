##	common/connection_zeroconf.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##	- Travis Shirk <travis@pobox.com>
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

from common import i18n
_ = i18n._

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
				display_key = self.zeroconf.check_jid(key)
				self.dispatch('NOTIFY', (display_key, self.roster.getStatus(key), self.roster.getMessage(key), 'local', 0, None, 0))
		return self.call_resolve_timeout

	# callbacks called from zeroconf	
	def _on_new_service(self,jid):
		self.roster.setItem(jid)	
		display_jid = self.zeroconf.check_jid(jid)
		self.dispatch('ROSTER_INFO', (display_jid, display_jid, 'both', 'no', self.roster.getGroups(jid)))
		self.dispatch('NOTIFY', (display_jid, self.roster.getStatus(jid), self.roster.getMessage(jid), 'local', 0, None, 0))
		
	
	def _on_remove_service(self,jid):
		self.roster.delItem(jid)
		# 'NOTIFY' (account, (jid, status, status message, resource, priority,
		# keyID, timestamp))
		jid = self.zeroconf.check_jid(jid)
		self.dispatch('NOTIFY', (jid, 'offline', '', 'local', 0, None, 0))


	def connect(self, data = None, show = 'online'):
		if self.connection:
			return self.connection, ''
		
		self.zeroconf.connect()
		self.connection = client_zeroconf.ClientZeroconf(self.zeroconf)
		self.roster = self.connection.getRoster()
		self.dispatch('ROSTER', self.roster)

		#display contacts already detected and resolved
		for jid in self.roster.keys():
			display_jid = self.zeroconf.check_jid(jid)
			self.dispatch('ROSTER_INFO', (display_jid, display_jid, 'both', 'no', self.roster.getGroups(jid)))
			self.dispatch('NOTIFY', (display_jid, self.roster.getStatus(jid), self.roster.getMessage(jid), 'local', 0, None, 0))

		self.connected = STATUS_LIST.index(show)

		# refresh all contacts data all 10 seconds
		self.call_resolve_timeout = True
		gobject.timeout_add(10000, self._on_resolve_timeout)
		
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
		
		# 'connect'
		if show != 'offline' and not self.connected:
			self.on_purpose = False
			self.connect_and_init(show, msg, '')
			if show != 'invisible':
					self.zeroconf.announce()
			else:
					self.connected = STATUS_LIST.index(show)

		# 'disconnect'
		elif show == 'offline' and self.connected:
			self.connected = 0
			self.dispatch('STATUS', 'offline')
			self.disconnect()

		# update status
		elif show != 'offline' and self.connected:
			was_invisible = self.connected == STATUS_LIST.index('invisible')
			self.connected = STATUS_LIST.index(show)
			if show == 'invisible':
				self.zeroconf.remove_announce()
				return
			if was_invisible:
				self.zeroconf.announce()
			if self.connection:
				txt = {}
				txt['status'] = show
				txt['msg'] = msg
				self.zeroconf.update_txt(txt)
		self.dispatch('STATUS', show)

	def get_status(self):
		return STATUS_LIST[self.connected]

	def send_message(self, jid, msg, keyID, type = 'chat', subject='',
	chatstate = None, msg_id = None, composing_jep = None, resource = None):
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
		
		self.zeroconf.send_message(jid, msgtxt)
		
		self.dispatch('MSGSENT', (jid, msg, keyID))
		
	def send_stanza(self, stanza):
		# send a stanza untouched
		print 'connection_zeroconf.py: send_stanza'
		if not self.connection:
			return
		#self.connection.send(stanza)
		pass
	
	def ack_subscribed(self, jid):
		if not self.connection:
			return
		pass

		'''
		gajim.log.debug('ack\'ing subscription complete for %s' % jid)
		p = common.xmpp.Presence(jid, 'subscribe')
		self.connection.send(p)
		'''

	def ack_unsubscribed(self, jid):
		if not self.connection:
			return
		pass
		
		'''		
		gajim.log.debug('ack\'ing unsubscription complete for %s' % jid)
		p = common.xmpp.Presence(jid, 'unsubscribe')
		self.connection.send(p)
		'''

	def request_subscription(self, jid, msg = '', name = '', groups = [],
	auto_auth = False):
		if not self.connection:
			return
		pass
		
		'''		
		gajim.log.debug('subscription request for %s' % jid)
		if auto_auth:
			self.jids_for_auto_auth.append(jid)
		# RFC 3921 section 8.2
		infos = {'jid': jid}
		if name:
			infos['name'] = name
		iq = common.xmpp.Iq('set', common.xmpp.NS_ROSTER)
		q = iq.getTag('query')
		item = q.addChild('item', attrs = infos)
		for g in groups:
			item.addChild('group').setData(g)
		self.connection.send(iq)

		p = common.xmpp.Presence(jid, 'subscribe')
		p = self.add_sha(p)
		if not msg:
			msg = _('I would like to add you to my roster.')
		p.setStatus(msg)
		self.connection.send(p)
		'''

	def send_authorization(self, jid):
		if not self.connection:
			return
		pass
		
		'''		
		p = common.xmpp.Presence(jid, 'subscribed')
		p = self.add_sha(p)
		self.connection.send(p)
		'''

	def refuse_authorization(self, jid):
		if not self.connection:
			return
		pass
		
		'''		
		p = common.xmpp.Presence(jid, 'unsubscribed')
		p = self.add_sha(p)
		self.connection.send(p)
		'''

	def unsubscribe(self, jid, remove_auth = True):
		if not self.connection:
			return
		pass
		
		'''		
		if remove_auth:
			self.connection.getRoster().delItem(jid)
			jid_list = gajim.config.get_per('contacts')
			for j in jid_list:
				if j.startswith(jid):
					gajim.config.del_per('contacts', j)
		else:
			self.connection.getRoster().Unsubscribe(jid)
			self.update_contact(jid, '', [])
		'''

	def unsubscribe_agent(self, agent):
		if not self.connection:
			return
		pass
		
		'''		
		iq = common.xmpp.Iq('set', common.xmpp.NS_REGISTER, to = agent)
		iq.getTag('query').setTag('remove')
		id = self.connection.getAnID()
		iq.setID(id)
		self.awaiting_answers[id] = (AGENT_REMOVED, agent)
		self.connection.send(iq)
		self.connection.getRoster().delItem(agent)
		'''

	def update_contact(self, jid, name, groups):	
		if self.connection:
			self.connection.getRoster().setItem(jid = jid, name = name,
				groups = groups)
	
	def new_account(self, name, config, sync = False):
		'''
		# If a connection already exist we cannot create a new account
		if self.connection :
			return
		self._hostname = config['hostname']
		self.new_account_info = config
		self.name = name
		self.on_connect_success = self._on_new_account
		self.on_connect_failure = self._on_new_account
		self.connect(config)
		'''		

	def _on_new_account(self, con = None, con_type = None):
		'''
		if not con_type:
			self.dispatch('ACC_NOT_OK',
				(_('Could not connect to "%s"') % self._hostname))
			return
		self.on_connect_failure = None
		self.connection = con
		common.xmpp.features_nb.getRegInfo(con, self._hostname)
		'''

	def account_changed(self, new_name):
		self.name = new_name

	def request_last_status_time(self, jid, resource):
		'''
		if not self.connection:
			return
		to_whom_jid = jid
		if resource:
			to_whom_jid += '/' + resource
		iq = common.xmpp.Iq(to = to_whom_jid, typ = 'get', queryNS =\
			common.xmpp.NS_LAST)
		self.connection.send(iq)
		'''
		pass

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
		'''
		# Get Gajim settings as described in JEP 0049
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq3 = iq2.addChild(name='gajim', namespace='gajim:prefs')
		self.connection.send(iq)
		'''
		pass

	def get_bookmarks(self):
		'''
		# Get Bookmarks from storage as described in JEP 0048
		self.bookmarks = [] #avoid multiple bookmarks when re-connecting
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq2.addChild(name='storage', namespace='storage:bookmarks')
		self.connection.send(iq)
		'''
		pass
		
	def store_bookmarks(self):
		'''
		# Send bookmarks to the storage namespace
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='set')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq3 = iq2.addChild(name='storage', namespace='storage:bookmarks')
		for bm in self.bookmarks:
			iq4 = iq3.addChild(name = "conference")
			iq4.setAttr('jid', bm['jid'])
			iq4.setAttr('autojoin', bm['autojoin'])
			iq4.setAttr('name', bm['name'])
			# Only add optional elements if not empty
			# Note: need to handle both None and '' as empty
			#   thus shouldn't use "is not None"
			if bm['nick']:
				iq5 = iq4.setTagData('nick', bm['nick'])
			if bm['password']:
				iq5 = iq4.setTagData('password', bm['password'])
			if bm['print_status']:
				iq5 = iq4.setTagData('print_status', bm['print_status'])
		self.connection.send(iq)
		'''		
		pass

	def get_metacontacts(self):
		'''		
		# Get metacontacts list from storage as described in JEP 0049
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq2.addChild(name='storage', namespace='storage:metacontacts')
		self.connection.send(iq)
		'''
		pass

	'''
	def store_metacontacts(self, tags_list):
		# Send meta contacts to the storage namespace
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='set')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq3 = iq2.addChild(name='storage', namespace='storage:metacontacts')
		for tag in tags_list:
			for data in tags_list[tag]:
				jid = data['jid']
				dict_ = {'jid': jid, 'tag': tag}
				if data.has_key('order'):
					dict_['order'] = data['order']
				iq3.addChild(name = 'meta', attrs = dict_)
		self.connection.send(iq)
	'''

	def send_agent_status(self, agent, ptype):
		'''
		if not self.connection:
			return
		p = common.xmpp.Presence(to = agent, typ = ptype)
		p = self.add_sha(p, ptype != 'unavailable')
		self.connection.send(p)
		'''
		pass


	def join_gc(self, nick, room, server, password):
		'''
		if not self.connection:
			return
		show = helpers.get_xmpp_show(STATUS_LIST[self.connected])
		if show == 'invisible':
			# Never join a room when invisible
			return
		p = common.xmpp.Presence(to = '%s@%s/%s' % (room, server, nick),
			show = show, status = self.status)
		if gajim.config.get('send_sha_in_gc_presence'):
			p = self.add_sha(p)
		t = p.setTag(common.xmpp.NS_MUC + ' x')
		if password:
			t.setTagData('password', password)
		self.connection.send(p)
		#last date/time in history to avoid duplicate
		# FIXME: This JID needs to be normalized; see #1364
		jid='%s@%s' % (room, server)
		last_log = gajim.logger.get_last_date_that_has_logs(jid, is_room = True)
		if last_log is None:
			last_log = 0
		self.last_history_line[jid]= last_log
		'''
		pass
		
	def send_gc_message(self, jid, msg):
		'''
		if not self.connection:
			return
		msg_iq = common.xmpp.Message(jid, msg, typ = 'groupchat')
		self.connection.send(msg_iq)
		self.dispatch('MSGSENT', (jid, msg))
		'''
		pass
		
	def send_gc_subject(self, jid, subject):
		'''
		if not self.connection:
			return
		msg_iq = common.xmpp.Message(jid,typ = 'groupchat', subject = subject)
		self.connection.send(msg_iq)
		'''
		pass
		
	def request_gc_config(self, room_jid):
		'''
		iq = common.xmpp.Iq(typ = 'get', queryNS = common.xmpp.NS_MUC_OWNER,
			to = room_jid)
		self.connection.send(iq)
		'''
		pass

	def change_gc_nick(self, room_jid, nick):
		'''
		if not self.connection:
			return
		p = common.xmpp.Presence(to = '%s/%s' % (room_jid, nick))
		p = self.add_sha(p)
		self.connection.send(p)
		'''
		pass
		
	def send_gc_status(self, nick, jid, show, status):
		'''
		if not self.connection:
			return
		if show == 'invisible':
			show = 'offline'
		ptype = None
		if show == 'offline':
			ptype = 'unavailable'
		show = helpers.get_xmpp_show(show)
		p = common.xmpp.Presence(to = '%s/%s' % (jid, nick), typ = ptype,
			show = show, status = status)
		if gajim.config.get('send_sha_in_gc_presence'):
			p = self.add_sha(p, ptype != 'unavailable')
		# send instantly so when we go offline, status is sent to gc before we
		# disconnect from jabber server
		self.connection.send(p)
		'''
		pass
		
	def gc_set_role(self, room_jid, nick, role, reason = ''):
		'''
		# role is for all the life of the room so it's based on nick
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS =\
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query').setTag('item')
		item.setAttr('nick', nick)
		item.setAttr('role', role)
		if reason:
			item.addChild(name = 'reason', payload = reason)
		self.connection.send(iq)
		'''
		pass
		
	def gc_set_affiliation(self, room_jid, jid, affiliation, reason = ''):
		'''
		# affiliation is for all the life of the room so it's based on jid
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS =\
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query').setTag('item')
		item.setAttr('jid', jid)
		item.setAttr('affiliation', affiliation)
		if reason:
			item.addChild(name = 'reason', payload = reason)
		self.connection.send(iq)
		'''
		pass
		
	def send_gc_affiliation_list(self, room_jid, list):
		'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS = \
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query')
		for jid in list:
			item_tag = item.addChild('item', {'jid': jid,
				'affiliation': list[jid]['affiliation']})
			if list[jid].has_key('reason') and list[jid]['reason']:
				item_tag.setTagData('reason', list[jid]['reason'])
		self.connection.send(iq)
		'''
		pass
		
	def get_affiliation_list(self, room_jid, affiliation):
		'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'get', to = room_jid, queryNS = \
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query').setTag('item')
		item.setAttr('affiliation', affiliation)
		self.connection.send(iq)
		'''
		pass
		
	def send_gc_config(self, room_jid, config):
		'''
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS =\
			common.xmpp.NS_MUC_OWNER)
		query = iq.getTag('query')
		self.build_data_from_dict(query, config)
		self.connection.send(iq)
		'''
		pass
		
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
		'''
		# no need to write this as a class method and keep the value of on_remove_success
		# as a class property as pass it as an argument
		def _on_unregister_account_connect(con):
			self.on_connect_auth = None
			if self.connected > 1:
				hostname = gajim.config.get_per('accounts', self.name, 'hostname')
				iq = common.xmpp.Iq(typ = 'set', to = hostname)
				q = iq.setTag(common.xmpp.NS_REGISTER + ' query').setTag('remove')
				con.send(iq)
				on_remove_success(True)
				return
			on_remove_success(False)
		if self.connected == 0:
			self.on_connect_auth = _on_unregister_account_connect
			self.connect_and_auth()
		else:
			_on_unregister_account_connect(self.connection)
		'''
		pass
		
	def send_invite(self, room, to, reason=''):
		'''
		# sends invitation
		message=common.xmpp.Message(to = room)
		c = message.addChild(name = 'x', namespace = common.xmpp.NS_MUC_USER)
		c = c.addChild(name = 'invite', attrs={'to' : to})
		if reason != '':
			c.setTagData('reason', reason)
		self.connection.send(message)
		'''
		pass
		
	def send_keepalive(self):
		# nothing received for the last foo seconds (60 secs by default)
		if self.connection:
			self.connection.send(' ')
		
# END ConnectionZeroconf
