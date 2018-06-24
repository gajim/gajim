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

import logging
import datetime
import time

import nbxmpp

from gajim.common import app
from gajim.common.nec import NetworkIncomingEvent

log = logging.getLogger('gajim.c.m.entity_time')

ZERO = datetime.timedelta(0)


class EntityTime:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            ('iq', self._answer_request, 'get', nbxmpp.NS_TIME_REVISED),
        ]

    def request_entity_time(self, jid, resource):
        if not app.account_is_connected(self._account):
            return
        # If we are invisible, do not request
        if self._con.connected == app.SHOW_LIST.index('invisible'):
            return

        if resource:
            jid += '/' + resource
        iq = nbxmpp.Iq(to=jid, typ='get')
        iq.addChild('time', namespace=nbxmpp.NS_TIME_REVISED)

        log.info('Requested: %s', jid)

        self._con.connection.SendAndCallForResponse(iq, self._result_received)

    def _result_received(self, stanza):
        time_info = None
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
        else:
            time_info = self._extract_info(stanza)

        log.info('Received: %s %s',
                 stanza.getFrom(), time_info)

        app.nec.push_incoming_event(
            TimeResultReceivedEvent(None, conn=self._con,
                                    jid=stanza.getFrom(),
                                    time_info=time_info))

    def _extract_info(self, stanza):
        time_ = stanza.getTag('time')
        if not time_:
            log.warning('No time node: %s', stanza)
            return

        tzo = time_.getTag('tzo').getData()
        if tzo.lower() == 'z':
            tzo = '0:0'
        try:
            tzoh, tzom = tzo.split(':')
        except Exception as e:
            log.warning('Wrong tzo node: %s', stanza)
            return
        utc_time = time_.getTag('utc').getData()

        if utc_time[-1:] == 'Z':
            # Remove the trailing 'Z'
            utc_time = utc_time[:-1]
        elif utc_time[-6:] == "+00:00":
            # Remove the trailing "+00:00"
            utc_time = utc_time[:-6]
        else:
            log.warning('Wrong timezone defintion: %s', utc_time)
            return

        try:
            t = datetime.datetime.strptime(utc_time, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            try:
                t = datetime.datetime.strptime(utc_time,
                                               '%Y-%m-%dT%H:%M:%S.%f')
            except ValueError as e:
                log.warning('Wrong time format: %s', e)
                return

        t = t.replace(tzinfo=UTC())
        return t.astimezone(contact_tz(tzoh, tzom)).strftime('%c')

    def _answer_request(self, con, stanza):
        log.info('%s asked for the time', stanza.getFrom())
        if app.config.get_per('accounts', self._account, 'send_time_info'):
            iq = stanza.buildReply('result')
            time_ = iq.setTag('time', namespace=nbxmpp.NS_TIME_REVISED)
            formated_time = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
            time_.setTagData('utc', formated_time)
            isdst = time.localtime().tm_isdst
            zone = -(time.timezone, time.altzone)[isdst] / 60.0
            tzo = (zone / 60, abs(zone % 60))
            time_.setTagData('tzo', '%+03d:%02d' % (tzo))
            log.info('Answer: %s %s', formated_time, '%+03d:%02d' % (tzo))
        else:
            iq = stanza.buildReply('error')
            err = nbxmpp.ErrorNode(nbxmpp.ERR_SERVICE_UNAVAILABLE)
            iq.addChild(node=err)
            log.info('Send service-unavailable')
        self._con.connection.send(iq)
        raise nbxmpp.NodeProcessed


class TimeResultReceivedEvent(NetworkIncomingEvent):
    name = 'time-result-received'
    base_network_events = []

    def generate(self):
        return True


class UTC(datetime.tzinfo):
    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO


class contact_tz(datetime.tzinfo):

    def __init__(self, tzoh, tzom):
        self._tzoh = tzoh
        self._tzom = tzom

    def utcoffset(self, dt):
        return datetime.timedelta(hours=int(self._tzoh),
                                  minutes=int(self._tzom))

    def tzname(self, dt):
        return "remote timezone"

    def dst(self, dt):
        return ZERO
