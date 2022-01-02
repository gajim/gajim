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

# XEP-0070: Verifying HTTP Requests via XMPP

import nbxmpp
from nbxmpp.structs import StanzaHandler
from nbxmpp.namespaces import Namespace

from gajim.common import app
from gajim.common.events import HttpAuthReceived
from gajim.common.modules.base import BaseModule


class HTTPAuth(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._http_auth,
                          ns=Namespace.HTTP_AUTH,
                          priority=45),
            StanzaHandler(name='iq',
                          callback=self._http_auth,
                          typ='get',
                          ns=Namespace.HTTP_AUTH,
                          priority=45)
        ]

    def _http_auth(self, _con, stanza, properties):
        if not properties.is_http_auth:
            return

        self._log.info('Auth request received')
        auto_answer = app.settings.get_account_setting(self._account,
                                                       'http_auth')
        if auto_answer in ('yes', 'no'):
            self.build_http_auth_answer(stanza, auto_answer)
            raise nbxmpp.NodeProcessed

        app.ged.raise_event(
            HttpAuthReceived(conn=self._con,
                             iq_id=properties.http_auth.id,
                             method=properties.http_auth.method,
                             url=properties.http_auth.url,
                             msg=properties.http_auth.body,
                             stanza=stanza))
        raise nbxmpp.NodeProcessed

    def build_http_auth_answer(self, stanza, answer):
        if answer == 'yes':
            self._log.info('Auth request approved')
            confirm = stanza.getTag('confirm')
            reply = stanza.buildReply('result')
            if stanza.getName() == 'message':
                reply.addChild(node=confirm)
            self._con.connection.send(reply)
        elif answer == 'no':
            self._log.info('Auth request denied')
            err = nbxmpp.Error(stanza, nbxmpp.protocol.ERR_NOT_AUTHORIZED)
            self._con.connection.send(err)
