'''
Unit test for tranports classes.
'''

import unittest
import socket

import lib
lib.setup_env()

from xmpp_mocks import IdleQueueThread, IdleMock
from common.xmpp import transports_nb


class TestModuleLevelFunctions(unittest.TestCase):
	'''
	Test class for functions defined at module level
	'''
	def test_urisplit(self):
		def check_uri(uri, proto, host, path):
			_proto, _host, _path = transports_nb.urisplit(uri)
			self.assertEqual(proto, _proto)
			self.assertEqual(host, _host)
			self.assertEqual(path, _path)
		check_uri('http://httpcm.jabber.org/webclient',
			proto='http', host='httpcm.jabber.org', path='/webclient')

	def test_get_proxy_data_from_dict(self):
		def check_dict(proxy_dict, host, port, user, passwd):
			_host, _port, _user, _passwd = transports_nb.get_proxy_data_from_dict(
				proxy_dict)
			self.assertEqual(_host, host)
			self.assertEqual(_port, port)
			self.assertEqual(_user, user)
			self.assertEqual(_passwd, passwd)

		bosh_dict = {'bosh_content': u'text/xml; charset=utf-8',
 						'bosh_hold': 2,
 						'bosh_http_pipelining': False,
 						'bosh_port': 5280,
 						'bosh_uri': u'http://gajim.org:5280/http-bind',
						'bosh_useproxy': False,
 						'bosh_wait': 30,
 						'bosh_wait_for_restart_response': False,
 						'host': u'172.16.99.11',
 						'pass': u'pass',
 						'port': 3128,
 						'type': u'bosh',
 						'useauth': True,
 						'user': u'user'}
		check_dict(bosh_dict, host=u'gajim.org', port=5280, user=u'user',
			passwd=u'pass')

		proxy_dict = {'bosh_content': u'text/xml; charset=utf-8',
 						'bosh_hold': 2,
						'bosh_http_pipelining': False,
						'bosh_port': 5280,
						'bosh_uri': u'',
						'bosh_useproxy': True,
						'bosh_wait': 30,
						'bosh_wait_for_restart_response': False,
						'host': u'172.16.99.11',
						'pass': u'pass',
						'port': 3128,
						'type': 'socks5',
						'useauth': True,
						'user': u'user'}
		check_dict(proxy_dict, host=u'172.16.99.11', port=3128, user=u'user',
			passwd=u'pass')


class AbstractTransportTest(unittest.TestCase):
	''' Encapsulates Idlequeue instantiation for transports and more...'''

	def setUp(self):
		''' IdleQueue thread is run and dummy connection is created. '''
		self.idlequeue_thread = IdleQueueThread()
		self.idlequeue_thread.start()
		self._setup_hook()

	def tearDown(self):
		''' IdleQueue thread is stopped. '''
		self._teardown_hook()
		self.idlequeue_thread.stop_thread()
		self.idlequeue_thread.join()

	def _setup_hook(self):
		pass

	def _teardown_hook(self):
		pass

	def expect_receive(self, expected, count=1, msg=None):
		'''
		Returns a callback function that will assert whether the data passed to 
		it equals the one specified when calling this function.

		Can be used to make sure transport dispatch correct data.
		'''
		def receive(data, *args, **kwargs):
			self.assertEqual(data, expected, msg=msg)
			self._expected_count -= 1
		self._expected_count = count
		return receive

	def have_received_expected(self):
		'''
		Plays together with expect_receive(). Will return true if expected_rcv
		callback was called as often as specified
		'''
		return self._expected_count == 0


class TestNonBlockingTCP(AbstractTransportTest):
	'''
	Test class for NonBlockingTCP. Will actually try to connect to an existing
	XMPP server.
	'''
	class MockClient(IdleMock):
		''' Simple client to test transport functionality '''
		def __init__(self, idlequeue, testcase):
			self.idlequeue = idlequeue
			self.testcase = testcase
			IdleMock.__init__(self)

		def do_connect(self, establish_tls=False, proxy_dict=None):
			try:
				ips = socket.getaddrinfo('gajim.org', 5222,
					socket.AF_UNSPEC,socket.SOCK_STREAM) 
				ip = ips[0]
			except socket.error, e:
				self.testcase.fail(msg=str(e))

			self.socket = transports_nb.NonBlockingTCP(
				raise_event=lambda event_type, data: self.testcase.assertTrue(
					event_type and data),
				on_disconnect=lambda: self.on_success(mode='SocketDisconnect'),
				idlequeue=self.idlequeue,
				estabilish_tls=establish_tls,
				certs=('../data/other/cacerts.pem', 'tmp/cacerts.pem'),
				proxy_dict=proxy_dict)

			self.socket.PlugIn(self)

			self.socket.connect(conn_5tuple=ip,
				on_connect=lambda: self.on_success(mode='TCPconnect'),
				on_connect_failure=self.on_failure)
			self.testcase.assertTrue(self.wait(), msg='Connection timed out')

		def do_disconnect(self):
			self.socket.disconnect()
			self.testcase.assertTrue(self.wait(), msg='Disconnect timed out')

		def on_failure(self, err_message):
			self.set_event()
			self.testcase.fail(msg=err_message)

		def on_success(self, mode, data=None):
			if mode == "TCPconnect":
				pass
			if mode == "SocketDisconnect":
				pass
			self.set_event()

	def _setup_hook(self):
		self.client = self.MockClient(idlequeue=self.idlequeue_thread.iq,
			testcase=self)
	
	def _teardown_hook(self):
		if self.client.socket.state == 'CONNECTED':
			self.client.do_disconnect()

	def test_connect_disconnect_plain(self):
		''' Establish plain connection '''
		self.client.do_connect(establish_tls=False)
		self.assert_(self.client.socket.state == 'CONNECTED')
		self.client.do_disconnect()
		self.assert_(self.client.socket.state == 'DISCONNECTED')
	
	# FIXME: testcase not working...
	#def test_connect_disconnect_ssl(self):
	#	''' Establish SSL (not TLS) connection '''
	#	self.client.do_connect(establish_tls=True)
	#	self.assert_(self.client.socket.state == 'CONNECTED')
	#	self.client.do_disconnect()
	#	self.assert_(self.client.socket.state == 'DISCONNECTED')

	def test_do_receive(self):
		''' Test _do_receive method by overwriting socket.recv '''
		self.client.do_connect()
		sock = self.client.socket

		# transport shall receive data
		data = "Please don't fail"
		sock._recv = lambda buffer: data
		sock.onreceive(self.expect_receive(data))
		sock._do_receive()
		self.assertTrue(self.have_received_expected(), msg='Did not receive data')
		self.assert_(self.client.socket.state == 'CONNECTED')

		# transport shall do nothing as an non-fatal SSL is simulated
		sock._recv = lambda buffer: None
		sock.onreceive(self.assertFalse) # we did not receive anything...
		sock._do_receive()
		self.assert_(self.client.socket.state == 'CONNECTED')

		# transport shall disconnect as remote side closed the connection 
		sock._recv = lambda buffer: ''
		sock.onreceive(self.assertFalse) # we did not receive anything...
		sock._do_receive()
		self.assert_(self.client.socket.state == 'DISCONNECTED')

	def test_do_send(self):
		''' Test _do_send method by overwriting socket.send '''
		self.client.do_connect()
		sock = self.client.socket

		outgoing = [] # what we have actually send to our socket.socket
		data_part1 = "Please don't "
		data_part2 = "fail!"
		data_complete = data_part1 + data_part2
	
		# Simulate everything could be send in one go
		def _send_all(data):
			outgoing.append(data)
			return len(data)
		sock._send = _send_all
		sock.send(data_part1)
		sock.send(data_part2)
		sock._do_send()
		sock._do_send()
		self.assertTrue(self.client.socket.state == 'CONNECTED')
		self.assertTrue(data_part1 in outgoing and data_part2 in outgoing)
		self.assertFalse(sock.sendqueue and sock.sendbuff,
			msg='There is still unsend data in buffers')

		# Simulate data could only be sent in chunks
		self.chunk_count = 0
		outgoing = []
		def _send_chunks(data):
			if self.chunk_count == 0:
				outgoing.append(data_part1)
				self.chunk_count += 1
				return len(data_part1)
			else:
				outgoing.append(data_part2)
				return len(data_part2)
		sock._send = _send_chunks
		sock.send(data_complete)
		sock._do_send() # process first chunk
		sock._do_send() # process the second one
		self.assertTrue(self.client.socket.state == 'CONNECTED')
		self.assertTrue(data_part1 in outgoing and data_part2 in outgoing)
		self.assertFalse(sock.sendqueue and sock.sendbuff,
			msg='There is still unsend data in buffers')


class TestNonBlockingHTTP(AbstractTransportTest):
	''' Test class for NonBlockingHTTP transport'''

	bosh_http_dict = {
		'http_uri': 'http://httpcm.jabber.org/webclient',			
		'http_port': 1010,
		'http_version': 'HTTP/1.1',
		'http_persistent': True,
		'add_proxy_headers': False
		}

	def _get_transport(self, http_dict, proxy_dict=None):
		return transports_nb.NonBlockingHTTP(
			raise_event=None,
			on_disconnect=None,
			idlequeue=self.idlequeue_thread.iq,
			estabilish_tls=False,
			certs=None,
			on_http_request_possible=lambda: None,
			on_persistent_fallback=None,
			http_dict=http_dict,
			proxy_dict=proxy_dict,
			)
	
	def test_parse_own_http_message(self):
		''' Build a HTTP message and try to parse it afterwards '''
		transport = self._get_transport(self.bosh_http_dict)

		data = "<test>Please don't fail!</test>"
		http_message = transport.build_http_message(data)
		statusline, headers, http_body = transport.parse_http_message(
			http_message)

		self.assertTrue(statusline and isinstance(statusline, list))
		self.assertTrue(headers and isinstance(headers, dict))
		self.assertEqual(data, http_body, msg='Input and output are different')

	def test_receive_http_message(self):
		''' Let _on_receive handle some http messages '''
		transport = self._get_transport(self.bosh_http_dict)
		
		header = ("HTTP/1.1 200 OK\r\nContent-Type: text/xml; charset=utf-8\r\n" +
			"Content-Length: 88\r\n\r\n")
		payload = "<test>Please don't fail!</test>"
		body = "<body xmlns='http://jabber.org/protocol/httpbind'>%s</body>" \
			% payload
		message = "%s%s" % (header, body)

		# try to receive in one go
		transport.onreceive(self.expect_receive(body, msg='Failed: In one go'))
		transport._on_receive(message)
		self.assertTrue(self.have_received_expected(), msg='Failed: In one go')

		# try to receive in chunks
		chunk1, chunk2, chunk3  = message[:20], message[20:73], message[73:]
		nextmessage_chunk = "\r\n\r\nHTTP/1.1 200 OK\r\nContent-Type: text/x"
		chunks = (chunk1, chunk2, chunk3, nextmessage_chunk)

		#TODO: BOSH implementatio ndoesn't support that for the moment
#		transport.onreceive(self.expect_receive(body, msg='Failed: In chunks'))
#		for chunk in chunks:
#			transport._on_receive(chunk)
#		self.assertTrue(self.have_received_expected(), msg='Failed: In chunks')

if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
