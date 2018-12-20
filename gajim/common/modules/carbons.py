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

# XEP-0280: Message Carbons

import logging

import nbxmpp

from gajim.common import app

log = logging.getLogger('gajim.c.m.carbons')


class Carbons:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = []

        self.supported = False

    def pass_disco(self, from_, _identities, features, _data, _node):
        if nbxmpp.NS_CARBONS not in features:
            return

        self.supported = True
        log.info('Discovered carbons: %s', from_)

        if app.config.get_per('accounts', self._account,
                              'enable_message_carbons'):
            iq = nbxmpp.Iq('set')
            iq.setTag('enable', namespace=nbxmpp.NS_CARBONS)
            log.info('Activate')
            self._con.connection.send(iq)
        else:
            log.warning('Carbons deactivated (user setting)')


def get_instance(*args, **kwargs):
    return Carbons(*args, **kwargs), 'Carbons'
