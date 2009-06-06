## bosh.py	
##
##
## Copyright (C) 2008 Tomas Karasek <tom.to.the.k@gmail.com>
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


import locale, random
from hashlib import sha1
from transports_nb import NonBlockingTransport, NonBlockingHTTPBOSH,\
	CONNECTED, CONNECTING, DISCONNECTED, DISCONNECTING,\
	urisplit, DISCONNECT_TIMEOUT_SECONDS
from protocol import BOSHBody
from simplexml import Node

import logging
log = logging.getLogger('gajim.c.x.bosh')

KEY_COUNT = 10

# Fake file descriptor - it's used for setting read_timeout in idlequeue for
# BOSH Transport. In TCP-derived transports this is file descriptor of socket.
FAKE_DESCRIPTOR = -1337


class NonBlockingBOSH(NonBlockingTransport):
	def __init__(self, raise_event, on_disconnect, idlequeue, estabilish_tls, certs,
			xmpp_server, domain, bosh_dict, proxy_creds):
		NonBlockingTransport.__init__(self, raise_event, on_disconnect, idlequeue,
			estabilish_tls, certs)

		self.bosh_sid = None
		if locale.getdefaultlocale()[0]:
			self.bosh_xml_lang = locale.getdefaultlocale()[0].split('_')[0]
		else:
			self.bosh_xml_lang = 'en'

		self.http_version = 'HTTP/1.1'
		self.http_persistent = True
		self.http_pipelining = bosh_dict['bosh_http_pipelining']
		self.bosh_to = domain

		self.route_host, self.route_port = xmpp_server

		self.bosh_wait = bosh_dict['bosh_wait']
		if not self.http_pipelining:
			self.bosh_hold = 1
		else:
			self.bosh_hold = bosh_dict['bosh_hold']
		self.bosh_requests = self.bosh_hold
		self.bosh_uri = bosh_dict['bosh_uri']
		self.bosh_port = bosh_dict['bosh_port']
		self.bosh_content = bosh_dict['bosh_content']
		self.over_proxy = bosh_dict['bosh_useproxy']
		if estabilish_tls:
			self.bosh_secure = 'true'
		else:
			self.bosh_secure = 'false'
		self.use_proxy_auth = bosh_dict['useauth']
		self.proxy_creds = proxy_creds
		self.wait_cb_time = None
		self.http_socks = []
		self.stanza_buffer = []
		self.prio_bosh_stanzas = []
		self.current_recv_handler = None
		self.current_recv_socket = None
		self.key_stack = None
		self.ack_checker = None
		self.after_init = False
		self.proxy_dict = {}
		if self.over_proxy and self.estabilish_tls:
			self.proxy_dict['type'] = 'http'
			# with SSL over proxy, we do HTTP CONNECT to proxy to open a channel to 
			# BOSH Connection Manager
			self.proxy_dict['xmpp_server'] = (urisplit(self.bosh_uri)[1], self.bosh_port)
			self.proxy_dict['credentials'] = self.proxy_creds

		
	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		NonBlockingTransport.connect(self, conn_5tuple, on_connect, on_connect_failure)

		global FAKE_DESCRIPTOR
		FAKE_DESCRIPTOR = FAKE_DESCRIPTOR - 1
		self.fd = FAKE_DESCRIPTOR

		self.stanza_buffer = []
		self.prio_bosh_stanzas = []

		self.key_stack = KeyStack(KEY_COUNT)
		self.ack_checker = AckChecker()
		self.after_init = True

		self.http_socks.append(self.get_new_http_socket())
		self._tcp_connecting_started()

		self.http_socks[0].connect(
			conn_5tuple = conn_5tuple,
			on_connect = self._on_connect,
			on_connect_failure = self._on_connect_failure)

	def _on_connect(self):
		self.peerhost = self.http_socks[0].peerhost
		self.ssl_lib = self.http_socks[0].ssl_lib
		NonBlockingTransport._on_connect(self)



	def set_timeout(self, timeout):
		if self.get_state() != DISCONNECTED and self.fd != -1:
			NonBlockingTransport.set_timeout(self, timeout)
		else:
			log.warn('set_timeout: TIMEOUT NOT SET: state is %s, fd is %s' % (self.get_state(), self.fd))

	def on_http_request_possible(self):
		'''
		Called when HTTP request it's possible to send a HTTP request. It can be when
		socket is connected or when HTTP response arrived.
		There should be always one pending request to BOSH CM.
		'''
		log.debug('on_http_req possible, state:\n%s' % self.get_current_state())
		if self.get_state()==DISCONNECTED: return

		#Hack for making the non-secure warning dialog work
		if self._owner.got_features:
			if (hasattr(self._owner, 'NonBlockingNonSASL') or hasattr(self._owner, 'SASL')):
				self.send_BOSH(None)
			else:
				# If we already got features and no auth module was plugged yet, we are
				# probably waiting for confirmation of the "not-secure-connection" dialog.
				# We don't send HTTP request in that case.
				# see http://lists.jabber.ru/pipermail/ejabberd/2008-August/004027.html
				return
		else:
			self.send_BOSH(None)

		

	def get_socket_in(self, state):
		''' gets sockets in desired state '''
		for s in self.http_socks:
			if s.get_state()==state: return s
		return None


	def get_free_socket(self):
		''' Selects and returns socket eligible for sending a data to.'''
		if self.http_pipelining:
			return self.get_socket_in(CONNECTED)
		else:
			last_recv_time, tmpsock = 0, None
			for s in self.http_socks:
				# we're interested only in CONNECTED socket with no requests pending
				if s.get_state()==CONNECTED and s.pending_requests==0:
					# if there's more of them, we want the one with the least recent data receive
					# (lowest last_recv_time)
					if (last_recv_time==0) or (s.last_recv_time < last_recv_time):
						last_recv_time = s.last_recv_time
						tmpsock = s
			if tmpsock:
				return tmpsock
			else:
				return None


	def send_BOSH(self, payload):
		'''
		Tries to send a stanza in payload by appeding it to a buffer and plugging a 
		free socket for writing.
		'''
		total_pending_reqs = sum([s.pending_requests for s in self.http_socks])

		# when called after HTTP response (Payload=None) and when there are already 
		# some pending requests and no data to send, or when the socket is
		# disconnected, we do nothing
		if      payload is None and \
			total_pending_reqs > 0 and \
			self.stanza_buffer == [] and \
			self.prio_bosh_stanzas == [] or \
			self.get_state()==DISCONNECTED:
			return

		# now the payload is put to buffer and will be sent at some point
		self.append_stanza(payload)

		# if we're about to make more requests than allowed, we don't send - stanzas will be
		# sent after HTTP response from CM, exception is when we're disconnecting - then we
		# send anyway
		if total_pending_reqs >= self.bosh_requests and self.get_state()!=DISCONNECTING:
			log.warn('attemp to make more requests than allowed by Connection Manager:\n%s' % 
				self.get_current_state())
			return

		# when there's free CONNECTED socket, we plug it for write and the data will
		# be sent when write is possible
		if self.get_free_socket():
			self.plug_socket()
			return

		# if there is a connecting socket, we just wait for when it connects,
		# payload will be sent in a sec when the socket connects
		if self.get_socket_in(CONNECTING): return
		
		# being here means there are either DISCONNECTED sockets or all sockets are
		# CONNECTED with too many pending requests
		s = self.get_socket_in(DISCONNECTED)

		# if we have DISCONNECTED socket, lets connect it and plug for send
		if s:
			self.connect_and_flush(s)
		else:
			# otherwise create and connect a new one
			ss = self.get_new_http_socket()
			self.http_socks.append(ss)
			self.connect_and_flush(ss)
		return

	def plug_socket(self):
		stanza = None
		s = self.get_free_socket()
		if s:
			s._plug_idle(writable=True, readable=True)
		else:
			log.error('=====!!!!!!!!====> Couldn\'t get free socket in plug_socket())')

	def build_stanza(self, socket):
		'''
		Builds a BOSH body tag from data in buffers and adds key, rid and ack
		attributes to it.
		This method is called from _do_send() of underlying transport. This is to
		ensure rid and keys will be processed in correct order. If I generate them 
		before	plugging a socket for write (and did it for two sockets/HTTP 
		connections) in parallel, they might be sent in wrong order, which results
		in violating the BOSH session and server-side disconnect.
		'''
		if self.prio_bosh_stanzas:
			stanza, add_payload = self.prio_bosh_stanzas.pop(0)
			if add_payload:
				stanza.setPayload(self.stanza_buffer)
				self.stanza_buffer = []
		else:
			stanza = self.boshify_stanzas(self.stanza_buffer)
			self.stanza_buffer = []

		stanza = self.ack_checker.backup_stanza(stanza, socket)

		key, newkey = self.key_stack.get()
		if key:
			stanza.setAttr('key', key)
		if newkey:
			stanza.setAttr('newkey', newkey)


		log.info('sending msg with rid=%s to sock %s' % (stanza.getAttr('rid'), id(socket)))
		self.renew_bosh_wait_timeout(self.bosh_wait + 3)
		return stanza


	def on_bosh_wait_timeout(self):
		log.error('Connection Manager didn\'t respond within %s + 3 seconds --> forcing disconnect' % self.bosh_wait)
		self.disconnect()


	def renew_bosh_wait_timeout(self, timeout):
		if self.wait_cb_time is not None:
			self.remove_bosh_wait_timeout()
		sched_time = self.idlequeue.set_alarm(self.on_bosh_wait_timeout, timeout)
		self.wait_cb_time = sched_time

	def remove_bosh_wait_timeout(self):
		self.idlequeue.remove_alarm(
				self.on_bosh_wait_timeout,
				self.wait_cb_time)

	def on_persistent_fallback(self, socket):
		'''
		Called from underlying transport when server closes TCP connection.
		:param socket: disconnected transport object
		'''
		if socket.http_persistent:
			log.warn('Fallback to nonpersistent HTTP (no pipelining as well)')
			socket.http_persistent = False
			self.http_persistent = False
			self.http_pipelining = False
			socket.disconnect(do_callback=False)
			self.connect_and_flush(socket)
		else:
			socket.disconnect()

		

	def handle_body_attrs(self, stanza_attrs):
		'''
		Called for each incoming body stanza from dispatcher. Checks body attributes.
		'''
		self.remove_bosh_wait_timeout()

		if self.after_init:
			if stanza_attrs.has_key('sid'):
				# session ID should be only in init response
				self.bosh_sid = stanza_attrs['sid']

			if stanza_attrs.has_key('requests'):
				self.bosh_requests = int(stanza_attrs['requests'])

			if stanza_attrs.has_key('wait'):
				self.bosh_wait = int(stanza_attrs['wait'])
			self.after_init = False

		ack = None
		if stanza_attrs.has_key('ack'):
			ack = stanza_attrs['ack']
		self.ack_checker.process_incoming_ack(ack=ack, 
			socket=self.current_recv_socket)

		if stanza_attrs.has_key('type'):
			if stanza_attrs['type'] in ['terminate', 'terminal']:
				condition = 'n/a'
				if stanza_attrs.has_key('condition'):
					condition = stanza_attrs['condition']
				if condition == 'n/a':
					log.info('Received sesion-ending terminating stanza')
				else:
					log.error('Received terminating stanza: %s - %s' % (condition,
						bosh_errors[condition]))
				self.disconnect()
				return

			if stanza_attrs['type'] == 'error':
				# recoverable error
				pass
		return


	def append_stanza(self, stanza):
		''' appends stanza to a buffer to send '''
		if stanza:
			if isinstance(stanza, tuple):
				# stanza is tuple of BOSH stanza and bool value for whether to add payload
				self.prio_bosh_stanzas.append(stanza)
			else:
				# stanza is XMPP stanza. Will be boshified before send.
				self.stanza_buffer.append(stanza)


	def send(self, stanza, now=False):
		self.send_BOSH(stanza)


		
	def get_current_state(self):
		t = '------ SOCKET_ID\tSOCKET_STATE\tPENDING_REQS\n'
		for s in self.http_socks:
			t = '%s------ %s\t%s\t%s\n' % (t,id(s), s.get_state(), s.pending_requests)
		t = '%s------ prio stanzas: %s, queued XMPP stanzas: %s, not_acked stanzas: %s' \
			% (t, self.prio_bosh_stanzas, self.stanza_buffer,
			self.ack_checker.get_not_acked_rids())
		return t
		

	def connect_and_flush(self, socket):
		socket.connect(
			conn_5tuple = self.conn_5tuple, 
			on_connect = self.on_http_request_possible,
			on_connect_failure = self.disconnect)


	def boshify_stanzas(self, stanzas=[], body_attrs=None):
		''' wraps zero to many stanzas by body tag with xmlns and sid '''
		log.debug('boshify_staza - type is: %s, stanza is %s' % (type(stanzas), stanzas))
		tag = BOSHBody(attrs={'sid': self.bosh_sid})
		tag.setPayload(stanzas)
		return tag


	def send_init(self, after_SASL=False):
		if after_SASL:
			t = BOSHBody(
				attrs={	'to': self.bosh_to,
					'sid': self.bosh_sid,
					'xml:lang': self.bosh_xml_lang,
					'xmpp:restart': 'true',
					'secure': self.bosh_secure,
					'xmlns:xmpp': 'urn:xmpp:xbosh'})
		else:
			t = BOSHBody(
				attrs={ 'content': self.bosh_content,
					'hold': str(self.bosh_hold),
					'route': '%s:%s' % (self.route_host, self.route_port),
					'to': self.bosh_to,
					'wait': str(self.bosh_wait),
					'xml:lang': self.bosh_xml_lang,
					'xmpp:version': '1.0',
					'ver': '1.6',
					'xmlns:xmpp': 'urn:xmpp:xbosh'})
		self.send_BOSH((t,True))

	def start_disconnect(self):
		NonBlockingTransport.start_disconnect(self)
		self.renew_bosh_wait_timeout(DISCONNECT_TIMEOUT_SECONDS)
		self.send_BOSH(
			(BOSHBody(attrs={'sid': self.bosh_sid, 'type': 'terminate'}), True))


	def get_new_http_socket(self):
		http_dict = {'http_uri': self.bosh_uri,			
			'http_port': self.bosh_port,
			'http_version': self.http_version,
			'http_persistent': self.http_persistent,
			'add_proxy_headers': self.over_proxy and not self.estabilish_tls}
		if self.use_proxy_auth:
			http_dict['proxy_user'], http_dict['proxy_pass'] = self.proxy_creds

		s = NonBlockingHTTPBOSH(
			raise_event=self.raise_event,
			on_disconnect=self.disconnect,
			idlequeue = self.idlequeue,
			estabilish_tls = self.estabilish_tls,
			certs = self.certs,
			on_http_request_possible = self.on_http_request_possible,
			http_dict = http_dict,
			proxy_dict = self.proxy_dict,
			on_persistent_fallback = self.on_persistent_fallback)

		s.onreceive(self.on_received_http)
		s.set_stanza_build_cb(self.build_stanza)
		return s


	def onreceive(self, recv_handler):
		if recv_handler is None:
			recv_handler = self._owner.Dispatcher.ProcessNonBlocking
		self.current_recv_handler = recv_handler


	def on_received_http(self, data, socket):
		self.current_recv_socket = socket
		self.current_recv_handler(data)


	def disconnect(self, do_callback=True):
		self.remove_bosh_wait_timeout()
		if self.get_state() == DISCONNECTED: return
		self.fd = -1
		for s in self.http_socks:
			s.disconnect(do_callback=False)
		NonBlockingTransport.disconnect(self, do_callback)


def get_rand_number():
	# with 50-bit random initial rid, session would have to go up
	# to 7881299347898368 messages to raise rid over 2**53 
	# (see http://www.xmpp.org/extensions/xep-0124.html#rids)
	# it's also used for sequence key initialization
	r = random.Random()
	r.seed()
	return r.getrandbits(50)
	


class AckChecker():
	'''
	Class for generating rids and generating and checking acknowledgements in
	BOSH messages.
	'''
	def __init__(self):
		self.rid = get_rand_number()
		self.ack = 1
		self.last_rids = {}
		self.not_acked = []


	def get_not_acked_rids(self): return [rid for rid, st in self.not_acked]

	def backup_stanza(self, stanza, socket):
		socket.pending_requests += 1
		rid = self.get_rid()
		self.not_acked.append((rid, stanza))
		stanza.setAttr('rid', str(rid))
		self.last_rids[socket]=rid

		if self.rid != self.ack + 1:
			stanza.setAttr('ack', str(self.ack))
		return stanza

	def process_incoming_ack(self, socket, ack=None):
		socket.pending_requests -= 1
		if ack:
			ack = int(ack)
		else:
			ack = self.last_rids[socket]

		i = len([rid for rid, st in self.not_acked if ack >= rid])
		self.not_acked = self.not_acked[i:]

		self.ack = ack

		
	def get_rid(self):
		self.rid = self.rid + 1
		return self.rid
		




class KeyStack():
	'''
	Class implementing key sequences for BOSH messages
	'''
	def __init__(self, count):
		self.count = count
		self.keys = []
		self.reset()
		self.first_call = True

	def reset(self):
		seed = str(get_rand_number())
		self.keys = [sha1(seed).hexdigest()]
		for i in range(self.count-1):
			curr_seed = self.keys[i]
			self.keys.append(sha1(curr_seed).hexdigest())

	def get(self):
		if self.first_call:
			self.first_call = False
			return (None, self.keys.pop())
			
		if len(self.keys)>1:
			return (self.keys.pop(), None)
		else:
			last_key = self.keys.pop()
			self.reset()
			new_key = self.keys.pop()
			return (last_key, new_key)

# http://www.xmpp.org/extensions/xep-0124.html#errorstatus-terminal
bosh_errors = {
	'n/a': 'none or unknown condition in terminating body stanza',
	'bad-request': 'The format of an HTTP header or binding element received from the client is unacceptable (e.g., syntax error), or Script Syntax is not supported.',
	'host-gone': 'The target domain specified in the "to" attribute or the target host or port specified in the "route" attribute is no longer serviced by the connection manager.',
	'host-unknown': 'The target domain specified in the "to" attribute or the target host or port specified in the "route" attribute is unknown to the connection manager.',
	'improper-addressing': 'The initialization element lacks a "to" or "route" attribute (or the attribute has no value) but the connection manager requires one.',
	'internal-server-error': 'The connection manager has experienced an internal error that prevents it from servicing the request.',
	'item-not-found': '(1) "sid" is not valid, (2) "stream" is not valid, (3) "rid" is larger than the upper limit of the expected window, (4) connection manager is unable to resend response, (5) "key" sequence is invalid',
	'other-request': 'Another request being processed at the same time as this request caused the session to terminate.',
	'policy-violation': 'The client has broken the session rules (polling too frequently, requesting too frequently, too many simultaneous requests).',
	'remote-connection-failed': 'The connection manager was unable to connect to, or unable to connect securely to, or has lost its connection to, the server.',
	'remote-stream-error': 'Encapsulates an error in the protocol being transported.',
	'see-other-uri': 'The connection manager does not operate at this URI (e.g., the connection manager accepts only SSL or TLS connections at some https: URI rather than the http: URI requested by the client). The client may try POSTing to the URI in the content of the <uri/> child element.',
	'system-shutdown': 'The connection manager is being shut down. All active HTTP sessions are being terminated. No new sessions can be created.',
	'undefined-condition': 'The error is not one of those defined herein; the connection manager SHOULD include application-specific information in the content of the <body/> wrapper.'
}
