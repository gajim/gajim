'''
Test for Contact, GC_Contact and Contacts
'''
import unittest

import lib
lib.setup_env()

from common.contacts import CommonContact, Contact, GC_Contact
from common.xmpp import NS_MUC

from common import caps

class TestCommonContact(unittest.TestCase):
	
	def setUp(self):
		self.contact = CommonContact(jid='', resource='', show='', status='',
			name='', our_chatstate=None, composing_xep=None, chatstate=None,
			client_caps=None)

	def test_default_client_supports(self):
		'''
		Test the caps support method of contacts.
		See test_caps for more enhanced tests.
		'''
		caps.capscache = caps.CapsCache()
		self.assertTrue(self.contact.supports(NS_MUC),
			msg="Must not backtrace on simple check for supported feature")
		
		self.contact.client_caps = caps.NullClientCaps()
					
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