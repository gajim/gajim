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

# XEP-0092: Software Version

import logging

import nbxmpp

from gajim.common import app
from gajim.common.helpers import get_os_info
from gajim.common.nec import NetworkIncomingEvent

log = logging.getLogger('gajim.c.m.software_version')


class SoftwareVersion:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            ('iq', self._answer_request, 'get', nbxmpp.NS_VERSION),
        ]

    def request_os_info(self, jid, resource):
        if not app.account_is_connected(self._account):
            return
        # If we are invisible, do not request
        if self._con.connected == app.SHOW_LIST.index('invisible'):
            return

        if resource:
            jid += '/' + resource
        iq = nbxmpp.Iq(to=jid, typ='get', queryNS=nbxmpp.NS_VERSION)

        log.info('Requested: %s', jid)

        self._con.connection.SendAndCallForResponse(iq, self._result_received)

    def _result_received(self, stanza):
        client_info, os_info = None, None
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
        else:
            try:
                client_info, os_info = self._extract_info(stanza)
            except Exception:
                log.exception('Error')
                log.error(stanza)

        log.info('Received: %s %s %s',
                 stanza.getFrom(), client_info, os_info)

        app.nec.push_incoming_event(
            VersionResultReceivedEvent(None, conn=self._con,
                                       jid=stanza.getFrom(),
                                       client_info=client_info,
                                       os_info=os_info))

    @staticmethod
    def _extract_info(stanza):
        query = stanza.getTag('query')
        name = query.getTag('name').getData()
        version = query.getTag('version').getData()
        client_info = '%s %s' % (name, version)
        os_info = query.getTag('os')
        if os_info is not None:
            os_info = os_info.getData()
        return client_info, os_info

    def _answer_request(self, _con, stanza):
        log.info('%s asked for the software version', stanza.getFrom())
        if app.config.get_per('accounts', self._account, 'send_os_info'):
            os_info = get_os_info()
            iq = stanza.buildReply('result')
            query = iq.getQuery()
            query.setTagData('name', 'Gajim')
            query.setTagData('version', app.version)
            query.setTagData('os', os_info)
            log.info('Answer: Gajim %s %s', app.version, os_info)
        else:
            iq = stanza.buildReply('error')
            err = nbxmpp.ErrorNode(nbxmpp.ERR_SERVICE_UNAVAILABLE)
            iq.addChild(node=err)
            log.info('Send service-unavailable')
        self._con.connection.send(iq)
        raise nbxmpp.NodeProcessed


class VersionResultReceivedEvent(NetworkIncomingEvent):
    name = 'version-result-received'


def get_instance(*args, **kwargs):
    return SoftwareVersion(*args, **kwargs), 'SoftwareVersion'
