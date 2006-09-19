##      common/zeroconf/client_zeroconf.py
##
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
## 				2006 Dimitur Kirov <dkirov@gmail.com>
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
from common import gajim
from common.xmpp.idlequeue import IdleObject
from common.xmpp import dispatcher_nb, simplexml
from common.xmpp.client import *
from common.xmpp.simplexml import ustr
from dialogs import BindPortError
from  common.xmpp.protocol import *
import socket
import errno

from common.zeroconf import roster_zeroconf

MAX_BUFF_LEN = 65536
DATA_RECEIVED='DATA RECEIVED'
DATA_SENT='DATA SENT'
TYPE_SERVER, TYPE_CLIENT = range(2)

class ZeroconfListener(IdleObject):
	def __init__(self, port, caller = None):
		''' handle all incomming connections on ('0.0.0.0', port)'''
		self.port = port
		self.queue_idx = -1	
		#~ self.queue = None
		self.started = False
		self._sock = None
		self.fd = -1
		self.caller = caller
		
	def bind(self):
		self._serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		self._serv.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
		# will fail when port as busy, or we don't have rights to bind
		try:
			self._serv.bind(('0.0.0.0', self.port))
		except Exception, e:
			# unable to bind, show error dialog
			return None
		self._serv.listen(socket.SOMAXCONN)
		self._serv.setblocking(False)
		self.fd = self._serv.fileno()
		gajim.idlequeue.plug_idle(self, False, True)
		self.started = True
	
	def pollend(self):
		''' called when we stop listening on (host, port) '''
		self.disconnect()
	
	def pollin(self):
		''' accept a new incomming connection and notify queue'''
		sock = self.accept_conn()
		P2PClient(sock[0], sock[1][0], sock[1][1], self.caller)
	
	def disconnect(self):
		''' free all resources, we are not listening anymore '''
		gajim.idlequeue.remove_timeout(self.fd)
		gajim.idlequeue.unplug_idle(self.fd)
		self.fd = -1
		self.started = False
		try:
			self._serv.close()
		except:
			pass
		#XXX kill all active connection
	
	def accept_conn(self):
		''' accepts a new incomming connection '''
		_sock  = self._serv.accept()
		_sock[0].setblocking(False)
		return _sock



class P2PClient(IdleObject):
	def __init__(self, _sock, host, port, caller):
		self._owner = self
		self.Namespace = 'jabber:client'
		self.defaultNamespace = self.Namespace
		self._component=0
		self._caller = caller
		self.Server = host
		self.DBG = 'client'
		debug = ['always', 'nodebuilder']
		self._DEBUG = Debug.Debug(debug)
		self.DEBUG = self._DEBUG.Show
		self.debug_flags = self._DEBUG.debug_flags
		self.debug_flags.append(self.DBG)
		P2PConnection('', _sock, host, port, caller, self.on_connect)
	
	def on_connect(self, conn):
		self.Connection = conn
		self.Connection.PlugIn(self)
		dispatcher_nb.Dispatcher().PlugIn(self)
		self.RegisterHandler('message', self._messageCB)
	
	def StreamInit(self):
		''' Send an initial stream header. '''
		self.Dispatcher.Stream = simplexml.NodeBuilder()
		self.Dispatcher.Stream._dispatch_depth = 2
		self.Dispatcher.Stream.dispatch = self.Dispatcher.dispatch
		self.Dispatcher.Stream.stream_header_received = self.Dispatcher._check_stream_start
		self.debug_flags.append(simplexml.DBG_NODEBUILDER)
		self.Dispatcher.Stream.DEBUG = self.DEBUG
		self.Dispatcher.Stream.features = None
		self.Dispatcher._metastream = Node('stream:stream')
		self.Dispatcher._metastream.setNamespace(self.Namespace)
		#~ self._metastream.setAttr('version', '1.0')
		self.Dispatcher._metastream.setAttr('xmlns:stream', NS_STREAMS)
		#~ self._metastream.setAttr('to', self._owner.Server)
		self.Dispatcher.send("<?xml version='1.0'?>%s>" % str(self.Dispatcher._metastream)[:-2])
	
	def disconnected(self):
		if self.__dict__.has_key('Dispatcher'):
			self.Dispatcher.PlugOut()
		if self.__dict__.has_key('P2PConnection'):
			self.P2PConnection.PlugOut()
		
	def _on_receive_document_attrs(self, data):
		if data:
			self.Dispatcher.ProcessNonBlocking(data)
		if not hasattr(self, 'Dispatcher') or \
			self.Dispatcher.Stream._document_attrs is None:
			return
		self.onreceive(None)
		if self.Dispatcher.Stream._document_attrs.has_key('version') and \
			self.Dispatcher.Stream._document_attrs['version'] == '1.0':
				#~ self.onreceive(self._on_receive_stream_features)
				#XXX continue with TLS
				return
		self.onreceive(None)
		return True
		
		
	def _messageCB(self, conn, data):
		self._caller._messageCB(self.Server, conn, data)
		
		
class P2PConnection(IdleObject, PlugIn):
	''' class for sending file to socket over socks5 '''
	def __init__(self, sock_hash, _sock, host = None, port = None, caller = None, on_connect = None):
		IdleObject.__init__(self)
		PlugIn.__init__(self)
		self.DBG_LINE='socket'
		self.sendqueue = []
		self.sendbuff = None
		self._sock = _sock
		self.host, self.port = host, port
		self.on_connect = on_connect
		self.writable = False
		self.readable = False
		# waiting for first bytes
		# start waiting for data
		self._registered_name = None
		self._exported_methods=[self.send, self.disconnect, self.onreceive]
		self.on_receive = None
		if _sock:
			self.sock_type = TYPE_SERVER
			self.connected = True
			self.state = 1 
			_sock.setblocking(False)
			self.fd = _sock.fileno()
			self.on_connect(self)
		else:
			self.sock_type = TYPE_CLIENT
			self.connected = False
			self.state = 0
			self.idlequeue.plug_idle(self, True, False)
			self.do_connect()
			
		
		
		
	def plugin(self, owner):
		self.onreceive(owner._on_receive_document_attrs)
		self._plug_idle()
		return True
	
	def plugout(self):
		''' Disconnect from the remote server and unregister self.disconnected method from
			the owner's dispatcher. '''
		self.disconnect()
		self._owner.Connection = None
		self._owner = None
	
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
	
	
	
	def send(self, stanza):
		'''Append stanza to the queue of messages to be send. 
		If supplied data is unicode string, encode it to utf-8.
		'''
		if self.state <= 0:
			return
		r = stanza
		if isinstance(r, unicode): 
			r = r.encode('utf-8')
		#~ elif not isinstance(r, str): 
			#~ r = ustr(r).encode('utf-8')
		self.sendqueue.append(r)
		self._plug_idle()
		
	def read_timeout(self):
		gajim.idlequeue.remove_timeout(self.fd)
		# no activity for foo seconds
		# self.pollend()
	
	
	def do_connect(self):
		try:
			self._sock.connect((self.host, self.port))
			self._sock.setblocking(False)
		except Exception, ee:
			(errnum, errstr) = ee
			if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK): 
				return
			# win32 needs this
			elif errnum not in  (10056, errno.EISCONN) or self.state != 0:
				self.disconnect()
				return None
			else: # socket is already connected
				self._sock.setblocking(False)
		self.connected = True
		self.state = 1 # connected
		self.on_connect(self)
		return 1 # we are connected
	
	
	def pollout(self):
		if not self.connected:
			self.disconnect()
			return
		if self.state == 0:
			self.do_connect()
			return
		gajim.idlequeue.remove_timeout(self.fd)
		self._do_send()
	
	def pollend(self):
		self.state = -1
		self.disconnect()
	
	def pollin(self):
		''' Reads all pending incoming data. Calls owner's disconnected() method if appropriate.'''
		received = ''
		errnum = 0
		try: 
			# get as many bites, as possible, but not more than RECV_BUFSIZE
			received = self._sock.recv(MAX_BUFF_LEN)
		except Exception, e:
			if len(e.args)  > 0 and isinstance(e.args[0], int):
				errnum = e[0]
			sys.exc_clear()
			# "received" will be empty anyhow 
		if errnum == socket.SSL_ERROR_WANT_READ:
			pass
		elif errnum in [errno.ECONNRESET, errno.ENOTCONN, errno.ESHUTDOWN]:
			self.pollend()
			# don't proccess result, cas it will raise error
			return
		elif not received :
			if errnum != socket.SSL_ERROR_EOF: 
				# 8 EOF occurred in violation of protocol
				self.pollend()
			if self.state >= 0:
				self.disconnect()
			return
		
		if self.state < 0:
			return
		if self.on_receive:
			if hasattr(self._owner, 'Dispatcher'):
				self._owner.Dispatcher.Event('', DATA_RECEIVED, received)
			self.on_receive(received)
		else:
			# This should never happed, so we need the debug
			self.DEBUG('Unhandled data received: %s' % received,'got')
			self.disconnect()
			if self.on_connect_failure:
				self.on_connect_failure()
		return True
	
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
	
	def disconnect(self):
		''' Closes the socket. '''
		gajim.idlequeue.remove_timeout(self.fd)
		gajim.idlequeue.unplug_idle(self.fd)
		try:
			self._sock.shutdown(socket.SHUT_RDWR)
			self._sock.close()
		except:
			# socket is already closed
			pass
		self.connected = False
		self.fd = -1
		self.state = -1
		self._owner.disconnected()

	def _do_send(self):
		if not self.sendbuff:
			if not self.sendqueue:
				return None # nothing to send
			self.sendbuff = self.sendqueue.pop(0)
			self.sent_data = self.sendbuff
		try:
			send_count = self._sock.send(self.sendbuff)
			if send_count:
				self.sendbuff = self.sendbuff[send_count:]
				if not self.sendbuff and not self.sendqueue:
					if self.state < 0:
						gajim.idlequeue.unplug_idle(self.fd)
						self._on_send()
						self.disconnect()
						return
					# we are not waiting for write 
					self._plug_idle()
				self._on_send()
		except socket.error, e:
			sys.exc_clear()
			if e[0] == socket.SSL_ERROR_WANT_WRITE:
				return True		
			if self.state < 0:
				self.disconnect()
				return
			self._on_send_failure()
			return
		return True
	
	def _plug_idle(self):
		readable = self.state != 0
		if self.sendqueue or self.sendbuff:
			writable = True
		else:
			writable = False
		if self.writable != writable or self.readable != readable:
			gajim.idlequeue.plug_idle(self, writable, readable)
	
	
	def _on_send(self):
		if self.sent_data and self.sent_data.strip():
			#~ self.DEBUG(self.sent_data,'sent')
			if hasattr(self._owner, 'Dispatcher'):
				self._owner.Dispatcher.Event('', DATA_SENT, self.sent_data)
		self.sent_data  = None
	
	def _on_send_failure(self):
		self.DEBUG("Socket error while sending data",'error')
		self._owner.disconnected()
		self.sent_data = None


class ClientZeroconf:
	def __init__(self, zeroconf, caller):
		self.roster = roster_zeroconf.Roster(zeroconf)
		self.caller = caller
		self.start_listener(zeroconf.port)
		
		
	def start_listener(self, port):
		self.listener = ZeroconfListener(port, self.caller)
		self.listener.bind()
		if self.listener.started is False:
			self.listener = None
			# We cannot bind port, call error 
			# dialog from dialogs.py and fail
			BindPortError(port)
			return None
		#~ self.connected += 1
	def getRoster(self):
		return self.roster.getRoster()

	def send(self, str):
		pass
