'''
Tests for capabilities and the capabilities cache
'''
import unittest

import lib
lib.setup_env()

from common import helpers
from common.contacts import Contact
from common.xmpp import NS_MUC, NS_PING, NS_XHTML_IM

from common.caps import CapsCache, ClientCaps, OldClientCaps

from mock import Mock

		
class CommonCapsTest(unittest.TestCase):	
	
	def setUp(self):
		self.caps_method = 'sha-1'
		self.caps_hash = 'm3P2WeXPMGVH2tZPe7yITnfY0Dw='
		self.caps = (self.caps_method, self.caps_hash)
		
		self.node = "http://gajim.org"
		self.identity = {'category': 'client', 'type': 'pc', 'name':'Gajim'}

		self.identities = [self.identity]
		self.features = [NS_MUC, NS_XHTML_IM] # NS_MUC not supported!
		
		# Simulate a filled db
		db_caps_cache = [
				(self.caps_method, self.caps_hash, self.identities, self.features),
				('old', self.node + '#' + self.caps_hash, self.identities, self.features)]
		self.logger = Mock(returnValues={"iter_caps_data":db_caps_cache})
		
		self.cc = CapsCache(self.logger)
			
			
class TestCapsCache(CommonCapsTest):
	
	def test_set_retrieve(self):
		''' Test basic set / retrieve cycle '''

		self.cc[self.caps].identities = self.identities
		self.cc[self.caps].features = self.features

		self.assert_(NS_MUC in self.cc[self.caps].features)
		self.assert_(NS_PING not in self.cc[self.caps].features)

		identities = self.cc[self.caps].identities

		self.assertEqual(1, len(identities))

		identity = identities[0]
		self.assertEqual('client', identity['category'])
		self.assertEqual('pc', identity['type'])
		
	def test_update(self):
		''' Test caps update gets logged into db '''
		
		item = self.cc[self.caps]
		item.update(self.identities, self.features)
		
		self.logger.mockCheckCall(0, "add_caps_entry", self.caps_method,
				self.caps_hash, self.identities, self.features)
		
	def test_initialize_from_db(self):
		''' Read cashed dummy data from db ''' 
		self.assertEqual(self.cc[self.caps].queried, 0)
		self.cc.initialize_from_db()
		self.assertEqual(self.cc[self.caps].queried, 2)

	def test_preload_triggering_query(self):
		''' Make sure that preload issues a disco '''
		connection = Mock()
		
		self.cc.preload(connection, "test@gajim.org", self.node,
				self.caps_method, self.caps_hash)
		
		connection.mockCheckCall(0, "discoverInfo", "test@gajim.org", 
				"http://gajim.org#m3P2WeXPMGVH2tZPe7yITnfY0Dw=")
		
	def test_no_preload_query_if_cashed(self):
		''' Preload must not send a query if the data is already cached '''
		connection = Mock()
		
		self.cc.initialize_from_db()
		self.cc.preload(connection, "test@gajim.org", self.node,
				self.caps_method, self.caps_hash)
	
		self.assertEqual(0, len(connection.mockGetAllCalls()))

	def test_is_supported(self):
		contact = Contact(caps_node=self.node,
								caps_hash_method=self.caps_method,
								caps_hash=self.caps_hash)
		
		self.assertTrue(self.cc.is_supported(contact, NS_PING),
				msg="Assume everything is supported, if we don't have caps")
		
		self.cc.initialize_from_db()
		
		self.assertFalse(self.cc.is_supported(contact, NS_PING),
				msg="Must return false on unsupported feature")
		
		self.assertTrue(self.cc.is_supported(contact, NS_MUC),
				msg="Must return True on supported feature")
		
	def test_hash(self):
		'''tests the hash computation'''
		computed_hash = helpers.compute_caps_hash(self.identities, self.features)
		self.assertEqual(self.caps_hash, computed_hash)


class TestClientCaps(CommonCapsTest):
	
	def setUp(self):
		CommonCapsTest.setUp(self)
		self.caps = ClientCaps(self.cc, self.caps_hash, self.node,
			self.caps_method) 
	
	def test_no_query_client_of_jid(self):
		''' Client must not be queried if the data is already cached '''		
		connection = Mock()
		self.cc.initialize_from_db()
		self.caps.query_client_of_jid_if_unknown(connection, "test@gajim.org")
		
		self.assertEqual(0, len(connection.mockGetAllCalls()))
	
	def test_query_client_of_jid_if_unknown(self):
		''' Client must be queried if the data is unkown '''	
		connection = Mock()
		self.caps.query_client_of_jid_if_unknown(connection, "test@gajim.org")	
		
		connection.mockCheckCall(0, "discoverInfo", "test@gajim.org", 
				"http://gajim.org#m3P2WeXPMGVH2tZPe7yITnfY0Dw=")
		
	def test_is_supported(self):		
		self.assertTrue(self.caps.contains_feature(NS_PING),
				msg="Assume supported, if we don't have caps")
		
		self.assertFalse(self.caps.contains_feature(NS_XHTML_IM),
			msg="Must not assume blacklisted feature is supported on default")
		
		self.cc.initialize_from_db()
		
		self.assertFalse(self.caps.contains_feature(NS_PING),
				msg="Must return false on unsupported feature")
		
		self.assertTrue(self.caps.contains_feature(NS_XHTML_IM),
				msg="Must return True on supported feature")
		
		self.assertTrue(self.caps.contains_feature(NS_MUC),
				msg="Must return True on supported feature")	
	

class TestOldClientCaps(TestClientCaps):	

	def setUp(self):
		TestClientCaps.setUp(self)
		self.caps = OldClientCaps(self.cc, self.caps_hash, self.node) 

	def test_no_query_client_of_jid(self):
		''' Client must not be queried if the data is already cached '''		
		connection = Mock()
		self.cc.initialize_from_db()
		self.caps.query_client_of_jid_if_unknown(connection, "test@gajim.org")
		
		self.assertEqual(0, len(connection.mockGetAllCalls()))
	
	def test_query_client_of_jid_if_unknown(self):
		''' Client must be queried if the data is unkown '''	
		connection = Mock()
		self.caps.query_client_of_jid_if_unknown(connection, "test@gajim.org")	
		
		connection.mockCheckCall(0, "discoverInfo", "test@gajim.org")



if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
