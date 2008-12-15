# tests for xmpppy's dispatcher_nb.py
import unittest

import lib
lib.setup_env()

from mock import Mock

from common.xmpp import dispatcher_nb
from common.xmpp import auth_nb

class TestDispatcherNB(unittest.TestCase):
	def test_unbound_namespace_prefix(self):
		'''tests our handling of a message with an unbound namespace prefix'''
		d = dispatcher_nb.XMPPDispatcher()

		conn = Mock()

		owner = Mock()
		owner._caller = Mock()
		owner.defaultNamespace = auth_nb.NS_CLIENT
		owner.debug_flags = []
		owner.Connection = conn
		owner._component = False

		d._owner = owner
		d.plugin(owner)

		msgs = []

		def _got_message(conn, msg):
			msgs.append(msg)

		d.RegisterHandler('message', _got_message)

		d.StreamInit()

		d.ProcessNonBlocking("<stream:stream xmlns:stream='http://etherx.jabber.org/streams' xmlns='jabber:client'>")

		# should be able to parse a normal message
		d.ProcessNonBlocking('<message><body>hello</body></message>')
		self.assertEqual(1, len(msgs))

		d.ProcessNonBlocking('<message><x:y/></message>')
		# we should not have been disconnected after that message
		self.assertEqual(0, len(conn.mockGetNamedCalls('pollend')))

		# we should be able to keep parsing
		d.ProcessNonBlocking('<message><body>still here?</body></message>')
		self.assertEqual(3, len(msgs))

if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
