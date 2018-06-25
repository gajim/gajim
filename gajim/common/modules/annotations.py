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

# XEP-0145: Annotations

import logging

import nbxmpp

from gajim.common import app
from gajim.common import helpers

log = logging.getLogger('gajim.c.m.annotations')


class Annotations:
    def __init__(self, con):
        self._con = con
        self._account = con.name
        self._server = self._con.get_own_jid().getDomain()

        self.handlers = []
        self.annotations = {}

    def get_annotations(self):
        if not app.account_is_connected(self._account):
            return

        log.info('Request annotations for %s', self._server)
        iq = nbxmpp.Iq(typ='get')
        iq2 = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        iq2.addChild(name='storage', namespace='storage:rosternotes')

        self._con.connection.SendAndCallForResponse(iq, self._result_received)

    def _result_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Error: %s', stanza.getError())
            return

        log.info('Received annotations from %s', self._server)
        self.annotations = {}
        query = stanza.getTag('query')
        storage_node = query.getTag('storage')
        if storage_node is None:
            return

        notes = storage_node.getTags('note')
        if notes is None:
            return

        for note in notes:
            try:
                jid = helpers.parse_jid(note.getAttr('jid'))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it',
                            note.getAttr('jid'))
                continue
            self.annotations[jid] = note.getData()

    def store_annotations(self):
        if not app.account_is_connected(self._account):
            return

        iq = nbxmpp.Iq(typ='set')
        iq2 = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        iq3 = iq2.addChild(name='storage', namespace='storage:rosternotes')
        for jid in self.annotations.keys():
            if self.annotations[jid]:
                iq4 = iq3.addChild(name='note')
                iq4.setAttr('jid', jid)
                iq4.setData(self.annotations[jid])

        self._con.connection.SendAndCallForResponse(
            iq, self._store_result_received)

    def _store_result_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.warning('Storing rosternotes failed: %s', stanza.getError())
            return
        log.info('Storing rosternotes successful')
