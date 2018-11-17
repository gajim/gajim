'''
Some diverse tests covering functionality in the GUI Interface class.
'''
import unittest

from test import lib
lib.setup_env()

from gajim.common import logging_helpers
logging_helpers.set_quiet()

from gajim.common import app

from gajim.gui_interface import Interface

from gi.repository import GLib

class TestInterface(unittest.TestCase):

    def test_instantiation(self):
        ''' Test that we can proper initialize and do not fail on globals '''
        def close_app():
            app.app.quit()
        GLib.idle_add(close_app)
        app.app.run()

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
    unittest.main()
