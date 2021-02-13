import unittest

from gajim import gui
gui.init('gtk')
import gajim.common.regex as regex

class Test(unittest.TestCase):
    def test_links_regexp_entire(self):
        def assert_matches_all(str_):
            m = regex.BASIC_REGEX.match(str_)

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
    unittest.main()
