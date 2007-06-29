##	common/connection.py
##
##
## Copyright (C) 2003-2004 Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2003-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov@gmail.com>
## Copyright (C) 2005-2006 Travis Shirk <travis@pobox.com>
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
import socket

import time

try:
	randomsource = random.SystemRandom()
except:
	randomsource = random.Random()
	randomsource.seed()

import signal
if os.name != 'nt':
	signal.signal(signal.SIGPIPE, signal.SIG_DFL)

import common.xmpp
from common import helpers
from common import gajim
from common import GnuPG
from common import passwords

from connection_handlers import *
USE_GPG = GnuPG.USE_GPG

from common.rst_xhtml_generator import create_xhtml

from string import Template
import logging
log = logging.getLogger('gajim.c.connection')

import gtkgui_helpers

class Connection(ConnectionHandlers):
	'''Connection class'''
	def __init__(self, name):
		ConnectionHandlers.__init__(self)
		self.name = name
		self.connected = 0 # offline
		self.connection = None # xmpppy ClientCommon instance
		# this property is used to prevent double connections
		self.last_connection = None # last ClientCommon instance
		self.is_zeroconf = False
		self.gpg = None
		self.status = ''
		self.priority = gajim.get_priority(name, 'offline')
		self.old_show = ''
		# increase/decrease default timeout for server responses
		self.try_connecting_for_foo_secs = 45
		# holds the actual hostname to which we are connected
		self.connected_hostname = None
		self.time_to_reconnect = None
		self.last_time_to_reconnect = None
		self.new_account_info = None
		self.bookmarks = []
		self.annotations = {}
		self.on_purpose = False
		self.last_io = gajim.idlequeue.current_time()
		self.last_sent = []
		self.last_history_line = {}
		self.password = passwords.get_password(name)
		self.server_resource = gajim.config.get_per('accounts', name, 'resource')
		# All valid resource substitution strings should be added to this hash. 
		if self.server_resource:
			self.server_resource = Template(self.server_resource).safe_substitute({
				'hostname': socket.gethostname()
			})
		if gajim.config.get_per('accounts', self.name, 'keep_alives_enabled'):
			self.keepalives = gajim.config.get_per('accounts', self.name,'keep_alive_every_foo_secs')
		else:
			self.keepalives = 0
		self.privacy_rules_supported = False
		self.blocked_list = []
		self.blocked_contacts = []
		self.blocked_groups = []
		self.pep_supported = False
		# Do we continue connection when we get roster (send presence,get vcard...)
		self.continue_connect_info = None
		if USE_GPG:
			self.gpg = GnuPG.GnuPG(gajim.config.get('use_gpg_agent'))
			gajim.config.set('usegpg', True)
		else:
			gajim.config.set('usegpg', False)
		
		self.on_connect_success = None
		self.on_connect_failure = None
		self.retrycount = 0
		self.jids_for_auto_auth = [] # list of jid to auto-authorize
		self.muc_jid = {} # jid of muc server for each transport type
		self.available_transports = {} # list of available transports on this
		# server {'icq': ['icq.server.com', 'icq2.server.com'], }
		self.vcard_supported = True
		self.metacontacts_supported = True
	# END __init__

	def put_event(self, ev):
		if gajim.handlers.has_key(ev[0]):
			gajim.handlers[ev[0]](self.name, ev[1])

	def dispatch(self, event, data):
		'''always passes account name as first param'''
		self.put_event((event, data))


	def _reconnect(self):
		# Do not try to reco while we are already trying
		self.time_to_reconnect = None
		if self.connected < 2: # connection failed
			log.debug('reconnect')
			self.connected = 1
			self.dispatch('STATUS', 'connecting')
			self.retrycount += 1
			signed = self.get_signed_msg(self.status)
			self.on_connect_auth = self._init_roster
			self.connect_and_init(self.old_show, self.status, signed)
		else:
			# reconnect succeeded
			self.time_to_reconnect = None
			self.retrycount = 0
	
	# We are doing disconnect at so many places, better use one function in all
	def disconnect(self, on_purpose = False):
		self.on_purpose = on_purpose
		self.connected = 0
		self.time_to_reconnect = None
		self.privacy_rules_supported = False
		if self.connection:
			# make sure previous connection is completely closed
			gajim.proxy65_manager.disconnect(self.connection)
			self.connection.disconnect()
			self.last_connection = None
			self.connection = None
	
	def _disconnectedReconnCB(self):
		'''Called when we are disconnected'''
		log.debug('disconnectedReconnCB')
		if gajim.account_is_connected(self.name):
			# we cannot change our status to offline or connecting
			# after we auth to server
			self.old_show = STATUS_LIST[self.connected]
		self.connected = 0
		self.dispatch('STATUS', 'offline')
		if not self.on_purpose:
			self.disconnect()
			if gajim.config.get_per('accounts', self.name, 'autoreconnect'):
				self.connected = -1
				self.dispatch('STATUS', 'error')
				if gajim.status_before_autoaway[self.name]:
					# We were auto away. So go back online
					self.status = gajim.status_before_autoaway[self.name]
					gajim.status_before_autoaway[self.name] = ''
					self.old_show = 'online'
				# this check has moved from _reconnect method
				# do exponential backoff until 15 minutes,
				# then small linear increase
				if self.retrycount < 2 or self.last_time_to_reconnect is None:
					self.last_time_to_reconnect = 5
				if self.last_time_to_reconnect < 800:
					self.last_time_to_reconnect *= 1.5
				self.last_time_to_reconnect += randomsource.randint(0, 5)
				self.time_to_reconnect = int(self.last_time_to_reconnect)
				log.info("Reconnect to %s in %ss", self.name, self.time_to_reconnect)
				gajim.idlequeue.set_alarm(self._reconnect_alarm,
					self.time_to_reconnect)
			elif self.on_connect_failure:
				self.on_connect_failure()
				self.on_connect_failure = None
			else:
				# show error dialog
				self._connection_lost()
		else:
			self.disconnect()
		self.on_purpose = False
	# END disconenctedReconnCB
	
	def _connection_lost(self):
		self.disconnect(on_purpose = False)
		self.dispatch('STATUS', 'offline')
		self.dispatch('CONNECTION_LOST',
			(_('Connection with account "%s" has been lost') % self.name,
			_('Reconnect manually.')))

	def _event_dispatcher(self, realm, event, data):
		if realm == common.xmpp.NS_REGISTER:
			if event == common.xmpp.features_nb.REGISTER_DATA_RECEIVED:
				# data is (agent, DataFrom, is_form, error_msg)
				if self.new_account_info and \
				self.new_account_info['hostname'] == data[0]:
					# it's a new account
					if not data[1]: # wrong answer
						self.dispatch('ACC_NOT_OK', (
							_('Transport %s answered wrongly to register request: %s')\
							% (data[0], data[3])))
						return
					req = data[1].asDict()
					req['username'] = self.new_account_info['name']
					req['password'] = self.new_account_info['password']
					def _on_register_result(result):
						if not common.xmpp.isResultNode(result):
							self.dispatch('ACC_NOT_OK', (result.getError()))
							return
						self.password = self.new_account_info['password']
						if USE_GPG:
							self.gpg = GnuPG.GnuPG(gajim.config.get('use_gpg_agent'))
							gajim.config.set('usegpg', True)
						else:
							gajim.config.set('usegpg', False)
						gajim.connections[self.name] = self
						self.dispatch('ACC_OK', (self.new_account_info))
						self.new_account_info = None
						if self.connection:
							self.connection.UnregisterDisconnectHandler(self._on_new_account)
						self.disconnect(on_purpose=True)
					common.xmpp.features_nb.register(self.connection, data[0],
						req, _on_register_result)
					return
				if not data[1]: # wrong answer
					self.dispatch('ERROR', (_('Invalid answer'),
						_('Transport %s answered wrongly to register request: %s') % \
						(data[0], data[3])))
					return
				is_form = data[2]
				if is_form:
					conf = data[1]
				else:
					conf = data[1].asDict()
				self.dispatch('REGISTER_AGENT_INFO', (data[0], conf, is_form))
		elif realm == common.xmpp.NS_PRIVACY:
			if event == common.xmpp.features_nb.PRIVACY_LISTS_RECEIVED:
				# data is (list)
				self.dispatch('PRIVACY_LISTS_RECEIVED', (data))
			elif event == common.xmpp.features_nb.PRIVACY_LIST_RECEIVED:
				# data is (resp)
				if not data:
					return
				rules = []
				name = data.getTag('query').getTag('list').getAttr('name')
				for child in data.getTag('query').getTag('list').getChildren():
					dict_item = child.getAttrs()
					childs = []
					if dict_item.has_key('type'):
						for scnd_child in child.getChildren():
							childs += [scnd_child.getName()]
						rules.append({'action':dict_item['action'],
							'type':dict_item['type'], 'order':dict_item['order'],
							'value':dict_item['value'], 'child':childs})
					else:
						for scnd_child in child.getChildren():
							childs.append(scnd_child.getName())
						rules.append({'action':dict_item['action'],
							'order':dict_item['order'], 'child':childs})
				self.dispatch('PRIVACY_LIST_RECEIVED', (name, rules))
			elif event == common.xmpp.features_nb.PRIVACY_LISTS_ACTIVE_DEFAULT:
				# data is (dict)
				self.dispatch('PRIVACY_LISTS_ACTIVE_DEFAULT', (data))
		elif realm == '':
			if event == common.xmpp.transports.DATA_RECEIVED:
				self.dispatch('STANZA_ARRIVED', unicode(data, errors = 'ignore'))
			elif event == common.xmpp.transports.DATA_SENT:
				self.dispatch('STANZA_SENT', unicode(data))

	def select_next_host(self, hosts):
		hosts_best_prio = []
		best_prio = 65535
		sum_weight = 0
		for h in hosts:
			if h['prio'] < best_prio:
				hosts_best_prio = [h]
				best_prio = h['prio']
				sum_weight = h['weight']
			elif h['prio'] == best_prio:
				hosts_best_prio.append(h)
				sum_weight += h['weight']
		if len(hosts_best_prio) == 1:
			return hosts_best_prio[0]
		r = random.randint(0, sum_weight)
		min_w = sum_weight
		# We return the one for which has the minimum weight and weight >= r
		for h in hosts_best_prio:
			if h['weight'] >= r:
				if h['weight'] <= min_w:
					min_w = h['weight']
		return h

	def connect(self, data = None):
		''' Start a connection to the Jabber server.
		Returns connection, and connection type ('tls', 'ssl', 'tcp', '')
		data MUST contain hostname, usessl, proxy, use_custom_host,
		custom_host (if use_custom_host), custom_port (if use_custom_host)'''
		if self.connection:
			return self.connection, ''

		if data:
			hostname = data['hostname']
			usessl = data['usessl']
			self.try_connecting_for_foo_secs = 45
			p = data['proxy']
			use_srv = True
			use_custom = data['use_custom_host']
			if use_custom:
				custom_h = data['custom_host']
				custom_p = data['custom_port']
		else:
			hostname = gajim.config.get_per('accounts', self.name, 'hostname')
			usessl = gajim.config.get_per('accounts', self.name, 'usessl')
			self.try_connecting_for_foo_secs = gajim.config.get_per('accounts',
				self.name, 'try_connecting_for_foo_secs')
			p = gajim.config.get_per('accounts', self.name, 'proxy')
			use_srv = gajim.config.get_per('accounts', self.name, 'use_srv')
			use_custom = gajim.config.get_per('accounts', self.name,
				'use_custom_host')
			custom_h = gajim.config.get_per('accounts', self.name, 'custom_host')
			custom_p = gajim.config.get_per('accounts', self.name, 'custom_port')

		# create connection if it doesn't already exist
		self.connected = 1
		if p and p in gajim.config.get_per('proxies'):
			proxy = {'host': gajim.config.get_per('proxies', p, 'host')}
			proxy['port'] = gajim.config.get_per('proxies', p, 'port')
			proxy['user'] = gajim.config.get_per('proxies', p, 'user')
			proxy['password'] = gajim.config.get_per('proxies', p, 'pass')
			proxy['type'] = gajim.config.get_per('proxies', p, 'type')
		else:
			proxy = None

		h = hostname
		p = 5222
		# autodetect [for SSL in 5223/443 and for TLS if broadcasted]
		secur = None
		if usessl:
			p = 5223
			secur = 1 # 1 means force SSL no matter what the port will be
			use_srv = False # wants ssl? disable srv lookup
		if use_custom:
			h = custom_h
			p = custom_p
			use_srv = False

		hosts = []
		# SRV resolver
		self._proxy = proxy
		self._secure = secur
		self._hosts = [ {'host': h, 'port': p, 'prio': 10, 'weight': 10} ]
		self._hostname = hostname
		if use_srv:
			# add request for srv query to the resolve, on result '_on_resolve'
			# will be called
			gajim.resolver.resolve('_xmpp-client._tcp.' + helpers.idn_to_ascii(h),
				self._on_resolve)
		else:
			self._on_resolve('', [])

	def _on_resolve(self, host, result_array):
		# SRV query returned at least one valid result, we put it in hosts dict
		if len(result_array) != 0:
			self._hosts = [i for i in result_array]
		self.connect_to_next_host()

	def on_proxy_failure(self, reason):
		log.debug('Connection to proxy failed')
		self.time_to_reconnect = None
		self.on_connect_failure = None
		self.disconnect(on_purpose = True)
		self.dispatch('STATUS', 'offline')
		self.dispatch('CONNECTION_LOST',
			(_('Connection to proxy failed'), reason))

	def connect_to_next_host(self, retry = False):
		if len(self._hosts):
			if self.last_connection:
				self.last_connection.socket.disconnect()
				self.last_connection = None
				self.connection = None
			if gajim.verbose:
				con = common.xmpp.NonBlockingClient(self._hostname, caller = self,
					on_connect = self.on_connect_success,
					on_proxy_failure = self.on_proxy_failure,
					on_connect_failure = self.connect_to_next_host)
			else:
				con = common.xmpp.NonBlockingClient(self._hostname, debug = [], caller = self,
					on_connect = self.on_connect_success,
					on_proxy_failure = self.on_proxy_failure,
					on_connect_failure = self.connect_to_next_host)
			self.last_connection = con
			# increase default timeout for server responses
			common.xmpp.dispatcher_nb.DEFAULT_TIMEOUT_SECONDS = self.try_connecting_for_foo_secs
			con.set_idlequeue(gajim.idlequeue)
			host = self.select_next_host(self._hosts)
			self._current_host = host
			self._hosts.remove(host)

			# FIXME: this is a hack; need a better way
			if self.on_connect_success == self._on_new_account:
				con.RegisterDisconnectHandler(self._on_new_account)

			log.info("Connecting to %s: [%s:%d]", self.name, host['host'], host['port'])
			con.connect((host['host'], host['port']), proxy = self._proxy,
				secure = self._secure)
		else:
			if not retry and self.retrycount == 0:
				log.debug("Out of hosts, giving up connecting to %s", self.name)
				self.time_to_reconnect = None
				if self.on_connect_failure:
					self.on_connect_failure()
					self.on_connect_failure = None
				else:
					# shown error dialog
					self._connection_lost()
			else:
				# try reconnect if connection has failed before auth to server
				self._disconnectedReconnCB()

	def _connect_failure(self, con_type = None):
		if not con_type:
			# we are not retrying, and not conecting
			if not self.retrycount and self.connected != 0:
				self.disconnect(on_purpose = True)
				self.dispatch('STATUS', 'offline')
				self.dispatch('CONNECTION_LOST',
					(_('Could not connect to "%s"') % self._hostname,
					_('Check your connection or try again later.')))

	def _connect_success(self, con, con_type):
		if not self.connected: # We went offline during connecting process
			# FIXME - not possible, maybe it was when we used threads
			return
		self.hosts = []
		if not con_type:
			log.debug('Could not connect to %s:%s' % (self._current_host['host'],
				self._current_host['port']))
		self.connected_hostname = self._current_host['host']
		self.on_connect_failure = None
		con.RegisterDisconnectHandler(self._disconnectedReconnCB)
		log.debug(_('Connected to server %s:%s with %s') % (self._current_host['host'],
			self._current_host['port'], con_type))
		self._register_handlers(con, con_type)

		name = gajim.config.get_per('accounts', self.name, 'name')
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		self.connection = con

		fpr_good = self._check_fingerprint(con, con_type)
		if fpr_good == False:
			self.disconnect(on_purpose = True)
			self.dispatch('STATUS', 'offline')
			self.dispatch('CONNECTION_LOST',
				(_('Security error connecting to "%s"') % self._hostname,
				_("The server's key has changed, or someone is trying to hack your connection.")))
			if self.on_connect_auth:
				self.on_connect_auth(None)
				self.on_connect_auth = None
			return

		if fpr_good == None:
			log.warning(_("Unable to check fingerprint for %s. Connection could be insecure."), hostname)

		if fpr_good == True:
			log.info("Fingerprint found and matched for %s.", hostname)

		con.auth(name, self.password, self.server_resource, 1, self.__on_auth)

		return True

	def _check_fingerprint(self, con, con_type):
		fpr_good = None # None: Unable to check fpr, False: mismatch, True: match

		# FIXME: not tidy
		if not common.xmpp.transports_nb.USE_PYOPENSSL: return None

		# FIXME: find a more permanent place for loading servers.xml
		servers_xml = os.path.join(gajim.DATA_DIR, 'other', 'servers.xml')
		servers = gtkgui_helpers.parse_server_xml(servers_xml)
		servers = dict(map(lambda e: (e[0], e), servers))

		hostname = gajim.config.get_per('accounts', self.name, 'hostname')

		try:
			log.debug("con: %s", con)
			log.debug("con.Connection: %s", con.Connection)
			log.debug("con.Connection.serverDigestSHA1: %s", con.Connection.serverDigestSHA1)
			log.debug("con.Connection.serverDigestMD5: %s", con.Connection.serverDigestMD5)
			sha1 = gtkgui_helpers.HashDigest('sha1', con.Connection.serverDigestSHA1)
			md5 = gtkgui_helpers.HashDigest('md5', con.Connection.serverDigestMD5)
			log.debug("sha1: %s", repr(sha1))
			log.debug("md5: %s", repr(md5))

			sv = servers.get(hostname)
			if sv:
				for got in (sha1, md5):
					expected = sv[2]['digest'].get(got.algo)
					if expected:
						fpr_good = (got == expected)
						break

		except AttributeError:
			if con_type in ('ssl', 'tls'):
				log.error(_("Missing fingerprint in SSL connection to %s") + ':', hostname, exc_info=True)
				# fpr_good = False # FIXME: enable this when sequence is sorted
			else:
				log.debug("Connection to %s doesn't seem to have a fingerprint:", hostname, exc_info=True)

		if fpr_good == False:
			log.error(_("Fingerprint mismatch for %s: Got %s, expected %s"), hostname, got, expected)

		return fpr_good

	def _register_handlers(self, con, con_type):
		self.peerhost = con.get_peerhost()
		# notify the gui about con_type
		self.dispatch('CON_TYPE', con_type)
		ConnectionHandlers._register_handlers(self, con, con_type)

	def __on_auth(self, con, auth):
		if not con:
			self.disconnect(on_purpose = True)
			self.dispatch('STATUS', 'offline')
			self.dispatch('CONNECTION_LOST',
				(_('Could not connect to "%s"') % self._hostname,
				_('Check your connection or try again later')))
			if self.on_connect_auth:
				self.on_connect_auth(None)
				self.on_connect_auth = None
				return
		if not self.connected: # We went offline during connecting process
			if self.on_connect_auth:
				self.on_connect_auth(None)
				self.on_connect_auth = None
				return
		if hasattr(con, 'Resource'):
			self.server_resource = con.Resource
		if auth:
			self.last_io = gajim.idlequeue.current_time()
			self.connected = 2
			self.retrycount = 0
			if self.on_connect_auth:
				self.on_connect_auth(con)
				self.on_connect_auth = None
		else:
			# Forget password if needed
			if not gajim.config.get_per('accounts', self.name, 'savepass'):
				self.password = None
			gajim.log.debug("Couldn't authenticate to %s" % self._hostname)
			self.disconnect(on_purpose = True)
			self.dispatch('STATUS', 'offline')
			self.dispatch('ERROR', (_('Authentication failed with "%s"') % self._hostname,
				_('Please check your login and password for correctness.')))
			if self.on_connect_auth:
				self.on_connect_auth(None)
				self.on_connect_auth = None
	# END connect

	def quit(self, kill_core):
		if kill_core and gajim.account_is_connected(self.name):
			self.disconnect(on_purpose = True)
	
	def get_privacy_lists(self):
		if not self.connection:
			return
		common.xmpp.features_nb.getPrivacyLists(self.connection)

	def sendPing(self, pingTo):
		if not self.connection:
			return
		iq = common.xmpp.Iq('get', to = pingTo.get_full_jid())
		iq.addChild(name = 'ping', namespace = common.xmpp.NS_PING)
		def _on_response(resp):
			timePong = time.time()
			if not common.xmpp.isResultNode(resp):
				self.dispatch('PING_ERROR', (pingTo))
				return
			timeDiff = round(timePong - timePing,2)
			self.dispatch('PING_REPLY', (pingTo, timeDiff))
		self.dispatch('PING_SENT', (pingTo))
		timePing = time.time()
		self.connection.SendAndCallForResponse(iq, _on_response)

	def get_active_default_lists(self):
		if not self.connection:
			return
		common.xmpp.features_nb.getActiveAndDefaultPrivacyLists(self.connection)
	
	def del_privacy_list(self, privacy_list):
		if not self.connection:
			return
		def _on_del_privacy_list_result(result):
			if result:
				self.dispatch('PRIVACY_LIST_REMOVED', privacy_list)
			else:
				self.dispatch('ERROR', (_('Error while removing privacy list'),
					_('Privacy list %s has not been removed. It is maybe active in '
					'one of your connected resources. Deactivate it and try '
					'again.') % privacy_list))
		common.xmpp.features_nb.delPrivacyList(self.connection, privacy_list,
			_on_del_privacy_list_result)
	
	def get_privacy_list(self, title):
		if not self.connection:
			return
		common.xmpp.features_nb.getPrivacyList(self.connection, title)
	
	def set_privacy_list(self, listname, tags):
		if not self.connection:
			return
		common.xmpp.features_nb.setPrivacyList(self.connection, listname, tags)
	
	def set_active_list(self, listname):
		if not self.connection:
			return
		common.xmpp.features_nb.setActivePrivacyList(self.connection, listname, 'active')

	def set_default_list(self, listname):
		if not self.connection:
			return
		common.xmpp.features_nb.setDefaultPrivacyList(self.connection, listname)
	
	def build_privacy_rule(self, name, action):
		'''Build a Privacy rule stanza for invisibility'''
		iq = common.xmpp.Iq('set', common.xmpp.NS_PRIVACY, xmlns = '')
		l = iq.getTag('query').setTag('list', {'name': name})
		i = l.setTag('item', {'action': action, 'order': '1'})
		i.setTag('presence-out')
		return iq

	def activate_privacy_rule(self, name):
		if not self.connection:
			return
		'''activate a privacy rule'''
		iq = common.xmpp.Iq('set', common.xmpp.NS_PRIVACY, xmlns = '')
		iq.getTag('query').setTag('active', {'name': name})
		self.connection.send(iq)

	def send_invisible_presence(self, msg, signed, initial = False):
		# try to set the privacy rule
		iq = self.build_privacy_rule('invisible', 'deny')
		self.connection.SendAndCallForResponse(iq, self._continue_invisible,
			{'msg': msg, 'signed': signed, 'initial': initial})

	def _continue_invisible(self, con, iq_obj, msg, signed, initial):
		ptype = ''
		show = ''
		# FIXME: JEP 126 need some modifications (see http://lists.jabber.ru/pipermail/ejabberd/2005-July/001252.html). So I disable it for the moment
		if 1 or iq_obj.getType() == 'error': #server doesn't support privacy lists
			# We use the old way which is not xmpp complient
			ptype = 'invisible'
			show = 'invisible'
		else:
			# active the privacy rule
			self.privacy_rules_supported = True
			self.activate_privacy_rule('invisible')
		priority = unicode(gajim.get_priority(self.name, show))
		p = common.xmpp.Presence(typ = ptype, priority = priority, show = show)
		p = self.add_sha(p, ptype != 'unavailable')
		if msg:
			p.setStatus(msg)
		if signed:
			p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)
		self.connection.send(p)
		self.priority = priority
		self.dispatch('STATUS', 'invisible')
		if initial:
			#ask our VCard
			self.request_vcard(None)

			#Get bookmarks from private namespace
			self.get_bookmarks()
			
			#Get annotations
			self.get_annotations()

			#Inform GUI we just signed in
			self.dispatch('SIGNED_IN', ())

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

	def connect_and_auth(self):
		self.on_connect_success = self._connect_success
		self.on_connect_failure = self._connect_failure
		self.connect()

	def connect_and_init(self, show, msg, signed):
		self.continue_connect_info = [show, msg, signed]
		self.on_connect_auth = self._init_roster
		self.connect_and_auth()

	def _init_roster(self, con):
		self.connection = con
		if self.connection:
			con.set_send_timeout(self.keepalives, self.send_keepalive)
			self.connection.onreceive(None)
			iq = common.xmpp.Iq('get', common.xmpp.NS_PRIVACY, xmlns = '')
			id = self.connection.getAnID()
			iq.setID(id)
			self.awaiting_answers[id] = (PRIVACY_ARRIVED, )
			self.connection.send(iq)

	def send_custom_status(self, show, msg, jid):
		if not show in STATUS_LIST:
			return -1
		if not self.connection:
			return
		sshow = helpers.get_xmpp_show(show)
		if not msg:
			msg = ''
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		if show == 'offline':
			p = common.xmpp.Presence(typ = 'unavailable', to = jid)
			p = self.add_sha(p, False)
			if msg:
				p.setStatus(msg)
		else:
			signed = self.get_signed_msg(msg)
			priority = unicode(gajim.get_priority(self.name, sshow))
			p = common.xmpp.Presence(typ = None, priority = priority, show = sshow,
				to = jid)
			p = self.add_sha(p)
			if msg:
				p.setStatus(msg)
			if signed:
				p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)
		self.connection.send(p)

	def change_status(self, show, msg, auto = False):
		if not show in STATUS_LIST:
			return -1
		sshow = helpers.get_xmpp_show(show)
		if not msg:
			msg = ''
		keyID = gajim.config.get_per('accounts', self.name, 'keyid')
		signed = ''
		if not auto and not show == 'offline':
			signed = self.get_signed_msg(msg)
		self.status = msg
		if show != 'offline' and not self.connected:
			# set old_show to requested 'show' in case we need to
			# recconect before we auth to server
			self.old_show = show
			self.on_purpose = False 
			self.server_resource = gajim.config.get_per('accounts', self.name,
				'resource')
			self.connect_and_init(show, msg, signed)

		elif show == 'offline':
			self.connected = 0
			if self.connection:
				self.on_purpose = True
				p = common.xmpp.Presence(typ = 'unavailable')
				p = self.add_sha(p, False)
				if msg:
					p.setStatus(msg)
				self.remove_all_transfers()
				self.time_to_reconnect = None
				self.connection.start_disconnect(p, self._on_disconnected)
			else:
				self.time_to_reconnect = None
				self._on_disconnected()

		elif show != 'offline' and self.connected:
			# dont'try to connect, when we are in state 'connecting'
			if self.connected == 1:
				return
			was_invisible = self.connected == STATUS_LIST.index('invisible')
			self.connected = STATUS_LIST.index(show)
			if show == 'invisible':
				self.send_invisible_presence(msg, signed)
				return
			if was_invisible and self.privacy_rules_supported:
				iq = self.build_privacy_rule('visible', 'allow')
				self.connection.send(iq)
				self.activate_privacy_rule('visible')
			priority = unicode(gajim.get_priority(self.name, sshow))
			p = common.xmpp.Presence(typ = None, priority = priority, show = sshow)
			p = self.add_sha(p)
			if msg:
				p.setStatus(msg)
			if signed:
				p.setTag(common.xmpp.NS_SIGNED + ' x').setData(signed)
			if self.connection:
				self.connection.send(p)
				self.priority = priority
			self.dispatch('STATUS', show)

	def _on_disconnected(self):
		''' called when a disconnect request has completed successfully'''
		self.dispatch('STATUS', 'offline')
		self.disconnect()

	def get_status(self):
		return STATUS_LIST[self.connected]


	def send_motd(self, jid, subject = '', msg = '', xhtml = None):
		if not self.connection:
			return
		msg_iq = common.xmpp.Message(to = jid, body = msg, subject = subject,
			xhtml = xhtml)

		self.connection.send(msg_iq)

	def send_message(self, jid, msg, keyID, type = 'chat', subject='',
	chatstate = None, msg_id = None, composing_jep = None, resource = None,
	user_nick = None, xhtml = None, session = None):
		if not self.connection:
			return 1
		if msg and not xhtml and gajim.config.get('rst_formatting_outgoing_messages'):
			xhtml = create_xhtml(msg)
		if not msg and chatstate is None:
			return 2
		fjid = jid
		if resource:
			fjid += '/' + resource
		msgtxt = msg
		msgenc = ''
		if keyID and USE_GPG:
			#encrypt
			msgenc, error = self.gpg.encrypt(msg, [keyID])
			if msgenc and not error:
				msgtxt = '[This message is encrypted]'
				lang = os.getenv('LANG')
				if lang is not None and lang != 'en': # we're not english
					# one  in locale and one en
					msgtxt = _('[This message is *encrypted* (See :JEP:`27`]') +\
						' ([This message is *encrypted* (See :JEP:`27`])'
			else:
				# Encryption failed, do not send message
				tim = time.localtime()
				self.dispatch('MSGNOTSENT', (jid, error, msgtxt, tim))
				return 3
		if msgtxt and not xhtml and gajim.config.get(
			'rst_formatting_outgoing_messages'):
			# Generate a XHTML part using reStructured text markup
			xhtml = create_xhtml(msgtxt)
		if type == 'chat':
			msg_iq = common.xmpp.Message(to = fjid, body = msgtxt, typ = type,
				xhtml = xhtml)
		else:
			if subject:
				msg_iq = common.xmpp.Message(to = fjid, body = msgtxt,
					typ = 'normal', subject = subject, xhtml = xhtml)
			else:
				msg_iq = common.xmpp.Message(to = fjid, body = msgtxt,
					typ = 'normal', xhtml = xhtml)
		if msgenc:
			msg_iq.setTag(common.xmpp.NS_ENCRYPTED + ' x').setData(msgenc)

		# JEP-0172: user_nickname
		if user_nick:
			msg_iq.setTag('nick', namespace = common.xmpp.NS_NICK).setData(
				user_nick)

		# chatstates - if peer supports jep85 or jep22, send chatstates
		# please note that the only valid tag inside a message containing a <body>
		# tag is the active event
		if chatstate is not None:
			if (composing_jep == 'JEP-0085' or not composing_jep) and \
			composing_jep != 'asked_once':
				# JEP-0085
				msg_iq.setTag(chatstate, namespace = common.xmpp.NS_CHATSTATES)
			if composing_jep in ('JEP-0022', 'asked_once') or not composing_jep:
				# JEP-0022
				chatstate_node = msg_iq.setTag('x',
					namespace = common.xmpp.NS_EVENT)
				if not msgtxt: # when no <body>, add <id>
					if not msg_id: # avoid putting 'None' in <id> tag
						msg_id = ''
					chatstate_node.setTagData('id', msg_id)
				# when msgtxt, requests JEP-0022 composing notification
				if chatstate is 'composing' or msgtxt: 
					chatstate_node.addChild(name = 'composing') 

		if session:
			# XEP-0201
			session.last_send = time.time()
			msg_iq.setThread(session.thread_id)

			# XEP-0200
			if session.enable_encryption:
				msg_iq = session.encrypt_stanza(msg_iq)

		self.connection.send(msg_iq)

		if session.is_loggable():
			log_msg = msg
			if subject:
				log_msg = _('Subject: %s\n%s') % (subject, msg)
			if log_msg:
				if type == 'chat':
					kind = 'chat_msg_sent'
				else:
					kind = 'single_msg_sent'
				gajim.logger.write(kind, jid, log_msg)
		self.dispatch('MSGSENT', (jid, msg, keyID))
	
	def send_stanza(self, stanza):
		''' send a stanza untouched '''
		if not self.connection:
			return
		self.connection.send(stanza)
	
	def ack_subscribed(self, jid):
		if not self.connection:
			return
		log.debug('ack\'ing subscription complete for %s' % jid)
		p = common.xmpp.Presence(jid, 'subscribe')
		self.connection.send(p)

	def ack_unsubscribed(self, jid):
		if not self.connection:
			return
		log.debug('ack\'ing unsubscription complete for %s' % jid)
		p = common.xmpp.Presence(jid, 'unsubscribe')
		self.connection.send(p)

	def request_subscription(self, jid, msg = '', name = '', groups = [],
	auto_auth = False, user_nick = ''):
		if not self.connection:
			return
		log.debug('subscription request for %s' % jid)
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
		if user_nick:
			p.setTag('nick', namespace = common.xmpp.NS_NICK).setData(user_nick)
		p = self.add_sha(p)
		if msg:
			p.setStatus(msg)
		self.connection.send(p)

	def send_authorization(self, jid):
		if not self.connection:
			return
		p = common.xmpp.Presence(jid, 'subscribed')
		p = self.add_sha(p)
		self.connection.send(p)

	def refuse_authorization(self, jid):
		if not self.connection:
			return
		p = common.xmpp.Presence(jid, 'unsubscribed')
		p = self.add_sha(p)
		self.connection.send(p)

	def unsubscribe(self, jid, remove_auth = True):
		if not self.connection:
			return
		if remove_auth:
			self.connection.getRoster().delItem(jid)
			jid_list = gajim.config.get_per('contacts')
			for j in jid_list:
				if j.startswith(jid):
					gajim.config.del_per('contacts', j)
		else:
			self.connection.getRoster().Unsubscribe(jid)
			self.update_contact(jid, '', [])

	def unsubscribe_agent(self, agent):
		if not self.connection:
			return
		iq = common.xmpp.Iq('set', common.xmpp.NS_REGISTER, to = agent)
		iq.getTag('query').setTag('remove')
		id = self.connection.getAnID()
		iq.setID(id)
		self.awaiting_answers[id] = (AGENT_REMOVED, agent)
		self.connection.send(iq)
		self.connection.getRoster().delItem(agent)

	def update_contact(self, jid, name, groups):
		'''update roster item on jabber server'''
		if self.connection:
			self.connection.getRoster().setItem(jid = jid, name = name,
				groups = groups)

	def new_account(self, name, config, sync = False):
		# If a connection already exist we cannot create a new account
		if self.connection:
			return
		self._hostname = config['hostname']
		self.server_resource = config['resource']
		self.new_account_info = config
		self.name = name
		self.on_connect_success = self._on_new_account
		self.on_connect_failure = self._on_new_account
		self.connect(config)

	def _on_new_account(self, con = None, con_type = None):
		if not con_type:
			self.dispatch('ACC_NOT_OK',
				(_('Could not connect to "%s"') % self._hostname))
			return
		self.on_connect_failure = None
		self.connection = con
		#if con:
		#	con.RegisterDisconnectHandler(self._on_new_account)
		common.xmpp.features_nb.getRegInfo(con, self._hostname)

	def account_changed(self, new_name):
		self.name = new_name

	def request_last_status_time(self, jid, resource):
		if not self.connection:
			return
		to_whom_jid = jid
		if resource:
			to_whom_jid += '/' + resource
		iq = common.xmpp.Iq(to = to_whom_jid, typ = 'get', queryNS =\
			common.xmpp.NS_LAST)
		self.connection.send(iq)

	def request_os_info(self, jid, resource):
		if not self.connection:
			return
		# If we are invisible, do not request
		if self.connected == gajim.SHOW_LIST.index('invisible'):
			self.dispatch('OS_INFO', (jid, resource, _('Not fetched because of invisible status'), _('Not fetched because of invisible status')))
			return
		to_whom_jid = jid
		if resource:
			to_whom_jid += '/' + resource
		iq = common.xmpp.Iq(to = to_whom_jid, typ = 'get', queryNS =\
			common.xmpp.NS_VERSION)
		self.connection.send(iq)

	def get_settings(self):
		''' Get Gajim settings as described in JEP 0049 '''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq3 = iq2.addChild(name='gajim', namespace='gajim:prefs')
		self.connection.send(iq)

	def get_bookmarks(self):
		'''Get Bookmarks from storage as described in JEP 0048'''
		self.bookmarks = [] #avoid multiple bookmarks when re-connecting
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq2.addChild(name='storage', namespace='storage:bookmarks')
		self.connection.send(iq)

	def store_bookmarks(self):
		''' Send bookmarks to the storage namespace '''
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
			if bm.get('nick', None):
				iq5 = iq4.setTagData('nick', bm['nick'])
			if bm.get('password', None):
				iq5 = iq4.setTagData('password', bm['password'])
			if bm.get('print_status', None):
				iq5 = iq4.setTagData('print_status', bm['print_status'])
		self.connection.send(iq)

	def get_annotations(self):
		'''Get Annonations from storage as described in XEP 0048, and XEP 0145'''
		self.annotations = {}
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq2.addChild(name='storage', namespace='storage:rosternotes')
		self.connection.send(iq)

	def store_annotations(self):
		'''Set Annonations in private storage as described in XEP 0048, and XEP 0145'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='set')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq3 = iq2.addChild(name='storage', namespace='storage:rosternotes')
		for jid in self.annotations.keys():
			if self.annotations[jid]:
				iq4 = iq3.addChild(name = "note")
				iq4.setAttr('jid', jid)
				iq4.setData(self.annotations[jid])
		self.connection.send(iq)


	def get_metacontacts(self):
		'''Get metacontacts list from storage as described in JEP 0049'''
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ='get')
		iq2 = iq.addChild(name='query', namespace='jabber:iq:private')
		iq2.addChild(name='storage', namespace='storage:metacontacts')
		id = self.connection.getAnID()
		iq.setID(id)
		self.awaiting_answers[id] = (METACONTACTS_ARRIVED, )
		self.connection.send(iq)

	def store_metacontacts(self, tags_list):
		''' Send meta contacts to the storage namespace '''
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

	def send_agent_status(self, agent, ptype):
		if not self.connection:
			return
		show = helpers.get_xmpp_show(STATUS_LIST[self.connected])
		p = common.xmpp.Presence(to = agent, typ = ptype, show = show)
		p = self.add_sha(p, ptype != 'unavailable')
		self.connection.send(p)

	def join_gc(self, nick, room_jid, password):
		# FIXME: This room JID needs to be normalized; see #1364
		if not self.connection:
			return
		show = helpers.get_xmpp_show(STATUS_LIST[self.connected])
		if show == 'invisible':
			# Never join a room when invisible
			return
		p = common.xmpp.Presence(to = '%s/%s' % (room_jid, nick),
			show = show, status = self.status)
		if gajim.config.get('send_sha_in_gc_presence'):
			p = self.add_sha(p)
		t = p.setTag(common.xmpp.NS_MUC + ' x')
		if password:
			t.setTagData('password', password)
		self.connection.send(p)

		# last date/time in history to avoid duplicate
		if not self.last_history_line.has_key(room_jid): 
			# Not in memory, get it from DB
			last_log = gajim.logger.get_last_date_that_has_logs(room_jid,
				is_room = True)
			if last_log is None:
				last_log = 0
			self.last_history_line[room_jid]= last_log

	def send_gc_message(self, jid, msg, xhtml = None):
		if not self.connection:
			return
		if not xhtml and gajim.config.get('rst_formatting_outgoing_messages'):
			xhtml = create_xhtml(msg)
		msg_iq = common.xmpp.Message(jid, msg, typ = 'groupchat', xhtml = xhtml)
		self.connection.send(msg_iq)
		self.dispatch('MSGSENT', (jid, msg))

	def send_gc_subject(self, jid, subject):
		if not self.connection:
			return
		msg_iq = common.xmpp.Message(jid,typ = 'groupchat', subject = subject)
		self.connection.send(msg_iq)

	def request_gc_config(self, room_jid):
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'get', queryNS = common.xmpp.NS_MUC_OWNER,
			to = room_jid)
		self.connection.send(iq)

	def destroy_gc_room(self, room_jid, reason = '', jid = ''):
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'set', queryNS = common.xmpp.NS_MUC_OWNER,
			to = room_jid)
		destroy = iq.getTag('query').setTag('destroy')
		if reason:
			destroy.setTagData('reason', reason)
		if jid:
			destroy.setAttr('jid', jid)
		self.connection.send(iq)

	def send_gc_status(self, nick, jid, show, status):
		if not self.connection:
			return
		if show == 'invisible':
			show = 'offline'
		ptype = None
		if show == 'offline':
			ptype = 'unavailable'
		xmpp_show = helpers.get_xmpp_show(show)
		p = common.xmpp.Presence(to = '%s/%s' % (jid, nick), typ = ptype,
			show = xmpp_show, status = status)
		if gajim.config.get('send_sha_in_gc_presence') and show != 'offline':
			p = self.add_sha(p, ptype != 'unavailable')
		# send instantly so when we go offline, status is sent to gc before we
		# disconnect from jabber server
		self.connection.send(p)
		# Save the time we quit to avoid duplicate logs AND be faster than 
		# get that date from DB
		self.last_history_line[jid] = time.time()

	def gc_set_role(self, room_jid, nick, role, reason = ''):
		'''role is for all the life of the room so it's based on nick'''
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

	def gc_set_affiliation(self, room_jid, jid, affiliation, reason = ''):
		'''affiliation is for all the life of the room so it's based on jid'''
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

	def send_gc_affiliation_list(self, room_jid, list):
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

	def get_affiliation_list(self, room_jid, affiliation):
		if not self.connection:
			return
		iq = common.xmpp.Iq(typ = 'get', to = room_jid, queryNS = \
			common.xmpp.NS_MUC_ADMIN)
		item = iq.getTag('query').setTag('item')
		item.setAttr('affiliation', affiliation)
		self.connection.send(iq)

	def send_gc_config(self, room_jid, form):
		iq = common.xmpp.Iq(typ = 'set', to = room_jid, queryNS =\
			common.xmpp.NS_MUC_OWNER)
		query = iq.getTag('query')
		form.setAttr('type', 'submit')
		query.addChild(node = form)
		self.connection.send(iq)

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
		hostname = gajim.config.get_per('accounts', self.name, 'hostname')
		username = gajim.config.get_per('accounts', self.name, 'name')
		iq = common.xmpp.Iq(typ = 'set', to = hostname)
		q = iq.setTag(common.xmpp.NS_REGISTER + ' query')
		q.setTagData('username',username)
		q.setTagData('password',password)
		self.connection.send(iq)

	def unregister_account(self, on_remove_success):
		# no need to write this as a class method and keep the value of
		# on_remove_success as a class property as pass it as an argument
		def _on_unregister_account_connect(con):
			self.on_connect_auth = None
			if gajim.account_is_connected(self.name):
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

	def send_invite(self, room, to, reason=''):
		'''sends invitation'''
		message=common.xmpp.Message(to = room)
		c = message.addChild(name = 'x', namespace = common.xmpp.NS_MUC_USER)
		c = c.addChild(name = 'invite', attrs={'to' : to})
		if reason != '':
			c.setTagData('reason', reason)
		self.connection.send(message)

	def send_keepalive(self):
		# nothing received for the last foo seconds (60 secs by default)
		if self.connection:
			self.connection.send(' ')

	def _reconnect_alarm(self):
		if self.time_to_reconnect:
			if self.connected < 2:
				self._reconnect()
			else:
				self.time_to_reconnect = None

	def request_search_fields(self, jid):
		iq = common.xmpp.Iq(typ = 'get', to = jid, queryNS = \
			common.xmpp.NS_SEARCH)
		self.connection.send(iq)

	def send_search_form(self, jid, form, is_form):
		iq = common.xmpp.Iq(typ = 'set', to = jid, queryNS = \
			common.xmpp.NS_SEARCH)
		item = iq.getTag('query')
		if is_form:
			item.addChild(node = form)
		else:
			for i in form.keys():
				item.setTagData(i,form[i])
		def _on_response(resp):
			jid = jid = helpers.get_jid_from_iq(resp)
			tag = resp.getTag('query', namespace = common.xmpp.NS_SEARCH)
			if not tag:
				self.dispatch('SEARCH_RESULT', (jid, None, False))
				return
			df = tag.getTag('x', namespace = common.xmpp.NS_DATA)
			if df:
				self.dispatch('SEARCH_RESULT', (jid, df, True))
				return
			df = []
			for item in tag.getTags('item'):
				f = {}
				for i in item.getPayload():
					f[i.getName()] = i.getData()
				df.append(f)
			self.dispatch('SEARCH_RESULT', (jid, df, False))

		self.connection.SendAndCallForResponse(iq, _on_response)

# END Connection
