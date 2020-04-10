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

import logging

import nbxmpp
from nbxmpp.client import Client as NBXMPPClient
from nbxmpp.const import StreamError
from nbxmpp.const import ConnectionType

from gi.repository import GLib

from gajim.common import passwords
from gajim.common.nec import NetworkEvent

from gajim.common import app
from gajim.common import helpers
from gajim.common import modules
from gajim.common.const import ClientState
from gajim.common.helpers import get_encryption_method
from gajim.common.helpers import get_custom_host
from gajim.common.helpers import get_user_proxy
from gajim.common.helpers import warn_about_plain_connection
from gajim.common.helpers import get_resource
from gajim.common.helpers import get_ignored_ssl_errors
from gajim.common.i18n import _

from gajim.common.connection_handlers import ConnectionHandlers
from gajim.common.connection_handlers_events import OurShowEvent
from gajim.common.connection_handlers_events import MessageSentEvent

from gajim.gtk.util import open_window


log = logging.getLogger('gajim.client')


class Client(ConnectionHandlers):
    def __init__(self, account):
        self._client = None
        self._account = account
        self.name = account
        self._hostname = app.config.get_per(
            'accounts', self._account, 'hostname')
        self._user = app.config.get_per('accounts', self._account, 'name')
        self.password = None

        self._priority = 0
        self.handlers_registered = False
        self._connect_machine_calls = 0
        self.avatar_conversion = False
        self.addressing_supported = False

        self.is_zeroconf = False
        self.pep = {}
        self.roster_supported = True

        self._state = ClientState.DISCONNECTED
        self._status = 'online'
        self._status_message = ''

        self._reconnect = True
        self._reconnect_timer_source = None
        self._destroy_client = False
        self._remove_account = False

        self._ssl_errors = set()

        self.available_transports = {}

        # Register all modules
        modules.register_modules(self)

        self._create_client()

        ConnectionHandlers.__init__(self)

    def _set_state(self, state):
        log.info('State: %s', state)
        self._state = state

    @property
    def state(self):
        return self._state

    @property
    def status(self):
        return self._status

    @property
    def status_message(self):
        return self._status_message

    @property
    def priority(self):
        return self._priority

    @property
    def certificate(self):
        return self._client.peer_certificate[0]

    @property
    def features(self):
        return self._client.features

    def set_remove_account(self, value):
        # Used by the RemoveAccount Assistant to make the Client
        # not react to any stream errors that happen while the
        # account is removed by the server and the connection is killed
        self._remove_account = value

    def _create_client(self):
        log.info('Create new nbxmpp client')
        self._client = NBXMPPClient(log_context=self._account)
        self.connection = self._client
        self._client.set_domain(self._hostname)
        self._client.set_username(self._user)
        self._client.set_resource(get_resource(self._account))

        custom_host = get_custom_host(self._account)
        if custom_host is not None:
            self._client.set_custom_host(*custom_host)

        pass_saved = app.config.get_per('accounts', self._account, 'savepass')
        if pass_saved:
            # Request password from keyring only if the user chose to save
            # his password
            self.password = passwords.get_password(self._account)

        self._client.set_password(self.password)
        self._client.set_accepted_certificates(
            app.cert_store.get_certificates())

        self._client.set_ignored_tls_errors(
            get_ignored_ssl_errors(self._account))

        if app.config.get_per('accounts', self._account,
                              'use_plain_connection'):
            self._client.set_connection_types([ConnectionType.PLAIN])

        proxy = get_user_proxy(self._account)
        if proxy is not None:
            self._client.set_proxy(proxy)

        self._client.subscribe('resume-failed', self._on_resume_failed)
        self._client.subscribe('resume-successful', self._on_resume_successful)
        self._client.subscribe('disconnected', self._on_disconnected)
        self._client.subscribe('connection-failed', self._on_connection_failed)
        self._client.subscribe('connected', self._on_connected)

        self._client.subscribe('stanza-sent', self._on_stanza_sent)
        self._client.subscribe('stanza-received', self._on_stanza_received)

        self._register_new_handlers()

    def process_ssl_errors(self):
        if not self._ssl_errors:
            self.connect(ignore_all_errors=True)
            return

        open_window('SSLErrorDialog',
                    account=self._account,
                    connection=self,
                    cert=self._client.peer_certificate[0],
                    error_num=self._ssl_errors.pop())

    def _on_resume_failed(self, _client, _signal_name):
        log.info('Resume failed')
        app.nec.push_incoming_event(OurShowEvent(
            None, conn=self, show='offline'))
        self.get_module('Chatstate').enabled = False

    def _on_resume_successful(self, _client, _signal_name):
        self._set_state(ClientState.CONNECTED)
        self._set_client_available()

    def _set_client_available(self):
        self._set_state(ClientState.AVAILABLE)
        app.nec.push_incoming_event(NetworkEvent('account-connected',
                                                 account=self._account))

        app.nec.push_incoming_event(
            OurShowEvent(None, conn=self, show=self._status))

    def disconnect(self, gracefully, reconnect, destroy_client=False):
        if self._state.is_disconnecting:
            log.warning('Disconnect already in progress')
            return

        self._set_state(ClientState.DISCONNECTING)
        self._reconnect = reconnect
        self._destroy_client = destroy_client

        log.info('Starting to disconnect %s', self._account)
        self._client.disconnect(immediate=not gracefully)

    def _on_disconnected(self, _client, _signal_name):
        log.info('Disconnect %s', self._account)
        self._set_state(ClientState.DISCONNECTED)

        domain, error, text = self._client.get_error()

        if self._remove_account:
            # Account was removed via RemoveAccount Assistant.
            self._reconnect = False

        elif domain == StreamError.BAD_CERTIFICATE:
            self._ssl_errors = self._client.peer_certificate[1]
            self.get_module('Chatstate').enabled = False
            self._reconnect = False
            self._after_disconnect()
            app.nec.push_incoming_event(OurShowEvent(
                None, conn=self, show='offline'))
            self.process_ssl_errors()

        elif domain in (StreamError.STREAM, StreamError.BIND):
            if error == 'conflict':
                # Reset resource
                app.config.set_per('accounts', self._account,
                                   'resource', 'gajim.$rand')

        elif domain == StreamError.SASL:
            self._reconnect = False

            if error in ('not-authorized', 'no-password'):
                def _on_password(password):
                    self.password = password
                    self._client.set_password(password)
                    self.connect()

                app.nec.push_incoming_event(NetworkEvent(
                    'password-required', conn=self, on_password=_on_password))

            app.nec.push_incoming_event(
                NetworkEvent('simple-notification',
                             account=self._account,
                             type_='connection-failed',
                             title=_('Authentication failed'),
                             text=text or error))

        if self._reconnect:
            self._after_disconnect()
            self._schedule_reconnect()
            app.nec.push_incoming_event(
                OurShowEvent(None, conn=self, show='error'))

        else:
            self.get_module('Chatstate').enabled = False
            app.nec.push_incoming_event(OurShowEvent(
                None, conn=self, show='offline'))
            self._after_disconnect()

    def _after_disconnect(self):
        self._disable_reconnect_timer()

        app.interface.music_track_changed(None, None, self._account)
        self.get_module('VCardAvatars').avatar_advertised = False

        app.proxy65_manager.disconnect(self._client)
        self.terminate_sessions()
        self.get_module('Bytestream').remove_all_transfers()

        if self._destroy_client:
            self._client.destroy()
            self._destroy_client = False
            self._create_client()

        app.nec.push_incoming_event(NetworkEvent('account-disconnected',
                                                 account=self._account))

    def _on_connection_failed(self, _client, _signal_name):
        self._schedule_reconnect()

    def _on_connected(self, _client, _signal_name):
        self._set_state(ClientState.CONNECTED)
        self.get_module('Discovery').discover_server_info()
        self.get_module('Discovery').discover_account_info()
        self.get_module('Discovery').discover_server_items()
        self.get_module('Chatstate').enabled = True
        self.get_module('MAM').reset_state()

    def _on_stanza_sent(self, _client, _signal_name, stanza):
        app.nec.push_incoming_event(NetworkEvent('stanza-sent',
                                                 account=self._account,
                                                 stanza=stanza))

    def _on_stanza_received(self, _client, _signal_name, stanza):
        app.nec.push_incoming_event(NetworkEvent('stanza-received',
                                                 account=self._account,
                                                 stanza=stanza))
    def get_own_jid(self):
        """
        Return the last full JID we received on a bind event.
        In case we were never connected it returns the bare JID from config.
        """
        if self._client is not None:
            jid = self._client.get_bound_jid()
            if jid is not None:
                return jid

        # This returns the bare jid
        return nbxmpp.JID(app.get_jid_from_account(self._account))

    def change_status(self, show, msg, auto=False):
        if not msg:
            msg = ''

        if show != 'offline':
            self._status = show
        self._status_message = msg

        if self._state.is_disconnecting:
            log.warning('Can\'t change status while '
                        'disconnect is in progress')
            return

        if self._state.is_disconnected:
            if show == 'offline':
                return

            self.connect()
            return

        if self._state.is_connecting:
            if show == 'offline':
                self.disconnect(gracefully=False,
                                reconnect=False,
                                destroy_client=True)
            return

        if self._state.is_reconnect_scheduled:
            if show == 'offline':
                self._destroy_client = True
                self._abort_reconnect()
            else:
                self.connect()
            return

        # We are connected
        if show == 'offline':
            presence = self.get_module('Presence').get_presence(
                typ='unavailable',
                status=msg,
                caps=False)

            self.send_stanza(presence)
            self.disconnect(gracefully=True,
                            reconnect=False,
                            destroy_client=True)
            return

        self._priority = app.get_priority(self._account, show)

        self.get_module('Presence').send_presence(
            priority=self._priority,
            show=show,
            status=msg,
            idle_time=auto)

        self.get_module('MUC').update_presence(auto=auto)

        app.nec.push_incoming_event(
            OurShowEvent(None, conn=self, show=show))

    def _register_new_handlers(self):
        for handler in modules.get_handlers(self):
            if len(handler) == 5:
                name, func, typ, ns, priority = handler
                self._client.register_handler(
                    name, func, typ, ns, priority=priority)
            else:
                self._client.register_handler(*handler)
        self.handlers_registered = True

    def get_module(self, name):
        return modules.get(self._account, name)

    @helpers.call_counter
    def connect_machine(self):
        log.info('Connect machine state: %s', self._connect_machine_calls)
        if self._connect_machine_calls == 1:
            self.get_module('MetaContacts').get_metacontacts()
        elif self._connect_machine_calls == 2:
            self.get_module('Delimiter').get_roster_delimiter()
        elif self._connect_machine_calls == 3:
            self.get_module('Roster').request_roster()
        elif self._connect_machine_calls == 4:
            self._send_first_presence()

    def _send_first_presence(self):
        self._priority = app.get_priority(self._account, self._status)

        self.get_module('Presence').send_presence(
            priority=self._priority,
            show=self._status,
            status=self._status_message)

        self._set_client_available()

        if not self.avatar_conversion:
            # ask our VCard
            self.get_module('VCardTemp').request_vcard()

        self.get_module('Bookmarks').request_bookmarks()
        self.get_module('SoftwareVersion').set_enabled(True)
        self.get_module('Annotations').request_annotations()
        self.get_module('Blocking').get_blocking_list()

        # Inform GUI we just signed in
        app.nec.push_incoming_event(NetworkEvent('signed-in', conn=self))
        modules.send_stored_publish(self._account)

    def send_stanza(self, stanza):
        """
        Send a stanza untouched
        """
        return self._client.send_stanza(stanza)

    def send_message(self, message):
        if not self._state.is_available:
            log.warning('Trying to send message while offline')
            return

        stanza = self.get_module('Message').build_message_stanza(message)
        message.stanza = stanza

        method = get_encryption_method(message.account, message.jid)
        if method is not None:
            # TODO: Make extension point return encrypted message

            extension = 'encrypt'
            if message.is_groupchat:
                extension = 'gc_encrypt'
            app.plugin_manager.extension_point(extension + method,
                                               self,
                                               message,
                                               self._send_message)
            return

        self._send_message(message)

    def _send_message(self, message):
        message.set_sent_timestamp()
        message.message_id = self.send_stanza(message.stanza)

        app.nec.push_incoming_event(
            MessageSentEvent(None, jid=message.jid, **vars(message)))

        if message.is_groupchat:
            return

        self.get_module('Message').log_message(message)

    def send_messages(self, jids, message):
        if not self._state.is_available:
            log.warning('Trying to send message while offline')
            return

        for jid in jids:
            message = message.copy()
            message.contact = app.contacts.create_contact(jid, message.account)
            stanza = self.get_module('Message').build_message_stanza(message)
            message.stanza = stanza
            self._send_message(message)

    def connect(self, ignore_all_errors=False):
        if self._state not in (ClientState.DISCONNECTED,
                               ClientState.RECONNECT_SCHEDULED):
            # Do not try to reco while we are already trying
            return

        log.info('Connect')
        self._reconnect = True
        self._disable_reconnect_timer()
        self._set_state(ClientState.CONNECTING)
        if ignore_all_errors:
            self._client.set_ignore_tls_errors(True)
            self._client.connect()
        else:
            if warn_about_plain_connection(self._account,
                                           self._client.connection_types):
                app.nec.push_incoming_event(NetworkEvent(
                    'plain-connection',
                    account=self._account,
                    connect=self._client.connect,
                    abort=self._abort_reconnect))
                return
            self._client.connect()

    def _schedule_reconnect(self):
        self._set_state(ClientState.RECONNECT_SCHEDULED)
        if app.status_before_autoaway[self._account]:
            # We were auto away. So go back online
            self._status_message = app.status_before_autoaway[self._account]
            app.status_before_autoaway[self._account] = ''
            self._status = 'online'

        log.info("Reconnect to %s in 3s", self._account)
        self._reconnect_timer_source = GLib.timeout_add_seconds(
            3, self.connect)

    def _abort_reconnect(self):
        self._set_state(ClientState.DISCONNECTED)
        self._disable_reconnect_timer()
        app.nec.push_incoming_event(
            OurShowEvent(None, conn=self, show='offline'))

        if self._destroy_client:
            self._client.destroy()
            self._destroy_client = False
            self._create_client()

    def _disable_reconnect_timer(self):
        if self._reconnect_timer_source is not None:
            GLib.source_remove(self._reconnect_timer_source)
            self._reconnect_timer_source = None

    def cleanup(self):
        pass

    def quit(self, kill_core):
        if kill_core and self._state in (ClientState.CONNECTING,
                                         ClientState.CONNECTED,
                                         ClientState.AVAILABLE):
            self.disconnect(gracefully=True, reconnect=False)
