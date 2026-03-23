# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0202: Entity Time

from __future__ import annotations

from typing import cast

from nbxmpp.protocol import JID

from gajim.common import types
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import BareContact


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

    def set_enabled(self, enabled: bool) -> None:
        if not enabled:
            self._nbxmpp('EntityTime').disable()
            return

        self._nbxmpp('EntityTime').enable()
        self._nbxmpp('EntityTime').set_allow_reply_func(self._allow_reply)

    def _allow_reply(self, jid: JID) -> bool:
        bare_jid = jid.new_as_bare()
        item = self._con.get_module('Roster').get_item(bare_jid)
        if item is None:
            return False

        if not self._client.get_module("VCard4").is_timezone_published():
            self._log.info(
                "Ignore entity time request, because timezone is not published"
            )
            return False

        contact = cast(BareContact, self._get_contact(bare_jid))
        return contact.is_subscribed
