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

from __future__ import annotations

from typing import Any

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import MDSData
from nbxmpp.structs import MessageProperties

from gajim.common import app
from gajim.common import types
from gajim.common.events import ReadStateSync
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import event_node


class MDS(BaseModule):
    _nbxmpp_extends = 'MDS'
    _nbxmpp_methods = ['set_mds']

    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)
        self._register_pubsub_handler(self._mds_received)

    @event_node(Namespace.MDS)
    def _mds_received(self,
                      _client: types.Client,
                      _stanza: Any,
                      properties: MessageProperties) -> None:
        if not properties.pubsub_event:
            return

        data = properties.pubsub_event.data

        if data is None:
            return

        assert isinstance(data, MDSData)

        if not data.jid or not data.stanza_id:
            self._log.warning('Received invalid MDS event')
            return

        self._log.info('Read state sync (MDS): %s - %s',
                       data.jid,
                       data.stanza_id)
        app.ged.raise_event(
            ReadStateSync(account=self._account,
                          jid=data.jid,
                          marker_id=data.stanza_id))
