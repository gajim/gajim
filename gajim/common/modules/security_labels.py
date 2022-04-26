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

# XEP-0258: Security Labels in XMPP

from typing import Optional

from nbxmpp.errors import is_error
from nbxmpp.namespaces import Namespace
from nbxmpp.modules.security_labels import Catalog

from gajim.common import app
from gajim.common.events import SecCatalogReceived
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import as_task


class SecLabels(BaseModule):

    _nbxmpp_extends = 'SecurityLabels'
    _nbxmpp_methods = [
        'request_catalog',
    ]

    def __init__(self, con):
        BaseModule.__init__(self, con)

        self._catalogs: dict[str, Catalog] = {}
        self.supported = False

    def pass_disco(self, info):
        if Namespace.SECLABEL not in info.features:
            return

        self.supported = True
        self._log.info('Discovered security labels: %s', info.jid)

    @as_task
    def request_catalog(self, jid: str):

        _task = yield

        catalog = yield self._nbxmpp('SecurityLabels').request_catalog(jid)

        if is_error(catalog):
            self._log.info(catalog)
            return

        self._catalogs[jid] = catalog

        self._log.info('Received catalog: %s', jid)

        app.ged.raise_event(SecCatalogReceived(account=self._account,
                                               jid=jid,
                                               catalog=catalog))

    def get_catalog(self, jid: str) -> Optional[Catalog]:
        if not self.supported:
            return None

        catalog = self._catalogs.get(jid)
        if catalog is None:
            self.request_catalog(jid)
            return None
        return catalog
