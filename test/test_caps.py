'''
Tests for capabilities and the capabilities cache
'''
import unittest

import lib
lib.setup_env()

from common import gajim
from common import xmpp
from common import helpers

from common.caps import CapsCache

from mock import Mock

class MockLogger(Mock):
	def __init__(self, *args):
		Mock.__init__(self, *args)

class TestCapsCache(unittest.TestCase):
	def setUp(self):
		self.logger = MockLogger()
		self.cc = CapsCache(self.logger)

		self.caps_method = 'sha-1'
		self.caps_hash = 'zaQfb22o0UCwYDIk8KZOnoZTnrs='
		self.caps = (self.caps_method, self.caps_hash)
		self.identity = {'category': 'client', 'type': 'pc'}

		self.muc = 'http://jabber.org/protocol/muc'
		self.chatstates = 'http://jabber.org/protocol/chatstates'

		self.identities = [self.identity]
		self.features = [self.muc]

	def test_examples(self):
		'''tests the examples given in common/caps.py'''

		self.cc[self.caps].identities = self.identities
		self.cc[self.caps].features = self.features

		self.assert_(self.muc in self.cc[self.caps].features)
		self.assert_(self.chatstates not in self.cc[self.caps].features)

		id = self.cc[self.caps].identities

		self.assertEqual(1, len(id))

		id = id[0]
		self.assertEqual('client', id['category'])
		self.assertEqual('pc', id['type'])

	def test_hash(self):
		'''tests the hash computation'''
		computed_hash = helpers.compute_caps_hash(self.identities, self.features)

		self.assertEqual(self.caps_hash, computed_hash)

if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
