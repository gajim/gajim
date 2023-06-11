# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

# Chat Markers (XEP-0333)

from __future__ import annotations

from typing import Any

import datetime as dt

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import DisplayedReceived
from gajim.common.events import ReadStateSync
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.storage.archive import models as mod
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

    def _process_chat_marker(self,
                             _client: types.xmppClient,
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
            assert properties.muc_jid is not None
            contact = self._client.get_module('Contacts').get_contact(
                properties.muc_jid,
                groupchat=True)
            assert isinstance(contact, GroupchatContact)
            if not contact.is_joined:
                self._log.warning('Received chat marker while not joined')
                return

            if properties.muc_nickname != contact.nickname:
                return

            self._raise_read_state_sync(jid, properties.marker.id)
            return

        if (properties.is_sent_carbon or
                (properties.is_mam_message and properties.is_from_us())):
            self._raise_read_state_sync(jid, properties.marker.id)
            return

        self._raise_event('displayed-received', properties)

    def _raise_read_state_sync(self, jid: JID, marker_id: str) -> None:
        self._log.info('Read state sync: %s - %s', jid, marker_id)
        app.ged.raise_event(
            ReadStateSync(account=self._account,
                          jid=jid,
                          marker_id=marker_id))

    def _raise_event(self, name: str, properties: Any) -> None:
        self._log.info('%s: %s %s',
                       name,
                       properties.jid,
                       properties.marker.id)

        if not properties.is_muc_pm and not properties.type.is_groupchat:
            if properties.is_mam_message:
                timestamp = properties.mam.timestamp
            else:
                timestamp = properties.timestamp

            timestamp = dt.datetime.fromtimestamp(
                timestamp, dt.timezone.utc)

            marker_data = mod.DisplayedMarker(
                account_=self._account,
                remote_jid_=properties.remote_jid,
                occupant_=None,
                id=properties.marker.id,
                timestamp=timestamp)
            app.storage.archive.insert_object(marker_data)

        app.ged.raise_event(
            DisplayedReceived(account=self._account,
                              jid=properties.remote_jid,
                              properties=properties,
                              type=properties.type,
                              is_muc_pm=properties.is_muc_pm,
                              marker_id=properties.marker.id))

    def _send_marker(self,
                     contact: types.ChatContactT,
                     marker: str,
                     id_: str) -> None:

        typ = 'groupchat' if contact.is_groupchat else 'chat'

        message = OutgoingMessage(account=self._account,
                                  contact=contact,
                                  text=None,
                                  type_=typ,
                                  marker=(marker, id_),
                                  play_sound=False)

        self._client.send_message(message)
        self._log.info('Send %s: %s', marker, contact.jid)

    def send_displayed_marker(self,
                              contact: types.ChatContactT,
                              message_id: str,
                              stanza_id: str | None) -> None:

        if not self._is_sending_marker_allowed(contact):
            return

        marker_id = self._determine_marker_id(contact, message_id, stanza_id)
        self._send_marker(contact, 'displayed', marker_id)

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

    @staticmethod
    def _is_sending_marker_allowed(contact: types.ChatContactT) -> bool:
        if isinstance(contact, BareContact):
            return app.settings.get_contact_setting(
                contact.account, contact.jid, 'send_marker')

        return app.settings.get_group_chat_setting(
            contact.account, contact.jid.new_as_bare(), 'send_marker')
