# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from gajim.common.util.uri import DataUri
from gajim.common.util.uri import XmppIri


class TestUriUtil(unittest.TestCase):
    def test_parsing_xmpp_iri(self) -> None:
        xiri = XmppIri.from_string(
            r"xmpp:nasty!%23$%25()*+,-.;=%3F%5B%5C%5D%5E_%60%7B%7C%7D~n@example.com"
        )
        self.assertEqual(str(xiri.jid), r"nasty!#$%()*+,-.;=?[\]^_`{|}~n@example.com")

        xiri = XmppIri.from_string(
            "xmpp:example-node@example.com?message;subject=Hello%20World"
        )
        self.assertEqual(str(xiri.jid), "example-node@example.com")
        self.assertEqual(xiri.action, "message")
        self.assertEqual(xiri.params, {"subject": "Hello World"})

        xiri = XmppIri.from_string(r"xmpp:aD%C3%BCrst@asd.at")
        self.assertEqual(str(xiri.jid), "adürst@asd.at")

    def test_parse_data_uri(self) -> None:
        test_uris = {
            "data:,A%20brief%20note": DataUri(
                scheme="data",
                uri="data:,A%20brief%20note",
                media_type="text/plain",
                parameters={},
                is_base64=False,
                data="A%20brief%20note",
            ),
            "data:image/gif;base64,R0lGODdhMAAwAPAAAAAAAP///ywA": DataUri(
                scheme="data",
                uri="data:image/gif;base64,R0lGODdhMAAwAPAAAAAAAP///ywA",
                media_type="image/gif",
                parameters={},
                is_base64=True,
                data="R0lGODdhMAAwAPAAAAAAAP///ywA",
            ),
            "data:text/plain;charset=iso-8859-7,%be%fg%be": DataUri(
                scheme="data",
                uri="data:text/plain;charset=iso-8859-7,%be%fg%be",
                media_type="text/plain",
                parameters={"charset": "iso-8859-7"},
                is_base64=False,
                data="%be%fg%be",
            ),
        }

        for uri, expected_res in test_uris.items():
            self.assertEqual(DataUri.from_string(uri), expected_res)


if __name__ == "__main__":
    unittest.main()
