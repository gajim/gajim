# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

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
