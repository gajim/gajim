# tests for capabilities and the capabilities cache
import unittest

import lib
lib.setup_env()

from common import gajim
from common import xmpp

from common.caps import CapsCache

from mock import Mock

class MockLogger(Mock):
	def __init__(self, *args):
		Mock.__init__(self, *args)

class TestCapsCache(unittest.TestCase):
	def setUp(self):
		self.logger = MockLogger()
		self.cc = CapsCache(self.logger)

	def test_examples(self):
		'''tests the examples given in common/caps.py'''

		caps = ('sha-1', '66/0NaeaBKkwk85efJTGmU47vXI=')
		identity = {'category': 'client', 'type': 'pc'}

		muc = 'http://jabber.org/protocol/muc'
		chatstates = 'http://jabber.org/protocol/chatstates'

		self.cc[caps].identities = [identity]
		self.cc[caps].features = [muc]

		self.assert_(muc in self.cc[caps].features)
		self.assert_(chatstates not in self.cc[caps].features)

		id = self.cc[caps].identities

		self.assertEqual(1, len(id))

		id = id[0]
		self.assertEqual('client', id['category'])
		self.assertEqual('pc', id['type'])

if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
