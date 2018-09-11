# Copyright (C) 2003-2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
#                    Stéphan Kochen <stephan AT kochen.nl>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
#                         Travis Shirk <travis AT pobox.com>
#                         Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Junglecow J <junglecow AT gmail.com>
#                    Stefan Bethge <stefan AT lanpartei.de>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 Tomasz Melcer <liori AT exroot.org>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#                    Jonathan Schleifer <js-gajim AT webkeks.org>
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

import sys
import random
import socket
import operator
import string
import time
import hashlib
import json
import logging
import base64
import ssl
from functools import partial
from string import Template
from urllib.request import urlopen
from urllib.error import URLError

if sys.platform in ('win32', 'darwin'):
    import certifi
import OpenSSL.crypto
import nbxmpp
from nbxmpp import Smacks

from gajim import common
from gajim.common import helpers
from gajim.common import app
from gajim.common import gpg
from gajim.common import passwords
from gajim.common import idle
from gajim.common.connection_handlers import *
from gajim.common.contacts import GC_Contact
from gajim.common import modules


log = logging.getLogger('gajim.c.connection')

SERVICE_START_TLS = 'xmpp-client'
SERVICE_DIRECT_TLS = 'xmpps-client'

class CommonConnection:
    """
    Common connection class, can be derived for normal connection or zeroconf
    connection
    """

    def __init__(self, name):
        self.name = name
        self._modules = {}
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
        if app.is_installed('GPG'):
            self.USE_GPG = True
            self.gpg = gpg.GnuPG()
        self.status = ''
        self.old_show = ''
        self.priority = app.get_priority(name, 'offline')
        self.time_to_reconnect = None

        self.pep = {}
        # Do we continue connection when we get roster (send presence,get vcard..)
        self.continue_connect_info = None

        # Remember where we are in the register agent process
        self.agent_registrations = {}
        # To know the groupchat jid associated with a stanza ID. Useful to
        # request vcard or os info... to a real JID but act as if it comes from
        # the fake jid
        self.groupchat_jids = {} # {ID : groupchat_jid}

        self.roster_supported = True
        self.addressing_supported = False
        self.avatar_conversion = False

        self.muc_jid = {} # jid of muc server for each transport type
        self._stun_servers = [] # STUN servers of our jabber server

        self.awaiting_cids = {} # Used for XEP-0231

        # Tracks the calls of the connect_machine() method
        self._connect_machine_calls = 0

        self.get_config_values_or_default()

    def _compute_resource(self):
        resource = app.config.get_per('accounts', self.name, 'resource')
        # All valid resource substitution strings should be added to this hash.
        if resource:
            rand = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            resource = Template(resource).safe_substitute({
                    'hostname': socket.gethostname(),
                    'rand': rand
            })
            app.config.set_per('accounts', self.name, 'resource', resource)
        return resource

    def dispatch(self, event, data):
        """
        Always passes account name as first param
        """
        app.ged.raise_event(event, self.name, data)

    def get_module(self, name):
        return modules.get(self.name, name)

    def reconnect(self):
        """
        To be implemented by derived classes
        """
        raise NotImplementedError

    def quit(self, kill_core):
        if kill_core and app.account_is_connected(self.name):
            self.disconnect(on_purpose=True)

    def test_gpg_passphrase(self, password):
        """
        Returns 'ok', 'bad_pass' or 'expired'
        """
        if not self.gpg:
            return False
        self.gpg.passphrase = password
        keyID = app.config.get_per('accounts', self.name, 'keyid')
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
        keyID = app.config.get_per('accounts', self.name, 'keyid')
        if keyID and self.USE_GPG:
            if self.gpg.passphrase is None and not self.gpg.use_agent:
                # We didn't set a passphrase
                return None
            signed = self.gpg.sign(msg, keyID)
            if signed == 'BAD_PASSPHRASE':
                self.USE_GPG = False
                signed = ''
                app.nec.push_incoming_event(BadGPGPassphraseEvent(None,
                    conn=self))
        return signed

    def _on_disconnected(self):
        """
        Called when a disconnect request has completed successfully
        """
        self.disconnect(on_purpose=True)
        app.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='offline'))

    def get_status(self):
        return app.SHOW_LIST[self.connected]

    def check_jid(self, jid):
        """
        This function must be implemented by derived classes. It has to return
        the valid jid, or raise a helpers.InvalidFormat exception
        """
        raise NotImplementedError

    def _prepare_message(self, obj):

        if not self.connection or self.connected < 2:
            return 1

        if isinstance(obj.jid, list):
            for jid in obj.jid:
                try:
                    self.check_jid(jid)
                except helpers.InvalidFormat:
                    app.nec.push_incoming_event(InformationEvent(
                        None, dialog_name='invalid-jid', args=jid))
                    return
        else:
            try:
                self.check_jid(obj.jid)
            except helpers.InvalidFormat:
                app.nec.push_incoming_event(InformationEvent(
                    None, dialog_name='invalid-jid', args=obj.jid))
                return

        if obj.message and not obj.xhtml and app.config.get(
        'rst_formatting_outgoing_messages'):
            from gajim.common.rst_xhtml_generator import create_xhtml
            obj.xhtml = create_xhtml(obj.message)
        if not obj.message and obj.chatstate is None and obj.form_node is None:
            return

        self._build_message_stanza(obj)

    def _build_message_stanza(self, obj):
        if obj.jid == app.get_jid_from_account(self.name):
            fjid = obj.jid
        else:
            fjid = obj.get_full_jid()

        if obj.type_ == 'chat':
            msg_iq = nbxmpp.Message(body=obj.message, typ=obj.type_,
                    xhtml=obj.xhtml)
        else:
            if obj.subject:
                msg_iq = nbxmpp.Message(body=obj.message, typ='normal',
                        subject=obj.subject, xhtml=obj.xhtml)
            else:
                msg_iq = nbxmpp.Message(body=obj.message, typ='normal',
                        xhtml=obj.xhtml)

        if obj.correct_id:
            msg_iq.setTag('replace', attrs={'id': obj.correct_id},
                          namespace=nbxmpp.NS_CORRECT)

        # XEP-0359
        obj.stanza_id = self.connection.getAnID()
        msg_iq.setID(obj.stanza_id)
        if obj.message:
            msg_iq.setOriginID(obj.stanza_id)

        if obj.form_node:
            msg_iq.addChild(node=obj.form_node)
        if obj.label:
            msg_iq.addChild(node=obj.label)

        # XEP-0172: user_nickname
        if obj.user_nick:
            msg_iq.setTag('nick', namespace=nbxmpp.NS_NICK).setData(
                    obj.user_nick)

        # XEP-0203
        if obj.delayed:
            our_jid = app.get_jid_from_account(self.name) + '/' + \
                    self.server_resource
            timestamp = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(obj.delayed))
            msg_iq.addChild('delay', namespace=nbxmpp.NS_DELAY2,
                    attrs={'from': our_jid, 'stamp': timestamp})

        # XEP-0224
        if obj.attention:
            msg_iq.setTag('attention', namespace=nbxmpp.NS_ATTENTION)

        if isinstance(obj.jid, list):
            if self.addressing_supported:
                msg_iq.setTo(app.config.get_per('accounts', self.name, 'hostname'))
                addresses = msg_iq.addChild('addresses',
                    namespace=nbxmpp.NS_ADDRESS)
                for j in obj.jid:
                    addresses.addChild('address', attrs = {'type': 'to',
                        'jid': j})
            else:
                iqs = []
                for j in obj.jid:
                    iq = nbxmpp.Message(node=msg_iq)
                    iq.setTo(j)
                    iqs.append(iq)
                msg_iq = iqs
        else:
            msg_iq.setTo(fjid)
            r_ = obj.resource
            if not r_ and obj.jid != fjid: # Only if we're not in a pm
                r_ = app.get_resource_from_jid(fjid)
            if r_:
                contact = app.contacts.get_contact(self.name, obj.jid, r_)
            else:
                contact = app.contacts.get_contact_with_highest_priority(
                    self.name, obj.jid)

            # Mark Message as MUC PM
            if isinstance(contact, GC_Contact):
                msg_iq.setTag('x', namespace=nbxmpp.NS_MUC_USER)

            # chatstates - if peer supports xep85, send chatstates
            # please note that the only valid tag inside a message containing a
            # <body> tag is the active event
            if obj.chatstate and contact and contact.supports(nbxmpp.NS_CHATSTATES):
                msg_iq.setTag(obj.chatstate, namespace=nbxmpp.NS_CHATSTATES)
                if not obj.message:
                    msg_iq.setTag('no-store',
                                  namespace=nbxmpp.NS_MSG_HINTS)

            # XEP-0184
            if obj.jid != app.get_jid_from_account(self.name):
                request = app.config.get_per('accounts', self.name,
                                               'request_receipt')
                if obj.message and request:
                    msg_iq.setTag('request', namespace=nbxmpp.NS_RECEIPTS)

            if obj.session:
                # XEP-0201
                obj.session.last_send = time.time()
                msg_iq.setThread(obj.session.thread_id)

        self._push_stanza_message_outgoing(obj, msg_iq)

    def _push_stanza_message_outgoing(self, obj, msg_iq):
        obj.conn = self
        if isinstance(msg_iq, list):
            for iq in msg_iq:
                obj.msg_iq = iq
                app.nec.push_incoming_event(
                    StanzaMessageOutgoingEvent(None, **vars(obj)))
        else:
            obj.msg_iq = msg_iq
            app.nec.push_incoming_event(
                StanzaMessageOutgoingEvent(None, **vars(obj)))

    def log_message(self, obj, jid):
        if not obj.is_loggable:
            return

        if obj.session and not obj.session.is_loggable():
            return

        if not app.config.should_log(self.name, jid):
            return

        if obj.xhtml and app.config.get('log_xhtml_messages'):
            obj.message = '<body xmlns="%s">%s</body>' % (nbxmpp.NS_XHTML,
                                                          obj.xhtml)
        if obj.message is None:
            return

        app.logger.insert_into_logs(self.name, jid, obj.timestamp, obj.kind,
                                    message=obj.message,
                                    subject=obj.subject,
                                    additional_data=obj.additional_data,
                                    stanza_id=obj.stanza_id)

    def unsubscribe_agent(self, agent):
        """
        To be implemented by derived classes
        """
        raise NotImplementedError

    def update_contact(self, jid, name, groups):
        if self.connection:
            self.getRoster().set_item(jid=jid, name=name, groups=groups)

    def update_contacts(self, contacts):
        """
        Update multiple roster items
        """
        if self.connection:
            self.getRoster().set_item_multi(contacts)

    def new_account(self, name, config, sync=False):
        """
        To be implemented by derived classes
        """
        raise NotImplementedError

    def _on_new_account(self, con=None, con_type=None):
        """
        To be implemented by derived classes
        """
        raise NotImplementedError

    def account_changed(self, new_name):
        self.name = new_name

    def send_agent_status(self, agent, ptype):
        """
        To be implemented by derived classes
        """
        raise NotImplementedError

    def gpg_passphrase(self, passphrase):
        if self.gpg:
            if self.gpg.use_agent:
                self.gpg.passphrase = None
            else:
                self.gpg.passphrase = passphrase

    def ask_gpg_keys(self, keyID=None):
        if self.gpg:
            if keyID:
                return self.gpg.get_key(keyID)
            return self.gpg.get_keys()
        return None

    def ask_gpg_secrete_keys(self):
        if self.gpg:
            return self.gpg.get_secret_keys()
        return None

    def _event_dispatcher(self, realm, event, data):
        if realm == '':
            if event == 'STANZA RECEIVED':
                app.nec.push_incoming_event(StanzaReceivedEvent(
                    None, conn=self, stanza_str=str(data)))
            elif event == 'DATA SENT':
                app.nec.push_incoming_event(StanzaSentEvent(
                    None, conn=self, stanza_str=str(data)))

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
            if app.is_installed('GPG'):
                self.USE_GPG = True
                self.gpg = gpg.GnuPG()
            app.nec.push_incoming_event(BeforeChangeShowEvent(None,
                conn=self, show=show, message=msg))
            self.connect_and_init(show, msg, sign_msg)
            return

        if show == 'offline':
            self.connected = 0
            if self.connection:
                app.nec.push_incoming_event(BeforeChangeShowEvent(None,
                    conn=self, show=show, message=msg))

                p = self.get_module('Presence').get_presence(
                    typ='unavailable',
                    status=msg,
                    caps=False)

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
                app.nec.push_incoming_event(BeforeChangeShowEvent(None,
                    conn=self, show=show, message=msg))
                self._change_to_invisible(msg)
                return
            if show not in ['offline', 'online', 'chat', 'away', 'xa', 'dnd']:
                return -1
            was_invisible = self.connected == app.SHOW_LIST.index('invisible')
            self.connected = app.SHOW_LIST.index(show)
            idle_time = None
            if auto:
                if app.is_installed('IDLE') and app.config.get('autoaway'):
                    idle_sec = idle.Monitor.get_idle_sec()
                    idle_time = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                        time.gmtime(time.time() - idle_sec))
            app.nec.push_incoming_event(BeforeChangeShowEvent(None,
                conn=self, show=show, message=msg))
            if was_invisible:
                self._change_from_invisible()
            self._update_status(show, msg, idle_time=idle_time)

class Connection(CommonConnection, ConnectionHandlers):
    def __init__(self, name):
        CommonConnection.__init__(self, name)
        ConnectionHandlers.__init__(self)

        # increase/decrease default timeout for server responses
        self.try_connecting_for_foo_secs = 45
        # holds the actual hostname to which we are connected
        self.connected_hostname = None
        # Holds the full jid we received on the bind event
        self.registered_name = None
        self.last_time_to_reconnect = None
        self.new_account_info = None
        self.new_account_form = None
        self.last_sent = []
        self.password = passwords.get_password(name)

        self.music_track_info = 0

        self.register_supported = False
        # Do we auto accept insecure connection
        self.connection_auto_accepted = False
        self.pasword_callback = None

        self.on_connect_success = None
        self.on_connect_failure = None
        self.retrycount = 0
        self.available_transports = {} # list of available transports on this
        # server {'icq': ['icq.server.com', 'icq2.server.com'], }

        self.streamError = ''
        self.removing_account = False

        # We only request POSH once
        self._posh_requested = False
        # Fingerprints received via POSH
        self._posh_hashes = []
        # The SSL Errors that we can override with POSH
        self._posh_errors = [18, 19]

        self.sm = Smacks(self) # Stream Management

        # Register all modules
        modules.register(self)

        app.ged.register_event_handler('message-outgoing', ged.OUT_CORE,
            self._nec_message_outgoing)
        app.ged.register_event_handler('gc-message-outgoing', ged.OUT_CORE,
            self._nec_gc_message_outgoing)
        app.ged.register_event_handler('gc-stanza-message-outgoing', ged.OUT_CORE,
            self._nec_gc_stanza_message_outgoing)
        app.ged.register_event_handler('stanza-message-outgoing',
            ged.OUT_CORE, self._nec_stanza_message_outgoing)
    # END __init__

    def cleanup(self):
        ConnectionHandlers.cleanup(self)
        modules.unregister(self)

        app.ged.remove_event_handler('message-outgoing', ged.OUT_CORE,
            self._nec_message_outgoing)
        app.ged.remove_event_handler('gc-message-outgoing', ged.OUT_CORE,
            self._nec_gc_message_outgoing)
        app.ged.remove_event_handler('gc-stanza-message-outgoing', ged.OUT_CORE,
            self._nec_gc_stanza_message_outgoing)
        app.ged.remove_event_handler('stanza-message-outgoing', ged.OUT_CORE,
            self._nec_stanza_message_outgoing)

    def get_config_values_or_default(self):
        if app.config.get_per('accounts', self.name, 'keep_alives_enabled'):
            self.keepalives = app.config.get_per('accounts', self.name,
                    'keep_alive_every_foo_secs')
        else:
            self.keepalives = 0
        if app.config.get_per('accounts', self.name, 'ping_alives_enabled'):
            self.pingalives = app.config.get_per('accounts', self.name,
                    'ping_alive_every_foo_secs')
        else:
            self.pingalives = 0
        self.client_cert = app.config.get_per('accounts', self.name,
            'client_cert')
        self.client_cert_passphrase = ''

    def check_jid(self, jid):
        return helpers.parse_jid(jid)

    def get_own_jid(self, warn=False):
        """
        Return the last full JID we received on a bind event.
        In case we were never connected it returns the bare JID from config.
        """
        if self.registered_name:
            # This returns the full jid we received on the bind event
            return self.registered_name
        else:
            if warn:
                log.warning('only bare JID available')
            # This returns the bare jid 
            return nbxmpp.JID(app.get_jid_from_account(self.name))

    def reconnect(self):
        # Do not try to reco while we are already trying
        self.time_to_reconnect = None
        if self.connected < 2: # connection failed
            log.info('Reconnect')
            self.connected = 1
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='connecting'))
            self.retrycount += 1
            self.on_connect_auth = self._discover_server_at_connection
            self.connect_and_init(self.old_show, self.status, self.USE_GPG)
        else:
            log.info('Reconnect successfull')
            # reconnect succeeded
            self.time_to_reconnect = None
            self.retrycount = 0

    # We are doing disconnect at so many places, better use one function in all
    def disconnect(self, on_purpose=False):
        log.info('Disconnect: on_purpose: %s', on_purpose)
        app.interface.music_track_changed(None, None, self.name)
        self.get_module('PEP').reset_stored_publish()
        self.on_purpose = on_purpose
        self.connected = 0
        self.time_to_reconnect = None
        self.get_module('VCardAvatars').avatar_advertised = False
        if on_purpose:
            self.sm = Smacks(self)
        if self.connection:
            # make sure previous connection is completely closed
            app.proxy65_manager.disconnect(self.connection)
            self.terminate_sessions()
            self.remove_all_transfers()
            self.connection.disconnect()
            ConnectionHandlers._unregister_handlers(self)
            self.connection = None

    def set_oldst(self): # Set old state
        if self.old_show:
            self.connected = app.SHOW_LIST.index(self.old_show)
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                                           show=self.connected))
        else: # we default to online
            self.connected = 2
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                                    show=app.SHOW_LIST[self.connected]))

    def disconnectedReconnCB(self):
        """
        Called when we are disconnected
        """
        log.info('disconnectedReconnCB called')
        if app.account_is_connected(self.name):
            # we cannot change our status to offline or connecting
            # after we auth to server
            self.old_show = app.SHOW_LIST[self.connected]
        self.connected = 0
        if not self.on_purpose:
            if not (self.sm and self.sm.resumption):
                app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='offline'))
            else:
                self.sm.enabled = False
                app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='error'))
            if self.connection:
                self.connection.UnregisterDisconnectHandler(
                    self.disconnectedReconnCB)
            self.disconnect()
            if app.config.get_per('accounts', self.name, 'autoreconnect'):
                self.connected = -1
                app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='error'))
                if app.status_before_autoaway[self.name]:
                    # We were auto away. So go back online
                    self.status = app.status_before_autoaway[self.name]
                    app.status_before_autoaway[self.name] = ''
                    self.old_show = 'online'
                # this check has moved from reconnect method
                # do exponential backoff until less than 5 minutes
                if self.retrycount < 2 or self.last_time_to_reconnect is None:
                    self.last_time_to_reconnect = 5
                    self.last_time_to_reconnect += random.randint(0, 5)
                if self.last_time_to_reconnect < 200:
                    self.last_time_to_reconnect *= 1.5
                self.time_to_reconnect = int(self.last_time_to_reconnect)
                log.info("Reconnect to %s in %ss", self.name, self.time_to_reconnect)
                app.idlequeue.set_alarm(self._reconnect_alarm,
                        self.time_to_reconnect)
            elif self.on_connect_failure:
                self.on_connect_failure()
                self.on_connect_failure = None
            else:
                # show error dialog
                self._connection_lost()
        else:
            self.disconnect()
        self.on_purpose = False
    # END disconnectedReconnCB

    def _connection_lost(self):
        log.info('_connection_lost')
        self.disconnect(on_purpose = False)
        if self.removing_account:
            return
        app.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
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
                        app.nec.push_incoming_event(AccountNotCreatedEvent(
                            None, conn=self, reason=reason))
                        return
                    is_form = data[2]
                    conf = data[1]
                    if data[4] is not '':
                        helpers.replace_dataform_media(conf, data[4])
                    if self.new_account_form:
                        def _on_register_result(result):
                            if not nbxmpp.isResultNode(result):
                                reason = result.getErrorMsg() or result.getError()
                                app.nec.push_incoming_event(AccountNotCreatedEvent(
                                    None, conn=self, reason=reason))
                                return
                            if app.is_installed('GPG'):
                                self.USE_GPG = True
                                self.gpg = gpg.GnuPG()
                            app.nec.push_incoming_event(
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
                                app.nec.push_incoming_event(AccountNotCreatedEvent(
                                    None, conn=self, reason=reason))
                                return
                            nbxmpp.features_nb.register(self.connection,
                                    self._hostname, self.new_account_form,
                                    _on_register_result)
                        return
                    app.nec.push_incoming_event(NewAccountConnectedEvent(None,
                        conn=self, config=conf, is_form=is_form))
                    self.connection.UnregisterDisconnectHandler(
                        self._on_new_account)
                    self.disconnect(on_purpose=True)
                    return
                if not data[1]: # wrong answer
                    app.nec.push_incoming_event(InformationEvent(
                        None, dialog_name='invalid-answer',
                        kwargs={'name': data[0], 'error': data[3]}))
                    return

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
        Start a connection to the XMPP server

        Returns connection, and connection type ('tls', 'ssl', 'plain', '') data
        MUST contain hostname, proxy, use_custom_host, custom_host (if
        use_custom_host), custom_port (if use_custom_host)
        """
        if self.connection:
            return self.connection, ''

        log.info('Connect')
        if self.sm.resuming and self.sm.location:
            # If resuming and server gave a location, connect from there
            hostname = self.sm.location
            self.try_connecting_for_foo_secs = app.config.get_per('accounts',
                self.name, 'try_connecting_for_foo_secs')
            use_custom = False
            proxy = helpers.get_proxy_info(self.name)

        elif data:
            hostname = data['hostname']
            self.try_connecting_for_foo_secs = 45
            p = data['proxy']
            if p and p in app.config.get_per('proxies'):
                proxy = {}
                proxyptr = app.config.get_per('proxies', p)
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
            hostname = app.config.get_per('accounts', self.name, 'hostname')
            self.try_connecting_for_foo_secs = app.config.get_per('accounts',
                    self.name, 'try_connecting_for_foo_secs')
            proxy = helpers.get_proxy_info(self.name)
            use_srv = app.config.get_per('accounts', self.name, 'use_srv')

            use_custom = app.config.get_per('accounts', self.name,
                'use_custom_host')
            if use_custom:
                custom_h = app.config.get_per('accounts', self.name,
                    'custom_host')
                custom_p = app.config.get_per('accounts', self.name,
                    'custom_port')
                try:
                    helpers.idn_to_ascii(custom_h)
                except Exception:
                    app.nec.push_incoming_event(InformationEvent(
                        None, dialog_name='invalid-custom-hostname',
                        args=custom_h))
                    use_custom = False

        # create connection if it doesn't already exist
        self.connected = 1

        h = hostname
        p = 5222
        ssl_p = 5223
        if use_custom:
            h = custom_h
            p = custom_p
            ssl_p = custom_p
            use_srv = False

        # SRV resolver
        self._proxy = proxy
        self._hosts = [
            {'host': h, 'port': p, 'type': 'tls', 'prio': 10, 'weight': 10, 'alpn': False},
            {'host': h, 'port': ssl_p, 'type': 'ssl', 'prio': 10, 'weight': 10, 'alpn': False},
            {'host': h, 'port': p, 'type': 'plain', 'prio': 10, 'weight': 10, 'alpn': False}
        ]
        self._hostname = hostname

        if h:
            app.resolver.resolve('_xmppconnect.' + helpers.idn_to_ascii(h),
                                 self._on_resolve_txt, type_='txt')

        if use_srv and self._proxy is None:
            self._srv_hosts = []

            services = [SERVICE_START_TLS, SERVICE_DIRECT_TLS]
            self._num_pending_srv_records = len(services)

            for service in services:
                record_name = '_' + service + '._tcp.' + helpers.idn_to_ascii(h)
                app.resolver.resolve(record_name, self._on_resolve_srv)
        else:
            self._connect_to_next_host()

    def _append_srv_record(self, record, con_type):
        tmp = record.copy()
        tmp['type'] = con_type

        if tmp in self._srv_hosts:
            return

        self._srv_hosts.append(tmp)

    def _on_resolve_srv(self, host, result):
        for record in result:
            service = host[1:]
            if service.startswith(SERVICE_START_TLS):
                record['alpn'] = False
                self._append_srv_record(record, 'tls')
                self._append_srv_record(record, 'plain')
            elif service.startswith(SERVICE_DIRECT_TLS):
                record['alpn'] = True
                self._append_srv_record(record, 'ssl')

        self._num_pending_srv_records -= 1
        if self._num_pending_srv_records:
            return

        if self._srv_hosts:
            self._hosts = self._srv_hosts.copy()

        self._connect_to_next_host()

    def _on_resolve_txt(self, host, result_array):
        for res in result_array:
            if res.startswith('_xmpp-client-xbosh='):
                url = res[19:]
                found = False
                proxies = app.config.get_per('proxies')
                for p in proxies:
                    if app.config.get_per('proxies', p, 'type') == 'bosh' \
                    and app.config.get_per('proxies', p, 'bosh_uri') == url:
                        found = True
                        break
                if not found:
                    h = app.config.get_per('accounts', self.name, 'hostname')
                    p = 'bosh_' + h
                    i = 0
                    while p in proxies:
                        i += 1
                        p = 'bosh_' + h + str(i)
                    app.config.add_per('proxies', p)
                    app.config.set_per('proxies', p, 'type', 'bosh')
                    app.config.set_per('proxies', p, 'bosh_uri', url)

    def _connect_to_next_host(self, retry=False):
        log.debug('Connection to next host')
        if not self._hosts:
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
                self.disconnectedReconnCB()

            return

        connection_types = ['tls', 'ssl']
        allow_plaintext_connection = app.config.get_per('accounts', self.name,
            'allow_plaintext_connection')

        if allow_plaintext_connection:
            connection_types.append('plain')

        if self._proxy and self._proxy['type'] == 'bosh':
            # with BOSH, we can't do TLS negotiation with <starttls>, we do only "plain"
            # connection and TLS with handshake right after TCP connecting ("ssl")
            scheme = nbxmpp.transports_nb.urisplit(self._proxy['bosh_uri'])[0]
            if scheme == 'https':
                connection_types = ['ssl']
            else:
                if allow_plaintext_connection:
                    connection_types = ['plain']
                else:
                    connection_types = []

        host = self._select_next_host(self._hosts)
        self._hosts.remove(host)

        # Skip record if connection type is not supported.
        if host['type'] not in connection_types:
            log.info("Skipping connection record with unsupported type: %s",
                     host['type'])
            self._connect_to_next_host(retry)
            return

        self._current_host = host

        self._current_type = self._current_host['type']

        port = self._current_host['port']

        cacerts = ''
        if sys.platform in ('win32', 'darwin'):
            cacerts = certifi.where()
        mycerts = common.configpaths.get('MY_CACERTS')
        tls_version = app.config.get_per('accounts', self.name, 'tls_version')
        cipher_list = app.config.get_per('accounts', self.name, 'cipher_list')

        secure_tuple = (self._current_type, cacerts, mycerts, tls_version,
                        cipher_list, self._current_host['alpn'])

        con = nbxmpp.NonBlockingClient(
            domain=self._hostname,
            caller=self,
            idlequeue=app.idlequeue)

        # increase default timeout for server responses
        nbxmpp.dispatcher_nb.DEFAULT_TIMEOUT_SECONDS = \
            self.try_connecting_for_foo_secs
        # FIXME: this is a hack; need a better way
        if self.on_connect_success == self._on_new_account:
            con.RegisterDisconnectHandler(self._on_new_account)

        if self.client_cert and app.config.get_per('accounts', self.name,
        'client_cert_encrypted'):
            app.nec.push_incoming_event(ClientCertPassphraseEvent(
                None, conn=self, con=con, port=port,
                secure_tuple=secure_tuple))
            return
        self.on_client_cert_passphrase('', con, port, secure_tuple)

    def on_client_cert_passphrase(self, passphrase, con, port, secure_tuple):
        self.client_cert_passphrase = passphrase

        self.log_hosttype_info(port)
        con.connect(
            hostname=self._current_host['host'],
            port=port,
            on_connect=self.on_connect_success,
            on_proxy_failure=self.on_proxy_failure,
            on_connect_failure=self._connect_to_next_host,
            on_stream_error_cb=self._StreamCB,
            proxy=self._proxy,
            secure_tuple=secure_tuple)

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
                        app.nec.push_incoming_event(InformationEvent(None,
                            conn=self, level='error', pri_txt=pritxt,
                            sec_txt='%s\n%s' % (sectxt2, sectxt)))
                        return
                # show popup
                app.nec.push_incoming_event(ConnectionLostEvent(None,
                    conn=self, title=pritxt, msg=sectxt))

    def on_proxy_failure(self, reason):
        log.error('Connection to proxy failed: %s' % reason)
        self.time_to_reconnect = None
        self.on_connect_failure = None
        self.disconnect(on_purpose = True)
        app.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
            title=_('Connection to proxy failed'), msg=reason))

    def _connect_success(self, con, con_type):
        if not self.connected: # We went offline during connecting process
            # FIXME - not possible, maybe it was when we used threads
            return
        log.info('Connect successfull')
        _con_type = con_type
        if _con_type != self._current_type:
            log.info('Connecting to next host beacuse desired type is %s and returned is %s'
                    % (self._current_type, _con_type))
            self._connect_to_next_host()
            return
        con.RegisterDisconnectHandler(self._on_disconnected)
        if _con_type == 'plain' and app.config.get_per('accounts', self.name,
        'action_when_plaintext_connection') == 'warn':
            app.nec.push_incoming_event(PlainConnectionEvent(None, conn=self,
                xmpp_client=con))
            return True
        if _con_type == 'plain' and app.config.get_per('accounts', self.name,
        'action_when_plaintext_connection') == 'disconnect':
            self.disconnect(on_purpose=True)
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            return False
        if _con_type in ('tls', 'ssl') and con.Connection.ssl_lib != 'PYOPENSSL' \
        and app.config.get_per('accounts', self.name,
        'warn_when_insecure_ssl_connection') and \
        not self.connection_auto_accepted:
            # Pyopenssl is not used
            app.nec.push_incoming_event(InsecureSSLConnectionEvent(None,
                conn=self, xmpp_client=con, conn_type=_con_type))
            return True
        return self.connection_accepted(con, con_type)

    def connection_accepted(self, con, con_type):
        if not con or not con.Connection:
            self.disconnect(on_purpose=True)
            app.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not connect to account %s') % self.name,
                msg=_('Connection with account %s has been lost. Retry '
                'connecting.') % self.name))
            return
        log.info('Connection accepted')
        self._hosts = []
        self.connection_auto_accepted = False
        self.connected_hostname = self._current_host['host']
        self.on_connect_failure = None
        con.UnregisterDisconnectHandler(self._on_disconnected)
        con.RegisterDisconnectHandler(self.disconnectedReconnCB)
        log.debug('Connected to server %s:%s with %s' % (
                self._current_host['host'], self._current_host['port'], con_type))

        self.connection = con

        ssl_errors = con.Connection.ssl_errors
        ignored_ssl_errors = self._get_ignored_ssl_errors()
        self._ssl_errors = [n for n in ssl_errors if n not in ignored_ssl_errors]
        self._ssl_errors.reverse()
        self.process_ssl_errors()

    def _get_ignored_ssl_errors(self):
        ignore_ssl_errors = app.config.get_per(
            'accounts', self.name, 'ignore_ssl_errors').split()
        return [int(err) for err in ignore_ssl_errors]

    def process_ssl_errors(self):
        if not self._ssl_errors:
            self.ssl_certificate_accepted()
            return

        cert = self.connection.Connection.ssl_certificate
        errnum = self._ssl_errors.pop()

        # Check if we can verify the cert with POSH
        if errnum in self._posh_errors:
            # Request the POSH json file
            self._get_posh_file(self._hostname)
            self._posh_requested = True
            cert_hash256 = self._calculate_cert_sha256(cert)

            if cert_hash256 in self._posh_hashes:
                # Ignore this error if this cert is
                # verifyed with POSH
                self.process_ssl_errors()
                return

        app.nec.push_incoming_event(SSLErrorEvent(None, conn=self,
                                                  error_num=errnum,
                                                  cert=cert))

    @staticmethod
    def _calculate_cert_sha256(cert):
        der_encoded = OpenSSL.crypto.dump_certificate(
            OpenSSL.crypto.FILETYPE_ASN1, cert)
        hash_obj = hashlib.sha256(der_encoded)
        hash256 = base64.b64encode(hash_obj.digest()).decode('utf8')
        return hash256

    def _get_posh_file(self, hostname=None, redirect=None):
        if self._posh_requested:
            # We already have requested POSH
            return

        if not app.config.get_per('accounts', self.name, 'allow_posh'):
            return

        if hostname is None and redirect is None:
            raise ValueError('There must be either a hostname or a url')

        url = redirect
        if hostname is not None:
            url = 'https://%s/.well-known/posh/xmpp-client.json' % hostname

        cafile = None
        if sys.platform in ('win32', 'darwin'):
            cafile = certifi.where()

        log.info('Request POSH from %s', url)
        try:
            file = urlopen(
                url, cafile=cafile, timeout=2)
        except (URLError, ssl.CertificateError) as exc:
            log.info('Error while requesting POSH: %s' % exc)
            return

        if file.getcode() != 200:
            log.info('No POSH file found at %s', url)
            return

        try:
            posh = json.loads(file.read())
        except json.decoder.JSONDecodeError as json_error:
            log.warning(json_error)
            return

        # Redirect
        if 'url' in posh and redirect is None:
            # We dont allow redirects in redirects
            log.info('POSH redirect found')
            self._get_posh_file(redirect=posh['url'])
            return

        if 'fingerprints' in posh:
            fingerprints = posh['fingerprints']
            for fingerprint in fingerprints:
                if 'sha-256' not in fingerprint:
                    continue
                self._posh_hashes.append(fingerprint['sha-256'])

        log.info('POSH sha-256 fingerprints found: %s',
                 self._posh_hashes)

    def ssl_certificate_accepted(self):
        if not self.connection:
            self.disconnect(on_purpose=True)
            app.nec.push_incoming_event(
                ConnectionLostEvent(
                    None, conn=self,
                    title=_('Could not connect to account %s') % self.name,
                    msg=_('Connection with account %s has been lost. '
                          'Retry connecting.') % self.name))
            return

        log.info('SSL Cert accepted')
        name = None
        if not app.config.get_per('accounts', self.name, 'anonymous_auth'):
            name = app.config.get_per('accounts', self.name, 'name')

        self._register_handlers(self.connection, self._current_type)

        auth_mechs = app.config.get_per(
            'accounts', self.name, 'authentication_mechanisms').split()
        for mech in auth_mechs:
            if mech not in nbxmpp.auth_nb.SASL_AUTHENTICATION_MECHANISMS | set(['XEP-0078']):
                log.warning("Unknown authentication mechanisms %s" % mech)
        if len(auth_mechs) == 0:
            auth_mechs = None
        else:
            auth_mechs = set(auth_mechs)
        self.connection.auth(user=name,
                             password=self.password,
                             resource=self.server_resource,
                             sasl=True,
                             on_auth=self.__on_auth,
                             auth_mechs=auth_mechs)

    def _register_handlers(self, con, con_type):
        self.peerhost = con.get_peerhost()
        app.con_types[self.name] = con_type
        # notify the gui about con_type
        app.nec.push_incoming_event(ConnectionTypeEvent(None,
            conn=self, connection_type=con_type))
        ConnectionHandlers._register_handlers(self, con, con_type)

    def __on_auth(self, con, auth):
        log.info('auth')
        if not con:
            self.disconnect(on_purpose=True)
            app.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
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
        if con._registered_name is not None:
            log.info('Bound JID: %s', con._registered_name)
            self.registered_name = con._registered_name
        if app.config.get_per('accounts', self.name, 'anonymous_auth'):
            # Get jid given by server
            old_jid = app.get_jid_from_account(self.name)
            app.config.set_per('accounts', self.name, 'name', con.User)
            new_jid = app.get_jid_from_account(self.name)
            app.nec.push_incoming_event(AnonymousAuthEvent(None,
                conn=self, old_jid=old_jid, new_jid=new_jid))
        if auth:
            self.connected = 2
            self.retrycount = 0
            if self.on_connect_auth:
                self.on_connect_auth(con)
                self.on_connect_auth = None
        else:
            if not app.config.get_per('accounts', self.name, 'savepass'):
                # Forget password, it's wrong
                self.password = None
            log.debug("Couldn't authenticate to %s" % self._hostname)
            self.disconnect(on_purpose = True)
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            app.nec.push_incoming_event(InformationEvent(None, conn=self,
                level='error', pri_txt=_('Authentication failed with "%s"') % \
                self._hostname, sec_txt=_('Please check your login and password'
                ' for correctness.')))
            if self.on_connect_auth:
                self.on_connect_auth(None)
                self.on_connect_auth = None
    # END connect

    def send_keepalive(self):
        # nothing received for the last foo seconds
        if self.connection:
            self.connection.send(' ')

    def send_invisible_presence(self, msg, signed, initial = False):
        if not app.account_is_connected(self.name):
            return
        if not self.get_module('PrivacyLists').supported:
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show=app.SHOW_LIST[self.connected]))
            app.nec.push_incoming_event(InformationEvent(
                None, dialog_name='invisibility-not-supported', args=self.name))
            return
        # If we are already connected, and privacy rules are supported, send
        # offline presence first as it's required by XEP-0126
        if self.connected > 1 and self.get_module('PrivacyLists').supported:
            self.on_purpose = True

            self.remove_all_transfers()
            self.get_module('Presence').send_presence(
                typ='unavailable',
                status=msg,
                caps=False)

        # try to set the privacy rule
        self.get_module('PrivacyLists').set_invisible_rule(
            callback=self._continue_invisible,
            msg=msg,
            signed=signed,
            initial=initial)

    def _continue_invisible(self, con, iq_obj, msg, signed, initial):
        if iq_obj.getType() == 'error': # server doesn't support privacy lists
            return
        # active the privacy rule
        self.get_module('PrivacyLists').set_active_list('invisible')
        self.connected = app.SHOW_LIST.index('invisible')
        self.status = msg
        priority = app.get_priority(self.name, 'invisible')

        self.get_module('Presence').send_presence(
            priority=priority,
            status=msg,
            sign=signed)

        self.priority = priority
        app.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='invisible'))
        if initial:
            if not self.avatar_conversion:
                # ask our VCard
                self.get_module('VCardTemp').request_vcard()

            # Get bookmarks
            self.get_module('Bookmarks').get_bookmarks()

            # Get annotations
            self.get_module('Annotations').get_annotations()

            # Blocking
            self.get_module('Blocking').get_blocking_list()

            # Inform GUI we just signed in
            app.nec.push_incoming_event(SignedInEvent(None, conn=self))

    def get_signed_presence(self, msg, callback = None):
        if app.config.get_per('accounts', self.name, 'gpg_sign_presence'):
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
        if not app.account_is_connected(self.name):
            return

        self.connection.set_send_timeout(self.keepalives, self.send_keepalive)
        self.connection.set_send_timeout2(
            self.pingalives, self.get_module('Ping').send_keepalive_ping)
        self.connection.onreceive(None)

        # If we are not resuming, we ask for discovery info
        # and archiving preferences
        if not self.sm.supports_sm or (not self.sm.resuming and self.sm.enabled):
            # This starts the connect_machine
            self.get_module('Discovery').discover_server_info()
            self.get_module('Discovery').discover_account_info()
            self.get_module('Discovery').discover_server_items()

        self.sm.resuming = False  # back to previous state
        # Discover Stun server(s)
        if self._proxy is None:
            hostname = app.config.get_per('accounts', self.name, 'hostname')
            app.resolver.resolve(
                '_stun._udp.' + helpers.idn_to_ascii(hostname),
                self._on_stun_resolved)

    def _on_stun_resolved(self, host, result_array):
        if len(result_array) != 0:
            self._stun_servers = self._hosts = [i for i in result_array]

    @helpers.call_counter
    def connect_machine(self, restart=False):
        log.info('Connect machine state: %s', self._connect_machine_calls)
        if self._connect_machine_calls == 1:
            self.get_module('MetaContacts').get_metacontacts()
        elif self._connect_machine_calls == 2:
            self.get_module('Delimiter').get_roster_delimiter()
        elif self._connect_machine_calls == 3:
            self.get_module('Roster').request_roster()
        elif self._connect_machine_calls == 4:
            self.send_first_presence()

    def send_custom_status(self, show, msg, jid):
        if show not in app.SHOW_LIST:
            return -1
        if not app.account_is_connected(self.name):
            return
        sshow = helpers.get_xmpp_show(show)
        if not msg:
            msg = ''
        if show == 'offline':
            self.get_module('Presence').send_presence(
                jid,
                'unavailable',
                caps=False,
                status=msg)

        else:
            signed = self.get_signed_presence(msg)
            priority = app.get_priority(self.name, sshow)
            self.get_module('Presence').send_presence(
                jid,
                priority=priority,
                show=sshow,
                status=msg,
                sign=signed)

    def _change_to_invisible(self, msg):
        signed = self.get_signed_presence(msg)
        self.send_invisible_presence(msg, signed)

    def _change_from_invisible(self):
        if self.get_module('PrivacyLists').supported:
            self.get_module('PrivacyLists').set_active_list(None)

    def _update_status(self, show, msg, idle_time=None):
        xmpp_show = helpers.get_xmpp_show(show)
        priority = app.get_priority(self.name, xmpp_show)
        signed = self.get_signed_presence(msg)

        self.get_module('Presence').send_presence(
            priority=priority,
            show=xmpp_show,
            status=msg,
            sign=signed,
            idle_time=idle_time)

        if self.connection:
            self.priority = priority
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show=show))

    def send_motd(self, jid, subject='', msg='', xhtml=None):
        if not app.account_is_connected(self.name):
            return
        msg_iq = nbxmpp.Message(to=jid, body=msg, subject=subject,
            xhtml=xhtml)

        self.connection.send(msg_iq)

    def _nec_message_outgoing(self, obj):
        if obj.account != self.name:
            return

        self._prepare_message(obj)

    def _nec_stanza_message_outgoing(self, obj):
        if obj.conn.name != self.name:
            return

        config_key = '%s-%s' % (self.name, obj.jid)
        encryption = app.config.get_per('encryption', config_key, 'encryption')
        if encryption:
            app.plugin_manager.extension_point(
                'encrypt' + encryption, self, obj, self.send_message)
            if not obj.encrypted:
                # Dont propagate event
                return True
        else:
            self.send_message(obj)

    def send_message(self, obj):
        obj.timestamp = time.time()
        obj.stanza_id = self.connection.send(obj.msg_iq, now=obj.now)

        app.nec.push_incoming_event(MessageSentEvent(None, **vars(obj)))

        if isinstance(obj.jid, list):
            for j in obj.jid:
                if obj.session is None:
                    obj.session = self.get_or_create_session(j, '')
                self.log_message(obj, j)
        else:
            self.log_message(obj, obj.jid)

    def send_stanza(self, stanza):
        """
        Send a stanza untouched
        """
        if not self.connection:
            return
        self.connection.send(stanza)

    def unsubscribe_agent(self, agent):
        if not app.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq('set', nbxmpp.NS_REGISTER, to=agent)
        iq.setQuery().setTag('remove')
        id_ = self.connection.getAnID()
        iq.setID(id_)
        self.awaiting_answers[id_] = (AGENT_REMOVED, agent)
        self.connection.send(iq)
        self.getRoster().del_item(agent)

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
        app.resolver.resolve('_xmppconnect.' + helpers.idn_to_ascii(
            self._hostname), self._on_resolve_txt, type_='txt')

    def _on_new_account(self, con=None, con_type=None):
        if not con_type:
            if self._hosts:
                # There are still other way to try to connect
                return
            reason = _('Could not connect to "%s"') % self._hostname
            app.nec.push_incoming_event(NewAccountNotConnectedEvent(None,
                conn=self, reason=reason))
            return
        self.on_connect_failure = None
        self.connection = con
        nbxmpp.features_nb.getRegInfo(con, self._hostname)

    def request_gateway_prompt(self, jid, prompt=None):
        def _on_prompt_result(resp):
            app.nec.push_incoming_event(GatewayPromptReceivedEvent(None,
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

    def getRoster(self):
        return self.get_module('Roster')

    def send_agent_status(self, agent, ptype):
        if not app.account_is_connected(self.name):
            return
        show = helpers.get_xmpp_show(app.SHOW_LIST[self.connected])

        self.get_module('Presence').send_presence(
            agent,
            ptype,
            show=show,
            caps=ptype != 'unavailable')

    def send_captcha(self, jid, form_node):
        if not app.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='set', to=jid)
        captcha = iq.addChild(name='captcha', namespace=nbxmpp.NS_CAPTCHA)
        captcha.addChild(node=form_node)
        self.connection.send(iq)

    def check_unique_room_id_support(self, server, instance):
        if not app.account_is_connected(self.name):
            return
        iq = nbxmpp.Iq(typ='get', to=server)
        iq.setAttr('id', 'unique1')
        iq.addChild('unique', namespace=nbxmpp.NS_MUC_UNIQUE)
        def _on_response(resp):
            if not nbxmpp.isResultNode(resp):
                app.nec.push_incoming_event(UniqueRoomIdNotSupportedEvent(
                    None, conn=self, instance=instance, server=server))
                return
            app.nec.push_incoming_event(UniqueRoomIdSupportedEvent(None,
                conn=self, instance=instance, server=server,
                room_id=resp.getTag('unique').getData()))
        self.connection.SendAndCallForResponse(iq, _on_response)

    def join_gc(self, nick, room_jid, password, change_nick=False,
    rejoin=False):
        # FIXME: This room JID needs to be normalized; see #1364
        if not app.account_is_connected(self.name):
            return
        show = helpers.get_xmpp_show(app.SHOW_LIST[self.connected])
        if show == 'invisible':
            # Never join a room when invisible
            return

        self.get_module('Discovery').disco_muc(
            room_jid, partial(self._join_gc, nick, show, room_jid,
                              password, change_nick, rejoin))

    def _join_gc(self, nick, show, room_jid, password, change_nick, rejoin):
        if change_nick:
            self.get_module('Presence').send_presence(
                '%s/%s' % (room_jid, nick),
                show=show,
                status=self.status)
        else:
            self.get_module('MUC').send_muc_join_presence(
                '%s/%s' % (room_jid, nick),
                show=show,
                status=self.status,
                room_jid=room_jid,
                password=password,
                rejoin=rejoin)

    def _nec_gc_message_outgoing(self, obj):
        if obj.account != self.name:
            return
        if not app.account_is_connected(self.name):
            return

        if not obj.xhtml and app.config.get('rst_formatting_outgoing_messages'):
            from gajim.common.rst_xhtml_generator import create_xhtml
            obj.xhtml = create_xhtml(obj.message)

        msg_iq = nbxmpp.Message(obj.jid, obj.message, typ='groupchat',
                                xhtml=obj.xhtml)

        obj.stanza_id = self.connection.getAnID()
        msg_iq.setID(obj.stanza_id)
        if obj.message:
            msg_iq.setOriginID(obj.stanza_id)

        if obj.correct_id:
            msg_iq.setTag('replace', attrs={'id': obj.correct_id},
                          namespace=nbxmpp.NS_CORRECT)

        if obj.chatstate:
            msg_iq.setTag(obj.chatstate, namespace=nbxmpp.NS_CHATSTATES)
            if not obj.message:
                msg_iq.setTag('no-store', namespace=nbxmpp.NS_MSG_HINTS)
        if obj.label is not None:
            msg_iq.addChild(node=obj.label)

        obj.msg_iq = msg_iq
        obj.conn = self
        app.nec.push_incoming_event(GcStanzaMessageOutgoingEvent(None, **vars(obj)))

    def _nec_gc_stanza_message_outgoing(self, obj):
        if obj.conn.name != self.name:
            return

        config_key = '%s-%s' % (self.name, obj.jid)
        encryption = app.config.get_per('encryption', config_key, 'encryption')
        if encryption:
            app.plugin_manager.extension_point(
                'gc_encrypt' + encryption, self, obj, self.send_gc_message)
        else:
            self.send_gc_message(obj)

    def send_gc_message(self, obj):
        obj.stanza_id = self.connection.send(obj.msg_iq)
        app.nec.push_incoming_event(MessageSentEvent(
            None, conn=self, jid=obj.jid, message=obj.message, keyID=None,
            chatstate=None, automatic_message=obj.automatic_message,
            stanza_id=obj.stanza_id, additional_data=obj.additional_data))

    def send_gc_status(self, nick, jid, show, status, auto=False):
        if not app.account_is_connected(self.name):
            return
        if show == 'invisible':
            show = 'offline'
        ptype = None
        if show == 'offline':
            ptype = 'unavailable'
        xmpp_show = helpers.get_xmpp_show(show)

        idle_time = None
        if auto and app.is_installed('IDLE') and app.config.get('autoaway'):
            idle_sec = idle.Monitor.get_idle_sec()
            idle_time = time.strftime('%Y-%m-%dT%H:%M:%SZ',
                                      time.gmtime(time.time() - idle_sec))

        self.get_module('Presence').send_presence(
            '%s/%s' % (jid, nick),
            typ=ptype,
            show=xmpp_show,
            status=status,
            caps=ptype != 'unavailable',
            idle_time=idle_time)

    def get_password(self, callback, type_):
        if app.config.get_per('accounts', self.name, 'anonymous_auth') and \
        type_ != 'ANONYMOUS':
            app.nec.push_incoming_event(NonAnonymousServerErrorEvent(None,
                conn=self))
            self._on_disconnected()
            return
        self.pasword_callback = (callback, type_)
        if type_ == 'X-MESSENGER-OAUTH2':
            client_id = app.config.get_per('accounts', self.name,
                'oauth2_client_id')
            refresh_token = app.config.get_per('accounts', self.name,
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
            script_url = app.config.get_per('accounts', self.name,
                'oauth2_redirect_url')
            token_URL = 'https://oauth.live.com/authorize?client_id=' \
                '%(client_id)s&scope=wl.messenger%%20wl.offline_access&' \
                'response_type=code&redirect_uri=%(script_url)s' % locals()
            helpers.launch_browser_mailer('url', token_URL)
            self.disconnect(on_purpose=True)
            app.nec.push_incoming_event(Oauth2CredentialsRequiredEvent(None,
                conn=self))
            return
        if self.password:
            self.set_password(self.password)
            return
        app.nec.push_incoming_event(PasswordRequiredEvent(None, conn=self))

    def set_password(self, password):
        self.password = password
        if self.pasword_callback:
            callback, type_ = self.pasword_callback
            if self._current_type == 'plain' and type_ == 'PLAIN' and \
            app.config.get_per('accounts', self.name,
            'warn_when_insecure_password'):
                app.nec.push_incoming_event(InsecurePasswordEvent(None,
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
            self.removing_account = True
            if app.account_is_connected(self.name):
                hostname = app.config.get_per('accounts', self.name, 'hostname')
                iq = nbxmpp.Iq(typ='set', to=hostname)
                id_ = self.connection.getAnID()
                iq.setID(id_)
                iq.setTag(nbxmpp.NS_REGISTER + ' query').setTag('remove')
                def _on_answer(con, result):
                    if result.getID() == id_:
                        on_remove_success(True)
                        return
                    app.nec.push_incoming_event(InformationEvent(
                        None, dialog_name='unregister-error',
                        kwargs={'server': hostname, 'error': result.getErrorMsg()}))
                    on_remove_success(False)
                con.RegisterHandler('iq', _on_answer, 'result', system=True)
                con.SendAndWaitForResponse(iq)
                return
            on_remove_success(False)
            self.removing_account = False
        if self.connected == 0:
            self.on_connect_auth = _on_unregister_account_connect
            self.connect_and_auth()
        else:
            _on_unregister_account_connect(self.connection)

    def _reconnect_alarm(self):
        if not app.config.get_per('accounts', self.name, 'active'):
            # Account may have been disabled
            return
        if self.time_to_reconnect:
            if self.connected < 2:
                self.reconnect()
            else:
                self.time_to_reconnect = None
