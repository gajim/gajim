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

# XEP-0425: Message Moderation

from __future__ import annotations

import datetime as dt

from nbxmpp import NodeProcessed
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import Message
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import MessageModerated
from gajim.common.events import MessageReceived
from gajim.common.i18n import _
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import get_chat_type_and_direction
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.structs import MUCData

UNKNOWN_MESSAGE = _('Message content unknown')

class Moderations(BaseModule):
    def __init__(self, client: types.Client) -> None:
        BaseModule.__init__(self, client)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_fasten_message,
                          typ='groupchat',
                          ns=Namespace.FASTEN,
                          priority=48),
            StanzaHandler(name='message',
                          callback=self._process_message_moderated_tombstone,
                          typ='groupchat',
                          ns=Namespace.MESSAGE_MODERATE,
                          priority=48),
        ]

    def _process_message_moderated_tombstone(
        self,
        _client: types.xmppClient,
        stanza: Message,
        properties: MessageProperties
    ) -> None:

        if not properties.is_moderation:
            return

        if not properties.is_mam_message:
            return

        assert properties.moderation is not None

        if not properties.moderation.is_tombstone:
            return

        assert properties.remote_jid is not None

        remote_jid = properties.remote_jid
        muc_data = self._client.get_module('MUC').get_muc_data(remote_jid)
        if muc_data is None:
            self._log.warning('Groupchat message from unknown MUC: %s',
                              remote_jid)
            return

        is_occupant_id_supported = self._is_occupant_id_supported(properties)

        self._insert_tombstone(muc_data, properties, is_occupant_id_supported)
        self._insert_moderation_message(properties, is_occupant_id_supported)

        raise NodeProcessed

    def _process_fasten_message(
        self,
        _client: types.xmppClient,
        stanza: Message,
        properties: MessageProperties
    ) -> None:

        if not properties.is_moderation:
            return

        assert properties.moderation is not None

        is_occupant_id_supported = self._is_occupant_id_supported(properties)

        self._insert_moderation_message(properties, is_occupant_id_supported)

        raise NodeProcessed

    def _insert_moderation_message(
        self,
        properties: MessageProperties,
        is_occupant_id_supported: bool
    ) -> None:

        assert properties.moderation is not None

        moderator_nickname = self._get_moderator_nickname(properties)

        moderator_occupant_id = None
        if is_occupant_id_supported:
            moderator_occupant_id = properties.moderation.occupant_id

        remote_jid = properties.remote_jid
        assert remote_jid is not None

        timestamp = dt.datetime.fromtimestamp(
            properties.moderation.stamp, dt.timezone.utc)

        occupant_data = None
        if moderator_occupant_id is not None:
            occupant_data = mod.Occupant(
                account_=self._account,
                remote_jid_=remote_jid,
                id=moderator_occupant_id,
                nickname=moderator_nickname,
                updated_at=timestamp,
            )

        moderation_data = mod.Moderation(
            account_=self._account,
            remote_jid_=remote_jid,
            occupant_=occupant_data,
            stanza_id=properties.moderation.stanza_id,
            by=properties.moderation.by,
            reason=properties.moderation.reason,
            timestamp=timestamp,
        )

        pk = app.storage.archive.insert_row(
            moderation_data, ignore_on_conflict=True)
        if pk == -1:
            return

        app.ged.raise_event(
            MessageModerated(
                account=self._account,
                jid=remote_jid,
                moderation=moderation_data))

    def _insert_tombstone(
        self,
        muc_data: MUCData,
        properties: MessageProperties,
        is_occupant_id_supported: bool
    ) -> None:

        assert properties.mam is not None

        remote_jid = properties.remote_jid
        assert remote_jid is not None
        assert properties.jid is not None

        message_occupant_id = None
        if is_occupant_id_supported:
            message_occupant_id = properties.occupant_id

        timestamp = dt.datetime.fromtimestamp(
            properties.mam.timestamp, dt.timezone.utc)

        occupant_data = None
        if message_occupant_id is not None:
            occupant_data = mod.Occupant(
                account_=self._account,
                remote_jid_=remote_jid,
                id=message_occupant_id,
                nickname=properties.jid.resource,
                updated_at=timestamp,
            )

        m_type, direction = get_chat_type_and_direction(
            muc_data, self._client.get_own_jid(), properties)

        assert properties.id is not None

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
            occupant_=occupant_data,
        )

        pk = app.storage.archive.insert_object(message_data)

        app.ged.raise_event(
            MessageReceived(
                account=self._account,
                jid=remote_jid,
                m_type=MessageType.GROUPCHAT,
                from_mam=True,
                pk=pk))

    def _is_occupant_id_supported(self, properties: MessageProperties) -> bool:
        assert properties.remote_jid is not None
        contact = self._client.get_module('Contacts').get_contact(
            properties.remote_jid, groupchat=True)
        return contact.supports(Namespace.OCCUPANT_ID)

    def _get_moderator_nickname(
        self,
        properties: MessageProperties
    ) -> str | None:

        assert properties.moderation is not None
        if properties.moderation.by is None:
            return None
        return properties.moderation.by.resource
