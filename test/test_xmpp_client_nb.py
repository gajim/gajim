'''
Testing script for NonBlockingClient class (src/common/xmpp/client_nb.py)

It actually connects to a xmpp server.
'''

import unittest

import lib
lib.setup_env()

from xmpp_mocks import MockConnection, IdleQueueThread
from mock import Mock
from common.xmpp import client_nb

#import logging
#log = logging.getLogger('gajim')
#log.setLevel(logging.DEBUG)

# (XMPP server hostname, c2s port). Script will connect to the machine.
xmpp_server_port = ('gajim.org', 5222)

# [username, password, passphrase]. Script will authenticate to server above
credentials = ['unittest', 'testtest', 'res']

class TestNonBlockingClient(unittest.TestCase):
	'''
	Test Cases class for NonBlockingClient. 
	'''
	def setUp(self):
		''' IdleQueue thread is run and dummy connection is created. '''
		self.idlequeue_thread = IdleQueueThread()
		self.connection = MockConnection() # for dummy callbacks
		self.idlequeue_thread.start()

	def tearDown(self):
		''' IdleQueue thread is stopped. '''
		self.idlequeue_thread.stop_thread()
		self.idlequeue_thread.join()

		self.client = None

	def open_stream(self, server_port, wrong_pass=False):
		'''
		Method opening the XMPP connection. It returns when <stream:features>
		is received from server.

		:param server_port: tuple of (hostname, port) for where the client should
		connect.
		'''

		class TempConnection():
			def get_password(self, cb):
				if wrong_pass:
					cb('wrong pass')
				else:
					cb(credentials[1])
			def on_connect_failure(self):
				pass

		self.client = client_nb.NonBlockingClient(
			domain=server_port[0],
			idlequeue=self.idlequeue_thread.iq,
			caller=Mock(realClass=TempConnection))

		self.client.connect(
			hostname=server_port[0],
			port=server_port[1],
			on_connect=lambda *args: self.connection.on_connect(True, *args),
			on_connect_failure=lambda *args: self.connection.on_connect(
				False, *args))

		self.assert_(self.connection.wait(),
			msg='waiting for callback from client constructor')
		
		# if on_connect was called, client has to be connected and vice versa
		if self.connection.connect_succeeded:
			self.assert_(self.client.get_connect_type())
		else:
			self.assert_(not self.client.get_connect_type())

	def client_auth(self, username, password, resource, sasl):
		'''
		Method authenticating connected client with supplied credentials. Returns
		when authentication is over.

		:param sasl: whether to use sasl (sasl=1) or old (sasl=0) authentication
		:todo: to check and be more specific about when it returns
			(bind, session..)
		'''
		self.client.auth(username, password, resource, sasl, 
				on_auth=self.connection.on_auth)

		self.assert_(self.connection.wait(), msg='waiting for authentication')

	def do_disconnect(self):
		'''
		Does disconnecting of connected client. Returns when TCP connection is 
		closed.
		'''
		self.client.RegisterDisconnectHandler(self.connection.set_event)
		self.client.disconnect()

		self.assertTrue(self.connection.wait(), msg='waiting for disconnecting')

	def test_proper_connect_sasl(self):
		'''
		The ideal testcase - client is connected, authenticated with SASL and 
		then disconnected.
		'''
		self.open_stream(xmpp_server_port)

		# if client is not connected, lets raise the AssertionError
		self.assert_(self.client.get_connect_type())
		# client.disconnect() is already called from NBClient via 
		# _on_connected_failure, no need to call it here

		self.client_auth(credentials[0], credentials[1], credentials[2], sasl=1)
		self.assert_(self.connection.con)
		self.assert_(self.connection.auth=='sasl', msg='Unable to auth via SASL')

		self.do_disconnect()

	def test_proper_connect_oldauth(self):
		'''
		The ideal testcase - client is connected, authenticated with old auth and 
		then disconnected.
		'''
		self.open_stream(xmpp_server_port)
		self.assert_(self.client.get_connect_type())
		self.client_auth(credentials[0], credentials[1], credentials[2], sasl=0)
		self.assert_(self.connection.con)
		features = self.client.Dispatcher.Stream.features
		if not features.getTag('auth'):
			print "Server doesn't support old authentication type, ignoring test"
		else:
			self.assert_(self.connection.auth=='old_auth',
				msg='Unable to auth via old_auth')
		self.do_disconnect()

	def test_connect_to_nonexisting_host(self):
		'''
		Connect to nonexisting host. DNS request for A records should return
		nothing.
		'''
		self.open_stream(('fdsfsdf.fdsf.fss', 5222))
		self.assert_(not self.client.get_connect_type())

	def test_connect_to_wrong_port(self):
		'''
		Connect to nonexisting server. DNS request for A records should return an
		IP	but there shouldn't be XMPP server running on specified port.
		'''
		self.open_stream((xmpp_server_port[0], 31337))
		self.assert_(not self.client.get_connect_type())

	def test_connect_with_wrong_creds(self):
		'''
		Connecting with invalid password.
		'''
		self.open_stream(xmpp_server_port, wrong_pass=True)
		self.assert_(self.client.get_connect_type())
		self.client_auth(credentials[0], 'wrong pass', credentials[2], sasl=1)
		self.assert_(self.connection.auth is None)
		self.do_disconnect()


if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
