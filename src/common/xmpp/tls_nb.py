##   tls_nb.py
##       based on transports_nb.py
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

import socket
from client import PlugIn
from protocol import *

import sys
import os
import errno
import time

import traceback

import logging
log = logging.getLogger('gajim.c.x.tls_nb')

# I don't need to load gajim.py just because of few TLS variables, so I changed
# %s/common\.gajim\.DATA_DIR/\'\.\.\/data\'/c
# %s/common\.gajim\.MY_CACERTS/\'\%s\/\.gajim\/cacerts\.pem\' \% os\.environ\[\'HOME\'\]/c

# To change it back do:
# %s/\'\.\.\/data\'/common\.gajim\.DATA_DIR/c
# %s/\'%s\/\.gajim\/cacerts\.pem\'\ %\ os\.environ\[\'HOME\'\]/common\.gajim\.MY_CACERTS/c
# TODO: make the paths configurable - as constructor parameters or sth

# import common.gajim

USE_PYOPENSSL = False


#TODO: add callback set from PlugIn for errors during runtime
#      - sth like on_disconnect in socket wrappers


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
		''' Receive wrapper for SSL object

		We can return None out of this function to signal that no data is
		available right now. Better than an exception, which differs
		depending on which SSL lib we're using. Unfortunately returning ''
		can indicate that the socket has been closed, so to be sure, we avoid
		this by returning None. '''

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
			log.debug("Recv: Want-error: " + repr(e))
			pass
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
			log.warn("TLS unsupported by remote server.")
			self.on_tls_failure("TLS unsupported by remote server.")
			return
		log.debug("TLS supported by remote server. Requesting TLS start.")
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
		log.debug('Got starttls proceed response. Switching to TLS/SSL...')
		try:
			self._startSSL()
		except Exception, e:
			log.error("StartTLSHandler:", exc_info=True)
			self.on_tls_failure('in StartTLSHandler')
			#traceback.print_exc()
			return
		self._owner.Dispatcher.PlugOut()
		self.on_tls_success()
