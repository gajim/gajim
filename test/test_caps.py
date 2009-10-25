'''
Tests for capabilities and the capabilities cache
'''
import unittest

import lib
lib.setup_env()

from common import helpers
from common.contacts import Contact
from common.caps import CapsCache

from mock import Mock

		
class CommonCapsTest(unittest.TestCase):	
	
	def setUp(self):
		self.caps_method = 'sha-1'
		self.caps_hash = 'RNzJvJnTWqczirzu+YF4V8am9ro='
		self.caps = (self.caps_method, self.caps_hash)
		
		self.node = "http://gajim.org"
		self.identity = {'category': 'client', 'type': 'pc', 'name':'Gajim'}

		self.muc = 'http://jabber.org/protocol/muc'
		self.chatstates = 'http://jabber.org/protocol/chatstates'

		self.identities = [self.identity]
		self.features = [self.muc]
			
			
class TestCapsCache(CommonCapsTest):
	
	def setUp(self):
		CommonCapsTest.setUp(self)

		# Simulate a filled db
		db_caps_cache = [
				(self.caps_method, self.caps_hash, self.identities, self.features),
				(self.caps_method, self.caps_hash, self.identities, self.features)]
		self.logger = Mock(returnValues={"iter_caps_data":db_caps_cache})
		
		self.cc = CapsCache(self.logger)

	def test_set_retrieve(self):
		''' Test basic set / retrieve cycle '''

		self.cc[self.caps].identities = self.identities
		self.cc[self.caps].features = self.features

		self.assert_(self.muc in self.cc[self.caps].features)
		self.assert_(self.chatstates not in self.cc[self.caps].features)

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
		
		connection.mockCheckCall(0, "discoverInfo", 'test@gajim.org', 
				'http://gajim.org#RNzJvJnTWqczirzu+YF4V8am9ro=')
		
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
		
		self.assertTrue(self.cc.is_supported(contact, self.chatstates),
				msg="Assume everything is supported, if we don't have caps")
		
		self.cc.initialize_from_db()
		
		self.assertFalse(self.cc.is_supported(contact, self.chatstates),
				msg="Must return false on unsupported feature")
		
		self.assertTrue(self.cc.is_supported(contact, self.muc),
				msg="Must return True on supported feature")
		
	def test_hash(self):
		'''tests the hash computation'''
		computed_hash = helpers.compute_caps_hash(self.identities, self.features)
		self.assertEqual(self.caps_hash, computed_hash)




if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
