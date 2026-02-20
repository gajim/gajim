# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import base64
import io
import threading

from nbxmpp.structs import OpenGraphData
from nbxmpp.util import utf8_decode
from PIL import Image

from gajim.common.multiprocess.http import http_request
from gajim.common.open_graph_parser import OpenGraphParser

MAX_THUMBNAIL_SIZE = 256


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
    open_graph_data = open_graph_parser.parse(html_content)
    if open_graph_data and open_graph_data.image:
        image_url = open_graph_data.image

        image_result = http_request(
            event=event,
            ft_id="preview",
            method="GET",
            url=image_url,
            timeout=5,
            max_download_size=1024 * 150,
            proxy=proxy,
        )
        try:
            image = Image.open(io.BytesIO(image_result.content))
            image.thumbnail((MAX_THUMBNAIL_SIZE, MAX_THUMBNAIL_SIZE))
            image_buffer = io.BytesIO()
            image.save(image_buffer, format="PNG")
            base64_data = base64.b64encode(image_buffer.getvalue()).decode("ascii")
            open_graph_data.image = f"data:image/png;base64,{base64_data}"
        except Exception:
            pass

    return open_graph_data
