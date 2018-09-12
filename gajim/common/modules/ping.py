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

import logging
import time

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkIncomingEvent

log = logging.getLogger('gajim.c.m.ping')


class Ping:
    def __init__(self, con):
        self._con = con
        self._account = con.name
        self._alarm_time = None

        self.handlers = [
            ('iq', self._answer_request, 'get', nbxmpp.NS_PING),
        ]

    @staticmethod
    def _get_ping_iq(to: str) -> nbxmpp.Iq:
        iq = nbxmpp.Iq('get', to=to)
        iq.addChild(name='ping', namespace=nbxmpp.NS_PING)
        return iq

    def send_keepalive_ping(self) -> None:
        if not app.account_is_connected(self._account):
            return

        to = app.config.get_per('accounts', self._account, 'hostname')
        self._con.connection.SendAndCallForResponse(self._get_ping_iq(to),
                                                    self._keepalive_received)

        log.info('Send keepalive')

        seconds = app.config.get_per('accounts', self._account,
                                     'time_for_ping_alive_answer')
        self._alarm_time = app.idlequeue.set_alarm(self._reconnect, seconds)

    def _keepalive_received(self, _stanza: nbxmpp.Iq) -> None:
        log.info('Received keepalive')
        app.idlequeue.remove_alarm(self._reconnect, self._alarm_time)

    def _reconnect(self) -> None:
        if not app.config.get_per('accounts', self._account, 'active'):
            # Account may have been disabled
            return

        # We haven't got the pong in time, disco and reconnect
        log.warning('No reply received for keepalive ping. Reconnecting...')
        self._con.disconnectedReconnCB()

    def send_ping(self, contact):
        if not app.account_is_connected(self._account):
            return

        to = contact.get_full_jid()
        iq = self._get_ping_iq(to)

        log.info('Send ping to %s', to)

        self._con.connection.SendAndCallForResponse(
            iq, self._pong_received, {'ping_time': time.time(),
                                      'contact': contact})

        app.nec.push_incoming_event(
            PingSentEvent(None, conn=self._con, contact=contact))

    def _pong_received(self, _con, stanza, ping_time, contact):
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
            app.nec.push_incoming_event(
                PingErrorEvent(None, conn=self._con, contact=contact))
            return
        diff = round(time.time() - ping_time, 2)
        log.info('Received pong from %s after %s seconds',
                 stanza.getFrom(), diff)
        app.nec.push_incoming_event(
            PingReplyEvent(None, conn=self._con,
                           contact=contact,
                           seconds=diff))

    def _answer_request(self, _con, stanza):
        iq = stanza.buildReply('result')
        ping = iq.getTag('ping')
        if ping is not None:
            iq.delChild(ping)
        self._con.connection.send(iq)
        log.info('Send pong to %s', stanza.getFrom())
        raise nbxmpp.NodeProcessed


class PingSentEvent(NetworkIncomingEvent):
    name = 'ping-sent'


class PingReplyEvent(NetworkIncomingEvent):
    name = 'ping-reply'


class PingErrorEvent(NetworkIncomingEvent):
    name = 'ping-error'


def get_instance(*args, **kwargs):
    return Ping(*args, **kwargs), 'Ping'
