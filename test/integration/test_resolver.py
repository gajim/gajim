import unittest

import time

import lib
lib.setup_env()

from common import resolver

from mock import Mock, expectParams
from gajim_mocks import *
from xmpp_mocks import IdleQueueThread

GMAIL_SRV_NAME = '_xmpp-client._tcp.gmail.com'
NONSENSE_NAME = 'sfsdfsdfsdf.sdfs.fsd'
JABBERCZ_TXT_NAME = '_xmppconnect.jabber.cz'
JABBERCZ_SRV_NAME = '_xmpp-client._tcp.jabber.cz'

TEST_LIST = [(GMAIL_SRV_NAME, 'srv', True), 
	(NONSENSE_NAME, 'srv', False),
	(JABBERCZ_SRV_NAME, 'srv', True)]

class TestResolver(unittest.TestCase):
	'''
	Test for LibAsyncNSResolver and NSLookupResolver. Requires working
	network connection.
	'''
	def setUp(self):
		self.idlequeue_thread = IdleQueueThread()
		self.idlequeue_thread.start()

		self.iq = self.idlequeue_thread.iq
		self._reset()
		self.resolver = None

	def tearDown(self):
		self.idlequeue_thread.stop_thread()
		self.idlequeue_thread.join()

	def _reset(self):
		self.flag = False
		self.expect_results = False
		self.nslookup = False
		self.resolver = None

	def testLibAsyncNSResolver(self):
		self._reset()
		if not resolver.USE_LIBASYNCNS:
			print 'testLibAsyncResolver: libasyncns-python not installed'
			return
		self.resolver = resolver.LibAsyncNSResolver()

		for name, type, expect_results in TEST_LIST:
			self.expect_results = expect_results
			self._runLANSR(name, type)
			self.flag = False

	def _runLANSR(self, name, type):
		self.resolver.resolve(
			host = name,
			type = type,
			on_ready = self._myonready)
		while not self.flag:
			time.sleep(1)
			self.resolver.process()

	def _myonready(self, name, result_set):
		if __name__ == '__main__':
			from pprint import pprint
			pprint('on_ready called ...')
			pprint('hostname: %s' % name)
			pprint('result set: %s' % result_set)
			pprint('res.resolved_hosts: %s' % self.resolver.resolved_hosts)
			pprint('')
		if self.expect_results:
			self.assert_(len(result_set) > 0)
		else:
			self.assert_(result_set == [])
		self.flag = True
		if self.nslookup:
			self._testNSLR()
		
	def testNSLookupResolver(self):
		self._reset()
		self.nslookup = True
		self.resolver = resolver.NSLookupResolver(self.iq)
		self.test_list = TEST_LIST
		self._testNSLR()

	def _testNSLR(self):
		if self.test_list == []: 
			return
		name, type, self.expect_results = self.test_list.pop()
		self.resolver.resolve(
			host = name,
			type = type,
			on_ready = self._myonready)

if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
