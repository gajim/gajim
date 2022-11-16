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

# Message Reactions (XEP-0444)

from __future__ import annotations

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import ReactionReceived
from gajim.common.modules.base import BaseModule


class Reactions(BaseModule):

    _nbxmpp_extends = 'Reactions'

    def __init__(self, client: types.Client) -> None:
        BaseModule.__init__(self, client)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_reaction,
                          ns=Namespace.REACTIONS,
                          priority=47)
        ]

    def _process_reaction(self,
                          _client: types.xmppClient,
                          _stanza: Message,
                          properties: MessageProperties
                          ) -> None:

        if properties.reactions is None:
            return

        if properties.type.is_error:
            return

        # TODO: make sure to use correct jid here
        jid = properties.jid
        assert jid is not None

        app.storage.archive.update_reactions(
            self._account,
            jid,
            properties.occupant_id,
            properties.timestamp,
            properties.reactions)

        app.ged.raise_event(
            ReactionReceived(account=self._account,
                             jid=jid,
                             reaction_id=properties.reactions.id))

    def add_reaction(self,
                     jid: JID,
                     message_id: str,
                     reactions: list[str]
                     ) -> None:

        # TODO
        pass

    def remove_reaction(self,
                        jid: JID,
                        message_id: str,
                        reactions: list[str]
                        ) -> None:

        # TODO
        pass
