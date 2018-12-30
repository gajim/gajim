# Copyright (C) 2010-2014 Yann Leboulanger <asterix AT lagaule.org>
#
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

# pylint: disable=no-init
# pylint: disable=attribute-defined-outside-init

import logging
from time import time as time_time

import OpenSSL.crypto
import nbxmpp

from gajim.common import nec
from gajim.common import helpers
from gajim.common import app
from gajim.common import i18n
from gajim.common.i18n import _
from gajim.common.helpers import AdditionalDataDict
from gajim.common.modules import dataforms
from gajim.common.modules.misc import parse_idle
from gajim.common.modules.misc import parse_delay
from gajim.common.const import KindConstant, SSLError
from gajim.common.pep import SUPPORTED_PERSONAL_USER_EVENTS
from gajim.common.jingle_transport import JingleTransportSocks5
from gajim.common.file_props import FilesProp


log = logging.getLogger('gajim.c.connection_handlers_events')


class HelperEvent:
    def get_jid_resource(self, check_fake_jid=False):
        if check_fake_jid and hasattr(self, 'id_') and \
                self.id_ in self.conn.groupchat_jids:
            self.fjid = self.conn.groupchat_jids[self.id_]
            del self.conn.groupchat_jids[self.id_]
        else:
            self.fjid = helpers.get_full_jid_from_iq(self.stanza)
        if self.fjid is None:
            self.jid = None
        else:
            self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)

    def get_id(self):
        self.id_ = self.stanza.getID()

    def get_gc_control(self):
        self.gc_control = app.interface.msg_win_mgr.get_gc_control(self.jid,
                                                                     self.conn.name)

        # If gc_control is missing - it may be minimized. Try to get it
        # from there. If it's not there - then it's missing anyway and
        # will remain set to None.
        if not self.gc_control:
            minimized = app.interface.minimized_controls[self.conn.name]
            self.gc_control = minimized.get(self.jid)

    def get_oob_data(self, stanza):
        oob_node = stanza.getTag('x', namespace=nbxmpp.NS_X_OOB)
        if oob_node is not None:
            oob_url = oob_node.getTagData('url')
            if oob_url is not None:
                self.additional_data.set_value('gajim', 'oob_url', oob_url)
            oob_desc = oob_node.getTagData('desc')
            if oob_desc is not None:
                self.additional_data.set_value('gajim', 'oob_desc', oob_desc)

    def get_stanza_id(self, stanza, query=False):
        if query:
            # On a MAM query the stanza-id is maybe not set, so
            # get the id of the stanza
            return stanza.getAttr('id')
        stanza_id, by = stanza.getStanzaIDAttrs()
        if by is None:
            # We can not verify who set this stanza-id, ignore it.
            return
        if stanza.getType() == 'groupchat':
            if stanza.getFrom().bareMatch(by):
                # by attribute must match the server
                return stanza_id
        elif self.conn.get_own_jid().bareMatch(by):
            # by attribute must match the server
            return stanza_id
        return

    @staticmethod
    def get_forwarded_message(stanza):
        forwarded = stanza.getTag('forwarded',
                                  namespace=nbxmpp.NS_FORWARD,
                                  protocol=True)
        if forwarded is not None:
            return forwarded.getTag('message', protocol=True)

    def _is_self_message(self, message):
        if self.self_message is not None:
            return self.self_message
        own_jid = self.conn.get_own_jid()
        frm = message.getFrom()
        to = message.getTo()
        # If 'to' is not set we assume own jid
        self.self_message = frm.bareMatch(to or own_jid)
        return self.self_message

    def _is_muc_pm(self, message):
        if self.muc_pm is not None:
            return self.muc_pm
        self.muc_pm = False
        muc_user = message.getTag('x', namespace=nbxmpp.NS_MUC_USER)
        if muc_user is not None:
            self.muc_pm = muc_user.getChildren() == []
        return self.muc_pm

class IqErrorReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'iq-error-received'

    def generate(self):
        self.get_id()
        self.get_jid_resource(check_fake_jid=True)
        self.errmsg = self.stanza.getErrorMsg()
        self.errcode = self.stanza.getErrorCode()
        return True

class StreamReceivedEvent(nec.NetworkIncomingEvent):
    name = 'stream-received'

class StreamConflictReceivedEvent(nec.NetworkIncomingEvent):
    name = 'stream-conflict-received'
    base_network_events = ['stream-received']

    def generate(self):
        if self.base_event.stanza.getTag('conflict'):
            self.conn = self.base_event.conn
            return True

class PresenceHelperEvent:
    def _generate_show(self):
        self.show = self.stanza.getShow()
        if self.show not in ('chat', 'away', 'xa', 'dnd'):
            self.show = '' # We ignore unknown show
        if not self.ptype and not self.show:
            self.show = 'online'
        elif self.ptype == 'unavailable':
            self.show = 'offline'

    def _generate_ptype(self):
        self.ptype = self.stanza.getType()
        if self.ptype == 'available':
            self.ptype = None
        rfc_types = ('unavailable', 'error', 'subscribe', 'subscribed',
            'unsubscribe', 'unsubscribed')
        if self.ptype and not self.ptype in rfc_types:
            self.ptype = None

class PresenceReceivedEvent(nec.NetworkIncomingEvent, HelperEvent,
PresenceHelperEvent):
    name = 'presence-received'
    base_network_events = ['raw-pres-received']

    def _generate_keyID(self, sig_tag):
        self.keyID = ''
        if sig_tag and self.conn.USE_GPG and self.ptype != 'error':
            # error presences contain our own signature
            # verify
            sig_msg = sig_tag.getData()
            self.keyID = self.conn.gpg.verify(self.status, sig_msg)
            self.keyID = helpers.prepare_and_validate_gpg_keyID(self.conn.name,
                                                                self.jid,
                                                                self.keyID)

    def _generate_prio(self):
        self.prio = self.stanza.getPriority()
        try:
            self.prio = int(self.prio)
        except Exception:
            self.prio = 0

    def generate(self):
        self.conn = self.base_event.conn
        self.stanza = self.base_event.stanza

        self.need_add_in_roster = False
        self.need_redraw = False

        self.popup = False # Do we want to open chat window ?

        if not self.conn or self.conn.connected < 2:
            log.debug('account is no more connected')
            return

        self._generate_ptype()
        try:
            self.get_jid_resource()
        except Exception:
            log.warning('Invalid JID: %s, ignoring it', self.stanza.getFrom())
            return
        jid_list = app.contacts.get_jid_list(self.conn.name)
        self.timestamp = None
        self.get_id()
        self.avatar_sha = None
        # XEP-0172 User Nickname
        self.user_nick = self.stanza.getTagData('nick') or ''
        self.contact_nickname = None
        self.transport_auto_auth = False

        # XEP-0203
        self.timestamp = parse_delay(self.stanza)
        if self.timestamp is None:
            self.timestamp = time_time()

        # XEP-0319
        self.idle_time = parse_idle(self.stanza)

        sig_tag = self.stanza.getTag('x', namespace=nbxmpp.NS_SIGNED)

        self.status = self.stanza.getStatus() or ''
        self._generate_show()
        self._generate_prio()
        self._generate_keyID(sig_tag)

        self.errcode = self.stanza.getErrorCode()
        self.errmsg = self.stanza.getErrorMsg()

        if self.ptype == 'error':
            return

        if not self.ptype or self.ptype == 'unavailable':
            our_jid = app.get_jid_from_account(self.conn.name)
            if self.jid == our_jid and self.resource == self.conn.server_resource:
                # We got our own presence
                app.nec.push_incoming_event(OurShowEvent(None, conn=self.conn,
                                                           show=self.show))
            elif self.jid in jid_list or self.jid == our_jid:
                return True

class ZeroconfPresenceReceivedEvent(nec.NetworkIncomingEvent):
    name = 'presence-received'

    def generate(self):
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.resource = 'local'
        self.prio = 0
        self.keyID = None
        self.idle_time = None
        self.timestamp = 0
        self.contact_nickname = None
        self.avatar_sha = None
        self.need_add_in_roster = False
        self.need_redraw = False
        if self.show == 'offline':
            self.ptype = 'unavailable'
        else:
            self.ptype = None
        self.user_nick = ''
        self.transport_auto_auth = False
        self.errcode = None
        self.errmsg = ''
        self.popup = False # Do we want to open chat window ?
        return True

class OurShowEvent(nec.NetworkIncomingEvent):
    name = 'our-show'

class MessageSentEvent(nec.NetworkIncomingEvent):
    name = 'message-sent'

    def generate(self):
        if not self.automatic_message:
            self.conn.sent_message_ids.append(self.stanza_id)
            # only record the last 20000 message ids (should be about 1MB [36 byte per uuid]
            # and about 24 hours if you send out a message every 5 seconds)
            self.conn.sent_message_ids = self.conn.sent_message_ids[-20000:]
        return True

class MessageNotSentEvent(nec.NetworkIncomingEvent):
    name = 'message-not-sent'

class MessageErrorEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'message-error'

    def init(self):
        self.zeroconf = False

    def generate(self):
        if self.zeroconf:
            return True
        self.get_id()
        #only alert for errors of explicitly sent messages (see https://trac.gajim.org/ticket/8222)
        if self.id_ in self.conn.sent_message_ids:
            self.conn.sent_message_ids.remove(self.id_)
            return True
        return False

class AnonymousAuthEvent(nec.NetworkIncomingEvent):
    name = 'anonymous-auth'

class JingleRequestReceivedEvent(nec.NetworkIncomingEvent):
    name = 'jingle-request-received'

    def generate(self):
        self.fjid = self.jingle_session.peerjid
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.sid = self.jingle_session.sid
        return True

class JingleConnectedReceivedEvent(nec.NetworkIncomingEvent):
    name = 'jingle-connected-received'

    def generate(self):
        self.fjid = self.jingle_session.peerjid
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.sid = self.jingle_session.sid
        return True

class JingleDisconnectedReceivedEvent(nec.NetworkIncomingEvent):
    name = 'jingle-disconnected-received'

    def generate(self):
        self.fjid = self.jingle_session.peerjid
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.sid = self.jingle_session.sid
        return True

class JingleTransferCancelledEvent(nec.NetworkIncomingEvent):
    name = 'jingleFT-cancelled-received'

    def generate(self):
        self.fjid = self.jingle_session.peerjid
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.sid = self.jingle_session.sid
        return True

class JingleErrorReceivedEvent(nec.NetworkIncomingEvent):
    name = 'jingle-error-received'

    def generate(self):
        self.fjid = self.jingle_session.peerjid
        self.jid, self.resource = app.get_room_and_nick_from_fjid(self.fjid)
        self.sid = self.jingle_session.sid
        return True

class AccountCreatedEvent(nec.NetworkIncomingEvent):
    name = 'account-created'

class AccountNotCreatedEvent(nec.NetworkIncomingEvent):
    name = 'account-not-created'

class NewAccountConnectedEvent(nec.NetworkIncomingEvent):
    name = 'new-account-connected'

    def generate(self):
        try:
            self.errnum = self.conn.connection.Connection.ssl_errnum
        except AttributeError:
            self.errnum = 0 # we don't have an errnum
        self.ssl_msg = ''
        if self.errnum > 0:
            self.ssl_msg = SSLError.get(self.errnum,
                _('Unknown SSL error: %d') % self.errnum)
        self.ssl_cert = ''
        self.ssl_fingerprint_sha1 = ''
        self.ssl_fingerprint_sha256 = ''
        if self.conn.connection.Connection.ssl_certificate:
            cert = self.conn.connection.Connection.ssl_certificate
            self.ssl_cert = OpenSSL.crypto.dump_certificate(
                OpenSSL.crypto.FILETYPE_PEM, cert).decode('utf-8')
            self.ssl_fingerprint_sha1 = cert.digest('sha1').decode('utf-8')
            self.ssl_fingerprint_sha256 = cert.digest('sha256').decode('utf-8')
        return True

class NewAccountNotConnectedEvent(nec.NetworkIncomingEvent):
    name = 'new-account-not-connected'

class ConnectionTypeEvent(nec.NetworkIncomingEvent):
    name = 'connection-type'

class StanzaReceivedEvent(nec.NetworkIncomingEvent):
    name = 'stanza-received'

class StanzaSentEvent(nec.NetworkIncomingEvent):
    name = 'stanza-sent'

class AgentRemovedEvent(nec.NetworkIncomingEvent):
    name = 'agent-removed'

    def generate(self):
        self.jid_list = []
        for jid in app.contacts.get_jid_list(self.conn.name):
            if jid.endswith('@' + self.agent):
                self.jid_list.append(jid)
        return True

class BadGPGPassphraseEvent(nec.NetworkIncomingEvent):
    name = 'bad-gpg-passphrase'

    def generate(self):
        self.account = self.conn.name
        self.use_gpg_agent = app.config.get('use_gpg_agent')
        self.keyID = app.config.get_per('accounts', self.conn.name, 'keyid')
        return True

class ConnectionLostEvent(nec.NetworkIncomingEvent):
    name = 'connection-lost'

    def generate(self):
        app.nec.push_incoming_event(OurShowEvent(None, conn=self.conn,
            show='offline'))
        return True

class GPGTrustKeyEvent(nec.NetworkIncomingEvent):
    name = 'gpg-trust-key'

class GPGPasswordRequiredEvent(nec.NetworkIncomingEvent):
    name = 'gpg-password-required'

    def generate(self):
        self.keyid = app.config.get_per('accounts', self.conn.name, 'keyid')
        return True

class PEPReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'pep-received'

    def generate(self):
        if not self.stanza.getTag('event'):
            return
        if self.stanza.getTag('error'):
            log.debug('PEPReceivedEvent received error stanza. Ignoring')
            return

        try:
            self.get_jid_resource()
        except Exception:
            return

        self.event_tag = self.stanza.getTag('event')

        for pep_class in SUPPORTED_PERSONAL_USER_EVENTS:
            pep = pep_class.get_tag_as_PEP(self.fjid, self.conn.name,
                self.event_tag)
            if pep:
                self.pep_type = pep.type_
                return True

class PlainConnectionEvent(nec.NetworkIncomingEvent):
    name = 'plain-connection'

class InsecureSSLConnectionEvent(nec.NetworkIncomingEvent):
    name = 'insecure-ssl-connection'

class SSLErrorEvent(nec.NetworkIncomingEvent):
    name = 'ssl-error'

class UniqueRoomIdSupportedEvent(nec.NetworkIncomingEvent):
    name = 'unique-room-id-supported'

class UniqueRoomIdNotSupportedEvent(nec.NetworkIncomingEvent):
    name = 'unique-room-id-not-supported'

class NonAnonymousServerErrorEvent(nec.NetworkIncomingEvent):
    name = 'non-anonymous-server-error'

class UpdateGCAvatarEvent(nec.NetworkIncomingEvent):
    name = 'update-gc-avatar'

    def generate(self):
        return True

class UpdateRosterAvatarEvent(nec.NetworkIncomingEvent):
    name = 'update-roster-avatar'

    def generate(self):
        return True

class UpdateRoomAvatarEvent(nec.NetworkIncomingEvent):
    name = 'update-room-avatar'

    def generate(self):
        return True

class ZeroconfNameConflictEvent(nec.NetworkIncomingEvent):
    name = 'zeroconf-name-conflict'

class PasswordRequiredEvent(nec.NetworkIncomingEvent):
    name = 'password-required'

class SignedInEvent(nec.NetworkIncomingEvent):
    name = 'signed-in'

class FileRequestReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'file-request-received'

    def init(self):
        self.jingle_content = None
        self.FT_content = None

    def generate(self):
        self.get_id()
        self.fjid = self.conn._ft_get_from(self.stanza)
        self.jid = app.get_jid_without_resource(self.fjid)
        if self.jingle_content:
            secu = self.jingle_content.getTag('security')
            self.FT_content.use_security = bool(secu)
            if secu:
                fingerprint = secu.getTag('fingerprint')
                if fingerprint:
                    self.FT_content.x509_fingerprint = fingerprint.getData()
            if not self.FT_content.transport:
                self.FT_content.transport = JingleTransportSocks5()
                self.FT_content.transport.set_our_jid(
                    self.FT_content.session.ourjid)
                self.FT_content.transport.set_connection(
                    self.FT_content.session.connection)
            sid = self.stanza.getTag('jingle').getAttr('sid')
            self.file_props = FilesProp.getNewFileProp(self.conn.name, sid)
            self.file_props.transport_sid = self.FT_content.transport.sid
            self.FT_content.file_props = self.file_props
            self.FT_content.transport.set_file_props(self.file_props)
            self.file_props.streamhosts.extend(
                    self.FT_content.transport.remote_candidates)
            for host in self.file_props.streamhosts:
                host['initiator'] = self.FT_content.session.initiator
                host['target'] = self.FT_content.session.responder
            self.file_props.session_type = 'jingle'
            self.file_props.stream_methods = nbxmpp.NS_BYTESTREAM
            desc = self.jingle_content.getTag('description')
            if self.jingle_content.getAttr('creator') == 'initiator':
                file_tag = desc.getTag('file')
                self.file_props.sender = self.fjid
                self.file_props.receiver = self.conn._ft_get_our_jid()
            else:
                file_tag = desc.getTag('file')
                h = file_tag.getTag('hash')
                h = h.getData() if h else None
                n = file_tag.getTag('name')
                n = n.getData() if n else None
                pjid = app.get_jid_without_resource(self.fjid)
                file_info = self.conn.get_file_info(
                    pjid, hash_=h, name=n, account=self.conn.name)
                self.file_props.file_name = file_info['file-name']
                self.file_props.sender = self.conn._ft_get_our_jid()
                self.file_props.receiver = self.fjid
                self.file_props.type_ = 's'
            for child in file_tag.getChildren():
                name = child.getName()
                val = child.getData()
                if val is None:
                    continue
                if name == 'name':
                    self.file_props.name = val
                if name == 'size':
                    self.file_props.size = int(val)
                if name == 'hash':
                    self.file_props.algo = child.getAttr('algo')
                    self.file_props.hash_ = val
                if name == 'date':
                    self.file_props.date = val
        else:
            si = self.stanza.getTag('si')
            self.file_props = FilesProp.getNewFileProp(self.conn.name,
                si.getAttr('id'))
            self.file_props.transport_sid = self.file_props.sid
            profile = si.getAttr('profile')
            if profile != nbxmpp.NS_FILE:
                self.conn.send_file_rejection(self.file_props, code='400',
                    typ='profile')
                raise nbxmpp.NodeProcessed
            feature_tag = si.getTag('feature', namespace=nbxmpp.NS_FEATURE)
            if not feature_tag:
                return
            form_tag = feature_tag.getTag('x', namespace=nbxmpp.NS_DATA)
            if not form_tag:
                return
            self.dataform = dataforms.extend_form(node=form_tag)
            for f in self.dataform.iter_fields():
                if f.var == 'stream-method' and f.type_ == 'list-single':
                    values = [o[1] for o in f.options]
                    self.file_props.stream_methods = ' '.join(values)
                    if nbxmpp.NS_BYTESTREAM in values or \
                    nbxmpp.NS_IBB in values:
                        break
            else:
                self.conn.send_file_rejection(self.file_props, code='400',
                    typ='stream')
                raise nbxmpp.NodeProcessed
            file_tag = si.getTag('file')
            for name, val in file_tag.getAttrs().items():
                if val is None:
                    continue
                if name == 'name':
                    self.file_props.name = val
                if name == 'size':
                    self.file_props.size = int(val)
            mime_type = si.getAttr('mime-type')
            if mime_type is not None:
                self.file_props.mime_type = mime_type
            self.file_props.sender = self.fjid
            self.file_props.receiver = self.conn._ft_get_our_jid()
        self.file_props.request_id = self.id_
        file_desc_tag = file_tag.getTag('desc')
        if file_desc_tag is not None:
            self.file_props.desc = file_desc_tag.getData()
        self.file_props.transfered_size = []
        return True

class FileRequestErrorEvent(nec.NetworkIncomingEvent):
    name = 'file-request-error'

    def generate(self):
        self.jid = app.get_jid_without_resource(self.jid)
        return True

class FileTransferCompletedEvent(nec.NetworkIncomingEvent):
    name = 'file-transfer-completed'

    def generate(self):
        jid = str(self.file_props.receiver)
        self.jid = app.get_jid_without_resource(jid)
        return True

class GatewayPromptReceivedEvent(nec.NetworkIncomingEvent, HelperEvent):
    name = 'gateway-prompt-received'

    def generate(self):
        self.get_jid_resource()
        query = self.stanza.getTag('query')
        if query:
            self.desc = query.getTagData('desc')
            self.prompt = query.getTagData('prompt')
            self.prompt_jid = query.getTagData('jid')
        else:
            self.desc = None
            self.prompt = None
            self.prompt_jid = None
        return True

class NotificationEvent(nec.NetworkIncomingEvent):
    name = 'notification'
    base_network_events = ['decrypted-message-received',
                           'gc-message-received',
                           'presence-received']

    def generate(self):
        # what's needed to compute output
        self.account = self.base_event.conn.name
        self.conn = self.base_event.conn
        self.jid = ''
        self.control = None
        self.control_focused = False
        self.first_unread = False

        # For output
        self.do_sound = False
        self.sound_file = ''
        self.sound_event = '' # gajim sound played if not sound_file is set
        self.show_popup = False

        self.do_popup = False
        self.popup_title = ''
        self.popup_text = ''
        self.popup_event_type = ''
        self.popup_msg_type = ''
        self.icon_name = None
        self.transport_name = None
        self.show = None
        self.popup_timeout = -1

        self.do_command = False
        self.command = ''

        self.show_in_notification_area = False
        self.show_in_roster = False

        self.detect_type()

        if self.notif_type == 'msg':
            self.handle_incoming_msg_event(self.base_event)
        elif self.notif_type == 'gc-msg':
            self.handle_incoming_gc_msg_event(self.base_event)
        elif self.notif_type == 'pres':
            self.handle_incoming_pres_event(self.base_event)
        return True

    def detect_type(self):
        if self.base_event.name == 'decrypted-message-received':
            self.notif_type = 'msg'
        if self.base_event.name == 'gc-message-received':
            self.notif_type = 'gc-msg'
        if self.base_event.name == 'presence-received':
            self.notif_type = 'pres'

    def handle_incoming_msg_event(self, msg_obj):
        # don't alert for carbon copied messages from ourselves
        if msg_obj.sent:
            return
        if not msg_obj.msgtxt:
            return
        self.jid = msg_obj.jid
        if msg_obj.mtype == 'pm':
            self.jid = msg_obj.fjid

        self.control = app.interface.msg_win_mgr.search_control(
            msg_obj.jid, self.account, msg_obj.resource)

        if self.control is None:
            if len(app.events.get_events(
                    self.account, msg_obj.jid, [msg_obj.mtype])) <= 1:
                self.first_unread = True
        else:
            self.control_focused = self.control.has_focus()

        if msg_obj.mtype == 'pm':
            nick = msg_obj.resource
        else:
            nick = app.get_name_from_jid(self.conn.name, self.jid)

        if self.first_unread:
            self.sound_event = 'first_message_received'
        elif self.control_focused:
            self.sound_event = 'next_message_received_focused'
        else:
            self.sound_event = 'next_message_received_unfocused'

        if app.config.get('notification_preview_message'):
            self.popup_text = msg_obj.msgtxt
            if self.popup_text and (self.popup_text.startswith('/me ') or \
            self.popup_text.startswith('/me\n')):
                self.popup_text = '* ' + nick + self.popup_text[3:]
        else:
            # We don't want message preview, do_preview = False
            self.popup_text = ''

        if msg_obj.mtype == 'normal': # single message
            self.popup_msg_type = 'normal'
            self.popup_event_type = _('New Single Message')
        elif msg_obj.mtype == 'pm':
            self.popup_msg_type = 'pm'
            self.popup_event_type = _('New Private Message')
        else: # chat message
            self.popup_msg_type = 'chat'
            self.popup_event_type = _('New Message')

        num_unread = len(app.events.get_events(self.conn.name, self.jid,
            ['printed_' + self.popup_msg_type, self.popup_msg_type]))
        self.popup_title = i18n.ngettext(
            'New message from %(nickname)s',
            '%(n_msgs)i unread messages from %(nickname)s',
            num_unread) % {'nickname': nick, 'n_msgs': num_unread}

        if app.config.get('notify_on_new_message'):
            if self.first_unread or (app.config.get('autopopup_chat_opened') \
            and not self.control_focused):
                if app.config.get('autopopupaway'):
                    # always show notification
                    self.do_popup = True
                if app.connections[self.conn.name].connected in (2, 3):
                    # we're online or chat
                    self.do_popup = True

        if msg_obj.attention and not app.config.get(
        'ignore_incoming_attention'):
            self.popup_timeout = 0
            self.do_popup = True
        else:
            self.popup_timeout = app.config.get('notification_timeout')

        if msg_obj.attention and not app.config.get(
        'ignore_incoming_attention') and app.config.get_per('soundevents',
        'attention_received', 'enabled'):
            self.sound_event = 'attention_received'
            self.do_sound = True
        elif self.first_unread and helpers.allow_sound_notification(
        self.conn.name, 'first_message_received'):
            self.do_sound = True
        elif not self.first_unread and self.control_focused and \
        helpers.allow_sound_notification(self.conn.name,
        'next_message_received_focused'):
            self.do_sound = True
        elif not self.first_unread and not self.control_focused and \
        helpers.allow_sound_notification(self.conn.name,
        'next_message_received_unfocused'):
            self.do_sound = True

    def handle_incoming_gc_msg_event(self, msg_obj):
        if not msg_obj.gc_control:
            # we got a message from a room we're not in? ignore it
            return
        self.jid = msg_obj.jid
        sound = msg_obj.gc_control.highlighting_for_message(
            msg_obj.msgtxt, msg_obj.timestamp)[1]

        if msg_obj.nickname != msg_obj.gc_control.nick:
            self.do_sound = True
            if sound == 'received':
                self.sound_event = 'muc_message_received'
            elif sound == 'highlight':
                self.sound_event = 'muc_message_highlight'
            else:
                self.do_sound = False
        else:
            self.do_sound = False

        self.control = app.interface.msg_win_mgr.search_control(
            msg_obj.jid, self.account)

        if self.control is not None:
            self.control_focused = self.control.has_focus()

        if app.config.get('notify_on_new_message'):
            notify_for_muc = (app.config.notify_for_muc(self.jid) or
                              sound == 'highlight')
            if not notify_for_muc:
                self.do_popup = False

            elif self.control_focused:
                self.do_popup = False

            elif app.config.get('autopopupaway'):
                # always show notification
                self.do_popup = True

            elif app.connections[self.conn.name].connected in (2, 3):
                # we're online or chat
                self.do_popup = True

        self.popup_msg_type = 'gc_msg'
        self.popup_event_type = _('New Group Chat Message')

        if app.config.get('notification_preview_message'):
            self.popup_text = msg_obj.msgtxt

        type_events = ['printed_marked_gc_msg', 'printed_gc_msg']
        count = len(app.events.get_events(self.account, self.jid, type_events))

        contact = app.contacts.get_contact(self.account, self.jid)

        self.popup_title = i18n.ngettext(
            'New message from %(nickname)s',
            '%(n_msgs)i unread messages in %(groupchat_name)s',
            count) % {'nickname': msg_obj.nick,
                      'n_msgs': count,
                      'groupchat_name': contact.get_shown_name()}

    def handle_incoming_pres_event(self, pres_obj):
        if app.jid_is_transport(pres_obj.jid):
            return True
        account = pres_obj.conn.name
        self.jid = pres_obj.jid
        resource = pres_obj.resource or ''
        # It isn't an agent
        for c in pres_obj.contact_list:
            if c.resource == resource:
                # we look for other connected resources
                continue
            if c.show not in ('offline', 'error'):
                return True

        # no other resource is connected, let's look in metacontacts
        family = app.contacts.get_metacontacts_family(account, self.jid)
        for info in family:
            acct_ = info['account']
            jid_ = info['jid']
            c_ = app.contacts.get_contact_with_highest_priority(acct_, jid_)
            if not c_:
                continue
            if c_.jid == self.jid:
                continue
            if c_.show not in ('offline', 'error'):
                return True

        if pres_obj.old_show < 2 and pres_obj.new_show > 1:
            event = 'contact_connected'
            server = app.get_server_from_jid(self.jid)
            account_server = account + '/' + server
            block_transport = False
            if account_server in app.block_signed_in_notifications and \
            app.block_signed_in_notifications[account_server]:
                block_transport = True
            if helpers.allow_showing_notification(account, 'notify_on_signin') \
            and not app.block_signed_in_notifications[account] and \
            not block_transport:
                self.do_popup = True
            if app.config.get_per('soundevents', 'contact_connected',
            'enabled') and not app.block_signed_in_notifications[account] and\
            not block_transport and helpers.allow_sound_notification(account,
            'contact_connected'):
                self.sound_event = event
                self.do_sound = True

        elif pres_obj.old_show > 1 and pres_obj.new_show < 2:
            event = 'contact_disconnected'
            if helpers.allow_showing_notification(account, 'notify_on_signout'):
                self.do_popup = True
            if app.config.get_per('soundevents', 'contact_disconnected',
            'enabled') and helpers.allow_sound_notification(account, event):
                self.sound_event = event
                self.do_sound = True
        # Status change (not connected/disconnected or error (<1))
        elif pres_obj.new_show > 1:
            event = 'status_change'
        else:
            return True

        if app.jid_is_transport(self.jid):
            self.transport_name = app.get_transport_name_from_jid(self.jid)

        self.show = pres_obj.show

        self.popup_timeout = app.config.get('notification_timeout')

        nick = i18n.direction_mark + app.get_name_from_jid(account, self.jid)
        if event == 'status_change':
            self.popup_title = _('%(nick)s Changed Status') % \
                {'nick': nick}
            self.popup_text = _('%(nick)s is now %(status)s') % \
                {'nick': nick, 'status': helpers.get_uf_show(pres_obj.show)}
            if pres_obj.status:
                self.popup_text = self.popup_text + " : " + pres_obj.status
            self.popup_event_type = _('Contact Changed Status')
        elif event == 'contact_connected':
            self.popup_title = _('%(nickname)s Signed In') % {'nickname': nick}
            self.popup_text = ''
            if pres_obj.status:
                self.popup_text = pres_obj.status
            self.popup_event_type = _('Contact Signed In')
        elif event == 'contact_disconnected':
            self.popup_title = _('%(nickname)s Signed Out') % {'nickname': nick}
            self.popup_text = ''
            if pres_obj.status:
                self.popup_text = pres_obj.status
            self.popup_event_type = _('Contact Signed Out')

class MessageOutgoingEvent(nec.NetworkOutgoingEvent):
    name = 'message-outgoing'

    def init(self):
        self.additional_data = AdditionalDataDict()
        self.message = None
        self.keyID = None
        self.type_ = 'chat'
        self.kind = None
        self.timestamp = None
        self.subject = ''
        self.chatstate = None
        self.stanza_id = None
        self.resource = None
        self.user_nick = None
        self.xhtml = None
        self.label = None
        self.session = None
        self.form_node = None
        self.delayed = None
        self.callback = None
        self.callback_args = []
        self.now = False
        self.is_loggable = True
        self.control = None
        self.attention = False
        self.correct_id = None
        self.automatic_message = True
        self.encryption = ''
        self.encrypted = False

    def get_full_jid(self):
        if self.resource:
            return self.jid + '/' + self.resource
        if self.session:
            return self.session.get_to()
        return self.jid

    def generate(self):
        if self.type_ == 'chat':
            self.kind = KindConstant.CHAT_MSG_SENT
        else:
            self.kind = KindConstant.SINGLE_MSG_SENT
        return True

class StanzaMessageOutgoingEvent(nec.NetworkOutgoingEvent):
    name = 'stanza-message-outgoing'


class GcStanzaMessageOutgoingEvent(nec.NetworkOutgoingEvent):
    name = 'gc-stanza-message-outgoing'


class GcMessageOutgoingEvent(nec.NetworkOutgoingEvent):
    name = 'gc-message-outgoing'

    def init(self):
        self.additional_data = AdditionalDataDict()
        self.message = ''
        self.chatstate = None
        self.xhtml = None
        self.stanza_id = None
        self.label = None
        self.callback = None
        self.callback_args = []
        self.is_loggable = True
        self.control = None
        self.correct_id = None
        self.automatic_message = True

    def generate(self):
        return True


class ClientCertPassphraseEvent(nec.NetworkIncomingEvent):
    name = 'client-cert-passphrase'

class InformationEvent(nec.NetworkIncomingEvent):
    name = 'information'

    def init(self):
        self.args = None
        self.kwargs = {}
        self.dialog_name = None
        self.popup = True

    def generate(self):
        if self.args is None:
            self.args = ()
        else:
            self.args = (self.args,)
        return True


class StyleChanged(nec.NetworkIncomingEvent):
    name = 'style-changed'

    def generate(self):
        return True
