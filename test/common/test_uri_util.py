# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from gajim.common.util.uri import XmppIri


class TestUriUtil(unittest.TestCase):

    def test_parsing_xmpp_iri(self) -> None:
        xiri = XmppIri.from_string(
            r'xmpp:nasty!%23$%25()*+,-.;=%3F%5B%5C%5D%5E_%60%7B%7C%7D~n@example.com')
        self.assertEqual(str(xiri.jid), r'nasty!#$%()*+,-.;=?[\]^_`{|}~n@example.com')

        xiri = XmppIri.from_string(
            'xmpp:example-node@example.com?message;subject=Hello%20World')
        self.assertEqual(str(xiri.jid), 'example-node@example.com')
        self.assertEqual(xiri.action, 'message')
        self.assertEqual(xiri.params, {'subject': 'Hello World'})

        xiri = XmppIri.from_string(r'xmpp:aD%C3%BCrst@asd.at')
        self.assertEqual(str(xiri.jid), 'adürst@asd.at')


if __name__ == '__main__':
    unittest.main()
