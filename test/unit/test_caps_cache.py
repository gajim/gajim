'''
Tests for capabilities and the capabilities cache
'''
import unittest

import lib
lib.setup_env()

from nbxmpp import NS_MUC, NS_PING, NS_XHTML_IM, Iq
from gajim.common import caps_cache as caps
from gajim.common.contacts import Contact
from gajim.common.connection_handlers_events import AgentInfoReceivedEvent

from mock import Mock

COMPLEX_EXAMPLE = '''
<iq from='benvolio@capulet.lit/230193' id='disco1' to='juliet@capulet.lit/chamber' type='result'>
<query xmlns='http://jabber.org/protocol/disco#info' node='http://psi-im.org#q07IKJEyjvHSyhy//CH0CxmKi8w='>
<identity xml:lang='en' category='client' name='Psi 0.11' type='pc'/>
<identity xml:lang='el' category='client' name='Ψ 0.11' type='pc'/>
<feature var='http://jabber.org/protocol/caps'/>
<feature var='http://jabber.org/protocol/disco#info'/>
<feature var='http://jabber.org/protocol/disco#items'/>
<feature var='http://jabber.org/protocol/muc'/>
<x xmlns='jabber:x:data' type='result'>
<field var='FORM_TYPE' type='hidden'>
<value>urn:xmpp:dataforms:softwareinfo</value>
</field>
<field var='ip_version'>
<value>ipv4</value>
<value>ipv6</value>
</field>
<field var='os'>
<value>Mac</value>
</field>
<field var='os_version'>
<value>10.5.1</value>
</field>
<field var='software'>
<value>Psi</value>
</field>
<field var='software_version'>
<value>0.11</value>
</field>
</x>
</query>
</iq>'''


class CommonCapsTest(unittest.TestCase):

    def setUp(self):
        self.caps_method = 'sha-1'
        self.caps_hash = 'm3P2WeXPMGVH2tZPe7yITnfY0Dw='
        self.client_caps = (self.caps_method, self.caps_hash)

        self.node = "http://gajim.org"
        self.identity = {'category': 'client', 'type': 'pc', 'name':'Gajim'}

        self.identities = [self.identity]
        self.features = [NS_MUC, NS_XHTML_IM] # NS_MUC not supported!

        # Simulate a filled db
        db_caps_cache = [
                        (self.caps_method, self.caps_hash, self.identities, self.features),
                        ('old', self.node + '#' + self.caps_hash, self.identities, self.features)]
        self.logger = Mock(returnValues={"iter_caps_data":db_caps_cache})

        self.cc = caps.CapsCache(self.logger)
        caps.capscache = self.cc


class TestCapsCache(CommonCapsTest):

    def test_set_retrieve(self):
        ''' Test basic set / retrieve cycle '''

        self.cc[self.client_caps].identities = self.identities
        self.cc[self.client_caps].features = self.features

        self.assertTrue(NS_MUC in self.cc[self.client_caps].features)
        self.assertTrue(NS_PING not in self.cc[self.client_caps].features)

        identities = self.cc[self.client_caps].identities

        self.assertEqual(1, len(identities))

        identity = identities[0]
        self.assertEqual('client', identity['category'])
        self.assertEqual('pc', identity['type'])

    def test_set_and_store(self):
        ''' Test client_caps update gets logged into db '''

        item = self.cc[self.client_caps]
        item.set_and_store(self.identities, self.features)

        self.logger.mockCheckCall(0, "add_caps_entry", self.caps_method,
                        self.caps_hash, self.identities, self.features)

    def test_initialize_from_db(self):
        ''' Read cashed dummy data from db '''
        self.assertEqual(self.cc[self.client_caps].status, caps.NEW)
        self.cc.initialize_from_db()
        self.assertEqual(self.cc[self.client_caps].status, caps.CACHED)

    def test_preload_triggering_query(self):
        ''' Make sure that preload issues a disco '''
        connection = Mock()
        client_caps = caps.ClientCaps(self.caps_hash, self.node, self.caps_method)

        self.cc.query_client_of_jid_if_unknown(connection, "test@gajim.org",
                        client_caps)

        self.assertEqual(1, len(connection.mockGetAllCalls()))

    def test_no_preload_query_if_cashed(self):
        ''' Preload must not send a query if the data is already cached '''
        connection = Mock()
        client_caps = caps.ClientCaps(self.caps_hash, self.node, self.caps_method)

        self.cc.initialize_from_db()
        self.cc.query_client_of_jid_if_unknown(connection, "test@gajim.org",
                        client_caps)

        self.assertEqual(0, len(connection.mockGetAllCalls()))

    def test_hash(self):
        '''tests the hash computation'''
        stanza = Iq(node=COMPLEX_EXAMPLE)
        identities, features, data, _ = AgentInfoReceivedEvent.parse_stanza(stanza)
        computed_hash = caps.compute_caps_hash(identities, features, data)
        self.assertEqual('q07IKJEyjvHSyhy//CH0CxmKi8w=', computed_hash)


class TestClientCaps(CommonCapsTest):

    def setUp(self):
        CommonCapsTest.setUp(self)
        self.client_caps = caps.ClientCaps(self.caps_hash, self.node, self.caps_method)

    def test_query_by_get_discover_strategy(self):
        ''' Client must be queried if the data is unkown '''
        connection = Mock()
        discover = self.client_caps.get_discover_strategy()
        discover(connection, "test@gajim.org")

        connection.mockCheckCall(0, "discoverInfo", "test@gajim.org",
                        "http://gajim.org#m3P2WeXPMGVH2tZPe7yITnfY0Dw=")

    def test_client_supports(self):
        self.assertTrue(caps.client_supports(self.client_caps, NS_PING),
                        msg="Assume supported, if we don't have caps")

        self.assertFalse(caps.client_supports(self.client_caps, NS_XHTML_IM),
                msg="Must not assume blacklisted feature is supported on default")

        self.cc.initialize_from_db()

        self.assertFalse(caps.client_supports(self.client_caps, NS_PING),
                        msg="Must return false on unsupported feature")

        self.assertTrue(caps.client_supports(self.client_caps, NS_XHTML_IM),
                        msg="Must return True on supported feature")

        self.assertTrue(caps.client_supports(self.client_caps, NS_MUC),
                        msg="Must return True on supported feature")


class TestOldClientCaps(TestClientCaps):

    def setUp(self):
        TestClientCaps.setUp(self)
        self.client_caps = caps.OldClientCaps(self.caps_hash, self.node)

    def test_query_by_get_discover_strategy(self):
        ''' Client must be queried if the data is unknown '''
        connection = Mock()
        discover = self.client_caps.get_discover_strategy()
        discover(connection, "test@gajim.org")

        connection.mockCheckCall(0, "discoverInfo", "test@gajim.org")

if __name__ == '__main__':
    unittest.main()
