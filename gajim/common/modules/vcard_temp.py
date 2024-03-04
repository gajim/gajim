# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0054: vcard-temp

from __future__ import annotations

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import DiscoInfo

from gajim.common import types
from gajim.common.modules.base import BaseModule


class VCardTemp(BaseModule):

    _nbxmpp_extends = 'VCardTemp'
    _nbxmpp_methods = [
        'request_vcard',
        'set_vcard',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self._own_vcard = None
        self.supported = False

    def pass_disco(self, info: DiscoInfo) -> None:
        if Namespace.VCARD not in info.features:
            return

        self.supported = True
        self._log.info('Discovered vcard-temp: %s', info.jid)
