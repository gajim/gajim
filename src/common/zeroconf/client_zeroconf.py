##      common/zeroconf/client_zeroconf.py
##
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
## 				2006 Dimitur Kirov <dkirov@gmail.com>
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
from common import gajim
import common.xmpp
from common.xmpp.idlequeue import IdleObject
from common.xmpp import dispatcher_nb, simplexml
from common.xmpp.client import *
from common.xmpp.simplexml import ustr
from common.zeroconf import zeroconf

from common.xmpp.protocol import *
import socket
import errno
import sys

import logging
log = logging.getLogger('gajim.c.z.client_zeroconf')

from common.zeroconf import roster_zeroconf

MAX_BUFF_LEN = 65536
DATA_RECEIVED = 'DATA RECEIVED'
DATA_SENT = 'DATA SENT'
TYPE_SERVER, TYPE_CLIENT = range(2)

# wait XX sec to establish a connection
CONNECT_TIMEOUT_SECONDS = 10

# after XX sec with no activity, close the stream
ACTIVITY_TIMEOUT_SECONDS = 30

class ZeroconfListener(IdleObject):
	def __init__(self, port, conn_holder):
		''' handle all incomming connections on ('0.0.0.0', port)'''
		self.port = port
		self.queue_idx = -1
		#~ self.queue = None
		self.started = False
		self._sock = None
		self.fd = -1
		self.caller = conn_holder.caller
		self.conn_holder = conn_holder

	def bind(self):
		flags = socket.AI_PASSIVE
		if hasattr(socket, 'AI_ADDRCONFIG'):
			flags |= socket.AI_ADDRCONFIG
		ai = socket.getaddrinfo(None, self.port, socket.AF_UNSPEC,
			socket.SOCK_STREAM, 0, flags)[0]
		self._serv = socket.socket(ai[0], ai[1])
		self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self._serv.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
		self._serv.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
		# will fail when port is busy, or we don't have rights to bind
		try:
			self._serv.bind((ai[4][0], self.port))
		except Exception:
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
		# loop through roster to find who has connected to us
		from_jid = None
		ipaddr = sock[1][0]
		for jid in self.conn_holder.getRoster().keys():
			entry = self.conn_holder.getRoster().getItem(jid)
			if (entry['address'] == ipaddr):
				from_jid = jid
				break
		P2PClient(sock[0], ipaddr, sock[1][1], self.conn_holder, [], from_jid)

	def disconnect(self):
		''' free all resources, we are not listening anymore '''
		gajim.idlequeue.remove_timeout(self.fd)
		gajim.idlequeue.unplug_idle(self.fd)
		self.fd = -1
		self.started = False
		try:
			self._serv.close()
		except socket.error:
			pass
		self.conn_holder.kill_all_connections()

	def accept_conn(self):
		''' accepts a new incoming connection '''
		_sock = self._serv.accept()
		_sock[0].setblocking(False)
		return _sock

class P2PClient(IdleObject):
	def __init__(self, _sock, host, port, conn_holder, stanzaqueue=[], to=None,
	on_ok=None, on_not_ok=None):
		self._owner = self
		self.Namespace = 'jabber:client'
		self.defaultNamespace = self.Namespace
		self._component = 0
		self._registered_name = None
		self._caller = conn_holder.caller
		self.conn_holder = conn_holder
		self.stanzaqueue = stanzaqueue
		self.to = to
		self.Server = host
		self.on_ok = on_ok
		self.on_not_ok = on_not_ok
		self.DBG = 'client'
		self.Connection = None
		if gajim.verbose:
			debug = ['always', 'nodebuilder']
		else:
			debug = []
		self._DEBUG = Debug.Debug(debug)
		self.DEBUG = self._DEBUG.Show
		self.debug_flags = self._DEBUG.debug_flags
		self.debug_flags.append(self.DBG)
		self.sock_hash = None
		if _sock:
			self.sock_type = TYPE_SERVER
		else:
			self.sock_type = TYPE_CLIENT
		self.fd = -1
		conn = P2PConnection('', _sock, host, port, self._caller, self.on_connect,
			self)
		if not self.conn_holder:
			# An error occured, disconnect() has been called
			if on_not_ok:
				on_not_ok('Connection to host could not be established.')
			return
		self.sock_hash = conn._sock.__hash__
		self.fd = conn.fd
		self.conn_holder.add_connection(self, self.Server, port, self.to)
		# count messages in queue
		for val in self.stanzaqueue:
			is_message = val[1]
			if is_message:
				if self.fd == -1:
					if on_not_ok:
						on_not_ok('Connection to host could not be established.')
					return
				id = stanza.getThread()
				if self.conn_holder.ids_of_awaiting_messages.has_key(self.fd):
					self.conn_holder.ids_of_awaiting_messages[self.fd].append(id)
				else:
					self.conn_holder.ids_of_awaiting_messages[self.fd] = [id]

	def add_stanza(self, stanza, is_message=False):
		if self.Connection:
			if self.Connection.state == -1:
				return False
			self.send(stanza, is_message)
		else:
			self.stanzaqueue.append((stanza, is_message))

		if is_message:
			id = stanza.getThread()
			if self.conn_holder.ids_of_awaiting_messages.has_key(self.fd):
				self.conn_holder.ids_of_awaiting_messages[self.fd].append(id)
			else:
				self.conn_holder.ids_of_awaiting_messages[self.fd] = [id]

		return True

	def on_message_sent(self, connection_id):
		self.conn_holder.ids_of_awaiting_messages[connection_id].pop(0)

	def on_connect(self, conn):
		self.Connection = conn
		self.Connection.PlugIn(self)
		dispatcher_nb.Dispatcher().PlugIn(self)
		self._register_handlers()
		if self.on_ok:
			self.on_ok()

	def StreamInit(self):
		''' Send an initial stream header. '''
		self.Dispatcher.Stream = simplexml.NodeBuilder()
		self.Dispatcher.Stream._dispatch_depth = 2
		self.Dispatcher.Stream.dispatch = self.Dispatcher.dispatch
		self.Dispatcher.Stream.stream_header_received = self._check_stream_start
		self.debug_flags.append(simplexml.DBG_NODEBUILDER)
		self.Dispatcher.Stream.DEBUG = self.DEBUG
		self.Dispatcher.Stream.features = None
		if self.sock_type == TYPE_CLIENT:
			self.send_stream_header()

	def send_stream_header(self):
		self.Dispatcher._metastream = Node('stream:stream')
		self.Dispatcher._metastream.setNamespace(self.Namespace)
		self.Dispatcher._metastream.setAttr('version', '1.0')
		self.Dispatcher._metastream.setAttr('xmlns:stream', NS_STREAMS)
		self.Dispatcher._metastream.setAttr('from', self.conn_holder.zeroconf.name)
		if self.to:
			self.Dispatcher._metastream.setAttr('to', self.to)
		self.Dispatcher.send("<?xml version='1.0'?>%s>" % str(
			self.Dispatcher._metastream)[:-2])

	def _check_stream_start(self, ns, tag, attrs):
		if ns != NS_STREAMS or tag != 'stream':
			self.Connection.DEBUG('Incorrect stream start: (%s,%s).Terminating! ' \
				% (tag, ns), 'error')
			self.Connection.disconnect()
			if self.on_not_ok:
				self.on_not_ok('Connection to host could not be established: Incorrect answer from server.')
			return
		if self.sock_type == TYPE_SERVER:
			if attrs.has_key('from'):
				self.to = attrs['from']
			self.send_stream_header()
			if attrs.has_key('version') and attrs['version'] == '1.0':
				# other part supports stream features
				features = Node('stream:features')
				self.Dispatcher.send(features)
			while self.stanzaqueue:
				stanza, is_message = self.stanzaqueue.pop(0)
				self.send(stanza, is_message)
		elif self.sock_type == TYPE_CLIENT:
			while self.stanzaqueue:
				stanza, is_message = self.stanzaqueue.pop(0)
				self.send(stanza, is_message)

	def on_disconnect(self):
		if self.conn_holder:
			if self.conn_holder.ids_of_awaiting_messages.has_key(self.fd):
				del self.conn_holder.ids_of_awaiting_messages[self.fd]
			self.conn_holder.remove_connection(self.sock_hash)
		if self.__dict__.has_key('Dispatcher'):
			self.Dispatcher.PlugOut()
		if self.__dict__.has_key('P2PConnection'):
			self.P2PConnection.PlugOut()
		self.Connection = None
		self._caller = None
		self.conn_holder = None

	def force_disconnect(self):
		if self.Connection:
			self.disconnect()
		else:
			self.on_disconnect()

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

	def _register_handlers(self):
		self.RegisterHandler('message', lambda conn, data:self._caller._messageCB(
			self.Server, conn, data))
		self.RegisterHandler('iq', self._caller._siSetCB, 'set',
			common.xmpp.NS_SI)
		self.RegisterHandler('iq', self._caller._siErrorCB, 'error',
			common.xmpp.NS_SI)
		self.RegisterHandler('iq', self._caller._siResultCB, 'result',
			common.xmpp.NS_SI)
		self.RegisterHandler('iq', self._caller._bytestreamSetCB, 'set',
			common.xmpp.NS_BYTESTREAM)
		self.RegisterHandler('iq', self._caller._bytestreamResultCB, 'result',
			common.xmpp.NS_BYTESTREAM)
		self.RegisterHandler('iq', self._caller._bytestreamErrorCB, 'error',
			common.xmpp.NS_BYTESTREAM)

class P2PConnection(IdleObject, PlugIn):
	def __init__(self, sock_hash, _sock, host=None, port=None, caller=None,
	on_connect=None, client=None):
		IdleObject.__init__(self)
		self._owner = client
		PlugIn.__init__(self)
		self.DBG_LINE = 'socket'
		self.sendqueue = []
		self.sendbuff = None
		self.buff_is_message = False
		self._sock = _sock
		self.sock_hash = None
		self.host, self.port = host, port
		self.on_connect = on_connect
		self.client = client
		self.writable = False
		self.readable = False
		self._exported_methods = [self.send, self.disconnect, self.onreceive]
		self.on_receive = None
		if _sock:
			self._sock = _sock
			self.state = 1
			self._sock.setblocking(False)
			self.fd = self._sock.fileno()
			self.on_connect(self)
		else:
			self.state = 0
			try:
				self.ais = socket.getaddrinfo(host, port, socket.AF_UNSPEC,
					socket.SOCK_STREAM)
			except socket.gaierror, e:
				log.info('Lookup failure for %s: %s[%s]', host, e[1], repr(e[0]),
					exc_info=True)
			else:
				self.connect_to_next_ip()

	def connect_to_next_ip(self):
		if len(self.ais) == 0:
			log.error('Connection failure to %s', self.host, exc_info=True)
			self.disconnect()
			return
		ai = self.ais.pop(0)
		log.info('Trying to connect to %s through %s:%s', self.host, ai[4][0],
			ai[4][1], exc_info=True)
		try:
			self._sock = socket.socket(*ai[:3])
			self._sock.setblocking(False)
			self._server = ai[4]
		except socket.error:
			if sys.exc_value[0] != errno.EINPROGRESS:
				# for all errors, we try other addresses
				self.connect_to_next_ip()
				return
		self.fd = self._sock.fileno()
		gajim.idlequeue.plug_idle(self, True, False)
		self.set_timeout(CONNECT_TIMEOUT_SECONDS)
		self.do_connect()

	def set_timeout(self, timeout):
		gajim.idlequeue.remove_timeout(self.fd)
		if self.state >= 0:
			gajim.idlequeue.set_read_timeout(self.fd, timeout)

	def plugin(self, owner):
		self.onreceive(owner._on_receive_document_attrs)
		self._plug_idle()
		return True

	def plugout(self):
		'''Disconnect from the remote server and unregister self.disconnected method from
			the owner's dispatcher.'''
		self.disconnect()
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

	def send(self, packet, is_message=False, now=False):
		'''Append stanza to the queue of messages to be send if now is
		False, else send it instantly.
		If supplied data is unicode string, encode it to utf-8.
		'''
		if self.state <= 0:
			return

		r = packet

		if isinstance(r, unicode):
			r = r.encode('utf-8')
		elif not isinstance(r, str):
			r = ustr(r).encode('utf-8')

		if now:
			self.sendqueue.insert(0, (r, is_message))
			self._do_send()
		else:
			self.sendqueue.append((r, is_message))
		self._plug_idle()

	def read_timeout(self):
		ids = self.client.conn_holder.ids_of_awaiting_messages
		if self.fd in ids and len(ids[self.fd]) > 0:
			for id in ids[self.fd]:
				self._owner.Dispatcher.Event('', DATA_ERROR, (self.client.to, id))
			ids[self.fd] = []
		self.pollend()

	def do_connect(self):
		errnum = 0
		try:
			self._sock.connect(self._server)
			self._sock.setblocking(False)
		except Exception, ee:
			(errnum, errstr) = ee
		if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
			return
		# win32 needs this
		elif errnum not in (0, 10056, errno.EISCONN) or self.state != 0:
			log.error('Could not connect to %s: %s [%s]', self.host, errnum,
				errstr)
			self.connect_to_next_ip()
			return
		else: # socket is already connected
			self._sock.setblocking(False)
		self.state = 1 # connected
		# we are connected
		self.on_connect(self)

	def pollout(self):
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
			if len(e.args) > 0 and isinstance(e.args[0], int):
				errnum = e[0]
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
			if self._owner.sock_type == TYPE_CLIENT:
				self.set_timeout(ACTIVITY_TIMEOUT_SECONDS)
			if received.strip():
				self.DEBUG(received, 'got')
			if hasattr(self._owner, 'Dispatcher'):
				self._owner.Dispatcher.Event('', DATA_RECEIVED, received)
			self.on_receive(received)
		else:
			# This should never happed, so we need the debug
			self.DEBUG('Unhandled data received: %s' % received,'error')
			self.disconnect()
		return True

	def disconnect(self):
		''' Closes the socket. '''
		gajim.idlequeue.remove_timeout(self.fd)
		gajim.idlequeue.unplug_idle(self.fd)
		try:
			self._sock.shutdown(socket.SHUT_RDWR)
			self._sock.close()
		except socket.error:
			# socket is already closed
			pass
		self.fd = -1
		self.state = -1
		if self._owner:
			self._owner.on_disconnect()

	def _do_send(self):
		if not self.sendbuff:
			if not self.sendqueue:
				return None # nothing to send
			self.sendbuff, self.buff_is_message = self.sendqueue.pop(0)
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
			if e[0] == socket.SSL_ERROR_WANT_WRITE:
				return True
			if self.state < 0:
				self.disconnect()
				return
			self._on_send_failure()
			return
		if self._owner.sock_type == TYPE_CLIENT:
			self.set_timeout(ACTIVITY_TIMEOUT_SECONDS)
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
			self.DEBUG(self.sent_data,'sent')
			if hasattr(self._owner, 'Dispatcher'):
				self._owner.Dispatcher.Event('', DATA_SENT, self.sent_data)
		self.sent_data = None
		if self.buff_is_message:
			self._owner.on_message_sent(self.fd)
			self.buff_is_message = False

	def _on_send_failure(self):
		self.DEBUG("Socket error while sending data",'error')
		self._owner.disconnected()
		self.sent_data = None

class ClientZeroconf:
	def __init__(self, caller):
		self.caller = caller
		self.zeroconf = None
		self.roster = None
		self.last_msg = ''
		self.connections = {}
		self.recipient_to_hash = {}
		self.ip_to_hash = {}
		self.hash_to_port = {}
		self.listener = None
		self.ids_of_awaiting_messages = {}

	def connect(self, show, msg):
		self.port = self.start_listener(self.caller.port)
		if not self.port:
			return False
		self.zeroconf_init(show, msg)
		if not self.zeroconf.connect():
			self.disconnect()
			return None
		self.roster = roster_zeroconf.Roster(self.zeroconf)
		return True

	def remove_announce(self):
		if self.zeroconf:
			return self.zeroconf.remove_announce()

	def announce(self):
		if self.zeroconf:
			return self.zeroconf.announce()

	def set_show_msg(self, show, msg):
		if self.zeroconf:
			self.zeroconf.txt['msg'] = msg
			self.last_msg = msg
			return self.zeroconf.update_txt(show)

	def resolve_all(self):
		if self.zeroconf:
			self.zeroconf.resolve_all()

	def reannounce(self, txt):
		self.remove_announce()
		self.zeroconf.txt = txt
		self.zeroconf.port = self.port
		self.zeroconf.username = self.caller.username
		return self.announce()

	def zeroconf_init(self, show, msg):
		self.zeroconf = zeroconf.Zeroconf(self.caller._on_new_service,
			self.caller._on_remove_service, self.caller._on_name_conflictCB,
			self.caller._on_disconnected, self.caller._on_error,
			self.caller.username, self.caller.host, self.port)
		self.zeroconf.txt['msg'] = msg
		self.zeroconf.txt['status'] = show
		self.zeroconf.txt['1st'] = self.caller.first
		self.zeroconf.txt['last'] = self.caller.last
		self.zeroconf.txt['jid'] = self.caller.jabber_id
		self.zeroconf.txt['email'] = self.caller.email
		self.zeroconf.username = self.caller.username
		self.zeroconf.host = self.caller.host
		self.zeroconf.port = self.port
		self.last_msg = msg

	def disconnect(self):
		if self.listener:
			self.listener.disconnect()
			self.listener = None
		if self.zeroconf:
			self.zeroconf.disconnect()
			self.zeroconf = None
		if self.roster:
			self.roster.zeroconf = None
			self.roster._data = None
			self.roster = None

	def kill_all_connections(self):
		for connection in self.connections.values():
			connection.force_disconnect()

	def add_connection(self, connection, ip, port, recipient):
		sock_hash=connection.sock_hash
		if sock_hash not in self.connections:
			self.connections[sock_hash] = connection
		self.ip_to_hash[ip] = sock_hash
		self.hash_to_port[sock_hash] = port
		if recipient:
			self.recipient_to_hash[recipient] = sock_hash

	def remove_connection(self, sock_hash):
		if sock_hash in self.connections:
			del self.connections[sock_hash]
		for i in self.recipient_to_hash:
			if self.recipient_to_hash[i] == sock_hash:
				del self.recipient_to_hash[i]
				break
		for i in self.ip_to_hash:
			if self.ip_to_hash[i] == sock_hash:
				del self.ip_to_hash[i]
				break
		if self.hash_to_port.has_key(sock_hash):
			del self.hash_to_port[sock_hash]

	def start_listener(self, port):
		for p in range(port, port + 5):
			self.listener = ZeroconfListener(p, self)
			self.listener.bind()
			if self.listener.started:
				return p
		self.listener = None
		return False

	def getRoster(self):
		if self.roster:
			return self.roster.getRoster()
		return {}

	def send(self, stanza, is_message=False, now=False, on_ok=None,
	on_not_ok=None):
		stanza.setFrom(self.roster.zeroconf.name)
		to = stanza.getTo()

		try:
			item = self.roster[to]
		except KeyError:
			# Contact offline
			return -1

		# look for hashed connections
		if to in self.recipient_to_hash:
			conn = self.connections[self.recipient_to_hash[to]]
			id_ = conn.Dispatcher.getAnID()
			stanza.setID(id_)
			if conn.add_stanza(stanza, is_message):
				if on_ok:
					on_ok()
				return id_

		if item['address'] in self.ip_to_hash:
			hash_ = self.ip_to_hash[item['address']]
			if self.hash_to_port[hash_] == item['port']:
				conn = self.connections[hash_]
				id_ = conn.Dispatcher.getAnID()
				stanza.setID(id_)
				if conn.add_stanza(stanza, is_message):
					if on_ok:
						on_ok()
					return id_

		# otherwise open new connection
		stanza.setID('zero')
		P2PClient(None, item['address'], item['port'], self,
			[(stanza, is_message)], to, on_ok=on_ok, on_not_ok=on_not_ok)

		return 'zero'

# vim: se ts=3:
