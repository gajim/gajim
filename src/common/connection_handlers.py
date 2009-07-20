# -*- coding:utf-8 -*-
## src/common/connection_handlers.py
##
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
##                    Junglecow J <junglecow AT gmail.com>
## Copyright (C) 2006-2007 Tomasz Melcer <liori AT exroot.org>
##                         Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Jean-Marie Traissard <jim AT lapin.org>
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

import os
import base64
import socket
import sys
import operator
import hashlib

from time import (altzone, daylight, gmtime, localtime, mktime, strftime,
	time as time_time, timezone, tzname)
from calendar import timegm
import datetime

import socks5
import common.xmpp

from common import helpers
from common import gajim
from common import atom
from common import pep
from common import exceptions
from common.commands import ConnectionCommands
from common.pubsub import ConnectionPubSub
from common.caps import ConnectionCaps

from common import dbus_support
if dbus_support.supported:
	import dbus
	from music_track_listener import MusicTrackListener

import logging
log = logging.getLogger('gajim.c.connection_handlers')

# kind of events we can wait for an answer
VCARD_PUBLISHED = 'vcard_published'
VCARD_ARRIVED = 'vcard_arrived'
AGENT_REMOVED = 'agent_removed'
METACONTACTS_ARRIVED = 'metacontacts_arrived'
ROSTER_ARRIVED = 'roster_arrived'
PRIVACY_ARRIVED = 'privacy_arrived'
PEP_CONFIG = 'pep_config'
HAS_IDLE = True
try:
	import idle
except Exception:
	log.debug(_('Unable to load idle module'))
	HAS_IDLE = False

class ConnectionBytestream:
	def __init__(self):
		self.files_props = {}
		self.awaiting_xmpp_ping_id = None

	def is_transfer_stopped(self, file_props):
		if 'error' in file_props and file_props['error'] != 0:
			return True
		if 'completed' in file_props and file_props['completed']:
			return True
		if 'connected' in file_props and file_props['connected'] == False:
			return True
		if 'stopped' not in file_props or not file_props['stopped']:
			return False
		return True

	def send_success_connect_reply(self, streamhost):
		''' send reply to the initiator of FT that we
		made a connection
		'''
		if not self.connection or self.connected < 2:
			return
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
			if self.is_transfer_stopped(file_props):
				continue
			receiver_jid = unicode(file_props['receiver'])
			if contact.get_full_jid() == receiver_jid:
				file_props['error'] = -5
				self.remove_transfer(file_props)
				self.dispatch('FILE_REQUEST_ERROR', (contact.jid, file_props, ''))
			sender_jid = unicode(file_props['sender'])
			if contact.get_full_jid() == sender_jid:
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
			if 'sid' in self.files_props:
				del(self.files_props['sid'])

	def disconnect_transfer(self, file_props):
		if file_props is None:
			return
		if 'hash' in file_props:
			gajim.socks5queue.remove_sender(file_props['hash'])

		if 'streamhosts' in file_props:
			for host in file_props['streamhosts']:
				if 'idx' in host and host['idx'] > 0:
					gajim.socks5queue.remove_receiver(host['idx'])
					gajim.socks5queue.remove_sender(host['idx'])

	def send_socks5_info(self, file_props, fast = True, receiver = None,
		sender = None):
		''' send iq for the present streamhosts and proxies '''
		if not self.connection or self.connected < 2:
			return
		if not isinstance(self.peerhost, tuple):
			return
		port = gajim.config.get('file_transfers_port')
		ft_add_hosts_to_send = gajim.config.get('ft_add_hosts_to_send')
		cfg_proxies = gajim.config.get_per('accounts', self.name,
			'file_transfer_proxies')
		if receiver is None:
			receiver = file_props['receiver']
		if sender is None:
			sender = file_props['sender']
		proxyhosts = []
		if fast and cfg_proxies:
			proxies = [e.strip() for e in cfg_proxies.split(',')]
			default = gajim.proxy65_manager.get_default_for_name(self.name)
			if default:
				# add/move default proxy at top of the others
				if proxies.__contains__(default):
					proxies.remove(default)
				proxies.insert(0, default)

			for proxy in proxies:
				(host, _port, jid) = gajim.proxy65_manager.get_proxy(proxy, self.name)
				if host is None:
					continue
				host_dict={
					'state': 0,
					'target': unicode(receiver),
					'id': file_props['sid'],
					'sid': file_props['sid'],
					'initiator': proxy,
					'host': host,
					'port': unicode(_port),
					'jid': jid
				}
				proxyhosts.append(host_dict)
		sha_str = helpers.get_auth_sha(file_props['sid'], sender,
			receiver)
		file_props['sha_str'] = sha_str
		ft_add_hosts = []
		if ft_add_hosts_to_send:
			ft_add_hosts_to_send = [e.strip() for e in ft_add_hosts_to_send.split(',')]
			for ft_host in ft_add_hosts_to_send:
				ft_add_hosts.append(ft_host)
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
		query.setAttr('mode', 'plain')
		query.setAttr('sid', file_props['sid'])
		for ft_host in ft_add_hosts:
			# The streamhost, if set
			ostreamhost = common.xmpp.Node(tag = 'streamhost')
			query.addChild(node = ostreamhost)
			ostreamhost.setAttr('port', unicode(port))
			ostreamhost.setAttr('host', ft_host)
			ostreamhost.setAttr('jid', sender)
		try:
			# The ip we're connected to server with
			my_ips = [self.peerhost[0]]
			# all IPs from local DNS
			for addr in socket.getaddrinfo(socket.gethostname(), None):
				if not addr[4][0] in my_ips:
					my_ips.append(addr[4][0])
			for ip in my_ips:
				streamhost = common.xmpp.Node(tag = 'streamhost')
				query.addChild(node = streamhost)
				streamhost.setAttr('port', unicode(port))
				streamhost.setAttr('host', ip)
				streamhost.setAttr('jid', sender)
		except socket.gaierror:
			self.dispatch('ERROR', (_('Wrong host'),
				_('Invalid local address? :-O')))

		if fast and proxyhosts != [] and gajim.config.get_per('accounts',
		self.name, 'use_ft_proxies'):
			file_props['proxy_receiver'] = unicode(receiver)
			file_props['proxy_sender'] = unicode(sender)
			file_props['proxyhosts'] = proxyhosts
			for proxyhost in proxyhosts:
				streamhost = common.xmpp.Node(tag = 'streamhost')
				query.addChild(node=streamhost)
				streamhost.setAttr('port', proxyhost['port'])
				streamhost.setAttr('host', proxyhost['host'])
				streamhost.setAttr('jid', proxyhost['jid'])

				# don't add the proxy child tag for streamhosts, which are proxies
				# proxy = streamhost.setTag('proxy')
				# proxy.setNamespace(common.xmpp.NS_STREAM)
		self.connection.send(iq)

	def send_file_rejection(self, file_props, code='403', typ=None):
		''' informs sender that we refuse to download the file
		typ is used when code = '400', in this case typ can be 'strean' for
		invalid stream or 'profile' for invalid profile'''
		# user response to ConfirmationDialog may come after we've disconneted
		if not self.connection or self.connected < 2:
			return
		iq = common.xmpp.Protocol(name = 'iq',
			to = unicode(file_props['sender']), typ = 'error')
		iq.setAttr('id', file_props['request-id'])
		if code == '400' and typ in ('stream', 'profile'):
			name = 'bad-request'
			text = ''
		else:
			name = 'forbidden'
			text = 'Offer Declined'
		err = common.xmpp.ErrorNode(code=code, typ='cancel', name=name, text=text)
		if code == '400' and typ in ('stream', 'profile'):
			if typ == 'stream':
				err.setTag('no-valid-streams', namespace=common.xmpp.NS_SI)
			else:
				err.setTag('bad-profile', namespace=common.xmpp.NS_SI)
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
		if 'offset' in file_props and file_props['offset']:
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
		resource = self.server_resource
		frm = our_jid + '/' + resource
		file_props['sender'] = frm
		fjid = file_props['receiver'].jid + '/' + file_props['receiver'].resource
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

	def _result_socks5_sid(self, sid, hash_id):
		''' store the result of sha message from auth. '''
		if sid not in self.files_props:
			return
		file_props = self.files_props[sid]
		file_props['hash'] = hash_id
		return

	def _connect_error(self, to, _id, sid, code = 404):
		''' cb, when there is an error establishing BS connection, or
		when connection is rejected'''
		if not self.connection or self.connected < 2:
			return
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
		if not self.connection or self.connected < 2:
			return
		file_props = self.files_props[proxy['sid']]
		iq = common.xmpp.Protocol(name = 'iq', to = proxy['initiator'],
		typ = 'set')
		auth_id = "au_" + proxy['sid']
		iq.setID(auth_id)
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		query.setAttr('sid', proxy['sid'])
		activate = query.setTag('activate')
		activate.setData(file_props['proxy_receiver'])
		iq.setID(auth_id)
		self.connection.send(iq)

	# register xmpppy handlers for bytestream and FT stanzas
	def _bytestreamErrorCB(self, con, iq_obj):
		log.debug('_bytestreamErrorCB')
		id_ = unicode(iq_obj.getAttr('id'))
		frm = helpers.get_full_jid_from_iq(iq_obj)
		query = iq_obj.getTag('query')
		gajim.proxy65_manager.error_cb(frm, query)
		jid = helpers.get_jid_from_iq(iq_obj)
		id_ = id_[3:]
		if id_ not in self.files_props:
			return
		file_props = self.files_props[id_]
		file_props['error'] = -4
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props, ''))
		raise common.xmpp.NodeProcessed

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
					'initiator': helpers.get_full_jid_from_iq(iq_obj)
				}
				for attr in item.getAttrs():
					host_dict[attr] = item.getAttr(attr)
				streamhosts.append(host_dict)
		if file_props is None:
			if sid in self.files_props:
				file_props = self.files_props[sid]
				file_props['fast'] = streamhosts
				if file_props['type'] == 's': # FIXME: remove fast xmlns
					# only psi do this

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
		# if we want to respect xep-0065 we have to check for proxy
		# activation result in any result iq
		real_id = unicode(iq_obj.getAttr('id'))
		if real_id == self.awaiting_xmpp_ping_id:
			self.awaiting_xmpp_ping_id = None
			return
		if not real_id.startswith('au_'):
			return
		frm = helpers.get_full_jid_from_iq(iq_obj)
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
		frm = helpers.get_full_jid_from_iq(iq_obj)
		real_id = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		gajim.proxy65_manager.resolve_result(frm, query)

		try:
			streamhost = query.getTag('streamhost-used')
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
		jid = helpers.parse_jid(streamhost.getAttr('jid'))
		if 'streamhost-used' in file_props and \
			file_props['streamhost-used'] is True:
			raise common.xmpp.NodeProcessed

		if real_id.startswith('au_'):
			if 'stopped' in file and file_props['stopped']:
				self.remove_transfer(file_props)
			else:
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
			receiver = socks5.Socks5Receiver(gajim.idlequeue, proxy,
				file_props['sid'], file_props)
			gajim.socks5queue.add_receiver(self.name, receiver)
			proxy['idx'] = receiver.queue_idx
			gajim.socks5queue.on_success = self._proxy_auth_ok
			raise common.xmpp.NodeProcessed

		else:
			if 'stopped' in file_props and file_props['stopped']:
				self.remove_transfer(file_props)
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
		file_props['receiver'] = helpers.get_full_jid_from_iq(iq_obj)
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
		jid = helpers.get_jid_from_iq(iq_obj)
		file_props = {'type': 'r'}
		file_props['sender'] = helpers.get_full_jid_from_iq(iq_obj)
		file_props['request-id'] = unicode(iq_obj.getAttr('id'))
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		mime_type = si.getAttr('mime-type')
		if profile != common.xmpp.NS_FILE:
			self.send_file_rejection(file_props, code='400', typ='profile')
			raise common.xmpp.NodeProcessed
		feature_tag = si.getTag('feature', namespace=common.xmpp.NS_FEATURE)
		if not feature_tag:
			return
		form_tag = feature_tag.getTag('x', namespace=common.xmpp.NS_DATA)
		if not form_tag:
			return
		form = common.dataforms.ExtendForm(node=form_tag)
		for f in form.iter_fields():
			if f.var == 'stream-method' and f.type == 'list-single':
				values = [o[1] for o in f.options]
				if common.xmpp.NS_BYTESTREAM in values:
					break
		else:
			self.send_file_rejection(file_props, code='400', typ='stream')
			raise common.xmpp.NodeProcessed
		file_tag = si.getTag('file')
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
		resource = self.server_resource
		file_props['receiver'] = our_jid + '/' + resource
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
		jid = helpers.get_jid_from_iq(iq_obj)
		file_props['error'] = -3
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props, ''))
		raise common.xmpp.NodeProcessed

class ConnectionDisco:
	''' hold xmpppy handlers and public methods for discover services'''
	def discoverItems(self, jid, node = None, id_prefix = None):
		'''According to XEP-0030: jid is mandatory,
		name, node, action is optional.'''
		self._discover(common.xmpp.NS_DISCO_ITEMS, jid, node, id_prefix)

	def discoverInfo(self, jid, node = None, id_prefix = None):
		'''According to XEP-0030:
			For identity: category, type is mandatory, name is optional.
			For feature: var is mandatory'''
		self._discover(common.xmpp.NS_DISCO_INFO, jid, node, id_prefix)

	def request_register_agent_info(self, agent):
		if not self.connection or self.connected < 2:
			return None
		iq = common.xmpp.Iq('get', common.xmpp.NS_REGISTER, to=agent)
		id_ = self.connection.getAnID()
		iq.setID(id_)
		# Wait the answer during 30 secondes
		self.awaiting_timeouts[gajim.idlequeue.current_time() + 30] = (id_,
			_('Registration information for transport %s has not arrived in time')\
			% agent)
		self.connection.SendAndCallForResponse(iq, self._ReceivedRegInfo,
			{'agent': agent})

	def _agent_registered_cb(self, con, resp, agent):
		if resp.getType() == 'result':
			self.dispatch('INFORMATION', (_('Registration succeeded'),
				_('Registration with agent %s succeeded') % agent))
		if resp.getType() == 'error':
			self.dispatch('ERROR', (_('Registration failed'), _('Registration with'
				' agent %(agent)s failed with error %(error)s: %(error_msg)s') % {
				'agent': agent, 'error': resp.getError(),
				'error_msg': resp.getErrorMsg()}))

	def register_agent(self, agent, info, is_form = False):
		if not self.connection or self.connected < 2:
			return
		if is_form:
			iq = common.xmpp.Iq('set', common.xmpp.NS_REGISTER, to = agent)
			query = iq.getTag('query')
			info.setAttr('type', 'submit')
			query.addChild(node = info)
			self.connection.SendAndCallForResponse(iq, self._agent_registered_cb,
				{'agent': agent})
		else:
			# fixed: blocking
			common.xmpp.features_nb.register(self.connection, agent, info, None)

	def _discover(self, ns, jid, node = None, id_prefix = None):
		if not self.connection or self.connected < 2:
			return
		iq = common.xmpp.Iq(typ = 'get', to = jid, queryNS = ns)
		if id_prefix:
			id_ = self.connection.getAnID()
			iq.setID('%s%s' % (id_prefix, id_))
		if node:
			iq.setQuerynode(node)
		self.connection.send(iq)

	def _ReceivedRegInfo(self, con, resp, agent):
		common.xmpp.features_nb._ReceivedRegInfo(con, resp, agent)
		self._IqCB(con, resp)

	def _discoGetCB(self, con, iq_obj):
		''' get disco info '''
		if not self.connection or self.connected < 2:
			return
		frm = helpers.get_full_jid_from_iq(iq_obj)
		to = unicode(iq_obj.getAttr('to'))
		id_ = unicode(iq_obj.getAttr('id'))
		iq = common.xmpp.Iq(to = frm, typ = 'result', queryNS =\
			common.xmpp.NS_DISCO, frm = to)
		iq.setAttr('id', id_)
		query = iq.setTag('query')
		query.setAttr('node','http://gajim.org#' + gajim.version.split('-',
			1)[0])
		for f in (common.xmpp.NS_BYTESTREAM, common.xmpp.NS_SI,
		common.xmpp.NS_FILE, common.xmpp.NS_COMMANDS):
			feature = common.xmpp.Node('feature')
			feature.setAttr('var', f)
			query.addChild(node=feature)

		self.connection.send(iq)
		raise common.xmpp.NodeProcessed

	def _DiscoverItemsErrorCB(self, con, iq_obj):
		log.debug('DiscoverItemsErrorCB')
		jid = helpers.get_full_jid_from_iq(iq_obj)
		self.dispatch('AGENT_ERROR_ITEMS', (jid))

	def _DiscoverItemsCB(self, con, iq_obj):
		log.debug('DiscoverItemsCB')
		q = iq_obj.getTag('query')
		node = q.getAttr('node')
		if not node:
			node = ''
		qp = iq_obj.getQueryPayload()
		items = []
		if not qp:
			qp = []
		for i in qp:
			# CDATA payload is not processed, only nodes
			if not isinstance(i, common.xmpp.simplexml.Node):
				continue
			attr = {}
			for key in i.getAttrs():
				attr[key] = i.getAttrs()[key]
			if 'jid' not in attr:
				continue
			try:
				attr['jid'] = helpers.parse_jid(attr['jid'])
			except common.helpers.InvalidFormat:
				# jid is not conform
				continue
			items.append(attr)
		jid = helpers.get_full_jid_from_iq(iq_obj)
		hostname = gajim.config.get_per('accounts', self.name,
													'hostname')
		id_ = iq_obj.getID()
		if jid == hostname and id_[:6] == 'Gajim_':
			for item in items:
				self.discoverInfo(item['jid'], id_prefix='Gajim_')
		else:
			self.dispatch('AGENT_INFO_ITEMS', (jid, node, items))

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

	def _DiscoverInfoGetCB(self, con, iq_obj):
		log.debug('DiscoverInfoGetCB')
		if not self.connection or self.connected < 2:
			return
		q = iq_obj.getTag('query')
		node = q.getAttr('node')

		if self.commandInfoQuery(con, iq_obj):
			raise common.xmpp.NodeProcessed

		id_ = unicode(iq_obj.getAttr('id'))
		if id_[:6] == 'Gajim_':
			# We get this request from echo.server
			raise common.xmpp.NodeProcessed

		iq = iq_obj.buildReply('result')
		q = iq.getTag('query')
		if node:
			q.setAttr('node', node)
		q.addChild('identity', attrs = gajim.gajim_identity)
		client_version = 'http://gajim.org#' + gajim.caps_hash[self.name]

		if node in (None, client_version):
			for f in gajim.gajim_common_features:
				q.addChild('feature', attrs = {'var': f})
			for f in gajim.gajim_optional_features[self.name]:
				q.addChild('feature', attrs = {'var': f})

		if q.getChildren():
			self.connection.send(iq)
			raise common.xmpp.NodeProcessed

	def _DiscoverInfoErrorCB(self, con, iq_obj):
		log.debug('DiscoverInfoErrorCB')
		jid = helpers.get_full_jid_from_iq(iq_obj)
		self.dispatch('AGENT_ERROR_INFO', (jid))

	def _DiscoverInfoCB(self, con, iq_obj):
		log.debug('DiscoverInfoCB')
		if not self.connection or self.connected < 2:
			return
		# According to XEP-0030:
		# For identity: category, type is mandatory, name is optional.
		# For feature: var is mandatory
		identities, features, data = [], [], []
		q = iq_obj.getTag('query')
		node = q.getAttr('node')
		if not node:
			node = ''
		qc = iq_obj.getQueryChildren()
		if not qc:
			qc = []
		is_muc = False
		transport_type = ''
		for i in qc:
			if i.getName() == 'identity':
				attr = {}
				for key in i.getAttrs().keys():
					attr[key] = i.getAttr(key)
				if 'category' in attr and \
					attr['category'] in ('gateway', 'headline') and \
					'type' in attr:
					transport_type = attr['type']
				if 'category' in attr and \
					attr['category'] == 'conference' and \
					'type' in attr and attr['type'] == 'text':
					is_muc = True
				identities.append(attr)
			elif i.getName() == 'feature':
				features.append(i.getAttr('var'))
			elif i.getName() == 'x' and i.getNamespace() == common.xmpp.NS_DATA:
				data.append(common.xmpp.DataForm(node=i))
		jid = helpers.get_full_jid_from_iq(iq_obj)
		if transport_type and jid not in gajim.transport_type:
			gajim.transport_type[jid] = transport_type
			gajim.logger.save_transport_type(jid, transport_type)
		id_ = iq_obj.getID()
		if id_ is None:
			log.warn('Invalid IQ received without an ID. Ignoring it: %s' % iq_obj)
			return
		if not identities: # ejabberd doesn't send identities when we browse online users
		#FIXME: see http://www.jabber.ru/bugzilla/show_bug.cgi?id=225
			identities = [{'category': 'server', 'type': 'im', 'name': node}]
		if id_[:6] == 'Gajim_':
			if jid == gajim.config.get_per('accounts', self.name, 'hostname'):
				if features.__contains__(common.xmpp.NS_GMAILNOTIFY):
					gajim.gmail_domains.append(jid)
					self.request_gmail_notifications()
				for identity in identities:
					if identity['category'] == 'pubsub' and identity.get('type') == \
					'pep':
						self.pep_supported = True
						if dbus_support.supported:
							listener = MusicTrackListener.get()
							track = listener.get_playing_track()
							if gajim.config.get_per('accounts', self.name,
							'publish_tune'):
								gajim.interface.roster.music_track_changed(listener,
										track, self.name)
						break
			if features.__contains__(common.xmpp.NS_PUBSUB):
				self.pubsub_supported = True
			if features.__contains__(common.xmpp.NS_BYTESTREAM):
				our_jid = helpers.parse_jid(gajim.get_jid_from_account(self.name) +\
					'/' + self.server_resource)
				gajim.proxy65_manager.resolve(jid, self.connection, our_jid,
					self.name)
			if features.__contains__(common.xmpp.NS_MUC) and is_muc:
				type_ = transport_type or 'jabber'
				self.muc_jid[type_] = jid
			if transport_type:
				if transport_type in self.available_transports:
					self.available_transports[transport_type].append(jid)
				else:
					self.available_transports[transport_type] = [jid]

		self.dispatch('AGENT_INFO_INFO', (jid, node, identities,
			features, data))
		self._capsDiscoCB(jid, node, identities, features, data)

class ConnectionVcard:
	def __init__(self):
		self.vcard_sha = None
		self.vcard_shas = {} # sha of contacts
		self.room_jids = [] # list of gc jids so that vcard are saved in a folder

	def add_sha(self, p, send_caps = True):
		c = p.setTag('x', namespace = common.xmpp.NS_VCARD_UPDATE)
		if self.vcard_sha is not None:
			c.setTagData('photo', self.vcard_sha)
		if send_caps:
			return self.add_caps(p)
		return p

	def add_caps(self, p):
		''' advertise our capabilities in presence stanza (xep-0115)'''
		c = p.setTag('c', namespace = common.xmpp.NS_CAPS)
		c.setAttr('hash', 'sha-1')
		c.setAttr('node', 'http://gajim.org')
		c.setAttr('ver', gajim.caps_hash[self.name])
		return p

	def node_to_dict(self, node):
		dict_ = {}
		for info in node.getChildren():
			name = info.getName()
			if name in ('ADR', 'TEL', 'EMAIL'): # we can have several
				dict_.setdefault(name, [])
				entry = {}
				for c in info.getChildren():
					entry[c.getName()] = c.getData()
				dict_[name].append(entry)
			elif info.getChildren() == []:
				dict_[name] = info.getData()
			else:
				dict_[name] = {}
				for c in info.getChildren():
					dict_[name][c.getName()] = c.getData()
		return dict_

	def save_vcard_to_hd(self, full_jid, card):
		jid, nick = gajim.get_room_and_nick_from_fjid(full_jid)
		puny_jid = helpers.sanitize_filename(jid)
		path = os.path.join(gajim.VCARD_PATH, puny_jid)
		if jid in self.room_jids or os.path.isdir(path):
			if not nick:
				return
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
		try:
			fil = open(path_to_file, 'w')
			fil.write(str(card))
			fil.close()
		except IOError, e:
			self.dispatch('ERROR', (_('Disk Write Error'), str(e)))

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
		try:
			card = common.xmpp.Node(node = c)
		except Exception:
			# We are unable to parse it. Remove it
			os.remove(path_to_file)
			return None
		vcard = self.node_to_dict(card)
		if 'PHOTO' in vcard:
			if not isinstance(vcard['PHOTO'], dict):
				del vcard['PHOTO']
			elif 'SHA' in vcard['PHOTO']:
				cached_sha = vcard['PHOTO']['SHA']
				if jid in self.vcard_shas and self.vcard_shas[jid] != \
					cached_sha:
					# user change his vcard so don't use the cached one
					return {}
		vcard['jid'] = jid
		vcard['resource'] = gajim.get_resource_from_jid(fjid)
		return vcard

	def request_vcard(self, jid = None, groupchat_jid = None):
		'''request the VCARD. If groupchat_jid is not nul, it means we request a vcard
		to a fake jid, like in private messages in groupchat. jid can be the
		real jid of the contact, but we want to consider it comes from a fake jid'''
		if not self.connection or self.connected < 2:
			return
		iq = common.xmpp.Iq(typ = 'get')
		if jid:
			iq.setTo(jid)
		iq.setTag(common.xmpp.NS_VCARD + ' vCard')

		id_ = self.connection.getAnID()
		iq.setID(id_)
		j = jid
		if not j:
			j = gajim.get_jid_from_account(self.name)
		self.awaiting_answers[id_] = (VCARD_ARRIVED, j, groupchat_jid)
		if groupchat_jid:
			room_jid = gajim.get_room_and_nick_from_fjid(groupchat_jid)[0]
			if not room_jid in self.room_jids:
				self.room_jids.append(room_jid)
			self.groupchat_jids[id_] = groupchat_jid
		self.connection.send(iq)

	def send_vcard(self, vcard):
		if not self.connection or self.connected < 2:
			return
		iq = common.xmpp.Iq(typ = 'set')
		iq2 = iq.setTag(common.xmpp.NS_VCARD + ' vCard')
		for i in vcard:
			if i == 'jid':
				continue
			if isinstance(vcard[i], dict):
				iq3 = iq2.addChild(i)
				for j in vcard[i]:
					iq3.addChild(j).setData(vcard[i][j])
			elif isinstance(vcard[i], list):
				for j in vcard[i]:
					iq3 = iq2.addChild(i)
					for k in j:
						iq3.addChild(k).setData(j[k])
			else:
				iq2.addChild(i).setData(vcard[i])

		id_ = self.connection.getAnID()
		iq.setID(id_)
		self.connection.send(iq)

		our_jid = gajim.get_jid_from_account(self.name)
		# Add the sha of the avatar
		if 'PHOTO' in vcard and isinstance(vcard['PHOTO'], dict) and \
		'BINVAL' in vcard['PHOTO']:
			photo = vcard['PHOTO']['BINVAL']
			photo_decoded = base64.decodestring(photo)
			gajim.interface.save_avatar_files(our_jid, photo_decoded)
			avatar_sha = hashlib.sha1(photo_decoded).hexdigest()
			iq2.getTag('PHOTO').setTagData('SHA', avatar_sha)
		else:
			gajim.interface.remove_avatar_files(our_jid)

		self.awaiting_answers[id_] = (VCARD_PUBLISHED, iq2)

	def _IqCB(self, con, iq_obj):
		id_ = iq_obj.getID()

		# Check if we were waiting a timeout for this id
		found_tim = None
		for tim in self.awaiting_timeouts:
			if id_ == self.awaiting_timeouts[tim][0]:
				found_tim = tim
				break
		if found_tim:
			del self.awaiting_timeouts[found_tim]

		if id_ not in self.awaiting_answers:
			return
		if self.awaiting_answers[id_][0] == VCARD_PUBLISHED:
			if iq_obj.getType() == 'result':
				vcard_iq = self.awaiting_answers[id_][1]
				# Save vcard to HD
				if vcard_iq.getTag('PHOTO') and vcard_iq.getTag('PHOTO').getTag('SHA'):
					new_sha = vcard_iq.getTag('PHOTO').getTagData('SHA')
				else:
					new_sha = ''

				# Save it to file
				our_jid = gajim.get_jid_from_account(self.name)
				self.save_vcard_to_hd(our_jid, vcard_iq)

				# Send new presence if sha changed and we are not invisible
				if self.vcard_sha != new_sha and gajim.SHOW_LIST[self.connected] !=\
				'invisible':
					if not self.connection or self.connected < 2:
						return
					self.vcard_sha = new_sha
					sshow = helpers.get_xmpp_show(gajim.SHOW_LIST[self.connected])
					p = common.xmpp.Presence(typ = None, priority = self.priority,
						show = sshow, status = self.status)
					p = self.add_sha(p)
					self.connection.send(p)
				self.dispatch('VCARD_PUBLISHED', ())
			elif iq_obj.getType() == 'error':
				self.dispatch('VCARD_NOT_PUBLISHED', ())
		elif self.awaiting_answers[id_][0] == VCARD_ARRIVED:
			# If vcard is empty, we send to the interface an empty vcard so that
			# it knows it arrived
			jid = self.awaiting_answers[id_][1]
			groupchat_jid = self.awaiting_answers[id_][2]
			frm = jid
			if groupchat_jid:
				# We do as if it comes from the fake_jid
				frm = groupchat_jid
			our_jid = gajim.get_jid_from_account(self.name)
			if iq_obj.getType() == 'error' and jid == our_jid:
				# our server doesn't support vcard
				log.debug('xxx error xxx')
				self.vcard_supported = False
			if not iq_obj.getTag('vCard') or iq_obj.getType() == 'error':
				if frm and frm != our_jid:
					# Write an empty file
					self.save_vcard_to_hd(frm, '')
					jid, resource = gajim.get_room_and_nick_from_fjid(frm)
					self.dispatch('VCARD', {'jid': jid, 'resource': resource})
				elif frm == our_jid:
					self.dispatch('MYVCARD', {'jid': frm})
		elif self.awaiting_answers[id_][0] == AGENT_REMOVED:
			jid = self.awaiting_answers[id_][1]
			self.dispatch('AGENT_REMOVED', jid)
		elif self.awaiting_answers[id_][0] == METACONTACTS_ARRIVED:
			if not self.connection:
				return
			if iq_obj.getType() == 'result':
				# Metacontact tags
				# http://www.xmpp.org/extensions/xep-0209.html
				meta_list = {}
				query = iq_obj.getTag('query')
				storage = query.getTag('storage')
				metas = storage.getTags('meta')
				for meta in metas:
					try:
						jid = helpers.parse_jid(meta.getAttr('jid'))
					except common.helpers.InvalidFormat:
						continue
					tag = meta.getAttr('tag')
					data = {'jid': jid}
					order = meta.getAttr('order')
					try:
						order = int(order)
					except Exception:
						order = 0
					if order is not None:
						data['order'] = order
					if tag in meta_list:
						meta_list[tag].append(data)
					else:
						meta_list[tag] = [data]
				self.dispatch('METACONTACTS', meta_list)
			else:
				if iq_obj.getErrorCode() not in ('403', '406', '404'):
					self.private_storage_supported = False
			# We can now continue connection by requesting the roster
			version = gajim.config.get_per('accounts', self.name,
				'roster_version')
			iq_id = self.connection.initRoster(version=version)
			self.awaiting_answers[iq_id] = (ROSTER_ARRIVED, )
		elif self.awaiting_answers[id_][0] == ROSTER_ARRIVED:
			if iq_obj.getType() == 'result':
				if not iq_obj.getTag('query'):
					account_jid = gajim.get_jid_from_account(self.name)
					roster_data = gajim.logger.get_roster(account_jid)
					roster = self.connection.getRoster(force=True)
					roster.setRaw(roster_data)
				self._getRoster()
		elif self.awaiting_answers[id_][0] == PRIVACY_ARRIVED:
			if iq_obj.getType() != 'error':
				self.privacy_rules_supported = True
				self.get_privacy_list('block')
			elif self.continue_connect_info:
				if self.continue_connect_info[0] == 'invisible':
					# Trying to login as invisible but privacy list not supported
					self.disconnect(on_purpose=True)
					self.dispatch('STATUS', 'offline')
					self.dispatch('ERROR', (_('Invisibility not supported'),
						_('Account %s doesn\'t support invisibility.') % self.name))
					return
			# Ask metacontacts before roster
			self.get_metacontacts()
		elif self.awaiting_answers[id_][0] == PEP_CONFIG:
			conf = iq_obj.getTag('pubsub').getTag('configure')
			node = conf.getAttr('node')
			form_tag = conf.getTag('x', namespace=common.xmpp.NS_DATA)
			if form_tag:
				form = common.dataforms.ExtendForm(node=form_tag)
				self.dispatch('PEP_CONFIG', (node, form))

		del self.awaiting_answers[id_]

	def _vCardCB(self, con, vc):
		'''Called when we receive a vCard
		Parse the vCard and send it to plugins'''
		if not vc.getTag('vCard'):
			return
		if not vc.getTag('vCard').getNamespace() == common.xmpp.NS_VCARD:
			return
		id_ = vc.getID()
		frm_iq = vc.getFrom()
		our_jid = gajim.get_jid_from_account(self.name)
		resource = ''
		if id_ in self.groupchat_jids:
			who = self.groupchat_jids[id_]
			frm, resource = gajim.get_room_and_nick_from_fjid(who)
			del self.groupchat_jids[id_]
		elif frm_iq:
			who = helpers.get_full_jid_from_iq(vc)
			frm, resource = gajim.get_room_and_nick_from_fjid(who)
		else:
			who = frm = our_jid
		card = vc.getChildren()[0]
		vcard = self.node_to_dict(card)
		photo_decoded = None
		if 'PHOTO' in vcard and isinstance(vcard['PHOTO'], dict) and \
		'BINVAL' in vcard['PHOTO']:
			photo = vcard['PHOTO']['BINVAL']
			try:
				photo_decoded = base64.decodestring(photo)
				avatar_sha = hashlib.sha1(photo_decoded).hexdigest()
			except Exception:
				avatar_sha = ''
		else:
			avatar_sha = ''

		if avatar_sha:
			card.getTag('PHOTO').setTagData('SHA', avatar_sha)

		# Save it to file
		self.save_vcard_to_hd(who, card)
		# Save the decoded avatar to a separate file too, and generate files for dbus notifications
		puny_jid = helpers.sanitize_filename(frm)
		puny_nick = None
		begin_path = os.path.join(gajim.AVATAR_PATH, puny_jid)
		frm_jid = frm
		if frm in self.room_jids:
			puny_nick = helpers.sanitize_filename(resource)
			# create folder if needed
			if not os.path.isdir(begin_path):
				os.mkdir(begin_path, 0700)
			begin_path = os.path.join(begin_path, puny_nick)
			frm_jid += '/' + resource
		if photo_decoded:
			avatar_file = begin_path + '_notif_size_colored.png'
			if frm_jid == our_jid and avatar_sha != self.vcard_sha:
				gajim.interface.save_avatar_files(frm, photo_decoded, puny_nick)
			elif frm_jid != our_jid and (not os.path.exists(avatar_file) or \
			frm_jid not in self.vcard_shas or \
			avatar_sha != self.vcard_shas[frm_jid]):
				gajim.interface.save_avatar_files(frm, photo_decoded, puny_nick)
				if avatar_sha:
					self.vcard_shas[frm_jid] = avatar_sha
			elif frm in self.vcard_shas:
				del self.vcard_shas[frm]
		else:
			for ext in ('.jpeg', '.png', '_notif_size_bw.png',
				'_notif_size_colored.png'):
				path = begin_path + ext
				if os.path.isfile(path):
					os.remove(path)

		vcard['jid'] = frm
		vcard['resource'] = resource
		if frm_jid == our_jid:
			self.dispatch('MYVCARD', vcard)
			# we re-send our presence with sha if has changed and if we are
			# not invisible
			if self.vcard_sha == avatar_sha:
				return
			self.vcard_sha = avatar_sha
			if gajim.SHOW_LIST[self.connected] == 'invisible':
				return
			if not self.connection:
				return
			sshow = helpers.get_xmpp_show(gajim.SHOW_LIST[self.connected])
			p = common.xmpp.Presence(typ = None, priority = self.priority,
				show = sshow, status = self.status)
			p = self.add_sha(p)
			self.connection.send(p)
		else:
			#('VCARD', {entry1: data, entry2: {entry21: data, ...}, ...})
			self.dispatch('VCARD', vcard)

# basic connection handlers used here and in zeroconf
class ConnectionHandlersBase:
	def __init__(self):
		# List of IDs we are waiting answers for {id: (type_of_request, data), }
		self.awaiting_answers = {}
		# List of IDs that will produce a timeout is answer doesn't arrive
		# {time_of_the_timeout: (id, message to send to gui), }
		self.awaiting_timeouts = {}
		# keep the jids we auto added (transports contacts) to not send the
		# SUBSCRIBED event to gui
		self.automatically_added = []

		# keep track of sessions this connection has with other JIDs
		self.sessions = {}

	def get_sessions(self, jid):
		'''get all sessions for the given full jid'''

		if not gajim.interface.is_pm_contact(jid, self.name):
			jid = gajim.get_jid_without_resource(jid)

		try:
			return self.sessions[jid].values()
		except KeyError:
			return []

	def get_or_create_session(self, fjid, thread_id):
		'''returns an existing session between this connection and 'jid', returns a
		new one if none exist.'''

		pm = True
		jid = fjid

		if not gajim.interface.is_pm_contact(fjid, self.name):
			pm = False
			jid = gajim.get_jid_without_resource(fjid)

		session = self.find_session(jid, thread_id)

		if session:
			return session

		if pm:
			return self.make_new_session(fjid, thread_id, type_='pm')
		else:
			return self.make_new_session(fjid, thread_id)

	def find_session(self, jid, thread_id):
		try:
			if not thread_id:
				return self.find_null_session(jid)
			else:
				return self.sessions[jid][thread_id]
		except KeyError:
			return None

	def terminate_sessions(self, send_termination=False):
		'''send termination messages and delete all active sessions'''
		for jid in self.sessions:
			for thread_id in self.sessions[jid]:
				self.sessions[jid][thread_id].terminate(send_termination)

		self.sessions = {}

	def delete_session(self, jid, thread_id):
		if not jid in self.sessions:
			jid = gajim.get_jid_without_resource(jid)
		if not jid in self.sessions:
			return

		del self.sessions[jid][thread_id]

		if not self.sessions[jid]:
			del self.sessions[jid]

	def find_null_session(self, jid):
		'''finds all of the sessions between us and a remote jid in which we
haven't received a thread_id yet and returns the session that we last
sent a message to.'''

		sessions = self.sessions[jid].values()

		# sessions that we haven't received a thread ID in
		idless = [s for s in sessions if not s.received_thread_id]

		# filter out everything except the default session type
		chat_sessions = [s for s in idless if isinstance(s,
			gajim.default_session_type)]

		if chat_sessions:
			# return the session that we last sent a message in
			return sorted(chat_sessions,
				key=operator.attrgetter("last_send"))[-1]
		else:
			return None

	def find_controlless_session(self, jid):
		'''find an active session that doesn't have a control attached'''

		try:
			sessions = self.sessions[jid].values()

			# filter out everything except the default session type
			chat_sessions = [s for s in sessions if isinstance(s,
				gajim.default_session_type)]

			orphaned = [s for s in chat_sessions if not s.control]

			return orphaned[0]
		except (KeyError, IndexError):
			return None

	def make_new_session(self, jid, thread_id=None, type_='chat', cls=None):
		'''create and register a new session. thread_id=None to generate one.
		type_ should be 'chat' or 'pm'.'''
		if not cls:
			cls = gajim.default_session_type

		sess = cls(self, common.xmpp.JID(jid), thread_id, type_)

		# determine if this session is a pm session
		# if not, discard the resource so that all sessions are stored bare
		if not type_ == 'pm':
			jid = gajim.get_jid_without_resource(jid)

		if not jid in self.sessions:
			self.sessions[jid] = {}

		self.sessions[jid][sess.thread_id] = sess

		return sess

class ConnectionHandlers(ConnectionVcard, ConnectionBytestream, ConnectionDisco, ConnectionCommands, ConnectionPubSub, ConnectionCaps, ConnectionHandlersBase):
	def __init__(self):
		ConnectionVcard.__init__(self)
		ConnectionBytestream.__init__(self)
		ConnectionCommands.__init__(self)
		ConnectionPubSub.__init__(self)
		ConnectionHandlersBase.__init__(self)
		self.gmail_url = None

		# keep the latest subscribed event for each jid to prevent loop when we
		# acknowledge presences
		self.subscribed_events = {}
		# IDs of jabber:iq:last requests
		self.last_ids = []
		# IDs of jabber:iq:version requests
		self.version_ids = []
		# IDs of urn:xmpp:time requests
		self.entity_time_ids = []
		# ID of urn:xmpp:ping requests
		self.awaiting_xmpp_ping_id = None
		self.continue_connect_info = None

		try:
			idle.init()
		except Exception:
			global HAS_IDLE
			HAS_IDLE = False

		self.gmail_last_tid = None
		self.gmail_last_time = None

	def build_http_auth_answer(self, iq_obj, answer):
		if not self.connection or self.connected < 2:
			return
		if answer == 'yes':
			self.connection.send(iq_obj.buildReply('result'))
		elif answer == 'no':
			err = common.xmpp.Error(iq_obj,
				common.xmpp.protocol.ERR_NOT_AUTHORIZED)
			self.connection.send(err)

	def _HttpAuthCB(self, con, iq_obj):
		log.debug('HttpAuthCB')
		opt = gajim.config.get_per('accounts', self.name, 'http_auth')
		if opt in ('yes', 'no'):
			self.build_http_auth_answer(iq_obj, opt)
		else:
			id_ = iq_obj.getTagAttr('confirm', 'id')
			method = iq_obj.getTagAttr('confirm', 'method')
			url = iq_obj.getTagAttr('confirm', 'url')
			msg = iq_obj.getTagData('body') # In case it's a message with a body
			self.dispatch('HTTP_AUTH', (method, url, id_, iq_obj, msg))
		raise common.xmpp.NodeProcessed

	def _ErrorCB(self, con, iq_obj):
		log.debug('ErrorCB')
		jid_from = helpers.get_full_jid_from_iq(iq_obj)
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(jid_from)
		id_ = unicode(iq_obj.getID())
		if id_ in self.version_ids:
			self.dispatch('OS_INFO', (jid_stripped, resource, '', ''))
			self.version_ids.remove(id_)
			return
		if id_ in self.last_ids:
			self.dispatch('LAST_STATUS_TIME', (jid_stripped, resource, -1, ''))
			self.last_ids.remove(id_)
			return
		if id_ in self.entity_time_ids:
			self.dispatch('ENTITY_TIME', (jid_stripped, resource, ''))
			self.entity_time_ids.remove(id_)
			return
		if id_ == self.awaiting_xmpp_ping_id:
			self.awaiting_xmpp_ping_id = None
		errmsg = iq_obj.getErrorMsg()
		errcode = iq_obj.getErrorCode()
		self.dispatch('ERROR_ANSWER', (id_, jid_from, errmsg, errcode))

	def _PrivateCB(self, con, iq_obj):
		'''
		Private Data (XEP 048 and 049)
		'''
		log.debug('PrivateCB')
		query = iq_obj.getTag('query')
		storage = query.getTag('storage')
		if storage:
			ns = storage.getNamespace()
			if ns == 'storage:bookmarks':
				# Bookmarked URLs and Conferences
				# http://www.xmpp.org/extensions/xep-0048.html
				confs = storage.getTags('conference')
				for conf in confs:
					autojoin_val = conf.getAttr('autojoin')
					if autojoin_val is None: # not there (it's optional)
						autojoin_val = False
					minimize_val = conf.getAttr('minimize')
					if minimize_val is None: # not there (it's optional)
						minimize_val = False
					print_status = conf.getTagData('print_status')
					if not print_status:
						print_status = conf.getTagData('show_status')
					try:
						bm = {'name': conf.getAttr('name'),
							'jid': helpers.parse_jid(conf.getAttr('jid')),
							'autojoin': autojoin_val,
							'minimize': minimize_val,
							'password': conf.getTagData('password'),
							'nick': conf.getTagData('nick'),
							'print_status': print_status}
					except common.helpers.InvalidFormat:
						log.warn('Invalid JID: %s, ignoring it' % conf.getAttr('jid'))
						continue

					self.bookmarks.append(bm)
				self.dispatch('BOOKMARKS', self.bookmarks)

			elif ns == 'gajim:prefs':
				# Preferences data
				# http://www.xmpp.org/extensions/xep-0049.html
				#TODO: implement this
				pass
			elif ns == 'storage:rosternotes':
				# Annotations
				# http://www.xmpp.org/extensions/xep-0145.html
				notes = storage.getTags('note')
				for note in notes:
					try:
						jid = helpers.parse_jid(note.getAttr('jid'))
					except common.helpers.InvalidFormat:
						log.warn('Invalid JID: %s, ignoring it' % note.getAttr('jid'))
						continue
					annotation = note.getData()
					self.annotations[jid] = annotation

	def _rosterSetCB(self, con, iq_obj):
		log.debug('rosterSetCB')
		version = iq_obj.getTagAttr('query', 'ver')
		for item in iq_obj.getTag('query').getChildren():
			try:
				jid = helpers.parse_jid(item.getAttr('jid'))
			except common.helpers.InvalidFormat:
				log.warn('Invalid JID: %s, ignoring it' % item.getAttr('jid'))
				continue
			name = item.getAttr('name')
			sub = item.getAttr('subscription')
			ask = item.getAttr('ask')
			groups = []
			for group in item.getTags('group'):
				groups.append(group.getData())
			self.dispatch('ROSTER_INFO', (jid, name, sub, ask, groups))
			account_jid = gajim.get_jid_from_account(self.name)
			gajim.logger.add_or_update_contact(account_jid, jid, name, sub, ask,
				groups)
			if version:
				gajim.config.set_per('accounts', self.name, 'roster_version',
					version)
		if not self.connection or self.connected < 2:
			raise common.xmpp.NodeProcessed
		reply = common.xmpp.Iq(typ='result', attrs={'id': iq_obj.getID()},
			to=iq_obj.getFrom(), frm=iq_obj.getTo(), xmlns=None)
		self.connection.send(reply)
		raise common.xmpp.NodeProcessed

	def _VersionCB(self, con, iq_obj):
		log.debug('VersionCB')
		if not self.connection or self.connected < 2:
			return
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.getTag('query')
		qp.setTagData('name', 'Gajim')
		qp.setTagData('version', gajim.version)
		send_os = gajim.config.get_per('accounts', self.name, 'send_os_info')
		if send_os:
			qp.setTagData('os', helpers.get_os_info())
		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed

	def _LastCB(self, con, iq_obj):
		log.debug('LastCB')
		if not self.connection or self.connected < 2:
			return
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.getTag('query')
		if not HAS_IDLE:
			qp.attrs['seconds'] = '0'
		else:
			qp.attrs['seconds'] = idle.getIdleSec()

		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed

	def _LastResultCB(self, con, iq_obj):
		log.debug('LastResultCB')
		qp = iq_obj.getTag('query')
		seconds = qp.getAttr('seconds')
		status = qp.getData()
		try:
			seconds = int(seconds)
		except Exception:
			return
		id_ = iq_obj.getID()
		if id_ in self.groupchat_jids:
			who = self.groupchat_jids[id_]
			del self.groupchat_jids[id_]
		else:
			who = helpers.get_full_jid_from_iq(iq_obj)
		if id_ in self.last_ids:
			self.last_ids.remove(id_)
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
		self.dispatch('LAST_STATUS_TIME', (jid_stripped, resource, seconds, status))

	def _VersionResultCB(self, con, iq_obj):
		log.debug('VersionResultCB')
		client_info = ''
		os_info = ''
		qp = iq_obj.getTag('query')
		if qp.getTag('name'):
			client_info += qp.getTag('name').getData()
		if qp.getTag('version'):
			client_info += ' ' + qp.getTag('version').getData()
		if qp.getTag('os'):
			os_info += qp.getTag('os').getData()
		id_ = iq_obj.getID()
		if id_ in self.groupchat_jids:
			who = self.groupchat_jids[id_]
			del self.groupchat_jids[id_]
		else:
			who = helpers.get_full_jid_from_iq(iq_obj)
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
		if id_ in self.version_ids:
			self.version_ids.remove(id_)
		self.dispatch('OS_INFO', (jid_stripped, resource, client_info, os_info))

	def _TimeCB(self, con, iq_obj):
		log.debug('TimeCB')
		if not self.connection or self.connected < 2:
			return
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.getTag('query')
		qp.setTagData('utc', strftime('%Y%m%dT%H:%M:%S', gmtime()))
		qp.setTagData('tz', helpers.decode_string(tzname[daylight]))
		qp.setTagData('display', helpers.decode_string(strftime('%c',
			localtime())))
		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed

	def _TimeRevisedCB(self, con, iq_obj):
		log.debug('TimeRevisedCB')
		if not self.connection or self.connected < 2:
			return
		iq_obj = iq_obj.buildReply('result')
		qp = iq_obj.setTag('time',
			namespace=common.xmpp.NS_TIME_REVISED)
		qp.setTagData('utc', strftime('%Y-%m-%dT%H:%M:%SZ', gmtime()))
		isdst = localtime().tm_isdst
		zone = -(timezone, altzone)[isdst] / 60
		tzo = (zone / 60, abs(zone % 60))
		qp.setTagData('tzo', '%+03d:%02d' % (tzo))
		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed

	def _TimeRevisedResultCB(self, con, iq_obj):
		log.debug('TimeRevisedResultCB')
		time_info = ''
		qp = iq_obj.getTag('time')
		if not qp:
			# wrong answer
			return
		tzo = qp.getTag('tzo').getData()
		if tzo == 'Z':
			tzo = '0:0'
		tzoh, tzom = tzo.split(':')
		utc_time = qp.getTag('utc').getData()
		ZERO = datetime.timedelta(0)
		class UTC(datetime.tzinfo):
			def utcoffset(self, dt):
				return ZERO
			def tzname(self, dt):
				return "UTC"
			def dst(self, dt):
				return ZERO

		class contact_tz(datetime.tzinfo):
			def utcoffset(self, dt):
				return datetime.timedelta(hours=int(tzoh), minutes=int(tzom))
			def tzname(self, dt):
				return "remote timezone"
			def dst(self, dt):
				return ZERO

		try:
			t = datetime.datetime.strptime(utc_time, '%Y-%m-%dT%H:%M:%SZ')
			t = t.replace(tzinfo=UTC())
			time_info = t.astimezone(contact_tz()).strftime('%c')
		except ValueError, e:
			log.info('Wrong time format: %s' % str(e))

		id_ = iq_obj.getID()
		if id_ in self.groupchat_jids:
			who = self.groupchat_jids[id_]
			del self.groupchat_jids[id_]
		else:
			who = helpers.get_full_jid_from_iq(iq_obj)
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
		if id_ in self.entity_time_ids:
			self.entity_time_ids.remove(id_)
		self.dispatch('ENTITY_TIME', (jid_stripped, resource, time_info))

	def _gMailNewMailCB(self, con, gm):
		'''Called when we get notified of new mail messages in gmail account'''
		if not self.connection or self.connected < 2:
			return
		if not gm.getTag('new-mail'):
			return
		if gm.getTag('new-mail').getNamespace() == common.xmpp.NS_GMAILNOTIFY:
			# we'll now ask the server for the exact number of new messages
			jid = gajim.get_jid_from_account(self.name)
			log.debug('Got notification of new gmail e-mail on %s. Asking the server for more info.' % jid)
			iq = common.xmpp.Iq(typ = 'get')
			iq.setID(self.connection.getAnID())
			query = iq.setTag('query')
			query.setNamespace(common.xmpp.NS_GMAILNOTIFY)
			# we want only be notified about newer mails
			if self.gmail_last_tid:
				query.setAttr('newer-than-tid', self.gmail_last_tid)
			if self.gmail_last_time:
				query.setAttr('newer-than-time', self.gmail_last_time)
			self.connection.send(iq)
			raise common.xmpp.NodeProcessed

	def _gMailQueryCB(self, con, gm):
		'''Called when we receive results from Querying the server for mail messages in gmail account'''
		if not gm.getTag('mailbox'):
			return
		self.gmail_url = gm.getTag('mailbox').getAttr('url')
		if gm.getTag('mailbox').getNamespace() == common.xmpp.NS_GMAILNOTIFY:
			newmsgs = gm.getTag('mailbox').getAttr('total-matched')
			if newmsgs != '0':
				# there are new messages
				gmail_messages_list = []
				if gm.getTag('mailbox').getTag('mail-thread-info'):
					gmail_messages = gm.getTag('mailbox').getTags('mail-thread-info')
					for gmessage in gmail_messages:
						unread_senders = []
						for sender in gmessage.getTag('senders').getTags('sender'):
							if sender.getAttr('unread') != '1':
								continue
							if sender.getAttr('name'):
								unread_senders.append(sender.getAttr('name') + '< ' + \
									sender.getAttr('address') + '>')
							else:
								unread_senders.append(sender.getAttr('address'))

						if not unread_senders:
							continue
						gmail_subject = gmessage.getTag('subject').getData()
						gmail_snippet = gmessage.getTag('snippet').getData()
						tid = int(gmessage.getAttr('tid'))
						if not self.gmail_last_tid or tid > self.gmail_last_tid:
							self.gmail_last_tid = tid
						gmail_messages_list.append({ \
							'From': unread_senders, \
							'Subject': gmail_subject, \
							'Snippet': gmail_snippet, \
							'url': gmessage.getAttr('url'), \
							'participation': gmessage.getAttr('participation'), \
							'messages': gmessage.getAttr('messages'), \
							'date': gmessage.getAttr('date')})
					self.gmail_last_time = int(gm.getTag('mailbox').getAttr(
						'result-time'))

				jid = gajim.get_jid_from_account(self.name)
				log.debug(('You have %s new gmail e-mails on %s.') % (newmsgs, jid))
				self.dispatch('GMAIL_NOTIFY', (jid, newmsgs, gmail_messages_list))
			raise common.xmpp.NodeProcessed

		
	def _rosterItemExchangeCB(self, con, msg):
		''' XEP-0144 Roster Item Echange '''
		exchange_items_list = {}
		jid_from = helpers.get_full_jid_from_iq(msg)
		items_list = msg.getTag('x').getChildren()
		action = items_list[0].getAttr('action')
		if action == None:
			action = 'add'
		for item in msg.getTag('x',
		namespace=common.xmpp.NS_ROSTERX).getChildren():
			try:
				jid = helpers.parse_jid(item.getAttr('jid'))
			except common.helpers.InvalidFormat:
				log.warn('Invalid JID: %s, ignoring it' % item.getAttr('jid'))
				continue
			name = item.getAttr('name')
			groups=[]
			for group in item.getTags('group'):
				groups.append(group.getData())
			exchange_items_list[jid] = []
			exchange_items_list[jid].append(name)
			exchange_items_list[jid].append(groups)
		self.dispatch('ROSTERX', (action, exchange_items_list, jid_from))


	def _messageCB(self, con, msg):
		'''Called when we receive a message'''
		log.debug('MessageCB')

		mtype = msg.getType()
		# check if the message is pubsub#event
		if msg.getTag('event') is not None:
			if mtype == 'groupchat':
				return
			if msg.getTag('error') is None:
				self._pubsubEventCB(con, msg)
			return
		
		# check if the message is a roster item exchange (XEP-0144)
		if msg.getTag('x', namespace=common.xmpp.NS_ROSTERX):
			self._rosterItemExchangeCB(con, msg)
			return

		# check if the message is a XEP-0070 confirmation request
		if msg.getTag('confirm', namespace=common.xmpp.NS_HTTP_AUTH):
			self._HttpAuthCB(con, msg)
			return

		try:
			frm = helpers.get_full_jid_from_iq(msg)
			jid = helpers.get_jid_from_iq(msg)
		except helpers.InvalidFormat:
			self.dispatch('ERROR', (_('Invalid Jabber ID'),
				_('A message from a non-valid JID arrived, it has been ignored.')))

		addressTag = msg.getTag('addresses', namespace = common.xmpp.NS_ADDRESS)

		# Be sure it comes from one of our resource, else ignore address element
		if addressTag and jid == gajim.get_jid_from_account(self.name):
			address = addressTag.getTag('address', attrs={'type': 'ofrom'})
			if address:
				try:
					frm = helpers.parse_jid(address.getAttr('jid'))
				except common.helpers.InvalidFormat:
					log.warn('Invalid JID: %s, ignoring it' % address.getAttr('jid'))
					return
				jid = gajim.get_jid_without_resource(frm)

		# invitations
		invite = None
		encTag = msg.getTag('x', namespace=common.xmpp.NS_ENCRYPTED)

		if not encTag:
			invite = msg.getTag('x', namespace = common.xmpp.NS_MUC_USER)
			if invite and not invite.getTag('invite'):
				invite = None

		# FIXME: Msn transport (CMSN1.2.1 and PyMSN0.10) do NOT RECOMMENDED
		# invitation
		# stanza (MUC XEP) remove in 2007, as we do not do NOT RECOMMENDED
		xtags = msg.getTags('x')
		for xtag in xtags:
			if xtag.getNamespace() == common.xmpp.NS_CONFERENCE and not invite:
				try:
					room_jid = helpers.parse_jid(xtag.getAttr('jid'))
				except common.helpers.InvalidFormat:
					log.warn('Invalid JID: %s, ignoring it' % xtag.getAttr('jid'))
					continue
				is_continued = False
				if xtag.getTag('continue'):
					is_continued = True
				self.dispatch('GC_INVITATION', (room_jid, frm, '', None,
					is_continued))
				return

		thread_id = msg.getThread()

		if not mtype:
			mtype = 'normal'

		msgtxt = msg.getBody()

		encrypted = False
		xep_200_encrypted = msg.getTag('c', namespace=common.xmpp.NS_STANZA_CRYPTO)

		session = None
		if mtype != 'groupchat':
			session = self.get_or_create_session(frm, thread_id)

			if thread_id and not session.received_thread_id:
				session.received_thread_id = True

			session.last_receive = time_time()

		# check if the message is a XEP-0020 feature negotiation request
		if msg.getTag('feature', namespace=common.xmpp.NS_FEATURE):
			if gajim.HAVE_PYCRYPTO:
				feature = msg.getTag(name='feature', namespace=common.xmpp.NS_FEATURE)
				form = common.xmpp.DataForm(node=feature.getTag('x'))

				if form['FORM_TYPE'] == 'urn:xmpp:ssn':
					session.handle_negotiation(form)
				else:
					reply = msg.buildReply()
					reply.setType('error')

					reply.addChild(feature)
					err = common.xmpp.ErrorNode('service-unavailable', typ='cancel')
					reply.addChild(node=err)

					con.send(reply)

				raise common.xmpp.NodeProcessed

			return

		if msg.getTag('init', namespace=common.xmpp.NS_ESESSION_INIT):
			init = msg.getTag(name='init', namespace=common.xmpp.NS_ESESSION_INIT)
			form = common.xmpp.DataForm(node=init.getTag('x'))

			session.handle_negotiation(form)

			raise common.xmpp.NodeProcessed

		tim = msg.getTimestamp()
		tim = helpers.datetime_tuple(tim)
		tim = localtime(timegm(tim))

		if xep_200_encrypted:
			encrypted = 'xep200'

			try:
				msg = session.decrypt_stanza(msg)
				msgtxt = msg.getBody()
			except Exception:
				self.dispatch('FAILED_DECRYPT', (frm, tim, session))

		# Receipt requested
		# TODO: We shouldn't answer if we're invisible!
		contact = gajim.contacts.get_contact(self.name, jid)
		nick = gajim.get_room_and_nick_from_fjid(frm)[1]
		gc_contact = gajim.contacts.get_gc_contact(self.name, jid, nick)
		if msg.getTag('request', namespace=common.xmpp.NS_RECEIPTS) \
		and gajim.config.get_per('accounts', self.name,
		'answer_receipts') and ((contact and contact.sub \
		not in (u'to', u'none')) or gc_contact):
			receipt = common.xmpp.Message(to=frm, typ='chat')
			receipt.setID(msg.getID())
			receipt.setTag('received',
				namespace='urn:xmpp:receipts')

			if thread_id:
				receipt.setThread(thread_id)
			con.send(receipt)

		# We got our message's receipt
		if msg.getTag('received', namespace=common.xmpp.NS_RECEIPTS) \
		and session.control and gajim.config.get_per('accounts',
		self.name, 'request_receipt'):
			session.control.conv_textview.hide_xep0184_warning(
				msg.getID())

		if encTag and self.USE_GPG:
			encmsg = encTag.getData()

			keyID = gajim.config.get_per('accounts', self.name, 'keyid')
			if keyID:
				def decrypt_thread(encmsg, keyID):
					decmsg = self.gpg.decrypt(encmsg, keyID)
					# \x00 chars are not allowed in C (so in GTK)
					msgtxt = helpers.decode_string(decmsg.replace('\x00', ''))
					encrypted = 'xep27'
					return (msgtxt, encrypted)
				gajim.thread_interface(decrypt_thread, [encmsg, keyID],
					self._on_message_decrypted, [mtype, msg, session, frm, jid,
					invite, tim])
				return
		self._on_message_decrypted((msgtxt, encrypted), mtype, msg, session, frm,
			jid, invite, tim)

	def _on_message_decrypted(self, output, mtype, msg, session, frm, jid,
	invite, tim):
		msgtxt, encrypted = output
		if mtype == 'error':
			self.dispatch_error_message(msg, msgtxt, session, frm, tim)
		elif mtype == 'groupchat':
			self.dispatch_gc_message(msg, frm, msgtxt, jid, tim)
		elif invite is not None:
			self.dispatch_invite_message(invite, frm)
		else:
			if isinstance(session, gajim.default_session_type):
				session.received(frm, msgtxt, tim, encrypted, msg)
			else:
				session.received(msg)
	# END messageCB

	# process and dispatch an error message
	def dispatch_error_message(self, msg, msgtxt, session, frm, tim):
		error_msg = msg.getErrorMsg()

		if not error_msg:
			error_msg = msgtxt
			msgtxt = None

		subject = msg.getSubject()

		if session.is_loggable():
			try:
				gajim.logger.write('error', frm, error_msg, tim=tim,
					subject=subject)
			except exceptions.PysqliteOperationalError, e:
				self.dispatch('ERROR', (_('Disk Write Error'), str(e)))
			except exceptions.DatabaseMalformed:
				pritext = _('Database Error')
				sectext = _('The database file (%s) cannot be read. Try to repair '
					'it (see http://trac.gajim.org/wiki/DatabaseBackup) or remove '
					'it (all history will be lost).') % common.logger.LOG_DB_PATH
				self.dispatch('ERROR', (pritext, sectext))
		self.dispatch('MSGERROR', (frm, msg.getErrorCode(), error_msg, msgtxt,
			tim, session))

	# process and dispatch a groupchat message
	def dispatch_gc_message(self, msg, frm, msgtxt, jid, tim):
		has_timestamp = bool(msg.timestamp)

		subject = msg.getSubject()

		if subject is not None:
			self.dispatch('GC_SUBJECT', (frm, subject, msgtxt, has_timestamp))
			return

		statusCode = msg.getStatusCode()

		if not msg.getTag('body'): # no <body>
			# It could be a config change. See
			# http://www.xmpp.org/extensions/xep-0045.html#roomconfig-notify
			if msg.getTag('x'):
				if statusCode != []:
					self.dispatch('GC_CONFIG_CHANGE', (jid, statusCode))
			return

		# Ignore message from room in which we are not
		if jid not in self.last_history_time:
			return

		self.dispatch('GC_MSG', (frm, msgtxt, tim, has_timestamp, msg.getXHTML(),
			statusCode))

		tim_int = int(float(mktime(tim)))
		if gajim.config.should_log(self.name, jid) and not \
		tim_int <= self.last_history_time[jid] and msgtxt and frm.find('/') >= 0:
			# if frm.find('/') < 0, it means message comes from room itself
			# usually it hold description and can be send at each connection
			# so don't store it in logs
			try:
				gajim.logger.write('gc_msg', frm, msgtxt, tim=tim)
			except exceptions.PysqliteOperationalError, e:
				self.dispatch('ERROR', (_('Disk Write Error'), str(e)))
			except exceptions.DatabaseMalformed:
				pritext = _('Database Error')
				sectext = _('The database file (%s) cannot be read. Try to repair '
					'it (see http://trac.gajim.org/wiki/DatabaseBackup) or remove '
					'it (all history will be lost).') % common.logger.LOG_DB_PATH
				self.dispatch('ERROR', (pritext, sectext))

	def dispatch_invite_message(self, invite, frm):
		item = invite.getTag('invite')
		try:
			jid_from = helpers.parse_jid(item.getAttr('from'))
		except common.helpers.InvalidFormat:
			log.warn('Invalid JID: %s, ignoring it' % item.getAttr('from'))
			return
		reason = item.getTagData('reason')
		item = invite.getTag('password')
		password = invite.getTagData('password')

		is_continued = False
		if invite.getTag('invite').getTag('continue'):
			is_continued = True
		self.dispatch('GC_INVITATION',(frm, jid_from, reason, password,
			is_continued))

	def _pubsubEventCB(self, con, msg):
		''' Called when we receive <message/> with pubsub event. '''
		# TODO: Logging? (actually services where logging would be useful, should
		# TODO: allow to access archives remotely...)
		jid = helpers.get_full_jid_from_iq(msg)
		event = msg.getTag('event')

		# XEP-0107: User Mood
		items = event.getTag('items', {'node': common.xmpp.NS_MOOD})
		if items: pep.user_mood(items, self.name, jid)
		# XEP-0118: User Tune
		items = event.getTag('items', {'node': common.xmpp.NS_TUNE})
		if items: pep.user_tune(items, self.name, jid)
		# XEP-0080: User Geolocation
		items = event.getTag('items', {'node': common.xmpp.NS_GEOLOC})
		if items: pep.user_geoloc(items, self.name, jid)
		# XEP-0108: User Activity
		items = event.getTag('items', {'node': common.xmpp.NS_ACTIVITY})
		if items: pep.user_activity(items, self.name, jid)
		# XEP-0172: User Nickname
		items = event.getTag('items', {'node': common.xmpp.NS_NICK})
		if items: pep.user_nickname(items, self.name, jid)

		items = event.getTag('items')
		if items is None: return

		for item in items.getTags('item'):
			entry = item.getTag('entry')
			if entry is not None:
				# for each entry in feed (there shouldn't be more than one,
				# but to be sure...
				self.dispatch('ATOM_ENTRY', (atom.OldEntry(node=entry),))
				continue
			# unknown type... probably user has another client who understands that event
		raise common.xmpp.NodeProcessed

	def _presenceCB(self, con, prs):
		'''Called when we receive a presence'''
		ptype = prs.getType()
		if ptype == 'available':
			ptype = None
		rfc_types = ('unavailable', 'error', 'subscribe', 'subscribed', 'unsubscribe', 'unsubscribed')
		if ptype and not ptype in rfc_types:
			ptype = None
		log.debug('PresenceCB: %s' % ptype)
		if not self.connection or self.connected < 2:
			log.debug('account is no more connected')
			return
		try:
			who = helpers.get_full_jid_from_iq(prs)
		except Exception:
			if prs.getTag('error') and prs.getTag('error').getTag('jid-malformed'):
				# wrong jid, we probably tried to change our nick in a room to a non
				# valid one
				who = str(prs.getFrom())
				jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
				self.dispatch('GC_MSG', (jid_stripped,
					_('Nickname not allowed: %s') % resource, None, False, None, []))
			return
		jid_stripped, resource = gajim.get_room_and_nick_from_fjid(who)
		timestamp = None
		is_gc = False # is it a GC presence ?
		sigTag = None
		ns_muc_user_x = None
		avatar_sha = None
		# XEP-0172 User Nickname
		user_nick = prs.getTagData('nick')
		if not user_nick:
			user_nick = ''
		contact_nickname = None
		transport_auto_auth = False
		# XEP-0203
		delay_tag = prs.getTag('delay', namespace=common.xmpp.NS_DELAY2)
		if delay_tag:
			tim = prs.getTimestamp2()
			tim = helpers.datetime_tuple(tim)
			timestamp = localtime(timegm(tim))
		xtags = prs.getTags('x')
		for x in xtags:
			namespace = x.getNamespace()
			if namespace.startswith(common.xmpp.NS_MUC):
				is_gc = True
				if namespace == common.xmpp.NS_MUC_USER and x.getTag('destroy'):
					ns_muc_user_x = x
			elif namespace == common.xmpp.NS_SIGNED:
				sigTag = x
			elif namespace == common.xmpp.NS_VCARD_UPDATE:
				avatar_sha = x.getTagData('photo')
				contact_nickname = x.getTagData('nickname')
			elif namespace == common.xmpp.NS_DELAY and not timestamp:
				# XEP-0091
				tim = prs.getTimestamp()
				tim = helpers.datetime_tuple(tim)
				timestamp = localtime(timegm(tim))
			elif namespace == 'http://delx.cjb.net/protocol/roster-subsync':
				# see http://trac.gajim.org/ticket/326
				agent = gajim.get_server_from_jid(jid_stripped)
				if self.connection.getRoster().getItem(agent): # to be sure it's a transport contact
					transport_auto_auth = True

		status = prs.getStatus() or ''
		show = prs.getShow()
		if not show in gajim.SHOW_LIST:
			show = '' # We ignore unknown show
		if not ptype and not show:
			show = 'online'
		elif ptype == 'unavailable':
			show = 'offline'

		prio = prs.getPriority()
		try:
			prio = int(prio)
		except Exception:
			prio = 0
		keyID = ''
		if sigTag and self.USE_GPG and ptype != 'error':
			# error presences contain our own signature
			# verify
			sigmsg = sigTag.getData()
			keyID = self.gpg.verify(status, sigmsg)

		if is_gc:
			if ptype == 'error':
				errmsg = prs.getError()
				errcode = prs.getErrorCode()
				room_jid, nick = gajim.get_room_and_nick_from_fjid(who)
				if errcode == '502': # Internal Timeout:
					self.dispatch('NOTIFY', (jid_stripped, 'error', errmsg, resource,
						prio, keyID, timestamp, None))
				elif errcode == '401': # password required to join
					self.dispatch('GC_PASSWORD_REQUIRED', (room_jid, nick))
				elif errcode == '403': # we are banned
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('You are banned from group chat %s.') % room_jid))
				elif errcode == '404': # group chat does not exist
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('Group chat %s does not exist.') % room_jid))
				elif errcode == '405':
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('Group chat creation is restricted.')))
				elif errcode == '406':
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('Your registered nickname must be used in group chat %s.') \
						% room_jid))
				elif errcode == '407':
					self.dispatch('ERROR', (_('Unable to join group chat'),
						_('You are not in the members list in groupchat %s.') % \
						room_jid))
				elif errcode == '409': # nick conflict
					room_jid = gajim.get_room_from_fjid(who)
					self.dispatch('ASK_NEW_NICK', (room_jid,))
				else:	# print in the window the error
					self.dispatch('ERROR_ANSWER', ('', jid_stripped,
						errmsg, errcode))
			if not ptype or ptype == 'unavailable':
				if gajim.config.get('log_contact_status_changes') and \
				gajim.config.should_log(self.name, jid_stripped):
					gc_c = gajim.contacts.get_gc_contact(self.name, jid_stripped,
						resource)
					st = status or ''
					if gc_c:
						jid = gc_c.jid
					else:
						jid = prs.getJid()
					if jid:
						# we know real jid, save it in db
						st += ' (%s)' % jid
					try:
						gajim.logger.write('gcstatus', who, st, show)
					except exceptions.PysqliteOperationalError, e:
						self.dispatch('ERROR', (_('Disk Write Error'), str(e)))
					except exceptions.DatabaseMalformed:
						pritext = _('Database Error')
						sectext = _('The database file (%s) cannot be read. Try to '
							'repair it (see http://trac.gajim.org/wiki/DatabaseBackup)'
							' or remove it (all history will be lost).') % \
							common.logger.LOG_DB_PATH
						self.dispatch('ERROR', (pritext, sectext))
				if avatar_sha or avatar_sha == '':
					if avatar_sha == '':
						# contact has no avatar
						puny_nick = helpers.sanitize_filename(resource)
						gajim.interface.remove_avatar_files(jid_stripped, puny_nick)
					# if it's a gc presence, don't ask vcard here. We may ask it to
					# real jid in gui part.
				if ns_muc_user_x:
					# Room has been destroyed. see
					# http://www.xmpp.org/extensions/xep-0045.html#destroyroom
					reason = _('Room has been destroyed')
					destroy = ns_muc_user_x.getTag('destroy')
					r = destroy.getTagData('reason')
					if r:
						reason += ' (%s)' % r
					try:
						jid = helpers.parse_jid(destroy.getAttr('jid'))
					except common.helpers.InvalidFormat:
						pass
					if jid:
						reason += '\n' + _('You can join this room instead: %s') % jid
					statusCode = ['destroyed']
				else:
					reason = prs.getReason()
					statusCode = prs.getStatusCode()
				self.dispatch('GC_NOTIFY', (jid_stripped, show, status, resource,
					prs.getRole(), prs.getAffiliation(), prs.getJid(),
					reason, prs.getActor(), statusCode, prs.getNewNick(),
					avatar_sha))
			return

		if ptype == 'subscribe':
			log.debug('subscribe request from %s' % who)
			if gajim.config.get('alwaysauth') or who.find("@") <= 0 or \
			jid_stripped in self.jids_for_auto_auth or transport_auto_auth:
				if self.connection:
					p = common.xmpp.Presence(who, 'subscribed')
					p = self.add_sha(p)
					self.connection.send(p)
				if who.find("@") <= 0 or transport_auto_auth:
					self.dispatch('NOTIFY', (jid_stripped, 'offline', 'offline',
						resource, prio, keyID, timestamp, None))
				if transport_auto_auth:
					self.automatically_added.append(jid_stripped)
					self.request_subscription(jid_stripped, name = user_nick)
			else:
				if not status:
					status = _('I would like to add you to my roster.')
				self.dispatch('SUBSCRIBE', (jid_stripped, status, user_nick))
		elif ptype == 'subscribed':
			if jid_stripped in self.automatically_added:
				self.automatically_added.remove(jid_stripped)
			else:
				# detect a subscription loop
				if jid_stripped not in self.subscribed_events:
					self.subscribed_events[jid_stripped] = []
				self.subscribed_events[jid_stripped].append(time_time())
				block = False
				if len(self.subscribed_events[jid_stripped]) > 5:
					if time_time() - self.subscribed_events[jid_stripped][0] < 5:
						block = True
					self.subscribed_events[jid_stripped] = self.subscribed_events[jid_stripped][1:]
				if block:
					gajim.config.set_per('account', self.name,
						'dont_ack_subscription', True)
				else:
					self.dispatch('SUBSCRIBED', (jid_stripped, resource))
			# BE CAREFUL: no con.updateRosterItem() in a callback
			log.debug(_('we are now subscribed to %s') % who)
		elif ptype == 'unsubscribe':
			log.debug(_('unsubscribe request from %s') % who)
		elif ptype == 'unsubscribed':
			log.debug(_('we are now unsubscribed from %s') % who)
			# detect a unsubscription loop
			if jid_stripped not in self.subscribed_events:
				self.subscribed_events[jid_stripped] = []
			self.subscribed_events[jid_stripped].append(time_time())
			block = False
			if len(self.subscribed_events[jid_stripped]) > 5:
				if time_time() - self.subscribed_events[jid_stripped][0] < 5:
					block = True
				self.subscribed_events[jid_stripped] = self.subscribed_events[jid_stripped][1:]
			if block:
				gajim.config.set_per('account', self.name, 'dont_ack_subscription',
					True)
			else:
				self.dispatch('UNSUBSCRIBED', jid_stripped)
		elif ptype == 'error':
			errmsg = prs.getError()
			errcode = prs.getErrorCode()
			if errcode != '502': # Internal Timeout:
				# print in the window the error
				self.dispatch('ERROR_ANSWER', ('', jid_stripped,
					errmsg, errcode))
			if errcode != '409': # conflict # See #5120
				self.dispatch('NOTIFY', (jid_stripped, 'error', errmsg, resource,
					prio, keyID, timestamp, None))

		if ptype == 'unavailable' and jid_stripped in self.sessions:
			# automatically terminate sessions that they haven't sent a thread ID
			# in, only if other part support thread ID
			for sess in self.sessions[jid_stripped].values():
				if not sess.received_thread_id:
					contact = gajim.contacts.get_contact(self.name, jid_stripped)

					session_supported = gajim.capscache.is_supported(contact,
						common.xmpp.NS_SSN) or gajim.capscache.is_supported(contact,
						common.xmpp.NS_ESESSION)
					if session_supported:
						sess.terminate()
						del self.sessions[jid_stripped][sess.thread_id]

		if avatar_sha is not None and ptype != 'error':
			if jid_stripped not in self.vcard_shas:
				cached_vcard = self.get_cached_vcard(jid_stripped)
				if cached_vcard and 'PHOTO' in cached_vcard and \
				'SHA' in cached_vcard['PHOTO']:
					self.vcard_shas[jid_stripped] = cached_vcard['PHOTO']['SHA']
				else:
					self.vcard_shas[jid_stripped] = ''
			if avatar_sha != self.vcard_shas[jid_stripped]:
				# avatar has been updated
				self.request_vcard(jid_stripped)
		if not ptype or ptype == 'unavailable':
			if gajim.config.get('log_contact_status_changes') and \
			gajim.config.should_log(self.name, jid_stripped):
				try:
					gajim.logger.write('status', jid_stripped, status, show)
				except exceptions.PysqliteOperationalError, e:
					self.dispatch('ERROR', (_('Disk Write Error'), str(e)))
				except exceptions.DatabaseMalformed:
					pritext = _('Database Error')
					sectext = _('The database file (%s) cannot be read. Try to '
						'repair it (see http://trac.gajim.org/wiki/DatabaseBackup) '
						'or remove it (all history will be lost).') % \
						common.logger.LOG_DB_PATH
					self.dispatch('ERROR', (pritext, sectext))
			our_jid = gajim.get_jid_from_account(self.name)
			if jid_stripped == our_jid and resource == self.server_resource:
				# We got our own presence
				self.dispatch('STATUS', show)
			else:
				self.dispatch('NOTIFY', (jid_stripped, show, status, resource, prio,
					keyID, timestamp, contact_nickname))
	# END presenceCB

	def _StanzaArrivedCB(self, con, obj):
		self.last_io = gajim.idlequeue.current_time()

	def _MucOwnerCB(self, con, iq_obj):
		log.debug('MucOwnerCB')
		qp = iq_obj.getQueryPayload()
		node = None
		for q in qp:
			if q.getNamespace() == common.xmpp.NS_DATA:
				node = q
		if not node:
			return
		self.dispatch('GC_CONFIG', (helpers.get_full_jid_from_iq(iq_obj), node))

	def _MucAdminCB(self, con, iq_obj):
		log.debug('MucAdminCB')
		items = iq_obj.getTag('query', namespace = common.xmpp.NS_MUC_ADMIN).getTags('item')
		users_dict = {}
		for item in items:
			if item.has_attr('jid') and item.has_attr('affiliation'):
				try:
					jid = helpers.parse_jid(item.getAttr('jid'))
				except common.helpers.InvalidFormat:
					log.warn('Invalid JID: %s, ignoring it' % item.getAttr('jid'))
					return
				affiliation = item.getAttr('affiliation')
				users_dict[jid] = {'affiliation': affiliation}
				if item.has_attr('nick'):
					users_dict[jid]['nick'] = item.getAttr('nick')
				if item.has_attr('role'):
					users_dict[jid]['role'] = item.getAttr('role')
				reason = item.getTagData('reason')
				if reason:
					users_dict[jid]['reason'] = reason

		self.dispatch('GC_AFFILIATION', (helpers.get_full_jid_from_iq(iq_obj),
															users_dict))

	def _MucErrorCB(self, con, iq_obj):
		log.debug('MucErrorCB')
		jid = helpers.get_full_jid_from_iq(iq_obj)
		errmsg = iq_obj.getError()
		errcode = iq_obj.getErrorCode()
		self.dispatch('MSGERROR', (jid, errcode, errmsg))

	def _IqPingCB(self, con, iq_obj):
		log.debug('IqPingCB')
		if not self.connection or self.connected < 2:
			return
		iq_obj = iq_obj.buildReply('result')
		self.connection.send(iq_obj)
		raise common.xmpp.NodeProcessed

	def _PrivacySetCB(self, con, iq_obj):
		'''
		Privacy lists (XEP 016)

		A list has been set
		'''
		log.debug('PrivacySetCB')
		if not self.connection or self.connected < 2:
			return
		result = iq_obj.buildReply('result')
		q = result.getTag('query')
		if q:
			result.delChild(q)
		self.connection.send(result)
		raise common.xmpp.NodeProcessed

	def _getRoster(self):
		log.debug('getRosterCB')
		if not self.connection:
			return
		self.connection.getRoster(self._on_roster_set)
		self.discoverItems(gajim.config.get_per('accounts', self.name,
			'hostname'), id_prefix='Gajim_')
		self.discoverInfo(gajim.config.get_per('accounts', self.name,
			'hostname'), id_prefix='Gajim_')
		if gajim.config.get_per('accounts', self.name, 'use_ft_proxies'):
			self.discover_ft_proxies()

	def discover_ft_proxies(self):
		cfg_proxies = gajim.config.get_per('accounts', self.name,
			'file_transfer_proxies')
		our_jid = helpers.parse_jid(gajim.get_jid_from_account(self.name) + '/' +\
			self.server_resource)
		if cfg_proxies:
			proxies = [e.strip() for e in cfg_proxies.split(',')]
			for proxy in proxies:
				gajim.proxy65_manager.resolve(proxy, self.connection, our_jid)

	def _on_roster_set(self, roster):
		roster_version = roster.version
		received_from_server = roster.received_from_server
		raw_roster = roster.getRaw()
		roster = {}
		our_jid = helpers.parse_jid(gajim.get_jid_from_account(self.name))
		if self.connected > 1 and self.continue_connect_info:
			msg = self.continue_connect_info[1]
			sign_msg = self.continue_connect_info[2]
			signed = ''
			send_first_presence = True
			if sign_msg:
				signed = self.get_signed_presence(msg, self._send_first_presence)
				if signed is None:
					self.dispatch('GPG_PASSWORD_REQUIRED',
						(self._send_first_presence,))
					# _send_first_presence will be called when user enter passphrase
					send_first_presence = False
			if send_first_presence:
				self._send_first_presence(signed)

		for jid in raw_roster:
			try:
				j = helpers.parse_jid(jid)
			except Exception:
				print >> sys.stderr, _('JID %s is not RFC compliant. It will not be added to your roster. Use roster management tools such as http://jru.jabberstudio.org/ to remove it') % jid
			else:
				infos = raw_roster[jid]
				if jid != our_jid and (not infos['subscription'] or \
				infos['subscription'] == 'none') and (not infos['ask'] or \
				infos['ask'] == 'none') and not infos['name'] and \
				not infos['groups']:
					# remove this useless item, it won't be shown in roster anyway
					self.connection.getRoster().delItem(jid)
				elif jid != our_jid: # don't add our jid
					roster[j] = raw_roster[jid]
					if gajim.jid_is_transport(jid) and \
					not gajim.get_transport_name_from_jid(jid):
						# we can't determine which iconset to use
						self.discoverInfo(jid)

		gajim.logger.replace_roster(self.name, roster_version, roster)
		if received_from_server:
			for contact in gajim.contacts.iter_contacts(self.name):
				if not contact.is_groupchat() and contact.jid not in roster:
					self.dispatch('ROSTER_INFO', (contact.jid, None, None, None,
						()))
			for jid in roster:
				self.dispatch('ROSTER_INFO', (jid, roster[jid]['name'],
					roster[jid]['subscription'], roster[jid]['ask'],
					roster[jid]['groups']))

	def _send_first_presence(self, signed = ''):
		show = self.continue_connect_info[0]
		msg = self.continue_connect_info[1]
		sign_msg = self.continue_connect_info[2]
		if sign_msg and not signed:
			signed = self.get_signed_presence(msg)
			if signed is None:
				self.dispatch('ERROR', (_('OpenPGP passphrase was not given'),
					#%s is the account name here
					_('You will be connected to %s without OpenPGP.') % self.name))
				self.USE_GPG = False
				signed = ''
		self.connected = gajim.SHOW_LIST.index(show)
		sshow = helpers.get_xmpp_show(show)
		# send our presence
		if show == 'invisible':
			self.send_invisible_presence(msg, signed, True)
			return
		priority = gajim.get_priority(self.name, sshow)
		our_jid = helpers.parse_jid(gajim.get_jid_from_account(self.name))
		vcard = self.get_cached_vcard(our_jid)
		if vcard and 'PHOTO' in vcard and 'SHA' in vcard['PHOTO']:
			self.vcard_sha = vcard['PHOTO']['SHA']
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
		# ask our VCard
		self.request_vcard(None)

		# Get bookmarks from private namespace
		self.get_bookmarks()

		# Get annotations from private namespace
		self.get_annotations()

		# Inform GUI we just signed in
		self.dispatch('SIGNED_IN', ())
		self.continue_connect_info = None

	def request_gmail_notifications(self):
		if not self.connection or self.connected < 2:
			return
		# It's a gmail account,
		# inform the server that we want e-mail notifications
		our_jid = helpers.parse_jid(gajim.get_jid_from_account(self.name))
		log.debug(('%s is a gmail account. Setting option '
			'to get e-mail notifications on the server.') % (our_jid))
		iq = common.xmpp.Iq(typ = 'set', to = our_jid)
		iq.setAttr('id', 'MailNotify')
		query = iq.setTag('usersetting')
		query.setNamespace(common.xmpp.NS_GTALKSETTING)
		query = query.setTag('mailnotifications')
		query.setAttr('value', 'true')
		self.connection.send(iq)
		# Ask how many messages there are now
		iq = common.xmpp.Iq(typ = 'get')
		iq.setID(self.connection.getAnID())
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_GMAILNOTIFY)
		self.connection.send(iq)


	def _search_fields_received(self, con, iq_obj):
		jid = jid = helpers.get_jid_from_iq(iq_obj)
		tag = iq_obj.getTag('query', namespace = common.xmpp.NS_SEARCH)
		if not tag:
			self.dispatch('SEARCH_FORM', (jid, None, False))
			return
		df = tag.getTag('x', namespace = common.xmpp.NS_DATA)
		if df:
			self.dispatch('SEARCH_FORM', (jid, df, True))
			return
		df = {}
		for i in iq_obj.getQueryPayload():
			df[i.getName()] = i.getData()
		self.dispatch('SEARCH_FORM', (jid, df, False))

	def _StreamCB(self, con, obj):
		if obj.getTag('conflict'):
			# disconnected because of a resource conflict
			self.dispatch('RESOURCE_CONFLICT', ())

	def _register_handlers(self, con, con_type):
		# try to find another way to register handlers in each class
		# that defines handlers
		con.RegisterHandler('message', self._messageCB)
		con.RegisterHandler('presence', self._presenceCB)
		con.RegisterHandler('presence', self._capsPresenceCB)
		con.RegisterHandler('iq', self._vCardCB, 'result',
			common.xmpp.NS_VCARD)
		con.RegisterHandler('iq', self._rosterSetCB, 'set',
			common.xmpp.NS_ROSTER)
		con.RegisterHandler('iq', self._siSetCB, 'set',
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._rosterItemExchangeCB, 'set',
			common.xmpp.NS_ROSTERX)
		con.RegisterHandler('iq', self._siErrorCB, 'error',
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._siResultCB, 'result',
			common.xmpp.NS_SI)
		con.RegisterHandler('iq', self._discoGetCB, 'get',
			common.xmpp.NS_DISCO)
		con.RegisterHandler('iq', self._bytestreamSetCB, 'set',
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._bytestreamResultCB, 'result',
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._bytestreamErrorCB, 'error',
			common.xmpp.NS_BYTESTREAM)
		con.RegisterHandler('iq', self._DiscoverItemsCB, 'result',
			common.xmpp.NS_DISCO_ITEMS)
		con.RegisterHandler('iq', self._DiscoverItemsErrorCB, 'error',
			common.xmpp.NS_DISCO_ITEMS)
		con.RegisterHandler('iq', self._DiscoverInfoCB, 'result',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._DiscoverInfoErrorCB, 'error',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._VersionCB, 'get',
			common.xmpp.NS_VERSION)
		con.RegisterHandler('iq', self._TimeCB, 'get',
			common.xmpp.NS_TIME)
		con.RegisterHandler('iq', self._TimeRevisedCB, 'get',
			common.xmpp.NS_TIME_REVISED)
		con.RegisterHandler('iq', self._LastCB, 'get',
			common.xmpp.NS_LAST)
		con.RegisterHandler('iq', self._LastResultCB, 'result',
			common.xmpp.NS_LAST)
		con.RegisterHandler('iq', self._VersionResultCB, 'result',
			common.xmpp.NS_VERSION)
		con.RegisterHandler('iq', self._TimeRevisedResultCB, 'result',
			common.xmpp.NS_TIME_REVISED)
		con.RegisterHandler('iq', self._MucOwnerCB, 'result',
			common.xmpp.NS_MUC_OWNER)
		con.RegisterHandler('iq', self._MucAdminCB, 'result',
			common.xmpp.NS_MUC_ADMIN)
		con.RegisterHandler('iq', self._PrivateCB, 'result',
			common.xmpp.NS_PRIVATE)
		con.RegisterHandler('iq', self._HttpAuthCB, 'get',
			common.xmpp.NS_HTTP_AUTH)
		con.RegisterHandler('iq', self._CommandExecuteCB, 'set',
			common.xmpp.NS_COMMANDS)
		con.RegisterHandler('iq', self._gMailNewMailCB, 'set',
			common.xmpp.NS_GMAILNOTIFY)
		con.RegisterHandler('iq', self._gMailQueryCB, 'result',
			common.xmpp.NS_GMAILNOTIFY)
		con.RegisterHandler('iq', self._DiscoverInfoGetCB, 'get',
			common.xmpp.NS_DISCO_INFO)
		con.RegisterHandler('iq', self._DiscoverItemsGetCB, 'get',
			common.xmpp.NS_DISCO_ITEMS)
		con.RegisterHandler('iq', self._IqPingCB, 'get',
			common.xmpp.NS_PING)
		con.RegisterHandler('iq', self._search_fields_received, 'result',
			common.xmpp.NS_SEARCH)
		con.RegisterHandler('iq', self._PrivacySetCB, 'set',
			common.xmpp.NS_PRIVACY)
		con.RegisterHandler('iq', self._PubSubCB, 'result')
		con.RegisterHandler('iq', self._ErrorCB, 'error')
		con.RegisterHandler('iq', self._IqCB)
		con.RegisterHandler('iq', self._StanzaArrivedCB)
		con.RegisterHandler('iq', self._ResultCB, 'result')
		con.RegisterHandler('presence', self._StanzaArrivedCB)
		con.RegisterHandler('message', self._StanzaArrivedCB)
		con.RegisterHandler('unknown', self._StreamCB, 'urn:ietf:params:xml:ns:xmpp-streams', xmlns='http://etherx.jabber.org/streams')

# vim: se ts=3:
