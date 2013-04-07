'''
Tests for caps network coding
'''
import unittest

import lib
lib.setup_env()

from common import gajim
from common import nec
from common import ged
from common import caps_cache
from common.connection_handlers import ConnectionHandlers
from common.protocol import caps
from common.contacts import Contact
from common.connection_handlers_events import CapsPresenceReceivedEvent

from mock import Mock

import nbxmpp

class TestableConnectionCaps(ConnectionHandlers, caps.ConnectionCaps):

    def __init__(self, *args, **kwargs):
        self.name = 'account'
        self._mocked_contacts = {}
        caps.ConnectionCaps.__init__(self, *args, **kwargs)

    def _get_contact_or_gc_contact_for_jid(self, jid):
        """
        Overwrite to decouple form contact handling
        """
        if jid not in self._mocked_contacts:
            self._mocked_contacts[jid] = Mock(realClass=Contact)
            self._mocked_contacts[jid].jid = jid
        return self._mocked_contacts[jid]

    def discoverInfo(self, *args, **kwargs):
        pass

    def get_mocked_contact_for_jid(self, jid):
        return self._mocked_contacts[jid]


class TestConnectionCaps(unittest.TestCase):

    def setUp(self):
        gajim.nec = nec.NetworkEventsController()
        gajim.ged.register_event_handler('caps-presence-received', ged.GUI2,
            self._nec_caps_presence_received)

    def _nec_caps_presence_received(self, obj):
        self.assertFalse(isinstance(obj.client_caps, caps_cache.NullClientCaps),
            msg="On receive of proper caps, we must not use the fallback")

    def test_capsPresenceCB(self):
        fjid = "user@server.com/a"

        connection_caps = TestableConnectionCaps("account", Mock(),
            caps_cache.create_suitable_client_caps)

        contact = connection_caps._get_contact_or_gc_contact_for_jid(fjid)

        xml = """<presence from='user@server.com/a' to='%s' id='123'>
            <c node='http://gajim.org' ver='pRCD6cgQ4SDqNMCjdhRV6TECx5o='
            hash='sha-1' xmlns='http://jabber.org/protocol/caps'/>
            </presence>
        """ % (fjid)
        msg = nbxmpp.protocol.Presence(node=nbxmpp.simplexml.XML2Node(xml))
        connection_caps._presenceCB(None, msg)

if __name__ == '__main__':
    unittest.main()
