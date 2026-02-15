# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import threading

from nbxmpp.structs import OpenGraphData
from nbxmpp.util import utf8_decode

from gajim.common.multiprocess.http import http_request
from gajim.common.open_graph_parser import OpenGraphParser


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
    return open_graph_parser.parse(html_content)
