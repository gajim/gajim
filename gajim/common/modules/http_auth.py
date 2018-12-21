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

import logging

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkEvent

log = logging.getLogger('gajim.c.m.http_auth')


class HTTPAuth:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = []

    def delegate(self, stanza, properties):
        log.info('Auth request received')
        auto_answer = app.config.get_per(
            'accounts', self._account, 'http_auth')
        if auto_answer in ('yes', 'no'):
            self.build_http_auth_answer(stanza, auto_answer)
            raise nbxmpp.NodeProcessed

        app.nec.push_incoming_event(
            NetworkEvent('http-auth-received',
                         conn=self._con,
                         iq_id=properties['id'],
                         method=properties['method'],
                         url=properties['url'],
                         msg=properties['body'],
                         stanza=stanza))

    def build_http_auth_answer(self, stanza, answer):
        if answer == 'yes':
            log.info('Auth request approved')
            confirm = stanza.getTag('confirm')
            reply = stanza.buildReply('result')
            if stanza.getName() == 'message':
                reply.addChild(node=confirm)
            self._con.connection.send(reply)
        elif answer == 'no':
            log.info('Auth request denied')
            err = nbxmpp.Error(stanza, nbxmpp.protocol.ERR_NOT_AUTHORIZED)
            self._con.connection.send(err)


def get_instance(*args, **kwargs):
    return HTTPAuth(*args, **kwargs), 'HTTPAuth'
