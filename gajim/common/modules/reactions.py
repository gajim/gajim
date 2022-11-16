# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

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
            StanzaHandler(
                name='message',
                callback=self._process_reaction,
                ns=Namespace.REACTIONS,
                priority=47,
            )
        ]

    def _process_reaction(
        self, _client: types.xmppClient, _stanza: Message, properties: MessageProperties
    ) -> None:

        if properties.reactions is None:
            return

        if properties.type.is_error:
            return

        # TODO: make sure to use correct jid here
        jid = properties.jid
        assert jid is not None

        # TODO: Add reaction to DB

        app.ged.raise_event(
            ReactionReceived(
                account=self._account, jid=jid, reaction_id=properties.reactions.id
            )
        )

    def add_reaction(self, jid: JID, message_id: str, reactions: list[str]) -> None:

        # TODO
        pass

    def remove_reaction(self, jid: JID, message_id: str, reactions: list[str]) -> None:

        # TODO
        pass
