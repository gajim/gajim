import unittest

import nbxmpp

from gajim.common.modules.misc import parse_delay

class TestHelpers(unittest.TestCase):

    def test_parse_delay(self):

        node = """
        <message>
            <delay xmlns='urn:xmpp:delay' from='capulet.com' stamp='2002-09-10T23:08:25Z' />
            <delay xmlns='urn:xmpp:delay' from='romeo.com' stamp='2010-09-10T23:08:25Z' />
            <delay xmlns='urn:xmpp:delay' stamp='2015-09-10T23:08:25Z' />
        </message>
        """
        message = nbxmpp.Node(node=node)

        timestamp = parse_delay(message)
        self.assertEqual(timestamp, 1031699305.0)

        timestamp = parse_delay(message, from_='capulet.com')
        self.assertEqual(timestamp, 1031699305.0)

        timestamp = parse_delay(message, from_='romeo.com')
        self.assertEqual(timestamp, 1284160105.0)

        timestamp = parse_delay(message, not_from=['romeo.com'])
        self.assertEqual(timestamp, 1031699305.0)