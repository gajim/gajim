'''
Unit test for NonBlockingTcp tranport.
'''

import unittest
from xmpp_mocks import *

import threading, sys, os.path, time

gajim_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')

sys.path.append(gajim_root + '/src/common/xmpp')
sys.path.append(gajim_root + '/src/common')

import transports_new, debug
from client import *

xmpp_server = ('xmpp.example.org',5222)
'''
2-tuple  - (XMPP server hostname, c2s port)
Script will connect to the machine.
'''

dns_timeout = 10
'''
timeout for DNS A-request (for getaddrinfo() call)
'''

class MockClient(IdleMock):
	def __init__(self, server, port):
		self.debug_flags=['all', 'nodebuilder']
		self._DEBUG = debug.Debug(['socket'])
		self.DEBUG = self._DEBUG.Show
		self.server = server
		self.port = port
		IdleMock.__init__(self)
		self.tcp_connected = False
		self.ip_addresses = []
		self.socket = None

	def do_dns_request(self):
		transports_new.NBgetaddrinfo(
			server=(self.server, self.port),
			on_success=lambda *args:self.on_success('DNSrequest', *args),
			on_failure=self.on_failure,
			timeout_sec=dns_timeout
			)
		self.wait()


	def try_next_ip(self, err_message=None):
		if err_message:
			print err_message
		if self.ip_addresses == []:
			self.on_failure('Run out of hosts')
			return
		current_ip = self.ip_addresses.pop(0)
		self.NonBlockingTcp.connect(
				conn_5tuple=current_ip,
				on_tcp_connect=lambda *args: self.on_success('TCPconnect',*args),
				on_tcp_failure=self.try_next_ip,
				idlequeue=self.idlequeue
				)
		self.wait()

		
	def set_idlequeue(self, idlequeue):
		self.idlequeue=idlequeue

	def on_failure(self, data):
		print 'Error: %s' % data
		self.set_event()

	def on_success(self, mode, data):
		if   mode == "DNSrequest":
			self.ip_addresses = data
		elif mode == "TCPconnect":
			pass
		self.set_event()



	




class TestNonBlockingTcp(unittest.TestCase):
	def setUp(self):
		self.nbtcp = transports_new.NonBlockingTcp()
		self.client = MockClient(*xmpp_server)
		self.idlequeue_thread = IdleQueueThread()
		self.idlequeue_thread.start()
		self.client.set_idlequeue(self.idlequeue_thread.iq)
		self.nbtcp.PlugIn(self.client)

	def tearDown(self):
		self.idlequeue_thread.stop_thread()
		self.idlequeue_thread.join()
		

	def testSth(self):
		self.client.do_dns_request()
		if self.client.ip_addresses == []:
			print 'No IP found for given hostname: %s' % self.client.server
			return
		else:
			self.client.try_next_ip()


		
		


if __name__ == '__main__':

	suite = unittest.TestLoader().loadTestsFromTestCase(TestNonBlockingTcp)
	unittest.TextTestRunner(verbosity=2).run(suite)

