'''
Tests for smacks.py Stream Management
'''
import unittest

import lib
lib.setup_env()

from mock import Mock

from common.xmpp import dispatcher_nb
from common.xmpp import protocol
from common.xmpp import smacks

class TestDispatcherNB(unittest.TestCase):
    '''
    Test class for NonBlocking dispatcher. Tested dispatcher will be plugged
    into a mock client
    '''
    def setUp(self):
        self.dispatcher = dispatcher_nb.XMPPDispatcher()

        # Setup mock client
        self.client = Mock()
        self.client.__str__ = lambda: 'Mock' # FIXME: why do I need this one?
        self.client._caller = Mock()
        self.client.defaultNamespace = protocol.NS_CLIENT
        self.client.Connection = Mock() # mock transport
        self.con = self.client.Connection
        self.con.sm = smacks.Smacks(self.con)

    def tearDown(self):
        # Unplug if needed
        if hasattr(self.dispatcher, '_owner'):
            self.dispatcher.PlugOut()

    def _simulate_connect(self):
        self.dispatcher.PlugIn(self.client) # client is owner
        self.con.sm.set_owner(self.client)
        self.dispatcher.sm = self.con.sm
        # Simulate that we have established a connection
        self.dispatcher.StreamInit()
        self.dispatcher.ProcessNonBlocking("<stream:stream "
            "xmlns:stream='http://etherx.jabber.org/streams' "
            "xmlns='jabber:client'>")
        self.dispatcher.ProcessNonBlocking("<stream:features> "
            "<sm xmlns='urn:xmpp:sm:2'> <optional/> </sm> </stream:features>")
        self.con.sm.negociate()
        self.dispatcher.ProcessNonBlocking("<enabled xmlns='urn:xmpp:sm:2' "
            "id='some-long-sm-id' resume='true'/>")
        assert(self.con.sm.enabled)

    def _simulate_resume(self):
        self.con.sm.resume_request()
        # Resuming acknowledging 5 stanzas
        self.dispatcher.ProcessNonBlocking("<resumed xmlns='urn:xmpp:sm:2' "
            "id='some-long-sm-id' h='5'/>")
        assert(self.con.sm.resuming)

    def _send(self, send, r, stanza):
        for i in range(r):
            send(stanza)
    def test_messages(self):
        message = '<message><body>Helloo </body></message>'
        iq = '''<iq from='proxy.jabber.ru' to='j.xxxxxxxx.org/Gajim' type='error' id='18'>
		    <query xmlns='http://jabber.org/protocol/bytestreams'/>
		    <error code='403' type='auth'>
		    <forbidden xmlns='urn:ietf:params:xml:ns:xmpp-stanzas'/>
		    </error>
		    </iq>'''
        presence = '''<presence from='xxxxxxxxx.com/Talk.v1044194B1E2' to='j.xxxxxxxx.org'>
		      <priority>24</priority>
		      <c node="http://www.google.com/xmpp/client/caps" ver="1.0.0.104" ext="share-v1 voice-v1" xmlns="http://jabber.org/protocol/caps"/>
		      <x stamp="20110614T23:17:51" xmlns="jabber:x:delay"/>
		      <status>In love  Kakashi Sensei :P</status>
		      <x xmlns="vcard-temp:x:update">
		      <photo>db4b7c52e39ba28562c74542d5988d47f09108a3</photo>
		      </x>
		      </presence> '''

        self._simulate_connect()
        uqueue = self.con.sm.uqueue
        self.assertEqual(self.con.sm.out_h, 0)
        self.assertEqual(self.con.sm.in_h, 0)

        # The server sends 10 stanzas
        self._send(self.dispatcher.ProcessNonBlocking, 5, message)
        self._send(self.dispatcher.ProcessNonBlocking, 4, iq)
        self._send(self.dispatcher.ProcessNonBlocking, 1, presence)

        # The client has recieved 10 stanzas and sent none
        self.assertEqual(self.con.sm.in_h, 10)
        self.assertEqual(self.con.sm.out_h, 0)

        m = protocol.Message()

        # The client sends 10 stanzas
        for i in range(10):
            m = protocol.Message(body=str(i))
            self.dispatcher.send(m)

        # Client sends 10 stanzas and put them in the queue
        self.assertEqual(self.con.sm.out_h, 10)
        self.assertEqual(len(uqueue), 10)

        # The server acknowledges that it recieved 5 stanzas
        self.dispatcher.ProcessNonBlocking("<a xmlns='urn:xmpp:sm:2' h='5'/>")
        # 5 stanzas are removed from the queue, only 5 stanzas are left

        self.assertEqual(len(uqueue), 5)

        # Check for the right order of stanzas in the queue
        l = ['5', '6', '7', '8', '9']
        for i in uqueue:
            self.assertEqual(i.getBody(), l[0])
            l.pop(0)

    def test_resumption(self):
        self._simulate_connect()

        m = protocol.Message()

        # The client sends 5 stanzas
        for i in range(5):
            m = protocol.Message(body=str(i))
            self.dispatcher.send(m)

        self._simulate_resume()
        # No stanzas left
        self.assertEqual(len(self.con.sm.uqueue), 0)

if __name__ == '__main__':
    unittest.main()