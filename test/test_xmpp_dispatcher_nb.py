'''
Tests for dispatcher_nb.py
'''
import unittest

import lib
lib.setup_env()

from mock import Mock

from common.xmpp import dispatcher_nb
from common.xmpp import protocol

class TestDispatcherNB(unittest.TestCase):
	'''
	Test class for NonBlocking dispatcher. Tested dispatcher will be plugged
	into a mock client
	'''
	def setUp(self):
		self.dispatcher = dispatcher_nb.XMPPDispatcher()

		# Setup mock client
		self.client = Mock()
		self.client.__str__ = lambda: 'Mock' # FIXME: why do I need this one?
		self.client._caller = Mock()
		self.client.defaultNamespace = protocol.NS_CLIENT
		self.client.Connection = Mock() # mock transport
		self.con = self.client.Connection
	
	def tearDown(self):
		# Unplug if needed
		if hasattr(self.dispatcher, '_owner'):
			self.dispatcher.PlugOut()

	def _simulate_connect(self):
		self.dispatcher.PlugIn(self.client) # client is owner
		# Simulate that we have established a connection
		self.dispatcher.ProcessNonBlocking("<stream:stream xmlns:stream='http://etherx.jabber.org/streams' xmlns='jabber:client'>")

	def test_unbound_namespace_prefix(self):
		'''tests our handling of a message with an unbound namespace prefix'''
		self._simulate_connect()
		
		msgs = []
		def _got_message(conn, msg):
			msgs.append(msg)
		self.dispatcher.RegisterHandler('message', _got_message)

		# should be able to parse a normal message
		self.dispatcher.ProcessNonBlocking('<message><body>hello</body></message>')
		self.assertEqual(1, len(msgs))

		self.dispatcher.ProcessNonBlocking('<message><x:y/></message>')
		self.assertEqual(2, len(msgs))
		# we should not have been disconnected after that message
		self.assertEqual(0, len(self.con.mockGetNamedCalls('pollend')))
		self.assertEqual(0, len(self.con.mockGetNamedCalls('disconnect')))

		# we should be able to keep parsing
		self.dispatcher.ProcessNonBlocking('<message><body>still here?</body></message>')
		self.assertEqual(3, len(msgs))

	def test_process_non_blocking(self):
		''' Check for ProcessNonBlocking return types '''
		self._simulate_connect()
		process = self.dispatcher.ProcessNonBlocking

		# length of data expected
		data = "Please don't fail"
		result = process(data)
		self.assertEqual(result, len(data))

		# no data processed, link shall still be active
		result = process('')
		self.assertEqual(result, '0')
		self.assertEqual(0, len(self.con.mockGetNamedCalls('pollend')) + 
			len(self.con.mockGetNamedCalls('disconnect')))

		# simulate disconnect
		result = process('</stream:stream>')
		self.assertEqual(1, len(self.client.mockGetNamedCalls('disconnect')))

	def test_return_stanza_handler(self):
		''' Test sasl_error_conditions transformation in protocol.py '''
		# quick'n dirty...I wasn't aware of it existance and thought it would
		# always fail :-)
		self._simulate_connect()
		stanza = "<iq type='get' />"
		def send(data):
			self.assertEqual(str(data), '<iq xmlns="jabber:client" type="error"><error code="501" type="cancel"><feature-not-implemented xmlns="urn:ietf:params:xml:ns:xmpp-stanzas" /><text xmlns="urn:ietf:params:xml:ns:xmpp-stanzas">The feature requested is not implemented by the recipient or server and therefore cannot be processed.</text></error></iq>')
		self.client.send = send
		self.dispatcher.ProcessNonBlocking(stanza)


if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
