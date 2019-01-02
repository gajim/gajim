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

from gajim.common import app
from gajim.common import helpers
from gajim.common.i18n import _
from gajim.common.nec import NetworkIncomingEvent
from gajim.common.nec import NetworkEvent
from gajim.common.helpers import AdditionalDataDict
from gajim.common.modules.security_labels import parse_securitylabel
from gajim.common.modules.user_nickname import parse_nickname
from gajim.common.modules.misc import parse_delay
from gajim.common.modules.misc import parse_eme
from gajim.common.modules.misc import parse_correction
from gajim.common.modules.misc import parse_attention
from gajim.common.modules.misc import parse_form
from gajim.common.modules.misc import parse_oob
from gajim.common.modules.misc import parse_xhtml
from gajim.common.modules.util import is_self_message
from gajim.common.modules.util import is_muc_pm


log = logging.getLogger('gajim.c.m.message')


class Message:
    def __init__(self, con):
        self._con = con
        self._account = con.name

        self.handlers = [('message', self._message_received)]

        # XEPs for which this message module should not be executed
        self._message_namespaces = set([nbxmpp.NS_PUBSUB_EVENT,
                                        nbxmpp.NS_ROSTERX,
                                        nbxmpp.NS_MAM_1,
                                        nbxmpp.NS_MAM_2,
                                        nbxmpp.NS_CONFERENCE,
                                        nbxmpp.NS_IBB,
                                        nbxmpp.NS_CAPTCHA,])

    def _message_received(self, _con, stanza, properties):
        # Check if a child of the message contains any
        # namespaces that we handle in other modules.
        # nbxmpp executes less common handlers last
        if self._message_namespaces & set(stanza.getProperties()):
            return

        muc_user = stanza.getTag('x', namespace=nbxmpp.NS_MUC_USER)
        if muc_user is not None and (stanza.getType() != 'error'):
            if muc_user.getChildren():
                # Not a PM, handled by MUC module
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
            stanza.setFrom(stanza.getTo().getBare())

        from_ = stanza.getFrom()
        type_ = stanza.getType()
        if type_ is None:
            type_ = 'normal'

        self_message = is_self_message(stanza, type_ == 'groupchat')
        muc_pm = is_muc_pm(stanza, from_, type_ == 'groupchat')

        id_ = stanza.getID()

        fjid = None
        if from_ is not None:
            try:
                fjid = helpers.parse_jid(str(from_))
            except helpers.InvalidFormat:
                log.warning('Invalid JID: %s, ignoring it',
                            stanza.getFrom())
                return

        jid, resource = app.get_room_and_nick_from_fjid(fjid)

        # Check for duplicates
        stanza_id, origin_id = self._get_unique_id(
            stanza, forwarded, sent, self_message, muc_pm)

        # Check groupchat messages for duplicates,
        # We do this because of MUC History messages
        if type_ == 'groupchat' or self_message or muc_pm:
            if type_ == 'groupchat':
                archive_jid = stanza.getFrom().getStripped()
            else:
                archive_jid = self._con.get_own_jid().getStripped()
            if app.logger.find_stanza_id(self._account,
                                         archive_jid,
                                         stanza_id,
                                         origin_id,
                                         type_ == 'groupchat'):
                return

        thread_id = stanza.getThread()
        msgtxt = stanza.getBody()

        # TODO: remove all control UI stuff
        gc_control = app.interface.msg_win_mgr.get_gc_control(
            jid, self._account)
        if not gc_control:
            minimized = app.interface.minimized_controls[self._account]
            gc_control = minimized.get(jid)

        if gc_control and jid == fjid:
            if type_ == 'error':
                if msgtxt:
                    msgtxt = _('error while sending %(message)s ( %(error)s )') % {
                        'message': msgtxt, 'error': stanza.getErrorMsg()}
                else:
                    msgtxt = _('error: %s') % stanza.getErrorMsg()
                # TODO: why is this here?
                if stanza.getTag('html'):
                    stanza.delChild('html')
            type_ = 'groupchat'

        session = None
        if type_ != 'groupchat':
            if muc_pm and type_ == 'error':
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
            'id_': id_,
            'encrypted': False,
            'additional_data': AdditionalDataDict(),
            'forwarded': forwarded,
            'sent': sent,
            'fjid': fjid,
            'jid': jid,
            'resource': resource,
            'stanza_id': stanza_id,
            'unique_id': stanza_id or origin_id,
            'mtype': type_,
            'msgtxt': msgtxt,
            'thread_id': thread_id,
            'session': session,
            'self_message': self_message,
            'muc_pm': muc_pm,
            'gc_control': gc_control
        }

        event = MessageReceivedEvent(None, **event_attr)
        app.nec.push_incoming_event(event)

        app.plugin_manager.extension_point(
            'decrypt', self._con, event, self._on_message_decrypted)
        if not event.encrypted:
            eme = parse_eme(event.stanza)
            if eme is not None:
                event.msgtxt = eme
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
                self._con.dispatch_error_message(
                    event.stanza, event.msgtxt,
                    event.session, event.fjid, timestamp)
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
            return

        app.nec.push_incoming_event(
            DecryptedMessageReceivedEvent(
                None, **vars(event)))

    def _get_unique_id(self, stanza, _forwarded, _sent, self_message, _muc_pm):
        if stanza.getType() == 'groupchat':
            # TODO: Disco the MUC check if 'urn:xmpp:mam:2' is announced
            return self._get_stanza_id(stanza), None

        if stanza.getType() != 'chat':
            return None, None

        # Messages we receive live
        if self._con.get_module('MAM').archiving_namespace != nbxmpp.NS_MAM_2:
            # Only mam:2 ensures valid stanza-id
            return None, None

        if self_message:
            return self._get_stanza_id(stanza), stanza.getOriginID()
        return self._get_stanza_id(stanza), None

    def _get_stanza_id(self, stanza):
        stanza_id, by = stanza.getStanzaIDAttrs()
        if by is None:
            # We can not verify who set this stanza-id, ignore it.
            return
        if stanza.getType() == 'groupchat':
            if stanza.getFrom().bareMatch(by):
                # by attribute must match the server
                return stanza_id
        elif self._con.get_own_jid().bareMatch(by):
            # by attribute must match the server
            return stanza_id
        return


class MessageReceivedEvent(NetworkIncomingEvent):
    name = 'message-received'


class DecryptedMessageReceivedEvent(NetworkIncomingEvent):
    name = 'decrypted-message-received'


def get_instance(*args, **kwargs):
    return Message(*args, **kwargs), 'Message'
