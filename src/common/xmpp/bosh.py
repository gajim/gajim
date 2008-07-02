
import protocol, simplexml, locale, random, dispatcher_nb 
from client_nb import NBCommonClient
import logging
log = logging.getLogger('gajim.c.x.bosh')


class BOSHClient(NBCommonClient):
	'''
	Client class implementing BOSH. 
	'''
	def __init__(self, *args, **kw):
		'''Preceeds constructor of NBCommonClient and sets some of values that will
		be used as attributes in <body> tag'''
		self.Namespace = protocol.NS_HTTP_BIND
		# BOSH parameters should be given via Advanced Configuration Editor
		self.bosh_xml_lang = None
		self.bosh_hold = 1
		self.bosh_wait=60
		self.bosh_rid=None
		self.bosh_sid=None

		self.bosh_httpversion = 'HTTP/1.1'
		NBCommonClient.__init__(self, *args, **kw)


	def connect(self, *args, **kw):


		if locale.getdefaultlocale()[0]:
			self.bosh_xml_lang = locale.getdefaultlocale()[0].split('_')[0]

		# with 50-bit random initial rid, session would have to go up
		# to 7881299347898368 messages to raise rid over 2**53 
		# (see http://www.xmpp.org/extensions/xep-0124.html#rids)
		r = random.Random()
		r.seed()
		self.bosh_rid = r.getrandbits(50)

		proxy = kw['proxy']
		#self.bosh_protocol, self.bosh_host, self.bosh_uri = transports_nb.urisplit(proxy['host'])
		self.bosh_port = proxy['port']
		self.bosh_wait = proxy['bosh_wait']
		self.bosh_hold = proxy['bosh_hold']
		self.bosh_to = proxy['to']
		#self.bosh_ack = proxy['bosh_ack']
		#self.bosh_secure = proxy['bosh_secure']
		NBCommonClient.connect(self, *args, **kw)
		
	def send(self, stanza, now = False):
		(id, stanza_to_send) = self.Dispatcher.assign_id(stanza)

		self.Connection.send(
			self.boshify_stanza(stanza_to_send),
			now = now)
		return id

	def get_bodytag(self):
		# this should be called not until after session creation response so sid has
		# to be initialized. 
		assert(self.sid is not None)
		self.rid = self.rid+1
		return protocol.BOSHBody(
			attrs={	'rid': str(self.bosh_rid),
				'sid': self.bosh_sid})


	def get_initial_bodytag(self):
		return protocol.BOSHBody(
			attrs={'content': 'text/xml; charset=utf-8',
				'hold': str(self.bosh_hold),
				'to': self.bosh_to,
				'wait': str(self.bosh_wait),
				'rid': str(self.bosh_rid),
				'xmpp:version': '1.0',
				'xmlns:xmpp': 'urn:xmpp:xbosh'}
			)

	def get_closing_bodytag(self):
		closing_bodytag = self.get_bodytag()
		closing_bodytag.setAttr('type', 'terminate')
		return closing_bodytag


	def boshify_stanza(self, stanza):
		''' wraps stanza by body tag or modifies message entirely (in case of stream
		opening and closing'''
		log.info('boshify_staza - type is: %s' % type(stanza))
		if isinstance(stanza, simplexml.Node):
			tag = self.get_bodytag()
			return tag.setPayload(stanza)
		else:
			# only stream initialization and stream terminatoion are not Nodes
			if stanza.startswith(dispatcher_nb.XML_DECLARATION):
				# stream init
				return self.get_initial_bodytag()
			else:
				# should be stream closing
				assert(stanza == dispatcher_nb.STREAM_TERMINATOR)
				return self.get_closing_bodytag()



	def _on_stream_start(self):
		'''
		Called after XMPP stream is opened. In BOSH, TLS is negotiated elsewhere 
		so success callback can be invoked.
		(authentication is started from auth() method)
		'''
		self.onreceive(None)
		if self.connected == 'tcp':
			self._on_connect()
