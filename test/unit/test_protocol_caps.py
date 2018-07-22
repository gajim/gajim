'''
Tests for caps network coding
'''

import unittest
from unittest.mock import MagicMock

import nbxmpp

import lib
lib.setup_env()

from gajim.common import app
from gajim.common import nec
from gajim.common import ged
from gajim.common import caps_cache
from gajim.common.modules.caps import Caps


class TestConnectionCaps(unittest.TestCase):

    def setUp(self):
        app.contacts.add_account('account')
        contact = app.contacts.create_contact(
            'user@server.com', 'account', resource='a')
        app.contacts.add_contact('account', contact)

        app.nec = nec.NetworkEventsController()
        app.ged.register_event_handler(
            'caps-presence-received', ged.GUI2,
            self._nec_caps_presence_received)

        self.module = Caps(MagicMock())
        self.module._account = 'account'
        self.module._capscache = MagicMock()

    def _nec_caps_presence_received(self, obj):
        self.assertTrue(
            isinstance(obj.client_caps, caps_cache.ClientCaps),
            msg="On receive of valid caps, ClientCaps should be returned")

    def test_capsPresenceCB(self):
        fjid = "user@server.com/a"

        xml = """<presence from='user@server.com/a' to='%s' id='123'>
            <c node='http://gajim.org' ver='pRCD6cgQ4SDqNMCjdhRV6TECx5o='
            hash='sha-1' xmlns='http://jabber.org/protocol/caps'/>
            </presence>
        """ % (fjid)
        msg = nbxmpp.protocol.Presence(node=nbxmpp.simplexml.XML2Node(xml))
        self.module._presence_received(None, msg)


if __name__ == '__main__':
    unittest.main()
