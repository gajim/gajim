import unittest

import time

import lib
lib.setup_env()

from common import resolver
from common.xmpp.idlequeue import GlibIdleQueue

from mock import Mock, expectParams
from mocks import *

import gtk

GMAIL_SRV_NAME = '_xmpp-client._tcp.gmail.com'
NONSENSE_NAME = 'sfsdfsdfsdf.sdfs.fsd'
JABBERCZ_TXT_NAME = '_xmppconnect.jabber.cz'
JABBERCZ_SRV_NAME = '_xmpp-client._tcp.jabber.cz'

TEST_LIST = [(GMAIL_SRV_NAME, 'srv', True), 
	(NONSENSE_NAME, 'srv', False),
	(JABBERCZ_SRV_NAME, 'srv', True)]

class TestResolver(unittest.TestCase):
	''' Test for LibAsyncNSResolver and NSLookupResolver '''

	def setUp(self):
		self.iq = GlibIdleQueue()
		self.reset()
		self.resolver = None

	def reset(self):
		self.flag = False
		self.expect_results = False
		self.nslookup = False
		self.resolver = None

	def testLibAsyncNSResolver(self):
		self.reset()
		if not resolver.USE_LIBASYNCNS:
			print 'testLibAsyncResolver: libasyncns-python not installed'
			return
		self.resolver = resolver.LibAsyncNSResolver()

		for name, type, expect_results in TEST_LIST:
			self.expect_results = expect_results
			self.runLANSR(name, type)
			self.flag = False

	def runLANSR(self, name, type):
		self.resolver.resolve(
			host = name,
			type = type,
			on_ready = self.myonready)
		while not self.flag:
			time.sleep(1)
			self.resolver.process()

	def myonready(self, name, result_set):
		if __name__ == '__main__':
			print 'on_ready called ...'
			print 'hostname: %s' % name
			print 'result set: %s' % result_set
			print 'res.resolved_hosts: %s' % self.resolver.resolved_hosts
		if self.expect_results:
			self.assert_(len(result_set) > 0)
		else:
			self.assert_(result_set == [])
		self.flag = True
		if self.nslookup: self._testNSLR()
		
	def testNSLookupResolver(self):
		self.reset()
		self.nslookup = True
		self.resolver = resolver.NSLookupResolver(self.iq)
		self.test_list = TEST_LIST
		self._testNSLR()
		try:
			gtk.main()
		except KeyboardInterrupt:
			print 'KeyboardInterrupt caught'

	def _testNSLR(self):
		if self.test_list == []: 
			gtk.main_quit()
			return
		name, type, self.expect_results = self.test_list.pop()
		self.resolver.resolve(
			host = name,
			type = type,
			on_ready = self.myonready)

if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
