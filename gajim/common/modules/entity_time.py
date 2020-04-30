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

import time

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler
from nbxmpp.modules.date_and_time import parse_datetime
from nbxmpp.modules.date_and_time import create_tzinfo

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.modules.base import BaseModule


class EntityTime(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='iq',
                          callback=self._answer_request,
                          typ='get',
                          ns=Namespace.TIME_REVISED),
        ]

    def request_entity_time(self, jid, resource):
        if not app.account_is_available(self._account):
            return

        if resource:
            jid += '/' + resource
        iq = nbxmpp.Iq(to=jid, typ='get')
        iq.addChild('time', namespace=Namespace.TIME_REVISED)

        self._log.info('Requested: %s', jid)

        self._con.connection.SendAndCallForResponse(iq, self._result_received)

    def _result_received(self, _nbxmpp_client, stanza):
        time_info = None
        if not nbxmpp.isResultNode(stanza):
            self._log.info('Error: %s', stanza.getError())
        else:
            time_info = self._extract_info(stanza)

        self._log.info('Received: %s %s', stanza.getFrom(), time_info)

        app.nec.push_incoming_event(NetworkEvent('time-result-received',
                                                 conn=self._con,
                                                 jid=stanza.getFrom(),
                                                 time_info=time_info))

    def _extract_info(self, stanza):
        time_ = stanza.getTag('time')
        if not time_:
            self._log.warning('No time node: %s', stanza)
            return None

        tzo = time_.getTag('tzo').getData()
        if not tzo:
            self._log.warning('Wrong tzo node: %s', stanza)
            return None

        remote_tz = create_tzinfo(tz_string=tzo)
        if remote_tz is None:
            self._log.warning('Wrong tzo node: %s', stanza)
            return None

        utc_time = time_.getTag('utc').getData()
        date_time = parse_datetime(utc_time, check_utc=True)
        if date_time is None:
            self._log.warning('Wrong timezone definition: %s %s',
                              utc_time, stanza.getFrom())
            return None

        date_time = date_time.astimezone(remote_tz)
        return date_time.strftime('%c %Z')

    def _answer_request(self, _con, stanza, _properties):
        self._log.info('%s asked for the time', stanza.getFrom())
        if app.config.get_per('accounts', self._account, 'send_time_info'):
            iq = stanza.buildReply('result')
            time_ = iq.setTag('time', namespace=Namespace.TIME_REVISED)
            formated_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            time_.setTagData('utc', formated_time)
            isdst = time.localtime().tm_isdst
            zone = -(time.timezone, time.altzone)[isdst] / 60.0
            tzo = (zone / 60, abs(zone % 60))
            time_.setTagData('tzo', '%+03d:%02d' % (tzo))
            self._log.info('Answer: %s %s', formated_time, '%+03d:%02d' % (tzo))
        else:
            iq = stanza.buildReply('error')
            err = nbxmpp.ErrorNode(nbxmpp.ERR_SERVICE_UNAVAILABLE)
            iq.addChild(node=err)
            self._log.info('Send service-unavailable')
        self._con.connection.send(iq)
        raise nbxmpp.NodeProcessed


def get_instance(*args, **kwargs):
    return EntityTime(*args, **kwargs), 'EntityTime'
