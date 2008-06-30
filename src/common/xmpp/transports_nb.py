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
import struct
from simplexml import ustr
from client import PlugIn
from idlequeue import IdleObject
from protocol import *

import sys
import os
import errno
import time

import traceback
import threading

import logging
log = logging.getLogger('gajim.c.x.transports_nb')
consoleloghandler = logging.StreamHandler()
consoleloghandler.setLevel(logging.DEBUG)
consoleloghandler.setFormatter(
	logging.Formatter('%(levelname)s: %(message)s')
)
log.setLevel(logging.DEBUG)
log.addHandler(consoleloghandler)
log.propagate = False


def urisplit(self, uri):
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
		



# I don't need to load gajim.py just because of few TLS variables, so I changed
# %s/common\.gajim\.DATA_DIR/\'\.\.\/data\'/c
# %s/common\.gajim\.MY_CACERTS/\'\%s\/\.gajim\/cacerts\.pem\' \% os\.environ\[\'HOME\'\]/c

# To change it back do:
# %s/\'\.\.\/data\'/common\.gajim\.DATA_DIR/c
# %s/\'%s\/\.gajim\/cacerts\.pem\'\ %\ os\.environ\[\'HOME\'\]/common\.gajim\.MY_CACERTS/c
# TODO: make the paths configurable - as constructor parameters or sth


# import common.gajim

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
CONNECTING ='CONNECTING'  
CONNECTED ='CONNECTED' 
DISCONNECTING ='DISCONNECTING' 

class NonBlockingTcp(PlugIn, IdleObject):
	'''
	Non-blocking TCP socket wrapper
	'''
	def __init__(self, on_disconnect):
		'''
		Class constructor.
		'''

		PlugIn.__init__(self)
		IdleObject.__init__(self)

		self.on_disconnect = on_disconnect

		self.on_connect = None
		self.on_connect_failure = None
		self.sock = None
		self.idlequeue = None
		self.on_receive = None
		self.DBG_LINE='socket'
		self.state = DISCONNECTED

		# writable, readable  -  keep state of the last pluged flags
		# This prevents replug of same object with the same flags
		self.writable = True
		self.readable = False

		# queue with messages to be send 
		self.sendqueue = []

		# time to wait for SOME stanza to come and then send keepalive
		self.sendtimeout = 0

		# in case we want to something different than sending keepalives
		self.on_timeout = None
		
		# bytes remained from the last send message
		self.sendbuff = ''
		self._exported_methods=[self.disconnect, self.onreceive, self.set_send_timeout, 
			self.set_timeout, self.remove_timeout]

	def plugin(self, owner):
		owner.Connection=self
		print 'plugin called'
		self.idlequeue = owner.idlequeue

	def plugout(self):
		self._owner.Connection = None
		self._owner = None


	def get_fd(self):
		try:
			tmp = self._sock.fileno()
			return tmp
		except:
			return 0

	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		'''
		Creates and connects socket to server and port defined in conn_5tupe which
		should be list item returned from getaddrinfo.
		:param conn_5tuple: 5-tuple returned from getaddrinfo
		:param on_connect: callback called on successful tcp connection
		:param on_connect_failure: callback called on failure when estabilishing tcp 
			connection
		'''
		self.on_connect = on_connect
		self.on_connect_failure = on_connect_failure
		(self.server, self.port) = conn_5tuple[4]
		log.debug('NonBlocking Connect :: About tot connect to %s:%s' % conn_5tuple[4])
		try:
			self._sock = socket.socket(*conn_5tuple[:3])
		except socket.error, (errnum, errstr):
			on_connect_failure('NonBlockingTcp: Error while creating socket: %s %s' % (errnum, errstr))
			return

		self._send = self._sock.send
		self._recv = self._sock.recv
		self.fd = self._sock.fileno()
		self.idlequeue.plug_idle(self, True, False)

		errnum = 0
		''' variable for errno symbol that will be found from exception raised from connect() '''
	
		# set timeout for TCP connecting - if nonblocking connect() fails, pollend
		# is called. If if succeeds pollout is called.
		self.idlequeue.set_read_timeout(self.get_fd(), CONNECT_TIMEOUT_SECONDS)

		try: 
			self._sock.setblocking(False)
			self._sock.connect((self.server,self.port))
		except Exception, (errnum, errstr):
			pass

		if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
			# connecting in progress
			self.set_state(CONNECTING)
			log.debug('After connect. "%s" raised => CONNECTING' % errstr)
			# on_connect/failure will be called from self.pollin/self.pollout
			return
		elif errnum in (0, 10056, errno.EISCONN):
			# already connected - this branch is very unlikely, nonblocking connect() will
			# return EINPROGRESS exception in most cases. When here, we don't need timeout
			# on connected descriptor and success callback can be called.
			log.debug('After connect. "%s" raised => CONNECTED' % errstr)
			self._on_connect(self)
			return

		# if there was some other error, call failure callback and unplug transport
		# which will also remove read_timeouts for descriptor
		self._on_connect_failure('Exception while connecting to %s:%s - %s %s' % 
			(self.server, self.port, errnum, errstr))
			
	def _on_connect(self, data):
		''' preceeds call of on_connect callback '''
		self.set_state(CONNECTED)
		self.idlequeue.remove_timeout(self.get_fd())
		self.on_connect()


	def set_state(self, newstate):
		assert(newstate in [DISCONNECTED, CONNECTING, CONNECTED, DISCONNECTING])
		if (self.state, newstate) in [(CONNECTING, DISCONNECTING), (DISCONNECTED, DISCONNECTING)]:
			log.info('strange move: %s -> %s' % (self.state, newstate))
		self.state = newstate


	def _on_connect_failure(self,err_message):
		''' preceeds call of on_connect_failure callback '''
		# In case of error while connecting we need to close socket
		# but we don't want to call DisconnectHandlers from client,
		# thus the do_callback=False
		self.disconnect(do_callback=False)
		self.on_connect_failure(err_message=err_message)

		

	def pollin(self):
		'''called when receive on plugged socket is possible '''
		log.debug('pollin called, state == %s' % self.state)
		self._do_receive() 

	def pollout(self):
		'''called when send to plugged socket is possible'''
		log.debug('pollout called, state == %s' % self.state)

		if self.state==CONNECTING:
			self._on_connect(self)
			return
		self._do_send()

	def pollend(self):
		log.debug('pollend called, state == %s' % self.state)

		if self.state==CONNECTING:
			self._on_connect_failure('Error during connect to %s:%s' % 
				(self.server, self.port))
		else :
			self.disconnect()

	def disconnect(self, do_callback=True):
		if self.state == DISCONNECTED:
			return
		self.idlequeue.unplug_idle(self.get_fd())
		try:
			self._sock.shutdown(socket.SHUT_RDWR)
			self._sock.close()
		except socket.error, (errnum, errstr):
			log.error('Error disconnecting a socket: %s %s' % (errnum,errstr))
		self.set_state(DISCONNECTED)
		if do_callback:
			# invoke callback given in __init__
			self.on_disconnect()

	def read_timeout(self):
		'''
		Implemntation of IdleObject function called on timeouts from IdleQueue.
		'''
		log.debug('read_timeout called, state == %s' % self.state)
		if self.state==CONNECTING:
			# if read_timeout is called during connecting, connect() didn't end yet
			# thus we have to call the tcp failure callback
			self._on_connect_failure('Error during connect to %s:%s' % 
				(self.server, self.port))
		else:
			if self.on_timeout:
				self.on_timeout()
			self.renew_send_timeout()

	def renew_send_timeout(self):
		if self.on_timeout and self.sendtimeout > 0:
			self.set_timeout(self.sendtimeout)
		else:
			self.remove_timeout()
	
	def set_send_timeout(self, timeout, on_timeout):
		self.sendtimeout = timeout
		if self.sendtimeout > 0:
			self.on_timeout = on_timeout
		else:
			self.on_timeout = None
	
	def set_timeout(self, timeout):
		if self.state in [CONNECTING, CONNECTED] and self.get_fd() > 0:
			self.idlequeue.set_read_timeout(self.get_fd(), timeout)

	def remove_timeout(self):
		if self.get_fd():
			self.idlequeue.remove_timeout(self.get_fd())

	def send(self, raw_data, now=False):
		'''Append raw_data to the queue of messages to be send. 
		If supplied data is unicode string, encode it to utf-8.
		'''

		if self.state not in [CONNECTED, DISCONNECTING]:
			log.error('Trying to send %s when transport is %s.' % 
				(raw_data, self.state))
			return
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
		self._plug_idle()



	def _plug_idle(self):
		# readable if socket is connected or disconnecting
		readable = self.state != DISCONNECTED
		# writeable if sth to send
		if self.sendqueue or self.sendbuff:
			writable = True
		else:
			writable = False
		print 'About to plug fd %d, W:%s, R:%s' % (self.get_fd(), writable, readable)
		if self.writable != writable or self.readable != readable:
			print 'Really plugging fd %d, W:%s, R:%s' % (self.get_fd(), writable, readable)
			self.idlequeue.plug_idle(self, writable, readable)
		else: 
			print 'Not plugging - is already plugged'



	def _do_send(self):
		if not self.sendbuff:
			if not self.sendqueue:
				return None # nothing to send
			self.sendbuff = self.sendqueue.pop(0)
		try:
			send_count = self._send(self.sendbuff)
			if send_count:
				sent_data = self.sendbuff[:send_count]
				self.sendbuff = self.sendbuff[send_count:]
				self._plug_idle()
				self._raise_event(DATA_SENT, sent_data)

		except socket.error, e:
			log.error('_do_send:', exc_info=True)
			traceback.print_exc()
			self.disconnect()

	def _raise_event(self, event_type, data):
		if data and data.strip():
			log.debug('raising event from transport: %s %s' % (event_type,data))
			if hasattr(self._owner, 'Dispatcher'):
				self._owner.Dispatcher.Event('', event_type, data)

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
			log.debug("_do_receive: got %s:" % received , exc_info=True)
		
		if received == '':
			errnum = ERR_DISCONN
			errstr = "Connection closed unexpectedly"

		if errnum in (ERR_DISCONN, errno.ECONNRESET, errno.ENOTCONN, errno.ESHUTDOWN):
			# ECONNRESET - connection you are trying to access has been reset by the peer
			# ENOTCONN - Transport endpoint is not connected
			# ESHUTDOWN  - shutdown(2) has been called on a socket to close down the
			# sending end of the transmision, and then data was attempted to be sent
			log.error("Connection to %s lost: %s %s" % ( self.server, errnum, errstr))
			self.disconnect()
			return

		if received is None:
			# in case of some other exception
			# FIXME: is this needed?? 
			if errnum != 0:
				self.DEBUG(self.DBG, errstr, 'error')
				log.error("CConnection to %s lost: %s %s" % (self.server, errnum, errstr))
				if not errors_only and self.state in [CONNECTING, CONNECTED]:
					self.pollend(retry=True)
				return
			received = ''

		# we have received some bytes, stop the timeout!
		self.renew_send_timeout()
		if self.on_receive:
			self._raise_event(DATA_RECEIVED, received)
			self._on_receive(received)
		else:
			# This should never happen, so we need the debug
			log.error('SOCKET Unhandled data received: %s' % received)
			self.disconnect()

	def _on_receive(self, data):
		# Overriding this method allows modifying received data before it is passed
		# to callback. 
		self.on_receive(data)


class NonBlockingHttpBOSH(NonBlockingTcp):
	'''
	Socket wrapper that makes HTTP message out of send data and peels-off 
	HTTP headers from incoming messages
	'''

	def __init__(self, bosh_uri, bosh_port, on_disconnect):
		self.bosh_protocol, self.bosh_host, self.bosh_path = self.urisplit(bosh_uri)
		if self.bosh_protocol is None:
			self.bosh_protocol = 'http'
		if self.bosh_path == '':
			bosh_path = '/'
		self.bosh_port = bosh_port
		
	def send(self, raw_data, now=False):

		NonBlockingTcp.send(
			self,
			self.build_http_message(raw_data),
			now)

	def _on_receive(self,data):
		'''Preceeds pass of received data to Client class. Gets rid of HTTP headers
		and checks them.'''
		statusline, headers, httpbody = self.parse_http_message(data)
		if statusline[1] != '200':
			log.error('HTTP Error: %s %s' % (statusline[1], statusline[2]))
			self.disconnect()
		self.on_receive(httpbody)
	
		
	def build_http_message(self, httpbody):
		'''
		Builds bosh http message with given body.
		Values for headers and status line fields are taken from class variables.
		)  
		'''
		headers = ['POST %s HTTP/1.1' % self.bosh_path,
			'Host: %s:%s' % (self.bosh_host, self.bosh_port),
			'Content-Type: text/xml; charset=utf-8',
			'Content-Length: %s' % len(str(httpbody)),
			'\r\n']
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
		(header, httpbody) = message.split('\n\n')
		header = header.split('\n')
		statusline = header[0].split(' ')
		header = header[1:]
		headers = {}
		for dummy in header:
			row = dummy.split(' ',1)
			headers[row[0][:-1]] = row[1]
		return (statusline, headers, httpbody)


USE_PYOPENSSL = False

try:
	#raise ImportError("Manually disabled PyOpenSSL")
	import OpenSSL.SSL
	import OpenSSL.crypto
	USE_PYOPENSSL = True
	log.info("PyOpenSSL loaded")
except ImportError:
	log.debug("Import of PyOpenSSL failed:", exc_info=True)

	# FIXME: Remove these prints before release, replace with a warning dialog.
	print >> sys.stderr, "=" * 79
	print >> sys.stderr, "PyOpenSSL not found, falling back to Python builtin SSL objects (insecure)."
	print >> sys.stderr, "=" * 79


def torf(cond, tv, fv):
	if cond: return tv
	return fv

def gattr(obj, attr, default=None):
	try:
		return getattr(obj, attr)
	except:
		return default

class SSLWrapper:
	class Error(IOError):
		def __init__(self, sock=None, exc=None, errno=None, strerror=None, peer=None):
			self.parent = IOError

			errno = errno or gattr(exc, 'errno')
			strerror = strerror or gattr(exc, 'strerror') or gattr(exc, 'args')
			if not isinstance(strerror, basestring): strerror = repr(strerror)

			self.sock = sock
			self.exc = exc
			self.peer = peer
			self.exc_name = None
			self.exc_args = None
			self.exc_str = None
			self.exc_repr = None

			if self.exc is not None:
				self.exc_name = str(self.exc.__class__)
				self.exc_args = gattr(self.exc, 'args')
				self.exc_str = str(self.exc)
				self.exc_repr = repr(self.exc)
				if not errno:
					try:
						if isinstance(exc, OpenSSL.SSL.SysCallError):
							if self.exc_args[0] > 0:
								errno = self.exc_args[0]
							strerror = self.exc_args[1]
					except: pass

			self.parent.__init__(self, errno, strerror)

			if self.peer is None and sock is not None:
				try:
					ppeer = self.sock.getpeername()
					if len(ppeer) == 2 and isinstance(ppeer[0], basestring) \
					and isinstance(ppeer[1], int):
						self.peer = ppeer
				except: pass

		def __str__(self):
			s = str(self.__class__)
			if self.peer: s += " for %s:%d" % self.peer
			if self.errno is not None: s += ": [Errno: %d]" % self.errno
			if self.strerror: s += " (%s)" % self.strerror
			if self.exc_name:
				s += ", Caused by %s" % self.exc_name
				if self.exc_str:
					if self.strerror: s += "(%s)" % self.exc_str
					else: s += "(%s)" % str(self.exc_args)
			return s

	def __init__(self, sslobj, sock=None):
		self.sslobj = sslobj
		self.sock = sock
		log.debug("%s.__init__ called with %s", self.__class__, sslobj)

	def recv(self, data, flags=None):
		""" Receive wrapper for SSL object

		We can return None out of this function to signal that no data is
		available right now. Better than an exception, which differs
		depending on which SSL lib we're using. Unfortunately returning ''
		can indicate that the socket has been closed, so to be sure, we avoid
		this by returning None. """

		raise NotImplementedException()

	def send(self, data, flags=None, now = False):
		raise NotImplementedException()

class PyOpenSSLWrapper(SSLWrapper):
	'''Wrapper class for PyOpenSSL's recv() and send() methods'''

	def __init__(self, *args):
		self.parent = SSLWrapper
		self.parent.__init__(self, *args)

	def is_numtoolarge(self, e):
		t = ('asn1 encoding routines', 'a2d_ASN1_OBJECT', 'first num too large')
		return isinstance(e.args, (list, tuple)) and len(e.args) == 1 and \
		isinstance(e.args[0], (list, tuple)) and len(e.args[0]) == 2 and \
		e.args[0][0] == e.args[0][1] == t

	def recv(self, bufsize, flags=None):
		retval = None
		try:
			if flags is None: retval = self.sslobj.recv(bufsize)
			else:		  retval = self.sslobj.recv(bufsize, flags)
		except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.WantWriteError), e:
			pass
			# log.debug("Recv: " + repr(e))
		except OpenSSL.SSL.SysCallError, e:
			log.debug("Recv: Got OpenSSL.SSL.SysCallError: " + repr(e), exc_info=True)
			#traceback.print_exc()
			raise SSLWrapper.Error(self.sock or self.sslobj, e)
		except OpenSSL.SSL.Error, e:
			if self.is_numtoolarge(e):
				# warn, but ignore this exception
				log.warning("Recv: OpenSSL: asn1enc: first num too large (ignored)")
			else:
				log.debug("Recv: Caught OpenSSL.SSL.Error:", exc_info=True)
				#traceback.print_exc()
				#print "Current Stack:"
				#traceback.print_stack()
				raise SSLWrapper.Error(self.sock or self.sslobj, e)
		return retval

	def send(self, data, flags=None, now = False):
		try:
			if flags is None: return self.sslobj.send(data)
			else:		  return self.sslobj.send(data, flags)
		except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.WantWriteError), e:
			#log.debug("Send: " + repr(e))
			time.sleep(0.1) # prevent 100% CPU usage
		except OpenSSL.SSL.SysCallError, e:
			log.error("Send: Got OpenSSL.SSL.SysCallError: " + repr(e), exc_info=True)
			#traceback.print_exc()
			raise SSLWrapper.Error(self.sock or self.sslobj, e)
		except OpenSSL.SSL.Error, e:
			if self.is_numtoolarge(e):
				# warn, but ignore this exception
				log.warning("Send: OpenSSL: asn1enc: first num too large (ignored)")
			else:
				log.error("Send: Caught OpenSSL.SSL.Error:", exc_info=True)
				#traceback.print_exc()
				#print "Current Stack:"
				#traceback.print_stack()
				raise SSLWrapper.Error(self.sock or self.sslobj, e)
		return 0

class StdlibSSLWrapper(SSLWrapper):
	'''Wrapper class for Python's socket.ssl read() and write() methods'''

	def __init__(self, *args):
		self.parent = SSLWrapper
		self.parent.__init__(self, *args)

	def recv(self, bufsize, flags=None):
		# we simply ignore flags since ssl object doesn't support it
		try:
			return self.sslobj.read(bufsize)
		except socket.sslerror, e:
			#log.debug("Recv: Caught socket.sslerror:", exc_info=True)
			#traceback.print_exc()
			if e.args[0] not in (socket.SSL_ERROR_WANT_READ, socket.SSL_ERROR_WANT_WRITE):
				raise SSLWrapper.Error(self.sock or self.sslobj, e)
		return None

	def send(self, data, flags=None, now = False):
		# we simply ignore flags since ssl object doesn't support it
		try:
			return self.sslobj.write(data)
		except socket.sslerror, e:
			#log.debug("Send: Caught socket.sslerror:", exc_info=True)
			#traceback.print_exc()
			if e.args[0] not in (socket.SSL_ERROR_WANT_READ, socket.SSL_ERROR_WANT_WRITE):
				raise SSLWrapper.Error(self.sock or self.sslobj, e)
		return 0


class NonBlockingTLS(PlugIn):
	''' TLS connection used to encrypts already estabilished tcp connection.'''

	# from ssl.h (partial extract)
	ssl_h_bits = {	"SSL_ST_CONNECT": 0x1000, "SSL_ST_ACCEPT": 0x2000, 
			"SSL_CB_LOOP": 0x01, "SSL_CB_EXIT": 0x02, 
			"SSL_CB_READ": 0x04, "SSL_CB_WRITE": 0x08, 
			"SSL_CB_ALERT": 0x4000, 
			"SSL_CB_HANDSHAKE_START": 0x10, "SSL_CB_HANDSHAKE_DONE": 0x20}

	def PlugIn(self, owner, on_tls_success, on_tls_failure, now=0):
		''' If the 'now' argument is true then starts using encryption immidiatedly.
			If 'now' in false then starts encryption as soon as TLS feature is
			declared by the server (if it were already declared - it is ok).
		'''
		if owner.__dict__.has_key('NonBlockingTLS'): 
			return  # Already enabled.
		PlugIn.PlugIn(self, owner)
		DBG_LINE='NonBlockingTLS'
		self.on_tls_success = on_tls_success
		self.on_tls_faliure = on_tls_failure
		if now:
			try:
				res = self._startSSL()
			except Exception, e:
				log.error("PlugIn: while trying _startSSL():", exc_info=True)
				#traceback.print_exc()
				self._owner.socket.pollend()
				return
			on_tls_success()
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
		# if dispatcher is not plugged we cannot (un)register handlers
		if self._owner.__dict__.has_key('Dispatcher'):
			self._owner.UnregisterHandler('features', self.FeaturesHandler,xmlns=NS_STREAMS)
			self._owner.Dispatcher.PlugOut()
		self._owner = None

	def FeaturesHandler(self, conn, feats):
		''' Used to analyse server <features/> tag for TLS support.
			If TLS is supported starts the encryption negotiation. Used internally '''
		if not feats.getTag('starttls', namespace=NS_TLS):
			self.DEBUG("TLS unsupported by remote server.", 'warn')
			self.on_tls_failure("TLS unsupported by remote server.")
			return
		self.DEBUG("TLS supported by remote server. Requesting TLS start.", 'ok')
		self._owner.RegisterHandlerOnce('proceed', self.StartTLSHandler, xmlns=NS_TLS)
		self._owner.RegisterHandlerOnce('failure', self.StartTLSHandler, xmlns=NS_TLS)
		self._owner.send('<starttls xmlns="%s"/>' % NS_TLS)
		raise NodeProcessed

	def _dumpX509(self, cert, stream=sys.stderr):
		print >> stream, "Digest (SHA-1):", cert.digest("sha1")
		print >> stream, "Digest (MD5):", cert.digest("md5")
		print >> stream, "Serial #:", cert.get_serial_number()
		print >> stream, "Version:", cert.get_version()
		print >> stream, "Expired:", torf(cert.has_expired(), "Yes", "No")
		print >> stream, "Subject:"
		self._dumpX509Name(cert.get_subject(), stream)
		print >> stream, "Issuer:"
		self._dumpX509Name(cert.get_issuer(), stream)
		self._dumpPKey(cert.get_pubkey(), stream)

	def _dumpX509Name(self, name, stream=sys.stderr):
		print >> stream, "X509Name:", str(name)

	def _dumpPKey(self, pkey, stream=sys.stderr):
		typedict = {OpenSSL.crypto.TYPE_RSA: "RSA", OpenSSL.crypto.TYPE_DSA: "DSA"}
		print >> stream, "PKey bits:", pkey.bits()
		print >> stream, "PKey type: %s (%d)" % (typedict.get(pkey.type(), "Unknown"), pkey.type())

	def _startSSL(self):
		''' Immidiatedly switch socket to TLS mode. Used internally.'''
		log.debug("_startSSL called")
		if USE_PYOPENSSL: return self._startSSL_pyOpenSSL()
		return self._startSSL_stdlib()

	def _startSSL_pyOpenSSL(self):
		#log.debug("_startSSL_pyOpenSSL called, thread id: %s", str(thread.get_ident()))
		log.debug("_startSSL_pyOpenSSL called")
		tcpsock = self._owner.Connection
		# FIXME: should method be configurable?
		tcpsock._sslContext = OpenSSL.SSL.Context(OpenSSL.SSL.TLSv1_METHOD)
		#tcpsock._sslContext = OpenSSL.SSL.Context(OpenSSL.SSL.SSLv23_METHOD)
		tcpsock.ssl_errnum = 0
		tcpsock._sslContext.set_verify(OpenSSL.SSL.VERIFY_PEER, self._ssl_verify_callback)
		cacerts = os.path.join('../data', 'other', 'cacerts.pem')
		try:
			tcpsock._sslContext.load_verify_locations(cacerts)
		except:
			log.warning('Unable to load SSL certificats from file %s' % \
				os.path.abspath(cacerts))
		# load users certs
		if os.path.isfile('%s/.gajim/cacerts.pem' % os.environ['HOME']):
			store = tcpsock._sslContext.get_cert_store()
			f = open('%s/.gajim/cacerts.pem' % os.environ['HOME'])
			lines = f.readlines()
			i = 0
			begin = -1
			for line in lines:
				if 'BEGIN CERTIFICATE' in line:
					begin = i
				elif 'END CERTIFICATE' in line and begin > -1:
					cert = ''.join(lines[begin:i+2])
					try:
						X509cert = OpenSSL.crypto.load_certificate(
							OpenSSL.crypto.FILETYPE_PEM, cert)
						store.add_cert(X509cert)
					except OpenSSL.crypto.Error, exception_obj:
						log.warning('Unable to load a certificate from file %s: %s' %\
							('%s/.gajim/cacerts.pem' % os.environ['HOME'], exception_obj.args[0][0][2]))
					except:
						log.warning(
							'Unknown error while loading certificate from file %s' % \
							'%s/.gajim/cacerts.pem' % os.environ['HOME'])
					begin = -1
				i += 1
		tcpsock._sslObj = OpenSSL.SSL.Connection(tcpsock._sslContext, tcpsock._sock)
		tcpsock._sslObj.set_connect_state() # set to client mode

		wrapper = PyOpenSSLWrapper(tcpsock._sslObj)
		tcpsock._recv = wrapper.recv
		tcpsock._send = wrapper.send

		log.debug("Initiating handshake...")
		# FIXME: Figure out why _connect_success is called before the
		# SSL handshake is completed in STARTTLS mode. See #2838.
		tcpsock._sslObj.setblocking(True)
		try:
			self.starttls='in progress'
			tcpsock._sslObj.do_handshake()
		except:
			log.error('Error while TLS handshake: ', exc_info=True)
			self.on_tls_failure('Error while TLS Handshake')
			return
		tcpsock._sslObj.setblocking(False)
		log.debug("Synchronous handshake completed")
		#log.debug("Async handshake started...")

		# fake it, for now
		self.starttls='success'

	def _startSSL_stdlib(self):
		log.debug("_startSSL_stdlib called")
		tcpsock=self._owner.Connection
		tcpsock._sock.setblocking(True)
		tcpsock._sslObj = socket.ssl(tcpsock._sock, None, None)
		tcpsock._sock.setblocking(False)
		tcpsock._sslIssuer = tcpsock._sslObj.issuer()
		tcpsock._sslServer = tcpsock._sslObj.server()
		wrapper = StdlibSSLWrapper(tcpsock._sslObj, tcpsock._sock)
		tcpsock._recv = wrapper.recv
		tcpsock._send = wrapper.send
		self.starttls='success'

	def _ssl_verify_callback(self, sslconn, cert, errnum, depth, ok):
		# Exceptions can't propagate up through this callback, so print them here.
		try:
			self._owner.Connection.ssl_fingerprint_sha1 = cert.digest('sha1')
			if errnum == 0:
				return True
			self._owner.Connection.ssl_errnum = errnum
			self._owner.Connection.ssl_cert_pem = OpenSSL.crypto.dump_certificate(
				OpenSSL.crypto.FILETYPE_PEM, cert)
			return True
		except:
			log.error("Exception caught in _ssl_info_callback:", exc_info=True)
			traceback.print_exc() # Make sure something is printed, even if log is disabled.

	def StartTLSHandler(self, conn, starttls):
		''' Handle server reply if TLS is allowed to process. Behaves accordingly.
			Used internally.'''
		if starttls.getNamespace() <> NS_TLS: 
			self.on_tls_failure('Unknown namespace: %s' % starttls.getNamespace())
			return
		self.starttls = starttls.getName()
		if self.starttls == 'failure':
			self.on_tls_failure('TLS <failure>  received: %s' % self.starttls)
			return
		self.DEBUG('Got starttls proceed response. Switching to TLS/SSL...','ok')
		try:
			self._startSSL()
		except Exception, e:
			log.error("StartTLSHandler:", exc_info=True)
			self.on_tls_failure('in StartTLSHandler')
			#traceback.print_exc()
			return
		self._owner.Dispatcher.PlugOut()
		self.on_tls_success()
		#dispatcher_nb.Dispatcher().PlugIn(self._owner)

class NBProxySocket(NonBlockingTcp):
	'''
	Interface for proxy socket wrappers - when tunnneling XMPP over proxies,
	some connecting process usually has to be done before opening stream.
	'''
	def __init__(self, on_disconnect, xmpp_server, proxy_creds=(None,None)):
		self.proxy_user, self.proxy_pass = proxy_creds
		self.xmpp_server = xmpp_server
		NonBlockingTcp.__init__(self, on_disconnect)
		

	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		'''
		connect method is extended by proxy credentials and xmpp server hostname
		and port because those are needed for 
		The idea is to insert Proxy-specific mechanism after TCP connect and 
		before XMPP stream opening (which is done from client).
		'''

		self.after_proxy_connect = on_connect
		
		NonBlockingTcp.connect(self,
				conn_5tuple=conn_5tuple,
				on_connect =self._on_tcp_connect,
				on_connect_failure =on_connect_failure)

	def _on_tcp_connect(self):
		pass



class NBHTTPProxySocket(NBProxySocket):
	''' This class can be used instead of NonBlockingTcp
	HTTP (CONNECT) proxy connection class. Allows to use HTTP proxies like squid with
	(optionally) simple authentication (using login and password). 
	'''
		
	def _on_tcp_connect(self):
		''' Starts connection. Connects to proxy, supplies login and password to it
			(if were specified while creating instance). Instructs proxy to make
			connection to the target server. Returns non-empty sting on success. '''
		log.debug('Proxy server contacted, performing authentification')
		connector = ['CONNECT %s:%s HTTP/1.0' % self.xmpp_server,
			'Proxy-Connection: Keep-Alive',
			'Pragma: no-cache',
			'Host: %s:%s' % self.xmpp_server,
			'User-Agent: HTTPPROXYsocket/v0.1']
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
		self.onreceive(self._on_proxy_auth)
	
	def _on_proxy_auth(self, reply):
		if self.reply.find('\n\n') == -1:
			if reply is None:
				self._on_connect_failure('Proxy authentification failed')
				return
			if reply.find('\n\n') == -1:
				self.reply += reply.replace('\r', '')
				self._on_connect_failure('Proxy authentification failed')
				return
		log.debug('Authentification successfull. Jabber server contacted.')
		self._on_connect(self)


class NBSOCKS5ProxySocket(NBProxySocket):
	'''SOCKS5 proxy connection class. Uses TCPsocket as the base class
		redefines only connect method. Allows to use SOCKS5 proxies with
		(optionally) simple authentication (only USERNAME/PASSWORD auth). 
	'''
	# TODO: replace DEBUG with ordinrar logging, replace on_proxy_failure() with
	#	_on_connect_failure, at the end call _on_connect()

	def _on_tcp_connect(self):
		self.DEBUG('Proxy server contacted, performing authentification', 'start')
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
			self.DEBUG('Invalid proxy reply', 'error')
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
				self.DEBUG('Authentification to proxy impossible: no acceptable '
					'auth method', 'error')
				self._owner.disconnected()
				self.on_proxy_failure('Authentification to proxy impossible: no '
					'acceptable authentification method')
				return
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return

	def _on_proxy_auth(self, reply):
		if reply is None:
			return
		if len(reply) != 2:
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[0] != '\x01':
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[1] != '\x00':
			self.DEBUG('Authentification to proxy failed', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Authentification to proxy failed')
			return
		self.DEBUG('Authentification successfull. Jabber server contacted.','ok')
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
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if reply[0] != '\x05':
			self.DEBUG('Invalid proxy reply', 'error')
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
			self.DEBUG(txt, 'error')
			self.on_proxy_failure(txt)
			return
		# Get the bound address/port
		elif reply[3] == "\x01":
			begin, end = 3, 7
		elif reply[3] == "\x03":
			begin, end = 4, 4 + reply[4]
		else:
			self.DEBUG('Invalid proxy reply', 'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return

		if self.on_connect_proxy:
			self.on_connect_proxy()

	def DEBUG(self, text, severity):
		''' Overwrites DEBUG tag to allow debug output be presented as "CONNECTproxy".'''
		return self._owner.DEBUG(DBG_CONNECT_PROXY, text, severity)
