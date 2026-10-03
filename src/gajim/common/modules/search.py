# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0055: Jabber Search

from __future__ import annotations

from gajim.common import types
from gajim.common.modules.base import BaseModule


class Search(BaseModule):
    _nbxmpp_extends = "Search"
    _nbxmpp_methods = [
        "request_form",
        "send_form",
    ]

    def __init__(self, client: types.Client) -> None:
        BaseModule.__init__(self, client)
