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

# XEP-0012: Last Activity

from gajim.common import app
from gajim.common import idle
from gajim.common.modules.base import BaseModule


class LastActivity(BaseModule):

    _nbxmpp_extends = 'LastActivity'
    _nbxmpp_methods = [
        'request_last_activity',
        'set_idle_func',
        'disable',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

    def set_enabled(self, enabled):
        if not enabled or not app.is_installed('IDLE'):
            self._nbxmpp('LastActivity').disable()
            return

        if not app.settings.get_account_setting(self._account,
                                                'send_idle_time'):
            return

        self._nbxmpp('LastActivity').set_idle_func(idle.Monitor.get_idle_sec)
        self._nbxmpp('LastActivity').set_allow_reply_func(self._allow_reply)

    def _allow_reply(self, jid):
        item = self._con.get_module('Roster').get_item(jid.bare)
        if item is None:
            return False

        contact = self._get_contact(jid.bare)
        return contact.is_subscribed


def get_instance(*args, **kwargs):
    return LastActivity(*args, **kwargs), 'LastActivity'
