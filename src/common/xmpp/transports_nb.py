##   transports_nb.py
##       based on transports.py
##  
##   Copyright (C) 2003-2004 Alexey "Snake" Nezhdanov
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

import socket,select,base64,dispatcher_nb
from simplexml import ustr
from client import PlugIn
from idlequeue import IdleObject
from protocol import *
from transports import * 

import sys
import os
import errno

# timeout to connect to the server socket, it doesn't include auth 
CONNECT_TIMEOUT_SECONDS = 30

# how long to wait for a disconnect to complete
DISCONNECT_TIMEOUT_SECONDS = 10

# size of the buffer which reads data from server
# if lower, more stanzas will be fragmented and processed twice
RECV_BUFSIZE = 1048576

class NonBlockingTcp(PlugIn, IdleObject):
	''' This class can be used instead of transports.Tcp in threadless implementations '''
	def __init__(self, on_connect = None, on_connect_failure = None, server=None, use_srv = True):
		''' Cache connection point 'server'. 'server' is the tuple of (host, port)
			absolutely the same as standard tcp socket uses. 
			on_connect - called when we connect to the socket
			on_connect_failure  - called if there was error connecting to socket
			'''
		IdleObject.__init__(self)
		PlugIn.__init__(self)
		self.DBG_LINE='socket'
		self._exported_methods=[self.send, self.disconnect, self.onreceive, self.set_send_timeout, 
			self.start_disconnect, self.set_timeout, self.remove_timeout]
		self._server = server
		self.on_connect  = on_connect
		self.on_connect_failure = on_connect_failure
		self.on_receive = None
		self.on_disconnect = None
		
		#  0 - not connected
		#  1 - connected
		# -1 - about to disconnect (when we wait for final events to complete)
		# -2 - disconnected
		self.state = 0
		
		# queue with messages to be send 
		self.sendqueue = []
		
		# bytes remained from the last send message
		self.sendbuff = ''
		
		# time to wait for SOME stanza to come and then send keepalive
		self.sendtimeout = 0
		
		# in case we want to something different than sending keepalives
		self.on_timeout = None
		
		# writable, readable  -  keep state of the last pluged flags
		# This prevents replug of same object with the same flags
		self.writable = True
		self.readable = False
	
	def plugin(self, owner):
		''' Fire up connection. Return non-empty string on success.
			Also registers self.disconnected method in the owner's dispatcher.
			Called internally. '''
		self.idlequeue = owner.idlequeue
		if not self._server: 
			self._server=(self._owner.Server,5222)
		if self.connect(self._server) is False:
			return False
		return True
		
	def read_timeout(self):
		if self.state == 0:
			self.idlequeue.unplug_idle(self.fd)
			if self.on_connect_failure:
				self.on_connect_failure()
		else:
			if self.on_timeout:
				self.on_timeout()
			self.renew_send_timeout()
		
	def connect(self,server=None, proxy = None, secure = None):
		''' Try to establish connection. Returns non-empty string on success. '''
		if not server:
			server=self._server
		else: 
			self._server = server
		self.state = 0
		try:
			self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			self._sock.setblocking(False)
		except:  
			if self.on_connect_failure:
				self.on_connect_failure()
			return False
		self.fd = self._sock.fileno()
		self.idlequeue.plug_idle(self, True, False)
		self.set_timeout(CONNECT_TIMEOUT_SECONDS)
		self._do_connect()
		return True
	
	def _plug_idle(self):
		readable = self.state != 0
		if self.sendqueue or self.sendbuff:
			writable = True
		else:
			writable = False
		if self.writable != writable or self.readable != readable:
			self.idlequeue.plug_idle(self, writable, readable)
	
	def pollout(self):
		if self.state == 0:
			return self._do_connect()
		return self._do_send()
	
	def plugout(self):
		''' Disconnect from the remote server and unregister self.disconnected method from
			the owner's dispatcher. '''
		self.disconnect()
		self._owner.Connection = None
	
	def pollin(self):
		self._do_receive() 
	
	def pollend(self):
		self.disconnect()
		if self.on_connect_failure:
			self.on_connect_failure()
		self.on_connect_failure = None
		
	def disconnect(self):
		if self.state == -2: # already disconnected
			return
		self.state = -2
		self.sendqueue = None
		self.remove_timeout() 
		self._owner.disconnected()
		self.idlequeue.unplug_idle(self.fd)
		if self.on_disconnect:
			self.on_disconnect()
	
	def end_disconnect(self):
		''' force disconnect only if we are still trying to disconnect '''
		if self.state == -1:
			self.disconnect()
	
	def start_disconnect(self, to_send, on_disconnect):
		self.on_disconnect = on_disconnect
		self.sendqueue = []
		self.send(to_send)
		self.send('</stream:stream>')
		self.state = -1 # about to disconnect
		self.idlequeue.set_alarm(self.end_disconnect, DISCONNECT_TIMEOUT_SECONDS)
	
	def set_timeout(self, timeout):
		if self.state >= 0 and self.fd > 0:
			self.idlequeue.set_read_timeout(self.fd, timeout)
	
	def remove_timeout(self):
		if self.fd:
			self.idlequeue.remove_timeout(self.fd)
	
	def onreceive(self, recv_handler):
		if not recv_handler:
			if hasattr(self._owner, 'Dispatcher'):
				self.on_receive = self._owner.Dispatcher.ProcessNonBlocking
			else:
				self.on_receive = None
			return
		_tmp = self.on_receive
		# make sure this cb is not overriden by recursive calls
		if not recv_handler(None) and _tmp == self.on_receive:
			self.on_receive = recv_handler
		
	def _do_receive(self):
		''' Reads all pending incoming data. Calls owner's disconnected() method if appropriate.'''
		received = ''
		errnum = 0
		try: 
			# get as many bites, as possible, but not more than RECV_BUFSIZE
			received = self._recv(RECV_BUFSIZE)
		except Exception, e:
			if len(e.args)  > 0 and isinstance(e.args[0], int):
				errnum = e[0]
			# "received" will be empty anyhow 
		
		if not received and errnum != 2:
			if errnum != 8: # EOF occurred in violation of protocol
				self.DEBUG('Socket error while receiving data', 'error')
			if self.state >= 0:
				self.disconnect()
			return False
		if self.state < 0:
			return
		# we have received some bites, stop the timeout!
		self.renew_send_timeout()
		if self.on_receive:
			if received.strip():
				self.DEBUG(received,'got')
			if hasattr(self._owner, 'Dispatcher'):
				self._owner.Dispatcher.Event('', DATA_RECEIVED, received)
			self.on_receive(received)
		else:
			# This should never happed, so we need the debug
			self.DEBUG('Unhandled data received: %s' % received,'got')
			self.disconnect()
		return True
	
	def _do_send(self):
		if not self.sendbuff:
			if not self.sendqueue:
				return None # nothing to send
			self.sendbuff = self.sendqueue.pop(0)
			self.sent_data = self.sendbuff
		try:
			send_count = self._send(self.sendbuff)
			if send_count:
				self.sendbuff = self.sendbuff[send_count:]
				if not self.sendbuff and not self.sendqueue:
					if self.state < 0:
						self._on_send()
						self.disconnect()
						return
					# we are not waiting for write 
					self._plug_idle()
				self._on_send()
		except Exception, e:
			if self.state < 0:
				self.disconnect()
				return
			if self._on_send_failure:
				self._on_send_failure()
				return
		return True

	def _do_connect(self):
		if self.state != 0:
			return
		self._sock.setblocking(False)
		errnum = 0
		try:
			self._sock.connect(self._server)
		except socket.error, e:
			errnum = e[0]
		# in progress, or would block
		if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK): 
			return
		# 10056  - already connected, only on win32
		# code 'WS*' is not available on GNU, so we use its numeric value
		elif errnum not in (0, 10056): 
			self.remove_timeout()
			if self.on_connect_failure:
				self.on_connect_failure()
			return
		self.remove_timeout()
		self._owner.Connection=self
		self.state = 1
		
		self._sock.setblocking(False)
		self._send = self._sock.send
		self._recv = self._sock.recv
		self._plug_idle()
		if self.on_connect:
			self.on_connect()
			self.on_connect = None
		return True

	def send(self, raw_data):
		''' Writes raw outgoing data. Blocks until done.
			If supplied data is unicode string, encodes it to utf-8 before send. '''
		if self.state <= 0:
			return
		r = raw_data
		if isinstance(r, unicode): 
			r = r.encode('utf-8')
		elif not isinstance(r, str): 
			r = ustr(r).encode('utf-8')
		self.sendqueue.append(r)
		self._plug_idle()

	def _on_send(self):
		if self.sent_data and self.sent_data.strip():
			self.DEBUG(self.sent_data,'sent')
			if hasattr(self._owner, 'Dispatcher'):
				self._owner.Dispatcher.Event('', DATA_SENT, self.sent_data)
		self.sent_data  = None
	
	def _on_send_failure(self):
		self.DEBUG("Socket error while sending data",'error')
		self._owner.disconnected()
		self.sent_data = None
	
	def set_send_timeout(self, timeout, on_timeout):
		self.sendtimeout = timeout
		if self.sendtimeout > 0:
			self.on_timeout = on_timeout
		else:
			self.on_timeout = None
	
	def renew_send_timeout(self):
		if self.on_timeout and self.sendtimeout > 0:
			self.set_timeout(self.sendtimeout)
		else:
			self.remove_timeout()
	
	def getHost(self):
		''' Return the 'host' value that is connection is [will be] made to.'''
		return self._server[0]
	
	def getPort(self):
		''' Return the 'port' value that is connection is [will be] made to.'''
		return self._server[1]
	
class NonBlockingTLS(PlugIn):
	''' TLS connection used to encrypts already estabilished tcp connection.'''
	def PlugIn(self, owner, now=0, on_tls_start = None):
		''' If the 'now' argument is true then starts using encryption immidiatedly.
			If 'now' in false then starts encryption as soon as TLS feature is
			declared by the server (if it were already declared - it is ok).
		'''
		if owner.__dict__.has_key('NonBlockingTLS'): 
			return  # Already enabled.
		PlugIn.PlugIn(self, owner)
		DBG_LINE='NonBlockingTLS'
		self.on_tls_start = on_tls_start
		if now: 
			res = self._startSSL()
			self.tls_start()
			return res
		if self._owner.Dispatcher.Stream.features:
			try: 
				self.FeaturesHandler(self._owner.Dispatcher, self._owner.Dispatcher.Stream.features)
			except NodeProcessed: 
				pass
		else: 
			self._owner.RegisterHandlerOnce('features',self.FeaturesHandler, xmlns=NS_STREAMS)
		self.starttls = None
		
	def plugout(self,now=0):
		''' Unregisters TLS handler's from owner's dispatcher. Take note that encription
			can not be stopped once started. You can only break the connection and start over.'''
		self._owner.UnregisterHandler('features',self.FeaturesHandler,xmlns=NS_STREAMS)

	def tls_start(self):
		if self.on_tls_start:
			self.on_tls_start()
			self.on_tls_start = None
		
	def FeaturesHandler(self, conn, feats):
		''' Used to analyse server <features/> tag for TLS support.
			If TLS is supported starts the encryption negotiation. Used internally '''
		if not feats.getTag('starttls', namespace=NS_TLS):
			self.DEBUG("TLS unsupported by remote server.", 'warn')
			self.tls_start()
			return
		self.DEBUG("TLS supported by remote server. Requesting TLS start.", 'ok')
		self._owner.RegisterHandlerOnce('proceed', self.StartTLSHandler, xmlns=NS_TLS)
		self._owner.RegisterHandlerOnce('failure', self.StartTLSHandler, xmlns=NS_TLS)
		self._owner.send('<starttls xmlns="%s"/>' % NS_TLS)
		self.tls_start()
		raise NodeProcessed

	def _startSSL(self):
		''' Immidiatedly switch socket to TLS mode. Used internally.'''
		tcpsock=self._owner.Connection
		tcpsock._sock.setblocking(True)
		tcpsock._sslObj    = socket.ssl(tcpsock._sock, None, None)
		tcpsock._sock.setblocking(False)
		tcpsock._sslIssuer = tcpsock._sslObj.issuer()
		tcpsock._sslServer = tcpsock._sslObj.server()
		tcpsock._recv = tcpsock._sslObj.read
		tcpsock._send = tcpsock._sslObj.write
		self.starttls='success'

	def StartTLSHandler(self, conn, starttls):
		''' Handle server reply if TLS is allowed to process. Behaves accordingly.
			Used internally.'''
		if starttls.getNamespace() <> NS_TLS: 
			return
		self.starttls = starttls.getName()
		if self.starttls == 'failure':
			self.DEBUG('Got starttls response: ' + self.starttls,'error')
			return
		self.DEBUG('Got starttls proceed response. Switching to TLS/SSL...','ok')
		self._startSSL()
		self._owner.Dispatcher.PlugOut()
		dispatcher_nb.Dispatcher().PlugIn(self._owner)


class NBHTTPPROXYsocket(NonBlockingTcp):
	''' This class can be used instead of transports.HTTPPROXYsocket
	HTTP (CONNECT) proxy connection class. Uses TCPsocket as the base class
		redefines only connect method. Allows to use HTTP proxies like squid with
		(optionally) simple authentication (using login and password). 
		
	'''
	def __init__(self, on_connect =None, on_connect_failure = None,proxy = None,server = None,use_srv=True):
		''' Caches proxy and target addresses.
			'proxy' argument is a dictionary with mandatory keys 'host' and 'port' (proxy address)
			and optional keys 'user' and 'password' to use for authentication.
			'server' argument is a tuple of host and port - just like TCPsocket uses. '''
		self.on_connect_proxy = on_connect  
		self.on_connect_failure = on_connect_failure
		NonBlockingTcp.__init__(self, self._on_tcp_connect, on_connect_failure, server, use_srv)
		self.DBG_LINE=DBG_CONNECT_PROXY
		self.server = server
		self.proxy=proxy

	def plugin(self, owner):
		''' Starts connection. Used interally. Returns non-empty string on success.'''
		owner.debug_flags.append(DBG_CONNECT_PROXY)
		NonBlockingTcp.plugin(self,owner)

	def connect(self,dupe=None):
		''' Starts connection. Connects to proxy, supplies login and password to it
			(if were specified while creating instance). Instructs proxy to make
			connection to the target server. Returns non-empty sting on success. '''
		NonBlockingTcp.connect(self, (self.proxy['host'], self.proxy['port']))
		
	def _on_tcp_connect(self):
		self.DEBUG('Proxy server contacted, performing authentification','start')
		connector = ['CONNECT %s:%s HTTP/1.0'%self.server,
			'Proxy-Connection: Keep-Alive',
			'Pragma: no-cache',
			'Host: %s:%s'%self.server,
			'User-Agent: HTTPPROXYsocket/v0.1']
		if self.proxy.has_key('user') and self.proxy.has_key('password'):
			credentials = '%s:%s' % ( self.proxy['user'], self.proxy['password'])
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
			raise error('Invalid proxy reply')
		if code <> '200':
			self.DEBUG('Invalid proxy reply: %s %s %s' % (proto, code, desc),'error')
			self._owner.disconnected()
			return
		self.onreceive(self._on_proxy_auth)
	
	def _on_proxy_auth(self, reply):
		if self.reply.find('\n\n') == -1:
			if reply is None:
				return 
			if reply.find('\n\n') == -1:
				self.reply += reply.replace('\r', '')
				return
		self.DEBUG('Authentification successfull. Jabber server contacted.','ok')
		if self.on_connect_proxy:
			self.on_connect_proxy()

	def DEBUG(self, text, severity):
		''' Overwrites DEBUG tag to allow debug output be presented as "CONNECTproxy".'''
		return self._owner.DEBUG(DBG_CONNECT_PROXY, text, severity)
