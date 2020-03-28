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

import nbxmpp
from nbxmpp.structs import StanzaHandler
from nbxmpp.util import generate_id

from gajim.common import app
from gajim.common.nec import NetworkEvent
from gajim.common.helpers import AdditionalDataDict
from gajim.common.const import KindConstant
from gajim.common.modules.base import BaseModule
from gajim.common.modules.util import get_eme_message
from gajim.common.modules.security_labels import parse_securitylabel
from gajim.common.modules.misc import parse_correction
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.misc import parse_xhtml


class Message(BaseModule):
    def __init__(self, con):
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
        self._message_namespaces = set([nbxmpp.NS_ROSTERX,
                                        nbxmpp.NS_IBB])

    def _check_if_unknown_contact(self, _con, stanza, properties):
        if (properties.type.is_groupchat or
                properties.is_muc_pm or
                properties.is_self_message or
                properties.is_mam_message):
            return

        if self._con.get_own_jid().getDomain() == str(properties.jid):
            # Server message
            return

        if not app.config.get_per('accounts',
                                  self._account,
                                  'ignore_unknown_contacts'):
            return

        jid = properties.jid.getBare()
        if self._con.get_module('Roster').get_item(jid) is None:
            self._log.warning('Ignore message from unknown contact: %s', jid)
            self._log.warning(stanza)
            raise nbxmpp.NodeProcessed

    def _message_received(self, _con, stanza, properties):
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

        app.nec.push_incoming_event(NetworkEvent(
            'raw-message-received',
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
        jid = from_.getBare()
        resource = from_.getResource()

        type_ = properties.type

        stanza_id, message_id = self._get_unique_id(properties)

        if properties.type.is_groupchat and properties.has_server_delay:
            # Only for XEP-0045 MUC History
            # Dont check for message text because the message could be encrypted
            if app.logger.deduplicate_muc_message(self._account,
                                                  properties.jid.getBare(),
                                                  properties.jid.getResource(),
                                                  properties.timestamp,
                                                  properties.id):
                raise nbxmpp.NodeProcessed

        if (properties.is_self_message or properties.is_muc_pm):
            archive_jid = self._con.get_own_jid().getStripped()
            if app.logger.find_stanza_id(self._account,
                                         archive_jid,
                                         stanza_id,
                                         message_id,
                                         properties.type.is_groupchat):
                return

        msgtxt = properties.body

        # TODO: remove all control UI stuff
        gc_control = app.interface.msg_win_mgr.get_gc_control(
            jid, self._account)
        if not gc_control:
            minimized = app.interface.minimized_controls[self._account]
            gc_control = minimized.get(jid)
        session = None
        if not properties.type.is_groupchat:
            if properties.is_muc_pm and properties.type.is_error:
                session = self._con.find_session(fjid, properties.thread)
                if not session:
                    session = self._con.get_latest_session(fjid)
                if not session:
                    session = self._con.make_new_session(
                        fjid, properties.thread, type_='pm')
            else:
                session = self._con.get_or_create_session(
                    fjid, properties.thread)

            if properties.thread and not session.received_thread_id:
                session.received_thread_id = True

            session.last_receive = time.time()

        additional_data = AdditionalDataDict()

        if properties.has_user_delay:
            additional_data.set_value(
                'gajim', 'user_timestamp', properties.user_timestamp)

        parse_oob(properties, additional_data)
        parse_xhtml(properties, additional_data)

        app.nec.push_incoming_event(NetworkEvent('update-client-info',
                                                 account=self._account,
                                                 jid=jid,
                                                 resource=resource))

        if properties.is_encrypted:
            additional_data['encrypted'] = properties.encrypted.additional_data
        else:
            if properties.eme is not None:
                msgtxt = get_eme_message(properties.eme)

        event_attr = {
            'conn': self._con,
            'stanza': stanza,
            'account': self._account,
            'additional_data': additional_data,
            'fjid': fjid,
            'jid': jid,
            'resource': resource,
            'stanza_id': stanza_id,
            'unique_id': stanza_id or message_id,
            'correct_id': parse_correction(properties),
            'msgtxt': msgtxt,
            'session': session,
            'delayed': properties.user_timestamp is not None,
            'gc_control': gc_control,
            'popup': False,
            'msg_log_id': None,
            'displaymarking': parse_securitylabel(stanza),
            'properties': properties,
        }

        if type_.is_groupchat:
            if not msgtxt:
                return

            event_attr.update({
                'room_jid': jid,
            })
            event = NetworkEvent('gc-message-received', **event_attr)
            app.nec.push_incoming_event(event)
            # TODO: Some plugins modify msgtxt in the GUI event
            self._log_muc_message(event)
            return

        app.nec.push_incoming_event(
            NetworkEvent('decrypted-message-received', **event_attr))

    def _message_error_received(self, _con, _stanza, properties):
        jid = properties.jid.copy()
        if not properties.is_muc_pm:
            jid.setBare()

        self._log.info(properties.error)

        app.logger.set_message_error(app.get_jid_from_account(self._account),
                                     jid,
                                     properties.id,
                                     properties.error)

        app.nec.push_incoming_event(
            NetworkEvent('message-error',
                         account=self._account,
                         jid=jid,
                         room_jid=jid,
                         message_id=properties.id,
                         error=properties.error))

    def _log_muc_message(self, event):
        self._check_for_mam_compliance(event.room_jid, event.stanza_id)

        if (app.config.should_log(self._account, event.jid) and
                event.msgtxt and event.properties.muc_nickname):
            # if not event.nick, it means message comes from room itself
            # usually it hold description and can be send at each connection
            # so don't store it in logs
            app.logger.insert_into_logs(
                self._account,
                event.jid,
                event.properties.timestamp,
                KindConstant.GC_MSG,
                message=event.msgtxt,
                contact_name=event.properties.muc_nickname,
                additional_data=event.additional_data,
                stanza_id=event.stanza_id,
                message_id=event.properties.id)

    def _check_for_mam_compliance(self, room_jid, stanza_id):
        disco_info = app.logger.get_last_disco_info(room_jid)
        if stanza_id is None and disco_info.mam_namespace == nbxmpp.NS_MAM_2:
            self._log.warning('%s announces mam:2 without stanza-id', room_jid)

    def _get_unique_id(self, properties):
        if properties.is_self_message:
            # Deduplicate self message with message-id
            return None, properties.id

        if properties.stanza_id is None:
            return None, None

        if properties.type.is_groupchat:
            disco_info = app.logger.get_last_disco_info(
                properties.jid.getBare())

            if disco_info.mam_namespace != nbxmpp.NS_MAM_2:
                return None, None

            archive = properties.jid
        else:
            if not self._con.get_module('MAM').available:
                return None, None

            archive = self._con.get_own_jid()

        if archive.bareMatch(properties.stanza_id.by):
            return properties.stanza_id.id, None
        # stanza-id not added by the archive, ignore it.
        return None, None

    def build_message_stanza(self, message):
        own_jid = self._con.get_own_jid()

        stanza = nbxmpp.Message(to=message.jid,
                                body=message.message,
                                typ=message.type_,
                                subject=message.subject,
                                xhtml=message.xhtml)

        if message.correct_id:
            stanza.setTag('replace', attrs={'id': message.correct_id},
                          namespace=nbxmpp.NS_CORRECT)

        # XEP-0359
        message.message_id = generate_id()
        stanza.setID(message.message_id)
        stanza.setOriginID(message.message_id)

        if message.label:
            stanza.addChild(node=message.label)

        # XEP-0172: user_nickname
        if message.user_nick:
            stanza.setTag('nick', namespace=nbxmpp.NS_NICK).setData(
                message.user_nick)

        # XEP-0203
        # TODO: Seems delayed is not set anywhere
        if message.delayed:
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                      time.gmtime(message.delayed))
            stanza.addChild('delay',
                            namespace=nbxmpp.NS_DELAY2,
                            attrs={'from': str(own_jid), 'stamp': timestamp})

        # XEP-0224
        if message.attention:
            stanza.setTag('attention', namespace=nbxmpp.NS_ATTENTION)

        # XEP-0066
        if message.oob_url is not None:
            oob = stanza.addChild('x', namespace=nbxmpp.NS_X_OOB)
            oob.addChild('url').setData(message.oob_url)

        # XEP-0184
        if not own_jid.bareMatch(message.jid):
            if message.message and not message.is_groupchat:
                stanza.setReceiptRequest()

        # Mark Message as MUC PM
        if message.contact.is_pm_contact:
            stanza.setTag('x', namespace=nbxmpp.NS_MUC_USER)

        # XEP-0085
        if message.chatstate is not None:
            stanza.setTag(message.chatstate, namespace=nbxmpp.NS_CHATSTATES)
            if not message.message:
                stanza.setTag('no-store',
                              namespace=nbxmpp.NS_MSG_HINTS)

        return stanza

    def log_message(self, message):
        if not message.is_loggable:
            return

        if not app.config.should_log(self._account, message.jid):
            return

        if message.message is None:
            return

        app.logger.insert_into_logs(self._account,
                                    message.jid,
                                    message.timestamp,
                                    message.kind,
                                    message=message.message,
                                    subject=message.subject,
                                    additional_data=message.additional_data,
                                    message_id=message.message_id,
                                    stanza_id=message.message_id)


def get_instance(*args, **kwargs):
    return Message(*args, **kwargs), 'Message'
