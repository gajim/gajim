'''
Some diverse tests covering functionality in the GUI Interface class.
'''
import unittest

import lib
lib.setup_env()

from common import logging_helpers
logging_helpers.set_quiet()

from common import gajim 

from gajim_mocks import MockLogger
gajim.logger = MockLogger()

from gui_interface import Interface

class TestInterface(unittest.TestCase):

	def test_instantiation(self):
		''' Test that we can proper initialize and do not fail on globals '''
		interface = Interface()
		interface.run()
						
	def test_dispatch(self):
		''' Test dispatcher forwarding network events to handler_* methods '''
		sut = Interface()
		
		success = sut.dispatch('No Such Event', None, None)
		self.assertFalse(success, msg="Unexisting event handled")
			
		success = sut.dispatch('STANZA_ARRIVED', None, None)
		self.assertTrue(success, msg="Existing event must be handled")
			
	def test_register_unregister_single_handler(self):
		''' Register / Unregister a custom event handler '''
		sut = Interface()
		event = 'TESTS_ARE_COOL_EVENT'
			
		self.called = False
		def handler(account, data):
			self.assertEqual(account, 'account')
			self.assertEqual(data, 'data')
			self.called = True
			
		self.assertFalse(self.called)
		sut.register_handler('TESTS_ARE_COOL_EVENT', handler)
		sut.dispatch(event, 'account', 'data')
		self.assertTrue(self.called, msg="Handler should have been called")

		self.called = False
		sut.unregister_handler('TESTS_ARE_COOL_EVENT', handler)
		sut.dispatch(event, 'account', 'data')
		self.assertFalse(self.called, msg="Handler should no longer be called")
			
		
	def test_dispatch_to_multiple_handlers(self):
		''' Register and dispatch a single event to multiple handlers '''
		sut = Interface()
		event = 'SINGLE_EVENT'
			
		self.called_a = False
		self.called_b = False
			
		def handler_a(account, data):
			self.assertFalse(self.called_a, msg="One must only be notified once")
			self.called_a = True
			
		def handler_b(account, data):
			self.assertFalse(self.called_b, msg="One must only be notified once")
			self.called_b = True
			
		sut.register_handler(event, handler_a)
		sut.register_handler(event, handler_b)
		
		# register again
		sut.register_handler('SOME_OTHER_EVENT', handler_b)
		sut.register_handler(event, handler_a)
			
		sut.dispatch(event, 'account', 'data')
		self.assertTrue(self.called_a and self.called_b,
			msg="Both handlers should have been called")

	def test_links_regexp_entire(self):
		sut = Interface()
		def assert_matches_all(str_):
			m = sut.basic_pattern_re.match(str_)

			# the match should equal the string
			str_span = (0, len(str_))
			self.assertEqual(m.span(), str_span)

		# these entire strings should be parsed as links
		assert_matches_all('http://google.com/')
		assert_matches_all('http://google.com')
		assert_matches_all('http://www.google.ca/search?q=xmpp')

		assert_matches_all('http://tools.ietf.org/html/draft-saintandre-rfc3920bis-05#section-12.3')

		assert_matches_all('http://en.wikipedia.org/wiki/Protocol_(computing)')
		assert_matches_all(
			'http://en.wikipedia.org/wiki/Protocol_%28computing%29')

		assert_matches_all('mailto:test@example.org')

		assert_matches_all('xmpp:example-node@example.com')
		assert_matches_all('xmpp:example-node@example.com/some-resource')
		assert_matches_all('xmpp:example-node@example.com?message')
		assert_matches_all('xmpp://guest@example.com/support@example.com?message')


if __name__ == "__main__":
		#import sys;sys.argv = ['', 'Test.test']
		unittest.main()