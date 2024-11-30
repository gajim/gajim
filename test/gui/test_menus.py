# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from gajim.common.const import URIType
from gajim.common.const import XmppUriQuery

from gajim.gtk.menus import _uri_context_menus
from gajim.gtk.menus import _xmpp_uri_context_menus


class Test(unittest.TestCase):
    def test_uri_menus_dict(self):
        for t in URIType:
            if t == URIType.INVALID:
                continue  # doesn't need to be present
            self.assertIn(t, _uri_context_menus)

    def test_xmpp_uri_menus_dict(self):
        for t in XmppUriQuery:
            self.assertIn(t, _xmpp_uri_context_menus)


if __name__ == "__main__":
    unittest.main()
