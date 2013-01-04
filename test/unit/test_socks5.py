'''
Tests for dispatcher_nb.py
'''
import unittest

import lib
lib.setup_env()

from mock import Mock
import sys
import socket

from common.socks5 import *
from common import jingle_xtls

class fake_sock(Mock):
    def __init__(self, sockobj):
        Mock.__init__(self)

        self.sockobj = sockobj


    def setup_stream(self):
        sha1 = self.sockobj._get_sha1_auth()

        self.incoming = []
        self.incoming.append(self.sockobj._get_auth_response())
        self.incoming.append(self.sockobj._get_request_buff(sha1, 0x00))
        self.outgoing = []
        self.outgoing.append(self.sockobj._get_auth_buff())
        self.outgoing.append(self.sockobj._get_request_buff(sha1))

    def switch_stream(self):
        # Roles are reversed, client will be expecting server stream
        # and server will be expecting client stream

        temp = self.incoming
        self.incoming = self.outgoing
        self.outgoing = temp

    def _recv(self, foo):
        return self.incoming.pop(0)

    def _send(self, data):
        # This method is surrounded by a try block,
        # we can't use assert here

        if data != self.outgoing[0]:
            print('FAILED SENDING TEST')
        self.outgoing.pop(0)

class fake_idlequeue(Mock):

    def __init__(self):
        Mock.__init__(self)

    def plug_idle(self, obj, writable=True, readable=True):

        if readable:
            obj.pollin()
        if writable:
            obj.pollout()

class TestSocks5(unittest.TestCase):
    '''
    Test class for Socks5
    '''
    def setUp(self):
        streamhost = { 'host': None,
                       'port': 1,
                       'initiator' : None,
                       'target' : None}
        queue = Mock()
        queue.file_props = {}
        #self.sockobj = Socks5Receiver(fake_idlequeue(), streamhost, None)
        self.sockobj = Socks5Sender(fake_idlequeue(), None, 'server', Mock() ,
                                    None, None, True, file_props={})
        sock = fake_sock(self.sockobj)
        self.sockobj._sock = sock
        self.sockobj._recv = sock._recv
        self.sockobj._send = sock._send
        self.sockobj.state = 1
        self.sockobj.connected = True
        self.sockobj.pollend = self._pollend

        # Something that the receiver needs
        #self.sockobj.file_props['type'] = 'r'

        # Something that the sender needs
        self.sockobj.file_props = {}
        self.sockobj.file_props['type'] = 'r'
        self.sockobj.file_props['paused'] = ''
        self.sockobj.queue = Mock()
        self.sockobj.queue.process_result = self._pollend

    def _pollend(self, foo = None, duu = None):
        # This is a disconnect function
        sys.exit("end of the road")

    def _check_inout(self):
        # Check if there isn't anything else to receive or send
        sock = self.sockobj._sock
        assert(sock.incoming == [])
        assert(sock.outgoing == [])

    def test_connection_server(self):
        return
        mocksock = self.sockobj._sock
        mocksock.setup_stream()
        #self.sockobj._sock.switch_stream()
        s = socket.socket(2, 1, 6)
        server = ('127.0.0.1', 28000)

        s.connect(server)

        s.send(mocksock.outgoing.pop(0))
        self.assertEquals(s.recv(64), mocksock.incoming.pop(0))

        s.send(mocksock.outgoing.pop(0))
        self.assertEquals(s.recv(64), mocksock.incoming.pop(0))

    def test_connection_client(self):


        mocksock = self.sockobj._sock
        mocksock.setup_stream()
        mocksock.switch_stream()
        s = socket.socket(10, 1, 6)


        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        s.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        netadd = ('::', 28000, 0, 0)
        s.bind(netadd)
        s.listen(socket.SOMAXCONN)
        (s, address) = s.accept()


        self.assertEquals(s.recv(64), mocksock.incoming.pop(0))
        s.send(mocksock.outgoing.pop(0))

        buff = s.recv(64)
        inco = mocksock.incoming.pop(0)
        #self.assertEquals(s.recv(64), mocksock.incoming.pop(0))
        s.send(mocksock.outgoing.pop(0))

    def test_client_negoc(self):
        return
        self.sockobj._sock.setup_stream()
        try:
            self.sockobj.pollout()
        except SystemExit:
            pass

        self._check_inout()

    def test_server_negoc(self):
        return
        self.sockobj._sock.setup_stream()
        self.sockobj._sock.switch_stream()
        try:
            self.sockobj.idlequeue.plug_idle(self.sockobj, False, True)
        except SystemExit:
            pass
        self._check_inout()




if __name__ == '__main__':

    unittest.main()
