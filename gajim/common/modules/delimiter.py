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

import logging

import nbxmpp

log = logging.getLogger('gajim.c.m.delimiter')


class Delimiter:
    def __init__(self, con):
        self._con = con
        self._account = con.name
        self.available = False

        self.delimiter = '::'

        self.handlers = []

    def get_roster_delimiter(self):
        log.info('Request')
        node = nbxmpp.Node('storage', attrs={'xmlns': 'roster:delimiter'})
        iq = nbxmpp.Iq('get', nbxmpp.NS_PRIVATE, payload=node)

        self._con.connection.SendAndCallForResponse(
            iq, self._delimiter_received)

    def _delimiter_received(self, stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Request error: %s', stanza.getError())
        else:
            delimiter = stanza.getQuery().getTagData('roster')
            self.available = True
            log.info('Delimiter received: %s', delimiter)
            if delimiter:
                self.delimiter = delimiter
            else:
                self.set_roster_delimiter()

        self._con.connect_machine()

    def set_roster_delimiter(self):
        log.info('Set delimiter')
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVATE)
        roster = iq.getQuery().addChild('roster', namespace='roster:delimiter')
        roster.setData('::')

        self._con.connection.SendAndCallForResponse(
            iq, self._set_delimiter_response)

    @staticmethod
    def _set_delimiter_response(stanza):
        if not nbxmpp.isResultNode(stanza):
            log.info('Store error: %s', stanza.getError())


def get_instance(*args, **kwargs):
    return Delimiter(*args, **kwargs), 'Delimiter'
