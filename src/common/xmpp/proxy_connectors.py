##   proxy_connectors.py
##       based on transports_nb.py
##  
##   Copyright (C) 2003-2004 Alexey "Snake" Nezhdanov
##       modified by Dimitur Kirov <dkirov@gmail.com>
##       modified by Tomas Karasek <tom.to.the.k@gmail.com>
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.
'''
Module containing classes for proxy connecting. So far its HTTP CONNECT
and SOCKS5 proxy. 
Authentication to NTLM (Microsoft implementation) proxies can be next.
'''

import struct, socket, base64
import logging
log = logging.getLogger('gajim.c.x.proxy_connectors')

class ProxyConnector:
	'''
	Interface for proxy-connecting object - when tunnneling XMPP over proxies,
	some connecting process usually has to be done before opening stream.
	Proxy connectors are used right after TCP connection is estabilished.
	'''
	def __init__(self, send_method, onreceive, old_on_receive, on_success,
		on_failure, xmpp_server, proxy_creds=(None,None)):
		'''
		Creates proxy connector, starts connecting immediately and gives control
		back to transport afterwards.

		:param send_method: transport send method
		:param onreceive: method to set on_receive callbacks
		:param old_on_receive: on_receive callback that should be set when 
			proxy connection was successful
		:param on_success: called after proxy connection was successfully opened
		:param on_failure: called when errors occured while connecting
		:param xmpp_server: tuple of (hostname, port)
		:param proxy_creds: tuple of (proxy_user, proxy_credentials)
		'''
		self.send = send_method
		self.onreceive = onreceive
		self.old_on_receive = old_on_receive
		self.on_success = on_success
		self.on_failure = on_failure
		self.xmpp_server = xmpp_server
		self.proxy_user, self.proxy_pass = proxy_creds
		self.old_on_receive = old_on_receive

		self.start_connecting()

	def start_connecting(self):
		raise NotImplementedError

	def connecting_over(self):
		self.onreceive(self.old_on_receive)
		self.on_success()
		
class HTTPCONNECTConnector(ProxyConnector):
	def start_connecting(self):
		'''
		Connects to proxy, supplies login and password to it
		(if were specified while creating instance). Instructs proxy to make
		connection to the target server.
		'''
		log.info('Proxy server contacted, performing authentification')
		connector = ['CONNECT %s:%s HTTP/1.1' % self.xmpp_server,
			'Proxy-Connection: Keep-Alive',
			'Pragma: no-cache',
			'Host: %s:%s' % self.xmpp_server,
			'User-Agent: Gajim']
		if self.proxy_user and self.proxy_pass:
			credentials = '%s:%s' % (self.proxy_user, self.proxy_pass)
			credentials = base64.encodestring(credentials).strip()
			connector.append('Proxy-Authorization: Basic '+credentials)
		connector.append('\r\n')
		self.onreceive(self._on_headers_sent)
		self.send('\r\n'.join(connector))
		
	def _on_headers_sent(self, reply):
		if reply is None:
			return
		self.reply = reply.replace('\r', '')
		try: 
			proto, code, desc = reply.split('\n')[0].split(' ', 2)
		except: 
			log.error("_on_headers_sent:", exc_info=True)
			#traceback.print_exc()
			self.on_failure('Invalid proxy reply')
			return
		if code <> '200':
			log.error('Invalid proxy reply: %s %s %s' % (proto, code, desc))
			self.on_failure('Invalid proxy reply')
			return
		if len(reply) != 2:
			pass
		self.connecting_over()


class SOCKS5Connector(ProxyConnector):
	'''
	SOCKS5 proxy connection class. Allows to use SOCKS5 proxies with
	(optionally) simple authentication (only USERNAME/PASSWORD auth). 
	'''
	def start_connecting(self):
		log.info('Proxy server contacted, performing authentification')
		if self.proxy_user and self.proxy_pass:
			to_send = '\x05\x02\x00\x02'
		else:
			to_send = '\x05\x01\x00'
		self.onreceive(self._on_greeting_sent)
		self.send(to_send)

	def _on_greeting_sent(self, reply):
		if reply is None:
			return
		if len(reply) != 2:
			self.on_failure('Invalid proxy reply')
			return
		if reply[0] != '\x05':
			log.info('Invalid proxy reply')
			self.on_failure('Invalid proxy reply')
			return
		if reply[1] == '\x00':
			return self._on_proxy_auth('\x01\x00')
		elif reply[1] == '\x02':
			to_send = '\x01' + chr(len(self.proxy_user)) + self.proxy_user +\
				chr(len(self.proxy_pass)) + self.proxy_pass
			self.onreceive(self._on_proxy_auth)
			self.send(to_send)
		else:
			if reply[1] == '\xff':
				log.error('Authentification to proxy impossible: no acceptable '
					'auth method')
				self.on_failure('Authentification to proxy impossible: no '
					'acceptable authentification method')
				return
			log.error('Invalid proxy reply')
			self.on_failure('Invalid proxy reply')
			return

	def _on_proxy_auth(self, reply):
		if reply is None:
			return
		if len(reply) != 2:
			log.error('Invalid proxy reply')
			self.on_failure('Invalid proxy reply')
			return
		if reply[0] != '\x01':
			log.error('Invalid proxy reply')
			self.on_failure('Invalid proxy reply')
			return
		if reply[1] != '\x00':
			log.error('Authentification to proxy failed')
			self.on_failure('Authentification to proxy failed')
			return
		log.info('Authentification successfull. Jabber server contacted.')
		# Request connection
		req = "\x05\x01\x00"
		# If the given destination address is an IP address, we'll
		# use the IPv4 address request even if remote resolving was specified.
		try:
			self.ipaddr = socket.inet_aton(self.xmpp_server[0])
			req = req + "\x01" + self.ipaddr
		except socket.error:
			# Well it's not an IP number,  so it's probably a DNS name.
#			if self.__proxy[3]==True:
			# Resolve remotely
			self.ipaddr = None
			req = req + "\x03" + chr(len(self.xmpp_server[0])) + self.xmpp_server[0]
#			else:
#				# Resolve locally
#				self.ipaddr = socket.inet_aton(socket.gethostbyname(self.xmpp_server[0]))
#				req = req + "\x01" + ipaddr
		req = req + struct.pack(">H", self.xmpp_server[1])
		self.onreceive(self._on_req_sent)
		self.send(req)

	def _on_req_sent(self, reply):
		if reply is None:
			return
		if len(reply) < 10:
			log.error('Invalid proxy reply')
			self.on_failure('Invalid proxy reply')
			return
		if reply[0] != '\x05':
			log.error('Invalid proxy reply')
			self.on_failure('Invalid proxy reply')
			return
		if reply[1] != "\x00":
			# Connection failed
			if ord(reply[1])<9:
				errors = ['general SOCKS server failure',
					'connection not allowed by ruleset',
					'Network unreachable',
					'Host unreachable',
					'Connection refused',
					'TTL expired',
					'Command not supported',
					'Address type not supported'
				]
				txt = errors[ord(reply[1])-1]
			else:
				txt = 'Invalid proxy reply'
			log.error(txt)
			self.on_failure(txt)
			return
		# Get the bound address/port
		elif reply[3] == "\x01":
			begin, end = 3, 7
		elif reply[3] == "\x03":
			begin, end = 4, 4 + reply[4]
		else:
			log.error('Invalid proxy reply')
			self.on_failure('Invalid proxy reply')
			return
		self.connecting_over()

# vim: se ts=3:
