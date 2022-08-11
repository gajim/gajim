from typing import Any

import unittest

from gajim.common.styling import URI_RX
from gajim.common.styling import ADDRESS_RX


TEST_URIS = [
    'http://google.com/',
    'http://google.com',
    'http://www.google.ca/search?q=xmpp',
    'http://tools.ietf.org/html/draft-saintandre-rfc3920bis-05#section-12.3',
    'http://en.wikipedia.org/wiki/Protocol_(computing)',
    'http://en.wikipedia.org/wiki/Protocol_%28computing%29',
]

ADDRESSES = [
    'mailto:test@example.org',
    'xmpp:example-node@example.com',
    # 'xmpp:example-node@example.com/some-resource', FIXME
    'xmpp:example-node@example.com?message',
]


class Test(unittest.TestCase):
    def test_links_regexp_entire(self):
        def assert_matches_all(regex: Any, uri_str: str) -> None:
            m = regex.match(uri_str)
            if m is None:
                raise AssertionError('Failed: %s' % uri_str)

            str_span = (0, len(uri_str))
            self.assertEqual(m.span(), str_span, uri_str)

        for uri in TEST_URIS:
            assert_matches_all(URI_RX, uri)

        for addr in ADDRESSES:
            assert_matches_all(ADDRESS_RX, addr)


if __name__ == '__main__':
    unittest.main()
