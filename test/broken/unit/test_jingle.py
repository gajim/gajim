'''
Tests for dispatcher.py
'''
import unittest

import lib
lib.setup_env()

from mock import Mock


from nbxmpp import dispatcher
from nbxmpp.namespaces import Namespace

from gajim.common.protocol.bytestream import ConnectionIBBytestream
from gajim.common.protocol.bytestream import ConnectionSocks5Bytestream
from gajim.common.jingle import ConnectionJingle
from gajim.common import app
from gajim.common.socks5 import SocksQueue


session_init = '''
<iq xmlns="jabber:client" to="jingleft@thiessen.im/Gajim" type="set" id="43">
<jingle xmlns="urn:xmpp:jingle:1" action="session-initiate" initiator="jtest@thiessen.im/Gajim" sid="38">
<content name="fileWL1Y2JIPTM5RAD68" creator="initiator">
<security xmlns="urn:xmpp:jingle:security:xtls:0">
<method name="x509" />
</security>
<description xmlns="urn:xmpp:jingle:apps:file-transfer:1">
<offer>
<file xmlns="http://jabber.org/protocol/si/profile/file-transfer" name="to" size="2273">
<desc />
</file>
</offer>
</description>
<transport xmlns="urn:xmpp:jingle:transports:s5b:1" sid="39">
<candidate jid="jtest@thiessen.im/Gajim" cid="40" priority="8257536" host="192.168.2.100" type="direct" port="28011" />
<candidate jid="proxy.thiessen.im" cid="41" priority="655360" host="192.168.2.100" type="proxy" port="5000" />
<candidate jid="proxy.jabbim.cz" cid="42" priority="655360" host="192.168.2.100" type="proxy" port="7777" />
</transport>
</content>
</jingle>
</iq>
        '''


transport_info = '''
<iq from='jtest@thiessen.im/Gajim'
    id='hjdi8'
    to='jingleft@thiessen.im/Gajim'
    type='set'>
  <jingle xmlns='urn:xmpp:jingle:1'
          action='transport-info'
          initiator='jtest@thiessen.im/Gajim'
          sid='38'>
    <content creator='initiator' name='fileWL1Y2JIPTM5RAD68'>
      <transport xmlns='urn:xmpp:jingle:transports:s5b:1'
                 sid='vj3hs98y'>
        <candidate-used cid='hr65dqyd'/>
      </transport>
    </content>
  </jingle>
</iq>

'''

class Connection(Mock, ConnectionJingle, ConnectionSocks5Bytestream,
                 ConnectionIBBytestream):

    def __init__(self):
        Mock.__init__(self)
        ConnectionJingle.__init__(self)
        ConnectionSocks5Bytestream.__init__(self)
        ConnectionIBBytestream.__init__(self)
        self.connected = 2 # This tells gajim we are connected

    def send(self, stanza=None, when=None):
        # Called when gajim wants to send something
        print(str(stanza))


class TestJingle(unittest.TestCase):

    def setUp(self):
        self.dispatcher = dispatcher.XMPPDispatcher()
        app.nec = Mock()
        app.socks5queue = SocksQueue(Mock())
        # Setup mock client
        self.client = Connection()
        self.client.__str__ = lambda: 'Mock' # FIXME: why do I need this one?
        self.client._caller = Connection()
        self.client.defaultNamespace = Namespace.CLIENT
        self.client.Connection = Connection() # mock transport
        self.con = self.client.Connection
        self.con.server_resource = None
        self.con.connection = Connection()

        '''
        Fake file_props when we receive a file. Gajim creates a file_props
        out of a FileRequestReceive event and from then on it changes in
        a lot of places. It is easier to just copy it in here.
        If the session_initiate stanza changes, this also must change.
        '''
        self.receive_file = {'stream-methods':
                             'http://jabber.org/protocol/bytestreams',
                             'sender': 'jtest@thiessen.im/Gajim',
                             'file-name': 'test_received_file',
                             'request-id': '43', 'sid': '39',
                             'session-sid': '38', 'session-type': 'jingle',
                             'transfered_size': [], 'receiver':
                             'jingleft@thiessen.im/Gajim', 'desc': '',
                              'size': '2273', 'type': 'r',
                              'streamhosts': [{'initiator':
                            'jtest@thiessen.im/Gajim',
                            'target': 'jingleft@thiessen.im/Gajim',
                            'cid': '41', 'state': 0, 'host': '192.168.2.100',
                             'type': 'direct', 'port': '28011'},
                            {'initiator': 'jtest@thiessen.im/Gajim',
                              'target': 'jingleft@thiessen.im/Gajim',
                              'cid': '42', 'state': 0, 'host': '192.168.2.100',
                              'type': 'proxy', 'port': '5000'}],
                             'name': 'to'}

    def tearDown(self):
        # Unplug if needed
        if hasattr(self.dispatcher, '_owner'):
            self.dispatcher.PlugOut()

    def _simulate_connect(self):
        self.dispatcher.PlugIn(self.client) # client is owner
        # Simulate that we have established a connection
        self.dispatcher.StreamInit()
        self.dispatcher.ProcessNonBlocking("<stream:stream xmlns:stream='http://etherx.jabber.org/streams' xmlns='jabber:client'>")

    def _simulate_jingle_session(self):

        self.dispatcher.RegisterHandler('iq', self.con._JingleCB, 'set',
                                        Namespace.JINGLE)
        self.dispatcher.ProcessNonBlocking(session_init)
        session = list(self.con._sessions.values())[0] # The only session we have
        jft = list(session.contents.values())[0] # jingleFT object
        jft.file_props = self.receive_file # We plug file_props manually
        # The user accepts to receive the file
        # we have to manually simulate this behavior
        session.approve_session()
        self.con.send_file_approval(self.receive_file)

        self.dispatcher.ProcessNonBlocking(transport_info)

    def test_jingle_session(self):
        self._simulate_connect()
        self._simulate_jingle_session()


if __name__ == '__main__':
    unittest.main()
