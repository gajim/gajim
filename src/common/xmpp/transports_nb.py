##   transports_nb.py
##       based on transports.py
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
Transports are objects responsible for connecting to XMPP server and putting 
data to wrapped sockets in in desired form (SSL, TLS, TCP, for HTTP proxy,
for SOCKS5 proxy...)

Transports are not aware of XMPP stanzas and only responsible for low-level
connection handling.
'''

from simplexml import ustr
from plugin import PlugIn
from idlequeue import IdleObject
import proxy_connectors
import tls_nb

import socket
import errno
import time
import traceback
import base64

import logging
log = logging.getLogger('gajim.c.x.transports_nb')

def urisplit(uri):
	'''
	Function for splitting URI string to tuple (protocol, host, path).
	e.g. urisplit('http://httpcm.jabber.org/webclient') returns
	('http', 'httpcm.jabber.org', '/webclient')
	'''
	import re
	regex = '(([^:/]+)(://))?([^/]*)(/?.*)'
	grouped = re.match(regex, uri).groups()
	proto, host, path = grouped[1], grouped[3], grouped[4]
	return proto, host, path

def get_proxy_data_from_dict(proxy):
	tcp_host, tcp_port, proxy_user, proxy_pass = None, None, None, None
	proxy_type = proxy['type']
	if proxy_type == 'bosh' and not proxy['bosh_useproxy']:
		# with BOSH not over proxy we have to parse the hostname from BOSH URI 
		tcp_host, tcp_port = urisplit(proxy['bosh_uri'])[1], proxy['bosh_port'] 
	else: 
		# with proxy!=bosh or with bosh over HTTP proxy we're connecting to proxy 
		# machine 
		tcp_host, tcp_port = proxy['host'], proxy['port'] 
		if proxy['useauth']:
			proxy_user, proxy_pass = proxy['user'], proxy['pass']
	return tcp_host, tcp_port, proxy_user, proxy_pass

#: timeout to connect to the server socket, it doesn't include auth
CONNECT_TIMEOUT_SECONDS = 30

#: how long to wait for a disconnect to complete
DISCONNECT_TIMEOUT_SECONDS = 5

#: size of the buffer which reads data from server
# if lower, more stanzas will be fragmented and processed twice
RECV_BUFSIZE = 32768 # 2x maximum size of ssl packet, should be plenty
# FIXME: (#2634) gajim breaks with #RECV_BUFSIZE = 16
# it's inefficient but should work. Problem is that connect machine makes wrong
# assumptions and that we only check for pending data in sockets but not in SSL
# buffer...

DATA_RECEIVED = 'DATA RECEIVED'
DATA_SENT = 'DATA SENT'

DISCONNECTED = 'DISCONNECTED'
DISCONNECTING = 'DISCONNECTING'
CONNECTING = 'CONNECTING'
PROXY_CONNECTING = 'PROXY_CONNECTING'
CONNECTED = 'CONNECTED'
STATES = (DISCONNECTED, CONNECTING, PROXY_CONNECTING, CONNECTED, DISCONNECTING)

class NonBlockingTransport(PlugIn):
	'''
	Abstract class representing a transport.

	Subclasses CAN have different constructor signature but connect method SHOULD
	be the same.
	'''
	def __init__(self, raise_event, on_disconnect, idlequeue, estabilish_tls,
	certs):
		'''
		Each trasport class can have different constructor but it has to have at
		least all the arguments of NonBlockingTransport constructor.
 
		:param raise_event: callback for monitoring of sent and received data
		:param on_disconnect: callback called on disconnection during runtime
		:param idlequeue: processing idlequeue
		:param estabilish_tls: boolean whether to estabilish TLS connection after
			TCP connection is done
		:param certs: tuple of (cacerts, mycerts) see constructor of 
			tls_nb.NonBlockingTLS for more details
		'''
		PlugIn.__init__(self)
		self.raise_event = raise_event
		self.on_disconnect = on_disconnect
		self.on_connect = None
		self.on_connect_failure = None
		self.idlequeue = idlequeue
		self.on_receive = None
		self.server = None
		self.port = None
		self.conn_5tuple = None
		self.set_state(DISCONNECTED) 
		self.estabilish_tls = estabilish_tls 
		self.certs = certs 
		# type of used ssl lib (if any) will be assigned to this member var 
		self.ssl_lib = None
		self._exported_methods=[self.onreceive, self.set_send_timeout,
			 self.set_timeout, self.remove_timeout, self.start_disconnect]

		# time to wait for SOME stanza to come and then send keepalive
		self.sendtimeout = 0

		# in case we want to something different than sending keepalives
		self.on_timeout = None

	def plugin(self, owner):
		owner.Connection = self

	def plugout(self):
		self._owner.Connection = None
		self._owner = None
		self.disconnect(do_callback=False)

	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		'''
		Creates and connects transport to server and port defined in conn_5tuple
		which should be item from list returned from getaddrinfo.

		:param conn_5tuple: 5-tuple returned from getaddrinfo
		:param on_connect: callback called on successful connect to the server
		:param on_connect_failure: callback called on failure when connecting
		'''
		self.on_connect = on_connect
		self.on_connect_failure = on_connect_failure
		self.server, self.port = conn_5tuple[4][:2]
		self.conn_5tuple = conn_5tuple

	def set_state(self, newstate):
		assert(newstate in STATES)
		self.state = newstate

	def get_state(self):
		return self.state

	def _on_connect(self):
		''' preceeds call of on_connect callback '''
		# data is reference to socket wrapper instance. We don't need it in client
		# because
		self.set_state(CONNECTED)
		self.on_connect()

	def _on_connect_failure(self, err_message):
		''' preceeds call of on_connect_failure callback '''
		# In case of error while connecting we need to disconnect transport
		# but we don't want to call DisconnectHandlers from client,
		# thus the do_callback=False
		self.disconnect(do_callback=False)
		self.on_connect_failure(err_message=err_message)

	def send(self, raw_data, now=False):
		if self.get_state() == DISCONNECTED:
			log.error('Unable to send %s \n because state is %s.' %
				(raw_data, self.get_state()))

	def disconnect(self, do_callback=True):
		self.set_state(DISCONNECTED)
		if do_callback:
			# invoke callback given in __init__
			self.on_disconnect()

	def onreceive(self, recv_handler):
		'''
		Sets the on_receive callback.

		onreceive(None) sets callback to Dispatcher.ProcessNonBlocking which is
		the default one that will decide what to do with received stanza based on
		its tag name and namespace.

		Do not confuse it with on_receive() method, which is the callback itself.
		'''
		if not recv_handler:
			if hasattr(self, '_owner') and hasattr(self._owner, 'Dispatcher'):
				self.on_receive = self._owner.Dispatcher.ProcessNonBlocking
			else:
				log.warning('No Dispatcher plugged. Received data will not be processed')
				self.on_receive = None
			return
		self.on_receive = recv_handler

	def _tcp_connecting_started(self):
		self.set_state(CONNECTING)

	def read_timeout(self): 
		''' called when there's no response from server in defined timeout '''
		if self.on_timeout:
			self.on_timeout()
		self.renew_send_timeout()

	def renew_send_timeout(self):
		if self.on_timeout and self.sendtimeout > 0:
			self.set_timeout(self.sendtimeout)
		else:
			self.remove_timeout()

	def set_timeout(self, timeout):
		self.idlequeue.set_read_timeout(self.fd, timeout)

	def get_fd(self):
		pass

	def remove_timeout(self):
		self.idlequeue.remove_timeout(self.fd)

	def set_send_timeout(self, timeout, on_timeout):
		self.sendtimeout = timeout
		if self.sendtimeout > 0:
			self.on_timeout = on_timeout
		else:
			self.on_timeout = None

	# FIXME: where and why does this need to be called
	def start_disconnect(self):
		self.set_state(DISCONNECTING)


class NonBlockingTCP(NonBlockingTransport, IdleObject):
	'''
	Non-blocking TCP socket wrapper.

	It is used for simple XMPP connection. Can be connected via proxy and can
	estabilish TLS connection.
	'''
	def __init__(self, raise_event, on_disconnect, idlequeue, estabilish_tls,
	certs, proxy_dict=None):
		'''
		:param proxy_dict: dictionary with proxy data as loaded from config file
		'''
		NonBlockingTransport.__init__(self, raise_event, on_disconnect, idlequeue,
			estabilish_tls, certs)
		IdleObject.__init__(self)

		# queue with messages to be send
		self.sendqueue = []

		# bytes remained from the last send message
		self.sendbuff = ''

		self.proxy_dict = proxy_dict
		self.on_remote_disconnect = self.disconnect
	
	# FIXME: transport should not be aware xmpp
	def start_disconnect(self):
		NonBlockingTransport.start_disconnect(self)
		self.send('</stream:stream>', now=True)
		self.disconnect()

	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		NonBlockingTransport.connect(self, conn_5tuple, on_connect,
			on_connect_failure)
		log.info('NonBlockingTCP Connect :: About to connect to %s:%s' %
			(self.server, self.port))

		try:
			self._sock = socket.socket(*conn_5tuple[:3])
		except socket.error, (errnum, errstr):
			self._on_connect_failure('NonBlockingTCP Connect: Error while creating\
				socket: %s %s' % (errnum, errstr))
			return

		self._send = self._sock.send
		self._recv = self._sock.recv
		self.fd = self._sock.fileno()
		
		# we want to be notified when send is possible to connected socket because
		# it means the TCP connection is estabilished
		self._plug_idle(writable=True, readable=False)
		self.peerhost = None

		# variable for errno symbol that will be found from exception raised 
		# from connect()
		errnum = 0
	
		# set timeout for TCP connecting - if nonblocking connect() fails, pollend
		# is called. If if succeeds pollout is called.
		self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT_SECONDS)

		try:
			self._sock.setblocking(False)
			self._sock.connect((self.server, self.port))
		except Exception, (errnum, errstr):
			pass

		if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
			# connecting in progress
			log.info('After NB connect() of %s. "%s" raised => CONNECTING' % 
				(id(self), errstr))
			self._tcp_connecting_started()
			return

		# if there was some other exception, call failure callback and unplug 
		# transport which will also remove read_timeouts for descriptor
		self._on_connect_failure('Exception while connecting to %s:%s - %s %s' %
			(self.server, self.port, errnum, errstr))

	def _connect_to_proxy(self):
		self.set_state(PROXY_CONNECTING)
		if self.proxy_dict['type']   == 'socks5':
			proxyclass = proxy_connectors.SOCKS5Connector
		elif self.proxy_dict['type'] == 'http'  :
			proxyclass = proxy_connectors.HTTPCONNECTConnector
		proxyclass.get_instance(
			send_method=self.send,
			onreceive=self.onreceive,
			old_on_receive=self.on_receive,
			on_success=self._on_connect,
			on_failure=self._on_connect_failure,
			xmpp_server=self.proxy_dict['xmpp_server'],
			proxy_creds=self.proxy_dict['credentials'])

	def _on_connect(self):
		'''
		Preceeds invoking of on_connect callback. TCP connection is already
		estabilished by this time.
		'''
		if self.estabilish_tls:
			self.tls_init(
				on_succ = lambda: NonBlockingTransport._on_connect(self),
				on_fail = lambda: self._on_connect_failure(
					'error while estabilishing TLS'))
		else:
			NonBlockingTransport._on_connect(self)

	def tls_init(self, on_succ, on_fail):
		'''
		Estabilishes TLS/SSL using this TCP connection by plugging a
		NonBlockingTLS module
		'''
		cacerts, mycerts = self.certs
		result = tls_nb.NonBlockingTLS.get_instance(cacerts, mycerts).PlugIn(self)
		if result:
			on_succ()
		else:
			on_fail()

	def pollin(self):
		'''called by idlequeu when receive on plugged socket is possible '''
		log.info('pollin called, state == %s' % self.get_state())
		self._do_receive()

	def pollout(self):
		'''called by idlequeu when send to plugged socket is possible'''
		log.info('pollout called, state == %s' % self.get_state())

		if self.get_state() == CONNECTING:
			log.info('%s socket wrapper connected' % id(self))
			self.idlequeue.remove_timeout(self.fd)
			self._plug_idle(writable=False, readable=False)
			self.peerhost  = self._sock.getsockname()
			if self.proxy_dict:
				self._connect_to_proxy()
			else:
				self._on_connect()
		else:
			self._do_send()

	def pollend(self):
		'''called by idlequeue on TCP connection errors'''
		log.info('pollend called, state == %s' % self.get_state())

		if self.get_state() == CONNECTING:
			self._on_connect_failure('Error during connect to %s:%s' %
				(self.server, self.port))
		else:
			self.disconnect()

	def disconnect(self, do_callback=True):
		if self.get_state() == DISCONNECTED:
			return
		self.set_state(DISCONNECTED)
		self.idlequeue.unplug_idle(self.fd)
		if 'NonBlockingTLS' in self.__dict__:
			self.NonBlockingTLS.PlugOut()
		try:
			self._sock.shutdown(socket.SHUT_RDWR)
			self._sock.close()
		except socket.error, (errnum, errstr):
			log.error('Error while disconnecting socket: %s' % errstr)
		self.fd = -1
		NonBlockingTransport.disconnect(self, do_callback)

	def read_timeout(self):
		log.info('read_timeout called, state == %s' % self.get_state())
		if self.get_state() == CONNECTING:
			# if read_timeout is called during connecting, connect() didn't end yet
			# thus we have to call the tcp failure callback
			self._on_connect_failure('Error during connect to %s:%s' %
				(self.server, self.port))
		else:
			NonBlockingTransport.read_timeout(self)

	def set_timeout(self, timeout):
		if self.get_state() != DISCONNECTED and self.fd != -1:
			NonBlockingTransport.set_timeout(self, timeout)
		else:
			log.warn('set_timeout: TIMEOUT NOT SET: state is %s, fd is %s' %
				(self.get_state(), self.fd))

	def remove_timeout(self):
		if self.fd:
			NonBlockingTransport.remove_timeout(self)
		else:
			log.warn('remove_timeout: no self.fd state is %s' % self.get_state())

	def send(self, raw_data, now=False):
		'''
		Append raw_data to the queue of messages to be send.
		If supplied data is unicode string, encode it to utf-8.
		'''
		NonBlockingTransport.send(self, raw_data, now)

		r = self.encode_stanza(raw_data)

		if now:
			self.sendqueue.insert(0, r)
			self._do_send()
		else:
			self.sendqueue.append(r)

		self._plug_idle(writable=True, readable=True)

	def encode_stanza(self, stanza):
		''' Encode str or unicode to utf-8 '''
		if isinstance(stanza, unicode):
			stanza = stanza.encode('utf-8')
		elif not isinstance(stanza, str):
			stanza = ustr(stanza).encode('utf-8')
		return stanza

	def _plug_idle(self, writable, readable):
		'''
		Plugs file descriptor of socket to Idlequeue.
		
		Plugged socket will be watched for "send possible" or/and "recv possible"
		events. pollin() callback is invoked on "recv possible", pollout() on
		"send_possible".

		Plugged socket will always be watched for "error" event - in that case,
		pollend() is called.
		'''
		log.info('Plugging fd %d, W:%s, R:%s' % (self.fd, writable, readable))
		self.idlequeue.plug_idle(self, writable, readable)

	def _do_send(self):
		'''
		Called when send() to connected socket is possible. First message from
		sendqueue will be sent.
		'''
		if not self.sendbuff:
			if not self.sendqueue:
				log.warn('calling send on empty buffer and queue')
				self._plug_idle(writable=False, readable=True)
				return None
			self.sendbuff = self.sendqueue.pop(0)
		try:
			send_count = self._send(self.sendbuff)
			if send_count:
				sent_data = self.sendbuff[:send_count]
				self.sendbuff = self.sendbuff[send_count:]
				self._plug_idle(
					writable=((self.sendqueue!=[]) or (self.sendbuff!='')),
					readable=True)
				self.raise_event(DATA_SENT, sent_data)

		except socket.error, e:
			log.error('_do_send:', exc_info=True)
			traceback.print_exc()
			self.disconnect()

	def _do_receive(self):
		'''
		Reads all pending incoming data. Will call owner's disconnected() method
		if appropriate.
		'''
		received = None
		errnum = 0
		errstr = 'No Error Set'

		try:
			# get as many bites, as possible, but not more than RECV_BUFSIZE
			received = self._recv(RECV_BUFSIZE)
		except socket.error, (errnum, errstr):
			log.info("_do_receive: got %s:" % received , exc_info=True)
		except tls_nb.SSLWrapper.Error, e:
			log.info("_do_receive, caught SSL error, got %s:" % received,
				exc_info=True)
			errnum, errstr = e.exc

		if received == '':
			errstr = 'zero bytes on recv'

		if (self.ssl_lib is None and received == '') or \
		(self.ssl_lib == tls_nb.PYSTDLIB  and errnum ==  8 ) or \
		(self.ssl_lib == tls_nb.PYOPENSSL and errnum == -1 ):
			#  8 in stdlib: errstr == EOF occured in violation of protocol
			# -1 in pyopenssl: errstr == Unexpected EOF
			log.info("Disconnected by remote server: #%s, %s" % (errnum, errstr))
			self.on_remote_disconnect()
			return

		if errnum:
			log.info("Connection to %s:%s lost: %s %s" % (self.server, self.port,
				errnum, errstr), exc_info=True)
			self.disconnect()
			return

		# this branch is for case of non-fatal SSL errors - None is returned from
		# recv() but no errnum is set
		if received is None:
			return

		# we have received some bytes, stop the timeout!
		self.renew_send_timeout()
		# pass received data to owner
		if self.on_receive:
			self.raise_event(DATA_RECEIVED, received)
			self._on_receive(received)
		else:
			# This should never happen, so we need the debug.
			# (If there is no handler on receive specified, data is passed to
			# Dispatcher.ProcessNonBlocking)
			log.error('SOCKET %s Unhandled data received: %s' % (id(self),
				received))
			self.disconnect()

	def _on_receive(self, data):
		''' preceeds on_receive callback. It peels off and checks HTTP headers in
		HTTP classes, in here it just calls the callback.'''
		self.on_receive(data)


class NonBlockingHTTP(NonBlockingTCP):
	'''
	Socket wrapper that creates HTTP message out of sent data and peels-off
	HTTP headers from incoming messages.
	'''

	def __init__(self, raise_event, on_disconnect, idlequeue, estabilish_tls,
	certs, on_http_request_possible, on_persistent_fallback, http_dict,
	proxy_dict=None):
		'''
		:param on_http_request_possible: method to call when HTTP request to
			socket owned by transport is possible.
		:param on_persistent_fallback: callback called when server ends TCP
			connection. It doesn't have to be fatal for HTTP session.
		:param http_dict: dictionary with data for HTTP request and headers
		'''
		NonBlockingTCP.__init__(self, raise_event, on_disconnect, idlequeue,
			estabilish_tls, certs, proxy_dict)

		self.http_protocol, self.http_host, self.http_path = urisplit(
			http_dict['http_uri'])
		self.http_protocol = self.http_protocol or 'http'
		self.http_path = self.http_path or '/'
		self.http_port = http_dict['http_port']
		self.http_version = http_dict['http_version']
		self.http_persistent = http_dict['http_persistent']
		self.add_proxy_headers =  http_dict['add_proxy_headers']

		if 'proxy_user' in http_dict and 'proxy_pass' in http_dict:
			self.proxy_user, self.proxy_pass = http_dict['proxy_user'], http_dict[
				'proxy_pass']
		else:
			self.proxy_user, self.proxy_pass = None, None

		# buffer for partial responses
		self.recvbuff = ''
		self.expected_length = 0 
		self.pending_requests = 0
		self.on_http_request_possible = on_http_request_possible
		self.last_recv_time = 0
		self.close_current_connection = False
		self.on_remote_disconnect = lambda: on_persistent_fallback(self)

	def http_send(self, raw_data, now=False):
		self.send(self.build_http_message(raw_data), now)

	def _on_receive(self, data):
		'''
		Preceeds passing received data to owner class. Gets rid of HTTP headers
		and checks them.
		'''
		if self.get_state() == PROXY_CONNECTING:
			NonBlockingTCP._on_receive(self, data)
			return
		if not self.recvbuff:
			# recvbuff empty - fresh HTTP message was received
			try:
				statusline, headers, self.recvbuff = self.parse_http_message(data)
			except ValueError:
				self.disconnect() 
				return
			if statusline[1] != '200':
				log.error('HTTP Error: %s %s' % (statusline[1], statusline[2]))
				self.disconnect()
				return
			self.expected_length = int(headers['Content-Length'])
			if 'Connection' in headers and headers['Connection'].strip()=='close':
				self.close_current_connection = True
		else:
			#sth in recvbuff - append currently received data to HTTP msg in buffer
			self.recvbuff = '%s%s' % (self.recvbuff, data)

		if self.expected_length > len(self.recvbuff):
			# If we haven't received the whole HTTP mess yet, let's end the thread.
			# It will be finnished from one of following recvs on plugged socket.
			log.info('not enough bytes in HTTP response - %d expected, %d got' %
				(self.expected_length, len(self.recvbuff)))
			return

		# everything was received
		httpbody = self.recvbuff

		self.recvbuff = ''
		self.expected_length = 0

		if not self.http_persistent or self.close_current_connection:
			# not-persistent connections disconnect after response
			self.disconnect(do_callback=False)
		self.close_current_connection = False
		self.last_recv_time = time.time()
		self.on_receive(data=httpbody, socket=self)
		self.on_http_request_possible()

	def build_http_message(self, httpbody, method='POST'):
		'''
		Builds http message with given body.
		Values for headers and status line fields are taken from class variables.
		'''
		absolute_uri = '%s://%s:%s%s' % (self.http_protocol, self.http_host,
			self.http_port, self.http_path)
		headers = ['%s %s %s' % (method, absolute_uri, self.http_version),
			'Host: %s:%s' % (self.http_host, self.http_port),
			'User-Agent: Gajim',
			'Content-Type: text/xml; charset=utf-8',
			'Content-Length: %s' % len(str(httpbody))]
		if self.add_proxy_headers:
			headers.append('Proxy-Connection: keep-alive')
			headers.append('Pragma: no-cache')
			if self.proxy_user and self.proxy_pass:
				credentials = '%s:%s' % (self.proxy_user, self.proxy_pass)
				credentials = base64.encodestring(credentials).strip()
				headers.append('Proxy-Authorization: Basic %s' % credentials)
		else:
			headers.append('Connection: Keep-Alive')
		headers.append('\r\n')
		headers = '\r\n'.join(headers)
		return('%s%s\r\n' % (headers, httpbody))

	def parse_http_message(self, message):
		'''
		splits http message to tuple:
			(statusline - list of e.g. ['HTTP/1.1', '200', 'OK'],
			headers - dictionary of headers e.g. {'Content-Length': '604',
				'Content-Type': 'text/xml; charset=utf-8'},
			httpbody - string with http body)
		'''
		message = message.replace('\r','')
		(header, httpbody) = message.split('\n\n', 1)
		header = header.split('\n')
		statusline = header[0].split(' ', 2)
		header = header[1:]
		headers = {}
		for dummy in header:
			row = dummy.split(' ', 1)
			headers[row[0][:-1]] = row[1]
		return (statusline, headers, httpbody)


class NonBlockingHTTPBOSH(NonBlockingHTTP):
	'''
	Class for BOSH HTTP connections. Slightly redefines HTTP transport by calling
	bosh bodytag generating callback before putting data on wire.
	'''

	def set_stanza_build_cb(self, build_cb):
		self.build_cb = build_cb

	def _do_send(self):
		if self.state == PROXY_CONNECTING:
			NonBlockingTCP._do_send(self)
			return
		if not self.sendbuff:
			stanza = self.build_cb(socket=self)
			stanza = self.encode_stanza(stanza)
			stanza = self.build_http_message(httpbody=stanza)
			self.sendbuff = stanza
		NonBlockingTCP._do_send(self)

# vim: se ts=3:
