# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Message Reactions (XEP-0444)

from __future__ import annotations

import emoji
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import ReactionUpdated
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.message_util import get_chat_type_and_direction
from gajim.common.modules.message_util import get_message_timestamp
from gajim.common.modules.message_util import get_occupant_info
from gajim.common.storage.archive import models as mod
from gajim.common.structs import MessageType
from gajim.common.structs import OutgoingMessage


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
        self,
        _client: types.xmppClient,
        _stanza: Message,
        properties: MessageProperties,
    ) -> None:

        if properties.reactions is None:
            return

        if properties.type.is_error:
            return

        remote_jid = properties.remote_jid
        assert remote_jid is not None

        if not properties.reactions.emojis:
            # TODO DELETE Reactions
            raise NodeProcessed

        # Set arbitrary limit of max reactions to prevent
        # performance problems when loading and displaying them.
        # Check if reactions qualify as emojis.
        reactions: list[str] = []
        for reaction in list(properties.reactions.emojis)[:10]:
            if emoji.is_emoji(reaction):
                reactions.append(reaction)

        if not reactions:
            self._log.warning(
                'Reactions did not qualify as emoji: %s', properties.reactions.emojis
            )
            raise NodeProcessed

        timestamp = get_message_timestamp(properties)

        muc_data = None
        if properties.type.is_groupchat:
            muc_data = self._client.get_module('MUC').get_muc_data(remote_jid)
            if muc_data is None:
                self._log.warning('Reaction message from unknown MUC: %s', remote_jid)
                raise NodeProcessed

        own_bare_jid = self._get_own_bare_jid()

        m_type, direction = get_chat_type_and_direction(
            muc_data, own_bare_jid, properties
        )

        occupant = None
        if m_type in (MessageType.GROUPCHAT, MessageType.PM):
            assert properties.jid is not None
            contact = self._client.get_module('Contacts').get_contact(
                properties.jid, groupchat=True
            )

            assert isinstance(contact, GroupchatParticipant)
            occupant = get_occupant_info(
                account=self._account,
                remote_jid=remote_jid,
                own_bare_jid=own_bare_jid,
                direction=direction,
                timestamp=timestamp,
                contact=contact,
                properties=properties,
            )

            if occupant is None:
                self._log.info('Reactions not supported without occupant-id')
                raise NodeProcessed

        reaction = mod.Reaction(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=occupant,
            id=properties.reactions.id,
            direction=direction,
            emojis=';'.join(reactions),
            timestamp=timestamp,
        )

        app.storage.archive.upsert_row2(reaction)

        app.ged.raise_event(
            ReactionUpdated(
                account=self._account,
                jid=remote_jid,
                reaction_id=properties.reactions.id,
            )
        )

        raise NodeProcessed

    def send_reaction(
        self,
        contact: types.ChatContactT,
        reaction_id: str,
        reactions: set[str],
    ) -> None:

        message = OutgoingMessage(
            account=self._account,
            contact=contact,
            reaction_data=(reaction_id, reactions),
            play_sound=False,
        )

        self._client.send_message(message)
        self._log.info('Send %s: %s', reactions, contact.jid)
