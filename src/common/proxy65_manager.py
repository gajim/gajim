##
## Copyright (C) 2006 Gajim Team
##
## Contributors for this file:
##	- Dimitur Kirov <dkirov@gmail.com>
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
import socket 
import struct
import errno

import common.xmpp
from common import gajim
from common import helpers
from socks5 import Socks5
from common.xmpp.idlequeue import IdleObject

S_INITIAL = 0
S_STARTED = 1
S_RESOLVED = 2
S_ACTIVATED = 3
S_FINISHED = 4

CONNECT_TIMEOUT = 20

class Proxy65Manager:
	''' keep records for file transfer proxies. Each time account 
	establishes a connection to its server call proxy65manger.resolve(proxy) 
	for every proxy that is convigured within the account. The class takes 
	care to resolve and test each proxy only once.'''
	def __init__(self, idlequeue):
		# dict {proxy: proxy properties}
		self.idlequeue = idlequeue
		self.proxies = {}
		# dict {account: proxy} default proxy for account
		self.default_proxies = {}
	
	def resolve(self, proxy, connection, default = None):
		''' start '''
		if self.proxies.has_key(proxy):
			resolver = self.proxies[proxy]
		else:
			# proxy is being ressolved for the first time
			resolver = ProxyResolver(proxy)
			self.proxies[proxy] = resolver
			resolver.add_connection(connection)
		if default:
			# add this proxy as default for account
			self.default_proxies[default] = proxy
	
	def disconnect(self, connection):
		for resolver in self.proxies.values():
			resolver.disconnect(connection)
	
	def resolve_result(self, proxy, query):
		if not self.proxies.has_key(proxy):
			return
		jid = None
		for item in query.getChildren():
			if item.getName() == 'streamhost':
				host = item.getAttr('host')
				port = item.getAttr('port')
				jid = item.getAttr('jid')
				self.proxies[proxy].resolve_result(host, port, jid)
				# we can have only one streamhost
				raise common.xmpp.NodeProcessed
	
	def error_cb(self, proxy, query):
		sid = query.getAttr('sid')
		for resolver in self.proxies.values():
			if resolver.sid == sid:
				resolver.keep_conf()
				break
	
	def get_default_for_name(self, account):
		if self.default_proxies.has_key(account):
			return self.default_proxies[account]
	
	def get_proxy(self, proxy, account):
		if self.proxies.has_key(proxy):
			resolver = self.proxies[proxy]
			if resolver.state == S_FINISHED:
				return (resolver.host, resolver.port, resolver.jid)
		return (None, 0, None)

class ProxyResolver:
	def resolve_result(self, host, port, jid):
		''' test if host has a real proxy65 listening on port '''
		self.host = unicode(host)
		self.port = int(port)
		self.jid = unicode(jid)
		self.state = S_RESOLVED
		self.host_tester = HostTester(self.host, self.port, self.jid, 
				self._on_connect_success, self._on_connect_failure)
		self.host_tester.connect()
	
	def _on_connect_success(self):
		iq = common.xmpp.Protocol(name = 'iq', to = self.jid, typ = 'set')
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		query.setAttr('sid',  self.sid)
		
		activate = query.setTag('activate')
		activate.setData(self.jid + "/" + self.sid)

		if self.active_connection:
			self.active_connection.send(iq)
			self.state = S_ACTIVATED
		else:
			self.state = S_INITIAL
		
	def keep_conf(self):
		self.state = S_FINISHED
	
	def _on_connect_failure(self):
		self.state = S_FINISHED
		self.host = None
		self.port = 0
		self.jid = None
	
	def disconnect(self, connection):
		if self.host_tester:
			self.host_tester.disconnect()
			self.host_tester = None
		try:
			self.connections.remove(connection)
		except ValueError:
			pass
		if connection == self.active_connection:
			self.active_connection = None
			if self.state != S_FINISHED:
				self.state = S_INITIAL
				self.try_next_connection()
	
	def try_next_connection(self):
		''' try to resolve proxy with the next possible connection '''
		if self.connections:
			connection = self.connections.pop(0)
			self.start_resolve(connection)
	
	def add_connection(self, connection):
		''' add a new connection in case the first fails '''
		self.connections.append(connection)
		if self.state == S_INITIAL:
			self.start_resolve(connection)
	
	def start_resolve(self, connection):
		''' request network address from proxy '''
		self.state = S_STARTED
		self.active_connection = connection
		iq = common.xmpp.Protocol(name = 'iq', to = self.proxy, typ = 'get')
		query = iq.setTag('query')
		query.setNamespace(common.xmpp.NS_BYTESTREAM)
		connection.send(iq)
	
	def __init__(self, proxy):
		self.proxy = proxy
		self.state = S_INITIAL
		self.active_connection = None
		self.connections = []
		self.host_tester = None
		self.jid = None
		self.host = None
		self.port = None
		self.sid = helpers.get_random_string_16()
		
class HostTester(Socks5, IdleObject):
	''' fake proxy tester. '''
	def __init__(self, host, port, jid, on_success, on_failure):
		''' try to establish and auth to proxy at (host, port)
		call on_success, or on_failure according to the result'''
		self.host = host
		self.port = port
		self.jid = jid
		self.on_success = on_success
		self.on_failure = on_failure
		self._sock = None
		self.file_props = {}
		Socks5.__init__(self, gajim.idlequeue, host, port, None, None, None)
	
	def connect(self):
		''' create the socket and plug it to the idlequeue '''
		if self.host is None:
			self.on_failure()
			return None
		self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._sock.setblocking(False)
		self.fd = self._sock.fileno()
		self.state = 0 # about to be connected
		gajim.idlequeue.plug_idle(self, True, False)
		self.do_connect()
		self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
		return None
		
	def read_timeout(self):
		self.idlequeue.remove_timeout(self.fd)
		self.pollend()
		
	def pollend(self):
		self.disconnect()
		self.on_failure()
	
	def pollout(self):
		self.idlequeue.remove_timeout(self.fd)
		if self.state == 0:
			self.do_connect()
			return
		elif self.state == 1: # send initially: version and auth types
			data = self._get_auth_buff()
			self.send_raw(data)
		else:
			return
		self.state += 1
		# unplug and plug for reading
		gajim.idlequeue.plug_idle(self, False, True)
		gajim.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
	
	def pollin(self):
		self.idlequeue.remove_timeout(self.fd)
		if self.state == 2:
			self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
			# begin negotiation. on success 'address' != 0 
			buff = self.receive()
			if buff == '':
				# end connection
				self.pollend()
				return
			# read auth response
			if buff is None or len(buff) != 2:
				return None
			version, method = struct.unpack('!BB', buff[:2])
			if version != 0x05 or method == 0xff:
				self.pollend()
			self.disconnect()
			self.on_success()
		else:
			self.disconnect()
	
	def do_connect(self):
		try:
			self._sock.connect((self.host, self.port))
			self._sock.setblocking(False)
			self._send=self._sock.send
			self._recv=self._sock.recv
		except Exception, ee:
			(errnum, errstr) = ee
			# 56 is for freebsd
			if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
				# still trying to connect
				return
			# win32 needs this
			if errnum not in (0, 10056, errno.EISCONN):
				# connection failed
				self.on_failure()
				return
			# socket is already connected
			self._sock.setblocking(False)
			self._send=self._sock.send
			self._recv=self._sock.recv
		self.buff = ''
		self.state = 1 # connected
		self.idlequeue.plug_idle(self, True, False)
		return 
		

# vim: se ts=3: