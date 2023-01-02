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

from __future__ import annotations

from typing import Union

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Iq
from nbxmpp.protocol import Message
from nbxmpp.structs import IqProperties
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import HttpAuth
from gajim.common.modules.base import BaseModule


class HTTPAuth(BaseModule):
    def __init__(self, con: types.Client) -> None:
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

    def _http_auth(self,
                   _con: types.xmppClient,
                   stanza: Union[Iq, Message],
                   properties: Union[IqProperties, MessageProperties]
                   ) -> None:
        if not properties.is_http_auth:
            return

        self._log.info('Auth request received')
        auto_answer = app.settings.get_account_setting(self._account,
                                                       'http_auth')
        if auto_answer in ('yes', 'no'):
            self.build_http_auth_answer(stanza, auto_answer)
            raise nbxmpp.NodeProcessed

        app.ged.raise_event(
            HttpAuth(client=self._con,
                     data=properties.http_auth,
                     stanza=stanza))
        raise nbxmpp.NodeProcessed

    def build_http_auth_answer(self,
                               stanza: Union[Iq, Message],
                               answer: str
                               ) -> None:
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
