
import protocol, locale, random, dispatcher_nb 
from client_nb import NBCommonClient
import transports_nb
import logging
from simplexml import Node
log = logging.getLogger('gajim.c.x.bosh')


class BOSHClient(NBCommonClient):
	'''
	Client class implementing BOSH. Extends common XMPP  
	'''
	def __init__(self, domain, idlequeue, caller=None):
		'''Preceeds constructor of NBCommonClient and sets some of values that will
		be used as attributes in <body> tag'''
		self.bosh_sid=None

		# with 50-bit random initial rid, session would have to go up
		# to 7881299347898368 messages to raise rid over 2**53 
		# (see http://www.xmpp.org/extensions/xep-0124.html#rids)
		r = random.Random()
		r.seed()
		self.bosh_rid = r.getrandbits(50)
		self.bosh_sid = None

		if locale.getdefaultlocale()[0]:
			self.bosh_xml_lang = locale.getdefaultlocale()[0].split('_')[0]
		else:
			self.bosh_xml_lang = 'en'

		self.http_version = 'HTTP/1.1'
		self.bosh_to = domain

		#self.Namespace = protocol.NS_HTTP_BIND
		#self.defaultNamespace = self.Namespace
		self.bosh_session_on = False

		NBCommonClient.__init__(self, domain, idlequeue, caller)



	def connect(self, on_connect, on_connect_failure, proxy, hostname=None, port=5222, 
		on_proxy_failure=None, secure=None):
		''' 
		Open XMPP connection (open XML streams in both directions).
		:param hostname: hostname of XMPP server from SRV request 
		:param port: port number of XMPP server
		:param on_connect: called after stream is successfully opened
		:param on_connect_failure: called when error occures during connection
		:param on_proxy_failure: called if error occurres during TCP connection to
			proxy server or during connection to the proxy
		:param proxy: dictionary with bosh-related paramters. It should contain at 
			least values for keys 'host' and 'port' - connection details for proxy
			server and optionally keys 'user' and 'pass' as proxy credentials
		:param secure: if 
		'''
		NBCommonClient.connect(self, on_connect, on_connect_failure, hostname, port,
			on_proxy_failure, proxy, secure)

		if hostname:
			self.route_host = hostname
		else:
			self.route_host = self.Server

		assert(proxy.has_key('type'))
		assert(proxy['type']=='bosh')

		self.bosh_wait = proxy['bosh_wait']
		self.bosh_hold = proxy['bosh_hold']
		self.bosh_host = proxy['host']
		self.bosh_port = proxy['port']
		self.bosh_content = proxy['bosh_content']

		# _on_tcp_failure is callback for errors which occur during name resolving or
		# TCP connecting.
		self._on_tcp_failure = self.on_proxy_failure


								
		# in BOSH, client connects to Connection Manager instead of directly to
		# XMPP server ((hostname, port)). If HTTP Proxy is specified, client connects
		# to HTTP proxy and Connection Manager is specified at URI and Host header
		# in HTTP message
				
		# tcp_host, tcp_port is hostname and port for socket connection - Connection
		# Manager or HTTP proxy
		if proxy.has_key('proxy_host') and proxy['proxy_host'] and \
			proxy.has_key('proxy_port') and proxy['proxy_port']:
			
			tcp_host=proxy['proxy_host']
			tcp_port=proxy['proxy_port']

			# user and password for HTTP proxy
			if proxy.has_key('user') and proxy['user'] and \
				proxy.has_key('pass') and proxy['pass']:

				proxy_creds=(proxy['user'],proxy['pass'])
			else:
				proxy_creds=(None, None)

		else:
			tcp_host = transports_nb.urisplit(proxy['host'])[1]
			tcp_port=proxy['port']

			if tcp_host is None:
				self._on_connect_failure("Invalid BOSH URI")
				return

		self.socket = self.get_socket()

		self._resolve_hostname(
			hostname=tcp_host,
			port=tcp_port,
			on_success=self._try_next_ip,
			on_failure=self._on_tcp_failure)

	def _on_stream_start(self):
		'''
		Called after XMPP stream is opened. In BOSH, TLS is negotiated on socket
		connect so success callback can be invoked after TCP connect.
		(authentication is started from auth() method)
		'''
		self.onreceive(None)
		if self.connected == 'tcp':
			self._on_connect()

	def get_socket(self):
		tmp = transports_nb.NonBlockingHTTP(
			raise_event=self.raise_event,
			on_disconnect=self.on_http_disconnect,
			http_uri = self.bosh_host,			
			http_port = self.bosh_port,
			http_version = self.http_version
			)
		tmp.PlugIn(self)
		return tmp

	def on_http_disconnect(self):
		log.info('HTTP socket disconnected')
		#import traceback
		#traceback.print_stack()
		if self.bosh_session_on:
                        self.socket.connect(
				conn_5tuple=self.current_ip,
				on_connect=self.on_http_reconnect,
				on_connect_failure=self.on_disconnect)
		else:
			self.on_disconnect()

	def on_http_reconnect(self):
		self.socket._plug_idle()
		log.info('Connected to BOSH CM again')
		pass


	def on_http_reconnect_fail(self):
		log.error('Error when reconnecting to BOSH CM')
		self.on_disconnect()
		
	def send(self, stanza, now = False):
		(id, stanza_to_send) = self.Dispatcher.assign_id(stanza)

		self.socket.send(
			self.boshify_stanza(stanza_to_send),
			now = now)
		return id

	def get_rid(self):
		# does this need a lock??"
		self.bosh_rid = self.bosh_rid + 1
		return str(self.bosh_rid)

	def get_bodytag(self):
		# this should be called not until after session creation response so sid has
		# to be initialized. 
		assert(hasattr(self, 'bosh_sid'))
		return protocol.BOSHBody(
			attrs={	'rid': self.get_rid(),
				'sid': self.bosh_sid})

	def get_initial_bodytag(self, after_SASL=False):
		tag = protocol.BOSHBody(
			attrs={'content': self.bosh_content,
				'hold': str(self.bosh_hold),
				'route': '%s:%s' % (self.route_host, self.Port),
				'to': self.bosh_to,
				'wait': str(self.bosh_wait),
				'rid': self.get_rid(),
				'xml:lang': self.bosh_xml_lang,
				'xmpp:version': '1.0',
				'ver': '1.6',
				'xmlns:xmpp': 'urn:xmpp:xbosh'})
		if after_SASL:
			tag.delAttr('content')
			tag.delAttr('hold')
			tag.delAttr('route')
			tag.delAttr('wait')
			tag.delAttr('ver')
			# xmpp:restart attribute is essential for stream restart request
			tag.setAttr('xmpp:restart','true')
			tag.setAttr('sid',self.bosh_sid)

		return tag


	def get_closing_bodytag(self):
		closing_bodytag = self.get_bodytag()
		closing_bodytag.setAttr('type', 'terminate')
		return closing_bodytag


	def boshify_stanza(self, stanza=None, body_attrs=None):
		''' wraps stanza by body tag with rid and sid '''
		#log.info('boshify_staza - type is: %s, stanza is %s' % (type(stanza), stanza))
		tag = self.get_bodytag()
		tag.setPayload([stanza])
		return tag


	def on_bodytag_attrs(self, body_attrs):
		#log.info('on_bodytag_attrs: %s' % body_attrs)
		if body_attrs.has_key('type'):
			if body_attrs['type']=='terminated':
				# BOSH session terminated 
				self.bosh_session_on = False
			elif body_attrs['type']=='error':
				# recoverable error
				pass
		if not self.bosh_sid:
			# initial response - when bosh_sid is set
			self.bosh_session_on = True
			self.bosh_sid = body_attrs['sid']
			self.Dispatcher.Stream._document_attrs['id']=body_attrs['authid']

