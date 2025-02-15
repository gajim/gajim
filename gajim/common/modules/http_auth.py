# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0070: Verifying HTTP Requests via XMPP

from __future__ import annotations

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
                   stanza: Iq | Message,
                   properties: IqProperties | MessageProperties
                   ) -> None:
        if properties.http_auth is None:
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
                               stanza: Iq | Message,
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
