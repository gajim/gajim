'''
Tests for capabilities and the capabilities cache
'''
from common.caps import NullClientCaps
import unittest

import lib
lib.setup_env()

from common.xmpp import NS_MUC, NS_PING, NS_XHTML_IM
from common import caps
from common.contacts import Contact

from mock import Mock


class CommonCapsTest(unittest.TestCase):

	def setUp(self):
		self.caps_method = 'sha-1'
		self.caps_hash = 'm3P2WeXPMGVH2tZPe7yITnfY0Dw='
		self.client_caps = (self.caps_method, self.caps_hash)

		self.node = "http://gajim.org"
		self.identity = {'category': 'client', 'type': 'pc', 'name':'Gajim'}

		self.identities = [self.identity]
		self.features = [NS_MUC, NS_XHTML_IM] # NS_MUC not supported!

		# Simulate a filled db
		db_caps_cache = [
				(self.caps_method, self.caps_hash, self.identities, self.features),
				('old', self.node + '#' + self.caps_hash, self.identities, self.features)]
		self.logger = Mock(returnValues={"iter_caps_data":db_caps_cache})

		self.cc = caps.CapsCache(self.logger)
		caps.capscache = self.cc


class TestCapsCache(CommonCapsTest):

	def test_set_retrieve(self):
		''' Test basic set / retrieve cycle '''

		self.cc[self.client_caps].identities = self.identities
		self.cc[self.client_caps].features = self.features

		self.assert_(NS_MUC in self.cc[self.client_caps].features)
		self.assert_(NS_PING not in self.cc[self.client_caps].features)

		identities = self.cc[self.client_caps].identities

		self.assertEqual(1, len(identities))

		identity = identities[0]
		self.assertEqual('client', identity['category'])
		self.assertEqual('pc', identity['type'])

	def test_set_and_store(self):
		''' Test client_caps update gets logged into db '''

		item = self.cc[self.client_caps]
		item.set_and_store(self.identities, self.features)

		self.logger.mockCheckCall(0, "add_caps_entry", self.caps_method,
				self.caps_hash, self.identities, self.features)

	def test_initialize_from_db(self):
		''' Read cashed dummy data from db '''
		self.assertEqual(self.cc[self.client_caps].status, caps.NEW)
		self.cc.initialize_from_db()
		self.assertEqual(self.cc[self.client_caps].status, caps.CACHED)

	def test_preload_triggering_query(self):
		''' Make sure that preload issues a disco '''
		connection = Mock()
		client_caps = caps.ClientCaps(self.caps_hash, self.node, self.caps_method)

		self.cc.query_client_of_jid_if_unknown(connection, "test@gajim.org",
				client_caps)

		self.assertEqual(1, len(connection.mockGetAllCalls()))

	def test_no_preload_query_if_cashed(self):
		''' Preload must not send a query if the data is already cached '''
		connection = Mock()
		client_caps = caps.ClientCaps(self.caps_hash, self.node, self.caps_method)

		self.cc.initialize_from_db()
		self.cc.query_client_of_jid_if_unknown(connection, "test@gajim.org",
				client_caps)

		self.assertEqual(0, len(connection.mockGetAllCalls()))

	def test_hash(self):
		'''tests the hash computation'''
		computed_hash = caps.compute_caps_hash(self.identities, self.features)
		self.assertEqual(self.caps_hash, computed_hash)


class TestClientCaps(CommonCapsTest):

	def setUp(self):
		CommonCapsTest.setUp(self)
		self.client_caps = caps.ClientCaps(self.caps_hash, self.node, self.caps_method)

	def test_query_by_get_discover_strategy(self):
		''' Client must be queried if the data is unkown '''
		connection = Mock()
		discover = self.client_caps.get_discover_strategy()
		discover(connection, "test@gajim.org")

		connection.mockCheckCall(0, "discoverInfo", "test@gajim.org",
				"http://gajim.org#m3P2WeXPMGVH2tZPe7yITnfY0Dw=")

	def test_client_supports(self):
		self.assertTrue(caps.client_supports(self.client_caps, NS_PING),
				msg="Assume supported, if we don't have caps")

		self.assertFalse(caps.client_supports(self.client_caps, NS_XHTML_IM),
			msg="Must not assume blacklisted feature is supported on default")

		self.cc.initialize_from_db()

		self.assertFalse(caps.client_supports(self.client_caps, NS_PING),
				msg="Must return false on unsupported feature")

		self.assertTrue(caps.client_supports(self.client_caps, NS_XHTML_IM),
				msg="Must return True on supported feature")

		self.assertTrue(caps.client_supports(self.client_caps, NS_MUC),
				msg="Must return True on supported feature")


class TestOldClientCaps(TestClientCaps):

	def setUp(self):
		TestClientCaps.setUp(self)
		self.client_caps = caps.OldClientCaps(self.caps_hash, self.node)

	def test_query_by_get_discover_strategy(self):
		''' Client must be queried if the data is unknown '''
		connection = Mock()
		discover = self.client_caps.get_discover_strategy()
		discover(connection, "test@gajim.org")

		connection.mockCheckCall(0, "discoverInfo", "test@gajim.org")


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


class TestConnectionCaps(CommonCapsTest):

	def test_capsPresenceCB(self):
		jid = "user@server.com/a"
		connection_caps = TestableConnectionCaps("account",
			self._build_assertering_dispatcher_function("CAPS_RECEIVED", jid))

		xml = """<presence from='user@server.com/a'
								to='%s' id='123'>
						<c node='http://gajim.org' ver='pRCD6cgQ4SDqNMCjdhRV6TECx5o='
							hash='sha-1' xmlns='http://jabber.org/protocol/caps'/>
					</presence>
				""" % (jid)
		iq = protocol.Iq(node=simplexml.XML2Node(xml))
		connection_caps._capsPresenceCB(None, iq)

		self.assertTrue(self._dispatcher_called, msg="Must have received caps")

		client_caps = connection_caps.get_mocked_contact_for_jid(jid).client_caps
		self.assertTrue(client_caps, msg="Client caps must be set")
		self.assertFalse(isinstance(client_caps, NullClientCaps),
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
