'''
Test for Contact, GC_Contact and Contacts
'''
import unittest

import lib
lib.setup_env()

from common.contacts import Contact, GC_Contact
from common.caps import NullClientCaps
from common.xmpp import NS_MUC

class TestCommonContact(unittest.TestCase):
	
	def setUp(self):
		self.contact = Contact()

	def test_default_client_supports(self):
		'''
		Test the caps support method of contacts.
		See test_caps for more enhanced tests.
		'''
		
		self.assertTrue(self.contact.supports(NS_MUC),
			msg="Must not backtrace on simple check for supported feature")
		
		client_caps = NullClientCaps()
		self.contact.set_supported_client_caps(client_caps)
					
		self.assertTrue(self.contact.supports(NS_MUC),
			msg="Must not backtrace on simple check for supported feature")
		
			
class TestContact(TestCommonContact):
	
	def setUp(self):
		TestCommonContact.setUp(self)
		self.contact = Contact()


class TestGC_Contact(TestCommonContact):

	def setUp(self):
		TestCommonContact.setUp(self)
		self.contact = GC_Contact()
			

if __name__ == "__main__":
		unittest.main()