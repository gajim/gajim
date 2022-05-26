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

# XEP-0163: Personal Eventing Protocol

from __future__ import annotations

from nbxmpp.structs import DiscoInfo

from gajim.common import types
from gajim.common.modules.base import BaseModule


class PEP(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.supported = False

    def pass_disco(self, info: DiscoInfo) -> None:
        for identity in info.identities:
            if identity.category == 'pubsub':
                if identity.type == 'pep':
                    self._log.info('Discovered PEP support: %s', info.jid)
                    self.supported = True
