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

import time
import logging

import nbxmpp
from nbxmpp.structs import StanzaHandler
from nbxmpp.const import MessageType

from gajim.common import app
from gajim.common import caps_cache
from gajim.common.i18n import _
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.nec import NetworkEvent
from gajim.common.helpers import AdditionalDataDict
from gajim.common.const import KindConstant
from gajim.common.modules.util import get_eme_message
from gajim.common.modules.security_labels import parse_securitylabel
from gajim.common.modules.user_nickname import parse_nickname
from gajim.common.modules.misc import parse_delay
from gajim.common.modules.misc import parse_correction
from gajim.common.modules.misc import parse_attention
from gajim.common.modules.misc import parse_form
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.misc import parse_xhtml
from gajim.common.connection_handlers_events import MessageErrorEvent


log = logging.getLogger('gajim.c.m.message')


class Message:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [
            StanzaHandler(name='message',
                          callback=self._message_received,
                          priority=50),
        ]

        # XEPs for which this message module should not be executed
        self._message_namespaces = set([nbxmpp.NS_ROSTERX,
                                        nbxmpp.NS_IBB])

    def _message_received(self, _con, stanza, properties):
        if properties.is_mam_message or properties.is_pubsub:
            return
        # Check if a child of the message contains any
        # namespaces that we handle in other modules.
        # nbxmpp executes less common handlers last
        if self._message_namespaces & set(stanza.getProperties()):
            return

        log.info('Received from %s', stanza.getFrom())

        app.nec.push_incoming_event(NetworkEvent(
            'raw-message-received',
            conn=self._con,
            stanza=stanza,
            account=self._account))

        forwarded = properties.carbon_type is not None
        sent = properties.carbon_type == 'sent'
        if sent:
            # Ugly, we treat the from attr as the remote jid,
            # to make that work with sent carbons we have to do this.
            # TODO: Check where in Gajim and plugins we depend on that behavior
            stanza.setFrom(stanza.getTo())

        from_ = stanza.getFrom()
        fjid = str(from_)
        jid = from_.getBare()
        resource = from_.getResource()

        type_ = properties.type

        # Check for duplicates
        stanza_id, message_id = self._get_unique_id(properties)

        # Check groupchat messages for duplicates,
        # We do this because of MUC History messages
        if (properties.type.is_groupchat or
            properties.is_self_message or
                properties.is_muc_pm):
            if properties.type.is_groupchat:
                archive_jid = stanza.getFrom().getStripped()
            else:
                archive_jid = self._con.get_own_jid().getStripped()
            if app.logger.find_stanza_id(self._account,
                                         archive_jid,
                                         stanza_id,
                                         message_id,
                                         properties.type.is_groupchat):
                return

        thread_id = properties.thread
        msgtxt = properties.body

        # TODO: remove all control UI stuff
        gc_control = app.interface.msg_win_mgr.get_gc_control(
            jid, self._account)
        if not gc_control:
            minimized = app.interface.minimized_controls[self._account]
            gc_control = minimized.get(jid)

        if gc_control and jid == fjid:
            if properties.type.is_error:
                if msgtxt:
                    msgtxt = _('error while sending %(message)s ( %(error)s )') % {
                        'message': msgtxt, 'error': stanza.getErrorMsg()}
                else:
                    msgtxt = _('error: %s') % stanza.getErrorMsg()
                # TODO: why is this here?
                if stanza.getTag('html'):
                    stanza.delChild('html')
            type_ = MessageType.GROUPCHAT

        session = None
        if not properties.type.is_groupchat:
            if properties.is_muc_pm and properties.type.is_error:
                session = self._con.find_session(fjid, thread_id)
                if not session:
                    session = self._con.get_latest_session(fjid)
                if not session:
                    session = self._con.make_new_session(
                        fjid, thread_id, type_='pm')
            else:
                session = self._con.get_or_create_session(fjid, thread_id)

            if thread_id and not session.received_thread_id:
                session.received_thread_id = True

            session.last_receive = time.time()

        event_attr = {
            'conn': self._con,
            'stanza': stanza,
            'account': self._account,
            'id_': properties.id,
            'encrypted': False,
            'additional_data': AdditionalDataDict(),
            'forwarded': forwarded,
            'sent': sent,
            'fjid': fjid,
            'jid': jid,
            'resource': resource,
            'stanza_id': stanza_id,
            'unique_id': stanza_id or message_id,
            'message_id': properties.id,
            'mtype': type_.value,
            'msgtxt': msgtxt,
            'thread_id': thread_id,
            'session': session,
            'self_message': properties.is_self_message,
            'muc_pm': properties.is_muc_pm,
            'gc_control': gc_control
        }

        app.nec.push_incoming_event(NetworkEvent('update-client-info',
                                                 account=self._account,
                                                 jid=jid,
                                                 resource=resource))

        event = MessageReceivedEvent(None, **event_attr)
        app.nec.push_incoming_event(event)

        if properties.is_encrypted:
            event.additional_data['encrypted'] = properties.encrypted.additional_data
            self._on_message_decrypted(event)
        else:
            app.plugin_manager.extension_point(
                'decrypt', self._con, event, self._on_message_decrypted)
            if not event.encrypted:
                if properties.eme is not None:
                    event.msgtxt = get_eme_message(properties.eme)
                self._on_message_decrypted(event)

    def _on_message_decrypted(self, event):
        try:
            self._con.get_module('Receipts').delegate(event)
            self._con.get_module('Chatstate').delegate(event)
        except nbxmpp.NodeProcessed:
            return

        subject = event.stanza.getSubject()
        groupchat = event.mtype == 'groupchat'

        # Determine timestamps
        if groupchat:
            delay_jid = event.jid
        else:
            delay_jid = self._con.get_own_jid().getDomain()
        timestamp = parse_delay(event.stanza, from_=delay_jid)
        if timestamp is None:
            timestamp = time.time()

        user_timestamp = parse_delay(event.stanza,
                                     not_from=[delay_jid])

        if user_timestamp is not None:
            event.additional_data.set_value(
                'gajim', 'user_timestamp', user_timestamp)

        event_attr = {
            'popup': False,
            'msg_log_id': None,
            'subject': subject,
            'displaymarking': parse_securitylabel(event.stanza),
            'attention': parse_attention(event.stanza),
            'correct_id': parse_correction(event.stanza),
            'user_nick': '' if event.sent else parse_nickname(event.stanza),
            'form_node': parse_form(event.stanza),
            'xhtml': parse_xhtml(event.stanza),
            'timestamp': timestamp,
            'delayed': user_timestamp is not None,
        }
        parse_oob(event)

        for name, value in event_attr.items():
            setattr(event, name, value)

        if event.mtype == 'error':
            if not event.msgtxt:
                event.msgtxt = _('message')
            if event.gc_control:
                event.gc_control.print_conversation(event.msgtxt)
            else:
                self._log_error_message(event)
                error_msg = event.stanza.getErrorMsg() or event.msgtxt
                msgtxt = None if error_msg == event.msgtxt else event.msgtxt
                app.nec.push_incoming_event(
                    MessageErrorEvent(None,
                                      conn=self._con,
                                      fjid=event.fjid,
                                      error_code=event.stanza.getErrorCode(),
                                      error_msg=error_msg,
                                      msg=msgtxt,
                                      time_=event.timestamp,
                                      session=event.session,
                                      stanza=event.stanza))
            return

        if groupchat:
            if not event.msgtxt:
                return

            event.room_jid = event.jid
            event.nickname = event.resource
            event.xhtml_msgtxt = event.xhtml
            event.nick = event.resource or ''

            app.nec.push_incoming_event(NetworkEvent('gc-message-received',
                                                     **vars(event)))
            # TODO: Some plugins modify msgtxt in the GUI event
            self._log_muc_message(event)
            return

        app.nec.push_incoming_event(
            DecryptedMessageReceivedEvent(
                None, **vars(event)))

    def _log_error_message(self, event):
        error_msg = event.stanza.getErrorMsg() or event.msgtxt
        if app.config.should_log(self._account, event.jid):
            app.logger.insert_into_logs(self._account,
                                        event.jid,
                                        event.timestamp,
                                        KindConstant.ERROR,
                                        message=error_msg,
                                        subject=event.subject)

    def _log_muc_message(self, event):
        if event.mtype == 'error':
            return

        self._check_for_mam_compliance(event.room_jid, event.stanza_id)

        if (app.config.should_log(self._account, event.jid) and
                event.msgtxt and event.nick):
            # if not event.nick, it means message comes from room itself
            # usually it hold description and can be send at each connection
            # so don't store it in logs
            app.logger.insert_into_logs(self._account,
                                        event.jid,
                                        event.timestamp,
                                        KindConstant.GC_MSG,
                                        message=event.msgtxt,
                                        contact_name=event.nick,
                                        additional_data=event.additional_data,
                                        stanza_id=event.stanza_id,
                                        message_id=event.message_id)
            app.logger.set_room_last_message_time(event.room_jid, event.timestamp)
            self._con.get_module('MAM').save_archive_id(
                event.room_jid, event.stanza_id, event.timestamp)

    @staticmethod
    def _check_for_mam_compliance(room_jid, stanza_id):
        namespace = caps_cache.muc_caps_cache.get_mam_namespace(room_jid)
        if stanza_id is None and namespace == nbxmpp.NS_MAM_2:
            log.warning('%s announces mam:2 without stanza-id', room_jid)

    def _get_unique_id(self, properties):
        if properties.is_self_message:
            # Deduplicate self message with message-id
            return None, properties.id

        if properties.stanza_id.by is None:
            # We can not verify who sent this stanza-id, ignore it.
            return None, None

        if properties.type.is_groupchat:
            namespace = caps_cache.muc_caps_cache.get_mam_namespace(
                properties.jid.getBare())
            archive = properties.jid
        else:
            namespace = self._con.get_module('MAM').archiving_namespace
            archive = self._con.get_own_jid()

        if namespace != nbxmpp.NS_MAM_2:
            # Only mam:2 ensures valid stanza-id
            return None, None

        if archive.bareMatch(properties.stanza_id.by):
            return properties.stanza_id.id, None
        # stanza-id not added by the archive, ignore it.
        return None, None


class MessageReceivedEvent(NetworkIncomingEvent):
    name = 'message-received'


class DecryptedMessageReceivedEvent(NetworkIncomingEvent):
    name = 'decrypted-message-received'


def get_instance(*args, **kwargs):
    return Message(*args, **kwargs), 'Message'
