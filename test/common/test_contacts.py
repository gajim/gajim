# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest
from unittest.mock import MagicMock

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.modules.contacts import BareContact
from gajim.common.storage.cache import CacheStorage


class ContactTest(unittest.TestCase):
    def test_contact_object(self):
        account = 'testacc'
        jid = JID.from_string('user@example.org')

        app.storage.cache = CacheStorage(in_memory=True)
        app.storage.cache.init()

        contact = BareContact(MagicMock(), jid, account)
        contact2 = BareContact(MagicMock(), jid, account)

        self.assertEqual(contact, contact2)
        self.assertEqual(hash(contact), hash(contact2))


if __name__ == '__main__':
    unittest.main()
