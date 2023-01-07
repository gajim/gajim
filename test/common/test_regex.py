from typing import Any

import re
import unittest

from gajim.common import regex

TEST_URIS = [
    'scheme:',
    'http:///',
    'http://',
    'http://google.com/',
    'http://google.com',
    'http://www.google.ca/search?q=xmpp',
    'http://tools.ietf.org/html/draft-saintandre-rfc3920bis-05#section-12.3',
    'http://en.wikipedia.org/wiki/Protocol_(computing)',
    'http://en.wikipedia.org/wiki/Protocol_%28computing%29',
    'mailto:test@example.org',
    'xmpp:example-node@example.com',
    'xmpp:example-node@example.com/some-resource',
    'xmpp:example-node@example.com?message',
]

JIDS = [
    'example-node@example.com',
    'me@[::1]',
    'myself@127.13.42.69',
    # 'myself@127.13.42.69/localhost',  TODO
    '#room%irc.example@biboumi.xmpp.example',
    r'here\27s_a_wild_\26_\2fcr%zy\2f_address_for\3a\3cwv\3e(\22IMPS\22)@example.com',
    r'CN=D\27Artagnan\20Saint-Andr\E9,O=Example\20\26\20Company,\20Inc.,DC=example,DC=com@st.example.com',
    'δοκιμή@παράδειγμα.δοκιμή',
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
            assert_matches_all(re.compile(regex.IRI), uri)

        for addr in JIDS:
            assert_matches_all(re.compile(regex.XMPP.jid), addr)


if __name__ == '__main__':
    unittest.main()
