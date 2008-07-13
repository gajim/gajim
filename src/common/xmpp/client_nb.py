##   client_nb.py
##	   based on client.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##	   modified by Dimitur Kirov <dkirov@gmail.com>
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

# $Id: client.py,v 1.52 2006/01/02 19:40:55 normanr Exp $

'''
Provides Client classes implementations as examples of xmpppy structures usage.
These classes can be used for simple applications "AS IS" though.
'''

import socket

import transports_nb, tls_nb, dispatcher_nb, auth_nb, roster_nb, protocol, bosh
from client import *

import logging
log = logging.getLogger('gajim.c.x.client_nb')


class NBCommonClient:
	''' Base for Client and Component classes.'''
	def __init__(self, domain, idlequeue, caller=None):
		
		''' Caches connection data:
		:param domain: domain - for to: attribute (from account info)
		:param idlequeue: processing idlequeue
		:param port: port of listening XMPP server
		:param caller: calling object - it has to implement certain methods (necessary?)
			
		'''
		self.Namespace = protocol.NS_CLIENT
		self.defaultNamespace = self.Namespace
		
		self.idlequeue = idlequeue
		self.disconnect_handlers = []

		self.Server = domain
		
		# caller is who initiated this client, it is needed to register the EventDispatcher
		self._caller = caller
		self._owner = self
		self._registered_name = None
		self.connected = ''
		self._component=0
		self.socket = None
		self.on_connect = None
		self.on_proxy_failure = None
		self.on_connect_failure = None
		self.proxy = None
		
	
	def on_disconnect(self):
		'''
		Called on disconnection - when connect failure occurs on running connection
		(after stream is successfully opened).
		Calls disconnect handlers and cleans things up.
		'''
		
		self.connected=''
		log.debug('Client disconnected..')
		for i in reversed(self.disconnect_handlers):
			log.debug('Calling disconnect handler %s' % i)
			i()
		if self.__dict__.has_key('NonBlockingRoster'):
			self.NonBlockingRoster.PlugOut()
		if self.__dict__.has_key('NonBlockingBind'):
			self.NonBlockingBind.PlugOut()
		if self.__dict__.has_key('NonBlockingNonSASL'):
			self.NonBlockingNonSASL.PlugOut()
		if self.__dict__.has_key('SASL'):
			self.SASL.PlugOut()
		if self.__dict__.has_key('NonBlockingTLS'):
			self.NonBlockingTLS.PlugOut()
		if self.__dict__.has_key('NBHTTPProxySocket'):
			self.NBHTTPPROXYsocket.PlugOut()
		if self.__dict__.has_key('NBSOCKS5ProxySocket'):
			self.NBSOCKS5PROXYsocket.PlugOut()
		if self.__dict__.has_key('NonBlockingTCP'):
			self.NonBlockingTCP.PlugOut()
		if self.__dict__.has_key('NonBlockingHTTP'):
			self.NonBlockingHTTP.PlugOut()
		if self.__dict__.has_key('NonBlockingBOSH'):
			self.NonBlockingBOSH.PlugOut()


	def connect(self, on_connect, on_connect_failure, hostname=None, port=5222, 
		on_proxy_failure=None, proxy=None, secure=None):
		''' 
		Open XMPP connection (open XML streams in both directions).
		:param hostname: hostname of XMPP server from SRV request 
		:param port: port number of XMPP server
		:param on_connect: called after stream is successfully opened
		:param on_connect_failure: called when error occures during connection
		:param on_proxy_failure: called if error occurres during TCP connection to
			proxy server or during connection to the proxy
		:param proxy: dictionary with proxy data. It should contain at least values
			for keys 'host' and 'port' - connection details for proxy server and
			optionally keys 'user' and 'pass' as proxy credentials
		:param secure:
		'''
		self.on_connect = on_connect
		self.on_connect_failure=on_connect_failure
		self.on_proxy_failure = on_proxy_failure
		self._secure = secure
		self.Connection = None
		self.Port = port


			
			

	def _resolve_hostname(self, hostname, port, on_success, on_failure):
		''' wrapper of getaddinfo call. FIXME: getaddinfo blocks'''
		try:
			self.ip_addresses = socket.getaddrinfo(hostname,port,
				socket.AF_UNSPEC,socket.SOCK_STREAM)
		except socket.gaierror, (errnum, errstr):
			on_failure(err_message='Lookup failure for %s:%s - %s %s' % 
				 (self.Server, self.Port, errnum, errstr))
		else:
			on_success()
		
		
	
	def _try_next_ip(self, err_message=None):
		'''iterates over IP addresses from getaddinfo'''
		if err_message:
			log.debug('While looping over DNS A records: %s' % connect)
		if self.ip_addresses == []:
			self._on_tcp_failure(err_message='Run out of hosts for name %s:%s' % 
				(self.Server, self.Port))
		else:
                        self.current_ip = self.ip_addresses.pop(0)
                        self.socket.connect(
				conn_5tuple=self.current_ip,
				on_connect=lambda: self._xmpp_connect(socket_type='tcp'),
				on_connect_failure=self._try_next_ip)


	def incoming_stream_version(self):
		''' gets version of xml stream'''
		if self.Dispatcher.Stream._document_attrs.has_key('version'):
			return self.Dispatcher.Stream._document_attrs['version']
		else:
			return None

	def _xmpp_connect(self, socket_type):
		self.connected = socket_type
		self._xmpp_connect_machine()


	def _xmpp_connect_machine(self, mode=None, data=None):
		'''
		Finite automaton called after TCP connecting. Takes care of stream opening
		and features tag handling. Calls _on_stream_start when stream is 
		started, and _on_connect_failure on failure.
		'''
		#FIXME: use RegisterHandlerOnce instead of onreceive
		log.info('-------------xmpp_connect_machine() >> mode: %s, data: %s' % (mode,str(data)[:20] ))

		def on_next_receive(mode):
			log.info('setting %s on next receive' % mode)
			if mode is None:
				self.onreceive(None)
			else:
				self.onreceive(lambda _data:self._xmpp_connect_machine(mode, _data))

		if not mode:
			# starting state
			d=dispatcher_nb.Dispatcher().PlugIn(self)
			on_next_receive('RECEIVE_DOCUMENT_ATTRIBUTES')

		elif mode == 'FAILURE':
			self._on_connect_failure(err_message='During XMPP connect: %s' % data)

		elif mode == 'RECEIVE_DOCUMENT_ATTRIBUTES':
			if data:
				self.Dispatcher.ProcessNonBlocking(data)
			if not hasattr(self, 'Dispatcher') or \
				self.Dispatcher.Stream._document_attrs is None:
				self._xmpp_connect_machine(
					mode='FAILURE',
					data='Error on stream open')
			if self.incoming_stream_version() == '1.0':
				if not self.Dispatcher.Stream.features: 
					on_next_receive('RECEIVE_STREAM_FEATURES')
				else:
					log.info('got STREAM FEATURES in first recv')
					self._xmpp_connect_machine(mode='STREAM_STARTED')

			else:
				log.info('incoming stream version less than 1.0')
				self._xmpp_connect_machine(mode='STREAM_STARTED')

		elif mode == 'RECEIVE_STREAM_FEATURES':
			if data:
				# sometimes <features> are received together with document
				# attributes and sometimes on next receive...
				self.Dispatcher.ProcessNonBlocking(data)
			if not self.Dispatcher.Stream.features: 
				self._xmpp_connect_machine(
					mode='FAILURE',
					data='Missing <features> in 1.0 stream')
			else:
				log.info('got STREAM FEATURES in second recv')
				self._xmpp_connect_machine(mode='STREAM_STARTED')

		elif mode == 'STREAM_STARTED':
			self._on_stream_start()

	def _on_stream_start(self):
		'''Called when stream is opened. To be overriden in derived classes.'''

	def _on_connect_failure(self, retry=None, err_message=None): 
		self.connected = None
		if err_message:
			log.debug('While connecting: %s' % err_message)
		if self.socket:
			self.socket.disconnect()
		self.on_connect_failure(retry)

	def _on_connect(self):
		self.onreceive(None)
		self.on_connect(self, self.connected)

	def raise_event(self, event_type, data):
		log.info('raising event from transport: :::::%s::::\n_____________\n%s\n_____________\n' % (event_type,data))
		if hasattr(self, 'Dispatcher'):
			self.Dispatcher.Event('', event_type, data)
		
	
	# moved from client.CommonClient:
	def RegisterDisconnectHandler(self,handler):
		""" Register handler that will be called on disconnect."""
		self.disconnect_handlers.append(handler)

	def UnregisterDisconnectHandler(self,handler):
		""" Unregister handler that is called on disconnect."""
		self.disconnect_handlers.remove(handler)

	def DisconnectHandler(self):
		""" Default disconnect handler. Just raises an IOError.
			If you choosed to use this class in your production client,
			override this method or at least unregister it. """
		raise IOError('Disconnected from server.')

	def get_connect_type(self):
		""" Returns connection state. F.e.: None / 'tls' / 'tcp+non_sasl' . """
		return self.connected

	def get_peerhost(self):
		''' get the ip address of the account, from which is made connection 
		to the server , (e.g. me).
		We will create listening socket on the same ip '''
		# FIXME: tuple (ip, port) is expected (and checked for) but port num is useless
		if hasattr(self, 'socket'):
			return self.socket.peerhost


	def auth(self, user, password, resource = '', sasl = 1, on_auth = None):
		''' Authenticate connnection and bind resource. If resource is not provided
			random one or library name used. '''
		self._User, self._Password, self._Resource, self._sasl = user, password, resource, sasl
		self.on_auth = on_auth
		self._on_doc_attrs()
		return
	
	def _on_old_auth(self, res):
		if res:
			self.connected += '+old_auth'
			self.on_auth(self, 'old_auth')
		else:
			self.on_auth(self, None)

	def _on_doc_attrs(self):
		if self._sasl: 
			auth_nb.SASL(self._User, self._Password, self._on_start_sasl).PlugIn(self)
		if not self._sasl or self.SASL.startsasl == 'not-supported':
			if not self._Resource: 
				self._Resource = 'xmpppy'
			auth_nb.NonBlockingNonSASL(self._User, self._Password, self._Resource, self._on_old_auth).PlugIn(self)
			return
		self.onreceive(self._on_start_sasl)
		self.SASL.auth()
		return True
		
	def _on_start_sasl(self, data=None):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if not self.__dict__.has_key('SASL'): 
			# SASL is pluged out, possible disconnect 
			return
		if self.SASL.startsasl == 'in-process': 
			return
		self.onreceive(None)
		if self.SASL.startsasl == 'failure': 
			# wrong user/pass, stop auth
			self.connected = None
			self._on_sasl_auth(None)
			self.SASL.PlugOut()
		elif self.SASL.startsasl == 'success':
			auth_nb.NonBlockingBind().PlugIn(self)
			self.onreceive(self._on_auth_bind)
		return True
		
	def _on_auth_bind(self, data):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if self.NonBlockingBind.bound is None: 
			return
		self.NonBlockingBind.NonBlockingBind(self._Resource, self._on_sasl_auth)
		return True
	
	def _on_sasl_auth(self, res):
		self.onreceive(None)
		if res:
			self.connected += '+sasl'
			self.on_auth(self, 'sasl')
		else:
			self.on_auth(self, None)


	def initRoster(self):
		''' Plug in the roster. '''
		if not self.__dict__.has_key('NonBlockingRoster'): 
			roster_nb.NonBlockingRoster().PlugIn(self)

	def getRoster(self, on_ready = None):
		''' Return the Roster instance, previously plugging it in and
			requesting roster from server if needed. '''
		if self.__dict__.has_key('NonBlockingRoster'):
			return self.NonBlockingRoster.getRoster(on_ready)
		return None

	def sendPresence(self, jid=None, typ=None, requestRoster=0):
		''' Send some specific presence state.
			Can also request roster from server if according agrument is set.'''
		if requestRoster: roster_nb.NonBlockingRoster().PlugIn(self)
		self.send(dispatcher_nb.Presence(to=jid, typ=typ))


	
class NonBlockingClient(NBCommonClient):
	''' Example client class, based on CommonClient. '''

	def __init__(self, domain, idlequeue, caller=None):
		NBCommonClient.__init__(self, domain, idlequeue, caller)
		self.protocol_type = 'XMPP'

	def connect(self, on_connect, on_connect_failure, hostname=None, port=5222, 
		on_proxy_failure=None, proxy=None, secure=None):

		NBCommonClient.connect(self, on_connect, on_connect_failure, hostname, port,
			on_proxy_failure, proxy, secure)

		if hostname:
			xmpp_hostname = hostname
		else:
			xmpp_hostname = self.Server

		if proxy:
			# with proxies, client connects to proxy instead of directly to
			# XMPP server ((hostname, port))
			# tcp_host is hostname of machine used for socket connection
			# (DNS request will be done for this hostname)
			tcp_host, tcp_port, proxy_user, proxy_pass = \
				transports_nb.get_proxy_data_from_dict(proxy)

			self._on_tcp_failure = self.on_proxy_failure
		
			if proxy['type'] == 'bosh':
				self.socket = bosh.NonBlockingBOSH(
						on_disconnect=self.on_disconnect,
						raise_event = self.raise_event,
						idlequeue = self.idlequeue,
						xmpp_server=(xmpp_hostname, self.Port),
						domain = self.Server,
						bosh_dict = proxy)
				self.protocol_type = 'BOSH'

			else:
				if proxy['type'] == 'socks5':
					proxy_class = transports_nb.NBSOCKS5ProxySocket
				elif proxy['type'] == 'http':
					proxy_class = transports_nb.NBHTTPProxySocket
				self.socket = proxy_class(
					on_disconnect=self.on_disconnect,
					raise_event = self.raise_event,
					idlequeue = self.idlequeue,
					proxy_creds=(proxy_user, proxy_pass),
					xmpp_server=(xmpp_hostname, self.Port))
		else: 
			self._on_tcp_failure = self._on_connect_failure
			tcp_host=xmpp_hostname
			tcp_port=self.Port
			self.socket = transports_nb.NonBlockingTCP(
					raise_event = self.raise_event,
					idlequeue = self.idlequeue,
					on_disconnect = self.on_disconnect)

		self.socket.PlugIn(self)

		self._resolve_hostname(
			hostname=tcp_host,
			port=tcp_port,
			on_success=self._try_next_ip,
			on_failure=self._on_tcp_failure)




	def _on_stream_start(self):
		'''
		Called after XMPP stream is opened.
		In pure XMPP client, TLS negotiation may follow after esabilishing a stream.
		'''
		self.onreceive(None)
		if self.connected == 'tcp':
			if not self.connected or not self._secure:
				# if we are disconnected or TLS/SSL is not desired, return
				self._on_connect()
				return 
			if not self.Dispatcher.Stream.features.getTag('starttls'): 
				# if server doesn't advertise TLS in init response
				self._on_connect()
				return 
			if self.incoming_stream_version() != '1.0':
				self._on_connect()
				return
			# otherwise start TLS 	
			tls_nb.NonBlockingTLS().PlugIn(
				self,
				on_tls_success=lambda: self._xmpp_connect(socket_type='tls'),
				on_tls_failure=self._on_connect_failure)
		elif self.connected == 'tls':
			self._on_connect()

		

