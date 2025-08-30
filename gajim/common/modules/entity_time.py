# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0202: Entity Time

from __future__ import annotations

from gajim.common import types
from gajim.common.modules.base import BaseModule


class EntityTime(BaseModule):

    _nbxmpp_extends = 'EntityTime'
    _nbxmpp_methods = [
        'request_entity_time',
        'enable',
        'disable',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = []
