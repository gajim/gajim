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

from __future__ import annotations

from typing import Any
from typing import Optional

import logging

import nbxmpp
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp.client import Client as NBXMPPClient
from nbxmpp.const import ConnectionType
from nbxmpp.const import StreamError
from nbxmpp.protocol import JID

from gajim.common import app
from gajim.common import helpers
from gajim.common import modules
from gajim.common import passwords
from gajim.common.const import ClientState
from gajim.common.const import SimpleClientState
from gajim.common.events import AccountConnected
from gajim.common.events import AccountDisconnected
from gajim.common.events import MessageSent
from gajim.common.events import Notification
from gajim.common.events import PasswordRequired
from gajim.common.events import PlainConnection
from gajim.common.events import SignedIn
from gajim.common.events import StanzaReceived
from gajim.common.events import StanzaSent
from gajim.common.helpers import get_account_proxy
from gajim.common.helpers import get_custom_host
from gajim.common.helpers import get_idle_status_message
from gajim.common.helpers import get_resource
from gajim.common.helpers import Observable
from gajim.common.helpers import warn_about_plain_connection
from gajim.common.i18n import _
from gajim.common.idle import IdleMonitorManager
from gajim.common.idle import Monitor
from gajim.common.structs import OutgoingMessage
from gajim.common.util.http import create_http_session
from gajim.gui.util import open_window

log = logging.getLogger('gajim.client')


IgnoredTlsErrorsT = Optional[set[Gio.TlsCertificateFlags]]


class Client(Observable):
    def __init__(self, account: str) -> None:
        Observable.__init__(self, log)
        self._client = None
        self._account = account
        self.name = account
        self._hostname = app.settings.get_account_setting(self._account,
                                                          'hostname')
        self._user = app.settings.get_account_setting(self._account, 'name')
        self.password = None

        self._priority = 0
        self._connect_machine_calls = 0
        self.addressing_supported = False

        self.roster_supported = True

        self._state = ClientState.DISCONNECTED
        self._status_sync_on_resume = False
        self._status = 'online'
        self._status_message = ''
        self._idle_status = 'online'
        self._idle_status_enabled = True
        self._idle_status_message = ''

        self._reconnect = True
        self._reconnect_timer_source = None
        self._destroy_client = False
        self._remove_account = False

        self._destroyed = False

        self.available_transports = {}

        modules.register_modules(self)

        self._create_client()

        if Monitor.is_available():
            self._idle_handler_id = Monitor.connect('state-changed',
                                                    self._idle_state_changed)
            self._screensaver_handler_id = app.app.connect(
                'notify::screensaver-active', self._screensaver_state_changed)

    def _set_state(self, state: ClientState) -> None:
        log.info('State: %s', state)
        self._state = state

    @property
    def state(self) -> ClientState:
        return self._state

    @property
    def account(self) -> str:
        return self._account

    @property
    def status(self) -> str:
        return self._status

    @property
    def status_message(self) -> str:
        if self._idle_status_active():
            return self._idle_status_message
        return self._status_message

    @property
    def priority(self) -> int:
        return self._priority

    @property
    def certificate(self):
        return self._client.peer_certificate[0]

    @property
    def features(self):
        return self._client.features

    @property
    def local_address(self) -> Optional[str]:
        address = self._client.local_address
        if address is not None:
            return address.to_string().split(':')[0]
        return None

    def is_destroyed(self) -> bool:
        return self._destroyed

    def set_remove_account(self, value: bool) -> None:
        # Used by the RemoveAccount Assistant to make the Client
        # not react to any stream errors that happen while the
        # account is removed by the server and the connection is killed
        self._remove_account = value

    def _create_client(self) -> None:
        log.info('Create new nbxmpp client')
        self._client = NBXMPPClient(log_context=self._account)
        self.connection = self._client
        self._client.set_domain(self._hostname)
        self._client.set_username(self._user)
        self._client.set_resource(get_resource(self._account))

        pass_saved = app.settings.get_account_setting(self._account, 'savepass')
        if pass_saved:
            # Request password from keyring only if the user chose to save
            # his password
            self.password = passwords.get_password(self._account)

        self._client.set_password(self.password)

        self._client.set_http_session(create_http_session())

        self._client.subscribe('resume-failed', self._on_resume_failed)
        self._client.subscribe('resume-successful', self._on_resume_successful)
        self._client.subscribe('disconnected', self._on_disconnected)
        self._client.subscribe('connection-failed', self._on_connection_failed)
        self._client.subscribe('connected', self._on_connected)

        self._client.subscribe('stanza-sent', self._on_stanza_sent)
        self._client.subscribe('stanza-received', self._on_stanza_received)

        for handler in modules.get_handlers(self):
            self._client.register_handler(handler)

    def _on_resume_failed(self,
                          _client: NBXMPPClient,
                          _signal_name: str) -> None:

        log.info('Resume failed')
        self.notify('resume-failed')

    def _on_resume_successful(self,
                              _client: NBXMPPClient,
                              _signal_name: str) -> None:

        self._set_state(ClientState.CONNECTED)
        self._set_client_available()

        if self._status_sync_on_resume:
            self._status_sync_on_resume = False
            self.update_presence()

        self.notify('state-changed', SimpleClientState.CONNECTED)

    def _set_client_available(self) -> None:
        self._set_state(ClientState.AVAILABLE)
        app.ged.raise_event(AccountConnected(account=self._account))

    def disconnect(self,
                   gracefully: bool,
                   reconnect: bool,
                   destroy_client: bool = False) -> None:

        if self._state.is_disconnecting:
            log.warning('Disconnect already in progress')
            return

        self._set_state(ClientState.DISCONNECTING)
        self._reconnect = reconnect
        self._destroy_client = destroy_client

        log.info('Starting to disconnect %s', self._account)
        self._client.disconnect(immediate=not gracefully)

    def _on_disconnected(self,
                         _client: NBXMPPClient,
                         _signal_name: str) -> None:

        log.info('Disconnect %s', self._account)
        self._set_state(ClientState.DISCONNECTED)

        domain, error, text = self._client.get_error()

        if self._remove_account:
            # Account was removed via RemoveAccount Assistant.
            self._reconnect = False

        elif domain == StreamError.BAD_CERTIFICATE:
            self._reconnect = False
            self._destroy_client = True

            cert, errors = self._client.peer_certificate

            open_window('SSLErrorDialog',
                        account=self._account,
                        client=self,
                        cert=cert,
                        error=errors.pop())

        elif domain in (StreamError.STREAM, StreamError.BIND):
            if error == 'conflict':
                # Reset resource
                app.settings.set_account_setting(self._account,
                                                 'resource',
                                                 'gajim.$rand')
            if error == 'system-shutdown':
                app.ged.raise_event(
                    Notification(account=self._account,
                                 type='server-shutdown',
                                 title=_('Server Shutdown'),
                                 text=text or _('The server was shut down.')))

        elif domain == StreamError.SASL:
            self._reconnect = False
            self._destroy_client = True

            if error in ('not-authorized', 'no-password'):
                def _on_password(password: str) -> None:
                    self.password = password
                    self._client.set_password(password)
                    self._prepare_for_connect()

                app.ged.raise_event(PasswordRequired(client=self,
                                                     on_password=_on_password))

            app.ged.raise_event(
                Notification(account=self._account,
                             type='connection-failed',
                             title=_('Authentication failed'),
                             text=text or error))

        if self._reconnect:
            self._after_disconnect()
            self._schedule_reconnect()
            if not self._client.resumeable:
                self.notify('state-changed', SimpleClientState.DISCONNECTED)
            self.notify('state-changed', SimpleClientState.RESUME_IN_PROGRESS)

        else:
            self._after_disconnect()
            self.notify('state-changed', SimpleClientState.DISCONNECTED)

    def _after_disconnect(self) -> None:
        self._disable_reconnect_timer()

        app.proxy65_manager.disconnect(self._client)
        self.get_module('Bytestream').remove_all_transfers()

        if self._destroy_client:
            self._client.destroy()
            self._client = None
            self._destroy_client = False
            self._create_client()

        app.ged.raise_event(AccountDisconnected(account=self._account))

    def _on_connection_failed(self,
                              _client: NBXMPPClient,
                              _signal_name: str) -> None:
        self._schedule_reconnect()

    def _on_connected(self,
                      _client: NBXMPPClient,
                      _signal_name: str) -> None:

        self._set_state(ClientState.CONNECTED)
        self.get_module('Discovery').discover_server_info()
        self.get_module('Discovery').discover_account_info()
        self.get_module('Discovery').discover_server_items()

    def _on_stanza_sent(self,
                        _client: NBXMPPClient,
                        _signal_name: str,
                        stanza: Any) -> None:

        app.ged.raise_event(StanzaSent(account=self._account,
                                       stanza=stanza))

    def _on_stanza_received(self,
                            _client: NBXMPPClient,
                            _signal_name: str,
                            stanza: Any) -> None:

        app.ged.raise_event(StanzaReceived(account=self._account,
                                           stanza=stanza))

    def get_own_jid(self) -> JID:
        '''
        Return the last full JID we received on a bind event.
        In case we were never connected it returns the bare JID from config.
        '''
        if self._client is not None:
            jid = self._client.get_bound_jid()
            if jid is not None:
                return jid

        # This returns the bare jid
        return nbxmpp.JID.from_string(app.get_jid_from_account(self._account))

    def change_status(self, show: str, message: str) -> None:
        if not message:
            message = ''

        self._idle_status_enabled = show == 'online'
        self._status_message = message

        if show != 'offline':
            self._status = show

            app.settings.set_account_setting(
                self._account,
                'last_status',
                show)
            app.settings.set_account_setting(
                self._account,
                'last_status_msg',
                helpers.to_one_line(message))

        if self._state.is_disconnecting:
            log.warning("Can\'t change status while "
                        'disconnect is in progress')
            return

        if self._state.is_disconnected:
            if show == 'offline':
                return

            self._prepare_for_connect()
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
                self._prepare_for_connect()
            return

        # We are connected
        if show == 'offline':
            self.get_module('UserTune').set_tune(None)
            self.get_module('UserLocation').set_location(None)
            presence = self.get_module('Presence').get_presence(
                typ='unavailable',
                status=message,
                caps=False)

            self.send_stanza(presence)
            self.disconnect(gracefully=True,
                            reconnect=False,
                            destroy_client=True)
            return

        self.update_presence()

    def update_presence(self, include_muc: bool = True) -> None:
        status, message, idle = self.get_presence_state()
        self._priority = app.get_priority(self._account, status)
        self.get_module('Presence').send_presence(
            priority=self._priority,
            show=status,
            status=message,
            idle_time=idle)

        if include_muc:
            self.get_module('MUC').update_presence()

    def get_module(self, name: str):
        return modules.get(self._account, name)

    @helpers.call_counter
    def connect_machine(self) -> None:
        log.info('Connect machine state: %s', self._connect_machine_calls)
        if self._connect_machine_calls == 1:
            self.get_module('Delimiter').get_roster_delimiter()
        elif self._connect_machine_calls == 2:
            self.get_module('Roster').request_roster()
        elif self._connect_machine_calls == 3:
            self._finish_connect()

    def _finish_connect(self) -> None:
        self._status_sync_on_resume = False
        self._set_client_available()

        # We did not resume the stream, so we are not joined any MUCs
        self.update_presence(include_muc=False)

        self.get_module('Bookmarks').request_bookmarks()
        self.get_module('SoftwareVersion').set_enabled(True)
        self.get_module('EntityTime').set_enabled(True)
        self.get_module('LastActivity').set_enabled(True)
        self.get_module('Annotations').request_annotations()
        self.get_module('Blocking').get_blocking_list()

        if app.settings.get_account_setting(self._account, 'publish_tune'):
            self.get_module('UserTune').set_enabled(True)

        self.notify('state-changed', SimpleClientState.CONNECTED)

        app.ged.raise_event(SignedIn(account=self._account, conn=self))
        modules.send_stored_publish(self._account)

    def send_stanza(self, stanza: Any) -> None:
        '''
        Send a stanza untouched
        '''
        return self._client.send_stanza(stanza)

    def send_message(self, message: OutgoingMessage) -> None:
        if not self._state.is_available:
            log.warning('Trying to send message while offline')
            return

        stanza = self.get_module('Message').build_message_stanza(message)
        message.stanza = stanza

        method = message.contact.settings.get('encryption')
        if not method:
            self._send_message(message)
            return

        # TODO: Make extension point return encrypted message
        extension = 'encrypt'
        if message.is_groupchat:
            extension = 'gc_encrypt'
        app.plugin_manager.extension_point(extension + method,
                                           self,
                                           message,
                                           self._send_message)

    def _send_message(self, message: OutgoingMessage) -> None:
        message.set_sent_timestamp()
        message.message_id = self.send_stanza(message.stanza)

        log_line_id = None
        if not message.is_groupchat:
            log_line_id = self.get_module('Message').log_message(message)

        app.ged.raise_event(
            MessageSent(jid=message.jid,
                        account=message.account,
                        message=message.message,
                        chatstate=message.chatstate,
                        timestamp=message.timestamp,
                        additional_data=message.additional_data,
                        label=message.label,
                        correct_id=message.correct_id,
                        message_id=message.message_id,
                        msg_log_id=log_line_id,
                        play_sound=message.play_sound))

    def _prepare_for_connect(self) -> None:
        custom_host = get_custom_host(self._account)
        if custom_host is not None:
            self._client.set_custom_host(*custom_host)

        gssapi = app.settings.get_account_setting(self._account,
                                                  'enable_gssapi')
        if gssapi:
            self._client.set_mechs(['GSSAPI'])

        anonymous = app.settings.get_account_setting(self._account,
                                                     'anonymous_auth')
        if anonymous:
            self._client.set_mechs(['ANONYMOUS'])

        if app.settings.get_account_setting(self._account,
                                            'use_plain_connection'):
            self._client.set_connection_types([ConnectionType.PLAIN])

        proxy = get_account_proxy(self._account)
        if proxy is not None:
            self._client.set_proxy(proxy)

        self.connect()

    def connect(self, ignored_tls_errors: IgnoredTlsErrorsT = None) -> None:
        if self._state not in (ClientState.DISCONNECTED,
                               ClientState.RECONNECT_SCHEDULED):
            # Do not try to reco while we are already trying
            return

        log.info('Connect')

        self._client.set_accepted_certificates(
            app.cert_store.get_certificates())
        self._client.set_ignored_tls_errors(ignored_tls_errors)
        self._reconnect = True
        self._disable_reconnect_timer()
        self._set_state(ClientState.CONNECTING)
        self.notify('state-changed', SimpleClientState.CONNECTING)

        if warn_about_plain_connection(self._account,
                                       self._client.connection_types):
            app.ged.raise_event(PlainConnection(account=self._account,
                                                connect=self._client.connect,
                                                abort=self._abort_reconnect))
            return

        self._client.connect()

    def _schedule_reconnect(self) -> None:
        self._set_state(ClientState.RECONNECT_SCHEDULED)
        log.info('Reconnect to %s in 3s', self._account)
        self._reconnect_timer_source = GLib.timeout_add_seconds(
            3, self._prepare_for_connect)

    def _abort_reconnect(self) -> None:
        self._set_state(ClientState.DISCONNECTED)
        self._disable_reconnect_timer()

        if self._destroy_client:
            self._client.destroy()
            self._client = None
            self._destroy_client = False
            self._create_client()

        self.notify('state-changed', SimpleClientState.DISCONNECTED)

    def _disable_reconnect_timer(self) -> None:
        if self._reconnect_timer_source is not None:
            GLib.source_remove(self._reconnect_timer_source)
            self._reconnect_timer_source = None

    def _idle_state_changed(self, monitor: IdleMonitorManager) -> None:
        state = monitor.state.value

        if monitor.is_awake():
            self._idle_status = state
            self._idle_status_message = ''
            self._update_status()
            return

        if not app.settings.get(f'auto{state}'):
            return

        if (state in ('away', 'xa') and self._status == 'online' or
                state == 'xa' and self._idle_status == 'away'):

            self._idle_status = state
            self._idle_status_message = get_idle_status_message(
                state, self._status_message)
            self._update_status()

    def _update_status(self) -> None:
        if not self._idle_status_enabled:
            return

        self._status = self._idle_status
        if self._state.is_available:
            self.update_presence()
        else:
            self._status_sync_on_resume = True

    def _idle_status_active(self) -> bool:
        if not Monitor.is_available():
            return False

        if not self._idle_status_enabled:
            return False

        return self._idle_status != 'online'

    def get_presence_state(self) -> tuple[str, str, bool]:
        if self._idle_status_active():
            return self._idle_status, self._idle_status_message, True
        return self._status, self._status_message, False

    @staticmethod
    def _screensaver_state_changed(application: Gtk.Application,
                                   _param: GObject.ParamSpec) -> None:
        active = application.get_property('screensaver-active')
        Monitor.set_extended_away(active)

    def cleanup(self) -> None:
        self.disconnect_signals()
        self._destroyed = True
        if Monitor.is_available():
            Monitor.disconnect(self._idle_handler_id)
            app.app.disconnect(self._screensaver_handler_id)
        if self._client is not None:
            self._client.destroy()
        modules.unregister_modules(self)

    def quit(self, kill_core: bool) -> None:
        if kill_core and self._state in (ClientState.CONNECTING,
                                         ClientState.CONNECTED,
                                         ClientState.AVAILABLE):
            self.disconnect(gracefully=True, reconnect=False)
