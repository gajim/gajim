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

from __future__ import annotations

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.structs import DiscoInfo

from gajim.common import types
from gajim.common.modules.base import BaseModule


class Carbons(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.supported = False

    def pass_disco(self, info: DiscoInfo) -> None:
        if Namespace.CARBONS not in info.features:
            return

        self.supported = True
        self._log.info('Discovered carbons: %s', info.jid)

        iq = nbxmpp.Iq('set')
        iq.setTag('enable', namespace=Namespace.CARBONS)
        self._log.info('Activate')
        self._con.connection.send(iq)
