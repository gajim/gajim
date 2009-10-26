'''
Test for Contact, GC_Contact and Contacts
'''
import unittest

import lib
lib.setup_env()

from common.contacts import Contact
from common.caps import NullClientCaps

from mock import Mock

class TestContact(unittest.TestCase):

		def test_supports(self):
			''' Test the Entity Capabilities part of the contact instance '''
			
			NS_MUC = 'http://jabber.org/protocol/muc'
			
			# Test with mocks to get basic set/get property behaviour checked
			all_supported_mock_entity_caps = Mock(
						returnValues={"contains_feature": True})
			nothing_supported_mock_entity_caps = Mock(
						returnValues={"contains_feature": False})
			
			contact = Contact()
			
			contact.supports = all_supported_mock_entity_caps			
			self.assertTrue(contact.supports(NS_MUC))
						
			contact.supports = nothing_supported_mock_entity_caps
			self.assertFalse(contact.supports(NS_MUC))
			
			# Test with EntityCapabilites to detect API changes
			contact.supports = NullClientCaps()
			self.assertTrue(contact.supports(NS_MUC),
				msg="Default behaviour is to support everything on unknown caps")
			

if __name__ == "__main__":
		unittest.main()