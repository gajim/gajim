# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing
from typing import NotRequired
from typing import TypedDict

import base64
import dataclasses
from html.parser import HTMLParser

import nbxmpp.structs

if typing.TYPE_CHECKING:
    from gajim.common.storage.archive import models as mod


MAX_ATTRIBUTE_SIZE = 200
ALLOWED_OG_PROPERTIES = [
    "og:title",
    "og:description",
    "og:image",
]


@dataclasses.dataclass
class OpenGraphThumbnail:
    uri: str
    type: str
    data: bytes

    @classmethod
    def from_bytes(cls, data: bytes, media_type: str) -> OpenGraphThumbnail:
        base64_data = base64.b64encode(data).decode()
        uri = f"data:{media_type};base64,{base64_data}"
        return cls(uri=uri, type=media_type, data=data)


@dataclasses.dataclass
class OpenGraphData:
    title: str
    description: str | None = None
    image: str | None = None
    thumbnail: OpenGraphThumbnail | None = None

    @classmethod
    def from_model(cls, row: mod.OpenGraph) -> OpenGraphData:
        thumbnail = None
        if row.image_bytes is not None:
            assert row.image_type is not None
            thumbnail = OpenGraphThumbnail.from_bytes(row.image_bytes, row.image_type)

        return cls(
            title=row.title,
            description=row.description,
            thumbnail=thumbnail,
        )

    def to_nbxmpp(self) -> nbxmpp.structs.OpenGraphData:
        attributes = dataclasses.asdict(self)
        attributes.pop("thumbnail", None)
        if self.thumbnail:
            attributes["image"] = self.thumbnail.uri
        return nbxmpp.structs.OpenGraphData(**attributes)


class OpenGraphAttributes(TypedDict):
    title: NotRequired[str]
    description: NotRequired[str]
    image: NotRequired[str]


class OpenGraphParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()

        self._attributes: OpenGraphAttributes = {}
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
