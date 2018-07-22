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

# Presence handler

import logging

from gajim.common import app
from gajim.common.nec import NetworkEvent

log = logging.getLogger('gajim.c.m.presence')


class Presence:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [('presence', self._presence_received)]

    def _presence_received(self, con, stanza):
        log.info('Received from %s', stanza.getFrom())
        app.nec.push_incoming_event(
            NetworkEvent('raw-pres-received',
                         conn=self._con,
                         stanza=stanza))


def parse_show(stanza):
    show = stanza.getShow()
    type_ = parse_type(stanza)
    if show is None and type_ is None:
        return 'online'

    if type_ == 'unavailable':
        return 'offline'

    if show not in (None, 'chat', 'away', 'xa', 'dnd'):
        log.warning('Invalid show element: %s', stanza)
        if type_ is None:
            return 'online'
        return 'offline'

    if show is None:
        return 'online'
    return show


def parse_type(stanza):
    type_ = stanza.getType()
    if type_ not in (None, 'unavailable', 'error', 'subscribe',
                     'subscribed', 'unsubscribe', 'unsubscribed'):
        log.warning('Invalid type: %s', stanza)
        return None
    return type_


def get_instance(*args, **kwargs):
    return Presence(*args, **kwargs), 'Presence'
