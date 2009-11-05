'''
Test for Contact, GC_Contact and Contacts
'''
import unittest

import lib
lib.setup_env()
from mock import Mock

from common.contacts import CommonContact, Contact, GC_Contact, Contacts
from common.xmpp import NS_MUC

from common import caps

class TestCommonContact(unittest.TestCase):
	
	def setUp(self):
		self.contact = CommonContact(jid='', account="", resource='', show='',
			status='', name='', our_chatstate=None, composing_xep=None,
			chatstate=None, client_caps=None)

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
		self.contact = Contact(jid="test@gajim.org", account="account")

	def test_attributes_available(self):
		'''This test supports the migration from the old to the new contact
		domain model by smoke testing that no attribute values are lost'''
		
		attributes = ["jid", "resource", "show", "status", "name", "our_chatstate",
			"composing_xep", "chatstate", "client_caps", "priority", "sub"]
		for attr in attributes:
			self.assertTrue(hasattr(self.contact, attr), msg="expected: " + attr)
		

class TestGC_Contact(TestCommonContact):

	def setUp(self):
		TestCommonContact.setUp(self)
		self.contact = GC_Contact(room_jid="confernce@gajim.org", account="account")
	
	def test_attributes_available(self):
		'''This test supports the migration from the old to the new contact
		domain model by asserting no attributes have been lost'''
		
		attributes = ["jid", "resource", "show", "status", "name", "our_chatstate",
			"composing_xep", "chatstate", "client_caps", "role", "room_jid"]
		for attr in attributes:
			self.assertTrue(hasattr(self.contact, attr), msg="expected: " + attr)
			
class TestContacts(unittest.TestCase):
	
	def setUp(self):
		self.contacts = Contacts()
		
	def test_create_add_get_contact(self):
		jid = 'test@gajim.org'
		account = "account"
		
		contact = self.contacts.create_contact(jid=jid, account=account)
		self.contacts.add_contact(account, contact)
		
		retrieved_contact = self.contacts.get_contact(account, jid)
		self.assertEqual(contact, retrieved_contact, "Contact must be known")
		
		self.contacts.remove_contact(account, contact)

		retrieved_contact = self.contacts.get_contact(account, jid)
		self.assertNotEqual(contact, retrieved_contact,
			msg="Contact must not be known any longer")
		
		
	def test_copy_contact(self):
		jid = 'test@gajim.org'
		account = "account"
		
		contact = self.contacts.create_contact(jid=jid, account=account)
		copy = self.contacts.copy_contact(contact)
		self.assertFalse(contact is copy, msg="Must not be the same")
		
		# Not yet implemented to remain backwart compatible
		# self.assertEqual(contact, copy, msg="Must be equal")
		
		
	
	# AUto generated tests. Can be dropped after migration	
	

	def test_creation(self):
		contacts = Contacts()
#Makesureitdoesn'traiseanyexceptions.

	def test_add_account_3_times(self):
		contacts = Contacts()
		
		from common import gajim
		gajim.connections[u'dingdong.org'] = Mock()
		gajim.connections[u'Cool"ch\xe2r\xdf\xe9\xb5\xf6'] = Mock()
		gajim.connections[u'acc1'] = Mock()
		
		self.assertEqual(None, contacts.add_account(account=u'acc1'))
		self.assertEqual(None, contacts.add_account(account=u'Cool"ch\xe2r\xdf\xe9\xb5\xf6'))
		self.assertEqual(None, contacts.add_account(account=u'dingdong.org'))

	def test_add_metacontact_4_times_and_define_metacontacts_3_times(self):
		contacts = Contacts()
		
		from common import gajim
		gajim.connections[u'dingdong.org'] = Mock()
		gajim.connections[u'Cool"ch\xe2r\xdf\xe9\xb5\xf6'] = Mock()
		gajim.connections[u'acc1'] = Mock()
		
		self.assertEqual(None, contacts.define_metacontacts(account=u'acc1', tags_list={}))
		self.assertEqual(None, contacts.define_metacontacts(account=u'Cool"ch\xe2r\xdf\xe9\xb5\xf6', tags_list={}))
		self.assertEqual(None, contacts.define_metacontacts(account=u'dingdong.org', tags_list={}))
		self.assertEqual(None, contacts.add_metacontact(account=u'dingdong.org', brother_account=u'dingdong.org', brother_jid=u'guypsych0\\40h.com@msn.dingdong.org', jid=u'guypsych0%h.com@msn.delx.cjb.net', order=None))
		self.assertEqual(None, contacts.add_metacontact(account=u'dingdong.org', brother_account=u'dingdong.org', brother_jid=u'guypsych0\\40h.com@msn.dingdong.org', jid=u'guypsych0%h.com@msn.jabber.wiretrip.org', order=None))
		self.assertEqual(None, contacts.add_metacontact(account=u'dingdong.org', brother_account=u'dingdong.org', brother_jid=u'guypsych0\\40h.com@msn.dingdong.org', jid=u'guypsycho\\40g.com@gtalk.dingdong.org', order=None))
		self.assertEqual(None, contacts.add_metacontact(account=u'Cool"ch\xe2r\xdf\xe9\xb5\xf6', brother_account=u'acc1', brother_jid=u'samejid@gajim.org', jid=u'samejid@gajim.org', order=None))


if __name__ == "__main__":
		unittest.main()