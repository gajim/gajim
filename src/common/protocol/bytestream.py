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

import socket

from common import xmpp
from common import gajim
from common import helpers
from common import dataforms

from common.socks5 import Socks5Receiver


def is_transfer_paused(file_props):
	if 'stopped' in file_props and file_props['stopped']:
		return False
	if 'completed' in file_props and file_props['completed']:
		return False
	if 'disconnect_cb' not in file_props:
		return False
	return file_props['paused']

def is_transfer_active(file_props):
	if 'stopped' in file_props and file_props['stopped']:
		return False
	if 'completed' in file_props and file_props['completed']:
		return False
	if 'started' not in file_props or not file_props['started']:
		return False
	if 'paused' not in file_props:
		return True
	return not file_props['paused']

def is_transfer_stopped(file_props):
	if 'error' in file_props and file_props['error'] != 0:
		return True
	if 'completed' in file_props and file_props['completed']:
		return True
	if 'connected' in file_props and file_props['connected'] == False:
		return True
	if 'stopped' not in file_props or not file_props['stopped']:
		return False
	return True


class ConnectionBytestream:

	def __init__(self):
		self.files_props = {}

	def send_success_connect_reply(self, streamhost):
		"""
		Send reply to the initiator of FT that we made a connection
		"""
		if not self.connection or self.connected < 2:
			return
		if streamhost is None:
			return None
		iq = xmpp.Iq(to=streamhost['initiator'], typ='result',
			frm=streamhost['target'])
		iq.setAttr('id', streamhost['id'])
		query = iq.setTag('query', namespace=xmpp.NS_BYTESTREAM)
		stream_tag = query.setTag('streamhost-used')
		stream_tag.setAttr('jid', streamhost['jid'])
		self.connection.send(iq)

	def stop_all_active_file_transfers(self, contact):
		"""
		Stop all active transfer to or from the given contact
		"""
		for file_props in self.files_props.values():
			if is_transfer_stopped(file_props):
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
		"""
		Stop and remove all active connections from the socks5 pool
		"""
		for file_props in self.files_props.values():
			self.remove_transfer(file_props, remove_from_list=False)
		self.files_props = {}

	def remove_transfer(self, file_props, remove_from_list=True):
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

	def _send_socks5_info(self, file_props):
		"""
		Send iq for the present streamhosts and proxies
		"""
		if not self.connection or self.connected < 2:
			return
		receiver = file_props['receiver']
		sender = file_props['sender']

		sha_str = helpers.get_auth_sha(file_props['sid'], sender, receiver)
		file_props['sha_str'] = sha_str

		port = gajim.config.get('file_transfers_port')
		listener = gajim.socks5queue.start_listener(port, sha_str,
			self._result_socks5_sid, file_props['sid'])
		if not listener:
			file_props['error'] = -5
			self.dispatch('FILE_REQUEST_ERROR', (unicode(receiver), file_props, ''))
			self._connect_error(unicode(receiver), file_props['sid'],
				file_props['sid'], code=406)
		else:
			iq = xmpp.Iq(to=unicode(receiver), typ='set')
			file_props['request-id'] = 'id_' + file_props['sid']
			iq.setID(file_props['request-id'])
			query = iq.setTag('query', namespace=xmpp.NS_BYTESTREAM)
			query.setAttr('mode', 'plain')
			query.setAttr('sid', file_props['sid'])

			self._add_addiditional_streamhosts_to_query(query, file_props)
			self._add_local_ips_as_streamhosts_to_query(query, file_props)
			self._add_proxy_streamhosts_to_query(query, file_props)

			self.connection.send(iq)

	def _add_streamhosts_to_query(self, query, sender, port, hosts):
		for host in hosts:
			streamhost = xmpp.Node(tag='streamhost')
			query.addChild(node=streamhost)
			streamhost.setAttr('port', unicode(port))
			streamhost.setAttr('host', host)
			streamhost.setAttr('jid', sender)

	def _add_local_ips_as_streamhosts_to_query(self, query, file_props):
		try:
			my_ips = [self.peerhost[0]] # The ip we're connected to server with
			# all IPs from local DNS
			for addr in socket.getaddrinfo(socket.gethostname(), None):
				if not addr[4][0] in my_ips and not addr[4][0].startswith('127'):
					my_ips.append(addr[4][0])

			sender = file_props['sender']
			port = gajim.config.get('file_transfers_port')
			self._add_streamhosts_to_query(query, sender, port, my_ips)
		except socket.gaierror:
			self.dispatch('ERROR', (_('Wrong host'),
				_('Invalid local address? :-O')))

	def _add_addiditional_streamhosts_to_query(self, query, file_props):
		sender = file_props['sender']
		port = gajim.config.get('file_transfers_port')
		ft_add_hosts_to_send = gajim.config.get('ft_add_hosts_to_send')
		additional_hosts = []
		if ft_add_hosts_to_send:
			additional_hosts = [e.strip() for e in ft_add_hosts_to_send.split(',')]
		else:
			additional_hosts = []
		self._add_streamhosts_to_query(query, sender, port, additional_hosts)

	def _add_proxy_streamhosts_to_query(self, query, file_props):
		proxyhosts = self._get_file_transfer_proxies_from_config(file_props)
		if proxyhosts:
			file_props['proxy_receiver'] = unicode(file_props['receiver'])
			file_props['proxy_sender'] = unicode(file_props['sender'])
			file_props['proxyhosts'] = proxyhosts

			for proxyhost in proxyhosts:
				self._add_streamhosts_to_query(query, proxyhost['jid'],
				proxyhost['port'], [proxyhost['host']])

	def _get_file_transfer_proxies_from_config(self, file_props):
		configured_proxies = gajim.config.get_per('accounts', self.name,
			'file_transfer_proxies')
		shall_use_proxies = gajim.config.get_per('accounts', self.name,
			'use_ft_proxies')
		if shall_use_proxies and configured_proxies:
			proxyhost_dicts = []
			proxies = [item.strip() for item in configured_proxies.split(',')]
			default_proxy = gajim.proxy65_manager.get_default_for_name(self.name)
			if default_proxy:
				# add/move default proxy at top of the others
				if default_proxy in proxies:
					proxies.remove(default_proxy)
				proxies.insert(0, default_proxy)

			for proxy in proxies:
				(host, _port, jid) = gajim.proxy65_manager.get_proxy(proxy, self.name)
				if not host:
					continue
				host_dict = {
					'state': 0,
					'target': unicode(file_props['receiver']),
					'id': file_props['sid'],
					'sid': file_props['sid'],
					'initiator': proxy,
					'host': host,
					'port': unicode(_port),
					'jid': jid
				}
				proxyhost_dicts.append(host_dict)
			return proxyhost_dicts
		else:
			return []

	def send_file_rejection(self, file_props, code='403', typ=None):
		"""
		Inform sender that we refuse to download the file

		typ is used when code = '400', in this case typ can be 'strean' for
		invalid stream or 'profile' for invalid profile
		"""
		# user response to ConfirmationDialog may come after we've disconneted
		if not self.connection or self.connected < 2:
			return
		iq = xmpp.Iq(to=unicode(file_props['sender']), typ='error')
		iq.setAttr('id', file_props['request-id'])
		if code == '400' and typ in ('stream', 'profile'):
			name = 'bad-request'
			text = ''
		else:
			name = 'forbidden'
			text = 'Offer Declined'
		err = xmpp.ErrorNode(code=code, typ='cancel', name=name, text=text)
		if code == '400' and typ in ('stream', 'profile'):
			if typ == 'stream':
				err.setTag('no-valid-streams', namespace=xmpp.NS_SI)
			else:
				err.setTag('bad-profile', namespace=xmpp.NS_SI)
		iq.addChild(node=err)
		self.connection.send(iq)

	def send_file_approval(self, file_props):
		"""
		Send iq, confirming that we want to download the file
		"""
		# user response to ConfirmationDialog may come after we've disconneted
		if not self.connection or self.connected < 2:
			return
		iq = xmpp.Iq(to=unicode(file_props['sender']), typ='result')
		iq.setAttr('id', file_props['request-id'])
		si = iq.setTag('si', namespace=xmpp.NS_SI)
		if 'offset' in file_props and file_props['offset']:
			file_tag = si.setTag('file', namespace=xmpp.NS_FILE)
			range_tag = file_tag.setTag('range')
			range_tag.setAttr('offset', file_props['offset'])
		feature = si.setTag('feature', namespace=xmpp.NS_FEATURE)
		_feature = xmpp.DataForm(typ='submit')
		feature.addChild(node=_feature)
		field = _feature.setField('stream-method')
		field.delAttr('type')
		field.setValue(xmpp.NS_BYTESTREAM)
		self.connection.send(iq)

	def _ft_get_our_jid(self):
		our_jid = gajim.get_jid_from_account(self.name)
		resource = self.server_resource
		return our_jid + '/' + resource

	def _ft_get_receiver_jid(self, file_props):
		return file_props['receiver'].jid + '/' + file_props['receiver'].resource

	def send_file_request(self, file_props):
		"""
		Send iq for new FT request
		"""
		if not self.connection or self.connected < 2:
			return
		file_props['sender'] = self._ft_get_our_jid()
		fjid = self._ft_get_receiver_jid(file_props)
		iq = xmpp.Iq(to=fjid, typ='set')
		iq.setID(file_props['sid'])
		self.files_props[file_props['sid']] = file_props
		si = iq.setTag('si', namespace=xmpp.NS_SI)
		si.setAttr('profile', xmpp.NS_FILE)
		si.setAttr('id', file_props['sid'])
		file_tag = si.setTag('file', namespace=xmpp.NS_FILE)
		file_tag.setAttr('name', file_props['name'])
		file_tag.setAttr('size', file_props['size'])
		desc = file_tag.setTag('desc')
		if 'desc' in file_props:
			desc.setData(file_props['desc'])
		file_tag.setTag('range')
		feature = si.setTag('feature', namespace=xmpp.NS_FEATURE)
		_feature = xmpp.DataForm(typ='form')
		feature.addChild(node=_feature)
		field = _feature.setField('stream-method')
		field.setAttr('type', 'list-single')
		field.addOption(xmpp.NS_BYTESTREAM)
		self.connection.send(iq)

	def _result_socks5_sid(self, sid, hash_id):
		"""
		Store the result of SHA message from auth
		"""
		if sid not in self.files_props:
			return
		file_props = self.files_props[sid]
		file_props['hash'] = hash_id
		return

	def _connect_error(self, to, _id, sid, code=404):
		"""
		Called when there is an error establishing BS connection, or when
		connection is rejected
		"""
		if not self.connection or self.connected < 2:
			return
		msg_dict = {
			404: 'Could not connect to given hosts',
			405: 'Cancel',
			406: 'Not acceptable',
		}
		msg = msg_dict[code]
		iq = xmpp.Iq(to=to, 	typ='error')
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
		"""
		Called after authentication to proxy server
		"""
		if not self.connection or self.connected < 2:
			return
		file_props = self.files_props[proxy['sid']]
		iq = xmpp.Iq(to=proxy['initiator'], 	typ='set')
		auth_id = "au_" + proxy['sid']
		iq.setID(auth_id)
		query = iq.setTag('query', namespace=xmpp.NS_BYTESTREAM)
		query.setAttr('sid', proxy['sid'])
		activate = query.setTag('activate')
		activate.setData(file_props['proxy_receiver'])
		iq.setID(auth_id)
		self.connection.send(iq)

	# register xmpppy handlers for bytestream and FT stanzas
	def _bytestreamErrorCB(self, con, iq_obj):
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
		raise xmpp.NodeProcessed

	def _ft_get_from(self, iq_obj):
		return helpers.get_full_jid_from_iq(iq_obj)

	def _bytestreamSetCB(self, con, iq_obj):
		target = unicode(iq_obj.getAttr('to'))
		id_ = unicode(iq_obj.getAttr('id'))
		query = iq_obj.getTag('query')
		sid = unicode(query.getAttr('sid'))
		file_props = gajim.socks5queue.get_file_props(self.name, sid)
		streamhosts = []
		for item in query.getChildren():
			if item.getName() == 'streamhost':
				host_dict = {
					'state': 0,
					'target': target,
					'id': id_,
					'sid': sid,
					'initiator': self._ft_get_from(iq_obj)
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
				raise xmpp.NodeProcessed

		file_props['streamhosts'] = streamhosts
		if file_props['type'] == 'r':
			gajim.socks5queue.connect_to_hosts(self.name, sid,
				self.send_success_connect_reply, self._connect_error)
		raise xmpp.NodeProcessed

	def _ResultCB(self, con, iq_obj):
		# if we want to respect xep-0065 we have to check for proxy
		# activation result in any result iq
		real_id = unicode(iq_obj.getAttr('id'))
		if not real_id.startswith('au_'):
			return
		frm = self._ft_get_from(iq_obj)
		id_ = real_id[3:]
		if id_ in self.files_props:
			file_props = self.files_props[id_]
			if file_props['streamhost-used']:
				for host in file_props['proxyhosts']:
					if host['initiator'] == frm and 'idx' in host:
						gajim.socks5queue.activate_proxy(host['idx'])
						raise xmpp.NodeProcessed

	def _ft_get_streamhost_jid_attr(self, streamhost):
		return helpers.parse_jid(streamhost.getAttr('jid'))

	def _bytestreamResultCB(self, con, iq_obj):
		frm = self._ft_get_from(iq_obj)
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
			raise xmpp.NodeProcessed
		if streamhost is None:
			# proxy approves the activate query
			if real_id.startswith('au_'):
				if 'streamhost-used' not in file_props or \
				file_props['streamhost-used'] is False:
					raise xmpp.NodeProcessed
				if 'proxyhosts' not in file_props:
					raise xmpp.NodeProcessed
				for host in file_props['proxyhosts']:
					if host['initiator'] == frm and \
					unicode(query.getAttr('sid')) == file_props['sid']:
						gajim.socks5queue.activate_proxy(host['idx'])
						break
			raise xmpp.NodeProcessed
		jid = self._ft_get_streamhost_jid_attr(streamhost)
		if 'streamhost-used' in file_props and \
			file_props['streamhost-used'] is True:
			raise xmpp.NodeProcessed

		if real_id.startswith('au_'):
			if 'stopped' in file and file_props['stopped']:
				self.remove_transfer(file_props)
			else:
				gajim.socks5queue.send_file(file_props, self.name)
			raise xmpp.NodeProcessed

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
			receiver = Socks5Receiver(gajim.idlequeue, proxy,
				file_props['sid'], file_props)
			gajim.socks5queue.add_receiver(self.name, receiver)
			proxy['idx'] = receiver.queue_idx
			gajim.socks5queue.on_success = self._proxy_auth_ok
			raise xmpp.NodeProcessed

		else:
			if 'stopped' in file_props and file_props['stopped']:
				self.remove_transfer(file_props)
			else:
				gajim.socks5queue.send_file(file_props, self.name)
			if 'fast' in file_props:
				fasts = file_props['fast']
				if len(fasts) > 0:
					self._connect_error(frm, fasts[0]['id'], file_props['sid'],
						code=406)

		raise xmpp.NodeProcessed

	def _siResultCB(self, con, iq_obj):
		file_props = self.files_props.get(iq_obj.getAttr('id'))
		if not file_props:
			return
		if 'request-id' in file_props:
			# we have already sent streamhosts info
			return
		file_props['receiver'] = self._ft_get_from(iq_obj)
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
		if feature.getNamespace() != xmpp.NS_FEATURE:
			return
		form_tag = feature.getTag('x')
		form = xmpp.DataForm(node=form_tag)
		field = form.getField('stream-method')
		if field.getValue() != xmpp.NS_BYTESTREAM:
			return
		self._send_socks5_info(file_props)
		raise xmpp.NodeProcessed

	def _siSetCB(self, con, iq_obj):
		jid = self._ft_get_from(iq_obj)
		file_props = {'type': 'r'}
		file_props['sender'] = jid
		file_props['request-id'] = unicode(iq_obj.getAttr('id'))
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		mime_type = si.getAttr('mime-type')
		if profile != xmpp.NS_FILE:
			self.send_file_rejection(file_props, code='400', typ='profile')
			raise xmpp.NodeProcessed
		feature_tag = si.getTag('feature', namespace=xmpp.NS_FEATURE)
		if not feature_tag:
			return
		form_tag = feature_tag.getTag('x', namespace=xmpp.NS_DATA)
		if not form_tag:
			return
		form = dataforms.ExtendForm(node=form_tag)
		for f in form.iter_fields():
			if f.var == 'stream-method' and f.type == 'list-single':
				values = [o[1] for o in f.options]
				if xmpp.NS_BYTESTREAM in values:
					break
		else:
			self.send_file_rejection(file_props, code='400', typ='stream')
			raise xmpp.NodeProcessed
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
		file_props['receiver'] = self._ft_get_our_jid()
		file_props['sid'] = unicode(si.getAttr('id'))
		file_props['transfered_size'] = []
		gajim.socks5queue.add_file_props(self.name, file_props)
		self.dispatch('FILE_REQUEST', (jid, file_props))
		raise xmpp.NodeProcessed

	def _siErrorCB(self, con, iq_obj):
		si = iq_obj.getTag('si')
		profile = si.getAttr('profile')
		if profile != xmpp.NS_FILE:
			return
		file_props = self.files_props.get(iq_obj.getAttr('id'))
		if not file_props:
			return
		jid = self._ft_get_from(iq_obj)
		file_props['error'] = -3
		self.dispatch('FILE_REQUEST_ERROR', (jid, file_props, ''))
		raise xmpp.NodeProcessed


class ConnectionBytestreamZeroconf(ConnectionBytestream):

	def _ft_get_from(self, iq_obj):
		return unicode(iq_obj.getFrom())

	def _ft_get_our_jid(self):
		return gajim.get_jid_from_account(self.name)

	def _ft_get_receiver_jid(self, file_props):
		return file_props['receiver'].jid

	def _ft_get_streamhost_jid_attr(self, streamhost):
		return streamhost.getAttr('jid')

# vim: se ts=3:
