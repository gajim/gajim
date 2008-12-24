'''
Unit test for NonBlockingTCP tranport.
'''

import unittest
from xmpp_mocks import IdleQueueThread, IdleMock
import sys, os.path

gajim_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')

sys.path.append(gajim_root + '/src/common/xmpp')
sys.path.append(gajim_root + '/src/common')

import transports_nb
from client import *

xmpp_server = ('gajim.org', 5222)
'''
2-tuple  - (XMPP server hostname, c2s port)
Script will connect to the machine.
'''

import socket
ips = socket.getaddrinfo(xmpp_server[0], xmpp_server[1],
	socket.AF_UNSPEC,socket.SOCK_STREAM) 

# change xmpp_server on real values
ip = ips[0]

class MockClient(IdleMock):

	def __init__(self, idlequeue):
		self.idlequeue = idlequeue
		IdleMock.__init__(self)

	def do_connect(self):
		self.socket = transports_nb.NonBlockingTCP(
			lambda(event_type, data): sys.stdout.write('raising event %s: %s' % (
			event_type, data)), lambda: self.on_success(mode='SocketDisconnect'),
			self.idlequeue, False, None)

		self.socket.PlugIn(self)

		self.socket.connect(conn_5tuple=ip,
			on_connect=lambda: self.on_success(mode='TCPconnect'),
			on_connect_failure=self.on_failure)
		self.wait()

	def do_disconnect(self):
		self.socket.disconnect()
		self.wait()

	def on_failure(self, data):
		print 'Error: %s' % data
		self.set_event()

	def on_success(self, mode, data=None):
		if mode == "TCPconnect":
			pass
		if mode == "SocketDisconnect":
			pass
		self.set_event()

class TestNonBlockingTCP(unittest.TestCase):
	def setUp(self):
		self.idlequeue_thread = IdleQueueThread()
		self.idlequeue_thread.start()
		self.client = MockClient(idlequeue=self.idlequeue_thread.iq)

	def tearDown(self):
		self.idlequeue_thread.stop_thread()
		self.idlequeue_thread.join()

	def test_connect_disconnect(self):
		self.client.do_connect()
		self.assert_(self.client.socket.state == 'CONNECTED')
		self.client.do_disconnect()
		self.assert_(self.client.socket.state == 'DISCONNECTED')


if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
