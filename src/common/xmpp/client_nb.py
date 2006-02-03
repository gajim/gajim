##   client_nb.py
##       based on client.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##       modified by Dimitur Kirov <dkirov@gmail.com>
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
Provides PlugIn class functionality to develop extentions for xmpppy.
Also provides Client and Component classes implementations as the
examples of xmpppy structures usage.
These classes can be used for simple applications "AS IS" though.
'''

import socket
import debug

import transports_nb, dispatcher_nb, auth_nb, roster_nb
from client import *

class NBCommonClient(CommonClient):
	''' Base for Client and Component classes.'''
	def __init__(self, server, port=5222, debug=['always', 'nodebuilder'], caller=None, 
		on_connect=None, on_connect_failure=None):
		''' Caches server name and (optionally) port to connect to. "debug" parameter specifies
			the debug IDs that will go into debug output. You can either specifiy an "include"
			or "exclude" list. The latter is done via adding "always" pseudo-ID to the list.
			Full list: ['nodebuilder', 'dispatcher', 'gen_auth', 'SASL_auth', 'bind', 'socket', 
			 'CONNECTproxy', 'TLS', 'roster', 'browser', 'ibb'] . '''
		
		if self.__class__.__name__ == 'NonBlockingClient': 
			self.Namespace, self.DBG = 'jabber:client', DBG_CLIENT
		elif self.__class__.__name__ == 'NBCommonClient': 
			self.Namespace, self.DBG = dispatcher_nb.NS_COMPONENT_ACCEPT, DBG_COMPONENT
		
		self.defaultNamespace = self.Namespace
		self.disconnect_handlers = []
		self.Server = server
		self.Port = port
		
		# Who initiated this client
		# Used to register the EventDispatcher
		self._caller = caller
		if debug and type(debug) != list: 
			debug = ['always', 'nodebuilder']
		self._DEBUG = Debug.Debug(debug)
		self.DEBUG = self._DEBUG.Show
		self.debug_flags = self._DEBUG.debug_flags
		self.debug_flags.append(self.DBG)
		self._owner = self
		self._registered_name = None
		self.connected = ''
		self._component=0
		self.idlequeue = None
		self.socket = None
		self.on_connect = on_connect
		self.on_connect_failure = on_connect_failure
		#~ self.RegisterDisconnectHandler(self.DisconnectHandler)
		
	def set_idlequeue(self, idlequeue):
		self.idlequeue = idlequeue
		
	def disconnected(self):
		''' Called on disconnection. Calls disconnect handlers and cleans things up. '''
		self.connected=''
		self.DEBUG(self.DBG,'Disconnect detected','stop')
		self.disconnect_handlers.reverse()
		for i in self.disconnect_handlers: 
			i()
		self.disconnect_handlers.reverse()
		if self.__dict__.has_key('NonBlockingTLS'): 
			self.NonBlockingTLS.PlugOut()
		
	def reconnectAndReauth(self):
		''' Example of reconnection method. In fact, it can be used to batch connection and auth as well. '''
		handlerssave=self.Dispatcher.dumpHandlers()
		self.Dispatcher.PlugOut()
		if self.__dict__.has_key('NonBlockingNonSASL'): 
			self.NonBlockingNonSASL.PlugOut()
		if self.__dict__.has_key('SASL'): 
			self.SASL.PlugOut()
		if self.__dict__.has_key('NonBlockingTLS'): 
			self.NonBlockingTLS.PlugOut()
		if self.__dict__.has_key('NBHTTPPROXYsocket'): 
			self.NBHTTPPROXYsocket.PlugOut()
		if self.__dict__.has_key('NonBlockingTcp'): 
			self.NonBlockingTcp.PlugOut()
		if not self.connect(server=self._Server, proxy=self._Proxy): 
			return
		if not self.auth(self._User, self._Password, self._Resource): 
			return
		self.Dispatcher.restoreHandlers(handlerssave)
		return self.connected

	def connect(self,server=None,proxy=None, ssl=None, on_stream_start = None):
		''' Make a tcp/ip connection, protect it with tls/ssl if possible and start XMPP stream. '''
		if not server: 
			server = (self.Server, self.Port)
		self._Server,  self._Proxy, self._Ssl = server ,  proxy, ssl
		self.on_stream_start = on_stream_start
		if proxy: 
			self.socket = transports_nb.NBHTTPPROXYsocket(self._on_connected, 
				self._on_connected_failure, proxy, server)
		else: 
			self.connected = 'tcp'
			self.socket = transports_nb.NonBlockingTcp(self._on_connected, 
				self._on_connected_failure, server)
		self.socket.PlugIn(self)
		return True
	
	def get_attrs(self, on_stream_start):
		self.on_stream_start = on_stream_start
		self.onreceive(self._on_receive_document_attrs)

	def _on_connected_failure(self): 
		if self.socket:
			self.socket.PlugOut()
		if self.on_connect_failure:
			self.on_connect_failure()

	def _on_connected(self):
		self.connected = 'tcp'
		if self._Ssl or self.Connection.getPort() in (5223, 443):
			try:
				transports_nb.NonBlockingTLS().PlugIn(self, now=1)
				self.connected = 'ssl'
			except socket.sslerror:
				return
		self.onreceive(self._on_receive_document_attrs)
		dispatcher_nb.Dispatcher().PlugIn(self)
		
	def _on_receive_document_attrs(self, data):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if not hasattr(self, 'Dispatcher') or \
			self.Dispatcher.Stream._document_attrs is None:
			return
		self.onreceive(None)
		if self.Dispatcher.Stream._document_attrs.has_key('version') and \
			self.Dispatcher.Stream._document_attrs['version'] == '1.0':
				self.onreceive(self._on_receive_stream_features)
				return
		if self.on_stream_start:
			self.on_stream_start()
			self.on_stream_start = None
		return True
	
	def _on_receive_stream_features(self, data):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if not self.Dispatcher.Stream.features: 
			return
			# pass  # If we get version 1.0 stream the features tag MUST BE presented
		self.onreceive(None)
		if self.on_stream_start:
			self.on_stream_start()
			self.on_stream_start = None
		return True
	
class NonBlockingClient(NBCommonClient):
	''' Example client class, based on CommonClient. '''
	def connect(self,server=None,proxy=None,secure=None,use_srv=True):
		''' Connect to jabber server. If you want to specify different ip/port to connect to you can
			pass it as tuple as first parameter. If there is HTTP proxy between you and server 
			specify it's address and credentials (if needed) in the second argument.
			If you want ssl/tls support to be discovered and enable automatically - leave third argument as None. (ssl will be autodetected only if port is 5223 or 443)
			If you want to force SSL start (i.e. if port 5223 or 443 is remapped to some non-standard port) then set it to 1.
			If you want to disable tls/ssl support completely, set it to 0.
			Example: connect(('192.168.5.5',5222),{'host':'proxy.my.net','port':8080,'user':'me','password':'secret'})
			Returns '' or 'tcp' or 'tls', depending on the result.'''
		self.__secure = secure
		self.Connection = None
		NBCommonClient.connect(self, server = server, proxy = proxy, 
			on_stream_start = self._on_tcp_stream_start) 
		return self.connected
	
	
	def _is_connected(self):
		self.onreceive(None)
		if self.on_connect:
			self.on_connect(self, self.connected)
			self.on_connect = None
	
	def _on_tcp_stream_start(self):
		if not self.connected or self.__secure is not None and not self.__secure:
			self._is_connected()
			return True
		self.isplugged = True
		self.onreceive(None)
		transports_nb.NonBlockingTLS().PlugIn(self)
		if not self.Dispatcher.Stream._document_attrs.has_key('version') or \
			not self.Dispatcher.Stream._document_attrs['version']=='1.0': 
			self._is_connected()
			return
		if not self.Dispatcher.Stream.features.getTag('starttls'): 
			self._is_connected()
			return 
		self.onreceive(self._on_receive_starttls)

	def _on_receive_starttls(self, data):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if not self.NonBlockingTLS.starttls:
			return
		self.onreceive(None)
		if not hasattr(self, 'NonBlockingTLS') or self.NonBlockingTLS.starttls != 'success': 
			self.event('tls_failed')
			self._is_connected()
			return
		self.connected = 'tls'
		self.onreceive(None)
		self._is_connected()
		return True
	
	def auth(self, user, password, resource = '', sasl = 1, on_auth = None):
		''' Authenticate connnection and bind resource. If resource is not provided
			random one or library name used. '''
		self._User, self._Password, self._Resource, self._sasl = user, password, resource, sasl
		self.on_auth = on_auth
		self.get_attrs(self._on_doc_attrs)
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

class Component(NBCommonClient):
	''' Component class. The only difference from CommonClient is ability to perform component authentication. '''
	def __init__(self, server, port=5347, typ=None, debug=['always', 'nodebuilder'],
		domains=None, component=0, on_connect = None, on_connect_failure = None):
		''' Init function for Components.
			As components use a different auth mechanism which includes the namespace of the component.
			Jabberd1.4 and Ejabberd use the default namespace then for all client messages.
			Jabberd2 uses jabber:client.
			'server' argument is a server name that you are connecting to (f.e. "localhost").
			'port' can be specified if 'server' resolves to correct IP. If it is not then you'll need to specify IP 
			and port while calling "connect()".'''
		NBCommonClient.__init__(self, server, port=port, debug=debug)
		self.typ = typ
		self.component=component
		if domains:
			self.domains=domains
		else:
			self.domains=[server]
		self.on_connect_component = on_connect
		self.on_connect_failure = on_connect_failure
	
	def connect(self, server=None, proxy=None):
		''' This will connect to the server, and if the features tag is found then set
			the namespace to be jabber:client as that is required for jabberd2.
			'server' and 'proxy' arguments have the same meaning as in xmpp.Client.connect() '''
		if self.component:
			self.Namespace=auth.NS_COMPONENT_1
			self.Server=server[0]
		NBCommonClient.connect(self, server=server, proxy=proxy, 
			on_connect = self._on_connect, on_connect_failure = self.on_connect_failure)
		
	def _on_connect(self):
		if self.typ=='jabberd2' or not self.typ and self.Dispatcher.Stream.features != None:
				self.defaultNamespace=auth.NS_CLIENT
				self.Dispatcher.RegisterNamespace(self.defaultNamespace)
				self.Dispatcher.RegisterProtocol('iq',dispatcher.Iq)
				self.Dispatcher.RegisterProtocol('message',dispatcher_nb.Message)
				self.Dispatcher.RegisterProtocol('presence',dispatcher_nb.Presence)
		self.on_connect(self.connected)

	def auth(self, name, password, dup=None, sasl=0):
		''' Authenticate component "name" with password "password".'''
		self._User, self._Password, self._Resource=name, password,''
		try:
			if self.component: 
				sasl=1
			if sasl: 
				auth.SASL(name,password).PlugIn(self)
			if not sasl or self.SASL.startsasl=='not-supported':
				if auth.NonSASL(name,password,'').PlugIn(self):
					self.connected+='+old_auth'
					return 'old_auth'
				return
			self.SASL.auth()
			self.onreceive(self._on_auth_component)
		except:
			self.DEBUG(self.DBG,"Failed to authenticate %s" % name,'error')
		
	def _on_auth_component(self, data):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if self.SASL.startsasl == 'in-process': 
			return
		if self.SASL.startsasl =='success':
			if self.component:
				self._component = self.component
				auth.NBComponentBind().PlugIn(self)
				self.onreceive(_on_component_bind)
			self.connected += '+sasl'
		else:
			raise auth.NotAuthorized(self.SASL.startsasl)
			
	def _on_component_bind(self, data):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if self.NBComponentBind.bound is None: 
			return
		
		for domain in self.domains:
			self.NBComponentBind.Bind(domain, _on_component_bound)
	
	def _on_component_bound(self, resp):
		self.NBComponentBind.PlugOut()
		
