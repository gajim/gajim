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

import logging

import nbxmpp

from gajim.common import app
from gajim.common import idle

log = logging.getLogger('gajim.c.m.last_activity')


class LastActivity:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [('iq', self._answer_request, 'get', nbxmpp.NS_LAST)]

    def _answer_request(self, _con, stanza):
        log.info('Request from %s', stanza.getFrom())
        if not app.account_is_connected(self._account):
            return

        allow_send = app.config.get_per(
            'accounts', self._account, 'send_idle_time')
        if app.is_installed('IDLE') and allow_send:
            iq = stanza.buildReply('result')
            query = iq.setQuery()
            query.attrs['seconds'] = idle.Monitor.get_idle_sec()
        else:
            iq = stanza.buildReply('error')
            err = nbxmpp.ErrorNode(nbxmpp.ERR_SERVICE_UNAVAILABLE)
            iq.addChild(node=err)

        self._con.connection.send(iq)

        raise nbxmpp.NodeProcessed


def get_instance(*args, **kwargs):
    return LastActivity(*args, **kwargs), 'LastActivity'
