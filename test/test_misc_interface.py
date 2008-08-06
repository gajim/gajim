# tests for the miscellaneous functions scattered throughout src/gajim.py
import unittest

import testlib
testlib.setup_env()

from common import gajim
from common import xmpp

from common.caps import CapsCache

from mock import Mock

from gajim import Interface

gajim.logger = Mock()

Interface()

class TestMiscInterface(unittest.TestCase):

	def test_links_regexp_entire(self):
		def assert_matches_all(str):
			m = gajim.interface.basic_pattern_re.match(str)

			# the match should equal the string
			str_span = (0, len(str))
			self.assertEqual(m.span(), str_span)

		# these entire strings should be parsed as links
		assert_matches_all('http://google.com/')
		assert_matches_all('http://google.com')
		assert_matches_all('http://www.google.ca/search?q=xmpp')

		assert_matches_all('http://tools.ietf.org/html/draft-saintandre-rfc3920bis-05#section-12.3')

		assert_matches_all('http://en.wikipedia.org/wiki/Protocol_(computing)')
		assert_matches_all('http://en.wikipedia.org/wiki/Protocol_%28computing%29')

		assert_matches_all('mailto:test@example.org')

		assert_matches_all('xmpp:example-node@example.com')
		assert_matches_all('xmpp:example-node@example.com/some-resource')
		assert_matches_all('xmpp:example-node@example.com?message')
		assert_matches_all('xmpp://guest@example.com/support@example.com?message')

if __name__ == '__main__':
	unittest.main()

# vim: se ts=3:
