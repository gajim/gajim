# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# XEP-0258: Security Labels in XMPP

from __future__ import annotations

from typing import Any

from collections.abc import Generator

from nbxmpp.errors import is_error
from nbxmpp.modules.security_labels import Catalog
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoInfo

from gajim.common import app
from gajim.common import types
from gajim.common.events import SecCatalogReceived
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task


class SecLabels(BaseModule):

    _nbxmpp_extends = 'SecurityLabels'
    _nbxmpp_methods = [
        'request_catalog',
    ]

    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self._catalogs: dict[JID, Catalog] = {}
        self.supported = False

    def pass_disco(self, info: DiscoInfo) -> None:
        if Namespace.SECLABEL not in info.features:
            return

        self.supported = True
        self._log.info('Discovered security labels: %s', info.jid)

    @as_task
    def request_catalog(self, jid: JID) -> Generator[Any, Any]:
        _task = yield

        catalog = yield self._nbxmpp('SecurityLabels').request_catalog(str(jid))

        if is_error(catalog):
            self._log.info(catalog)
            return

        assert isinstance(catalog, Catalog)
        self._catalogs[jid] = catalog

        self._log.info('Received catalog: %s', jid)

        app.ged.raise_event(SecCatalogReceived(account=self._account,
                                               jid=jid,
                                               catalog=catalog))

    def get_catalog(self, jid: JID) -> Catalog | None:
        if not self.supported:
            return None

        catalog = self._catalogs.get(jid)
        if catalog is None:
            self.request_catalog(jid)
            return None
        return catalog
