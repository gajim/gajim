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

# XEP-0199: XMPP Ping

from typing import Any
from typing import Tuple

import time

import nbxmpp
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.types import ConnectionT
from gajim.common.types import ContactsT
from gajim.common.modules.base import BaseModule


class Ping(BaseModule):
    def __init__(self, con: ConnectionT) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._answer_request,
                          typ='get',
                          ns=nbxmpp.NS_PING),
        ]

    @staticmethod
    def _get_ping_iq(to: str) -> nbxmpp.Iq:
        iq = nbxmpp.Iq('get', to=to)
        iq.addChild(name='ping', namespace=nbxmpp.NS_PING)
        return iq

    def send_ping(self, contact: ContactsT) -> None:
        if not app.account_is_available(self._account):
            return

        to = contact.get_full_jid()
        iq = self._get_ping_iq(to)

        self._log.info('Send ping to %s', to)

        self._con.connection.SendAndCallForResponse(
            iq, self._pong_received, {'ping_time': time.time(),
                                      'contact': contact})

        app.nec.push_incoming_event(
            PingSentEvent(None, conn=self._con, contact=contact))

    def _pong_received(self,
                       _nbxmpp_client: Any,
                       stanza: nbxmpp.Iq,
                       ping_time: int,
                       contact: ContactsT) -> None:
        if not nbxmpp.isResultNode(stanza):
            self._log.info('Error: %s', stanza.getError())
            app.nec.push_incoming_event(
                PingErrorEvent(None, conn=self._con, contact=contact))
            return
        diff = round(time.time() - ping_time, 2)
        self._log.info('Received pong from %s after %s seconds',
                       stanza.getFrom(), diff)
        app.nec.push_incoming_event(
            PingReplyEvent(None, conn=self._con,
                           contact=contact,
                           seconds=diff))

    def _answer_request(self,
                        _con: ConnectionT,
                        stanza: nbxmpp.Iq,
                        _properties: Any) -> None:
        iq = stanza.buildReply('result')
        ping = iq.getTag('ping')
        if ping is not None:
            iq.delChild(ping)
        self._con.connection.send(iq)
        self._log.info('Send pong to %s', stanza.getFrom())
        raise nbxmpp.NodeProcessed


class PingSentEvent(NetworkIncomingEvent):
    name = 'ping-sent'


class PingReplyEvent(NetworkIncomingEvent):
    name = 'ping-reply'


class PingErrorEvent(NetworkIncomingEvent):
    name = 'ping-error'


def get_instance(*args: Any, **kwargs: Any) -> Tuple[Ping, str]:
    return Ping(*args, **kwargs), 'Ping'
