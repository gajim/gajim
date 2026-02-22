# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import io
import threading

from nbxmpp.util import utf8_decode
from PIL import Image

from gajim.common.multiprocess.http import http_request
from gajim.common.open_graph_parser import OpenGraphData
from gajim.common.open_graph_parser import OpenGraphParser
from gajim.common.open_graph_parser import OpenGraphThumbnail

THUMBNAIL_SIZE = 128


def generate_url_preview(
    url: str,
    event: threading.Event,
    proxy: str | None,
) -> OpenGraphData | None:
    result = http_request(
        event=event,
        ft_id="preview",
        method="GET",
        url=url,
        timeout=5,
        max_download_size=1024 * 150,
        proxy=proxy,
    )

    html_content, _ = utf8_decode(result.content)

    open_graph_parser = OpenGraphParser()
    og_data = open_graph_parser.parse(html_content)
    if og_data is None or not og_data.image:
        return og_data

    try:
        image_result = http_request(
            event=event,
            ft_id="preview",
            method="GET",
            url=og_data.image,
            timeout=5,
            proxy=proxy,
        )

        og_data.thumbnail = _make_thumbnail(image_result.content)
    except Exception:
        pass

    return og_data


def _make_thumbnail(content: bytes) -> OpenGraphThumbnail:
    image = Image.open(io.BytesIO(content))
    image.thumbnail((THUMBNAIL_SIZE, THUMBNAIL_SIZE))
    thumbnail = io.BytesIO()
    image.save(thumbnail, format="PNG", optimize=True)
    return OpenGraphThumbnail.from_bytes(thumbnail.getvalue())
