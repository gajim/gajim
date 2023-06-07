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

# Message handler

from __future__ import annotations

from typing import Any

import time

import nbxmpp
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import generate_id

from gajim.common import app
from gajim.common import types
from gajim.common.const import KindConstant
from gajim.common.events import GcMessageReceived
from gajim.common.events import MessageError
from gajim.common.events import MessageReceived
from gajim.common.events import RawMessageReceived
from gajim.common.helpers import AdditionalDataDict
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.misc import parse_xhtml
from gajim.common.modules.util import check_if_message_correction
from gajim.common.modules.util import check_if_message_retraction
from gajim.common.modules.util import get_eme_message
from gajim.common.structs import OutgoingMessage


class Message(BaseModule):
    def __init__(self, con: types.Client) -> None:
        BaseModule.__init__(self, con)

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._check_if_unknown_contact,
                          priority=41),
            StanzaHandler(name='message',
                          callback=self._message_received,
                          priority=50),
            StanzaHandler(name='message',
                          typ='error',
                          callback=self._message_error_received,
                          priority=50),
        ]

        # XEPs for which this message module should not be executed
        self._message_namespaces = {Namespace.ROSTERX, Namespace.IBB}

    def _check_if_unknown_contact(self,
                                  _con: types.xmppClient,
                                  stanza: nbxmpp.Message,
                                  properties: MessageProperties
                                  ) -> None:
        if (properties.type.is_groupchat or
                properties.is_muc_pm or
                properties.is_self_message or
                properties.is_mam_message):
            return

        if self._con.get_own_jid().domain == str(properties.jid):
            # Server message
            return

        if not app.settings.get_account_setting(self._account,
                                                'ignore_unknown_contacts'):
            return

        jid = properties.jid.bare
        if self._con.get_module('Roster').get_item(jid) is None:
            self._log.warning('Ignore message from unknown contact: %s', jid)
            self._log.warning(stanza)
            raise nbxmpp.NodeProcessed

    def _message_received(self,
                          _con: types.xmppClient,
                          stanza: nbxmpp.Message,
                          properties: MessageProperties
                          ) -> None:
        if (properties.is_mam_message or
                properties.is_pubsub or
                properties.type.is_error):
            return
        # Check if a child of the message contains any
        # namespaces that we handle in other modules.
        # nbxmpp executes less common handlers last
        if self._message_namespaces & set(stanza.getProperties()):
            return

        self._log.info('Received from %s', stanza.getFrom())

        app.ged.raise_event(RawMessageReceived(
            conn=self._con,
            stanza=stanza,
            account=self._account))

        if properties.is_carbon_message and properties.carbon.is_sent:
            # Ugly, we treat the from attr as the remote jid,
            # to make that work with sent carbons we have to do this.
            # TODO: Check where in Gajim and plugins we depend on that behavior
            stanza.setFrom(stanza.getTo())

        from_ = stanza.getFrom()
        fjid = str(from_)
        jid = from_.bare
        resource = from_.resource

        type_ = properties.type

        stanza_id, message_id = self._get_unique_id(properties)

        if (properties.is_self_message or properties.is_muc_pm):
            archive_jid = self._con.get_own_jid().bare
            if app.storage.archive.find_stanza_id(
                    self._account,
                    archive_jid,
                    stanza_id,
                    message_id,
                    properties.type.is_groupchat):
                return

        msgtxt = properties.body

        additional_data = AdditionalDataDict()

        if properties.has_user_delay:
            additional_data.set_value(
                'gajim', 'user_timestamp', properties.user_timestamp)

        parse_oob(properties, additional_data)
        parse_xhtml(properties, additional_data)

        if properties.is_encrypted:
            additional_data['encrypted'] = properties.encrypted.additional_data
        else:
            if properties.eme is not None:
                msgtxt = get_eme_message(properties.eme)

        displaymarking = None
        if properties.has_security_label:
            displaymarking = properties.security_label.displaymarking

        event_attr: dict[str, Any] = {
            'conn': self._con,
            'stanza': stanza,
            'account': self._account,
            'additional_data': additional_data,
            'fjid': fjid,
            'jid': from_ if properties.is_muc_pm else from_.new_as_bare(),
            'resource': resource,
            'stanza_id': stanza_id,
            'unique_id': stanza_id or message_id,
            'msgtxt': msgtxt,
            'delayed': properties.user_timestamp is not None,
            'msg_log_id': None,
            'displaymarking': displaymarking,
            'properties': properties,
        }

        if type_.is_groupchat:
            kind = KindConstant.GC_MSG
        elif properties.is_sent_carbon:
            kind = KindConstant.CHAT_MSG_SENT
        else:
            kind = KindConstant.CHAT_MSG_RECV

        if check_if_message_correction(properties,
                                       self._account,
                                       from_,
                                       msgtxt,
                                       kind,
                                       properties.timestamp,
                                       self._log):
            return

        if check_if_message_retraction(properties,
                                       self._account,
                                       from_,
                                       kind,
                                       self._log):
            return

        if type_.is_groupchat:
            if not msgtxt:
                return

            occupant_id = None
            group_contact = self._client.get_module('Contacts').get_contact(
                jid, groupchat=True)
            if group_contact.supports(Namespace.OCCUPANT_ID):
                # Only store occupant-id if MUC announces support
                occupant_id = properties.occupant_id

            real_jid = self._get_real_jid(properties)

            event_attr.update({
                'room_jid': jid,
                'real_jid': real_jid,
                'occupant_id': occupant_id,
            })

            event = GcMessageReceived(**event_attr)

            # TODO: Some plugins modify msgtxt in the GUI event
            msg_log_id = self._log_muc_message(event)
            event.msg_log_id = msg_log_id
            app.ged.raise_event(event)
            return

        event = MessageReceived(**event_attr)
        if not msgtxt:
            app.ged.raise_event(event)
            return

        msg_log_id = app.storage.archive.insert_into_logs(
            self._account,
            fjid if properties.is_muc_pm else jid,
            properties.timestamp,
            kind,
            message=msgtxt,
            subject=properties.subject,
            additional_data=additional_data,
            stanza_id=stanza_id or message_id,
            message_id=properties.id)

        event.msg_log_id = msg_log_id
        app.ged.raise_event(event)

    def _message_error_received(self,
                                _con: types.xmppClient,
                                _stanza: nbxmpp.Message,
                                properties: MessageProperties
                                ) -> None:
        jid = properties.jid
        if not properties.is_muc_pm:
            jid = jid.new_as_bare()

        self._log.info(properties.error)

        app.storage.archive.set_message_error(
            app.get_jid_from_account(self._account),
            jid,
            properties.id,
            properties.error)

        app.ged.raise_event(
            MessageError(account=self._account,
                         jid=jid,
                         room_jid=jid,
                         message_id=properties.id,
                         error=properties.error))

    def _log_muc_message(self, event: GcMessageReceived) -> int | None:
        self._check_for_mam_compliance(event.room_jid, event.stanza_id)

        if event.msgtxt and event.properties.muc_nickname:
            msg_log_id = app.storage.archive.insert_into_logs(
                self._account,
                event.jid,
                event.properties.timestamp,
                KindConstant.GC_MSG,
                message=event.msgtxt,
                contact_name=event.properties.muc_nickname,
                additional_data=event.additional_data,
                stanza_id=event.stanza_id,
                message_id=event.properties.id,
                occupant_id=event.occupant_id,
                real_Jid=event.real_jid)
            return msg_log_id

        return None

    def _check_for_mam_compliance(self, room_jid: str, stanza_id: str) -> None:
        disco_info = app.storage.cache.get_last_disco_info(room_jid)
        if stanza_id is None and disco_info.mam_namespace == Namespace.MAM_2:
            self._log.warning('%s announces mam:2 without stanza-id', room_jid)

    def _get_real_jid(self, properties: MessageProperties) -> JID | None:
        if not properties.type.is_groupchat:
            return None

        if not properties.jid.is_full:
            return None

        participant = self._client.get_module('Contacts').get_contact(
                properties.jid, groupchat=True)
        assert isinstance(participant, GroupchatParticipant)
        return participant.real_jid

    def _get_unique_id(self,
                       properties: MessageProperties
                       ) -> tuple[str | None, str | None]:
        if properties.is_self_message:
            # Deduplicate self message with message-id
            return None, properties.id

        if not properties.stanza_ids:
            return None, None

        if properties.type.is_groupchat:
            disco_info = app.storage.cache.get_last_disco_info(
                properties.jid.bare)

            if disco_info.mam_namespace != Namespace.MAM_2:
                return None, None

            archive = properties.jid
        else:
            if not self._con.get_module('MAM').available:
                return None, None

            archive = self._con.get_own_jid()

        for stanza_id in properties.stanza_ids:
            if archive.bare_match(stanza_id.by):
                return stanza_id.id, None

        # stanza-id not added by the archive, ignore it.
        return None, None

    def build_message_stanza(self, message: OutgoingMessage) -> nbxmpp.Message:
        own_jid = self._con.get_own_jid()

        stanza = nbxmpp.Message(to=message.jid,
                                body=message.message,
                                typ=message.type_,
                                subject=message.subject,
                                xhtml=message.xhtml)

        if message.correct_id:
            stanza.setTag('replace', attrs={'id': message.correct_id},
                          namespace=Namespace.CORRECT)

        # XEP-0359
        message.message_id = generate_id()
        stanza.setID(message.message_id)
        stanza.setOriginID(message.message_id)

        if message.label:
            stanza.addChild(node=message.label.to_node())

        # XEP-0172: user_nickname
        if message.user_nick:
            stanza.setTag('nick', namespace=Namespace.NICK).setData(
                message.user_nick)

        # XEP-0203
        # TODO: Seems delayed is not set anywhere
        if message.delayed:
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                      time.gmtime(message.delayed))
            stanza.addChild('delay',
                            namespace=Namespace.DELAY2,
                            attrs={'from': str(own_jid), 'stamp': timestamp})

        # XEP-0224
        if message.attention:
            stanza.setTag('attention', namespace=Namespace.ATTENTION)

        # XEP-0066
        if message.oob_url is not None:
            oob = stanza.addChild('x', namespace=Namespace.X_OOB)
            oob.addChild('url').setData(message.oob_url)

        # XEP-0184
        if not own_jid.bare_match(message.jid):
            if message.message and not message.is_groupchat:
                stanza.setReceiptRequest()

        # Mark Message as MUC PM
        if message.contact.is_pm_contact:
            stanza.setTag('x', namespace=Namespace.MUC_USER)

        # XEP-0085
        if message.chatstate is not None:
            stanza.setTag(message.chatstate, namespace=Namespace.CHATSTATES)
            if not message.message:
                stanza.setTag('no-store',
                              namespace=Namespace.MSG_HINTS)

        # XEP-0333
        if message.message:
            stanza.setMarkable()
        if message.marker:
            marker, id_ = message.marker
            stanza.setMarker(marker, id_)

        # Add other nodes
        if message.nodes is not None:
            for node in message.nodes:
                stanza.addChild(node=node)

        return stanza

    def log_message(self, message: OutgoingMessage) -> int | None:
        if not message.is_loggable:
            return None

        if message.message is None:
            return None

        if message.correct_id is not None:
            app.storage.archive.try_message_correction(
                self._account,
                message.jid,
                None,
                message.message,
                message.correct_id,
                KindConstant.CHAT_MSG_SENT,
                message.timestamp)
            return None

        msg_log_id = app.storage.archive.insert_into_logs(
            self._account,
            message.jid,
            message.timestamp,
            message.kind,
            message=message.message,
            subject=message.subject,
            additional_data=message.additional_data,
            message_id=message.message_id,
            stanza_id=message.message_id)
        return msg_log_id
