import unittest, threading
from mock import Mock

import sys, time, os.path

gajim_root = os.path.join(os.path.abspath(os.path.dirname(__file__)), '..')

sys.path.append(gajim_root + '/src/common/xmpp')

import client_nb, idlequeue

'''
Testing script for NonBlockingClient class (src/common/xmpp/client_nb.py)
It actually connects to a xmpp server so the connection values have to be
changed before running.
'''

idlequeue_interval = 0.2
'''
IdleQueue polling interval. 200ms is used in Gajim as default
'''

xmpp_server_port = ('xmpp.example.org',5222)
'''
2-tuple  - (XMPP server hostname, c2s port)
Script will connect to the machine.
'''

credentials = ['primus', 'l0v3', 'testclient']
'''
[username, password, passphrase]
Script will autheticate itself with this credentials on above mentioned server.
'''


class MockConnectionClass(Mock):
	'''
	Class simulating Connection class from src/common/connection.py

	It is derived from Mock in order to avoid defining all methods
	from real Connection that are called from NBClient or Dispatcher
	( _event_dispatcher for example)
	'''

	def __init__(self, *args):
		self.event = threading.Event()
		'''
		is used for waiting on connect, auth and disconnect callbacks
		'''

		self.event.clear()
		Mock.__init__(self, *args)

	def on_connect(self, *args):
		'''
		Method called on succesful connecting - after receiving <stream:features>
		from server (NOT after TLS stream restart).
		'''

		#print 'on_connect - args:'
		#for i in args:
		#	print '    %s' % i
		self.connect_failed = False
		self.event.set()

	def on_connect_failure(self, *args):
		'''
		Method called on failure while connecting - on everything from TCP error
		to error during TLS handshake
		'''

		#print 'on_connect failure - args:'
		#for i in args:
		#	print '    %s' % i
		self.connect_failed = True
		self.event.set()
	
	def on_auth(self, con, auth):
		'''
		Method called after authentication is done regardless on the result.

		:Parameters:
			con : NonBlockingClient
				reference to authenticated object
			auth : string
				type of authetication in case of success ('old_auth', 'sasl') or
				None in case of auth failure
		'''

		#print 'on_auth - args:'
		#print '    con: %s' % con
		#print '    auth: %s' % auth
		self.auth_connection = con
		self.auth = auth
		self.event.set()

	def wait(self):
		'''
		Waiting until some callback sets the event and clearing the event subsequently. 
		'''

		self.event.wait()
		self.event.clear()

	


class IdleQueueThread(threading.Thread):
	'''
	Thread for regular processing of idlequeue.
	'''
	def __init__(self):
		self.iq = idlequeue.IdleQueue()
		self.stop = threading.Event()
		'''
		Event used to stopping the thread main loop.
		'''

		self.stop.clear()
		threading.Thread.__init__(self)
	
	def run(self):
		while not self.stop.isSet():
			self.iq.process()
			time.sleep(idlequeue_interval)
		self.iq.process()

	def stop_thread(self):
		self.stop.set()


	

class TestNonBlockingClient(unittest.TestCase):
	'''
	Test Cases class for NonBlockingClient. 
	'''

	def setUp(self):
		'''
		IdleQueue thread is run and dummy connection is created.
		'''

		self.idlequeue_thread = IdleQueueThread()
		self.connection = MockConnectionClass()

		self.client = client_nb.NonBlockingClient(
				server=xmpp_server_port[0],
				port=xmpp_server_port[1],
				on_connect=self.connection.on_connect,
				on_connect_failure=self.connection.on_connect_failure,
				caller=self.connection 
				)
		'''
		NonBlockingClient instance with parameters from global variables and with
		callbacks from dummy connection.
		'''

		self.client.set_idlequeue(self.idlequeue_thread.iq)	
		self.idlequeue_thread.start()

	def tearDown(self):
		'''
		IdleQueue thread is stopped.
		'''
		self.idlequeue_thread.stop_thread()
		self.idlequeue_thread.join()

	def open_stream(self, server_port):
		'''
		Method opening the XMPP connection. It returns when <stream:features>
		is received from server.

		:param server_port: tuple of (hostname, port) for where the client should
		connect.
		'''
		self.client.connect(server_port)

		print 'waiting for callback from client constructor'
		self.connection.wait()
		
		# if on_connect was called, client has to be connected and vice versa
		if self.connection.connect_failed:
			self.assert_(not self.client.isConnected())
		else:
			self.assert_(self.client.isConnected())

	def client_auth(self, username, password, resource, sasl):
		'''
		Method authenticating connected client with supplied credentials. Returns
		when authentication is over.
		:param sasl: whether to use sasl (sasl=1) or old (sasl=0) authentication

		:todo: to check and be more specific about when it returns (bind, session..)
		'''
		self.client.auth(username, password, resource, sasl, 
				on_auth=self.connection.on_auth)

		print 'waiting for authentication...'
		self.connection.wait()

	def do_disconnect(self):
		'''
		Does disconnecting of connected client. Returns when TCP connection is closed.
		'''
		self.client.start_disconnect(None, on_disconnect=self.connection.event.set)

		print 'waiting for disconnecting...'
		self.connection.wait()

	def test_proper_connect_sasl(self):
		'''
		The ideal testcase - client is connected, authenticated with SASL and 
		then disconnected.
		'''
		self.open_stream(xmpp_server_port)

		# if client is not connected, lets raise the AssertionError
		self.assert_(self.client.isConnected())
		# (client.disconnect() is already called from NBClient._on_connected_failure
		# so there's need to call it in this case

		self.client_auth(credentials[0], credentials[1], credentials[2], sasl=1)
		self.assert_(self.connection.con)
		self.assert_(self.connection.auth=='sasl')

		self.do_disconnect()


	def test_proper_connect_oldauth(self):
		'''
		The ideal testcase - client is connected, authenticated with old auth and 
		then disconnected.
		'''
		self.open_stream(xmpp_server_port)
		self.assert_(self.client.isConnected())
		self.client_auth(credentials[0], credentials[1], credentials[2], sasl=0)
		self.assert_(self.connection.con)
		self.assert_(self.connection.auth=='old_auth')
		self.do_disconnect()

	def test_connect_to_nonexisting_host(self):
		'''
		Connect to nonexisting host. DNS request for A records should return nothing.
		'''
		self.open_stream(('fdsfsdf.fdsf.fss', 5222))
		self.assert_(not self.client.isConnected())

	def test_connect_to_wrong_port(self):
		'''
		Connect to nonexisting host. DNS request for A records should return some IP
		but there shouldn't be XMPP server running on specified port.
		'''
		self.open_stream((xmpp_server_port[0], 31337))
		self.assert_(not self.client.isConnected())

	def test_connect_with_wrong_creds(self):
		'''
		Connecting with invalid password.
		'''
		self.open_stream(xmpp_server_port)
		self.assert_(self.client.isConnected())
		self.client_auth(credentials[0], "wrong pass", credentials[2], sasl=0)
		self.assert_(self.connection.auth is None)
		self.do_disconnect()






if __name__ == '__main__':

	suite = unittest.TestLoader().loadTestsFromTestCase(TestNonBlockingClient)
	unittest.TextTestRunner(verbosity=2).run(suite)





