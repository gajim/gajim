'''
Tests for caps network coding
'''
import unittest

import lib
lib.setup_env()

from common import caps_cache
from common.protocol import caps
from common.contacts import Contact

from mock import Mock

from common.xmpp import simplexml
from common.xmpp import protocol

class TestableConnectionCaps(caps.ConnectionCaps):

	def __init__(self, *args, **kwargs):
		self._mocked_contacts = {}
		caps.ConnectionCaps.__init__(self, *args, **kwargs)

	def _get_contact_or_gc_contact_for_jid(self, jid):
		"""
		Overwrite to decouple form contact handling
		"""
		if jid not in self._mocked_contacts:
			self._mocked_contacts[jid] = Mock(realClass=Contact)
			self._mocked_contacts[jid].jid = jid
		return self._mocked_contacts[jid]

	def discoverInfo(self, *args, **kwargs):
		pass

	def get_mocked_contact_for_jid(self, jid):
		return self._mocked_contacts[jid]


class TestConnectionCaps(unittest.TestCase):

	def test_capsPresenceCB(self):
		jid = "user@server.com/a"
		connection_caps = TestableConnectionCaps("account",
			self._build_assertering_dispatcher_function("CAPS_RECEIVED", jid),
			Mock(), caps_cache.create_suitable_client_caps)

		xml = """<presence from='user@server.com/a' to='%s' id='123'>
						<c node='http://gajim.org' ver='pRCD6cgQ4SDqNMCjdhRV6TECx5o='
							hash='sha-1' xmlns='http://jabber.org/protocol/caps'/>
					</presence>
				""" % (jid)
		iq = protocol.Iq(node=simplexml.XML2Node(xml))
		connection_caps._capsPresenceCB(None, iq)

		self.assertTrue(self._dispatcher_called, msg="Must have received caps")

		client_caps = connection_caps.get_mocked_contact_for_jid(jid).client_caps
		self.assertTrue(client_caps, msg="Client caps must be set")
		self.assertFalse(isinstance(client_caps, caps_cache.NullClientCaps),
			msg="On receive of proper caps, we must not use the fallback")

	def _build_assertering_dispatcher_function(self, expected_event, jid):
		self._dispatcher_called = False
		def dispatch(event, data):
			self.assertFalse(self._dispatcher_called, msg="Must only be called once")
			self._dispatcher_called = True
			self.assertEqual(expected_event, event)
			self.assertEqual(jid, data[0])
		return dispatch
	
if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
