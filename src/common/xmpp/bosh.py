
import locale, random
from transports_nb import NonBlockingTransport, NonBlockingHTTPBOSH,\
	CONNECTED, CONNECTING, DISCONNECTED, DISCONNECTING,\
	urisplit
from protocol import BOSHBody
from simplexml import Node
import sha

import logging
log = logging.getLogger('gajim.c.x.bosh')

KEY_COUNT = 10

FAKE_DESCRIPTOR = -1337
'''Fake file descriptor - it's used for setting read_timeout in idlequeue for
BOSH Transport.
In TCP-derived transports it is file descriptor of socket'''


class NonBlockingBOSH(NonBlockingTransport):
	def __init__(self, raise_event, on_disconnect, idlequeue, xmpp_server, domain,
		bosh_dict):
		NonBlockingTransport.__init__(self, raise_event, on_disconnect, idlequeue)

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
		self.bosh_hold = bosh_dict['bosh_hold']
		self.bosh_requests = self.bosh_hold
		self.bosh_uri = bosh_dict['bosh_uri']
		self.bosh_port = bosh_dict['bosh_port']
		self.bosh_content = bosh_dict['bosh_content']

		self.wait_cb_time = None
		self.http_socks = []
		self.stanza_buffer = []
		self.prio_bosh_stanzas = []
		self.current_recv_handler = None
		self.current_recv_socket = None
		self.key_stack = None
		self.ack_checker = None
		self.after_init = False

		# if proxy_host .. do sth about HTTP proxy etc.
		
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
		self.tcp_connection_started()

		# following connect() is not necessary because sockets can be connected on 
		# send but we need to know if host is reachable in order to invoke callback
		# for connecting failure eventually (the callback is different than callback
		# for errors occurring after connection is etabilished)
		self.http_socks[0].connect(
			conn_5tuple = conn_5tuple,
			on_connect = lambda: self._on_connect(self.http_socks[0]),
			on_connect_failure = self._on_connect_failure)

	def set_timeout(self, timeout):
		if self.state in [CONNECTING, CONNECTED] and self.fd != -1:
			NonBlockingTransport.set_timeout(self, timeout)
		else:
			log.warn('set_timeout: TIMEOUT NOT SET: state is %s, fd is %s' % (self.state, self.fd))

	def on_http_request_possible(self):
		'''
		Called after HTTP response is received - another request is possible. 
		There should be always one pending request on BOSH CM.
		'''
		log.info('on_http_req possible, state:\n%s' % self.get_current_state())
		if self.state == DISCONNECTING:
			self.disconnect()
			return
		self.send_BOSH(None)


	def get_socket_in(self, state):
		for s in self.http_socks:
			if s.state==state: return s
		return None

	def get_free_socket(self):
		if self.http_pipelining:
			assert( len(self.http_socks) == 1 )
			return self.get_socket_in(CONNECTED)
		else:
			last_recv_time, tmpsock = 0, None
			for s in self.http_socks:
				# we're interested only into CONNECTED socket with no req pending
				if s.state==CONNECTED and s.pending_requests==0:
					# if there's more of them, we want the one with less recent data receive
					# (lowest last_recv_time)
					if (last_recv_time==0) or (s.last_recv_time < last_recv_time):
						last_recv_time = s.last_recv_time
						tmpsock = s
			if tmpsock:
				return tmpsock
			else:
				return None


	def send_BOSH(self, payload):
		total_pending_reqs = sum([s.pending_requests for s in self.http_socks])

		# when called after HTTP response when there are some pending requests and
		# no data to send, we do nothing and disccard the payload
		if      payload is None and \
			total_pending_reqs > 0 and \
			self.stanza_buffer == [] and \
			self.prio_bosh_stanzas == [] or \
			self.state==DISCONNECTED:
			return

		# now the payload is put to buffer and will be sent at some point
		self.append_stanza(payload)

		# if we're about to make more requests than allowed, we don't send - stanzas will be
		# sent after HTTP response from CM, exception is when we're disconnecting - then we
		# send anyway
		if total_pending_reqs >= self.bosh_requests and self.state!=DISCONNECTING:
			log.warn('attemp to make more requests than allowed by Connection Manager:\n%s' % 
				self.get_current_state())
			return

		# when there's free CONNECTED socket, we flush the data
		if self.get_free_socket():
			self.plug_socket()
			return

		# if there is a connecting socket, we just wait for when it connects,
		# payload will be sent in a sec when the socket connects
		if self.get_socket_in(CONNECTING): return
		
		# being here means there are either DISCONNECTED sockets or all sockets are
		# CONNECTED with too many pending requests
		s = self.get_socket_in(DISCONNECTED)

		# if we have DISCONNECTED socket, lets connect it and ...
		if s:
			self.connect_and_flush(s)
		else:
			if len(self.http_socks) > 1: return
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
			log.error('=====!!!!!!!!====> Couldnt get free socket in plug_socket())')

	def build_stanza(self, socket):
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
		socket.send(stanza)
		self.renew_bosh_wait_timeout()
		return stanza


	def on_bosh_wait_timeout(self):
		log.error('Connection Manager didn\'t respond within % seconds --> forcing \
			disconnect' % self.bosh_wait)
		self.disconnect()


	def renew_bosh_wait_timeout(self):
		if self.wait_cb_time is not None:
			self.remove_bosh_wait_timeout()
		sched_time = self.idlequeue.set_alarm(self.on_bosh_wait_timeout, self.bosh_wait+10)
		self.wait_cb_time = sched_time

	def remove_bosh_wait_timeout(self):
		self.idlequeue.remove_alarm(
				self.on_bosh_wait_timeout,
				self.wait_cb_time)

	def on_persistent_fallback(self):
		log.warn('Fallback to nonpersistent HTTP (no pipelining as well)')
		self.http_persistent = False
		self.http_pipelining = False
		

	def handle_body_attrs(self, stanza_attrs):
		self.remove_bosh_wait_timeout()

		if self.after_init:
			self.after_init = False
			if stanza_attrs.has_key('sid'):
				# session ID should be only in init response
				self.bosh_sid = stanza_attrs['sid']

			if stanza_attrs.has_key('requests'):
				#self.bosh_requests = int(stanza_attrs['requests'])
				self.bosh_requests = int(stanza_attrs['wait'])

			if stanza_attrs.has_key('wait'):
				self.bosh_wait = int(stanza_attrs['wait'])

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
				log.error('Received terminating stanza: %s - %s' % (condition, bosh_errors[condition]))
				self.set_state(DISCONNECTING)

			if stanza_attrs['type'] == 'error':
				# recoverable error
				pass
		return


	def append_stanza(self, stanza):
		if stanza:
			if isinstance(stanza, tuple):
				# tuple of BOSH stanza and True/False for whether to add payload
				self.prio_bosh_stanzas.append(stanza)
			else:
				self.stanza_buffer.append(stanza)



	def send(self, stanza, now=False):
		# body tags should be send only via send_BOSH()
		assert(not isinstance(stanza, BOSHBody))
		self.send_BOSH(stanza)


		
	def get_current_state(self):
		t = '------ SOCKET_ID\tSOCKET_STATE\tPENDING_REQS\n'
		for s in self.http_socks:
			t = '%s------ %s\t%s\t%s\n' % (t,id(s), s.state, s.pending_requests)
		t = '%s------ prio stanzas: %s, queued XMPP stanzas: %s, not_acked stanzas: %s' \
			% (t, self.prio_bosh_stanzas, self.stanza_buffer,
			self.ack_checker.get_not_acked_rids())
		return t
		



	def connect_and_flush(self, socket):
		socket.connect(
			conn_5tuple = self.conn_5tuple, 
			on_connect = lambda :self.send_BOSH(None),
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
		self.send_BOSH(
			(BOSHBody(attrs={'sid': self.bosh_sid, 'type': 'terminate'}), True))


	def get_new_http_socket(self):
		s = NonBlockingHTTPBOSH(
			raise_event=self.raise_event,
			on_disconnect=self.disconnect,
			idlequeue = self.idlequeue,
			on_http_request_possible = self.on_http_request_possible,
			http_uri = self.bosh_uri,			
			http_port = self.bosh_port,
			http_version = self.http_version,
			http_persistent = self.http_persistent,
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
		if self.state == DISCONNECTED: return
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
        def __init__(self, count):
                self.count = count
                self.keys = []
                self.reset()
		self.first_call = True

        def reset(self):
                seed = str(get_rand_number())
                self.keys = [sha.new(seed).hexdigest()]
                for i in range(self.count-1):
                        curr_seed = self.keys[i]
                        self.keys.append(sha.new(curr_seed).hexdigest())

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
