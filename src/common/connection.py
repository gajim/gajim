# -*- coding:utf-8 -*-
## src/common/connection.py
##
## Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
##                    Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
##                         Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Tomasz Melcer <liori AT exroot.org>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import os
import random
import socket
import operator

import time
import locale
import hmac
import json

try:
    randomsource = random.SystemRandom()
except Exception:
    randomsource = random.Random()
    randomsource.seed()

import signal
if os.name != 'nt':
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

import nbxmpp
from common import helpers
from common import gajim
from common import gpg
from common import passwords
from common import exceptions
from common import check_X509
from common.connection_handlers import *

if gajim.HAVE_PYOPENSSL:
    import OpenSSL.crypto

from nbxmpp import Smacks
from string import Template
import logging
log = logging.getLogger('gajim.c.connection')

ssl_error = {
2: _("Unable to get issuer certificate"),
3: _("Unable to get certificate CRL"),
4: _("Unable to decrypt certificate's signature"),
5: _("Unable to decrypt CRL's signature"),
6: _("Unable to decode issuer public key"),
7: _("Certificate signature failure"),
8: _("CRL signature failure"),
9: _("Certificate is not yet valid"),
10: _("Certificate has expired"),
11: _("CRL is not yet valid"),
12: _("CRL has expired"),
13: _("Format error in certificate's notBefore field"),
14: _("Format error in certificate's notAfter field"),
15: _("Format error in CRL's lastUpdate field"),
16: _("Format error in CRL's nextUpdate field"),
17: _("Out of memory"),
18: _("Self signed certificate"),
19: _("Self signed certificate in certificate chain"),
20: _("Unable to get local issuer certificate"),
21: _("Unable to verify the first certificate"),
22: _("Certificate chain too long"),
23: _("Certificate revoked"),
24: _("Invalid CA certificate"),
25: _("Path length constraint exceeded"),
26: _("Unsupported certificate purpose"),
27: _("Certificate not trusted"),
28: _("Certificate rejected"),
29: _("Subject issuer mismatch"),
30: _("Authority and subject key identifier mismatch"),
31: _("Authority and issuer serial number mismatch"),
32: _("Key usage does not include certificate signing"),
50: _("Application verification failure")
#100 is for internal usage: host not correct
}

class CommonConnection:
    """
    Common connection class, can be derivated for normal connection or zeroconf
    connection
    """

    def __init__(self, name):
        self.name = name
        # self.connected:
        # 0=>offline,
        # 1=>connection in progress,
        # 2=>online
        # 3=>free for chat
        # ...
        self.connected = 0
        self.connection = None # xmpppy ClientCommon instance
        self.on_purpose = False
        self.is_zeroconf = False
        self.password = ''
        self.server_resource = self._compute_resource()
        self.gpg = None
        self.USE_GPG = False
        if gajim.HAVE_GPG:
            self.USE_GPG = True
            self.gpg = gpg.GnuPG(gajim.config.get('use_gpg_agent'))
        self.status = ''
        self.old_show = ''
        self.priority = gajim.get_priority(name, 'offline')
        self.time_to_reconnect = None
        self.bookmarks = []

        self.blocked_list = []
        self.blocked_contacts = []
        self.blocked_groups = []
        self.blocked_all = False

        self.seclabel_supported = False
        self.seclabel_catalogues = {}

        self.pep_supported = False
        self.pep = {}
        # Do we continue connection when we get roster (send presence,get vcard..)
        self.continue_connect_info = None

        # Remember where we are in the register agent process
        self.agent_registrations = {}
        # To know the groupchat jid associated with a sranza ID. Useful to
        # request vcard or os info... to a real JID but act as if it comes from
        # the fake jid
        self.groupchat_jids = {} # {ID : groupchat_jid}

        self.privacy_rules_supported = False
        self.vcard_supported = False
        self.private_storage_supported = False
        self.archiving_supported = False
        self.archive_pref_supported = False
        self.roster_supported = True
        self.blocking_supported = False
        self.addressing_supported = False
        self.carbons_enabled = False

        self.muc_jid = {} # jid of muc server for each transport type
        self._stun_servers = [] # STUN servers of our jabber server

        self.awaiting_cids = {} # Used for XEP-0231

        self.nested_group_delimiter = '::'

        self.get_config_values_or_default()

    def _compute_resource(self):
        resource = gajim.config.get_per('accounts', self.name, 'resource')
        # All valid resource substitution strings should be added to this hash.
        if resource:
            resource = Template(resource).safe_substitute({
                    'hostname': socket.gethostname()
            })
        return resource

    def dispatch(self, event, data):
        """
        Always passes account name as first param
        """
        gajim.ged.raise_event(event, self.name, data)

    def _reconnect(self):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def quit(self, kill_core):
        if kill_core and gajim.account_is_connected(self.name):
            self.disconnect(on_purpose=True)

    def test_gpg_passphrase(self, password):
        """
        Returns 'ok', 'bad_pass' or 'expired'
        """
        if not self.gpg:
            return False
        self.gpg.passphrase = password
        keyID = gajim.config.get_per('accounts', self.name, 'keyid')
        signed = self.gpg.sign('test', keyID)
        self.gpg.password = None
        if signed == 'KEYEXPIRED':
            return 'expired'
        elif signed == 'BAD_PASSPHRASE':
            return 'bad_pass'
        return 'ok'

    def get_signed_msg(self, msg, callback = None):
        """
        Returns the signed message if possible or an empty string if gpg is not
        used or None if waiting for passphrase

        callback is the function to call when user give the passphrase
        """
        signed = ''
        keyID = gajim.config.get_per('accounts', self.name, 'keyid')
        if keyID and self.USE_GPG:
            use_gpg_agent = gajim.config.get('use_gpg_agent')
            if self.gpg.passphrase is None and not use_gpg_agent:
                # We didn't set a passphrase
                return None
            signed = self.gpg.sign(msg, keyID)
            if signed == 'BAD_PASSPHRASE':
                self.USE_GPG = False
                signed = ''
                gajim.nec.push_incoming_event(BadGPGPassphraseEvent(None,
                    conn=self))
        return signed

    def _on_disconnected(self):
        """
        Called when a disconnect request has completed successfully
        """
        self.disconnect(on_purpose=True)
        gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='offline'))

    def get_status(self):
        return gajim.SHOW_LIST[self.connected]

    def check_jid(self, jid):
        """
        This function must be implemented by derivated classes. It has to return
        the valid jid, or raise a helpers.InvalidFormat exception
        """
        raise NotImplementedError

    def _prepare_message(self, jid, msg, keyID, type_='chat', subject='',
    chatstate=None, msg_id=None, resource=None, user_nick=None, xhtml=None,
    session=None, forward_from=None, form_node=None, label=None,
    original_message=None, delayed=None, attention=False, correction_msg=None,
    callback=None):
        if not self.connection or self.connected < 2:
            return 1

        if isinstance(jid, list):
            new_list = []
            for j in jid:
                try:
                    new_list.append(self.check_jid(j))
                except helpers.InvalidFormat:
                    gajim.nec.push_incoming_event(InformationEvent(None,
                        conn=self, level='error', pri_txt=_('Invalid Jabber '
                        'ID'), sec_txt=_('It is not possible to send a message '
                        'to %s, this JID is not valid.') % j))
                    return
            fjid = new_list
        else:
            try:
                jid = self.check_jid(jid)
            except helpers.InvalidFormat:
                gajim.nec.push_incoming_event(InformationEvent(None, conn=self,
                    level='error', pri_txt=_('Invalid Jabber ID'), sec_txt=_(
                    'It is not possible to send a message to %s, this JID is not '
                    'valid.') % jid))
                return
            fjid = jid
            if resource:
                fjid += '/' + resource

            if session:
                fjid = session.get_to()

        if msg and not xhtml and gajim.config.get(
        'rst_formatting_outgoing_messages'):
            from common.rst_xhtml_generator import create_xhtml
            xhtml = create_xhtml(msg)
        if not msg and chatstate is None and form_node is None:
            return

        msgtxt = msg
        msgenc = ''

        if keyID and self.USE_GPG:
            xhtml = None
            if keyID ==  'UNKNOWN':
                error = _('Neither the remote presence is signed, nor a key was '
                        'assigned.')
            elif keyID.endswith('MISMATCH'):
                error = _('The contact\'s key (%s) does not match the key assigned '
                        'in Gajim.' % keyID[:8])
            else:
                def encrypt_thread(msg, keyID, always_trust=False):
                    # encrypt message. This function returns (msgenc, error)
                    return self.gpg.encrypt(msg, [keyID], always_trust)
                def _on_encrypted(output):
                    msgenc, error = output
                    if error == 'NOT_TRUSTED':
                        def _on_always_trust(answer):
                            if answer:
                                gajim.thread_interface(encrypt_thread, [msg, keyID,
                                        True], _on_encrypted, [])
                            else:
                                self._message_encrypted_cb(output, type_, msg,
                                    msgtxt, original_message, fjid, resource,
                                    jid, xhtml, subject, chatstate, msg_id,
                                    label, forward_from, delayed, session,
                                    form_node, user_nick, keyID, attention,
                                    correction_msg, callback)
                        gajim.nec.push_incoming_event(GPGTrustKeyEvent(None,
                            conn=self, keyID=keyID, callback=_on_always_trust))
                    else:
                        self._message_encrypted_cb(output, type_, msg, msgtxt,
                            original_message, fjid, resource, jid, xhtml,
                            subject, chatstate, msg_id, label, forward_from,
                            delayed, session, form_node, user_nick, keyID,
                            attention, correction_msg, callback)
                gajim.thread_interface(encrypt_thread, [msg, keyID, False],
                    _on_encrypted, [])
                return

            self._message_encrypted_cb(('', error), type_, msg, msgtxt,
                original_message, fjid, resource, jid, xhtml, subject,
                chatstate, msg_id, label, forward_from, delayed, session,
                form_node, user_nick, keyID, attention, correction_msg,
                callback)
            return

        self._on_continue_message(type_, msg, msgtxt, original_message, fjid,
            resource, jid, xhtml, subject, msgenc, keyID, chatstate, msg_id,
            label, forward_from, delayed, session, form_node, user_nick,
            attention, correction_msg, callback)

    def _message_encrypted_cb(self, output, type_, msg, msgtxt,
    original_message, fjid, resource, jid, xhtml, subject, chatstate, msg_id,
    label, forward_from, delayed, session, form_node, user_nick, keyID,
    attention, correction_msg, callback):
        msgenc, error = output

        if msgenc and not error:
            msgtxt = '[This message is *encrypted* (See :XEP:`27`]'
            lang = os.getenv('LANG')
            if lang is not None and not lang.startswith('en'):
                # we're not english: one in locale and one en
                msgtxt = _('[This message is *encrypted* (See :XEP:`27`]') + \
                        ' (' + msgtxt + ')'
            self._on_continue_message(type_, msg, msgtxt, original_message,
                fjid, resource, jid, xhtml, subject, msgenc, keyID,
                chatstate, msg_id, label, forward_from, delayed, session,
                form_node, user_nick, attention, correction_msg, callback)
            return
        # Encryption failed, do not send message
        tim = localtime()
        gajim.nec.push_incoming_event(MessageNotSentEvent(None, conn=self,
            jid=jid, message=msgtxt, error=error, time_=tim, session=session))

    def _on_continue_message(self, type_, msg, msgtxt, original_message, fjid,
    resource, jid, xhtml, subject, msgenc, keyID, chatstate, msg_id,
    label, forward_from, delayed, session, form_node, user_nick, attention,
    correction_msg, callback):

        if correction_msg:
            id_ = correction_msg.getID()
            if correction_msg.getTag('replace'):
                correction_msg.delChild('replace')
            correction_msg.setTag('replace', attrs={'id': id_},
                namespace=nbxmpp.NS_CORRECT)
            id2 = self.connection.getAnID()
            correction_msg.setID(id2)
            correction_msg.setBody(msgtxt)
            if xhtml:
                correction_msg.setXHTML(xhtml)

            if session:
                session.last_send = time.time()

                # XEP-0200
                if session.enable_encryption:
                    correction_msg = session.encrypt_stanza(correction_msg)

            if callback:
                callback(jid, msg, keyID, forward_from, session, original_message,
                    subject, type_, correction_msg, xhtml)
            return


        if type_ == 'chat':
            msg_iq = nbxmpp.Message(body=msgtxt, typ=type_,
                    xhtml=xhtml)
        else:
            if subject:
                msg_iq = nbxmpp.Message(body=msgtxt, typ='normal',
                        subject=subject, xhtml=xhtml)
            else:
                msg_iq = nbxmpp.Message(body=msgtxt, typ='normal',
                        xhtml=xhtml)

        if msg_id:
            msg_iq.setID(msg_id)

        if msgenc:
            msg_iq.setTag(nbxmpp.NS_ENCRYPTED + ' x').setData(msgenc)
            if self.carbons_enabled:
                msg_iq.addChild(name='private', namespace=nbxmpp.NS_CARBONS)

        if form_node:
            msg_iq.addChild(node=form_node)
        if label:
            msg_iq.addChild(node=label)

        # XEP-0172: user_nickname
        if user_nick:
            msg_iq.setTag('nick', namespace = nbxmpp.NS_NICK).setData(
                    user_nick)

        # XEP-0203
        if delayed:
            our_jid = gajim.get_jid_from_account(self.name) + '/' + \
                    self.server_resource
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(delayed))
            msg_iq.addChild('delay', namespace=nbxmpp.NS_DELAY2,
                    attrs={'from': our_jid, 'stamp': timestamp})

        # XEP-0224
        if attention:
            msg_iq.setTag('attention', namespace=nbxmpp.NS_ATTENTION)

        if isinstance(jid, list):
            if self.addressing_supported:
                msg_iq.setTo(gajim.config.get_per('accounts', self.name, 'hostname'))
                addresses = msg_iq.addChild('addresses',
                    namespace=nbxmpp.NS_ADDRESS)
                for j in jid:
                    addresses.addChild('address', attrs = {'type': 'to',
                        'jid': j})
            else:
                iqs = []
                for j in jid:
                    iq = nbxmpp.Message(node=msg_iq)
                    iq.setTo(j)
                    iqs.append(iq)
                msg_iq = iqs
        else:
            msg_iq.setTo(fjid)
            r_ = resource or gajim.get_resource_from_jid(fjid)
            if r_:
                contact = gajim.contacts.get_contact(self.name, jid, r_)
            else:
                contact = gajim.contacts.get_contact_with_highest_priority(
                    self.name, jid)

            # chatstates - if peer supports xep85, send chatstates
            # please note that the only valid tag inside a message containing a
            # <body> tag is the active event
            if chatstate and contact and contact.supports(NS_CHATSTATES):
                msg_iq.setTag(chatstate, namespace=NS_CHATSTATES)

            # XEP-0184
            if msgtxt and gajim.config.get_per('accounts', self.name,
            'request_receipt') and contact and contact.supports(
            nbxmpp.NS_RECEIPTS):
                msg_iq.setTag('request', namespace=nbxmpp.NS_RECEIPTS)

            if forward_from:
                addresses = msg_iq.addChild('addresses',
                    namespace=nbxmpp.NS_ADDRESS)
                addresses.addChild('address', attrs = {'type': 'ofrom',
                    'jid': forward_from})

            if session:
                # XEP-0201
                session.last_send = time.time()
                msg_iq.setThread(session.thread_id)

                # XEP-0200
                if session.enable_encryption:
                    msg_iq = session.encrypt_stanza(msg_iq)
                    if self.carbons_enabled:
                        msg_iq.addChild(name='private',
                            namespace=nbxmpp.NS_CARBONS)

        if callback:
            callback(jid, msg, keyID, forward_from, session, original_message,
                subject, type_, msg_iq, xhtml)

    def log_message(self, jid, msg, forward_from, session, original_message,
    subject, type_, xhtml=None):
        if not forward_from and session and session.is_loggable():
            ji = gajim.get_jid_without_resource(jid)
            if gajim.config.should_log(self.name, ji):
                log_msg = msg
                if original_message is not None:
                    log_msg = original_message
                if subject:
                    log_msg = _('Subject: %(subject)s\n%(message)s') % \
                    {'subject': subject, 'message': log_msg}
                if log_msg:
                    if type_ == 'chat':
                        kind = 'chat_msg_sent'
                    else:
                        kind = 'single_msg_sent'
                    try:
                        if xhtml and gajim.config.get('log_xhtml_messages'):
                            log_msg = '<body xmlns="%s">%s</body>' % (
                                nbxmpp.NS_XHTML, xhtml)
                        gajim.logger.write(kind, jid, log_msg)
                    except exceptions.PysqliteOperationalError as e:
                        self.dispatch('DB_ERROR', (_('Disk Write Error'),
                            str(e)))
                    except exceptions.DatabaseMalformed:
                        pritext = _('Database Error')
                        sectext = _('The database file (%s) cannot be read. Try'
                            ' to repair it (see '
                            'http://trac.gajim.org/wiki/DatabaseBackup)'
                            ' or remove it (all history will be lost).') % \
                            common.logger.LOG_DB_PATH
                        self.dispatch('DB_ERROR', (pritext, sectext))

    def ack_subscribed(self, jid):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def ack_unsubscribed(self, jid):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def request_subscription(self, jid, msg='', name='', groups=[],
                    auto_auth=False):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def send_authorization(self, jid):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def refuse_authorization(self, jid):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def unsubscribe(self, jid, remove_auth = True):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def unsubscribe_agent(self, agent):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def update_contact(self, jid, name, groups):
        if self.connection and self.roster_supported:
            self.connection.getRoster().setItem(jid=jid, name=name, groups=groups)

    def update_contacts(self, contacts):
        """
        Update multiple roster items
        """
        if self.connection and self.roster_supported:
            self.connection.getRoster().setItemMulti(contacts)

    def new_account(self, name, config, sync=False):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def _on_new_account(self, con=None, con_type=None):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def account_changed(self, new_name):
        self.name = new_name

    def request_last_status_time(self, jid, resource, groupchat_jid=None):
        """
        groupchat_jid is used when we want to send a request to a real jid and
        act as if the answer comes from the groupchat_jid
        """
        if not gajim.account_is_connected(self.name):
            return
        to_whom_jid = jid
        if resource:
            to_whom_jid += '/' + resource
        iq = nbxmpp.Iq(to=to_whom_jid, typ='get', queryNS=nbxmpp.NS_LAST)
        id_ = self.connection.getAnID()
        iq.setID(id_)
        if groupchat_jid:
            self.groupchat_jids[id_] = groupchat_jid
        self.last_ids.append(id_)
        self.connection.send(iq)

    def request_os_info(self, jid, resource):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def get_settings(self):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def get_bookmarks(self):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def store_bookmarks(self):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def get_metacontacts(self):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def send_agent_status(self, agent, ptype):
        """
        To be implemented by derivated classes
        """
        raise NotImplementedError

    def gpg_passphrase(self, passphrase):
        if self.gpg:
            use_gpg_agent = gajim.config.get('use_gpg_agent')
            if use_gpg_agent:
                self.gpg.passphrase = None
            else:
                self.gpg.passphrase = passphrase

    def ask_gpg_keys(self):
        if self.gpg:
            return self.gpg.get_keys()
        return None

    def ask_gpg_secrete_keys(self):
        if self.gpg:
            return self.gpg.get_secret_keys()
        return None

    def load_roster_from_db(self):
        # Do nothing by default
        return

    def _event_dispatcher(self, realm, event, data):
        if realm == '':
            if event == nbxmpp.transports_nb.DATA_RECEIVED:
                gajim.nec.push_incoming_event(StanzaReceivedEvent(None,
                    conn=self, stanza_str=data))
            elif event == nbxmpp.transports_nb.DATA_SENT:
                gajim.nec.push_incoming_event(StanzaSentEvent(None, conn=self,
                    stanza_str=data))

    def change_status(self, show, msg, auto=False):
        if not msg:
            msg = ''
        sign_msg = False
        if not auto and not show == 'offline':
            sign_msg = True
        if show != 'invisible':
            # We save it only when privacy list is accepted
            self.status = msg
        if show != 'offline' and self.connected < 1:
            # set old_show to requested 'show' in case we need to
            # recconect before we auth to server
            self.old_show = show
            self.on_purpose = False
            self.server_resource = self._compute_resource()
            if gajim.HAVE_GPG:
                self.USE_GPG = True
                self.gpg = gpg.GnuPG(gajim.config.get('use_gpg_agent'))
            gajim.nec.push_incoming_event(BeforeChangeShowEvent(None,
                conn=self, show=show, message=msg))
            self.connect_and_init(show, msg, sign_msg)
            return

        if show == 'offline':
            self.connected = 0
            if self.connection:
                gajim.nec.push_incoming_event(BeforeChangeShowEvent(None,
                    conn=self, show=show, message=msg))
                p = nbxmpp.Presence(typ = 'unavailable')
                p = self.add_sha(p, False)
                if msg:
                    p.setStatus(msg)

                self.connection.RegisterDisconnectHandler(self._on_disconnected)
                self.connection.send(p, now=True)
                self.connection.start_disconnect()
            else:
                self._on_disconnected()
            return

        if show != 'offline' and self.connected > 0:
            # dont'try to connect, when we are in state 'connecting'
            if self.connected == 1:
                return
            if show == 'invisible':
                gajim.nec.push_incoming_event(BeforeChangeShowEvent(None,
                    conn=self, show=show, message=msg))
                self._change_to_invisible(msg)
                return
            if show not in ['offline', 'online', 'chat', 'away', 'xa', 'dnd']:
                return -1
            was_invisible = self.connected == gajim.SHOW_LIST.index('invisible')
            self.connected = gajim.SHOW_LIST.index(show)
            gajim.nec.push_incoming_event(BeforeChangeShowEvent(None,
                conn=self, show=show, message=msg))
            if was_invisible:
                self._change_from_invisible()
            self._update_status(show, msg)

class Connection(CommonConnection, ConnectionHandlers):
    def __init__(self, name):
        CommonConnection.__init__(self, name)
        ConnectionHandlers.__init__(self)
        # this property is used to prevent double connections
        self.last_connection = None # last ClientCommon instance
        # If we succeed to connect, remember it so next time we try (after a
        # disconnection) we try only this type.
        self.last_connection_type = None
        self.lang = None
        if locale.getdefaultlocale()[0]:
            self.lang = locale.getdefaultlocale()[0].split('_')[0]
        # increase/decrease default timeout for server responses
        self.try_connecting_for_foo_secs = 45
        # holds the actual hostname to which we are connected
        self.connected_hostname = None
        self.redirected = None
        self.last_time_to_reconnect = None
        self.new_account_info = None
        self.new_account_form = None
        self.annotations = {}
        self.last_io = gajim.idlequeue.current_time()
        self.last_sent = []
        self.last_history_time = {}
        self.password = passwords.get_password(name)

        self.music_track_info = 0
        self.location_info = {}
        self.pubsub_supported = False
        self.pubsub_publish_options_supported = False
        # Do we auto accept insecure connection
        self.connection_auto_accepted = False
        self.pasword_callback = None

        self.on_connect_success = None
        self.on_connect_failure = None
        self.retrycount = 0
        self.jids_for_auto_auth = [] # list of jid to auto-authorize
        self.available_transports = {} # list of available transports on this
        # server {'icq': ['icq.server.com', 'icq2.server.com'], }
        self.private_storage_supported = True
        self.privacy_rules_requested = False
        self.streamError = ''
        self.secret_hmac = str(random.random())[2:].encode('utf-8')

        self.sm = Smacks(self) # Stream Management

        gajim.ged.register_event_handler('privacy-list-received', ged.CORE,
            self._nec_privacy_list_received)
        gajim.ged.register_event_handler('agent-info-error-received', ged.CORE,
            self._nec_agent_info_error_received)
        gajim.ged.register_event_handler('agent-info-received', ged.CORE,
            self._nec_agent_info_received)
        gajim.ged.register_event_handler('message-outgoing', ged.OUT_CORE,
            self._nec_message_outgoing)
        gajim.ged.register_event_handler('gc-message-outgoing', ged.OUT_CORE,
            self._nec_gc_message_outgoing)
    # END __init__

    def cleanup(self):
        ConnectionHandlers.cleanup(self)
        gajim.ged.remove_event_handler('privacy-list-received', ged.CORE,
            self._nec_privacy_list_received)
        gajim.ged.remove_event_handler('agent-info-error-received', ged.CORE,
            self._nec_agent_info_error_received)
        gajim.ged.remove_event_handler('agent-info-received', ged.CORE,
            self._nec_agent_info_received)
        gajim.ged.remove_event_handler('message-outgoing', ged.OUT_CORE,
            self._nec_message_outgoing)
        gajim.ged.remove_event_handler('gc-message-outgoing', ged.OUT_CORE,
            self._nec_gc_message_outgoing)

    def get_config_values_or_default(self):
        if gajim.config.get_per('accounts', self.name, 'keep_alives_enabled'):
            self.keepalives = gajim.config.get_per('accounts', self.name,
                    'keep_alive_every_foo_secs')
        else:
            self.keepalives = 0
        if gajim.config.get_per('accounts', self.name, 'ping_alives_enabled'):
            self.pingalives = gajim.config.get_per('accounts', self.name,
                    'ping_alive_every_foo_secs')
        else:
            self.pingalives = 0
        self.client_cert = gajim.config.get_per('accounts', self.name,
            'client_cert')
        self.client_cert_passphrase = ''

    def check_jid(self, jid):
        return helpers.parse_jid(jid)

    def _reconnect(self):
        # Do not try to reco while we are already trying
        self.time_to_reconnect = None
        if self.connected < 2: # connection failed
            log.debug('reconnect')
            self.connected = 1
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='connecting'))
            self.retrycount += 1
            self.on_connect_auth = self._discover_server_at_connection
            self.connect_and_init(self.old_show, self.status, self.USE_GPG)
        else:
            # reconnect succeeded
            self.time_to_reconnect = None
            self.retrycount = 0

    # We are doing disconnect at so many places, better use one function in all
    def disconnect(self, on_purpose=False):
        gajim.interface.music_track_changed(None, None, self.name)
        self.reset_awaiting_pep()
        self.on_purpose = on_purpose
        self.connected = 0
        self.time_to_reconnect = None
        self.privacy_rules_supported = False
        if on_purpose:
            self.sm = Smacks(self)
        if self.connection:
            # make sure previous connection is completely closed
            gajim.proxy65_manager.disconnect(self.connection)
            self.terminate_sessions()
            self.remove_all_transfers()
            self.connection.disconnect()
            self.last_connection = None
            self.connection = None
    def set_oldst(self): # Set old state
        if self.old_show:
            self.connected = gajim.SHOW_LIST.index(self.old_show)
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                                           show=self.connected))
        else: # we default to online
            self.connected = 2
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                                    show=gajim.SHOW_LIST[self.connected]))

    def _disconnectedReconnCB(self):
        """
        Called when we are disconnected
        """
        log.info('disconnectedReconnCB called')
        if gajim.account_is_connected(self.name):
            # we cannot change our status to offline or connecting
            # after we auth to server
            self.old_show = gajim.SHOW_LIST[self.connected]
        self.connected = 0
        if not self.on_purpose:
            if not (self.sm and self.sm.resumption):
                gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='offline'))
            else:
                self.sm.enabled = False
                gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='error'))
            self.disconnect()
            if gajim.config.get_per('accounts', self.name, 'autoreconnect'):
                self.connected = -1
                gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='error'))
                if gajim.status_before_autoaway[self.name]:
                    # We were auto away. So go back online
                    self.status = gajim.status_before_autoaway[self.name]
                    gajim.status_before_autoaway[self.name] = ''
                    self.old_show = 'online'
                # this check has moved from _reconnect method
                # do exponential backoff until 15 minutes,
                # then small linear increase
                if self.retrycount < 2 or self.last_time_to_reconnect is None:
                    self.last_time_to_reconnect = 5
                if self.last_time_to_reconnect < 800:
                    self.last_time_to_reconnect *= 1.5
                self.last_time_to_reconnect += randomsource.randint(0, 5)
                self.time_to_reconnect = int(self.last_time_to_reconnect)
                log.info("Reconnect to %s in %ss", self.name, self.time_to_reconnect)
                gajim.idlequeue.set_alarm(self._reconnect_alarm,
                        self.time_to_reconnect)
            elif self.on_connect_failure:
                self.on_connect_failure()
                self.on_connect_failure = None
            else:
                # show error dialog
                self._connection_lost()
        else:
            if self.redirected:
                self.disconnect(on_purpose=True)
                self.connect()
                return
            else:
                self.disconnect()
        self.on_purpose = False
    # END disconnectedReconnCB

    def _connection_lost(self):
        log.debug('_connection_lost')
        self.disconnect(on_purpose = False)
        gajim.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
            title=_('Connection with account "%s" has been lost') % self.name,
            msg=_('Reconnect manually.')))

    def _event_dispatcher(self, realm, event, data):
        CommonConnection._event_dispatcher(self, realm, event, data)
        if realm == nbxmpp.NS_REGISTER:
            if event == nbxmpp.features_nb.REGISTER_DATA_RECEIVED:
                # data is (agent, DataFrom, is_form, error_msg)
                if self.new_account_info and \
                self.new_account_info['hostname'] == data[0]:
                    # it's a new account
                    if not data[1]: # wrong answer
                        reason = _('Server %(name)s answered wrongly to '
                            'register request: %(error)s') % {'name': data[0],
                            'error': data[3]}
                        gajim.nec.push_incoming_event(AccountNotCreatedEvent(
                            None, conn=self, reason=reason))
                        return
                    is_form = data[2]
                    conf = data[1]
                    if data[4] is not '':
                        helpers.replace_dataform_media(conf, data[4])
                    if self.new_account_form:
                        def _on_register_result(result):
                            if not nbxmpp.isResultNode(result):
                                gajim.nec.push_incoming_event(AccountNotCreatedEvent(
                                    None, conn=self, reason=result.getError()))
                                return
                            if gajim.HAVE_GPG:
                                self.USE_GPG = True
                                self.gpg = gpg.GnuPG(gajim.config.get(
                                        'use_gpg_agent'))
                            gajim.nec.push_incoming_event(
                                AccountCreatedEvent(None, conn=self,
                                account_info = self.new_account_info))
                            self.new_account_info = None
                            self.new_account_form = None
                            if self.connection:
                                self.connection.UnregisterDisconnectHandler(
                                        self._on_new_account)
                            self.disconnect(on_purpose=True)
                        # it's the second time we get the form, we have info user
                        # typed, so send them
                        if is_form:
                            #TODO: Check if form has changed
                            iq = nbxmpp.Iq('set', nbxmpp.NS_REGISTER,
                                to=self._hostname)
                            iq.setTag('query').addChild(node=self.new_account_form)
                            self.connection.SendAndCallForResponse(iq,
                                    _on_register_result)
                        else:
                            if list(self.new_account_form.keys()).sort() != \
                            list(conf.keys()).sort():
                                # requested config has changed since first connection
                                reason = _('Server %s provided a different '
                                    'registration form') % data[0]
                                gajim.nec.push_incoming_event(AccountNotCreatedEvent(
                                    None, conn=self, reason=reason))
                                return
                            nbxmpp.features_nb.register(self.connection,
                                    self._hostname, self.new_account_form,
                                    _on_register_result)
                        return
                    gajim.nec.push_incoming_event(NewAccountConnectedEvent(None,
                        conn=self, config=conf, is_form=is_form))
                    self.connection.UnregisterDisconnectHandler(
                        self._on_new_account)
                    self.disconnect(on_purpose=True)
                    return
                if not data[1]: # wrong answer
                    gajim.nec.push_incoming_event(InformationEvent(None,
                        conn=self, level='error', pri_txt=_('Invalid answer'),
                        sec_txt=_('Transport %(name)s answered wrongly to '
                        'register request: %(error)s') % {'name': data[0],
                        'error': data[3]}))
                    return
                is_form = data[2]
                conf = data[1]
                gajim.nec.push_incoming_event(RegisterAgentInfoReceivedEvent(
                    None, conn=self, agent=data[0], config=conf,
                    is_form=is_form))
        elif realm == nbxmpp.NS_PRIVACY:
            if event == nbxmpp.features_nb.PRIVACY_LISTS_RECEIVED:
                # data is (list)
                gajim.nec.push_incoming_event(PrivacyListsReceivedEvent(None,
                    conn=self, lists_list=data))
            elif event == nbxmpp.features_nb.PRIVACY_LIST_RECEIVED:
                # data is (resp)
                if not data:
                    return
                rules = []
                name = data.getTag('query').getTag('list').getAttr('name')
                for child in data.getTag('query').getTag('list').getChildren():
                    dict_item = child.getAttrs()
                    childs = []
                    if 'type' in dict_item:
                        for scnd_child in child.getChildren():
                            childs += [scnd_child.getName()]
                        rules.append({'action':dict_item['action'],
                                'type':dict_item['type'], 'order':dict_item['order'],
                                'value':dict_item['value'], 'child':childs})
                    else:
                        for scnd_child in child.getChildren():
                            childs.append(scnd_child.getName())
                        rules.append({'action':dict_item['action'],
                                'order':dict_item['order'], 'child':childs})
                gajim.nec.push_incoming_event(PrivacyListReceivedEvent(None,
                    conn=self, list_name=name, rules=rules))
            elif event == nbxmpp.features_nb.PRIVACY_LISTS_ACTIVE_DEFAULT:
                # data is (dict)
                gajim.nec.push_incoming_event(PrivacyListActiveDefaultEvent(
                    None, conn=self, active_list=data['active'],
                    default_list=data['default']))

    def _select_next_host(self, hosts):
        """
        Selects the next host according to RFC2782 p.3 based on it's priority.
        Chooses between hosts with the same priority randomly, where the
        probability of being selected is proportional to the weight of the host
        """
        hosts_by_prio = sorted(hosts, key=operator.itemgetter('prio'))

        try:
            lowest_prio = hosts_by_prio[0]['prio']
        except IndexError:
            raise ValueError("No hosts to choose from!")

        hosts_lowest_prio = [h for h in hosts_by_prio if h['prio'] == lowest_prio]

        if len(hosts_lowest_prio) == 1:
            return hosts_lowest_prio[0]
        else:
            rndint = random.randint(0, sum(h['weight'] for h in hosts_lowest_prio))
            weightsum = 0
            for host in sorted(hosts_lowest_prio, key=operator.itemgetter(
            'weight')):
                weightsum += host['weight']
                if weightsum >= rndint:
                    return host

    def connect(self, data=None):
        """
        Start a connection to the Jabber server

        Returns connection, and connection type ('tls', 'ssl', 'plain', '') data
        MUST contain hostname, usessl, proxy, use_custom_host, custom_host (if
        use_custom_host), custom_port (if use_custom_host)
        """
        if self.connection:
            return self.connection, ''

        if self.sm.resuming and self.sm.location:
            # If resuming and server gave a location, connect from there
            hostname = self.sm.location
            self.try_connecting_for_foo_secs = gajim.config.get_per('accounts',
                self.name, 'try_connecting_for_foo_secs')
            use_custom = False
            proxy = helpers.get_proxy_info(self.name)

        elif data:
            hostname = data['hostname']
            self.try_connecting_for_foo_secs = 45
            p = data['proxy']
            if p and p in gajim.config.get_per('proxies'):
                proxy = {}
                proxyptr = gajim.config.get_per('proxies', p)
                for key in proxyptr.keys():
                    proxy[key] = proxyptr[key]
            else:
                proxy = None
            use_srv = True
            use_custom = data['use_custom_host']
            if use_custom:
                custom_h = data['custom_host']
                custom_p = data['custom_port']
        else:
            hostname = gajim.config.get_per('accounts', self.name, 'hostname')
            usessl = gajim.config.get_per('accounts', self.name, 'usessl')
            self.try_connecting_for_foo_secs = gajim.config.get_per('accounts',
                    self.name, 'try_connecting_for_foo_secs')
            proxy = helpers.get_proxy_info(self.name)
            use_srv = gajim.config.get_per('accounts', self.name, 'use_srv')
            if self.redirected:
                use_custom = True
                custom_h = self.redirected['host']
                custom_p = self.redirected['port']
            else:
                use_custom = gajim.config.get_per('accounts', self.name,
                    'use_custom_host')
                custom_h = gajim.config.get_per('accounts', self.name,
                    'custom_host')
                custom_p = gajim.config.get_per('accounts', self.name,
                    'custom_port')

        # create connection if it doesn't already exist
        self.connected = 1

        h = hostname
        p = 5222
        ssl_p = 5223
        if use_custom:
            h = custom_h
            p = custom_p
            ssl_p = custom_p
            if not self.redirected:
                use_srv = False

        self.redirected = None
        # SRV resolver
        self._proxy = proxy
        self._hosts = [ {'host': h, 'port': p, 'ssl_port': ssl_p, 'prio': 10,
                'weight': 10} ]
        self._hostname = hostname
        if use_srv:
            # add request for srv query to the resolve, on result '_on_resolve'
            # will be called
            gajim.resolver.resolve('_xmpp-client._tcp.' + helpers.idn_to_ascii(
                h), self._on_resolve)
        else:
            self._on_resolve('', [])

    def _on_resolve(self, host, result_array):
        # SRV query returned at least one valid result, we put it in hosts dict
        if len(result_array) != 0:
            self._hosts = [i for i in result_array]
            # Add ssl port
            ssl_p = 5223
            if gajim.config.get_per('accounts', self.name, 'use_custom_host'):
                ssl_p = gajim.config.get_per('accounts', self.name,
                    'custom_port')
            for i in self._hosts:
                i['ssl_port'] = ssl_p
        self._connect_to_next_host()


    def _connect_to_next_host(self, retry=False):
        log.debug('Connection to next host')
        if len(self._hosts):
            # No config option exist when creating a new account
            if self.name in gajim.config.get_per('accounts'):
                self._connection_types = gajim.config.get_per('accounts', self.name,
                        'connection_types').split()
            else:
                self._connection_types = ['tls', 'ssl', 'plain']
            if self.last_connection_type:
                if self.last_connection_type in self._connection_types:
                    self._connection_types.remove(self.last_connection_type)
                self._connection_types.insert(0, self.last_connection_type)


            if self._proxy and self._proxy['type']=='bosh':
                # with BOSH, we can't do TLS negotiation with <starttls>, we do only "plain"
                # connection and TLS with handshake right after TCP connecting ("ssl")
                scheme = nbxmpp.transports_nb.urisplit(self._proxy['bosh_uri'])[0]
                if scheme=='https':
                    self._connection_types = ['ssl']
                else:
                    self._connection_types = ['plain']

            host = self._select_next_host(self._hosts)
            self._current_host = host
            self._hosts.remove(host)
            self.connect_to_next_type()

        else:
            if not retry and self.retrycount == 0:
                log.debug("Out of hosts, giving up connecting to %s", self.name)
                self.time_to_reconnect = None
                if self.on_connect_failure:
                    self.on_connect_failure()
                    self.on_connect_failure = None
                else:
                    # shown error dialog
                    self._connection_lost()
            else:
                # try reconnect if connection has failed before auth to server
                self._disconnectedReconnCB()

    def connect_to_next_type(self, retry=False):
        if self.redirected:
            self.disconnect(on_purpose=True)
            self.connect()
            return
        if len(self._connection_types):
            self._current_type = self._connection_types.pop(0)
            if self.last_connection:
                self.last_connection.socket.disconnect()
                self.last_connection = None
                self.connection = None

            if self._current_type == 'ssl':
                # SSL (force TLS on different port than plain)
                # If we do TLS over BOSH, port of XMPP server should be the standard one
                # and TLS should be negotiated because TLS on 5223 is deprecated
                if self._proxy and self._proxy['type']=='bosh':
                    port = self._current_host['port']
                else:
                    port = self._current_host['ssl_port']
            elif self._current_type == 'tls':
                # TLS - negotiate tls after XMPP stream is estabilished
                port = self._current_host['port']
            elif self._current_type == 'plain':
                # plain connection on defined port
                port = self._current_host['port']

            cacerts = os.path.join(common.gajim.DATA_DIR, 'other', 'cacerts.pem')
            if not os.path.exists(cacerts):
                cacerts = ''
            mycerts = common.gajim.MY_CACERTS
            tls_version = gajim.config.get_per('accounts', self.name,
                'tls_version')
            cipher_list = gajim.config.get_per('accounts', self.name,
                'cipher_list')
            secure_tuple = (self._current_type, cacerts, mycerts, tls_version, cipher_list)

            con = nbxmpp.NonBlockingClient(
                domain=self._hostname,
                caller=self,
                idlequeue=gajim.idlequeue)

            self.last_connection = con
            # increase default timeout for server responses
            nbxmpp.dispatcher_nb.DEFAULT_TIMEOUT_SECONDS = \
                self.try_connecting_for_foo_secs
            # FIXME: this is a hack; need a better way
            if self.on_connect_success == self._on_new_account:
                con.RegisterDisconnectHandler(self._on_new_account)

            if self.client_cert and gajim.config.get_per('accounts', self.name,
            'client_cert_encrypted'):
                gajim.nec.push_incoming_event(ClientCertPassphraseEvent(
                    None, conn=self, con=con, port=port,
                    secure_tuple=secure_tuple))
                return
            self.on_client_cert_passphrase('', con, port, secure_tuple)

        else:
            self._connect_to_next_host(retry)

    def on_client_cert_passphrase(self, passphrase, con, port, secure_tuple):
        self.client_cert_passphrase = passphrase

        self.log_hosttype_info(port)
        con.connect(
            hostname=self._current_host['host'],
            port=port,
            on_connect=self.on_connect_success,
            on_proxy_failure=self.on_proxy_failure,
            on_connect_failure=self.connect_to_next_type,
            on_stream_error_cb=self._StreamCB,
            proxy=self._proxy,
            secure_tuple = secure_tuple)

    def log_hosttype_info(self, port):
        msg = '>>>>>> Connecting to %s [%s:%d], type = %s' % (self.name,
                self._current_host['host'], port, self._current_type)
        log.info(msg)
        if self._proxy:
            msg = '>>>>>> '
            if self._proxy['type']=='bosh':
                msg = '%s over BOSH %s' % (msg, self._proxy['bosh_uri'])
            if self._proxy['type'] in ['http', 'socks5'] or self._proxy['bosh_useproxy']:
                msg = '%s over proxy %s:%s' % (msg, self._proxy['host'], self._proxy['port'])
            log.info(msg)

    def _connect_failure(self, con_type=None):
        if not con_type:
            # we are not retrying, and not conecting
            if not self.retrycount and self.connected != 0:
                self.disconnect(on_purpose = True)
                if self._proxy:
                    pritxt = _('Could not connect to "%(host)s" via proxy "%(proxy)s"') %\
                        {'host': self._hostname, 'proxy': self._proxy['host']}
                else:
                    pritxt = _('Could not connect to "%(host)s"') % {'host': \
                        self._hostname}
                sectxt = _('Check your connection or try again later.')
                if self.streamError:
                    # show error dialog
                    key = nbxmpp.NS_XMPP_STREAMS + ' ' + self.streamError
                    if key in nbxmpp.ERRORS:
                        sectxt2 = _('Server replied: %s') % nbxmpp.ERRORS[key][2]
                        gajim.nec.push_incoming_event(InformationEvent(None,
                            conn=self, level='error', pri_txt=pritxt,
                            sec_txt='%s\n%s' % (sectxt2, sectxt)))
                        return
                # show popup
                gajim.nec.push_incoming_event(ConnectionLostEvent(None,
                    conn=self, title=pritxt, msg=sectxt))

    def on_proxy_failure(self, reason):
        log.error('Connection to proxy failed: %s' % reason)
        self.time_to_reconnect = None
        self.on_connect_failure = None
        self.disconnect(on_purpose = True)
        gajim.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
            title=_('Connection to proxy failed'), msg=reason))

    def _connect_success(self, con, con_type):
        if not self.connected: # We went offline during connecting process
            # FIXME - not possible, maybe it was when we used threads
            return
        _con_type = con_type
        if _con_type != self._current_type:
            log.info('Connecting to next type beacuse desired is %s and returned is %s'
                    % (self._current_type, _con_type))
            self.connect_to_next_type()
            return
        con.RegisterDisconnectHandler(self._on_disconnected)
        if _con_type == 'plain' and gajim.config.get_per('accounts', self.name,
        'action_when_plaintext_connection') == 'warn':
            gajim.nec.push_incoming_event(PlainConnectionEvent(None, conn=self,
                xmpp_client=con))
            return True
        if _con_type == 'plain' and gajim.config.get_per('accounts', self.name,
        'action_when_plaintext_connection') == 'disconnect':
            self.disconnect(on_purpose=True)
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            return False
        if _con_type in ('tls', 'ssl') and con.Connection.ssl_lib != 'PYOPENSSL' \
        and gajim.config.get_per('accounts', self.name,
        'warn_when_insecure_ssl_connection') and \
        not self.connection_auto_accepted:
            # Pyopenssl is not used
            gajim.nec.push_incoming_event(InsecureSSLConnectionEvent(None,
                conn=self, xmpp_client=con, conn_type=_con_type))
            return True
        return self.connection_accepted(con, con_type)

    def connection_accepted(self, con, con_type):
        if not con or not con.Connection:
            self.disconnect(on_purpose=True)
            gajim.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not connect to account %s') % self.name,
                msg=_('Connection with account %s has been lost. Retry '
                'connecting.') % self.name))
            return
        self.hosts = []
        self.connection_auto_accepted = False
        self.connected_hostname = self._current_host['host']
        self.on_connect_failure = None
        con.UnregisterDisconnectHandler(self._on_disconnected)
        con.RegisterDisconnectHandler(self._disconnectedReconnCB)
        log.debug('Connected to server %s:%s with %s' % (
                self._current_host['host'], self._current_host['port'], con_type))

        self.last_connection_type = con_type
        if gajim.config.get_per('accounts', self.name, 'anonymous_auth'):
            name = None
        else:
            name = gajim.config.get_per('accounts', self.name, 'name')
        hostname = gajim.config.get_per('accounts', self.name, 'hostname')
        self.connection = con
        try:
            errnum = con.Connection.ssl_errnum
        except AttributeError:
            errnum = 0
        cert = con.Connection.ssl_certificate
        if errnum > 0 and str(errnum) not in gajim.config.get_per('accounts',
        self.name, 'ignore_ssl_errors').split():
            text = _('The authenticity of the %s certificate could be invalid'
                ) % hostname
            if errnum in ssl_error:
                text += _('\nSSL Error: <b>%s</b>') % ssl_error[errnum]
            else:
                text += _('\nUnknown SSL error: %d') % errnum
            fingerprint_sha1 = cert.digest('sha1').decode('utf-8')
            fingerprint_sha256 = cert.digest('sha256').decode('utf-8')
            pem = OpenSSL.crypto.dump_certificate(OpenSSL.crypto.FILETYPE_PEM,
                cert).decode('utf-8')
            gajim.nec.push_incoming_event(SSLErrorEvent(None, conn=self,
                error_text=text, error_num=errnum, cert=pem,
                fingerprint_sha1=fingerprint_sha1,
                fingerprint_sha256=fingerprint_sha256, certificate=cert))
            return True
        if cert:
            fingerprint_sha1 = cert.digest('sha1').decode('utf-8')
            fingerprint_sha256 = cert.digest('sha256').decode('utf-8')
            saved_fingerprint_sha1 = gajim.config.get_per('accounts', self.name,
                'ssl_fingerprint_sha1')
            if saved_fingerprint_sha1:
                # Check sha1 fingerprint
                if fingerprint_sha1 != saved_fingerprint_sha1:
                    gajim.nec.push_incoming_event(FingerprintErrorEvent(None,
                        conn=self, certificate=cert,
                        new_fingerprint_sha1=fingerprint_sha1,
                        new_fingerprint_sha256=fingerprint_sha256))
                    return True
            else:
                gajim.config.set_per('accounts', self.name,
                    'ssl_fingerprint_sha1', fingerprint_sha1)

            saved_fingerprint_sha256 = gajim.config.get_per('accounts', self.name,
                'ssl_fingerprint_sha256')
            if saved_fingerprint_sha256:
                # Check sha256 fingerprint
                if fingerprint_sha256 != saved_fingerprint_sha256:
                    gajim.nec.push_incoming_event(FingerprintErrorEvent(None,
                        conn=self, certificate=con.Connection.ssl_certificate,
                        new_fingerprint_sha1=fingerprint_sha1,
                        new_fingerprint_sha256=fingerprint_sha256))
                    return True
            else:
                gajim.config.set_per('accounts', self.name,
                    'ssl_fingerprint_sha256', fingerprint_sha256)

            if not check_X509.check_certificate(cert, hostname) and \
            '100' not in gajim.config.get_per('accounts', self.name,
            'ignore_ssl_errors').split():
                pem = OpenSSL.crypto.dump_certificate(
                    OpenSSL.crypto.FILETYPE_PEM, cert).decode('utf-8')
                txt = _('The authenticity of the %s certificate could be '
                    'invalid.\nThe certificate does not cover this domain.') %\
                    hostname
                gajim.nec.push_incoming_event(SSLErrorEvent(None, conn=self,
                    error_text=txt, error_num=100, cert=pem,
                    fingerprint_sha1=fingerprint_sha1,
                    fingerprint_sha256=fingerprint_sha256, certificate=cert))
                return True

        self._register_handlers(con, con_type)
        auth_mechs = gajim.config.get_per('accounts', self.name, 'authentication_mechanisms')
        auth_mechs = auth_mechs.split()
        for mech in auth_mechs:
            if mech not in nbxmpp.auth_nb.SASL_AUTHENTICATION_MECHANISMS | set(['XEP-0078']):
                log.warning("Unknown authentication mechanisms %s" % mech)
        if len(auth_mechs) == 0:
            auth_mechs = None
        con.auth(user=name, password=self.password,
            resource=self.server_resource, sasl=True, on_auth=self.__on_auth, auth_mechs=auth_mechs)

    def ssl_certificate_accepted(self):
        if not self.connection:
            self.disconnect(on_purpose=True)
            gajim.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not connect to account %s') % self.name,
                msg=_('Connection with account %s has been lost. Retry '
                'connecting.') % self.name))
            return
        if gajim.config.get_per('accounts', self.name, 'anonymous_auth'):
            name = None
        else:
            name = gajim.config.get_per('accounts', self.name, 'name')
        self._register_handlers(self.connection, 'ssl')
        self.connection.auth(name, self.password, self.server_resource, 1,
                self.__on_auth)

    def _register_handlers(self, con, con_type):
        self.peerhost = con.get_peerhost()
        gajim.con_types[self.name] = con_type
        # notify the gui about con_type
        gajim.nec.push_incoming_event(ConnectionTypeEvent(None,
            conn=self, connection_type=con_type))
        ConnectionHandlers._register_handlers(self, con, con_type)

    def __on_auth(self, con, auth):
        if not con:
            self.disconnect(on_purpose=True)
            gajim.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not connect to "%s"') % self._hostname,
                msg=_('Check your connection or try again later.')))
            if self.on_connect_auth:
                self.on_connect_auth(None)
                self.on_connect_auth = None
                return
        if not self.connected: # We went offline during connecting process
            if self.on_connect_auth:
                self.on_connect_auth(None)
                self.on_connect_auth = None
                return
        if hasattr(con, 'Resource'):
            self.server_resource = con.Resource
        if gajim.config.get_per('accounts', self.name, 'anonymous_auth'):
            # Get jid given by server
            old_jid = gajim.get_jid_from_account(self.name)
            gajim.config.set_per('accounts', self.name, 'name', con.User)
            new_jid = gajim.get_jid_from_account(self.name)
            gajim.nec.push_incoming_event(AnonymousAuthEvent(None,
                conn=self, old_jid=old_jid, new_jid=new_jid))
        if auth:
            self.last_io = gajim.idlequeue.current_time()
            self.connected = 2
            self.retrycount = 0
            if self.on_connect_auth:
                self.on_connect_auth(con)
                self.on_connect_auth = None
        else:
            if not gajim.config.get_per('accounts', self.name, 'savepass'):
                # Forget password, it's wrong
                self.password = None
            gajim.log.debug("Couldn't authenticate to %s" % self._hostname)
            self.disconnect(on_purpose = True)
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            gajim.nec.push_incoming_event(InformationEvent(None, conn=self,
                level='error', pri_txt=_('Authentication failed with "%s"') % \
                self._hostname, sec_txt=_('Please check your login and password'
                ' for correctness.')))
            if self.on_connect_auth:
                self.on_connect_auth(None)
                self.on_connect_auth = None
    # END connect

    def add_lang(self, stanza):
        if self.lang:
            stanza.setAttr('xml:lang', self.lang)

    def get_privacy_lists(self):
        if not gajim.account_is_connected(self.name):
            return
        nbxmpp.features_nb.getPrivacyLists(self.connection)

    def send_keepalive(self):
        # nothing received for the last foo seconds
        if self.connection:
            self.connection.send(' ')

    def _on_xmpp_ping_answer(self, iq_obj):
        id_ = iq_obj.getAttr('id')
        assert id_ == self.awaiting_xmpp_ping_id
        self.awaiting_xmpp_ping_id = None

    def sendPing(self, pingTo=None):
        """
        Send XMPP Ping (XEP-0199) request. If pingTo is not set, ping is sent to
        server to detect connection failure at application level
        """
        if not gajim.account_is_connected(self.name):
            return
        id_ = self.connection.getAnID()
        if pingTo:
            to = pingTo.get_full_jid()
            gajim.nec.push_incoming_event(PingSentEvent(None, conn=self,
                contact=pingTo))
        else:
            to = gajim.config.get_per('accounts', self.name, 'hostname')
            self.awaiting_xmpp_ping_id = id_
        iq = nbxmpp.Iq('get', to=to)
        iq.addChild(name='ping', namespace=nbxmpp.NS_PING)
        iq.setID(id_)
        def _on_response(resp):
            timePong = time_time()
            if not nbxmpp.isResultNode(resp):
                gajim.nec.push_incoming_event(PingErrorEvent(None, conn=self,
                    contact=pingTo))
                return
            timeDiff = round(timePong - timePing, 2)
            gajim.nec.push_incoming_event(PingReplyEvent(None, conn=self,
                contact=pingTo, seconds=timeDiff))
        if pingTo:
            timePing = time_time()
            self.connection.SendAndCallForResponse(iq, _on_response)
        else:
            self.connection.SendAndCallForResponse(iq, self._on_xmpp_ping_answer)
            gajim.idlequeue.set_alarm(self.check_pingalive, gajim.config.get_per(
                'accounts', self.name, 'time_for_ping_alive_answer'))

    def get_active_default_lists(self):
        if not gajim.account_is_connected(self.name):
            return
        nbxmpp.features_nb.getActiveAndDefaultPrivacyLists(self.connection)

    def del_privacy_list(self, privacy_list):
        if not gajim.account_is_connected(self.name):
            return
        def _on_del_privacy_list_result(result):
            if result:
                gajim.nec.push_incoming_event(PrivacyListRemovedEvent(None,
                    conn=self, list_name=privacy_list))
            else:
                gajim.nec.push_incoming_event(InformationEvent(None, conn=self,
                    level='error', pri_txt=_('Error while removing privacy '
                    'list'), sec_txt=_('Privacy list %s has not been removed. '
                    'It is maybe active in one of your connected resources. '
                    'Deactivate it and try again.') % privacy_list))
        nbxmpp.features_nb.delPrivacyList(self.connection, privacy_list,
            _on_del_privacy_list_result)

    def get_privacy_list(self, title):
        if not gajim.account_is_connected(self.name):
            return
        nbxmpp.features_nb.getPrivacyList(self.connection, title)

    def set_privacy_list(self, listname, tags):
        if not gajim.account_is_connected(self.name):
            return
        nbxmpp.features_nb.setPrivacyList(self.connection, listname, tags)

    def set_active_list(self, listname):
        if not gajim.account_is_connected(self.name):
            return
        nbxmpp.features_nb.setActivePrivacyList(self.connection, listname,
            'active')

    def set_default_list(self, listname):
        if not gajim.account_is_connected(self.name):
            return
        nbxmpp.features_nb.setDefaultPrivacyList(self.connection, listname)

    def build_privacy_rule(self, name, action, order=1):
        """
        Build a Privacy rule stanza for invisibility
        """
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVACY, xmlns='')
        l = iq.setQuery().setTag('list', {'name': name})
        i = l.setTag('item', {'action': action, 'order': str(order)})
        i.setTag('presence-out')
        return iq

    def build_invisible_rule(self):
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVACY, xmlns='')
        l = iq.setQuery().setTag('list', {'name': 'invisible'})
        if self.name in gajim.interface.status_sent_to_groups and \
        len(gajim.interface.status_sent_to_groups[self.name]) > 0:
            for group in gajim.interface.status_sent_to_groups[self.name]:
                i = l.setTag('item', {'type': 'group', 'value': group,
                        'action': 'allow', 'order': '1'})
                i.setTag('presence-out')
        if self.name in gajim.interface.status_sent_to_users and \
        len(gajim.interface.status_sent_to_users[self.name]) > 0:
            for jid in gajim.interface.status_sent_to_users[self.name]:
                i = l.setTag('item', {'type': 'jid', 'value': jid,
                        'action': 'allow', 'order': '2'})
                i.setTag('presence-out')
        i = l.setTag('item', {'action': 'deny', 'order': '3'})
        i.setTag('presence-out')
        return iq

    def set_invisible_rule(self):
        if not gajim.account_is_connected(self.name):
            return
        iq = self.build_invisible_rule()
        self.connection.send(iq)

    def activate_privacy_rule(self, name):
        """
        Activate a privacy rule
        """
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq('set', nbxmpp.NS_PRIVACY, xmlns='')
        iq.setQuery().setTag('active', {'name': name})
        self.connection.send(iq)

    def get_max_blocked_list_order(self):
        max_order = 0
        for rule in self.blocked_list:
            order = int(rule['order'])
            if order > max_order:
                max_order = order
        return max_order

    def block_contacts(self, contact_list, message):
        if not self.privacy_rules_supported:
            if self.blocking_supported: #XEP-0191
                iq = nbxmpp.Iq('set', xmlns='')
                query = iq.setQuery(name='block')
                query.setNamespace(nbxmpp.NS_BLOCKING)
                for contact in contact_list:
                    self.blocked_contacts.append(contact.jid)
                    query.addChild(name='item', attrs={'jid': contact.jid})
                self.connection.send(iq)
            return
        for contact in contact_list:
            self.send_custom_status('offline', message, contact.jid)
            max_order = self.get_max_blocked_list_order()
            new_rule = {'order': str(max_order + 1), 'type': 'jid', 'action': 'deny',
                'value' : contact.jid, 'child': ['message', 'iq',
                'presence-out']}
            self.blocked_list.append(new_rule)
            self.blocked_contacts.append(contact.jid)
        self.set_privacy_list('block', self.blocked_list)
        if len(self.blocked_list) == 1:
            self.set_active_list('block')
            self.set_default_list('block')
        self.get_privacy_list('block')

    def unblock_contacts(self, contact_list):
        if not self.privacy_rules_supported:
            if self.blocking_supported: #XEP-0191
                iq = nbxmpp.Iq('set', xmlns='')
                query = iq.setQuery(name='unblock')
                query.setNamespace(nbxmpp.NS_BLOCKING)
                for contact in contact_list:
                    self.blocked_contacts.append(contact.jid)
                    query.addChild(name='item', attrs={'jid': contact.jid})
                self.connection.send(iq)
            return
        self.new_blocked_list = []
        self.to_unblock = []
        for contact in contact_list:
            self.to_unblock.append(contact.jid)
            if contact.jid in self.blocked_contacts:
                self.blocked_contacts.remove(contact.jid)
        for rule in self.blocked_list:
            if rule['action'] != 'deny' or rule['type'] != 'jid' \
            or rule['value'] not in self.to_unblock:
                self.new_blocked_list.append(rule)
        self.set_privacy_list('block', self.new_blocked_list)
        self.get_privacy_list('block')
        if len(self.new_blocked_list) == 0:
            self.blocked_list = []
            self.blocked_contacts = []
            self.blocked_groups = []
            self.set_default_list('')
            self.set_active_list('')
            self.del_privacy_list('block')
        if not gajim.interface.roster.regroup:
            show = gajim.SHOW_LIST[self.connected]
        else:   # accounts merged
            show = helpers.get_global_show()
        if show == 'invisible':
            return
        for contact in contact_list:
            self.send_custom_status(show, self.status, contact.jid)

    def block_group(self, group, contact_list, message):
        if not self.privacy_rules_supported:
            return
        self.blocked_groups.append(group)
        for contact in contact_list:
            self.send_custom_status('offline', message, contact.jid)
        max_order = self.get_max_blocked_list_order()
        new_rule = {'order': str(max_order + 1), 'type': 'group', 'action': 'deny',
            'value' : group, 'child': ['message', 'iq', 'presence-out']}
        self.blocked_list.append(new_rule)
        self.set_privacy_list('block', self.blocked_list)
        if len(self.blocked_list) == 1:
            self.set_active_list('block')
            self.set_default_list('block')
        self.get_privacy_list('block')

    def unblock_group(self, group, contact_list):
        if not self.privacy_rules_supported:
            return
        if group in self.blocked_groups:
            self.blocked_groups.remove(group)
        self.new_blocked_list = []
        for rule in self.blocked_list:
            if rule['action'] != 'deny' or rule['type'] != 'group' or \
            rule['value'] != group:
                self.new_blocked_list.append(rule)
        self.set_privacy_list('block', self.new_blocked_list)
        self.get_privacy_list('block')
        if len(self.new_blocked_list) == 0:
            self.blocked_list = []
            self.blocked_contacts = []
            self.blocked_groups = []
            self.set_default_list('')
            self.set_active_list('')
            self.del_privacy_list('block')
        if not gajim.interface.roster.regroup:
            show = gajim.SHOW_LIST[self.connected]
        else:   # accounts merged
            show = helpers.get_global_show()
        if show == 'invisible':
            return
        for contact in contact_list:
            self.send_custom_status(show, self.status, contact.jid)

    def send_invisible_presence(self, msg, signed, initial = False):
        if not gajim.account_is_connected(self.name):
            return
        if not self.privacy_rules_supported:
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show=gajim.SHOW_LIST[self.connected]))
            gajim.nec.push_incoming_event(InformationEvent(None, conn=self,
                level='error', pri_txt=_('Invisibility not supported'),
                sec_txt=_('Account %s doesn\'t support invisibility.') % \
                self.name))
            return
        # If we are already connected, and privacy rules are supported, send
        # offline presence first as it's required by XEP-0126
        if self.connected > 1 and self.privacy_rules_supported:
            self.on_purpose = True
            p = nbxmpp.Presence(typ='unavailable')
            p = self.add_sha(p, False)
            if msg:
                p.setStatus(msg)
            self.remove_all_transfers()
            self.connection.send(p)

        # try to set the privacy rule
        iq = self.build_invisible_rule()
        self.connection.SendAndCallForResponse(iq, self._continue_invisible,
                {'msg': msg, 'signed': signed, 'initial': initial})

    def _continue_invisible(self, con, iq_obj, msg, signed, initial):
        if iq_obj.getType() == 'error': # server doesn't support privacy lists
            return
        # active the privacy rule
        self.privacy_rules_supported = True
        self.activate_privacy_rule('invisible')
        self.connected = gajim.SHOW_LIST.index('invisible')
        self.status = msg
        priority = gajim.get_priority(self.name, 'invisible')
        p = nbxmpp.Presence(priority=priority)
        p = self.add_sha(p, True)
        if msg:
            p.setStatus(msg)
        if signed:
            p.setTag(nbxmpp.NS_SIGNED + ' x').setData(signed)
        self.connection.send(p)
        self.priority = priority
        gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='invisible'))
        if initial:
            # ask our VCard
            self.request_vcard(None)

            # Get bookmarks from private namespace
            self.get_bookmarks()

            # Get annotations
            self.get_annotations()

            # Inform GUI we just signed in
            gajim.nec.push_incoming_event(SignedInEvent(None, conn=self))

    def get_signed_presence(self, msg, callback = None):
        if gajim.config.get_per('accounts', self.name, 'gpg_sign_presence'):
            return self.get_signed_msg(msg, callback)
        return ''

    def connect_and_auth(self):
        self.on_connect_success = self._connect_success
        self.on_connect_failure = self._connect_failure
        self.connect()

    def connect_and_init(self, show, msg, sign_msg):
        self.continue_connect_info = [show, msg, sign_msg]
        self.on_connect_auth = self._discover_server_at_connection
        self.connect_and_auth()

    def _discover_server_at_connection(self, con):
        self.connection = con
        if not gajim.account_is_connected(self.name):
            return
        self.connection.set_send_timeout(self.keepalives, self.send_keepalive)
        self.connection.set_send_timeout2(self.pingalives, self.sendPing)
        self.connection.onreceive(None)

        self.privacy_rules_requested = False

        # If we are not resuming, we ask for discovery info
        # and archiving preferences
        if not self.sm.supports_sm or (not self.sm.resuming and self.sm.enabled):
            self.request_message_archiving_preferences()
            self.discoverInfo(gajim.config.get_per('accounts', self.name,
                'hostname'), id_prefix='Gajim_')

        self.sm.resuming = False # back to previous state
        # Discover Stun server(s)
        gajim.resolver.resolve('_stun._udp.' + helpers.idn_to_ascii(
                self.connected_hostname), self._on_stun_resolved)

    def _on_stun_resolved(self, host, result_array):
        if len(result_array) != 0:
            self._stun_servers = self._hosts = [i for i in result_array]

    def _request_privacy(self):
        if not gajim.account_is_connected(self.name) or not self.connection:
            return
        iq = nbxmpp.Iq('get', nbxmpp.NS_PRIVACY, xmlns='')
        id_ = self.connection.getAnID()
        iq.setID(id_)
        self.awaiting_answers[id_] = (PRIVACY_ARRIVED, )
        self.connection.send(iq)

    def _nec_agent_info_error_received(self, obj):
        if obj.conn.name != self.name:
            return
        if obj.id_[:6] == 'Gajim_':
            if not self.privacy_rules_requested:
                self.privacy_rules_requested = True
                self._request_privacy()

    def _nec_agent_info_received(self, obj):
        if obj.conn.name != self.name:
            return
        is_muc = False
        transport_type = ''
        for identity in obj.identities:
            if 'category' in identity and identity['category'] in ('gateway',
            'headline') and 'type' in identity:
                transport_type = identity['type']
            if 'category' in identity and identity['category'] == 'server' and \
            'type' in identity and identity['type'] == 'im':
                transport_type = 'jabber' # it's a jabber server
            if 'category' in identity and identity['category'] == 'conference' \
            and 'type' in identity and identity['type'] == 'text':
                is_muc = True

        if transport_type != '' and obj.fjid not in gajim.transport_type:
            gajim.transport_type[obj.fjid] = transport_type
            gajim.logger.save_transport_type(obj.fjid, transport_type)

        if obj.id_[:6] == 'Gajim_':
            hostname = gajim.config.get_per('accounts', self.name, 'hostname')
            our_jid = gajim.get_jid_from_account(self.name)
            if obj.fjid == hostname:
                if nbxmpp.NS_GMAILNOTIFY in obj.features:
                    gajim.gmail_domains.append(obj.fjid)
                    self.request_gmail_notifications()
                if nbxmpp.NS_SECLABEL in obj.features:
                    self.seclabel_supported = True
                for identity in obj.identities:
                    if identity['category'] == 'pubsub' and identity.get(
                    'type') == 'pep':
                        self.pep_supported = True
                        break
                if nbxmpp.NS_VCARD in obj.features:
                    self.vcard_supported = True
                if nbxmpp.NS_PUBSUB in obj.features:
                    self.pubsub_supported = True
                    if nbxmpp.NS_PUBSUB_PUBLISH_OPTIONS in obj.features:
                        self.pubsub_publish_options_supported = True
                    else:
                        # Remove stored bookmarks accessible to everyone.
                        self.send_pb_purge(our_jid, 'storage:bookmarks')
                        self.send_pb_delete(our_jid, 'storage:bookmarks')
                if nbxmpp.NS_ARCHIVE in obj.features:
                    self.archiving_supported = True
                if nbxmpp.NS_ARCHIVE_AUTO in obj.features:
                    self.archive_auto_supported = True
                if nbxmpp.NS_ARCHIVE_MANAGE in obj.features:
                    self.archive_manage_supported = True
                if nbxmpp.NS_ARCHIVE_MANUAL in obj.features:
                    self.archive_manual_supported = True
                if nbxmpp.NS_ARCHIVE_PREF in obj.features:
                    self.archive_pref_supported = True
                if nbxmpp.NS_BLOCKING in obj.features:
                    self.blocking_supported = True
                if nbxmpp.NS_ADDRESS in obj.features:
                    self.addressing_supported = True
                if nbxmpp.NS_CARBONS in obj.features and gajim.config.get_per(
                'accounts', self.name, 'enable_message_carbons'):
                    self.carbons_enabled = True
                    # Server supports carbons, activate it
                    iq = nbxmpp.Iq('set')
                    iq.setTag('enable', namespace=nbxmpp.NS_CARBONS)
                    self.connection.send(iq)
            if nbxmpp.NS_BYTESTREAM in obj.features and \
            gajim.config.get_per('accounts', self.name, 'use_ft_proxies'):
                our_fjid = helpers.parse_jid(our_jid + '/' + \
                    self.server_resource)
                testit = gajim.config.get_per('accounts', self.name,
                    'test_ft_proxies_on_startup')
                gajim.proxy65_manager.resolve(obj.fjid, self.connection,
                    our_fjid, default=self.name, testit=testit)
            if nbxmpp.NS_MUC in obj.features and is_muc:
                type_ = transport_type or 'jabber'
                self.muc_jid[type_] = obj.fjid
            if transport_type:
                if transport_type in self.available_transports:
                    self.available_transports[transport_type].append(obj.fjid)
                else:
                    self.available_transports[transport_type] = [obj.fjid]
            if not self.privacy_rules_requested:
                self.privacy_rules_requested = True
                self._request_privacy()

    def send_custom_status(self, show, msg, jid):
        if not show in gajim.SHOW_LIST:
            return -1
        if not gajim.account_is_connected(self.name):
            return
        sshow = helpers.get_xmpp_show(show)
        if not msg:
            msg = ''
        if show == 'offline':
            p = nbxmpp.Presence(typ='unavailable', to=jid)
            p = self.add_sha(p, False)
            if msg:
                p.setStatus(msg)
        else:
            signed = self.get_signed_presence(msg)
            priority = gajim.get_priority(self.name, sshow)
            p = nbxmpp.Presence(typ=None, priority=priority, show=sshow, to=jid)
            p = self.add_sha(p)
            if msg:
                p.setStatus(msg)
            if signed:
                p.setTag(nbxmpp.NS_SIGNED + ' x').setData(signed)
        self.connection.send(p)

    def _change_to_invisible(self, msg):
        signed = self.get_signed_presence(msg)
        self.send_invisible_presence(msg, signed)

    def _change_from_invisible(self):
        if self.privacy_rules_supported:
            if self.blocked_list:
                self.activate_privacy_rule('block')
            else:
                iq = self.build_privacy_rule('visible', 'allow')
                self.connection.send(iq)
                self.activate_privacy_rule('visible')

    def _update_status(self, show, msg):
        xmpp_show = helpers.get_xmpp_show(show)
        priority = gajim.get_priority(self.name, xmpp_show)
        p = nbxmpp.Presence(typ=None, priority=priority, show=xmpp_show)
        p = self.add_sha(p)
        if msg:
            p.setStatus(msg)
        signed = self.get_signed_presence(msg)
        if signed:
            p.setTag(nbxmpp.NS_SIGNED + ' x').setData(signed)
        if self.connection:
            self.connection.send(p)
            self.priority = priority
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show=show))

    def send_motd(self, jid, subject='', msg='', xhtml=None):
        if not gajim.account_is_connected(self.name):
            return
        msg_iq = nbxmpp.Message(to=jid, body=msg, subject=subject,
            xhtml=xhtml)

        self.connection.send(msg_iq)

    def _nec_message_outgoing(self, obj):
        if obj.account != self.name:
            return

        def cb(jid, msg, keyID, forward_from, session, original_message,
        subject, type_, msg_iq, xhtml):
            if isinstance(msg_iq, list):
                for iq in msg_iq:
                    msg_id = self.connection.send(iq, now=obj.now)
            else:
                msg_id = self.connection.send(msg_iq, now=obj.now)
            gajim.nec.push_incoming_event(MessageSentEvent(None, conn=self,
                jid=jid, message=msg, keyID=keyID, chatstate=obj.chatstate))
            if obj.callback:
                obj.callback(msg_iq, *obj.callback_args)

            if not obj.is_loggable:
                return
            if isinstance(jid, list):
                for j in jid:
                    if session is None:
                        session = self.get_or_create_session(j, '')
                    self.log_message(j, msg, forward_from, session,
                        original_message, subject, type_, xhtml)
            else:
                self.log_message(jid, msg, forward_from, session,
                    original_message, subject, type_, xhtml)

        self._prepare_message(obj.jid, obj.message, obj.keyID, type_=obj.type_,
            subject=obj.subject, chatstate=obj.chatstate, msg_id=obj.msg_id,
            resource=obj.resource, user_nick=obj.user_nick, xhtml=obj.xhtml,
            label=obj.label, session=obj.session, forward_from=obj.forward_from,
            form_node=obj.form_node, original_message=obj.original_message,
            delayed=obj.delayed, attention=obj.attention,
            correction_msg=obj.correction_msg, callback=cb)

    def send_contacts(self, contacts, fjid, type_='message'):
        """
        Send contacts with RosterX (Xep-0144)
        """
        if not gajim.account_is_connected(self.name):
            return
        if type_ == 'message':
            if len(contacts) == 1:
                msg = _('Sent contact: "%s" (%s)') % (contacts[0].get_full_jid(),
                    contacts[0].get_shown_name())
            else:
                msg = _('Sent contacts:')
                for contact in contacts:
                    msg += '\n "%s" (%s)' % (contact.get_full_jid(),
                        contact.get_shown_name())
            stanza = nbxmpp.Message(to=gajim.get_jid_without_resource(fjid),
                body=msg)
        elif type_ == 'iq':
            stanza = nbxmpp.Iq(to=fjid, typ='set')
        x = stanza.addChild(name='x', namespace=nbxmpp.NS_ROSTERX)
        for contact in contacts:
            x.addChild(name='item', attrs={'action': 'add', 'jid': contact.jid,
                'name': contact.get_shown_name()})
        self.connection.send(stanza)

    def send_stanza(self, stanza):
        """
        Send a stanza untouched
        """
        if not self.connection:
            return
        self.connection.send(stanza)

    def ack_subscribed(self, jid):
        if not gajim.account_is_connected(self.name):
            return
        log.debug('ack\'ing subscription complete for %s' % jid)
        p = nbxmpp.Presence(jid, 'subscribe')
        self.connection.send(p)

    def ack_unsubscribed(self, jid):
        if not gajim.account_is_connected(self.name):
            return
        log.debug('ack\'ing unsubscription complete for %s' % jid)
        p = nbxmpp.Presence(jid, 'unsubscribe')
        self.connection.send(p)

    def request_subscription(self, jid, msg='', name='', groups=[],
    auto_auth=False, user_nick=''):
        if not gajim.account_is_connected(self.name):
            return
        log.debug('subscription request for %s' % jid)
        if auto_auth:
            self.jids_for_auto_auth.append(jid)
        # RFC 3921 section 8.2
        infos = {'jid': jid}
        if name:
            infos['name'] = name
        iq = nbxmpp.Iq('set', nbxmpp.NS_ROSTER)
        q = iq.setQuery()
        item = q.addChild('item', attrs=infos)
        for g in groups:
            item.addChild('group').setData(g)
        self.connection.send(iq)

        p = nbxmpp.Presence(jid, 'subscribe')
        if user_nick:
            p.setTag('nick', namespace = nbxmpp.NS_NICK).setData(user_nick)
        p = self.add_sha(p)
        if msg:
            p.setStatus(msg)
        self.connection.send(p)

    def send_authorization(self, jid):
        if not gajim.account_is_connected(self.name):
            return
        p = nbxmpp.Presence(jid, 'subscribed')
        p = self.add_sha(p)
        self.connection.send(p)

    def refuse_authorization(self, jid):
        if not gajim.account_is_connected(self.name):
            return
        p = nbxmpp.Presence(jid, 'unsubscribed')
        p = self.add_sha(p)
        self.connection.send(p)

    def unsubscribe(self, jid, remove_auth = True):
        if not gajim.account_is_connected(self.name):
            return
        if remove_auth:
            self.connection.getRoster().delItem(jid)
            jid_list = gajim.config.get_per('contacts')
            for j in jid_list:
                if j.startswith(jid):
                    gajim.config.del_per('contacts', j)
        else:
            self.connection.getRoster().Unsubscribe(jid)
            self.update_contact(jid, '', [])

    def unsubscribe_agent(self, agent):
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq('set', nbxmpp.NS_REGISTER, to=agent)
        iq.setQuery().setTag('remove')
        id_ = self.connection.getAnID()
        iq.setID(id_)
        self.awaiting_answers[id_] = (AGENT_REMOVED, agent)
        self.connection.send(iq)
        self.connection.getRoster().delItem(agent)

    def send_new_account_infos(self, form, is_form):
        if is_form:
            # Get username and password and put them in new_account_info
            for field in form.iter_fields():
                if field.var == 'username':
                    self.new_account_info['name'] = field.value
                if field.var == 'password':
                    self.new_account_info['password'] = field.value
        else:
            # Get username and password and put them in new_account_info
            if 'username' in form:
                self.new_account_info['name'] = form['username']
            if 'password' in form:
                self.new_account_info['password'] = form['password']
        self.new_account_form = form
        self.new_account(self.name, self.new_account_info)

    def new_account(self, name, config, sync=False):
        # If a connection already exist we cannot create a new account
        if self.connection:
            return
        self._hostname = config['hostname']
        self.new_account_info = config
        self.name = name
        self.on_connect_success = self._on_new_account
        self.on_connect_failure = self._on_new_account
        self.connect(config)

    def _on_new_account(self, con=None, con_type=None):
        if not con_type:
            if len(self._connection_types) or len(self._hosts):
                # There are still other way to try to connect
                return
            reason = _('Could not connect to "%s"') % self._hostname
            gajim.nec.push_incoming_event(NewAccountNotConnectedEvent(None,
                conn=self, reason=reason))
            return
        self.on_connect_failure = None
        self.connection = con
        nbxmpp.features_nb.getRegInfo(con, self._hostname)

    def request_os_info(self, jid, resource, groupchat_jid=None):
        """
        groupchat_jid is used when we want to send a request to a real jid and
        act as if the answer comes from the groupchat_jid
        """
        if not gajim.account_is_connected(self.name):
            return
        # If we are invisible, do not request
        if self.connected == gajim.SHOW_LIST.index('invisible'):
            self.dispatch('OS_INFO', (jid, resource, _('Not fetched because of invisible status'), _('Not fetched because of invisible status')))
            return
        to_whom_jid = jid
        if resource:
            to_whom_jid += '/' + resource
        iq = nbxmpp.Iq(to=to_whom_jid, typ='get', queryNS=nbxmpp.NS_VERSION)
        id_ = self.connection.getAnID()
        iq.setID(id_)
        if groupchat_jid:
            self.groupchat_jids[id_] = groupchat_jid
        self.version_ids.append(id_)
        self.connection.send(iq)

    def request_entity_time(self, jid, resource, groupchat_jid=None):
        """
        groupchat_jid is used when we want to send a request to a real jid and
        act as if the answer comes from the groupchat_jid
        """
        if not gajim.account_is_connected(self.name):
            return
        # If we are invisible, do not request
        if self.connected == gajim.SHOW_LIST.index('invisible'):
            self.dispatch('ENTITY_TIME', (jid, resource, _('Not fetched because of invisible status')))
            return
        to_whom_jid = jid
        if resource:
            to_whom_jid += '/' + resource
        iq = nbxmpp.Iq(to=to_whom_jid, typ='get')
        iq.addChild('time', namespace=nbxmpp.NS_TIME_REVISED)
        id_ = self.connection.getAnID()
        iq.setID(id_)
        if groupchat_jid:
            self.groupchat_jids[id_] = groupchat_jid
        self.entity_time_ids.append(id_)
        self.connection.send(iq)

    def request_gateway_prompt(self, jid, prompt=None):
        def _on_prompt_result(resp):
            gajim.nec.push_incoming_event(GatewayPromptReceivedEvent(None,
                conn=self, stanza=resp))
        if prompt:
            typ_ = 'set'
        else:
            typ_ = 'get'
        iq = nbxmpp.Iq(typ=typ_, to=jid)
        query = iq.addChild(name='query', namespace=nbxmpp.NS_GATEWAY)
        if prompt:
            query.setTagData('prompt', prompt)
        self.connection.SendAndCallForResponse(iq, _on_prompt_result)

    def get_settings(self):
        """
        Get Gajim settings as described in XEP 0049
        """
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get')
        iq2 = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        iq2.addChild(name='gajim', namespace='gajim:prefs')
        self.connection.send(iq)

    def seclabel_catalogue(self, to, callback):
        if not gajim.account_is_connected(self.name):
            return
        self.seclabel_catalogue_request(to, callback)
        server = gajim.get_jid_from_account(self.name).split("@")[1] # Really, no better way?
        iq = nbxmpp.Iq(typ='get', to=server)
        iq2 = iq.addChild(name='catalog', namespace=nbxmpp.NS_SECLABEL_CATALOG)
        iq2.setAttr('to', to)
        self.connection.send(iq)

    def _nec_privacy_list_received(self, obj):
        if obj.conn.name != self.name:
            return
        if obj.list_name != 'block':
            return
        self.blocked_contacts = []
        self.blocked_groups = []
        self.blocked_list = []
        self.blocked_all = False
        for rule in obj.rules:
            if rule['action'] == 'allow':
                if not 'type' in rule:
                    self.blocked_all = False
                elif rule['type'] == 'jid' and rule['value'] in \
                self.blocked_contacts:
                    self.blocked_contacts.remove(rule['value'])
                elif rule['type'] == 'group' and rule['value'] in \
                self.blocked_groups:
                    self.blocked_groups.remove(rule['value'])
            elif rule['action'] == 'deny':
                if not 'type' in rule:
                    self.blocked_all = True
                elif rule['type'] == 'jid' and rule['value'] not in \
                self.blocked_contacts:
                    self.blocked_contacts.append(rule['value'])
                elif rule['type'] == 'group' and rule['value'] not in \
                self.blocked_groups:
                    self.blocked_groups.append(rule['value'])
            self.blocked_list.append(rule)

    def _request_bookmarks_xml(self):
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get')
        iq2 = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        iq2.addChild(name='storage', namespace='storage:bookmarks')
        self.connection.send(iq)

    def _check_bookmarks_received(self):
        if not self.bookmarks:
            self._request_bookmarks_xml()

    def get_bookmarks(self, storage_type=None):
        """
        Get Bookmarks from storage or PubSub if supported as described in XEP
        0048

        storage_type can be set to xml to force request to xml storage
        """
        if not gajim.account_is_connected(self.name):
            return
        if self.pubsub_supported and storage_type != 'xml':
            self.send_pb_retrieve('', 'storage:bookmarks')
            # some server (ejabberd) are so slow to answer that we request via XML
            # if we don't get answer in the next 30 seconds
            gajim.idlequeue.set_alarm(self._check_bookmarks_received, 30)
        else:
            self._request_bookmarks_xml()

    def store_bookmarks(self, storage_type=None):
        """
        Send bookmarks to the storage namespace or PubSub if supported

        storage_type can be set to 'pubsub' or 'xml' so store in only one method
        else it will be stored on both
        """
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Node(tag='storage', attrs={'xmlns': 'storage:bookmarks'})
        for bm in self.bookmarks:
            iq2 = iq.addChild(name = "conference")
            iq2.setAttr('jid', bm['jid'])
            iq2.setAttr('autojoin', bm['autojoin'])
            iq2.setAttr('minimize', bm['minimize'])
            iq2.setAttr('name', bm['name'])
            # Only add optional elements if not empty
            # Note: need to handle both None and '' as empty
            #   thus shouldn't use "is not None"
            if bm.get('nick', None):
                iq2.setTagData('nick', bm['nick'])
            if bm.get('password', None):
                iq2.setTagData('password', bm['password'])
            if bm.get('print_status', None):
                iq2.setTagData('print_status', bm['print_status'])

        if self.pubsub_supported and self.pubsub_publish_options_supported and \
        storage_type != 'xml':
            options = nbxmpp.Node(nbxmpp.NS_DATA + ' x',
                attrs={'type': 'submit'})
            f = options.addChild('field', attrs={'var': 'FORM_TYPE',
                'type': 'hidden'})
            f.setTagData('value', nbxmpp.NS_PUBSUB_PUBLISH_OPTIONS)
            f = options.addChild('field', attrs={'var': 'pubsub#persist_items'})
            f.setTagData('value', 'true')
            f = options.addChild('field', attrs={'var': 'pubsub#access_model'})
            f.setTagData('value', 'whitelist')
            self.send_pb_publish('', 'storage:bookmarks', iq, 'current',
                options=options)
        if storage_type != 'pubsub':
            iqA = nbxmpp.Iq(typ='set')
            iqB = iqA.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
            iqB.addChild(node=iq)
            self.connection.send(iqA)

    def get_annotations(self):
        """
        Get Annonations from storage as described in XEP 0048, and XEP 0145
        """
        self.annotations = {}
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get')
        iq2 = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        iq2.addChild(name='storage', namespace='storage:rosternotes')
        self.connection.send(iq)

    def store_annotations(self):
        """
        Set Annonations in private storage as described in XEP 0048, and XEP 0145
        """
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set')
        iq2 = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        iq3 = iq2.addChild(name='storage', namespace='storage:rosternotes')
        for jid in self.annotations.keys():
            if self.annotations[jid]:
                iq4 = iq3.addChild(name = "note")
                iq4.setAttr('jid', jid)
                iq4.setData(self.annotations[jid])
        self.connection.send(iq)

    def get_roster_delimiter(self):
        """
        Get roster group delimiter from storage as described in XEP 0083
        """
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get')
        iq2 = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        iq2.addChild(name='roster', namespace='roster:delimiter')
        id_ = self.connection.getAnID()
        iq.setID(id_)
        self.awaiting_answers[id_] = (DELIMITER_ARRIVED, )
        self.connection.send(iq)

    def set_roster_delimiter(self, delimiter='::'):
        """
        Set roster group delimiter to the storage namespace
        """
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set')
        iq2 = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        iq3 = iq2.addChild(name='roster', namespace='roster:delimiter')
        iq3.setData(delimiter)

        self.connection.send(iq)

    def get_metacontacts(self):
        """
        Get metacontacts list from storage as described in XEP 0049
        """
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get')
        iq2 = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        iq2.addChild(name='storage', namespace='storage:metacontacts')
        id_ = self.connection.getAnID()
        iq.setID(id_)
        self.awaiting_answers[id_] = (METACONTACTS_ARRIVED, )
        self.connection.send(iq)

    def store_metacontacts(self, tags_list):
        """
        Send meta contacts to the storage namespace
        """
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set')
        iq2 = iq.addChild(name='query', namespace=nbxmpp.NS_PRIVATE)
        iq3 = iq2.addChild(name='storage', namespace='storage:metacontacts')
        for tag in tags_list:
            for data in tags_list[tag]:
                jid = data['jid']
                dict_ = {'jid': jid, 'tag': tag}
                if 'order' in data:
                    dict_['order'] = data['order']
                iq3.addChild(name='meta', attrs=dict_)
        self.connection.send(iq)

    def request_roster(self):
        version = None
        features =  self.connection.Dispatcher.Stream.features
        if features and features.getTag('ver',
        namespace=nbxmpp.NS_ROSTER_VER):
            version = gajim.config.get_per('accounts', self.name,
                'roster_version')
            if version and not gajim.contacts.get_contacts_jid_list(
            self.name):
                gajim.config.set_per('accounts', self.name, 'roster_version',
                    '')
                version = None

        iq_id = self.connection.initRoster(version=version)
        self.awaiting_answers[iq_id] = (ROSTER_ARRIVED, )

    def send_agent_status(self, agent, ptype):
        if not gajim.account_is_connected(self.name):
            return
        show = helpers.get_xmpp_show(gajim.SHOW_LIST[self.connected])
        p = nbxmpp.Presence(to=agent, typ=ptype, show=show)
        p = self.add_sha(p, ptype != 'unavailable')
        self.connection.send(p)

    def send_captcha(self, jid, form_node):
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set', to=jid)
        captcha = iq.addChild(name='captcha', namespace=nbxmpp.NS_CAPTCHA)
        captcha.addChild(node=form_node)
        self.connection.send(iq)

    def check_unique_room_id_support(self, server, instance):
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get', to=server)
        iq.setAttr('id', 'unique1')
        iq.addChild('unique', namespace=nbxmpp.NS_MUC_UNIQUE)
        def _on_response(resp):
            if not nbxmpp.isResultNode(resp):
                gajim.nec.push_incoming_event(UniqueRoomIdNotSupportedEvent(
                    None, conn=self, instance=instance, server=server))
                return
            gajim.nec.push_incoming_event(UniqueRoomIdSupportedEvent(None,
                conn=self, instance=instance, server=server,
                room_id=resp.getTag('unique').getData()))
        self.connection.SendAndCallForResponse(iq, _on_response)

    def join_gc(self, nick, room_jid, password, change_nick=False,
    rejoin=False):
        # FIXME: This room JID needs to be normalized; see #1364
        if not gajim.account_is_connected(self.name):
            return
        show = helpers.get_xmpp_show(gajim.SHOW_LIST[self.connected])
        if show == 'invisible':
            # Never join a room when invisible
            return

        # last date/time in history to avoid duplicate
        if room_jid not in self.last_history_time:
            # Not in memory, get it from DB
            last_log = None
            # Do not check if we are not logging for this room
            if gajim.config.should_log(self.name, room_jid):
                # Check time first in the FAST table
                last_log = gajim.logger.get_room_last_message_time(room_jid)
                if last_log is None:
                    # Not in special table, get it from messages DB
                    last_log = gajim.logger.get_last_date_that_has_logs(room_jid,
                            is_room=True)
            # Create self.last_history_time[room_jid] even if not logging,
            # could be used in connection_handlers
            if last_log is None:
                last_log = 0
            self.last_history_time[room_jid] = last_log

        p = nbxmpp.Presence(to='%s/%s' % (room_jid, nick),
                show=show, status=self.status)
        h = hmac.new(self.secret_hmac, room_jid.encode('utf-8')).hexdigest()[:6]
        id_ = self.connection.getAnID()
        id_ = 'gajim_muc_' + id_ + '_' + h
        p.setID(id_)
        if gajim.config.get('send_sha_in_gc_presence'):
            p = self.add_sha(p)
        self.add_lang(p)
        if not change_nick:
            t = p.setTag(nbxmpp.NS_MUC + ' x')
            tags = {}
            timeout = gajim.config.get_per('rooms', room_jid,
                'muc_restore_timeout')
            if timeout is None or timeout == -2:
                timeout = gajim.config.get('muc_restore_timeout')
            timeout *= 60
            if timeout >= 0:
                last_date = self.last_history_time[room_jid]
                if last_date == 0:
                    last_date = time.time() - timeout
                elif not rejoin:
                    last_date = min(last_date, time.time() - timeout)
                last_date = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(
                    last_date))
                tags['since'] = last_date
            nb = gajim.config.get_per('rooms', room_jid, 'muc_restore_lines')
            if nb is None or nb == -2:
                nb = gajim.config.get('muc_restore_lines')
            if nb >= 0:
                tags['maxstanzas'] = nb
            if tags:
                t.setTag('history', tags)
            if password:
                t.setTagData('password', password)
        self.connection.send(p)

    def _nec_gc_message_outgoing(self, obj):
        if obj.account != self.name:
            return
        if not gajim.account_is_connected(self.name):
            return

        if obj.correction_msg:
            id_ = obj.correction_msg.getID()
            if obj.correction_msg.getTag('replace'):
                obj.correction_msg.delChild('replace')
            obj.correction_msg.setTag('replace', attrs={'id': id_},
                namespace=nbxmpp.NS_CORRECT)
            id2 = self.connection.getAnID()
            obj.correction_msg.setID(id2)
            obj.correction_msg.setBody(obj.message)
            if obj.xhtml:
                obj.correction_msg.setXHTML(xhtml)
            self.connection.send(obj.correction_msg)
            gajim.nec.push_incoming_event(MessageSentEvent(None, conn=self,
                jid=obj.jid, message=obj.message, keyID=None, chatstate=None))
            if obj.callback:
                obj.callback(obj.correction_msg, obj.message)
            return
        if not obj.xhtml and gajim.config.get('rst_formatting_outgoing_messages'):
            from common.rst_xhtml_generator import create_xhtml
            obj.xhtml = create_xhtml(obj.message)
        msg_iq = nbxmpp.Message(obj.jid, obj.message, typ='groupchat',
            xhtml=obj.xhtml)
        if obj.label is not None:
            msg_iq.addChild(node=label)
        self.connection.send(msg_iq)
        gajim.nec.push_incoming_event(MessageSentEvent(None, conn=self,
            jid=obj.jid, message=obj.message, keyID=None, chatstate=None))
        if obj.callback:
            obj.callback(msg_iq, obj.message)

    def send_gc_subject(self, jid, subject):
        if not gajim.account_is_connected(self.name):
            return
        msg_iq = nbxmpp.Message(jid, typ='groupchat', subject=subject)
        self.connection.send(msg_iq)

    def request_gc_config(self, room_jid):
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get', queryNS=nbxmpp.NS_MUC_OWNER,
            to=room_jid)
        self.add_lang(iq)
        self.connection.send(iq)

    def destroy_gc_room(self, room_jid, reason = '', jid = ''):
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set', queryNS=nbxmpp.NS_MUC_OWNER,
            to=room_jid)
        destroy = iq.setQuery().setTag('destroy')
        if reason:
            destroy.setTagData('reason', reason)
        if jid:
            destroy.setAttr('jid', jid)
        self.connection.send(iq)

    def send_gc_status(self, nick, jid, show, status):
        if not gajim.account_is_connected(self.name):
            return
        if show == 'invisible':
            show = 'offline'
        ptype = None
        if show == 'offline':
            ptype = 'unavailable'
        xmpp_show = helpers.get_xmpp_show(show)
        p = nbxmpp.Presence(to='%s/%s' % (jid, nick), typ=ptype,
            show=xmpp_show, status=status)
        h = hmac.new(self.secret_hmac, jid.encode('utf-8')).hexdigest()[:6]
        id_ = self.connection.getAnID()
        id_ = 'gajim_muc_' + id_ + '_' + h
        p.setID(id_)
        if gajim.config.get('send_sha_in_gc_presence') and show != 'offline':
            p = self.add_sha(p, ptype != 'unavailable')
        self.add_lang(p)
        # send instantly so when we go offline, status is sent to gc before we
        # disconnect from jabber server
        self.connection.send(p)

    def gc_got_disconnected(self, room_jid):
        """
        A groupchat got disconnected. This can be or purpose or not

        Save the time we had last message to avoid duplicate logs AND be faster
        than get that date from DB. Save time that we have in mem in a small
        table (with fast access)
        """
        gajim.logger.set_room_last_message_time(room_jid, self.last_history_time[room_jid])

    def gc_set_role(self, room_jid, nick, role, reason=''):
        """
        Role is for all the life of the room so it's based on nick
        """
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set', to=room_jid, queryNS=nbxmpp.NS_MUC_ADMIN)
        item = iq.setQuery().setTag('item')
        item.setAttr('nick', nick)
        item.setAttr('role', role)
        if reason:
            item.addChild(name='reason', payload=reason)
        self.connection.send(iq)

    def gc_set_affiliation(self, room_jid, jid, affiliation, reason = ''):
        """
        Affiliation is for all the life of the room so it's based on jid
        """
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set', to=room_jid, queryNS=nbxmpp.NS_MUC_ADMIN)
        item = iq.setQuery().setTag('item')
        item.setAttr('jid', jid)
        item.setAttr('affiliation', affiliation)
        if reason:
            item.addChild(name = 'reason', payload = reason)
        self.connection.send(iq)

    def send_gc_affiliation_list(self, room_jid, users_dict):
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set', to=room_jid, queryNS=nbxmpp.NS_MUC_ADMIN)
        item = iq.setQuery()
        for jid in users_dict:
            item_tag = item.addChild('item', {'jid': jid,
                    'affiliation': users_dict[jid]['affiliation']})
            if 'reason' in users_dict[jid] and users_dict[jid]['reason']:
                item_tag.setTagData('reason', users_dict[jid]['reason'])
        self.connection.send(iq)

    def get_affiliation_list(self, room_jid, affiliation):
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get', to=room_jid, queryNS=nbxmpp.NS_MUC_ADMIN)
        item = iq.setQuery().setTag('item')
        item.setAttr('affiliation', affiliation)
        self.connection.send(iq)

    def send_gc_config(self, room_jid, form):
        if not gajim.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set', to=room_jid, queryNS=nbxmpp.NS_MUC_OWNER)
        query = iq.setQuery()
        form.setAttr('type', 'submit')
        query.addChild(node = form)
        self.connection.send(iq)

    def change_password(self, password):
        if not gajim.account_is_connected(self.name):
            return
        hostname = gajim.config.get_per('accounts', self.name, 'hostname')
        username = gajim.config.get_per('accounts', self.name, 'name')
        iq = nbxmpp.Iq(typ='set', to=hostname)
        q = iq.setTag(nbxmpp.NS_REGISTER + ' query')
        q.setTagData('username', username)
        q.setTagData('password', password)
        self.connection.send(iq)

    def get_password(self, callback, type_):
        self.pasword_callback = (callback, type_)
        if type_ == 'X-MESSENGER-OAUTH2':
            client_id = gajim.config.get_per('accounts', self.name,
                'oauth2_client_id')
            refresh_token = gajim.config.get_per('accounts', self.name,
                'oauth2_refresh_token')
            if refresh_token:
                renew_URL = 'https://oauth.live.com/token?client_id=' \
                    '%(client_id)s&redirect_uri=https%%3A%%2F%%2Foauth.live.' \
                    'com%%2Fdesktop&grant_type=refresh_token&refresh_token=' \
                    '%(refresh_token)s' % locals()
                result = helpers.download_image(self.name, {'src': renew_URL})[0]
                if result:
                    dict_ = json.loads(result)
                    if 'access_token' in dict_:
                        self.set_password(dict_['access_token'])
                        return
            script_url = gajim.config.get_per('accounts', self.name,
                'oauth2_redirect_url')
            token_URL = 'https://oauth.live.com/authorize?client_id=' \
                '%(client_id)s&scope=wl.messenger%%20wl.offline_access&' \
                'response_type=code&redirect_uri=%(script_url)s' % locals()
            helpers.launch_browser_mailer('url', token_URL)
            self.disconnect(on_purpose=True)
            gajim.nec.push_incoming_event(Oauth2CredentialsRequiredEvent(None,
                conn=self))
            return
        if self.password:
            self.set_password(self.password)
            return
        gajim.nec.push_incoming_event(PasswordRequiredEvent(None, conn=self))

    def set_password(self, password):
        self.password = password
        if self.pasword_callback:
            callback, type_ = self.pasword_callback
            if self._current_type == 'plain' and type_ == 'PLAIN' and \
            gajim.config.get_per('accounts', self.name,
            'warn_when_insecure_password'):
                gajim.nec.push_incoming_event(InsecurePasswordEvent(None,
                    conn=self))
                return
            callback(password)
            self.pasword_callback = None

    def accept_insecure_password(self):
        if self.pasword_callback:
            callback, type_ = self.pasword_callback
            callback(self.password)
            self.pasword_callback = None

    def unregister_account(self, on_remove_success):
        # no need to write this as a class method and keep the value of
        # on_remove_success as a class property as pass it as an argument
        def _on_unregister_account_connect(con):
            self.on_connect_auth = None
            if gajim.account_is_connected(self.name):
                hostname = gajim.config.get_per('accounts', self.name, 'hostname')
                iq = nbxmpp.Iq(typ='set', to=hostname)
                id_ = self.connection.getAnID()
                iq.setID(id_)
                iq.setTag(nbxmpp.NS_REGISTER + ' query').setTag('remove')
                def _on_answer(con, result):
                    if result.getID() == id_:
                        on_remove_success(True)
                        return
                    gajim.nec.push_incoming_event(InformationEvent(None,
                        conn=self, level='error',
                        pri_txt=_('Unregister failed'),
                        sec_txt=_('Unregistration with server %(server)s '
                        'failed: %(error)s') % {'server': hostname,
                        'error': result.getErrorMsg()}))
                    on_remove_success(False)
                con.RegisterHandler('iq', _on_answer, 'result', system=True)
                con.SendAndWaitForResponse(iq)
                return
            on_remove_success(False)
        if self.connected == 0:
            self.on_connect_auth = _on_unregister_account_connect
            self.connect_and_auth()
        else:
            _on_unregister_account_connect(self.connection)

    def send_invite(self, room, to, reason='', continue_tag=False):
        """
        Send invitation
        """
        contact = gajim.contacts.get_contact_from_full_jid(self.name, to)
        if contact and contact.supports(nbxmpp.NS_CONFERENCE):
            # send direct invite
            message=nbxmpp.Message(to=to)
            attrs = {'jid': room}
            if reason:
                attrs['reason'] = reason
            if continue_tag:
                attrs['continue'] = 'true'
            c = message.addChild(name='x', attrs=attrs,
                namespace=nbxmpp.NS_CONFERENCE)
            self.connection.send(message)
            return
        message=nbxmpp.Message(to=room)
        c = message.addChild(name='x', namespace=nbxmpp.NS_MUC_USER)
        c = c.addChild(name='invite', attrs={'to': to})
        if continue_tag:
            c.addChild(name='continue')
        if reason != '':
            c.setTagData('reason', reason)
        self.connection.send(message)

    def decline_invitation(self, room, to, reason=''):
        """
        decline a groupchat invitation
        """
        message=nbxmpp.Message(to=room)
        c = message.addChild(name='x', namespace=nbxmpp.NS_MUC_USER)
        c = c.addChild(name='decline', attrs={'to': to})
        if reason != '':
            c.setTagData('reason', reason)
        self.connection.send(message)

    def request_voice(self, room):
        """
        Request voice in a moderated room
        """
        message = nbxmpp.Message(to=room)

        x = nbxmpp.DataForm(typ='submit')
        x.addChild(node=nbxmpp.DataField(name='FORM_TYPE',
            value=nbxmpp.NS_MUC + '#request'))
        x.addChild(node=nbxmpp.DataField(name='muc#role', value='participant',
            typ='text-single'))

        message.addChild(node=x)

        self.connection.send(message)

    def check_pingalive(self):
        if not gajim.config.get_per('accounts', self.name, 'active'):
            # Account may have been disabled
            return
        if self.awaiting_xmpp_ping_id:
            # We haven't got the pong in time, disco and reconnect
            log.warning("No reply received for keepalive ping. Reconnecting.")
            self._disconnectedReconnCB()

    def _reconnect_alarm(self):
        if not gajim.config.get_per('accounts', self.name, 'active'):
            # Account may have been disabled
            return
        if self.time_to_reconnect:
            if self.connected < 2:
                self._reconnect()
            else:
                self.time_to_reconnect = None

    def request_search_fields(self, jid):
        iq = nbxmpp.Iq(typ='get', to=jid, queryNS=nbxmpp.NS_SEARCH)
        self.connection.send(iq)

    def send_search_form(self, jid, form, is_form):
        iq = nbxmpp.Iq(typ='set', to=jid, queryNS=nbxmpp.NS_SEARCH)
        item = iq.setQuery()
        if is_form:
            item.addChild(node=form)
        else:
            for i in form.keys():
                item.setTagData(i, form[i])
        def _on_response(resp):
            gajim.nec.push_incoming_event(SearchResultReceivedEvent(None,
                conn=self, stanza=resp))

        self.connection.SendAndCallForResponse(iq, _on_response)

    def load_roster_from_db(self):
        gajim.nec.push_incoming_event(RosterReceivedEvent(None, conn=self))

# END Connection
