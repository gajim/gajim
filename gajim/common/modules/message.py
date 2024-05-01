# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import datetime as dt
import time

import nbxmpp
import sqlalchemy.exc
from nbxmpp.namespaces import Namespace
from nbxmpp.protocol import JID
from nbxmpp.structs import MessageProperties
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import generate_id

from gajim.common import app
from gajim.common import types
from gajim.common.events import MessageAcknowledged
from gajim.common.events import MessageCorrected
from gajim.common.events import MessageError
from gajim.common.events import MessageReceived
from gajim.common.events import MessageSent
from gajim.common.events import RawMessageReceived
from gajim.common.helpers import get_uuid
from gajim.common.modules.base import BaseModule
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.util import get_chat_type_and_direction
from gajim.common.modules.util import get_eme_message
from gajim.common.storage.archive import models as mod
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageState
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.base import VALUE_MISSING
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

        if (properties.is_pubsub or
                properties.type.is_error or
                properties.type.is_normal):
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

        muc_data = None
        if properties.type.is_groupchat:
            muc_data = self._client.get_module('MUC').get_muc_data(
                properties.remote_jid)
            if muc_data is None:
                self._log.warning('Groupchat message from unknown MUC: %s',
                 properties.remote_jid)
                return

        m_type, direction = get_chat_type_and_direction(
            muc_data, self._client.get_own_jid(), properties)
        timestamp = self._get_message_timestamp(properties)
        remote_jid = properties.remote_jid
        assert remote_jid is not None

        user_delay_ts = None
        if properties.user_timestamp is not None:
            user_delay_ts = dt.datetime.fromtimestamp(
                properties.user_timestamp, tz=dt.timezone.utc)

        message_id = properties.id
        if message_id is None:
            self._log.warning('Received message without message id')
            self._log.warning(stanza)
            # TODO: Make Gajim not depend on a message_id being present
            message_id = get_uuid()
            self._log.warning('Generating id')

        stanza_id = self._get_stanza_id(properties)

        if (m_type != MessageType.GROUPCHAT and
                direction == ChatDirection.OUTGOING):
            if app.storage.archive.check_if_duplicate(
                    self._account, remote_jid, message_id):
                self._log.info('Duplicated message received: %s', message_id)
                return

        occupant = None
        if m_type == MessageType.GROUPCHAT:
            if direction == ChatDirection.OUTGOING:
                pk = app.storage.archive.update_pending_message(
                    self._account, remote_jid, properties.id, stanza_id)

                if pk is not None:
                    app.ged.raise_event(
                        MessageAcknowledged(account=self._account,
                                            jid=remote_jid,
                                            pk=pk))
                    return

        occupant = self._get_occupant_info(
            remote_jid, direction, timestamp, properties)

        assert properties.bodies is not None
        message_text = properties.bodies.get(None)
        oob_data = parse_oob(properties)

        encryption_data = None
        if properties.is_encrypted:
            enc_data = properties.encrypted.additional_data
            encryption_data = mod.Encryption(
                protocol=enc_data['name'],
                key=enc_data.get('fingerprint'),
                trust=enc_data['trust'],
            )

        elif properties.eme is not None:
            message_text = get_eme_message(properties.eme)

        if not message_text:
            self._log.debug('Received message without text')
            return

        securitylabel_data = None
        if properties.has_security_label:
            assert properties.security_label is not None
            displaymarking = properties.security_label.displaymarking
            if displaymarking is not None:
                securitylabel_data = mod.SecurityLabel(
                    account_=self._account,
                    remote_jid_=remote_jid,
                    label_hash=properties.security_label.get_label_hash(),
                    displaymarking=displaymarking.name,
                    fgcolor=displaymarking.fgcolor,
                    bgcolor=displaymarking.bgcolor,
                    updated_at=timestamp,
                )

        reply = None
        if properties.reply_data is not None:
            reply = mod.Reply(
                id=properties.reply_data.id,
                to=properties.reply_data.to
            )

        correction_id = None
        if properties.correction is not None:
            correction_id = properties.correction.id

        message_data = mod.Message(
            account_=self._account,
            remote_jid_=remote_jid,
            type=m_type,
            direction=direction,
            timestamp=timestamp,
            state=MessageState.ACKNOWLEDGED,
            resource=properties.jid.resource,
            text=message_text,
            id=message_id,
            stanza_id=stanza_id,
            user_delay_ts=user_delay_ts,
            correction_id=correction_id,
            encryption_=encryption_data,
            occupant_=occupant,
            oob=oob_data,
            security_label_=securitylabel_data,
            reply=reply,
            thread_id_=properties.thread,
        )

        try:
            pk = app.storage.archive.insert_object(
                message_data, ignore_on_conflict=False)
        except sqlalchemy.exc.IntegrityError:
            self._log.exception('Insertion Error')
            return

        if correction_id is not None:
            event = MessageCorrected(account=self._account,
                                     jid=remote_jid,
                                     corrected_message=message_data)
            app.ged.raise_event(event)
            return

        app.ged.raise_event(MessageReceived(account=self._account,
                                            jid=remote_jid,
                                            m_type=m_type,
                                            from_mam=properties.is_mam_message,
                                            pk=pk))

    def _get_message_timestamp(
        self,
        properties: MessageProperties
    ) -> dt.datetime:
        timestamp = properties.timestamp
        if properties.is_mam_message:
            timestamp = properties.mam.timestamp
        return dt.datetime.fromtimestamp(timestamp, tz=dt.timezone.utc)

    def _get_real_jid(self, properties: MessageProperties) -> JID | None:
        if properties.is_mam_message:
            if properties.muc_user is None:
                return None
            return properties.muc_user.jid

        if properties.jid.is_bare:
            return None

        occupant_contact = self._client.get_module('Contacts').get_contact(
            properties.jid, groupchat=True)
        assert isinstance(occupant_contact, GroupchatParticipant)
        real_jid = occupant_contact.real_jid
        if real_jid is None:
            return None
        return real_jid.new_as_bare()

    def _get_occupant_info(
        self,
        remote_jid: JID,
        direction: ChatDirection,
        timestamp: dt.datetime,
        properties: MessageProperties
    ) -> mod.Occupant | None:

        if not properties.type.is_groupchat:
            return None

        if direction == ChatDirection.OUTGOING:
            real_jid = self._client.get_own_jid().new_as_bare()
        else:
            real_jid = self._get_real_jid(properties)

        occupant_id = self._get_occupant_id(properties) or real_jid
        if occupant_id is None:
            return None

        resource = properties.jid.resource
        assert resource is not None

        return mod.Occupant(
            account_=self._account,
            remote_jid_=remote_jid,
            id=str(occupant_id),
            real_remote_jid_=real_jid or VALUE_MISSING,
            nickname=resource,
            updated_at=timestamp,
        )

    def _get_occupant_id(self, properties: MessageProperties) -> str | None:
        if not properties.type.is_groupchat:
            return None

        if properties.occupant_id is None:
            return None

        contact = self._client.get_module('Contacts').get_contact(
            properties.remote_jid, groupchat=True)
        if contact.supports(Namespace.OCCUPANT_ID):
            return properties.occupant_id
        return None

    def _message_error_received(self,
                                _con: types.xmppClient,
                                stanza: nbxmpp.Message,
                                properties: MessageProperties
                                ) -> None:

        remote_jid = properties.remote_jid
        assert remote_jid is not None
        message_id = properties.id
        if message_id is None:
            self._log.warning('Received error without message id')
            self._log.warning(stanza)
            return

        timestamp = self._get_message_timestamp(properties)

        error_data = mod.MessageError(
            account_=self._account,
            remote_jid_=remote_jid,
            message_id=message_id,
            by=properties.error.by,
            type=properties.error.type,
            text=properties.error.get_text() or None,
            condition=properties.error.condition,
            condition_text=properties.error.condition_data,
            timestamp=timestamp,
        )

        pk = app.storage.archive.insert_row(
            error_data, ignore_on_conflict=True)
        if pk == -1:
            self._log.warning(
                'Received error with already known message id: %s', message_id)
            return

        app.ged.raise_event(
            MessageError(account=self._account,
                         jid=remote_jid,
                         message_id=message_id,
                         error=properties.error))

    def _get_stanza_id(self,
                       properties: MessageProperties
                       ) -> str | None:

        if properties.is_mam_message:
            return properties.mam.id

        if not properties.stanza_ids:
            return None

        if properties.type.is_groupchat:
            archive = properties.remote_jid
            disco_info = app.storage.cache.get_last_disco_info(archive)
            if not disco_info.supports(Namespace.SID):
                return None

        else:
            if not self._con.get_module('MAM').available:
                return None

            archive = self._con.get_own_jid().new_as_bare()

        for stanza_id in properties.stanza_ids:
            # Check if message is from expected archive
            if archive.bare_match(stanza_id.by):
                return stanza_id.id
        return None

    def build_message_stanza(self, message: OutgoingMessage) -> nbxmpp.Message:
        own_jid = self._con.get_own_jid()

        stanza = nbxmpp.Message(to=message.jid,
                                body=message.get_text(),
                                typ=message.type_,
                                subject=message.subject)

        if message.correct_id:
            stanza.setTag('replace', attrs={'id': message.correct_id},
                          namespace=Namespace.CORRECT)

        # XEP-0461
        if message.reply_data is not None:
            stanza.setReply(str(message.reply_data.to),
                            message.reply_data.id,
                            message.reply_data.fallback_start,
                            message.reply_data.fallback_end)

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
            if message.has_text() and not message.is_groupchat:
                stanza.setReceiptRequest()

        # Mark Message as MUC PM
        if message.contact.is_pm_contact:
            stanza.setTag('x', namespace=Namespace.MUC_USER)

        # XEP-0085
        if message.chatstate is not None:
            stanza.setTag(message.chatstate, namespace=Namespace.CHATSTATES)
            if not message.has_text():
                stanza.setTag('no-store',
                              namespace=Namespace.MSG_HINTS)

        # XEP-0333
        if message.has_text():
            stanza.setMarkable()
        if message.marker:
            marker, id_ = message.marker
            stanza.setMarker(marker, id_)

        # Add other nodes
        if message.nodes is not None:
            for node in message.nodes:
                stanza.addChild(node=node)

        return stanza

    def send_message(self, message: OutgoingMessage) -> None:
        if not message.has_text():
            raise ValueError('Trying to send message without text')

        direction = ChatDirection.OUTGOING
        remote_jid = message.jid

        timestamp = dt.datetime.fromtimestamp(
            message.timestamp, tz=dt.timezone.utc)
        m_type = message.message_type
        assert message.message_id is not None

        occupant = None
        resource = self._client.get_bound_jid().resource
        state = MessageState.ACKNOWLEDGED

        if m_type in (MessageType.GROUPCHAT, MessageType.PM):
            # PM is a full jid, so convert to bare
            muc_jid = remote_jid.new_as_bare()
            muc_data = self._client.get_module('MUC').get_muc_data(muc_jid)
            if muc_data is None:
                self._log.warning('Trying to send message to unknown MUC: %s',
                                  muc_jid)
                return

            resource = muc_data.nick
            real_jid = self._client.get_own_jid().new_as_bare()
            occupant_id = muc_data.occupant_id or real_jid

            occupant = mod.Occupant(
                account_=self._account,
                remote_jid_=remote_jid,
                id=str(occupant_id),
                real_remote_jid_=real_jid,
                nickname=resource,
                updated_at=timestamp,
            )

            if m_type == MessageType.GROUPCHAT:
                state = MessageState.PENDING

        encryption_data = None
        if message.is_encrypted:
            enc_data = message.additional_data['encrypted']
            encryption_data = mod.Encryption(
                protocol=enc_data['name'],
                key='Unknown',
                trust=enc_data['trust'],
            )

        securitylabel_data = None
        if message.label is not None:
            displaymarking = message.label.displaymarking
            if displaymarking is not None:
                securitylabel_data = mod.SecurityLabel(
                    account_=self._account,
                    remote_jid_=remote_jid,
                    label_hash=message.label.get_label_hash(),
                    displaymarking=displaymarking.name,
                    fgcolor=displaymarking.fgcolor,
                    bgcolor=displaymarking.bgcolor,
                    updated_at=timestamp,
                )

        reply = None
        if message.reply_data is not None:
            reply = mod.Reply(
                id=message.reply_data.id,
                to=message.reply_data.to
            )

        oob_data: list[mod.OOB] = []
        if message.oob_url is not None:
            oob_data.append(mod.OOB(url=message.oob_url, description=None))

        message_data = mod.Message(
            account_=self._account,
            remote_jid_=remote_jid,
            type=m_type,
            direction=direction,
            timestamp=timestamp,
            state=state,
            resource=resource,
            text=message.get_text(with_fallback=False),
            id=message.message_id,
            stanza_id=None,
            user_delay_ts=None,
            correction_id=message.correct_id,
            encryption_=encryption_data,
            oob=oob_data,
            reply=reply,
            security_label_=securitylabel_data,
            occupant_=occupant,
        )


        pk = app.storage.archive.insert_object(message_data)
        if pk == -1:
            return

        if message.correct_id is not None:
            # TODO: Reset Chat Markers on Correction
            event = MessageCorrected(account=self._account,
                                     jid=message.jid,
                                     corrected_message=message_data)
            app.ged.raise_event(event)
            return

        app.ged.raise_event(
            MessageSent(jid=message.jid,
                        account=message.account,
                        pk=pk,
                        play_sound=message.play_sound))
