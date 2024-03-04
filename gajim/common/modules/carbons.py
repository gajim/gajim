# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

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
