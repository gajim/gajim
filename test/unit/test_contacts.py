'''
Test for Contact, GC_Contact and Contacts
'''
import unittest

import lib
lib.setup_env()

from common.contacts import CommonContact, Contact, GC_Contact, LegacyContactsAPI
from nbxmpp import NS_MUC

from common import caps_cache

class TestCommonContact(unittest.TestCase):

    def setUp(self):
        self.contact = CommonContact(jid='', account="", resource='', show='',
            status='', name='', our_chatstate=None, chatstate=None,
            client_caps=None)

    def test_default_client_supports(self):
        '''
        Test the caps support method of contacts.
        See test_caps for more enhanced tests.
        '''
        caps_cache.capscache = caps_cache.CapsCache()
        self.assertTrue(self.contact.supports(NS_MUC),
                msg="Must not backtrace on simple check for supported feature")

        self.contact.client_caps = caps_cache.NullClientCaps()

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
            "chatstate", "client_caps", "priority", "sub"]
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
            "chatstate", "client_caps", "role", "room_jid"]
        for attr in attributes:
            self.assertTrue(hasattr(self.contact, attr), msg="expected: " + attr)


class TestContacts(unittest.TestCase):

    def setUp(self):
        self.contacts = LegacyContactsAPI()

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

    def test_legacy_accounts_handling(self):
        self.contacts.add_account("one")
        self.contacts.add_account("two")

        self.contacts.change_account_name("two", "old")
        self.contacts.remove_account("one")

        self.assertEqual(["old"], self.contacts.get_accounts())

    def test_legacy_contacts_from_groups(self):
        jid1 = "test1@gajim.org"
        jid2 = "test2@gajim.org"
        account = "account"
        group = "GroupA"

        contact1 = self.contacts.create_contact(jid=jid1, account=account,
                groups=[group])
        self.contacts.add_contact(account, contact1)

        contact2 = self.contacts.create_contact(jid=jid2, account=account,
                groups=[group])
        self.contacts.add_contact(account, contact2)

        self.assertEqual(2, len(self.contacts.get_contacts_from_group(account, group)))
        self.assertEqual(0, len(self.contacts.get_contacts_from_group(account, '')))


if __name__ == "__main__":
    unittest.main()
