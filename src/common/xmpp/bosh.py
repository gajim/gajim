
import locale, random
from transports_nb import NonBlockingTransport, NonBlockingHTTP, CONNECTED, CONNECTING, DISCONNECTED
from protocol import BOSHBody
from simplexml import Node

import logging
log = logging.getLogger('gajim.c.x.bosh')


FAKE_DESCRIPTOR = -1337
'''Fake file descriptor - it's used for setting read_timeout in idlequeue for
BOSH Transport. Timeouts in queue are saved by socket descriptor.
In TCP-derived transports it is file descriptor of socket'''


class NonBlockingBOSH(NonBlockingTransport):
	def __init__(self, raise_event, on_disconnect, idlequeue, xmpp_server, domain,
		bosh_dict):
		NonBlockingTransport.__init__(self, raise_event, on_disconnect, idlequeue)

		# with 50-bit random initial rid, session would have to go up
		# to 7881299347898368 messages to raise rid over 2**53 
		# (see http://www.xmpp.org/extensions/xep-0124.html#rids)
		r = random.Random()
		r.seed()
		global FAKE_DESCRIPTOR
		FAKE_DESCRIPTOR = FAKE_DESCRIPTOR - 1
		self.fake_fd = FAKE_DESCRIPTOR
		self.bosh_rid = r.getrandbits(50)
		self.bosh_sid = None
		if locale.getdefaultlocale()[0]:
			self.bosh_xml_lang = locale.getdefaultlocale()[0].split('_')[0]
		else:
			self.bosh_xml_lang = 'en'

		self.http_version = 'HTTP/1.1'
		self.http_persistent = False
		self.http_pipelining = False
		self.bosh_to = domain

		self.route_host, self.route_port = xmpp_server

		self.bosh_wait = bosh_dict['bosh_wait']
		self.bosh_hold = bosh_dict['bosh_hold']
		self.bosh_host = bosh_dict['host']
		self.bosh_port = bosh_dict['port']
		self.bosh_content = bosh_dict['bosh_content']

		self.http_socks = []
		self.stanzas_to_send = []
		self.prio_bosh_stanza = None
		self.current_recv_handler = None

		# if proxy_host .. do sth about HTTP proxy etc.
		

	def connect(self, conn_5tuple, on_connect, on_connect_failure):
		NonBlockingTransport.connect(self, conn_5tuple, on_connect, on_connect_failure)
		self.http_socks.append(self.get_http_socket())
		self.tcp_connection_started()

		# this connect() is not needed because sockets can be connected on send but 
		# we need to know if host is reachable in order to invoke callback for
		# failure when connecting (it's different than callback for errors 
		# occurring after connection is etabilished)

		self.http_socks[0].connect(
			conn_5tuple = conn_5tuple,
			on_connect = lambda: self._on_connect(self.http_socks[0]),
			on_connect_failure = self._on_connect_failure)



	def get_fd(self):
		return self.fake_fd

	def on_http_request_possible(self):
		'''
		Called after HTTP response is received - another request is possible. 
		There should be always one pending request on BOSH CM.
		'''
		log.info('on_http_req possible, stanzas in list: %s, state:\n%s' % 
				(self.stanzas_to_send, self.get_current_state()))
		# if one of sockets is connecting, sth is about to be sent - we don't have to
		# send request from here
		for s in self.http_socks:
			if s.state==CONNECTING or s.pending_requests>0: return
		self.flush_stanzas()


	def flush_stanzas(self):
		# another to-be-locked candidate
		log.info('flushing stanzas')
		if self.prio_bosh_stanza:
			tmp = self.prio_bosh_stanza
			self.prio_bosh_stanza = None
		else:
			tmp = self.stanzas_to_send
			self.stanzas_to_send = []
		self.send_http(tmp)


	def send(self, stanza, now=False):
		# body tags should be send only via send_http()
		assert(not isinstance(stanza, BOSHBody))
		now = True
		if now:
			self.send_http([stanza])
		else:
			self.stanzas_to_send.append(stanza)


	def send_http(self, payload):
		# "Protocol" and string/unicode stanzas should be sent via send()
		# (only initiating and terminating BOSH stanzas should be send via send_http)
		assert(isinstance(payload, list) or isinstance(payload, BOSHBody))
		log.warn('send_http: stanzas: %s\n%s' % (payload, self.get_current_state()))

		if isinstance(payload, list):
			bosh_stanza = self.boshify_stanzas(payload)
		else:
			# bodytag_payload is <body ...>, we don't boshify, only add the rid
			bosh_stanza = payload
		picked_sock = self.pick_socket()
		if picked_sock:
			log.info('sending to socket %s' % id(picked_sock))
			bosh_stanza.setAttr('rid', self.get_rid())
			picked_sock.send(bosh_stanza)
		else:
			# no socket was picked but one is about to connect - save the stanza and
			# return
			if self.prio_bosh_stanza:
				payload = self.merge_stanzas(payload, self.prio_bosh_stanza)
				if payload is None:
					log.error('Error in BOSH socket handling - unable to send %s because %s\
					is already about to be sent' % (payload, self.prio_bosh_stanza))
					self.disconnect()
			self.prio_bosh_stanza = payload

	def merge_stanzas(self, s1, s2):
		if isinstance(s1, BOSHBody):
			if isinstance(s2, BOSHBody):
				# both are boshbodies
				return
			else:
				s1.setPayload(s2, add=True)
				return s1
		elif isinstance(s2, BOSHBody):
			s2.setPayload(s1, add=True)
			return s2
		else:
			#both are lists
			s1.extend(s2)
			return s1

		
	def get_current_state(self):
		t = '\t\tSOCKET_ID\tSOCKET_STATE\tPENDING_REQS\n'
		for s in self.http_socks:
			t = '%s\t\t%s\t%s\t%s\n' % (t,id(s), s.state, s.pending_requests)
		return t
		

	def pick_socket(self):
		# try to pick connected socket with no pending reqs
		for s in self.http_socks:
			if s.state == CONNECTED and s.pending_requests == 0:
				return s

		# try to connect some disconnected socket 
		for s in self.http_socks:
			if s.state==DISCONNECTED:
				self.connect_and_flush(s)
				return

		# if there is any just-connecting socket, it will send the data in its 
		# connect callback
		for s in self.http_socks:
			if s.state==CONNECTING:
				return
		# being here means there are only CONNECTED scokets with pending requests.
		# Lets create and connect another one
		s = self.get_http_socket()
		self.http_socks.append(s)
		self.connect_and_flush(s)
		return


	def connect_and_flush(self, socket):
		socket.connect(
			conn_5tuple = self.conn_5tuple, 
			on_connect = self.flush_stanzas,
			on_connect_failure = self.disconnect)


	def boshify_stanzas(self, stanzas=[], body_attrs=None):
		''' wraps zero to many stanzas by body tag with xmlns and sid '''
		log.debug('boshify_staza - type is: %s, stanza is %s' % (type(stanzas), stanzas))
		tag = BOSHBody(attrs={'sid': self.bosh_sid})
		tag.setPayload(stanzas)
		return tag


	def get_initial_bodytag(self, after_SASL=False):
		return BOSHBody(
			attrs={'content': self.bosh_content,
				'hold': str(self.bosh_hold),
				'route': '%s:%s' % (self.route_host, self.route_port),
				'to': self.bosh_to,
				'wait': str(self.bosh_wait),
				'xml:lang': self.bosh_xml_lang,
				'xmpp:version': '1.0',
				'ver': '1.6',
				'xmlns:xmpp': 'urn:xmpp:xbosh'})

	def get_after_SASL_bodytag(self):
		return BOSHBody(
			attrs={	'to': self.bosh_to,
				'sid': self.bosh_sid,
				'xml:lang': self.bosh_xml_lang,
				'xmpp:version': '1.0',
				'xmpp:restart': 'true',
				'xmlns:xmpp': 'urn:xmpp:xbosh'})

	def get_closing_bodytag(self):
		return BOSHBody(attrs={'sid': self.bosh_sid, 'type': 'terminate'})

	def get_rid(self):
		self.bosh_rid = self.bosh_rid + 1
		return str(self.bosh_rid)


	def get_http_socket(self):
		s = NonBlockingHTTP(
			raise_event=self.raise_event,
			on_disconnect=self.disconnect,
			idlequeue = self.idlequeue,
			on_http_request_possible = self.on_http_request_possible,
			http_uri = self.bosh_host,			
			http_port = self.bosh_port,
			http_version = self.http_version)
		if self.current_recv_handler:
			s.onreceive(self.current_recv_handler)
		return s

	def onreceive(self, recv_handler):
		if recv_handler is None:
			recv_handler = self._owner.Dispatcher.ProcessNonBlocking
		self.current_recv_handler = recv_handler
		for s in self.http_socks:
			s.onreceive(recv_handler)

	def disconnect(self, do_callback=True):
		if self.state == DISCONNECTED: return

		for s in self.http_socks:
			s.disconnect(do_callback=False)
		NonBlockingTransport.disconnect(self, do_callback)

