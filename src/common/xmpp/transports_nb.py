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
from transports import * 

import sys
import os
import errno
import time

import traceback
import thread

import logging
log = logging.getLogger('gajim.c.x.transports_nb')

import common.gajim

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

# timeout to connect to the server socket, it doesn't include auth 
CONNECT_TIMEOUT_SECONDS = 30

# how long to wait for a disconnect to complete
DISCONNECT_TIMEOUT_SECONDS = 10

# size of the buffer which reads data from server
# if lower, more stanzas will be fragmented and processed twice
RECV_BUFSIZE = 32768 # 2x maximum size of ssl packet, should be plenty
#RECV_BUFSIZE = 16 # FIXME: (#2634) gajim breaks with this setting: it's inefficient but should work.

def torf(cond, tv, fv):
	if cond: return tv
	return fv

def gattr(obj, attr, default=None):
	try:
		return getattr(obj, attr)
	except Exception:
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
		self._exported_methods=[self.send, self.disconnect, self.onreceive,
			self.set_send_timeout, self.set_send_timeout2, self.start_disconnect,
			self.set_timeout, self.remove_timeout]
		self._server = server
		self._hostfqdn = server[0]
		self.on_connect  = on_connect
		self.on_connect_failure = on_connect_failure
		self.on_receive = None
		self.on_disconnect = None
		self.printed_error = False
		
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
		self.sendtimeout2 = 0
		
		# in case we want to something different than sending keepalives
		self.on_timeout = None
		self.on_timeout2 = None
		
		# writable, readable  -  keep state of the last pluged flags
		# This prevents replug of same object with the same flags
		self.writable = True
		self.readable = False
		self.ais = None
	
	def plugin(self, owner):
		''' Fire up connection. Return non-empty string on success.
			Also registers self.disconnected method in the owner's dispatcher.
			Called internally. '''
		self.idlequeue = owner.idlequeue
		self.printed_error = False
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

	def read_timeout2(self):
		if self.on_timeout2:
			self.on_timeout2()
		self.renew_send_timeout2()

	def connect(self,server=None, proxy = None, secure = None):
		''' Try to establish connection. '''
		if not server:
			server=self._server
		else: 
			self._server = server
		self._hostfqdn = self._server[0]
		self.printed_error = False
		self.state = 0
		try:
			if len(server) == 2 and type(server[0]) in (str, unicode) and not \
			self.ais:
				# FIXME: blocks here
				self.ais = socket.getaddrinfo(server[0],server[1],socket.AF_UNSPEC,socket.SOCK_STREAM)
				log.info('Found IPs: %s', self.ais)
			else:
				self.ais = (server,)
			self.connect_to_next_ip()
			return
		except socket.gaierror, e:
			log.info('Lookup failure for %s: %s[%s]', self.getName(), e[1], repr(e[0]), exc_info=True)
		except:
			log.error('Exception trying to connect to %s:', self.getName(), exc_info=True)

		if self.on_connect_failure:
			self.on_connect_failure()

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
			self._do_connect()
			return
		self._do_send()
	
	def plugout(self):
		''' Disconnect from the remote server and unregister self.disconnected method from
			the owner's dispatcher. '''
		self.disconnect()
		self._owner.Connection = None
		self._owner = None
	
	def pollin(self):
		self._do_receive() 
	
	def pollend(self, retry=False):
		if not self.printed_error:
			self.printed_error = True
			try: self._do_receive(errors_only=True)
			except: log.error("pollend: Got exception from _do_receive:", exc_info=True)
		conn_failure_cb = self.on_connect_failure
		self.disconnect()
		if conn_failure_cb:
			conn_failure_cb(retry)
		
	def disconnect(self):
		if self.state == -2: # already disconnected
			return
		self.state = -2
		self.sendqueue = None
		self.remove_timeout() 
		try:
			self._owner.disconnected()
		except Exception:
			pass
		self.idlequeue.unplug_idle(self.fd)
		sock = getattr(self, '_sock', None)
		if sock:
			try:
				sock.shutdown(socket.SHUT_RDWR)
			except socket.error, e:
				if e[0] != errno.ENOTCONN:
					log.error("Error shutting down socket for %s:", self.getName(), exc_info=True)
			try: sock.close()
			except: log.error("Error closing socket for %s:", self.getName(), exc_info=True)
		# socket descriptor cannot be (un)plugged anymore
		self.fd = -1
		if self.on_disconnect:
			self.on_disconnect()
		self.on_connect_failure = None
	
	def end_disconnect(self):
		''' force disconnect only if we are still trying to disconnect '''
		if self.state == -1:
			self.disconnect()
	
	def start_disconnect(self, to_send, on_disconnect):
		self.on_disconnect = on_disconnect

		# flush the sendqueue
		while self.sendqueue:
			self._do_send()

		self.sendqueue = []
		self.send(to_send)
		self.send('</stream:stream>')
		self.state = -1 # about to disconnect
		self.idlequeue.set_alarm(self.end_disconnect, DISCONNECT_TIMEOUT_SECONDS)
	
	def set_timeout(self, timeout):
		if self.state >= 0 and self.fd > 0:
			self.idlequeue.set_read_timeout(self.fd, timeout)

	def set_timeout2(self, timeout2):
		if self.state >= 0 and self.fd > 0:
			self.idlequeue.set_read_timeout(self.fd, timeout2, self.read_timeout2)
	
	def remove_timeout(self):
		if self.fd:
			self.idlequeue.remove_timeout(self.fd)
	
	def onreceive(self, recv_handler):
		''' Sets the on_receive callback. Do not confuse it with
		on_receive() method, which is the callback itself.
		
		If recv_handler==None, it tries to set that callback assuming that
		our owner also has a Dispatcher object plugged in, to its
		ProcessNonBlocking method.'''
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
		
	def _do_receive(self, errors_only=False):
		''' Reads all pending incoming data. Calls owner's disconnected() method if appropriate.'''
		ERR_DISCONN = -2 # Misc error signifying that we got disconnected
		ERR_OTHER = -1 # Other error
		received = None
		errnum = 0
		errtxt = 'No Error Set'
		try: 
			# get as many bites, as possible, but not more than RECV_BUFSIZE
			received = self._recv(RECV_BUFSIZE)
		except (socket.error, socket.herror, socket.gaierror), e:
			log.debug("_do_receive: got %s:", e.__class__, exc_info=True)
			#traceback.print_exc()
			#print "Current Stack:"
			#traceback.print_stack()
			errnum = e[0]
			errtxt = str(errnum) + ':' + e[1]
		except socket.sslerror, e:
			log.error("_do_receive: got unknown %s:", e.__class__, exc_info=True)
			#traceback.print_exc()
			#print "Current Stack:"
			#traceback.print_stack()
			errnum = ERR_OTHER
			errtxt = repr("socket.sslerror: " + e.args)
		except SSLWrapper.Error, e:
			log.debug("Caught: %s", str(e))
			errnum = gattr(e, 'errno', ERR_OTHER)
			if not errnum: errnum = ERR_OTHER # unset, but we must put a status
			errtxt = gattr(e, 'strerror') or repr(e.args)

		if received == '':
			errnum = ERR_DISCONN
			errtxt = "Connection closed unexpectedly"

		if errnum in (ERR_DISCONN, errno.ECONNRESET, errno.ENOTCONN, errno.ESHUTDOWN):
			log.info("Connection to %s lost: %s [%d]", self.getName(), errtxt, errnum)
			self.printed_error = True
			if not errors_only:
				self.pollend(retry=(errnum in (ERR_DISCONN, errno.ECONNRESET)))
			# don't process result, because it will raise an error
			return

		if received is None:
			if self.state == 0 and errnum == errno.ECONNREFUSED:
				# We tried to connect to a port that did't listen.
				log.error("Connection to %s refused: %s [%d]", self.getName(), errtxt, errnum)
				self.pollend(retry=True)
				return
			elif errnum != 0:
				self.DEBUG(errtxt, 'error')
				log.info("Connection to %s lost: %s [%d]", self.getName(), errtxt, errnum)
				self._owner.disconnected()
				self.printed_error = True
				if not errors_only and self.state >= 0:
					self.pollend(retry=True)
				return
			received = ''

		if errors_only or self.state < 0:
			return

		# we have received some bites, stop the timeout!
		self.remove_timeout()
		self.renew_send_timeout()
		self.renew_send_timeout2()
		if self.on_receive:
			if received.strip():
				log.info("Got: %s", received)
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
						self.idlequeue.unplug_idle(self.fd)
						self._on_send()
						self.disconnect()
						return
					# we are not waiting for write 
					self._plug_idle()
				self._on_send()
		except socket.error, e:
			if e[0] == socket.SSL_ERROR_WANT_WRITE:
				return True		
			log.error("_do_send:", exc_info=True)
			#traceback.print_exc()
			if self.state < 0:
				self.disconnect()
				return
			if self._on_send_failure:
				self._on_send_failure()
				return
		return True

	def connect_to_next_ip(self):
		if self.state != 0:
			return
		if len(self.ais) == 0:
			if self.on_connect_failure:
				self.on_connect_failure()
			return
		ai = self.ais.pop(0)
		log.info('Trying to connect to %s:%s', ai[4][0], ai[4][1])
		try:
			self._sock = socket.socket(*ai[:3])
			self._sock.setblocking(False)
			self._server=ai[4]
		except socket.error, e:
			errnum, errstr = e
			
			# Ignore "Socket already connected".
			# FIXME: This happens when we switch an already
			# connected socket to SSL (STARTTLS). Instead of
			# ignoring the error, the socket should only be
			# connected to once. See #2846 and #3396.
			workaround = (errno.EALREADY, 10056, 56)

			# 10035 - winsock equivalent of EINPROGRESS
			if errnum not in (errno.EINPROGRESS, 10035) + workaround:
				log.error('Could not connect to %s: %s [%s]', ai[4][0], errnum,
					errstr, exc_info=True)
				#traceback.print_exc()
				self.connect_to_next_ip()
				return
		self.fd = self._sock.fileno()
		self.idlequeue.plug_idle(self, True, False)
		self._send = self._sock.send
		self._recv = self._sock.recv
		self.set_timeout(CONNECT_TIMEOUT_SECONDS)
		self._do_connect()

	def _do_connect(self):
		errnum = 0
		if self.state != 0:
			return

		try:
			self._sock.connect(self._server)
		except Exception, ee:
			(errnum, errstr) = ee
		# in progress, or would block
		if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK):
			return
		# 10056  - already connected, only on win32
		# code 'WS*' is not available on GNU, so we use its numeric value
		elif errnum not in (0, 10056, errno.EISCONN):
			log.error('Could not connect to %s: %s [%s]', self._server[0], errnum,
				errstr)
			self.connect_to_next_ip()
			return
		self.remove_timeout()
		self._owner.Connection=self
		self.state = 1

		self._plug_idle()
		if self.on_connect:
			self.on_connect()
		self.on_connect = None

	def send(self, raw_data, now = False):
		'''Append raw_data to the queue of messages to be send. 
		If supplied data is unicode string, encode it to utf-8.
		'''

		if self.state <= 0:
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

	def set_send_timeout2(self, timeout2, on_timeout2):
		self.sendtimeout2 = timeout2
		if self.sendtimeout2 > 0:
			self.on_timeout2 = on_timeout2
		else:
			self.on_timeout2 = None

	def renew_send_timeout(self):
		if self.on_timeout and self.sendtimeout > 0:
			self.set_timeout(self.sendtimeout)

	def renew_send_timeout2(self):
		if self.on_timeout2 and self.sendtimeout2 > 0:
			self.set_timeout2(self.sendtimeout2)

	def getHost(self):
		''' Return the 'host' value that is connection is [will be] made to.'''
		return self._server[0]

	def getName(self):
		''' Return the server's name, or 'getHost()' if not available.'''
		retval = None
		try:
			retval = gattr(self._owner, 'name')
		except Exception:
			pass
		if retval: return retval
		return self.getHost()

	def getPort(self):
		''' Return the 'port' value that is connection is [will be] made to.'''
		return self._server[1]

class NonBlockingTLS(PlugIn):
	''' TLS connection used to encrypts already estabilished tcp connection.'''

	# from ssl.h (partial extract)
	ssl_h_bits = {	"SSL_ST_CONNECT": 0x1000, "SSL_ST_ACCEPT": 0x2000, 
			"SSL_CB_LOOP": 0x01, "SSL_CB_EXIT": 0x02, 
			"SSL_CB_READ": 0x04, "SSL_CB_WRITE": 0x08, 
			"SSL_CB_ALERT": 0x4000, 
			"SSL_CB_HANDSHAKE_START": 0x10, "SSL_CB_HANDSHAKE_DONE": 0x20}

	def PlugIn(self, owner, now=0, on_tls_start = None):
		''' If the 'now' argument is true then starts using encryption immidiatedly.
			If 'now' in false then starts encryption as soon as TLS feature is
			declared by the server (if it were already declared - it is ok).
		'''
		if 'NonBlockingTLS' in owner.__dict__: 
			return  # Already enabled.
		PlugIn.PlugIn(self, owner)
		DBG_LINE='NonBlockingTLS'
		self.on_tls_start = on_tls_start
		if now:
			try:
				res = self._startSSL()
			except Exception, e:
				log.error("PlugIn: while trying _startSSL():", exc_info=True)
				#traceback.print_exc()
				self._owner.socket.pollend()
				return
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
		# if dispatcher is not plugged we cannot (un)register handlers
		if 'Dispatcher' in self._owner.__dict__:
			self._owner.UnregisterHandler('features', self.FeaturesHandler,xmlns=NS_STREAMS)
			self._owner.Dispatcher.PlugOut()
		self._owner = None

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
		# Some gmail server don't support TLSv1, but only SSLv3, so use method
		# that allow SSLv2, v3 and TLSv1
		#tcpsock._sslContext = OpenSSL.SSL.Context(OpenSSL.SSL.TLSv1_METHOD)
		tcpsock._sslContext = OpenSSL.SSL.Context(OpenSSL.SSL.SSLv23_METHOD)
		tcpsock.ssl_errnum = 0
		tcpsock._sslContext.set_verify(OpenSSL.SSL.VERIFY_PEER, self._ssl_verify_callback)
		cacerts = os.path.join(common.gajim.DATA_DIR, 'other', 'cacerts.pem')
		try:
			tcpsock._sslContext.load_verify_locations(cacerts)
		except Exception:
			log.warning('Unable to load SSL certificats from file %s' % \
				os.path.abspath(cacerts))
		# load users certs
		if os.path.isfile(common.gajim.MY_CACERTS):
			store = tcpsock._sslContext.get_cert_store()
			f = open(common.gajim.MY_CACERTS)
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
							(common.gajim.MY_CACERTS, exception_obj.args[0][0][2]))
					except:
						log.warning(
							'Unknown error while loading certificate from file %s' % \
							common.gajim.MY_CACERTS)
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
		# Errors are handeled in _do_receive function
		except Exception:
			pass
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
		except Exception:
			log.error("Exception caught in _ssl_info_callback:", exc_info=True)
			traceback.print_exc() # Make sure something is printed, even if log is disabled.

	def StartTLSHandler(self, conn, starttls):
		''' Handle server reply if TLS is allowed to process. Behaves accordingly.
			Used internally.'''
		if starttls.getNamespace() != NS_TLS: 
			return
		self.starttls = starttls.getName()
		if self.starttls == 'failure':
			self.DEBUG('Got starttls response: ' + self.starttls,'error')
			return
		self.DEBUG('Got starttls proceed response. Switching to TLS/SSL...','ok')
		try:
			self._startSSL()
		except Exception, e:
			log.error("StartTLSHandler:", exc_info=True)
			#traceback.print_exc()
			self._owner.socket.pollend()
			return
		self._owner.Dispatcher.PlugOut()
		dispatcher_nb.Dispatcher().PlugIn(self._owner)


class NBHTTPPROXYsocket(NonBlockingTcp):
	''' This class can be used instead of transports.HTTPPROXYsocket
	HTTP (CONNECT) proxy connection class. Uses TCPsocket as the base class
		redefines only connect method. Allows to use HTTP proxies like squid with
		(optionally) simple authentication (using login and password). 
		
	'''
	def __init__(self, on_connect =None, on_proxy_failure=None, on_connect_failure = None,proxy = None,server = None,use_srv=True):
		''' Caches proxy and target addresses.
			'proxy' argument is a dictionary with mandatory keys 'host' and 'port' (proxy address)
			and optional keys 'user' and 'password' to use for authentication.
			'server' argument is a tuple of host and port - just like TCPsocket uses. '''
		self.on_connect_proxy = on_connect  
		self.on_proxy_failure = on_proxy_failure
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
		if 'user' in self.proxy and 'password' in self.proxy:
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
		except Exception: 
			log.error("_on_headers_sent:", exc_info=True)
			#traceback.print_exc()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if code != '200':
			self.DEBUG('Invalid proxy reply: %s %s %s' % (proto, code, desc),'error')
			self._owner.disconnected()
			self.on_proxy_failure('Invalid proxy reply')
			return
		if len(reply) != 2:
			pass
		self.onreceive(self._on_proxy_auth)
	
	def _on_proxy_auth(self, reply):
		if self.reply.find('\n\n') == -1:
			if reply is None:
				self.on_proxy_failure('Proxy authentification failed')
				return
			if reply.find('\n\n') == -1:
				self.reply += reply.replace('\r', '')
				self.on_proxy_failure('Proxy authentification failed')
				return
		self.DEBUG('Authentification successfull. Jabber server contacted.','ok')
		if self.on_connect_proxy:
			self.on_connect_proxy()

	def DEBUG(self, text, severity):
		''' Overwrites DEBUG tag to allow debug output be presented as "CONNECTproxy".'''
		return self._owner.DEBUG(DBG_CONNECT_PROXY, text, severity)

class NBSOCKS5PROXYsocket(NonBlockingTcp):
	'''SOCKS5 proxy connection class. Uses TCPsocket as the base class
		redefines only connect method. Allows to use SOCKS5 proxies with
		(optionally) simple authentication (only USERNAME/PASSWORD auth). 
	'''
	def __init__(self, on_connect = None, on_proxy_failure = None,
	on_connect_failure = None, proxy = None, server = None, use_srv = True):
		''' Caches proxy and target addresses.
			'proxy' argument is a dictionary with mandatory keys 'host' and 'port'
			(proxy address) and optional keys 'user' and 'password' to use for
			authentication. 'server' argument is a tuple of host and port -
			just like TCPsocket uses. '''
		self.on_connect_proxy = on_connect  
		self.on_proxy_failure = on_proxy_failure
		self.on_connect_failure = on_connect_failure
		NonBlockingTcp.__init__(self, self._on_tcp_connect, on_connect_failure,
			server, use_srv)
		self.DBG_LINE=DBG_CONNECT_PROXY
		self.server = server
		self.proxy = proxy
		self.ipaddr = None

	def plugin(self, owner):
		''' Starts connection. Used interally. Returns non-empty string on
		success.'''
		owner.debug_flags.append(DBG_CONNECT_PROXY)
		NonBlockingTcp.plugin(self, owner)

	def connect(self, dupe = None):
		''' Starts connection. Connects to proxy, supplies login and password to
			it (if were specified while creating instance). Instructs proxy to make
			connection to the target server. Returns non-empty sting on success.
		'''
		NonBlockingTcp.connect(self, (self.proxy['host'], self.proxy['port']))
		
	def _on_tcp_connect(self):
		self.DEBUG('Proxy server contacted, performing authentification', 'start')
		if 'user' in self.proxy and 'password' in self.proxy:
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
			self._owner.disconnected()
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

# vim: se ts=3:
