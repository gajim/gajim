# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import unittest
from unittest.mock import MagicMock

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common.modules.contacts import BareContact
from gajim.common.settings import Settings
from gajim.common.storage.archive.storage import MessageArchiveStorage
from gajim.common.storage.cache import CacheStorage


class ContactTest(unittest.TestCase):
    def setUp(self) -> None:
        app.settings = Settings(in_memory=True)
        app.settings.init()
        app.settings.add_account("testacc1")
        app.settings.set_account_setting("testacc1", "address", "user@domain.org")

        app.storage.cache = CacheStorage(in_memory=True)
        app.storage.cache.init()
        app.storage.archive = MessageArchiveStorage(in_memory=True)
        app.storage.archive.init()

    def tearDown(self) -> None:
        del app.settings
        del app.storage.cache
        del app.storage.archive

    def test_contact_object(self):
        account = "testacc1"
        jid = JID.from_string("user@domain.org")

        contact = BareContact(MagicMock(), jid, account)
        contact2 = BareContact(MagicMock(), jid, account)

        self.assertEqual(contact, contact2)
        self.assertEqual(hash(contact), hash(contact2))


if __name__ == "__main__":
    unittest.main()
