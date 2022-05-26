# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

# XEP-0202: Entity Time

from __future__ import annotations

from nbxmpp.protocol import JID

from gajim.common import app
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

    def set_enabled(self, enabled: bool) -> None:
        if not enabled:
            self._nbxmpp('EntityTime').disable()
            return

        if not app.settings.get_account_setting(self._account,
                                                'send_time_info'):
            return

        self._nbxmpp('EntityTime').enable()
        self._nbxmpp('EntityTime').set_allow_reply_func(self._allow_reply)

    def _allow_reply(self, jid: JID) -> bool:
        item = self._con.get_module('Roster').get_item(jid.bare)
        if item is None:
            return False

        contact = self._get_contact(jid.bare)
        return contact.is_subscribed
