
import unittest
from unittest.mock import MagicMock

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.modules.contacts import Contacts
from gajim.common.modules.contacts import BareContact
from gajim.common.storage.cache import CacheStorage


class ContactTest(unittest.TestCase):
    def test_contact_object(self):
        account = 'testacc'
        jid = JID.from_string('user@example.org')
        module = Contacts(MagicMock())

        app.storage.cache = CacheStorage(in_memory=True)
        app.storage.cache.init()

        contact = BareContact(module._log, jid, account)
        contact2 = BareContact(module._log, jid, account)

        self.assertEqual(contact, contact2)
        self.assertEqual(hash(contact), hash(contact2))


if __name__ == '__main__':
    unittest.main()
