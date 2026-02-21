# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unittest

from gajim.common.open_graph_parser import OpenGraphData
from gajim.common.open_graph_parser import OpenGraphParser

EXAMPLE_1 = """
<!DOCTYPE html>
<html lang="en" dir="ltr">
<head>
  <meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Gajim</title>
<meta property="og:title" content="Gajim" />
<meta property="og:description" content="Free and fully featured chat app for XMPP" />
<meta property="og:type" content="website" />
<meta property="og:url" content="https://gajim.org/" />
<meta property="og:image" content="https://gajim.org/img/og-image.png" />

  <link rel="alternate" type="application/rss+xml" href="https://gajim.org/index.xml" title="Gajim">


<link rel="me" href="https://fosstodon.org/@gajim">

<link rel="icon" type="image/png" href="/favicon-96x96.png" sizes="96x96" />
<link rel="icon" type="image/svg+xml" href="/favicon.svg" />
<link rel="shortcut icon" href="/favicon.ico" />
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png" />
<meta name="apple-mobile-web-app-title" content="Gajim" />
<link rel="manifest" href="/site.webmanifest" />
<link rel="stylesheet" href="/font/inter/inter.css">
<link rel="stylesheet" href="/css/main.min.50abd93d84368b4faefaa11c38fabb177e442adde5a79989b65d96d7871bb4e9.css" integrity="sha256-UKvZPYQ2i0&#43;u&#43;qEcOPq7F35EKt3lp5mJtl2W14cbtOk=" crossorigin="anonymous">
<script src="/js/main.53216da438f76f46153f227656c218046669a230e3c456a5ec9fc06aaba51cf3.js" integrity="sha256-UyFtpDj3b0YVPyJ2VsIYBGZpojDjxFal7J/AaqulHPM=" crossorigin="anonymous"></script>
</head>
"""  # noqa: E501

EXAMPLE_2 = """
<title>title</title>
<meta name="description" content="description" />
<meta property="og:title" content="og title" />
<meta property="og:description" content="og description" />
"""

EXAMPLE_3 = """
<title>title</title>
<meta name="description" content="description" />
"""


class OpenGraphParserTest(unittest.TestCase):
    """Tests parsing HTML for Open Graph meta data."""

    def test_parsing(self) -> None:
        parser = OpenGraphParser()
        result = parser.parse(EXAMPLE_1)

        expected_result = OpenGraphData(
            title="Gajim",
            description="Free and fully featured chat app for XMPP",
            image="https://gajim.org/img/og-image.png",
        )

        self.assertEqual(result, expected_result)

        parser = OpenGraphParser()
        result = parser.parse(EXAMPLE_2)

        expected_result = OpenGraphData(
            title="og title",
            description="og description",
        )

        self.assertEqual(result, expected_result)

        parser = OpenGraphParser()
        result = parser.parse(EXAMPLE_3)

        expected_result = OpenGraphData(
            title="title",
            description="description",
        )

        self.assertEqual(result, expected_result)


if __name__ == "__main__":
    unittest.main()
