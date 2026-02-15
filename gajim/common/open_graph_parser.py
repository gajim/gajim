# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from html.parser import HTMLParser

from nbxmpp.structs import OpenGraphData

MAX_ATTRIBUTE_SIZE = 200
ALLOWED_OG_PROPERTIES = [
    "og:title",
    "og:description",
    "og:url",
    "og:image",
    "og:type",
    "og:site_name",
]


class OpenGraphParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()

        self._attributes: dict[str, str] = {}
        self._fallback_title: str = ""
        self._fallback_description: str = ""
        self._current_data = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "meta":
            return

        match dict(attrs):
            case {"property": prop, "content": content} if (
                prop in ALLOWED_OG_PROPERTIES and content
            ):
                self._attributes[prop.removeprefix("og:")] = content[
                    :MAX_ATTRIBUTE_SIZE
                ]

            case {"name": "description", "content": content} if content:
                self._fallback_description = content[:MAX_ATTRIBUTE_SIZE]

            case _:
                pass

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._fallback_title = self._current_data

        elif tag == "head":
            raise EOF

    def handle_data(self, data: str) -> None:
        self._current_data = data[:MAX_ATTRIBUTE_SIZE]

    def parse(self, text: str) -> OpenGraphData | None:
        try:
            self.feed(text)
        except EOF:
            pass

        if "title" not in self._attributes and self._fallback_title:
            self._attributes["title"] = self._fallback_title

        if "description" not in self._attributes and self._fallback_description:
            self._attributes["description"] = self._fallback_description

        if not self._attributes:
            return None

        return OpenGraphData(**self._attributes)


class EOF(Exception):
    pass
