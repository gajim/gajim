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

import socket,base64

from simplexml import ustr
from client import PlugIn
from idlequeue import IdleObject
from protocol import *

import sys
import os
import errno
import time

import traceback

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
	type = proxy['type']
	if type == 'bosh' and not proxy['bosh_useproxy']:
		# with BOSH not over proxy we have to parse the hostname from BOSH URI
		tcp_host, tcp_port = urisplit(proxy['bosh_uri'])[1], proxy['bosh_port']
	else:
		# with proxy!=bosh or with bosh over HTTP proxy we're connecting to proxy
		# machine
		tcp_host, tcp_port = proxy['host'], proxy['port']
		if proxy['useauth']:
			proxy_user, proxy_pass = proxy['user'], proxy['pass']
	return tcp_host, tcp_port, proxy_user, proxy_pass



# timeout to connect to the server socket, it doesn't include auth 
CONNECT_TIMEOUT_SECONDS = 30

# how long to wait for a disconnect to complete
DISCONNECT_TIMEOUT_SECONDS = 10

# size of the buffer which reads data from server
# if lower, more stanzas will be fragmented and processed twice
RECV_BUFSIZE = 32768 # 2x maximum size of ssl packet, should be plenty
#RECV_BUFSIZE = 16 # FIXME: (#2634) gajim breaks with this setting: it's inefficient but should work.

DATA_RECEIVED='DATA RECEIVED'
DATA_SENT='DATA SENT'


DISCONNECTED ='DISCONNECTED' 	
DISCONNECTING ='DISCONNECTING' 	
CONNECTING ='CONNECTING'  
CONNECTED ='CONNECTED' 

# transports have different constructor and same connect

class NonBlockingTransport(PlugIn):
	def __init__(self, raise_event, on_disconnect, idlequeue):
		PlugIn.__init__(self)
		self.raise_event = raise_event
		self.on_disconnect = on_disconnect
		self.on_connect = None
		self.on_connect_failure = None
		self.idlequeue = idlequeue
		self.on_receive = None
		self.server = None
		self.port = None
		self.state = DISCONNECTED
		self._exported_methods=[self.disconnect, self.onreceive, self.set_send_timeout, 
			self.set_timeout, self.remove_timeout, self.start_disconnect]

		# time to wait for SOME stanza to come and then send keepalive
		self.sendtimeout = 0

		# in case we want to something different than sending keepalives
		self.on_timeout = None

	def plugin(self, owner):
		owner.Connection=self

	def plugout(self):
		self._owner.Connection = None
		self._owner = None

	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		'''
		connect method should have the same declaration in all derived transports

		'''
		assert(self.state == DISCONNECTED)
		self.on_connect = on_connect
		self.on_connect_failure = on_connect_failure
		(self.server, self.port) = conn_5tuple[4][:2]
		self.conn_5tuple = conn_5tuple


	def set_state(self, newstate):
		assert(newstate in [DISCONNECTED, CONNECTING, CONNECTED, DISCONNECTING])
		self.state = newstate

	def _on_connect(self, data):
		''' preceeds call of on_connect callback '''
		# data is reference to socket wrapper instance. We don't need it in client
		# because 
		self.peerhost  = data._sock.getsockname()
		self.set_state(CONNECTED)
		self.on_connect()

	def _on_connect_failure(self,err_message):
		''' preceeds call of on_connect_failure callback '''
		# In case of error while connecting we need to disconnect transport
		# but we don't want to call DisconnectHandlers from client,
		# thus the do_callback=False
		self.disconnect(do_callback=False)
		self.on_connect_failure(err_message=err_message)

	def send(self, raw_data, now=False):
		if self.state not in [CONNECTED]:
			log.error('Unable to send %s \n because state is %s.' % 
				(raw_data, self.state))
			

	def disconnect(self, do_callback=True):
		self.set_state(DISCONNECTED)
		if do_callback:
			# invoke callback given in __init__
			self.on_disconnect()

	def onreceive(self, recv_handler):
		''' Sets the on_receive callback. Do not confuse it with
		on_receive() method, which is the callback itself.'''
		if not recv_handler:
			if hasattr(self._owner, 'Dispatcher'):
				self.on_receive = self._owner.Dispatcher.ProcessNonBlocking
			else:
				self.on_receive = None
			return
		self.on_receive = recv_handler

	def tcp_connection_started(self):
		self.set_state(CONNECTING)
		# on_connect/on_conn_failure will be called from self.pollin/self.pollout

	def read_timeout(self):
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

	def start_disconnect(self):
		self.set_state(DISCONNECTING)



class NonBlockingTCP(NonBlockingTransport, IdleObject):
	'''
	Non-blocking TCP socket wrapper
	'''
	def __init__(self, raise_event, on_disconnect, idlequeue):
		'''
		Class constructor.
		'''
		NonBlockingTransport.__init__(self, raise_event, on_disconnect, idlequeue)

		# queue with messages to be send 
		self.sendqueue = []

		# bytes remained from the last send message
		self.sendbuff = ''

		self.terminator = '</stream:stream>'
		
	def start_disconnect(self):
		self.send('</stream:stream>')
		NonBlockingTransport.start_disconnect(self)

	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		'''
		Creates and connects socket to server and port defined in conn_5tupe which
		should be list item returned from getaddrinfo.
		:param conn_5tuple: 5-tuple returned from getaddrinfo
		:param on_connect: callback called on successful tcp connection
		:param on_connect_failure: callback called on failure when estabilishing tcp 
			connection
		'''
		NonBlockingTransport.connect(self, conn_5tuple, on_connect, on_connect_failure)
		log.info('NonBlockingTCP Connect :: About to connect to %s:%s' % (self.server, self.port))

		try:
			self._sock = socket.socket(*conn_5tuple[:3])
		except socket.error, (errnum, errstr):
			self._on_connect_failure('NonBlockingTCP Connect: Error while creating socket:\
				%s %s' % (errnum, errstr))
			return

		self._send = self._sock.send
		self._recv = self._sock.recv
		self.fd = self._sock.fileno()

		# we want to be notified when send is possible to connected socket
		self._plug_idle(writable=True, readable=False)
		self.peerhost = None

		errnum = 0
		''' variable for errno symbol that will be found from exception raised from connect() '''
	
		# set timeout for TCP connecting - if nonblocking connect() fails, pollend
		# is called. If if succeeds pollout is called.
		self.idlequeue.set_read_timeout(self.fd, CONNECT_TIMEOUT_SECONDS)

		try: 
			self._sock.setblocking(False)
			self._sock.connect((self.server,self.port))
		except Exception, (errnum, errstr):
			pass

		if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
			# connecting in progress
			log.info('After NB connect() of %s. "%s" raised => CONNECTING' % (id(self),errstr))
			self.tcp_connection_started()
			return
		elif errnum in (0, 10056, errno.EISCONN):
			# already connected - this branch is probably useless, nonblocking connect() will
			# return EINPROGRESS exception in most cases. When here, we don't need timeout
			# on connected descriptor and success callback can be called.
			log.info('After connect. "%s" raised => CONNECTED' % errstr)
			self._on_connect(self)
			return

		# if there was some other error, call failure callback and unplug transport
		# which will also remove read_timeouts for descriptor
		self._on_connect_failure('Exception while connecting to %s:%s - %s %s' % 
			(self.server, self.port, errnum, errstr))
			
	def _on_connect(self, data):
		''' with TCP socket, we have to remove send-timeout '''
		self.idlequeue.remove_timeout(self.fd)

		NonBlockingTransport._on_connect(self, data)
		

	def pollin(self):
		'''called when receive on plugged socket is possible '''
		log.info('pollin called, state == %s' % self.state)
		self._do_receive() 

	def pollout(self):
		'''called when send to plugged socket is possible'''
		log.info('pollout called, state == %s' % self.state)

		if self.state==CONNECTING:
			log.info('%s socket wrapper connected' % id(self))
			self._on_connect(self)
			return
		self._do_send()

	def pollend(self):
		log.info('pollend called, state == %s' % self.state)

		if self.state==CONNECTING:
			self._on_connect_failure('Error during connect to %s:%s' % 
				(self.server, self.port))
		else :
			self.disconnect()

	def disconnect(self, do_callback=True):
		if self.state == DISCONNECTED:
			return
		self.set_state(DISCONNECTED)
		self.idlequeue.unplug_idle(self.fd)
		try:
			self._sock.shutdown(socket.SHUT_RDWR)
			self._sock.close()
		except socket.error, (errnum, errstr):
			log.error('Error while disconnecting  a socket: %s %s' % (errnum,errstr))
		self.fd = -1
		NonBlockingTransport.disconnect(self, do_callback)

	def read_timeout(self):
		'''
		Implemntation of IdleObject function called on timeouts from IdleQueue.
		'''
		log.warn('read_timeout called, state == %s' % self.state)
		if self.state==CONNECTING:
			# if read_timeout is called during connecting, connect() didn't end yet
			# thus we have to call the tcp failure callback
			self._on_connect_failure('Error during connect to %s:%s' % 
				(self.server, self.port))
		else:
			NonBlockingTransport.read_timeout(self)

	
	
	def set_timeout(self, timeout):
		if self.state != DISCONNECTED and self.fd != -1:
			NonBlockingTransport.set_timeout(self, timeout)
		else:
			log.warn('set_timeout: TIMEOUT NOT SET: state is %s, fd is %s' % (self.state, self.fd))

	def remove_timeout(self):
		if self.fd:
			NonBlockingTransport.remove_timeout(self)
		else:
			log.warn('remove_timeout: no self.fd state is %s' % self.state)

	def send(self, raw_data, now=False):
		'''Append raw_data to the queue of messages to be send. 
		If supplied data is unicode string, encode it to utf-8.
		'''
		NonBlockingTransport.send(self, raw_data, now)
		r = raw_data
		if isinstance(r, unicode): 
			r = r.encode('utf-8')
		elif not isinstance(r, str): 
			r = ustr(r).encode('utf-8')
		if now:
			self.sendqueue.insert(0, r)
			self._do_send()
		else:
			self.sendqueue.append(r)
		self._plug_idle(writable=True, readable=True)



	def _plug_idle(self, writable, readable):
		'''
		Plugs file descriptor of socket to Idlequeue. Plugged socket
		will be watched for "send possible" or/and "recv possible" events. pollin()
		callback is invoked on "recv possible", pollout() on "send_possible".
		Plugged socket will always be watched for "error" event - in that case,
		pollend() is called.
		'''
		# if we are connecting, we shouln't touch the socket until it's connected
		assert(self.state!=CONNECTING)
		self.idlequeue.plug_idle(self, writable, readable)

		log.info('Plugging fd %d, W:%s, R:%s' % (self.fd, writable, readable))
		self.idlequeue.plug_idle(self, writable, readable)




	def _do_send(self):
		if not self.sendbuff:
			if not self.sendqueue:
				log.warn('calling send on empty buffer and queue')
				self._plug_idle(
					writable= ((self.sendqueue!=[]) or (self.sendbuff!='')),
					readable=True)
				return None
			self.sendbuff = self.sendqueue.pop(0)
		try:
			send_count = self._send(self.sendbuff)
			if send_count:
				sent_data = self.sendbuff[:send_count]
				self.sendbuff = self.sendbuff[send_count:]
				self._plug_idle(
					writable= ((self.sendqueue!=[]) or (self.sendbuff!='')),
					readable=True)
				self.raise_event(DATA_SENT, sent_data)

		except socket.error, e:
			log.error('_do_send:', exc_info=True)
			traceback.print_exc()
			self.disconnect()


	def _do_receive(self):
		''' Reads all pending incoming data. Calls owner's disconnected() method if appropriate.'''
		ERR_DISCONN = -2 # Misc error signifying that we got disconnected
		received = None
		errnum = 0
		errstr = 'No Error Set'

		try: 
			# get as many bites, as possible, but not more than RECV_BUFSIZE
			received = self._recv(RECV_BUFSIZE)
		except (socket.error, socket.herror, socket.gaierror), (errnum, errstr):
			# save exception number and message to errnum, errstr
			log.info("_do_receive: got %s:" % received , exc_info=True)
		
		if received == '':
			errnum = ERR_DISCONN
			errstr = "Connection closed unexpectedly"

		if errnum in (ERR_DISCONN, errno.ECONNRESET, errno.ENOTCONN, errno.ESHUTDOWN):
			# ECONNRESET - connection you are trying to access has been reset by the peer
			# ENOTCONN - Transport endpoint is not connected
			# ESHUTDOWN  - shutdown(2) has been called on a socket to close down the
			# sending end of the transmision, and then data was attempted to be sent
			log.error("Connection to %s lost: %s %s" % ( self.server, errnum, errstr))
			if self.on_remote_disconnect:
				self.on_remote_disconnect()
			else:
				self.disconnect()
			return

		if received is None:
			# in case of some other exception
			# FIXME: is this needed?? 
			if errnum != 0:
				log.error("CConnection to %s lost: %s %s" % (self.server, errnum, errstr))
				self.disconnect()
				return
			received = ''

		# we have received some bytes, stop the timeout!
		self.renew_send_timeout()
		# pass received data to owner
		if self.on_receive:
			self.raise_event(DATA_RECEIVED, received)
			self._on_receive(received)
		else:
			# This should never happen, so we need the debug. (If there is no handler
			# on receive specified, data are passed to Dispatcher.ProcessNonBlocking)
			log.error('SOCKET %s Unhandled data received: %s' % (id(self), received))
			traceback.print_stack()
			self.disconnect()

	def _on_receive(self,data):
		''' preceeds on_receive callback. It peels off and checks HTTP headers in
		class, in here it just calls the callback.'''
		self.on_receive(data)


class NonBlockingHTTP(NonBlockingTCP):
	'''
	Socket wrapper that creates HTTP message out of sent data and peels-off 
	HTTP headers from incoming messages
	'''

	def __init__(self, raise_event, on_disconnect, idlequeue, on_http_request_possible,
			on_persistent_fallback, http_dict):

		NonBlockingTCP.__init__(self, raise_event, on_disconnect, idlequeue)

		self.http_protocol, self.http_host, self.http_path = urisplit(http_dict['http_uri'])
		if self.http_protocol is None:
			self.http_protocol = 'http'
		if self.http_path == '':
			self.http_path = '/'
		self.http_port = http_dict['http_port']
		self.http_version = http_dict['http_version']
		self.http_persistent = http_dict['http_persistent']
		self.over_proxy =  http_dict['over_proxy']
		if http_dict.has_key('proxy_user') and http_dict.has_key('proxy_pass'):
			self.proxy_user, self.proxy_pass = http_dict['proxy_user'], http_dict['proxy_pass']
		else:
			self.proxy_user, self.proxy_pass = None, None

		# buffer for partial responses
		self.recvbuff = ''
		self.expected_length = 0 
		self.pending_requests = 0
		self.on_persistent_fallback = on_persistent_fallback
		self.on_http_request_possible = on_http_request_possible
		self.just_responed = False
		self.last_recv_time = 0
		
	def send(self, raw_data, now=False):
		NonBlockingTCP.send(
			self,
			self.build_http_message(raw_data),
			now)


	def on_remote_disconnect(self):
		log.warn('on_remote_disconnect called, http_persistent = %s' % self.http_persistent)
		if self.http_persistent:
			self.http_persistent = False
			self.on_persistent_fallback()
			self.disconnect(do_callback=False)
			self.connect(
				conn_5tuple = self.conn_5tuple,
				# after connect, the socket will be plugged as writable - pollout will be
				# called, and since there are still data in sendbuff, _do_send will be 
				# called and sendbuff will be flushed
				on_connect = lambda: self._plug_idle(writable=True, readable=True),
				on_connect_failure = self.disconnect)

		else:
			self.disconnect()
		return

	def _on_receive(self,data):
		'''Preceeds passing received data to owner class. Gets rid of HTTP headers
		and checks them.'''
		if not self.recvbuff:
			# recvbuff empty - fresh HTTP message was received
			statusline, headers, self.recvbuff = self.parse_http_message(data)
			if statusline[1] != '200':
				log.error('HTTP Error: %s %s' % (statusline[1], statusline[2]))
				self.disconnect()
				return
			self.expected_length = int(headers['Content-Length'])
		else:
			#sth in recvbuff - append currently received data to HTTP mess in buffer 
			self.recvbuff = '%s%s' % (self.recvbuff, data)

		if self.expected_length > len(self.recvbuff):
			# If we haven't received the whole HTTP mess yet, let's end the thread.
			# It will be finnished from one of following polls (io_watch) on plugged socket.
			log.info('not enough bytes in HTTP response - %d expected, %d got' %
				(self.expected_length, len(self.recvbuff)))
			return

		# everything was received
		httpbody = self.recvbuff

		self.recvbuff=''
		self.expected_length=0

		if not self.http_persistent:
			# not-persistent connections disconnect after response
			self.disconnect(do_callback = False)
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
			'Content-Type: text/xml; charset=utf-8',
			'Content-Length: %s' % len(str(httpbody))]
		if self.over_proxy:
			headers.append('Proxy-Connection: keep-alive')
			headers.append('Pragma: no-cache')
			if self.proxy_user and self.proxy_pass:
				credentials = '%s:%s' % (self.proxy_user, self.proxy_pass)
				credentials = base64.encodestring(credentials).strip()
				headers.append('Proxy-Authorization: Basic %s' % credentials)
		headers.append('\r\n')
		headers = '\r\n'.join(headers)
		return('%s%s\r\n' % (headers, httpbody))

	def parse_http_message(self, message):
		'''
		splits http message to tuple (
		  statusline - list of e.g. ['HTTP/1.1', '200', 'OK'],
		  headers - dictionary of headers e.g. {'Content-Length': '604',
		            'Content-Type': 'text/xml; charset=utf-8'},
		  httpbody - string with http body
		)  
		'''
		message = message.replace('\r','')
		(header, httpbody) = message.split('\n\n',1)
		header = header.split('\n')
		statusline = header[0].split(' ',2)
		header = header[1:]
		headers = {}
		for dummy in header:
			row = dummy.split(' ',1)
			headers[row[0][:-1]] = row[1]
		return (statusline, headers, httpbody)

class NonBlockingHTTPBOSH(NonBlockingHTTP):


	def set_stanza_build_cb(self, build_cb):
		self.build_cb = build_cb

	def _do_send(self):
		if not self.sendbuff:
			stanza = self.build_cb(socket=self)
			stanza = self.build_http_message(httpbody=stanza)
			if isinstance(stanza, unicode): 
				stanza = stanza.encode('utf-8')
			elif not isinstance(stanza, str): 
				stanza = ustr(stanza).encode('utf-8')
			self.sendbuff = stanza
		try:
			send_count = self._send(self.sendbuff)
			if send_count:
				sent_data = self.sendbuff[:send_count]
				self.sendbuff = self.sendbuff[send_count:]
				self._plug_idle(writable = self.sendbuff != '', readable = True)
				self.raise_event(DATA_SENT, sent_data)

		except socket.error, e:
			log.error('_do_send:', exc_info=True)
			traceback.print_exc()
			self.disconnect()



class NBProxySocket(NonBlockingTCP):
	'''
	Interface for proxy socket wrappers - when tunnneling XMPP over proxies,
	some connecting process usually has to be done before opening stream.
	'''
	def __init__(self, raise_event, on_disconnect, idlequeue, xmpp_server,
		proxy_creds=(None,None)):
		self.proxy_user, self.proxy_pass = proxy_creds
		self.xmpp_server = xmpp_server
		NonBlockingTCP.__init__(self, raise_event, on_disconnect, idlequeue)
		

	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		'''
		connect method is extended by proxy credentials and xmpp server hostname
		and port because those are needed for 
		The idea is to insert Proxy-specific mechanism after TCP connect and 
		before XMPP stream opening (which is done from client).
		'''

		self.after_proxy_connect = on_connect
		
		NonBlockingTCP.connect(self,
				conn_5tuple=conn_5tuple,
				on_connect =self._on_tcp_connect,
				on_connect_failure =on_connect_failure)

	def _on_tcp_connect(self):
		pass


class NBHTTPProxySocket(NBProxySocket):
	''' This class can be used instead of NonBlockingTCP
	HTTP (CONNECT) proxy connection class. Allows to use HTTP proxies like squid with
	(optionally) simple authentication (using login and password). 
	'''
		
	def _on_tcp_connect(self):
		''' Starts connection. Connects to proxy, supplies login and password to it
			(if were specified while creating instance). Instructs proxy to make
			connection to the target server. Returns non-empty sting on success. '''
		log.info('Proxy server contacted, performing authentification')
		connector = ['CONNECT %s:%s HTTP/1.0' % self.xmpp_server,
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
			self._on_connect_failure('Invalid proxy reply')
			return
		if code <> '200':
			log.error('Invalid proxy reply: %s %s %s' % (proto, code, desc))
			self._on_connect_failure('Invalid proxy reply')
			return
		if len(reply) != 2:
			pass
		self.after_proxy_connect()
		#self.onreceive(self._on_proxy_auth)

	def _on_proxy_auth(self, reply):
		if self.reply.find('\n\n') == -1:
			if reply is None:
				self._on_connect_failure('Proxy authentification failed')
				return
			if reply.find('\n\n') == -1:
				self.reply += reply.replace('\r', '')
				self._on_connect_failure('Proxy authentification failed')
				return
		log.info('Authentification successfull. Jabber server contacted.')
		self._on_connect(self)


class NBSOCKS5ProxySocket(NBProxySocket):
	'''SOCKS5 proxy connection class. Uses TCPsocket as the base class
		redefines only connect method. Allows to use SOCKS5 proxies with
		(optionally) simple authentication (only USERNAME/PASSWORD auth). 
	'''
	# TODO:  replace on_proxy_failure() with
	#	_on_connect_failure, at the end call _on_connect()

	def _on_tcp_connect(self):
		log.info('Proxy server contacted, performing authentification')
		if self.proxy.has_key('user') and self.proxy.has_key('password'):
			to_send = '\x05\x02\x00\x02'
		else:
			to_send = '\x05\x01\x00'
		self.onreceive(self._on_greeting_sent)
		self.send(to_send)

	def _on_greeting_sent(self, reply):
		if reply is None:
			return
		if len(reply) != 2:
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[0] != '\x05':
			log.info('Invalid proxy reply')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[1] == '\x00':
			return self._on_proxy_auth('\x01\x00')
		elif reply[1] == '\x02':
			to_send = '\x01' + chr(len(self.proxy['user'])) + self.proxy['user'] +\
				chr(len(self.proxy['password'])) + self.proxy['password']
			self.onreceive(self._on_proxy_auth)
			self.send(to_send)
		else:
			if reply[1] == '\xff':
				log.error('Authentification to proxy impossible: no acceptable '
					'auth method')
				self._owner.disconnected()
				self.on_proxy_failure('Authentification to proxy impossible: no '
					'acceptable authentification method')
				return
			log.error('Invalid proxy reply')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return

	def _on_proxy_auth(self, reply):
		if reply is None:
			return
		if len(reply) != 2:
			log.error('Invalid proxy reply')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[0] != '\x01':
			log.error('Invalid proxy reply')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[1] != '\x00':
			log.error('Authentification to proxy failed')
			self._owner.disconnected()
			self.on_proxy_failure('Authentification to proxy failed')
			return
		log.info('Authentification successfull. Jabber server contacted.')
		# Request connection
		req = "\x05\x01\x00"
		# If the given destination address is an IP address, we'll
		# use the IPv4 address request even if remote resolving was specified.
		try:
			self.ipaddr = socket.inet_aton(self.server[0])
			req = req + "\x01" + self.ipaddr
		except socket.error:
			# Well it's not an IP number,  so it's probably a DNS name.
#			if self.__proxy[3]==True:
			# Resolve remotely
			self.ipaddr = None
			req = req + "\x03" + chr(len(self.server[0])) + self.server[0]
#			else:
#				# Resolve locally
#				self.ipaddr = socket.inet_aton(socket.gethostbyname(self.server[0]))
#				req = req + "\x01" + ipaddr
		req = req + struct.pack(">H",self.server[1])
		self.onreceive(self._on_req_sent)
		self.send(req)

	def _on_req_sent(self, reply):
		if reply is None:
			return
		if len(reply) < 10:
			log.error('Invalid proxy reply')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[0] != '\x05':
			log.error('Invalid proxy reply')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[1] != "\x00":
			# Connection failed
			self._owner.disconnected()
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
			self.on_proxy_failure(txt)
			return
		# Get the bound address/port
		elif reply[3] == "\x01":
			begin, end = 3, 7
		elif reply[3] == "\x03":
			begin, end = 4, 4 + reply[4]
		else:
			log.error('Invalid proxy reply')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return

		if self.on_connect_proxy:
			self.on_connect_proxy()




