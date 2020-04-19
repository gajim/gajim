# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

# XEP-0083: Nested Roster Groups

import nbxmpp
from nbxmpp.namespaces import Namespace

from gajim.common.modules.base import BaseModule


class Delimiter(BaseModule):
    def __init__(self, con):
        BaseModule.__init__(self, con)
        self.available = False
        self.delimiter = '::'

    def get_roster_delimiter(self):
        self._log.info('Request')
        node = nbxmpp.Node('storage', attrs={'xmlns': 'roster:delimiter'})
        iq = nbxmpp.Iq('get', Namespace.PRIVATE, payload=node)

        self._con.connection.SendAndCallForResponse(
            iq, self._delimiter_received)

    def _delimiter_received(self, _nbxmpp_client, stanza):
        if not nbxmpp.isResultNode(stanza):
            self._log.info('Request error: %s', stanza.getError())
        else:
            delimiter = stanza.getQuery().getTagData('roster')
            self.available = True
            self._log.info('Delimiter received: %s', delimiter)
            if delimiter:
                self.delimiter = delimiter
            else:
                self.set_roster_delimiter()

        self._con.connect_machine()

    def set_roster_delimiter(self):
        self._log.info('Set delimiter')
        iq = nbxmpp.Iq('set', Namespace.PRIVATE)
        roster = iq.getQuery().addChild('roster', namespace='roster:delimiter')
        roster.setData('::')

        self._con.connection.SendAndCallForResponse(
            iq, self._set_delimiter_response)

    def _set_delimiter_response(self, _nbxmpp_client, stanza):
        if not nbxmpp.isResultNode(stanza):
            self._log.info('Store error: %s', stanza.getError())


def get_instance(*args, **kwargs):
    return Delimiter(*args, **kwargs), 'Delimiter'
