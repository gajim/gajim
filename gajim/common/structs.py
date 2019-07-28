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
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

from collections import namedtuple

from nbxmpp.protocol import JID

from gajim.common.const import MUCJoinedState

URI = namedtuple('URI', 'type action data')
URI.__new__.__defaults__ = (None, None)  # type: ignore

CapsData = namedtuple('CapsData', 'identities features dataforms')
CapsIdentity = namedtuple('CapsIdentity', 'category type name lang')


class MUCData:
    def __init__(self, room_jid, nick, password, config=None):
        self._room_jid = JID(room_jid)
        self._config = config
        self.nick = nick
        self.password = password
        self.state = MUCJoinedState.NOT_JOINED

    @property
    def jid(self):
        return self._room_jid

    @property
    def occupant_jid(self):
        jid = self._room_jid.copy()
        jid.setResource(self.nick)
        return jid

    @property
    def config(self):
        return self._config
