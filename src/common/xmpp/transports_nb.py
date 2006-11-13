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

import traceback
import thread

import logging
h = logging.StreamHandler()
f = logging.Formatter('%(asctime)s %(name)s: %(levelname)s: %(message)s')
h.setFormatter(f)
log = logging.getLogger('Gajim.transports')
log.addHandler(h)
log.setLevel(logging.DEBUG)
log.propagate = False
del h, f

USE_PYOPENSSL = False

try:
	#raise ImportError("Manually disabled PyOpenSSL")
	import OpenSSL.SSL
	import OpenSSL.crypto
	USE_PYOPENSSL = True
	print "PyOpenSSL loaded."
except ImportError:
	# FIXME: Remove these prints before release, replace with a warning dialog.
	print "=" * 79
	print "PyOpenSSL not found, falling back to Python builtin SSL objects (insecure)."
	print "=" * 79

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

class SSLWrapper:
	def Error(Exception):
		parent = Exception
		def __init__(this, *args):
			this.parent.__init__(this, *args)

	def __init__(this, sslobj):
		this.sslobj = sslobj
		print "init called with", sslobj

	# We can return None out of this function to signal that no data is
	# available right now. Better than an exception, which differs
	# depending on which SSL lib we're using. Unfortunately returning ''
	# can indicate that the socket has been closed, so to be sure, we avoid
	# this.

	def recv(this, data, flags=None):
		raise NotImplementedException()

	def send(this, data, flags=None):
		raise NotImplementedException()

class PyOpenSSLWrapper(SSLWrapper):
	'''Wrapper class for PyOpenSSL's recv() and send() methods'''
	parent = SSLWrapper

	def __init__(this, *args):
		this.parent.__init__(this, *args)

	def is_numtoolarge(this, e):
		t = ('asn1 encoding routines', 'a2d_ASN1_OBJECT', 'first num too large')
		return isinstance(e.args, (list, tuple)) and len(e.args) == 1 and \
		isinstance(e.args[0], (list, tuple)) and len(e.args[0]) == 2 and \
		e.args[0][0] == e.args[0][1] == t

	def recv(this, bufsize, flags=None):
		retval = None
		try:
			#print "recv: thread id:", thread.get_ident()
			if flags is None: retval = this.sslobj.recv(bufsize)
			else:		  retval = this.sslobj.recv(bufsize, flags)
		except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.WantWriteError), e:
			log.debug("Recv: " + repr(e))
		except OpenSSL.SSL.SysCallError:
			log.error("Got OpenSSL.SSL.SysCallError: " + repr(e))
			traceback.print_exc()
			raise SSLWrapper.Error(('OpenSSL.SSL.SysCallError', e.args))
		except OpenSSL.SSL.Error, e:
			"Recv: Caught OpenSSL.SSL.Error:"
			traceback.print_exc()
			print "Current Stack:"
			traceback.print_stack()
			if this.is_numtoolarge(e):
				# print an error but ignore this exception
				log.warning("Recv: OpenSSL: asn1enc: first num too large (eaten)")
			else:
				raise

		return retval

	def send(this, data, flags=None):
		try:
			#print "send: thread id:", thread.get_ident()
			if flags is None: return this.sslobj.send(data)
			else:		  return this.sslobj.send(data, flags)
		except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.WantWriteError), e:
			log.debug("Send: " + repr(e))
		except OpenSSL.SSL.Error, e:
			print "Send: Caught OpenSSL.SSL.Error:"
			traceback.print_exc()
			print "Current Stack:"
			traceback.print_stack()
			if this.is_numtoolarge(e):
				# warn, but ignore this exception
				log.warning("Send: OpenSSL: asn1enc: first num too large (ignoring)")
			else:
				raise
		return 0

class StdlibSSLWrapper(SSLWrapper):
	'''Wrapper class for Python's socket.ssl read() and write() methods'''
	parent = SSLWrapper

	def __init__(this, *args):
		this.parent.__init__(this, *args)

	def recv(this, bufsize, flags=None):
		# we simply ignore flags since ssl object doesn't support it
		retval = None
		try:
			retval = this.sslobj.read(bufsize)
		except socket.sslerror, e:
			print "Got socket.sslerror"
			print e, e.args
			traceback.print_exc()
			print "Current Stack:"
			traceback.print_stack()
			if e.args[0] not in (socket.SSL_ERROR_WANT_READ, socket.SSL_ERROR_WANT_WRITE):
				raise

		return retval

	def send(this, data, flags=None):
		# we simply ignore flags since ssl object doesn't support it
		try:
			return this.sslobj.write(data)
		except socket.sslerror, e:
			print "Got socket.sslerror"
			print e, e.args
			traceback.print_exc()
			print "Current Stack:"
			traceback.print_stack()
			if e.args[0] not in (socket.SSL_ERROR_WANT_READ, socket.SSL_ERROR_WANT_WRITE):
				raise
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
			traceback.print_exc()
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
		self._owner = None
	
	def pollin(self):
		self._do_receive() 
	
	def pollend(self):
		conn_failure_cb = self.on_connect_failure
		self.disconnect()
		if conn_failure_cb:
			conn_failure_cb()
		
	def disconnect(self):
		if self.state == -2: # already disconnected
			return
		self.state = -2
		self.sendqueue = None
		self.remove_timeout() 
		self._owner.disconnected()
		self.idlequeue.unplug_idle(self.fd)
		try:
			self._sock.shutdown(socket.SHUT_RDWR)
			self._sock.close()
		except:
			traceback.print_exc()
			# socket is already closed
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
		ERR_DISCONN = -2 # Misc error signifying that we got disconnected
		ERR_OTHER = -1 # Other error
		received = None
		errnum = 0
		errtxt = 'No Error Set'
		try: 
			# get as many bites, as possible, but not more than RECV_BUFSIZE
			received = self._recv(RECV_BUFSIZE)
		except (socket.error, socket.herror, socket.gaierror), e:
			print "Got socket exception"
			traceback.print_exc()
			print "Current Stack:"
			traceback.print_stack()
			errnum = e[0]
			errtxt = str(errnum) + ':' + e[1]
		except socket.sslerror, e:
			print "Got unknown socket.sslerror"
			traceback.print_exc()
			print "Current Stack:"
			traceback.print_stack()
			errnum = ERR_OTHER
			errtxt = repr("socket.sslerror: " + e.args)
		except SSLWrapper.Error:
			errnum = ERR_OTHER
			errtxt = repr(e.args)

		# Should we really do this? In C, recv() will happily return 0
		# in nonblocking mode when there is no data waiting, and in
		# some cases select() will mark the socket for reading when
		# there is nothing to read, and the socket is still open. For
		# example, this can happen when the remote sends a zero-length
		# tcp packet.
		if received is '':
			errnum = ERR_DISCONN
			errtxt = "Connection closed unexpectedly"

		if errnum in (ERR_DISCONN, errno.ECONNRESET, errno.ENOTCONN, errno.ESHUTDOWN):
			self.DEBUG(errtxt, 'error')
			log.error("Got Disconnected: " + errtxt)
			self.pollend()
			# don't proccess result, cas it will raise error
			return

		if received is None:
			if errnum != 0:
				self.DEBUG(errtxt, 'error')
				log.error("Error: " + errtxt)
				if self.state >= 0:
					self.disconnect()
				return
			received = ''

		if self.state < 0:
			return

		# we have received some bites, stop the timeout!
		self.renew_send_timeout()
		if self.on_receive:
			if received.strip():
				self.DEBUG(received, 'got')
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
			traceback.print_exc()
			if e[0] == socket.SSL_ERROR_WANT_WRITE:
				return True		
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
			traceback.print_exc()
			errnum = e[0]
		# in progress, or would block
		if errnum in (errno.EINPROGRESS, errno.EALREADY, errno.EWOULDBLOCK): 
			return
		# 10056  - already connected, only on win32
		# code 'WS*' is not available on GNU, so we use its numeric value
		elif errnum not in (0, 10056, errno.EISCONN): 
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
		if owner.__dict__.has_key('NonBlockingTLS'): 
			return  # Already enabled.
		PlugIn.PlugIn(self, owner)
		DBG_LINE='NonBlockingTLS'
		self.on_tls_start = on_tls_start
		if now:
			try:
				res = self._startSSL()
			except Exception, e:
				traceback.print_exc()
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
		if self._owner.__dict__.has_key('Dispatcher'):
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

	def _dumpX509(this, cert):
		print "Digest (SHA-1):", cert.digest("sha1")
		print "Digest (MD5):", cert.digest("md5")
		print "Serial #:", cert.get_serial_number()
		print "Version:", cert.get_version()
		print "Expired:", torf(cert.has_expired(), "Yes", "No")
		print "Subject:"
		this._dumpX509Name(cert.get_subject())
		print "Issuer:"
		this._dumpX509Name(cert.get_issuer())
		this._dumpPKey(cert.get_pubkey())

	def _dumpX509Name(this, name):
		print "X509Name:", str(name)

	def _dumpPKey(this, pkey):
		typedict = {OpenSSL.crypto.TYPE_RSA: "RSA", OpenSSL.crypto.TYPE_DSA: "DSA"}
		print "PKey bits:", pkey.bits()
		print "PKey type: %s (%d)" % (typedict.get(pkey.type(), "Unknown"), pkey.type())

	def _startSSL(self):
		''' Immidiatedly switch socket to TLS mode. Used internally.'''
		print "_startSSL called"
		if USE_PYOPENSSL: return self._startSSL_pyOpenSSL()
		return self._startSSL_stdlib()

	def _startSSL_pyOpenSSL(self):
		print "_startSSL_pyOpenSSL called, thread id:", thread.get_ident()
		tcpsock = self._owner.Connection
		# FIXME: should method be configurable?
		tcpsock._sslContext = OpenSSL.SSL.Context(OpenSSL.SSL.TLSv1_METHOD)
		tcpsock._sslContext.set_info_callback(self._ssl_info_callback)
		tcpsock._sslObj = OpenSSL.SSL.Connection(tcpsock._sslContext, tcpsock._sock)
		tcpsock._sslObj.set_connect_state() # set to client mode

		wrapper = PyOpenSSLWrapper(tcpsock._sslObj)
		tcpsock._recv = wrapper.recv
		tcpsock._send = wrapper.send

		print "Initiating handshake..."
		#tcpsock._sslObj.setblocking(True)
		try:
			self.starttls='in progress'
			tcpsock._sslObj.do_handshake()
		except (OpenSSL.SSL.WantReadError, OpenSSL.SSL.WantWriteError), e:
			log.debug("do_handshake: " + repr(e))
		#tcpsock._sslObj.setblocking(False)
		#print "Done handshake"
		print "Async handshake started..."

	def _on_ssl_handshake_done(self):
		print "Handshake done!"
		self.starttls='success'

		tcpsock = self._owner.Connection
		cert = tcpsock._sslObj.get_peer_certificate()
		peer = cert.get_subject()
		issuer = cert.get_issuer()
		tcpsock._sslIssuer = unicode(issuer)
		tcpsock._sslServer = unicode(peer)

		# FIXME: remove debug prints
		peercert = tcpsock._sslObj.get_peer_certificate()
		ciphers = tcpsock._sslObj.get_cipher_list()

		print "Ciphers:", ciphers
		print "Peer cert:", peercert
		self._dumpX509(peercert)

		print OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM, peercert)

	def _startSSL_stdlib(self):
		print "_startSSL_stdlib called"
		tcpsock=self._owner.Connection
		tcpsock._sock.setblocking(True)
		tcpsock._sslObj = socket.ssl(tcpsock._sock, None, None)
		tcpsock._sock.setblocking(False)
		tcpsock._sslIssuer = tcpsock._sslObj.issuer()
		tcpsock._sslServer = tcpsock._sslObj.server()
		wrapper = StdlibSSLWrapper(tcpsock._sslObj)
		tcpsock._recv = wrapper.recv
		tcpsock._send = wrapper.send
		self.starttls='success'

	def _ssl_info_callback(this, sslconn, type, st):
		# Exceptions can't propagate up through this callback, so print them here.
		try:    this._ssl_info_callback_guarded(sslconn, type, st)
		except: traceback.print_exc()

	def _ssl_info_callback_guarded(this, sslconn, type, st):
		b = this.ssl_h_bits

		#if type & b['SSL_CB_LOOP']:
		#	if type & SSL_ST_CONNECT: tls_state = "connect"
		#	elif type & SSL_ST_ACCEPT: tls_state = "accept"
		#	else: tls_state = "undefined"
		#	print "tls_state: %s: %s" % (tls_state, sslconn.state_string())

		#if type & b['SSL_CB_ALERT']:
		#	if type & SSL_CB_READ: rdwr = "read"
		#	elif type & SSL_CB_WRITE: rdwr = "write"
		#	else: rdwr = "unknown"
		#	print "tls_alert: %s:%d: %s" % (rdwr, st, sslconn.state_string())

		#mask = ""
		#for k, v in b.iteritems():
		#	if type & v: mask += " " + k
		#print "mask:", mask, st

		if type & b['SSL_CB_HANDSHAKE_DONE']:
			this._on_ssl_handshake_done()

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
		try:
			self._startSSL()
		except Exception, e:
			traceback.print_exc()
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
			traceback.print_exc()
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
