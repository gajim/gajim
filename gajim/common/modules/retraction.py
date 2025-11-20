# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Message Retractions (XEP-0424)

from __future__ import annotations

from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.protocol import NodeProcessed
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import MessageReceived
from gajim.common.events import MessageRetracted
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.message import MessageState
from gajim.common.modules.message_util import get_chat_type_and_direction
from gajim.common.modules.message_util import get_message_timestamp
from gajim.common.modules.message_util import get_occupant_info
from gajim.common.modules.message_util import UNKNOWN_MESSAGE
from gajim.common.storage.archive import models as mod
from gajim.common.structs import MessageType
from gajim.common.structs import OutgoingMessage


class Retraction(BaseModule):

    _nbxmpp_extends = 'Retraction'

    def __init__(self, client: types.Client) -> None:
        BaseModule.__init__(self, client)

        self.handlers = [
            StanzaHandler(
                name="message",
                callback=self._process_retraction_message,
                ns=Namespace.MESSAGE_RETRACT_1,
                priority=46,
            ),
        ]

    def send_retraction(
        self,
        contact: types.ChatContactT,
        retract_ids: list[str],
    ) -> None:

        for retraction_id in retract_ids:
            message = OutgoingMessage(
                account=self._account,
                contact=contact,
                retraction_id=retraction_id,
                play_sound=False,
            )

            self._client.send_message(message)
            self._log.info('Send retraction for %s to %s', retraction_id, contact.jid)

    def _process_retraction_message(
        self,
        _client: types.NBXMPPClient,
        stanza: Message,
        properties: MessageProperties,
    ) -> None:

        if properties.retraction is None:
            return

        if properties.moderation is not None:
            # Handled in moderation module
            return

        if properties.type.is_error:
            return

        assert properties.remote_jid is not None
        assert properties.jid is not None

        muc_data = self._client.get_module('MUC').get_muc_data(properties.remote_jid)

        m_type, direction = get_chat_type_and_direction(
            muc_data, self._client.get_own_jid(), properties
        )

        remote_jid = properties.remote_jid
        assert remote_jid is not None

        timestamp = get_message_timestamp(properties)
        occupant = None

        if m_type in (MessageType.GROUPCHAT, MessageType.PM):
            contact = self._client.get_module('Contacts').get_contact(
                properties.jid, groupchat=True
            )
            if not isinstance(contact, GroupchatParticipant):
                self._log.warning(
                    'Ignore unexpected retraction from: %s' % properties.jid
                )
                return

            occupant = get_occupant_info(
                self._account,
                remote_jid,
                self._get_own_bare_jid(),
                direction,
                timestamp,
                contact,
                properties,
            )

        if properties.retraction.is_tombstone:
            assert properties.mam is not None

            self._log.info('Received retraction tombstone from %s for %s',
                           remote_jid, properties.mam.id)

            message_data = mod.Message(
                account_=self._account,
                remote_jid_=remote_jid,
                resource=properties.jid.resource,
                type=m_type,
                direction=direction,
                timestamp=timestamp,
                state=MessageState.ACKNOWLEDGED,
                text=UNKNOWN_MESSAGE,
                id=properties.id,
                stanza_id=properties.mam.id,
                occupant_=occupant,
            )

            pk = app.storage.archive.insert_object(message_data)

            app.ged.raise_event(
                MessageReceived(
                    account=self._account,
                    jid=remote_jid,
                    m_type=m_type,
                    mam=properties.mam,
                    pk=pk,
                )
            )

        else:

            self._log.info('Received retraction from %s for %s',
                           remote_jid, properties.retraction.id)
            retraction = mod.Retraction(
                account_=self._account,
                remote_jid_=remote_jid,
                occupant_=occupant,
                id=properties.retraction.id,
                direction=direction,
                timestamp=properties.retraction.timestamp,
            )

            pk = app.storage.archive.insert_row(retraction, ignore_on_conflict=True)
            if pk == -1:
                raise NodeProcessed

            app.ged.raise_event(
                MessageRetracted(
                    account=self._account, jid=remote_jid, retraction=retraction
                )
            )

        raise NodeProcessed
