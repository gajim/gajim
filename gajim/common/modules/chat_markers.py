# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Chat Markers (XEP-0333)

from __future__ import annotations

from typing import Any

from dataclasses import dataclass
from datetime import datetime

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import DiscoInfo
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import DisplayedReceived
from gajim.common.events import ReadStateSync
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import ResourceContact
from gajim.common.modules.message_util import get_chat_type_and_direction
from gajim.common.modules.message_util import get_message_timestamp
from gajim.common.modules.message_util import get_occupant_info
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.structs import OutgoingMessage


class ChatMarkers(BaseModule):

    _nbxmpp_extends = 'ChatMarkers'

    def __init__(self, client: types.Client):
        BaseModule.__init__(self, client)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._process_chat_marker,
                          ns=Namespace.CHATMARKERS,
                          priority=47),
        ]

    def pass_disco(self, info: DiscoInfo) -> None:
        self.mds_assist_supported = Namespace.MDS_ASSIST in info.features

    def _process_chat_marker(self,
                             _client: types.NBXMPPClient,
                             _stanza: Any,
                             properties: MessageProperties) -> None:

        if properties.marker is None or not properties.marker.is_displayed:
            return

        if properties.type.is_error:
            return

        self._process(properties)
        raise nbxmpp.NodeProcessed

    def _process(self, properties: MessageProperties) -> None:
        assert properties.marker is not None
        assert properties.jid is not None

        jid = properties.jid
        if not properties.is_muc_pm:
            jid = properties.jid.new_as_bare()

        if properties.type.is_groupchat:
            if properties.jid.resource is None:
                return

            assert properties.muc_jid is not None
            contact = self._client.get_module('Contacts').get_contact(
                properties.muc_jid,
                groupchat=True)
            assert isinstance(contact, GroupchatContact)
            if not contact.is_joined:
                self._log.warning('Received chat marker while not joined')
                return

            if properties.muc_nickname != contact.nickname:
                self._raise_event(properties)
                return

            self._raise_read_state_sync(jid, properties.marker.id)
            return

        if (properties.is_sent_carbon or
                (properties.is_mam_message and properties.is_from_us())):
            self._raise_read_state_sync(jid, properties.marker.id)
            return

        self._raise_event(properties)

    def _raise_read_state_sync(self, jid: JID, marker_id: str) -> None:
        self._log.info('Read state sync: %s - %s', jid, marker_id)
        app.ged.raise_event(
            ReadStateSync(account=self._account,
                          jid=jid,
                          marker_id=marker_id))

    def _raise_event(self, properties: MessageProperties) -> None:
        assert properties.marker is not None
        assert properties.jid is not None
        assert properties.remote_jid is not None

        self._log.info('displayed-received: %s %s',
                       properties.remote_jid,
                       properties.marker.id)

        remote_jid = properties.remote_jid
        timestamp = get_message_timestamp(properties)

        muc_data = None
        if properties.type.is_groupchat:
            muc_data = self._client.get_module('MUC').get_muc_data(remote_jid)
            if muc_data is None:
                self._log.warning(
                    'Groupchat message from unknown MUC: %s', remote_jid
                )
                return

        m_type, direction = get_chat_type_and_direction(
            muc_data, self._client.get_own_jid(), properties)

        if direction == ChatDirection.OUTGOING:
            return

        contact = self._get_contact_with_mtype(m_type, properties.jid)

        if not self._is_sending_marker_allowed(contact):
            self._log.info('Ignore marker because setting is disabled')
            return

        occupant = None
        if m_type in (MessageType.GROUPCHAT, MessageType.PM):
            if properties.jid.is_bare:
                self._log.warning("Received marker from MUC bare jid")
                return

            assert isinstance(contact, GroupchatParticipant)
            occupant = get_occupant_info(
                self._account,
                remote_jid=remote_jid,
                own_bare_jid=self._get_own_bare_jid(),
                direction=ChatDirection.INCOMING,
                timestamp=timestamp,
                contact=contact,
                properties=properties,
            )

            if occupant is None:
                # Support chat markers in group chats only if occupant-id
                # is available
                return

        marker_data = mod.DisplayedMarker(
            account_=self._account,
            remote_jid_=properties.remote_jid,
            occupant_=occupant,
            id=properties.marker.id,
            timestamp=timestamp)

        pk = app.storage.archive.insert_object(marker_data)
        if pk == -1:
            return

        app.ged.raise_event(
            DisplayedReceived(
                account=self._account,
                jid=properties.remote_jid,
                pk=pk,
            )
        )

    def send_displayed_marker(self,
                              contact: types.ChatContactT,
                              message_id: str,
                              stanza_id: str | None) -> bool:

        # Return value is True if displayed marker was sent and
        # mds assist was added

        if not self._is_sending_marker_allowed(contact):
            return False

        marker_id = self._determine_marker_id(contact, message_id, stanza_id)

        if not self.mds_assist_supported or isinstance(contact, ResourceContact):
            # Assist is not added for private groupchat messages see
            # https://xmpp.org/extensions/xep-0490.html#rules-client
            stanza_id = None

        message = OutgoingMessage(account=self._account,
                                  contact=contact,
                                  marker=('displayed', marker_id),
                                  mds_id=stanza_id,
                                  play_sound=False)

        self._client.send_message(message)
        self._log.info('Send displayed to %s, marker id: %s, mds id: %s',
                        contact.jid, marker_id, stanza_id)

        return stanza_id is not None

    @staticmethod
    def _determine_marker_id(contact: types.ChatContactT,
                             message_id: str,
                             stanza_id: str | None
                             ) -> str:

        if stanza_id is None:
            return message_id

        if isinstance(contact, GroupchatContact):
            return stanza_id
        return message_id

    def _get_contact_with_mtype(
        self, mtype: MessageType,
        jid: JID
    ) -> types.ChatContactT:

        if mtype in (MessageType.GROUPCHAT, MessageType.PM):
            contact = self._get_contact(jid, groupchat=True)
        else:
            contact = self._get_contact(jid.new_as_bare(), groupchat=False)
        assert not isinstance(contact, ResourceContact)
        return contact

    @staticmethod
    def _is_sending_marker_allowed(contact: types.ChatContactT) -> bool:
        if isinstance(contact, BareContact):
            if not contact.is_subscribed:
                return False

            return app.settings.get_contact_setting(
                contact.account, contact.jid, 'send_marker')

        return app.settings.get_group_chat_setting(
            contact.account, contact.jid.new_as_bare(), 'send_marker')


@dataclass
class DisplayedMarkerData:
    account: str
    jid: JID
    id: str
    timestamp: datetime
    occupant: mod.Occupant | None

    @classmethod
    def from_model(
        cls,
        account: str,
        marker: mod.DisplayedMarker
    ) -> DisplayedMarkerData:
        return cls(
            account=account,
            jid=marker.remote.jid,
            id=marker.id,
            timestamp=marker.timestamp,
            occupant=marker.occupant
        )
