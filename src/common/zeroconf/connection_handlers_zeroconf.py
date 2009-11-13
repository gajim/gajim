##
## Copyright (C) 2006 Gajim Team
##
## Contributors for this file:
##	- Yann Leboulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##	- Travis Shirk <travis@pobox.com>
## - Stefan Bethge <stefan@lanpartei.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

import time
import socket

from calendar import timegm

from common import socks5
import common.xmpp

from common import helpers
from common import gajim
from common.zeroconf import zeroconf
from common.commands import ConnectionCommands

import logging
log = logging.getLogger('gajim.c.z.connection_handlers_zeroconf')

STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
	'invisible']
# kind of events we can wait for an answer
VCARD_PUBLISHED = 'vcard_published'
VCARD_ARRIVED = 'vcard_arrived'
AGENT_REMOVED = 'agent_removed'
HAS_IDLE = True
try:
	import idle
except Exception:
	log.debug(_('Unable to load idle module'))
	HAS_IDLE = False

from common import connection_handlers
from session import ChatControlSession

class ConnectionVcard(connection_handlers.ConnectionVcard):
	def add_sha(self, p, send_caps = True):
		pass

	def add_caps(self, p):
		pass

	def request_vcard(self, jid = None, is_fake_jid = False):
		pass

	def send_vcard(self, vcard):
		pass

class ConnectionBytestream(connection_handlers.ConnectionBytestream):
	def send_socks5_info(self, file_props, fast = True, receiver = None,
		sender = None):
		''' send iq for the present streamhosts and proxies '''
		if not isinstance(self.peerhost, tuple):
			return
		port = gajim.config.get('file_transfers_port')
		ft_add_hosts_to_send = gajim.config.get('ft_add_hosts_to_send')
		if receiver is None:
			receiver = file_props['receiver']
		if sender is None:
			sender = file_props['sender']
		sha_str = helpers.get_auth_sha(file_props['sid'], sender,
			receiver)
		file_props['sha_str'] = sha_str
		ft_add_hosts = []
		if ft_add_hosts_to_send:
			ft_add_hosts_to_send = [e.strip() for e in ft_add_hosts_to_send.split(',')]
			for ft_host in ft_add_hosts_to_send:
				try:
					ft_host = socket.gethostbyname(ft_host)
					ft_add_hosts.append(ft_host)
				except socket.gaierror:
					self.dispatch('ERROR', (_('Wrong host'), _('The host %s you configured as the ft_add_hosts_to_send advanced option is not valid, so ignored.') % ft_host))
		listener = gajim.socks5queue.start_listener(port,
			sha_str, self._result_socks5_sid, file_props['sid'])
		if listener is None:
			file_props['error'] = -5
			self.dispatch('FILE_REQUEST_ERROR', (unicode(receiver), file_props,
				''))
			self._connect_error(unicode(receiver), file_props['sid'],
				file_props['sid'], code = 406)
			return

		iq = common.xmpp.Protocol(name = 'iq', to = unicode(receiver),
			typ = 'set')
		file_props['request-id'] = 'id_' + file_props['sid']
		iq.setID(file_props['request-id'])
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		query.setAttr('mode', 'tcp')
		query.setAttr('sid', file_props['sid'])
		for ft_host in ft_add_hosts:
			# The streamhost, if set
			ostreamhost = common.xmpp.Node(tag = 'streamhost')
			query.addChild(node = ostreamhost)
			ostreamhost.setAttr('port', unicode(port))
			ostreamhost.setAttr('host', ft_host)
			ostreamhost.setAttr('jid', sender)
		for thehost in self.peerhost:
			thehost = self.peerhost[0]
			streamhost = common.xmpp.Node(tag = 'streamhost') # My IP
			query.addChild(node = streamhost)
			streamhost.setAttr('port', unicode(port))
			streamhost.setAttr('host', thehost)
			streamhost.setAttr('jid', sender)
		self.connection.send(iq)

	def send_file_request(self, file_props):
		''' send iq for new FT request '''
		if not self.connection or self.connected < 2:
			return
		our_jid = gajim.get_jid_from_account(self.name)
		frm = our_jid
		file_props['sender'] = frm
		fjid = file_props['receiver'].jid
		iq = common.xmpp.Protocol(name = 'iq', to = fjid,
			typ = 'set')
		iq.setID(file_props['sid'])
		self.files_props[file_props['sid']] = file_props
		si = iq.setTag('si')
		si.setNamespace(common.xmpp.NS_SI)
		si.setAttr('profile', common.xmpp.NS_FILE)
		si.setAttr('id', file_props['sid'])
		file_tag = si.setTag('file')
		file_tag.setNamespace(common.xmpp.NS_FILE)
		file_tag.setAttr('name', file_props['name'])
		file_tag.setAttr('size', file_props['size'])
		desc = file_tag.setTag('desc')
		if 'desc' in file_props:
			desc.setData(file_props['desc'])
		file_tag.setTag('range')
		feature = si.setTag('feature')
		feature.setNamespace(common.xmpp.NS_FEATURE)
		_feature = common.xmpp.DataForm(typ='form')
		feature.addChild(node=_feature)
		field = _feature.setField('stream-method')
		field.setAttr('type', 'list-single')
		field.addOption(common.xmpp.NS_BYTESTREAM)
		self.connection.send(iq)

	def _bytestreamSetCB(self, con, iq_obj):
		log.debug('_bytestreamSetCB')
		target = unicode(iq_obj.getAttr('to'))
		id_ = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		sid = unicode(query.getAttr('sid'))
		file_props = gajim.socks5queue.get_file_props(
			self.name, sid)
		streamhosts=[]
		for item in query.getChildren():
			if item.getName() == 'streamhost':
				host_dict={
					'state': 0,
					'target': target,
					'id': id_,
					'sid': sid,
					'initiator': unicode(iq_obj.getFrom())
				}
				for attr in item.getAttrs():
					host_dict[attr] = item.getAttr(attr)
				streamhosts.append(host_dict)
		if file_props is None:
			if sid in self.files_props:
				file_props = self.files_props[sid]
				file_props['fast'] = streamhosts
				if file_props['type'] == 's':
					if 'streamhosts' in file_props:
						file_props['streamhosts'].extend(streamhosts)
					else:
						file_props['streamhosts'] = streamhosts
					if not gajim.socks5queue.get_file_props(self.name, sid):
						gajim.socks5queue.add_file_props(self.name, file_props)
					gajim.socks5queue.connect_to_hosts(self.name, sid,
						self.send_success_connect_reply, None)
				raise common.xmpp.NodeProcessed

		file_props['streamhosts'] = streamhosts
		if file_props['type'] == 'r':
			gajim.socks5queue.connect_to_hosts(self.name, sid,
				self.send_success_connect_reply, self._connect_error)
		raise common.xmpp.NodeProcessed

	def _ResultCB(self, con, iq_obj):
		log.debug('_ResultCB')
		# if we want to respect jep-0065 we have to check for proxy
		# activation result in any result iq
		real_id = unicode(iq_obj.getAttr('id'))
		if not real_id.startswith('au_'):
			return
		frm = unicode(iq_obj.getFrom())
		id_ = real_id[3:]
		if id_ in self.files_props:
			file_props = self.files_props[id_]
			if file_props['streamhost-used']:
				for host in file_props['proxyhosts']:
					if host['initiator'] == frm and 'idx' in host:
						gajim.socks5queue.activate_proxy(host['idx'])
						raise common.xmpp.NodeProcessed

	def _bytestreamResultCB(self, con, iq_obj):
		log.debug('_bytestreamResultCB')
		frm = unicode(iq_obj.getFrom())
		real_id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		gajim.proxy65_manager.resolve_result(frm, query)

		try:
			streamhost =  query.getTag('streamhost-used')
		except Exception: # this bytestream result is not what we need
			pass
		id_ = real_id[3:]
		if id_ in self.files_props:
			file_props = self.files_props[id_]
		else:
			raise common.xmpp.NodeProcessed
		if streamhost is None:
			# proxy approves the activate query
			if real_id.startswith('au_'):
				id_ = real_id[3:]
				if 'streamhost-used' not in file_props or \
					file_props['streamhost-used'] is False:
					raise common.xmpp.NodeProcessed
				if 'proxyhosts' not in file_props:
					raise common.xmpp.NodeProcessed
				for host in file_props['proxyhosts']:
					if host['initiator'] == frm and \
					unicode(query.getAttr('sid')) == file_props['sid']:
						gajim.socks5queue.activate_proxy(host['idx'])
						break
			raise common.xmpp.NodeProcessed
		jid = streamhost.getAttr('jid')
		if 'streamhost-used' in file_props and \
			file_props['streamhost-used'] is True:
			raise common.xmpp.NodeProcessed

		if real_id.startswith('au_'):
			gajim.socks5queue.send_file(file_props, self.name)
			raise common.xmpp.NodeProcessed

		proxy = None
		if 'proxyhosts' in file_props:
			for proxyhost in file_props['proxyhosts']:
				if proxyhost['jid'] == jid:
					proxy = proxyhost

		if proxy is not None:
			file_props['streamhost-used'] = True
			if 'streamhosts' not in file_props:
				file_props['streamhosts'] = []
			file_props['streamhosts'].append(proxy)
			file_props['is_a_proxy'] = True
			receiver = socks5.Socks5Receiver(gajim.idlequeue, proxy, file_props['sid'], file_props)
			gajim.socks5queue.add_receiver(self.name, receiver)
			proxy['idx'] = receiver.queue_idx
			gajim.socks5queue.on_success = self._proxy_auth_ok
			raise common.xmpp.NodeProcessed

		else:
			gajim.socks5queue.send_file(file_props, self.name)
			if 'fast' in file_props:
				fasts = file_props['fast']
				if len(fasts) > 0:
					self._connect_error(frm, fasts[0]['id'], file_props['sid'],
						code = 406)

		raise common.xmpp.NodeProcessed

	def _siResultCB(self, con, iq_obj):
		log.debug('_siResultCB')
		self.peerhost = con._owner.Connection._sock.getsockname()
		id_ = iq_obj.getAttr('id')
		if id_ not in self.files_props:
			# no such jid
			return
		file_props = self.files_props[id_]
		if file_props is None:
			# file properties for jid is none
			return
		if 'request-id' in file_props:
			# we have already sent streamhosts info
			return
		file_props['receiver'] = unicode(iq_obj.getFrom())
		si = iq_obj.getTag('si')
		file_tag = si.getTag('file')
		range_tag = None
		if file_tag:
			range_tag = file_tag.getTag('range')
		if range_tag:
			offset = range_tag.getAttr('offset')
			if offset:
				file_props['offset'] = int(offset)
			length = range_tag.getAttr('length')
			if length:
				file_props['length'] = int(length)
		feature = si.setTag('feature')
		if feature.getNamespace() != common.xmpp.NS_FEATURE:
			return
		form_tag = feature.getTag('x')
		form = common.xmpp.DataForm(node=form_tag)
		field = form.getField('stream-method')
		if field.getValue() != common.xmpp.NS_BYTESTREAM:
			return
		self.send_socks5_info(file_props, fast = True)
		raise common.xmpp.NodeProcessed

	def _siSetCB(self, con, iq_obj):
		log.debug('_siSetCB')
		jid = unicode(iq_obj.getFrom())
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		mime_type = si.getAttr('mime-type')
		if profile != common.xmpp.NS_FILE:
			return
		file_tag = si.getTag('file')
		file_props = {'type': 'r'}
		for attribute in file_tag.getAttrs():
			if attribute in ('name', 'size', 'hash', 'date'):
				val = file_tag.getAttr(attribute)
				if val is None:
					continue
				file_props[attribute] = val
		file_desc_tag = file_tag.getTag('desc')
		if file_desc_tag is not None:
			file_props['desc'] = file_desc_tag.getData()

		if mime_type is not None:
			file_props['mime-type'] = mime_type
		our_jid = gajim.get_jid_from_account(self.name)
		file_props['receiver'] = our_jid
		file_props['sender'] = unicode(iq_obj.getFrom())
		file_props['request-id'] = unicode(iq_obj.getAttr('id'))
		file_props['sid'] = unicode(si.getAttr('id'))
		file_props['transfered_size'] = []
		gajim.socks5queue.add_file_props(self.name, file_props)
		self.dispatch('FILE_REQUEST', (jid, file_props))
		raise common.xmpp.NodeProcessed

	def _siErrorCB(self, con, iq_obj):
		log.debug('_siErrorCB')
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		if profile != common.xmpp.NS_FILE:
			return
		id_ = iq_obj.getAttr('id')
		if id_ not in self.files_props:
			# no such jid
			return
		file_props = self.files_props[id_]
		if file_props is None:
			# file properties for jid is none
			return
		jid = unicode(iq_obj.getFrom())
		file_props['error'] = -3
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props, ''))
		raise common.xmpp.NodeProcessed

class ConnectionHandlersZeroconf(ConnectionVcard, ConnectionBytestream,
ConnectionCommands, connection_handlers.ConnectionHandlersBase):
	def __init__(self):
		ConnectionVcard.__init__(self)
		ConnectionBytestream.__init__(self)
		ConnectionCommands.__init__(self)
		connection_handlers.ConnectionHandlersBase.__init__(self)

		try:
			idle.init()
		except Exception:
			global HAS_IDLE
			HAS_IDLE = False

	def _messageCB(self, ip, con, msg):
		'''Called when we receive a message'''

		log.debug('Zeroconf MessageCB')

		frm = msg.getFrom()
		mtype = msg.getType()
		thread_id = msg.getThread()

		if not mtype:
			mtype = 'normal'

		if frm is None:
			for key in self.connection.zeroconf.contacts:
				if ip == self.connection.zeroconf.contacts[key][zeroconf.C_ADDRESS]:
					frm = key

		frm = unicode(frm)

		session = self.get_or_create_session(frm, thread_id)

		if thread_id and not session.received_thread_id:
			session.received_thread_id = True

		if msg.getTag('feature') and msg.getTag('feature').namespace == \
		common.xmpp.NS_FEATURE:
			if gajim.HAVE_PYCRYPTO:
				self._FeatureNegCB(con, msg, session)
			return

		if msg.getTag('init') and msg.getTag('init').namespace == \
		common.xmpp.NS_ESESSION_INIT:
			self._InitE2ECB(con, msg, session)

		encrypted = False
		tim = msg.getTimestamp()
		tim = helpers.datetime_tuple(tim)
		tim = time.localtime(timegm(tim))

		if msg.getTag('c', namespace = common.xmpp.NS_STANZA_CRYPTO):
			encrypted = True

			try:
				msg = session.decrypt_stanza(msg)
			except Exception:
				self.dispatch('FAILED_DECRYPT', (frm, tim))

		msgtxt = msg.getBody()
		subject = msg.getSubject() # if not there, it's None

		# invitations
		invite = None
		encTag = msg.getTag('x', namespace = common.xmpp.NS_ENCRYPTED)

		if not encTag:
			invite = msg.getTag('x', namespace = common.xmpp.NS_MUC_USER)
			if invite and not invite.getTag('invite'):
				invite = None

		if encTag and self.USE_GPG:
			#decrypt
			encmsg = encTag.getData()

			keyID = gajim.config.get_per('accounts', self.name, 'keyid')
			if keyID:
				decmsg = self.gpg.decrypt(encmsg, keyID)
				# \x00 chars are not allowed in C (so in GTK)
				msgtxt = decmsg.replace('\x00', '')
				encrypted = True

		if mtype == 'error':
			self.dispatch_error_msg(msg, msgtxt, session, frm, tim, subject)
		else:
			# XXX this shouldn't be hardcoded
			if isinstance(session, ChatControlSession):
				session.received(frm, msgtxt, tim, encrypted, msg)
			else:
				session.received(msg)
	# END messageCB

	def store_metacontacts(self, tags):
		''' fake empty method '''
		# serverside metacontacts are not supported with zeroconf
		# (there is no server)
		pass

	def remove_transfers_for_contact(self, contact):
		''' stop all active transfer for contact '''
		pass

	def remove_all_transfers(self):
		''' stops and removes all active connections from the socks5 pool '''
		pass

	def remove_transfer(self, file_props, remove_from_list = True):
		pass

	def _DiscoverItemsGetCB(self, con, iq_obj):
		log.debug('DiscoverItemsGetCB')

		if not self.connection or self.connected < 2:
			return

		if self.commandItemsQuery(con, iq_obj):
			raise common.xmpp.NodeProcessed
		node = iq_obj.getTagAttr('query', 'node')
		if node is None:
			result = iq_obj.buildReply('result')
			self.connection.send(result)
			raise common.xmpp.NodeProcessed
		if node==common.xmpp.NS_COMMANDS:
			self.commandListQuery(con, iq_obj)
			raise common.xmpp.NodeProcessed

# vim: se ts=3:
