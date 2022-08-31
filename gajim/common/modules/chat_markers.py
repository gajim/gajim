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

# Chat Markers (XEP-0333)

from __future__ import annotations

from typing import Any

from nbxmpp.namespaces import Namespace
from nbxmpp.structs import StanzaHandler

from gajim.common import app
from gajim.common import types
from gajim.common.events import DisplayedReceived
from gajim.common.events import ReadStateSync
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
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
                             properties: Any) -> None:

        if not properties.is_marker or not properties.marker.is_displayed:
            return

        if properties.type.is_error:
            return

        if properties.type.is_groupchat:
            contact = self._client.get_module('Contacts').get_contact(
                properties.muc_jid,
                groupchat=True)
            if not contact.is_joined:
                self._log.warning('Received chat marker while not joined')
                return

            if properties.muc_nickname != contact.nickname:
                return

            self._raise_event('read-state-sync', properties)
            return

        if properties.is_carbon_message and properties.carbon.is_sent:
            self._raise_event('read-state-sync', properties)
            return

        if properties.is_mam_message:
            if properties.from_.bare_match(self._client.get_own_jid()):
                self._raise_event('read-state-sync', properties)
                return

        self._raise_event('displayed-received', properties)

    def _raise_event(self, name: str, properties: Any) -> None:
        self._log.info('%s: %s %s',
                       name,
                       properties.jid,
                       properties.marker.id)

        jid = properties.jid
        if not properties.is_muc_pm and not properties.type.is_groupchat:
            jid = properties.jid.bare

        app.storage.archive.set_marker(
            app.get_jid_from_account(self._account),
            jid,
            properties.marker.id,
            'displayed')

        if name == 'read-state-sync':
            event_class = ReadStateSync
        elif name == 'displayed-received':
            event_class = DisplayedReceived
        else:
            raise ValueError

        app.ged.raise_event(
            event_class(account=self._account,
                        jid=jid,
                        properties=properties,
                        type=properties.type,
                        is_muc_pm=properties.is_muc_pm,
                        marker_id=properties.marker.id))

    def _send_marker(self,
                     contact: types.ChatContactT,
                     marker: str,
                     id_: str) -> None:

        if isinstance(contact, (GroupchatContact, GroupchatParticipant)):
            typ = 'groupchat'
            if not app.settings.get_group_chat_setting(
                    self._account, contact.jid.new_as_bare(), 'send_marker'):
                return
        else:
            typ = 'chat'
            if not app.settings.get_contact_setting(
                    self._account, contact.jid, 'send_marker'):
                return

        message = OutgoingMessage(account=self._account,
                                  contact=contact,
                                  message=None,
                                  type_=typ,
                                  marker=(marker, id_),
                                  play_sound=False)
        self._client.send_message(message)
        self._log.info('Send %s: %s', marker, contact.jid)

    def send_displayed_marker(self,
                              contact: types.ChatContactT,
                              id_: str) -> None:

        self._send_marker(contact, 'displayed', id_)
