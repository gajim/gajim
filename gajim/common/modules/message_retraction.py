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

# Message Retraction (XEP-0424)

from __future__ import annotations

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import MessageRetractionReceived
from gajim.common.modules.base import BaseModule


class MessageRetraction(BaseModule):

    _nbxmpp_extends = 'MessageRetraction'

    def __init__(self, client: types.Client) -> None:
        BaseModule.__init__(self, client)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_message_retraction,
                          ns=Namespace.MESSAGE_RETRACT,
                          priority=47)
        ]

    def _process_message_retraction(self,
                                    _client: types.xmppClient,
                                    _stanza: Message,
                                    properties: MessageProperties
                                    ) -> None:

        if properties.message_retraction is None:
            return

        if properties.type.is_error:
            return

        # TODO: make sure to use correct jid here
        jid = properties.jid
        assert jid is not None

        success = app.storage.archive.try_message_retraction(
            self._account,
            jid,
            properties.message_retraction.origin_id,
            properties.occupant_id)

        if not success:
            self._log.warning(
                'Received invalid message retraction request from %s', jid)
            return

        app.ged.raise_event(MessageRetractionReceived(
            account=self._account,
            jid=jid,
            origin_id=properties.message_retraction.origin_id))
        raise nbxmpp.NodeProcessed

    def retract_message(self,
                        jid: JID,
                        message_id: str
                        ) -> None:

        pass
