# Contributors for this file:
#      - Yann Leboulanger <asterix@lagaule.org>
#      - Nikos Kouremenos <nkour@jabber.org>
#      - Dimitur Kirov <dkirov@gmail.com>
#      - Travis Shirk <travis@pobox.com>
# - Stefan Bethge <stefan@lanpartei.de>
#
# Copyright (C) 2003-2014 Yann Leboulanger <asterix@lagaule.org>
# Copyright (C) 2003-2004 Vincent Hanquez <tab@snarc.org>
# Copyright (C) 2006 Nikos Kouremenos <nkour@jabber.org>
#                    Dimitur Kirov <dkirov@gmail.com>
#                    Travis Shirk <travis@pobox.com>
#                    Norman Rasmussen <norman@rasmussen.co.za>
#                    Stefan Bethge <stefan@lanpartei.de>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

import socket
import getpass
import logging
import time

import nbxmpp
from gi.repository import GLib

from gajim.common import app
from gajim.common import modules
from gajim.common.nec import NetworkEvent
from gajim.common.i18n import _
from gajim.common.const import ClientState
from gajim.common.connection import CommonConnection
from gajim.common.zeroconf import client_zeroconf
from gajim.common.zeroconf import zeroconf
from gajim.common.zeroconf.connection_handlers_zeroconf import ConnectionHandlersZeroconf
from gajim.common.connection_handlers_events import OurShowEvent
from gajim.common.connection_handlers_events import InformationEvent
from gajim.common.connection_handlers_events import ConnectionLostEvent
from gajim.common.connection_handlers_events import MessageSentEvent

log = logging.getLogger('gajim.c.connection_zeroconf')


class ConnectionZeroconf(CommonConnection, ConnectionHandlersZeroconf):
    def __init__(self, name):
        ConnectionHandlersZeroconf.__init__(self)
        # system username
        self.username = None
        self.server_resource = '' # zeroconf has no resource, fake an empty one
        self.call_resolve_timeout = False
        # we don't need a password, but must be non-empty
        self.password = 'zeroconf'
        self.autoconnect = False
        self.httpupload = False

        CommonConnection.__init__(self, name)
        self.is_zeroconf = True

        # Register all modules
        modules.register_modules(self)

    def get_config_values_or_default(self):
        """
        Get name, host, port from config, or create zeroconf account with default
        values
        """
        self.host = socket.gethostname()
        app.settings.set_account_setting(app.ZEROCONF_ACC_NAME,
                                         'hostname',
                                         self.host)
        self.port = app.settings.get_account_setting(app.ZEROCONF_ACC_NAME,
                                                     'custom_port')
        self.autoconnect = app.settings.get_account_setting(
            app.ZEROCONF_ACC_NAME, 'autoconnect')
        self.sync_with_global_status = app.settings.get_account_setting(
            app.ZEROCONF_ACC_NAME, 'sync_with_global_status')
        self.first = app.settings.get_account_setting(app.ZEROCONF_ACC_NAME,
                                                      'zeroconf_first_name')
        self.last = app.settings.get_account_setting(app.ZEROCONF_ACC_NAME,
                                                     'zeroconf_last_name')
        self.jabber_id = app.settings.get_account_setting(app.ZEROCONF_ACC_NAME,
                                                          'zeroconf_jabber_id')
        self.email = app.settings.get_account_setting(app.ZEROCONF_ACC_NAME,
                                                      'zeroconf_email')

        if not self.username:
            self.username = getpass.getuser()
            app.settings.set_account_setting(app.ZEROCONF_ACC_NAME,
                                             'name',
                                             self.username)
        else:
            self.username = app.settings.get_account_setting(
                app.ZEROCONF_ACC_NAME, 'name')

    def get_own_jid(self, *args, **kwargs):
        return nbxmpp.JID.from_string(self.username + '@' + self.host)

    def reconnect(self):
        # Do not try to reco while we are already trying
        self.time_to_reconnect = None
        log.debug('reconnect')

        self.disconnect()
        self.change_status(self._status, self._status_message)

    def disable_account(self):
        self.disconnect()

    def _on_resolve_timeout(self):
        if self._state.is_connected:
            if not self.connection.resolve_all():
                self.disconnect()
                return False
            diffs = self.roster.getDiffs()
            for key in diffs:
                self.roster.setItem(key)
                app.nec.push_incoming_event(NetworkEvent(
                    'roster-info', conn=self, jid=key,
                    nickname=self.roster.getName(key), sub='both',
                    ask='no', groups=self.roster.getGroups(key),
                    avatar_sha=None))
                self._on_presence(key)
                #XXX open chat windows don't get refreshed (full name), add that
        return self.call_resolve_timeout

    # callbacks called from zeroconf
    def _on_new_service(self, jid):
        self.roster.setItem(jid)
        app.nec.push_incoming_event(NetworkEvent(
            'roster-info', conn=self, jid=jid,
            nickname=self.roster.getName(jid), sub='both',
            ask='no', groups=self.roster.getGroups(jid),
            avatar_sha=None))
        self._on_presence(jid)

    def _on_remove_service(self, jid):
        self.roster.delItem(jid)
        # 'NOTIFY' (account, (jid, status, status message, resource, priority,
        # timestamp))
        self._on_presence(jid, show='offline', status='')

    def _on_presence(self, jid, show=None, status=None):
        if status is None:
            status = self.roster.getMessage(jid)
        if show is None:
            show = self.roster.getStatus(jid)

        ptype = 'unavailable' if show == 'offline' else None

        event_attrs = {
            'conn': self,
            'prio': 0,
            'need_add_in_roster': False,
            'popup': False,
            'ptype': ptype,
            'jid': jid,
            'resource': 'local',
            'id_': None,
            'fjid': jid,
            'timestamp': 0,
            'avatar_sha': None,
            'user_nick': '',
            'idle_time': None,
            'show': show,
            'new_show': show,
            'old_show': 0,
            'status': status,
            'contact_list': [],
            'contact': None,
        }

        event_ = NetworkEvent('presence-received', **event_attrs)

        self._update_contact(event_)

        app.nec.push_incoming_event(event_)

    def _update_contact(self, event):
        jid = event.jid

        status_strings = ['offline', 'error', 'online', 'chat', 'away',
                          'xa', 'dnd']

        event.new_show = status_strings.index(event.show)

        contact = app.contacts.get_contact_strict(self.name, jid, '')
        if contact is None:
            contact = app.contacts.get_contact_strict(self.name, jid, 'local')

        if contact.show in status_strings:
            event.old_show = status_strings.index(contact.show)

        # Update contact with presence data
        contact.resource = 'local'
        contact.show = event.show
        contact.status = event.status
        contact.priority = event.prio
        contact.idle_time = event.idle_time

        event.contact = contact

        # It's not an agent
        if event.old_show == 0 and event.new_show > 1:
            if not jid in app.newly_added[self.name]:
                app.newly_added[self.name].append(jid)
            if jid in app.to_be_removed[self.name]:
                app.to_be_removed[self.name].remove(jid)
        elif event.old_show > 1 and event.new_show == 0 and self._state.is_connected:
            if not jid in app.to_be_removed[self.name]:
                app.to_be_removed[self.name].append(jid)
            if jid in app.newly_added[self.name]:
                app.newly_added[self.name].remove(jid)

        if event.ptype == 'unavailable':
            # TODO: This causes problems when another
            # resource signs off!
            self.get_module('Bytestream').stop_all_active_file_transfers(contact)

    def _on_name_conflictCB(self, alt_name):
        self.disconnect()
        app.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='offline'))
        app.nec.push_incoming_event(
            NetworkEvent('zeroconf-name-conflict',
                         conn=self,
                         alt_name=alt_name))

    def _on_error(self, message):
        app.nec.push_incoming_event(InformationEvent(
            None, dialog_name='avahi-error', args=message))

    def connect(self, show='online', msg=''):
        self.get_config_values_or_default()
        if not self.connection:
            self.connection = client_zeroconf.ClientZeroconf(self)
            if not zeroconf.test_zeroconf():
                app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='offline'))
                self._status = 'offline'
                app.nec.push_incoming_event(ConnectionLostEvent(None,
                    conn=self, title=_('Could not connect to "%s"') % self.name,
                    msg=_('Please check if Avahi or Bonjour is installed.')))
                self.disconnect()
                return
            result = self.connection.connect(show, msg)
            if not result:
                app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='offline'))
                self._status = 'offline'
                if result is False:
                    app.nec.push_incoming_event(ConnectionLostEvent(None,
                        conn=self, title=_('Could not start local service'),
                        msg=_('Unable to bind to port %d.') % self.port))
                else: # result is None
                    app.nec.push_incoming_event(ConnectionLostEvent(None,
                        conn=self, title=_('Could not start local service'),
                        msg=_('Please check if avahi/bonjour-daemon is running.')))
                self.disconnect()
                return
        else:
            self.connection.announce()
        self.roster = self.connection.getRoster()
        app.nec.push_incoming_event(NetworkEvent('roster-received', conn=self,
            roster=self.roster.copy(), received_from_server=True))

        # display contacts already detected and resolved
        for jid in self.roster.keys():
            app.nec.push_incoming_event(NetworkEvent(
                'roster-info', conn=self, jid=jid,
                nickname=self.roster.getName(jid), sub='both',
                ask='no', groups=self.roster.getGroups(jid),
                avatar_sha=None))
            self._on_presence(jid)

        self._status = show

        # refresh all contacts data every five seconds
        self.call_resolve_timeout = True
        GLib.timeout_add_seconds(5, self._on_resolve_timeout)
        return True

    def disconnect(self, reconnect=True, immediately=True):
        log.info('Start disconnecting zeroconf')
        if reconnect:
            self.time_to_reconnect = 5
        else:
            self.time_to_reconnect = None

        self._set_state(ClientState.DISCONNECTED)
        if self.connection:
            self.connection.disconnect()
            self.connection = None
            # stop calling the timeout
            self.call_resolve_timeout = False
        app.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='offline'))

    def _on_disconnect(self):
        self._set_state(ClientState.DISCONNECTED)
        app.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='offline'))

    def reannounce(self):
        if self._state.is_connected:
            txt = {}
            txt['1st'] = app.settings.get_account_setting(
                app.ZEROCONF_ACC_NAME, 'zeroconf_first_name')
            txt['last'] = app.settings.get_account_setting(
                app.ZEROCONF_ACC_NAME, 'zeroconf_last_name')
            txt['jid'] = app.settings.get_account_setting(
                app.ZEROCONF_ACC_NAME, 'zeroconf_jabber_id')
            txt['email'] = app.settings.get_account_setting(
                app.ZEROCONF_ACC_NAME, 'zeroconf_email')
            self.connection.reannounce(txt)

    def update_details(self):
        if self.connection:
            port = app.settings.get_account_setting(app.ZEROCONF_ACC_NAME,
                                                    'custom_port')
            if port != self.port:
                self.port = port
                last_msg = self.connection.last_msg
                self.disconnect()
                if not self.connect(self._status, last_msg):
                    return
                self.connection.announce()
            else:
                self.reannounce()

    def connect_and_init(self, show, msg):
        # to check for errors from zeroconf
        check = True
        if not self.connect(show, msg):
            return

        check = self.connection.announce()

        # stay offline when zeroconf does something wrong
        if check:
            self._set_state(ClientState.CONNECTED)
            app.nec.push_incoming_event(NetworkEvent('signed-in', conn=self))
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show=show))
        else:
            # show notification that avahi or system bus is down
            self._set_state(ClientState.DISCONNECTED)
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            self._status = 'offline'
            app.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not change status of account "%s"') % self.name,
                msg=_('Please check if avahi-daemon is running.')))

    def _update_status(self, show, msg, idle_time=None):
        if self.connection.set_show_msg(show, msg):
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show=show))
        else:
            # show notification that avahi or system bus is down
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            self._status = 'offline'
            app.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not change status of account "%s"') % self.name,
                msg=_('Please check if avahi-daemon is running.')))

    def send_message(self, message):
        stanza = self.get_module('Message').build_message_stanza(message)
        message.stanza = stanza

        if message.contact is None:
            # Only Single Message should have no contact
            self._send_message(message)
            return

        method = message.contact.settings.get('encryption')
        if not method:
            self._send_message(message)
            return

        app.plugin_manager.extension_point('encrypt%s' % method,
                                           self,
                                           message,
                                           self._send_message)

    def _send_message(self, message):
        def on_send_ok(stanza_id):
            app.nec.push_incoming_event(
                MessageSentEvent(None, jid=message.jid, **vars(message)))
            self.get_module('Message').log_message(message)

        def on_send_not_ok(reason):
            reason += ' ' + _('Your message could not be sent.')
            app.nec.push_incoming_event(NetworkEvent(
                'zeroconf-error',
                account=self.name,
                jid=message.jid,
                message=reason))

        ret = self.connection.send(
            message.stanza, message.message is not None,
            on_ok=on_send_ok, on_not_ok=on_send_not_ok)
        message.timestamp = time.time()

        if ret == -1:
            # Contact Offline
            error_message = _(
                'Contact is offline. Your message could not be sent.')
            app.nec.push_incoming_event(NetworkEvent(
                'zeroconf-error',
                account=self.name,
                jid=message.jid,
                message=error_message))
            return

    def send_stanza(self, stanza):
        # send a stanza untouched
        if not self.connection:
            return
        if not isinstance(stanza, nbxmpp.Node):
            stanza = nbxmpp.Protocol(node=stanza)
        self.connection.send(stanza)

    def _event_dispatcher(self, realm, event, data):
        CommonConnection._event_dispatcher(self, realm, event, data)
        if realm == '':
            if event == nbxmpp.transports.DATA_ERROR:
                frm = data[0]
                error_message = _(
                    'Connection to host could not be established: '
                    'Timeout while sending data.')
                app.nec.push_incoming_event(NetworkEvent(
                    'zeroconf-error',
                    account=self.name,
                    jid=frm,
                    message=error_message))

    def cleanup(self):
        pass
