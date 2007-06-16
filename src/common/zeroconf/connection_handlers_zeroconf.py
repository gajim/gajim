##
## Copyright (C) 2006 Gajim Team
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <nkour@jabber.org>
##	- Dimitur Kirov <dkirov@gmail.com>
##	- Travis Shirk <travis@pobox.com>
## - Stefan Bethge <stefan@lanpartei.de> 
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
import time
import socket

from calendar import timegm

from common import socks5
import common.xmpp

from common import GnuPG
from common import helpers
from common import gajim
from common.zeroconf import zeroconf
STATUS_LIST = ['offline', 'connecting', 'online', 'chat', 'away', 'xa', 'dnd',
	'invisible']
# kind of events we can wait for an answer
VCARD_PUBLISHED = 'vcard_published'
VCARD_ARRIVED = 'vcard_arrived'
AGENT_REMOVED = 'agent_removed'
HAS_IDLE = True
try:
	import idle
except:
	gajim.log.debug(_('Unable to load idle module'))
	HAS_IDLE = False

class ConnectionVcard:
	def __init__(self): 
		self.vcard_sha = None 
		self.vcard_shas = {} # sha of contacts 
		self.room_jids = [] # list of gc jids so that vcard are saved in a folder

	def add_sha(self, p, send_caps = True): 
		pass 
	
	def add_caps(self, p):
		pass

	def node_to_dict(self, node):
		dict = {}
		
		for info in node.getChildren():
			name = info.getName()
			if name in ('ADR', 'TEL', 'EMAIL'): # we can have several
				if not dict.has_key(name):
					dict[name] = []
				entry = {}
				for c in info.getChildren():
					 entry[c.getName()] = c.getData()
				dict[name].append(entry)
			elif info.getChildren() == []:
				dict[name] = info.getData()
			else:
				dict[name] = {}
				for c in info.getChildren():
					 dict[name][c.getName()] = c.getData()
		
		return dict

	def save_vcard_to_hd(self, full_jid, card):
		jid, nick = gajim.get_room_and_nick_from_fjid(full_jid)
		puny_jid = helpers.sanitize_filename(jid)
		path = os.path.join(gajim.VCARD_PATH, puny_jid)
		if jid in self.room_jids or os.path.isdir(path):
			# remove room_jid file if needed
			if os.path.isfile(path):
				os.remove(path)
			# create folder if needed
			if not os.path.isdir(path):
				os.mkdir(path, 0700)
			puny_nick = helpers.sanitize_filename(nick)
			path_to_file = os.path.join(gajim.VCARD_PATH, puny_jid, puny_nick)
		else:
			path_to_file = path
		fil = open(path_to_file, 'w')
		fil.write(str(card))
		fil.close()
	
	def get_cached_vcard(self, fjid, is_fake_jid = False):
		'''return the vcard as a dict
		return {} if vcard was too old
		return None if we don't have cached vcard'''
		jid, nick = gajim.get_room_and_nick_from_fjid(fjid)
		puny_jid = helpers.sanitize_filename(jid)
		if is_fake_jid:
			puny_nick = helpers.sanitize_filename(nick)
			path_to_file = os.path.join(gajim.VCARD_PATH, puny_jid, puny_nick)
		else:
			path_to_file = os.path.join(gajim.VCARD_PATH, puny_jid)
		if not os.path.isfile(path_to_file):
			return None
		# We have the vcard cached
		f = open(path_to_file)
		c = f.read()
		f.close()
		card = common.xmpp.Node(node = c)
		vcard = self.node_to_dict(card)
		if vcard.has_key('PHOTO'):
			if not isinstance(vcard['PHOTO'], dict):
				del vcard['PHOTO']
			elif vcard['PHOTO'].has_key('SHA'):
				cached_sha = vcard['PHOTO']['SHA']
				if self.vcard_shas.has_key(jid) and self.vcard_shas[jid] != \
					cached_sha:
					# user change his vcard so don't use the cached one
					return {}
		vcard['jid'] = jid
		vcard['resource'] = gajim.get_resource_from_jid(fjid)
		return vcard

	def request_vcard(self, jid = None, is_fake_jid = False):
		pass
		
	def send_vcard(self, vcard):
		pass

class ConnectionBytestream:
	def __init__(self):
		self.files_props = {}
	
	def is_transfer_stoped(self, file_props):
		if file_props.has_key('error') and file_props['error'] != 0:
			return True
		if file_props.has_key('completed') and file_props['completed']:
			return True
		if file_props.has_key('connected') and file_props['connected'] == False:
			return True
		if not file_props.has_key('stopped') or not file_props['stopped']:
			return False
		return True
	
	def send_success_connect_reply(self, streamhost):
		''' send reply to the initiator of FT that we
		made a connection
		'''
		if streamhost is None:
			return None
		iq = common.xmpp.Iq(to = streamhost['initiator'], typ = 'result',
			frm = streamhost['target'])
		iq.setAttr('id', streamhost['id'])
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		stream_tag = query.setTag('streamhost-used')
		stream_tag.setAttr('jid', streamhost['jid'])
		self.connection.send(iq)
	
	def remove_transfers_for_contact(self, contact):
		''' stop all active transfer for contact '''
		for file_props in self.files_props.values():
			if self.is_transfer_stoped(file_props):
				continue
			receiver_jid = unicode(file_props['receiver']).split('/')[0]
			if contact.jid == receiver_jid:
				file_props['error'] = -5
				self.remove_transfer(file_props)
				self.dispatch('FILE_REQUEST_ERROR', (contact.jid, file_props, ''))
			sender_jid = unicode(file_props['sender'])
			if contact.jid == sender_jid:
				file_props['error'] = -3
				self.remove_transfer(file_props)
	
	def remove_all_transfers(self):
		''' stops and removes all active connections from the socks5 pool '''
		for file_props in self.files_props.values():
			self.remove_transfer(file_props, remove_from_list = False)
		del(self.files_props)
		self.files_props = {}
	
	def remove_transfer(self, file_props, remove_from_list = True):
		if file_props is None:
			return
		self.disconnect_transfer(file_props)
		sid = file_props['sid']
		gajim.socks5queue.remove_file_props(self.name, sid)

		if remove_from_list:
			if self.files_props.has_key('sid'):
				del(self.files_props['sid'])
	
	def disconnect_transfer(self, file_props):
		if file_props is None:
			return
		if file_props.has_key('hash'):
			gajim.socks5queue.remove_sender(file_props['hash'])

		if file_props.has_key('streamhosts'):
			for host in file_props['streamhosts']:
				if host.has_key('idx') and host['idx'] > 0:
					gajim.socks5queue.remove_receiver(host['idx'])
					gajim.socks5queue.remove_sender(host['idx'])
	
	def send_socks5_info(self, file_props, fast = True, receiver = None,
		sender = None):
		''' send iq for the present streamhosts and proxies '''
		if type(self.peerhost) != tuple:
			return
		port = gajim.config.get('file_transfers_port')
		ft_add_hosts_to_send = gajim.config.get('ft_add_hosts_to_send')
		if receiver is None:
			receiver = file_props['receiver']
		if sender is None:
			sender = file_props['sender']
		proxyhosts = []
		sha_str = helpers.get_auth_sha(file_props['sid'], sender,
			receiver)
		file_props['sha_str'] = sha_str
		ft_add_hosts = []
		if ft_add_hosts_to_send:
			ft_add_hosts_to_send = map(lambda e:e.strip(),
				ft_add_hosts_to_send.split(','))
			for ft_host in ft_add_hosts_to_send:
				try:
					ft_host = socket.gethostbyname(ft_host)
					ft_add_hosts.append(ft_host)
				except socket.gaierror:
					self.dispatch('ERROR', (_('Wrong host'), _('The host %s you configured as the ft_add_hosts_to_send advanced option is not valid, so ignored.') % ft_host))
		listener = gajim.socks5queue.start_listener(port,
			sha_str, self._result_socks5_sid, file_props['sid'])
		if listener == None:
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

	def send_file_rejection(self, file_props):
		''' informs sender that we refuse to download the file '''
		# user response to ConfirmationDialog may come after we've disconneted
		if not self.connection or self.connected < 2:
			return
		iq = common.xmpp.Protocol(name = 'iq',
			to = unicode(file_props['sender']), typ = 'error')
		iq.setAttr('id', file_props['request-id'])
		err = common.xmpp.ErrorNode(code = '403', typ = 'cancel', name =
			'forbidden', text = 'Offer Declined')
		iq.addChild(node=err)
		self.connection.send(iq)

	def send_file_approval(self, file_props):
		''' send iq, confirming that we want to download the file '''
		# user response to ConfirmationDialog may come after we've disconneted
		if not self.connection or self.connected < 2:
			return
		iq = common.xmpp.Protocol(name = 'iq',
			to = unicode(file_props['sender']), typ = 'result')
		iq.setAttr('id', file_props['request-id'])
		si = iq.setTag('si')
		si.setNamespace(common.xmpp.NS_SI)
		if file_props.has_key('offset') and file_props['offset']:
			file_tag = si.setTag('file')
			file_tag.setNamespace(common.xmpp.NS_FILE)
			range_tag = file_tag.setTag('range')
			range_tag.setAttr('offset', file_props['offset'])
		feature = si.setTag('feature')
		feature.setNamespace(common.xmpp.NS_FEATURE)
		_feature = common.xmpp.DataForm(typ='submit')
		feature.addChild(node=_feature)
		field = _feature.setField('stream-method')
		field.delAttr('type')
		field.setValue(common.xmpp.NS_BYTESTREAM)
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
		if file_props.has_key('desc'):
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
	
	def _result_socks5_sid(self, sid, hash_id):
		''' store the result of sha message from auth. '''
		if not self.files_props.has_key(sid):
			return
		file_props = self.files_props[sid]
		file_props['hash'] = hash_id
		return
	
	def _connect_error(self, to, _id, sid, code = 404):
		''' cb, when there is an error establishing BS connection, or 
		when connection is rejected'''
		msg_dict = {
			404: 'Could not connect to given hosts',
			405: 'Cancel',
			406: 'Not acceptable',
		}
		msg = msg_dict[code]
		iq = None
		iq = common.xmpp.Protocol(name = 'iq', to = to,
			typ = 'error')
		iq.setAttr('id', _id)
		err = iq.setTag('error')
		err.setAttr('code', unicode(code))
		err.setData(msg)
		self.connection.send(iq)
		if code == 404:
			file_props = gajim.socks5queue.get_file_props(self.name, sid)
			if file_props is not None:
				self.disconnect_transfer(file_props)
				file_props['error'] = -3
				self.dispatch('FILE_REQUEST_ERROR', (to, file_props, msg))

	def _proxy_auth_ok(self, proxy):
		'''cb, called after authentication to proxy server '''
		file_props = self.files_props[proxy['sid']]
		iq = common.xmpp.Protocol(name = 'iq', to = proxy['initiator'],
		typ = 'set')
		auth_id = "au_" + proxy['sid']
		iq.setID(auth_id)
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		query.setAttr('sid',  proxy['sid'])
		activate = query.setTag('activate')
		activate.setData(file_props['proxy_receiver'])
		iq.setID(auth_id)
		self.connection.send(iq)
	
	# register xmpppy handlers for bytestream and FT stanzas
	def _bytestreamErrorCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamErrorCB')
		id = unicode(iq_obj.getAttr('id'))
		frm = unicode(iq_obj.getFrom())
		query = iq_obj.getTag('query')
		gajim.proxy65_manager.error_cb(frm, query)
		jid = unicode(iq_obj.getFrom())
		id = id[3:]
		if not self.files_props.has_key(id):
			return
		file_props = self.files_props[id]
		file_props['error'] = -4
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props, ''))
		raise common.xmpp.NodeProcessed
	
	def _bytestreamSetCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamSetCB')
		target = unicode(iq_obj.getAttr('to'))
		id = unicode(iq_obj.getAttr('id'))
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
					'id': id,
					'sid': sid,
					'initiator': unicode(iq_obj.getFrom())
				}
				for attr in item.getAttrs():
					host_dict[attr] = item.getAttr(attr)
				streamhosts.append(host_dict)
		if file_props is None:
			if self.files_props.has_key(sid):
				file_props = self.files_props[sid]
				file_props['fast'] = streamhosts
				if file_props['type'] == 's': 
					if file_props.has_key('streamhosts'):
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
		gajim.log.debug('_ResultCB')
		# if we want to respect jep-0065 we have to check for proxy
		# activation result in any result iq
		real_id = unicode(iq_obj.getAttr('id'))
		if real_id[:3] != 'au_':
			return
		frm = unicode(iq_obj.getFrom())
		id = real_id[3:]
		if self.files_props.has_key(id):
			file_props = self.files_props[id]
			if file_props['streamhost-used']:
				for host in file_props['proxyhosts']:
					if host['initiator'] == frm and host.has_key('idx'):
						gajim.socks5queue.activate_proxy(host['idx'])
						raise common.xmpp.NodeProcessed
	
	def _bytestreamResultCB(self, con, iq_obj):
		gajim.log.debug('_bytestreamResultCB')
		frm = unicode(iq_obj.getFrom())
		real_id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		gajim.proxy65_manager.resolve_result(frm, query)
		
		try:
			streamhost =  query.getTag('streamhost-used')
		except: # this bytestream result is not what we need
			pass
		id = real_id[3:]
		if self.files_props.has_key(id):
			file_props = self.files_props[id]
		else:
			raise common.xmpp.NodeProcessed
		if streamhost is None:
			# proxy approves the activate query
			if real_id[:3] == 'au_':
				id = real_id[3:]
				if not file_props.has_key('streamhost-used') or \
					file_props['streamhost-used'] is False:
					raise common.xmpp.NodeProcessed
				if not file_props.has_key('proxyhosts'):
					raise common.xmpp.NodeProcessed
				for host in file_props['proxyhosts']:
					if host['initiator'] == frm and \
					unicode(query.getAttr('sid')) == file_props['sid']:
						gajim.socks5queue.activate_proxy(host['idx'])
						break
			raise common.xmpp.NodeProcessed
		jid = streamhost.getAttr('jid')
		if file_props.has_key('streamhost-used') and \
			file_props['streamhost-used'] is True:
			raise common.xmpp.NodeProcessed

		if real_id[:3] == 'au_':
			gajim.socks5queue.send_file(file_props, self.name)
			raise common.xmpp.NodeProcessed

		proxy = None
		if file_props.has_key('proxyhosts'):
			for proxyhost in file_props['proxyhosts']:
				if proxyhost['jid'] == jid:
					proxy = proxyhost

		if proxy != None:
			file_props['streamhost-used'] = True
			if not file_props.has_key('streamhosts'):
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
			if file_props.has_key('fast'):
				fasts = file_props['fast']
				if len(fasts) > 0:
					self._connect_error(frm, fasts[0]['id'], file_props['sid'],
						code = 406)
		
		raise common.xmpp.NodeProcessed
	
	def _siResultCB(self, con, iq_obj):
		gajim.log.debug('_siResultCB')
		self.peerhost = con._owner.Connection._sock.getsockname()
		id = iq_obj.getAttr('id')
		if not self.files_props.has_key(id):
			# no such jid
			return
		file_props = self.files_props[id]
		if file_props is None:
			# file properties for jid is none
			return
		if file_props.has_key('request-id'):
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
		gajim.log.debug('_siSetCB')
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
		gajim.socks5queue.add_file_props(self.name, file_props)
		self.dispatch('FILE_REQUEST', (jid, file_props))
		raise common.xmpp.NodeProcessed

	def _siErrorCB(self, con, iq_obj):
		gajim.log.debug('_siErrorCB')
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		if profile != common.xmpp.NS_FILE:
			return
		id = iq_obj.getAttr('id')
		if not self.files_props.has_key(id):
			# no such jid
			return
		file_props = self.files_props[id]
		if file_props is None:
			# file properties for jid is none
			return
		jid = unicode(iq_obj.getFrom())
		file_props['error'] = -3
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props, ''))
		raise common.xmpp.NodeProcessed

class ConnectionHandlersZeroconf(ConnectionVcard, ConnectionBytestream):
	def __init__(self):
		ConnectionVcard.__init__(self)
		ConnectionBytestream.__init__(self)
		# List of IDs we are waiting answers for {id: (type_of_request, data), }
		self.awaiting_answers = {}
		# List of IDs that will produce a timeout is answer doesn't arrive
		# {time_of_the_timeout: (id, message to send to gui), }
		self.awaiting_timeouts = {}
		# keep the jids we auto added (transports contacts) to not send the
		# SUBSCRIBED event to gui
		self.automatically_added = []
		try:
			idle.init()
		except:
			HAS_IDLE = False
			
	def _messageCB(self, ip, con, msg):
		'''Called when we receive a message'''
		msgtxt = msg.getBody()
		msghtml = msg.getXHTML()
		mtype = msg.getType()
		subject = msg.getSubject() # if not there, it's None
		tim = msg.getTimestamp()
		tim = time.strptime(tim, '%Y%m%dT%H:%M:%S')
		tim = time.localtime(timegm(tim))
		frm = msg.getFrom()
		if frm == None:
			for key in self.connection.zeroconf.contacts:
				if ip == self.connection.zeroconf.contacts[key][zeroconf.C_ADDRESS]:
					frm = key
		frm = unicode(frm)
		jid  = frm
		no_log_for = gajim.config.get_per('accounts', self.name,
			'no_log_for').split()
		encrypted = False
		chatstate = None
		encTag = msg.getTag('x', namespace = common.xmpp.NS_ENCRYPTED)
		decmsg = ''
		# invitations
		invite = None
		if not encTag:
			invite = msg.getTag('x', namespace = common.xmpp.NS_MUC_USER)
			if invite and not invite.getTag('invite'):
				invite = None
		delayed = msg.getTag('x', namespace = common.xmpp.NS_DELAY) != None
		msg_id = None
		composing_xep = None
		xtags = msg.getTags('x')
		# chatstates - look for chatstate tags in a message if not delayed
		if not delayed:
			composing_xep = False
			children = msg.getChildren()
			for child in children:
				if child.getNamespace() == 'http://jabber.org/protocol/chatstates':
					chatstate = child.getName()
					composing_xep = 'XEP-0085'
					break
			# No JEP-0085 support, fallback to JEP-0022
			if not chatstate:
				chatstate_child = msg.getTag('x', namespace = common.xmpp.NS_EVENT)
				if chatstate_child:
					chatstate = 'active'
					composing_xep = 'XEP-0022'
					if not msgtxt and chatstate_child.getTag('composing'):
						chatstate = 'composing'
		# JEP-0172 User Nickname
		user_nick = msg.getTagData('nick')
		if not user_nick:
			user_nick = ''

		if encTag and GnuPG.USE_GPG:
			#decrypt
			encmsg = encTag.getData()
			
			keyID = gajim.config.get_per('accounts', self.name, 'keyid')
			if keyID:
				decmsg = self.gpg.decrypt(encmsg, keyID)
		if decmsg:
			msgtxt = decmsg
			encrypted = True
		if mtype == 'error':
			error_msg = msg.getError()
			if not error_msg:
				error_msg = msgtxt
				msgtxt = None
			if self.name not in no_log_for:
				gajim.logger.write('error', frm, error_msg, tim = tim,
					subject = subject)
			self.dispatch('MSGERROR', (frm, msg.getErrorCode(), error_msg, msgtxt,
				tim))
		elif mtype == 'chat': # it's type 'chat'
			if not msg.getTag('body') and chatstate is None: #no <body>
				return
			if msg.getTag('body') and self.name not in no_log_for and jid not in\
				no_log_for and msgtxt:
				msg_id = gajim.logger.write('chat_msg_recv', frm, msgtxt, tim = tim,
					subject = subject)
			self.dispatch('MSG', (frm, msgtxt, tim, encrypted, mtype, subject,
				chatstate, msg_id, composing_xep, user_nick, msghtml))
		elif mtype == 'normal': # it's single message
			if self.name not in no_log_for and jid not in no_log_for and msgtxt:
				gajim.logger.write('single_msg_recv', frm, msgtxt, tim = tim,
					subject = subject)
			if invite:
				self.dispatch('MSG', (frm, msgtxt, tim, encrypted, 'normal',
					subject, chatstate, msg_id, composing_xep, user_nick))
	# END messageCB
	
	def parse_data_form(self, node):
		dic = {}
		tag = node.getTag('title')
		if tag:
			dic['title'] = tag.getData()
		tag = node.getTag('instructions')
		if tag:
			dic['instructions'] = tag.getData()
		i = 0
		for child in node.getChildren():
			if child.getName() != 'field':
				continue
			var = child.getAttr('var')
			ctype = child.getAttr('type')
			label = child.getAttr('label')
			if not var and ctype != 'fixed': # We must have var if type != fixed
				continue
			dic[i] = {}
			if var:
				dic[i]['var'] = var
			if ctype:
				dic[i]['type'] = ctype
			if label:
				dic[i]['label'] = label
			tags = child.getTags('value')
			if len(tags):
				dic[i]['values'] = []
				for tag in tags:
					data = tag.getData()
					if ctype == 'boolean':
						if data in ('yes', 'true', 'assent', '1'):
							data = True
						else:
							data = False
					dic[i]['values'].append(data)
			tag = child.getTag('desc')
			if tag:
				dic[i]['desc'] = tag.getData()
			option_tags = child.getTags('option')
			if len(option_tags):
				dic[i]['options'] = {}
				j = 0
				for option_tag in option_tags:
					dic[i]['options'][j] = {}
					label = option_tag.getAttr('label')
					tags = option_tag.getTags('value')
					dic[i]['options'][j]['values'] = []
					for tag in tags:
						dic[i]['options'][j]['values'].append(tag.getData())
					if not label:
						label = dic[i]['options'][j]['values'][0]
					dic[i]['options'][j]['label'] = label
					j += 1
				if not dic[i].has_key('values'):
					dic[i]['values'] = [dic[i]['options'][0]['values'][0]]
			i += 1
		return dic
	
	def store_metacontacts(self, tags):
		''' fake empty method '''
		# serverside metacontacts  are not supported with zeroconf 
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
