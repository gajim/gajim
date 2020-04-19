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

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import idle
from gajim.common.modules.base import BaseModule


class LastActivity(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          typ='get',
                          callback=self._answer_request,
                          ns=Namespace.LAST),
        ]

    def _answer_request(self, _con, stanza, properties):
        self._log.info('Request from %s', properties.jid)

        allow_send = app.config.get_per(
            'accounts', self._account, 'send_idle_time')
        if app.is_installed('IDLE') and allow_send:
            iq = stanza.buildReply('result')
            query = iq.setQuery()
            seconds = idle.Monitor.get_idle_sec()
            query.attrs['seconds'] = seconds
            self._log.info('Respond with seconds: %s', seconds)
        else:
            iq = stanza.buildReply('error')
            err = nbxmpp.ErrorNode(nbxmpp.ERR_SERVICE_UNAVAILABLE)
            iq.addChild(node=err)

        self._con.connection.send(iq)

        raise nbxmpp.NodeProcessed


def get_instance(*args, **kwargs):
    return LastActivity(*args, **kwargs), 'LastActivity'
