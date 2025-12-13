# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import json
import logging
from collections.abc import Callable

from nbxmpp.const import AnonymityMode
from nbxmpp.structs import MuclumbusItem
from nbxmpp.structs import MuclumbusResult

from gajim.common import app
from gajim.common import types
from gajim.common.file_transfer_manager import FileTransfer
from gajim.common.helpers import determine_proxy
from gajim.common.modules.base import BaseModule

log = logging.getLogger("gajim.c.m.http_muc_search")

EMPTY_RESULT = MuclumbusResult(first=None, last=None, max=None, end=True, items=[])


class HttpMucSearch(BaseModule):
    def __init__(self, client: types.Client) -> None:
        BaseModule.__init__(self, client)

    def search(
        self,
        keywords: list[str],
        last: str | None,
        callback: Callable[[MuclumbusResult], None],
    ) -> None:
        body: dict[str, str | list[str]] = {"keywords": keywords}
        if last is not None:
            body["after"] = last

        app.ftm.http_request(
            "GET",
            app.settings.get("muclumbus_api_http_uri"),
            content_type="application/json",
            input_=json.dumps(body).encode(),
            proxy=determine_proxy(self._account),
            timeout=3,
            user_data=callback,
            callback=self._on_search_result,
        )

    def _on_search_result(self, obj: FileTransfer) -> None:
        callback = obj.get_user_data()
        try:
            result = obj.get_result()
        except Exception as error:
            log.warning("Error while requesting muc search: %s", error)
            callback(EMPTY_RESULT)
            return

        log.info("Received search result: %s", len(result.content))

        try:
            res = self._parse_response(result.content)
        except Exception as error:
            log.error("Unable to parse response: %s", error)
            res = EMPTY_RESULT

        callback(res)

    def _parse_response(self, content: bytes) -> MuclumbusResult:
        response = json.loads(content)
        result = response["result"]
        items = result.get("items")
        if items is None:
            return EMPTY_RESULT

        results: list[MuclumbusItem] = []
        for item in items:
            try:
                anonymity_mode = AnonymityMode(item["anonymity_mode"])
            except (ValueError, KeyError):
                anonymity_mode = AnonymityMode.UNKNOWN

            results.append(
                MuclumbusItem(
                    jid=item["address"],
                    name=item["name"] or "",
                    nusers=str(item["nusers"] or ""),
                    description=item["description"] or "",
                    language=item["language"] or "",
                    is_open=item["is_open"],
                    anonymity_mode=anonymity_mode,
                )
            )

        return MuclumbusResult(
            first=None,
            last=result["last"],
            max=None,
            end=not result["more"],
            items=results,
        )
