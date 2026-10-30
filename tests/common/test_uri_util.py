# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

import unittest

from gajim.common.util.uri import Coords
from gajim.common.util.uri import DataUri
from gajim.common.util.uri import get_geo_choords
from gajim.common.util.uri import split_geo_uri
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

    def test_split_geo_uri(self) -> None:
        self.assertEqual(
            split_geo_uri("geo:37.786971,-122.399677,122.3;u=20"),
            Coords(
                location="37.786971,-122.399677", lat="37.786971", lon="-122.399677"
            ),
        )
        self.assertEqual(
            split_geo_uri("geo:-90,180"),
            Coords(location="-90,180", lat="-90", lon="180"),
        )

        invalid_uris = [
            "geo:nan,nan",
            "geo:NaN,0",
            "geo:0,-nan",
            "geo:inf,0",
            "geo:0,-infinity",
            "geo:1e1,0",
            "geo:1_0,0",
            "geo:+10,0",
            "geo:10.,0",
            "geo:91,0",
            "geo:0,-181",
            "geo:0",
        ]
        for uri in invalid_uris:
            with self.subTest(uri=uri):
                self.assertRaises(ValueError, split_geo_uri, uri)

    def test_get_geo_choords_invalid(self) -> None:
        self.assertIsNone(get_geo_choords("geo:nan,nan"))


if __name__ == "__main__":
    unittest.main()
