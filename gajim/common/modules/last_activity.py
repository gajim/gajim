# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0012: Last Activity

from __future__ import annotations

from typing import cast

from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import idle
from gajim.common import types
from gajim.common.modules.base import BaseModule


class LastActivity(BaseModule):

    _nbxmpp_extends = 'LastActivity'
    _nbxmpp_methods = [
        'request_last_activity',
        'set_idle_func',
        'disable',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

    def set_enabled(self, enabled: bool) -> None:
        if not enabled or not app.is_installed('IDLE'):
            self._nbxmpp('LastActivity').disable()
            return

        if not app.settings.get_account_setting(self._account,
                                                'send_idle_time'):
            return

        self._nbxmpp('LastActivity').set_idle_func(idle.Monitor.get_idle_sec)
        self._nbxmpp('LastActivity').set_allow_reply_func(self._allow_reply)

    def _allow_reply(self, jid: JID) -> bool:
        bare_jid = jid.new_as_bare()
        item = self._con.get_module('Roster').get_item(bare_jid)
        if item is None:
            return False

        contact = cast(types.BareContact, self._get_contact(bare_jid))
        return contact.is_subscribed
