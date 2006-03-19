##
## Copyright (C) 2006 Gajim Team
##
## Contributors for this file:
##	- Dimitur Kirov <dkirov@gmail.com>
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
import socket 
import struct

import common.xmpp
from common import gajim
from socks5 import Socks5
from common.xmpp.idlequeue import IdleObject

S_INITIAL = 0
S_STARTED = 1
S_RESOLVED = 2
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
	
	def resolve(self, proxy, connection):
		''' start '''
		if self.proxies.has_key(proxy):
			resolver = self.proxies[proxy]
		else:
			# proxy is being ressolved for the first time
			resolver = ProxyResolver(proxy)
			self.proxies[proxy] = resolver
			resolver.add_connection(connection)
		
		if resolver.state == S_FINISHED:
			# resolving this proxy is already started or completed
			return
	
	def diconnect(self, connection):
		for resolver in self.proxies:
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
	def get_proxy(self, proxy):
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
		conf = gajim.config
		conf.add_per('ft_proxies65_cache', self.proxy)
		conf.set_per('ft_proxies65_cache', self.proxy, 'host', self.host)
		conf.set_per('ft_proxies65_cache', self.proxy, 'port', self.port)
		conf.set_per('ft_proxies65_cache', self.proxy, 'jid', self.jid)
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
		if self.connections.has_key(connection):
			self.connections.remove(connection)
			if self.state == S_STARTED:
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
		self.connections = []
		self.host_tester = None
		self.jid = None
		self.host = None
		self.port = None
		
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
		elif self.state == 3: # send 'connect' request
			data = self._get_request_buff(self._get_sha1_auth())
			self.send_raw(data)
		else:
			return
		self.state += 1
		# unplug and plug for reading
		gajim.idlequeue.plug_idle(self, False, True)
		gajim.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
	
	def pollin(self):
		self.idlequeue.remove_timeout(self.fd)
		if self.state > 1:
			self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT)
			result = self.main(0)
		else:
			self.disconnect()
	
	def main(self, timeout = 0):
		''' begin negotiation. on success 'address' != 0 '''
		result = 1
		buff = self.receive()
		if buff == '':
			# end connection
			self.pollend()
			return
		
		if self.state == 2: # read auth response
			if buff is None or len(buff) != 2:
				return None
			version, method = struct.unpack('!BB', buff[:2])
			if version != 0x05 or method == 0xff:
				self.pollend()
			self.state = 3
			gajim.idlequeue.plug_idle(self, True, False)
		
		elif self.state == 4: # get approve of our request
			if buff == None:
				return None
			sub_buff = buff[:4]
			if len(sub_buff) < 4:
				return None
			version, command, rsvd, address_type = struct.unpack('!BBBB', buff[:4])
			addrlen, address, port = 0, 0, 0
			if address_type == 0x03:
				addrlen = ord(buff[4])
				address = struct.unpack('!%ds' % addrlen, buff[5:addrlen + 5])
				portlen = len(buff[addrlen + 5:])
				if portlen == 1: 
					port, = struct.unpack('!B', buff[addrlen + 5])
				elif portlen > 2:
					port, = struct.unpack('!H', buff[addrlen + 5:])
			self.disconnect()
			self.on_success()
		
	
	def do_connect(self):
		try:
			self._sock.connect((self.host, self.port))
			self._sock.setblocking(False)
			self._send=self._sock.send
			self._recv=self._sock.recv
		except Exception, ee:
			(errnum, errstr) = ee
			if errnum == 111:
				self.on_failure()
				return None
			# win32 needs this
			elif errnum != 10056 or self.state != 0:
				return None
			else: # socket is already connected
				self._sock.setblocking(False)
				self._send=self._sock.send
				self._recv=self._sock.recv
		self.buff = ''
		self.state = 1 # connected
		self.idlequeue.plug_idle(self, True, False)
		return 
		
