##      common/zeroconf/connection_zeroconf.py
##
## Contributors for this file:
##      - Yann Leboulanger <asterix@lagaule.org>
##      - Nikos Kouremenos <nkour@jabber.org>
##      - Dimitur Kirov <dkirov@gmail.com>
##      - Travis Shirk <travis@pobox.com>
## - Stefan Bethge <stefan@lanpartei.de>
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix@lagaule.org>
## Copyright (C) 2003-2004 Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2006 Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
##                    Stefan Bethge <stefan@lanpartei.de>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##


import os
import socket
import random
random.seed()

import signal
if os.name != 'nt':
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import getpass
from gi.repository import GLib

from gajim.common.connection import CommonConnection
from gajim.common import app
from gajim.common import ged
from gajim.common.zeroconf import client_zeroconf
from gajim.common.zeroconf import zeroconf
from gajim.common.zeroconf.connection_handlers_zeroconf import *
from gajim.common.connection_handlers_events import *

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

        CommonConnection.__init__(self, name)
        self.is_zeroconf = True

        app.ged.register_event_handler('stanza-message-outgoing', ged.OUT_CORE,
            self._nec_stanza_message_outgoing)

    def get_config_values_or_default(self):
        """
        Get name, host, port from config, or create zeroconf account with default
        values
        """
        if not app.config.get_per('accounts', app.ZEROCONF_ACC_NAME, 'name'):
            log.debug('Creating zeroconf account')
            app.config.add_per('accounts', app.ZEROCONF_ACC_NAME)
            app.config.set_per('accounts', app.ZEROCONF_ACC_NAME,
                    'autoconnect', True)
            app.config.set_per('accounts', app.ZEROCONF_ACC_NAME, 'no_log_for',
                    '')
            app.config.set_per('accounts', app.ZEROCONF_ACC_NAME, 'password',
                    'zeroconf')
            app.config.set_per('accounts', app.ZEROCONF_ACC_NAME,
                    'sync_with_global_status', True)

            app.config.set_per('accounts', app.ZEROCONF_ACC_NAME,
                    'custom_port', 5298)
            app.config.set_per('accounts', app.ZEROCONF_ACC_NAME,
                    'is_zeroconf', True)
            app.config.set_per('accounts', app.ZEROCONF_ACC_NAME,
                    'use_ft_proxies', False)
        self.host = socket.gethostname()
        app.config.set_per('accounts', app.ZEROCONF_ACC_NAME, 'hostname',
                self.host)
        self.port = app.config.get_per('accounts', app.ZEROCONF_ACC_NAME,
                'custom_port')
        self.autoconnect = app.config.get_per('accounts',
                app.ZEROCONF_ACC_NAME, 'autoconnect')
        self.sync_with_global_status = app.config.get_per('accounts',
                app.ZEROCONF_ACC_NAME, 'sync_with_global_status')
        self.first = app.config.get_per('accounts', app.ZEROCONF_ACC_NAME,
                'zeroconf_first_name')
        self.last = app.config.get_per('accounts', app.ZEROCONF_ACC_NAME,
                'zeroconf_last_name')
        self.jabber_id = app.config.get_per('accounts', app.ZEROCONF_ACC_NAME,
                'zeroconf_jabber_id')
        self.email = app.config.get_per('accounts', app.ZEROCONF_ACC_NAME,
                'zeroconf_email')

        if not self.username:
            self.username = getpass.getuser()
            app.config.set_per('accounts', app.ZEROCONF_ACC_NAME, 'name',
                self.username)
        else:
            self.username = app.config.get_per('accounts',
                app.ZEROCONF_ACC_NAME, 'name')
    # END __init__

    def check_jid(self, jid):
        return jid

    def reconnect(self):
        # Do not try to reco while we are already trying
        self.time_to_reconnect = None
        log.debug('reconnect')

        self.disconnect()
        self.change_status(self.old_show, self.status)

    def disable_account(self):
        self.disconnect()

    def _on_resolve_timeout(self):
        if self.connected:
            self.connection.resolve_all()
            diffs = self.roster.getDiffs()
            for key in diffs:
                self.roster.setItem(key)
                app.nec.push_incoming_event(RosterInfoEvent(None, conn=self,
                    jid=key, nickname=self.roster.getName(key), sub='both',
                    ask='no', groups=self.roster.getGroups(key)))
                app.nec.push_incoming_event(ZeroconfPresenceReceivedEvent(
                    None, conn=self, fjid=key, show=self.roster.getStatus(key),
                    status=self.roster.getMessage(key)))
                #XXX open chat windows don't get refreshed (full name), add that
        return self.call_resolve_timeout

    # callbacks called from zeroconf
    def _on_new_service(self, jid):
        self.roster.setItem(jid)
        app.nec.push_incoming_event(RosterInfoEvent(None, conn=self,
            jid=jid, nickname=self.roster.getName(jid), sub='both',
            ask='no', groups=self.roster.getGroups(jid)))
        app.nec.push_incoming_event(ZeroconfPresenceReceivedEvent(
            None, conn=self, fjid=jid, show=self.roster.getStatus(jid),
            status=self.roster.getMessage(jid)))

    def _on_remove_service(self, jid):
        self.roster.delItem(jid)
        # 'NOTIFY' (account, (jid, status, status message, resource, priority,
        # keyID, timestamp, contact_nickname))
        app.nec.push_incoming_event(ZeroconfPresenceReceivedEvent(
            None, conn=self, fjid=jid, show='offline', status=''))

    def disconnectedReconnCB(self):
        """
        Called when we are disconnected. Comes from network manager for example
        we don't try to reconnect, network manager will tell us when we can
        """
        if app.account_is_connected(self.name):
            # we cannot change our status to offline or connecting
            # after we auth to server
            self.old_show = STATUS_LIST[self.connected]
        self.connected = 0
        app.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='offline'))
        # random number to show we wait network manager to send us a reconenct
        self.time_to_reconnect = 5
        self.on_purpose = False

    def _on_name_conflictCB(self, alt_name):
        self.disconnect()
        app.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='offline'))
        app.nec.push_incoming_event(ZeroconfNameConflictEvent(None, conn=self,
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
                self.status = 'offline'
                app.nec.push_incoming_event(ConnectionLostEvent(None,
                    conn=self, title=_('Could not connect to "%s"') % self.name,
                    msg=_('Please check if Avahi or Bonjour is installed.')))
                self.disconnect()
                return
            result = self.connection.connect(show, msg)
            if not result:
                app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='offline'))
                self.status = 'offline'
                if result is False:
                    app.nec.push_incoming_event(ConnectionLostEvent(None,
                        conn=self, title=_('Could not start local service'),
                        msg=_('Unable to bind to port %d.' % self.port)))
                else: # result is None
                    app.nec.push_incoming_event(ConnectionLostEvent(None,
                        conn=self, title=_('Could not start local service'),
                        msg=_('Please check if avahi-daemon is running.')))
                self.disconnect()
                return
        else:
            self.connection.announce()
        self.roster = self.connection.getRoster()
        app.nec.push_incoming_event(RosterReceivedEvent(None, conn=self,
            xmpp_roster=self.roster))

        # display contacts already detected and resolved
        for jid in self.roster.keys():
            app.nec.push_incoming_event(RosterInfoEvent(None, conn=self,
                jid=jid, nickname=self.roster.getName(jid), sub='both',
                ask='no', groups=self.roster.getGroups(jid)))
            app.nec.push_incoming_event(ZeroconfPresenceReceivedEvent(
                None, conn=self, fjid=jid, show=self.roster.getStatus(jid),
                status=self.roster.getMessage(jid)))

        self.connected = STATUS_LIST.index(show)

        # refresh all contacts data every five seconds
        self.call_resolve_timeout = True
        GLib.timeout_add_seconds(5, self._on_resolve_timeout)
        return True

    def disconnect(self, on_purpose=False):
        self.connected = 0
        self.time_to_reconnect = None
        if self.connection:
            self.connection.disconnect()
            self.connection = None
            # stop calling the timeout
            self.call_resolve_timeout = False

    def reannounce(self):
        if self.connected:
            txt = {}
            txt['1st'] = app.config.get_per('accounts', app.ZEROCONF_ACC_NAME,
                    'zeroconf_first_name')
            txt['last'] = app.config.get_per('accounts', app.ZEROCONF_ACC_NAME,
                    'zeroconf_last_name')
            txt['jid'] = app.config.get_per('accounts', app.ZEROCONF_ACC_NAME,
                    'zeroconf_jabber_id')
            txt['email'] = app.config.get_per('accounts',
                    app.ZEROCONF_ACC_NAME, 'zeroconf_email')
            self.connection.reannounce(txt)

    def update_details(self):
        if self.connection:
            port = app.config.get_per('accounts', app.ZEROCONF_ACC_NAME,
                    'custom_port')
            if port != self.port:
                self.port = port
                last_msg = self.connection.last_msg
                self.disconnect()
                if not self.connect(self.status, last_msg):
                    return
                if self.status != 'invisible':
                    self.connection.announce()
            else:
                self.reannounce()

    def connect_and_init(self, show, msg, sign_msg):
        # to check for errors from zeroconf
        check = True
        if not self.connect(show, msg):
            return
        if show != 'invisible':
            check = self.connection.announce()
        else:
            self.connected = STATUS_LIST.index(show)
        app.nec.push_incoming_event(SignedInEvent(None, conn=self))

        # stay offline when zeroconf does something wrong
        if check:
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show=show))
        else:
            # show notification that avahi or system bus is down
            self.connected = 0
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            self.status = 'offline'
            app.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not change status of account "%s"') % self.name,
                msg=_('Please check if avahi-daemon is running.')))

    def _change_to_invisible(self, msg):
        if self.connection.remove_announce():
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='invisible'))
        else:
            # show notification that avahi or system bus is down
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            self.status = 'offline'
            app.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not change status of account "%s"') % self.name,
                msg=_('Please check if avahi-daemon is running.')))

    def _change_from_invisible(self):
        self.connection.announce()

    def _update_status(self, show, msg):
        if self.connection.set_show_msg(show, msg):
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show=show))
        else:
            # show notification that avahi or system bus is down
            app.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            self.status = 'offline'
            app.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not change status of account "%s"') % self.name,
                msg=_('Please check if avahi-daemon is running.')))

    def _nec_stanza_message_outgoing(self, obj):
        if obj.conn.name != self.name:
            return

        def on_send_ok(stanza_id):
            app.nec.push_incoming_event(MessageSentEvent(None, conn=self,
                jid=obj.jid, message=obj.message, keyID=obj.keyID,
                automatic_message=obj.automatic_message, chatstate=None,
                stanza_id=stanza_id))

            self.log_message(obj, obj.jid)

        def on_send_not_ok(reason):
            reason += ' ' + _('Your message could not be sent.')
            app.nec.push_incoming_event(MessageErrorEvent(None, conn=self,
                fjid=obj.jid, error_code=-1, error_msg=reason, msg=None,
                time_=None, session=obj.session))
            # Dont propagate event
            return True

        ret = self.connection.send(
            obj.msg_iq, obj.message is not None,
            on_ok=on_send_ok, on_not_ok=on_send_not_ok)

        if ret == -1:
            # Contact Offline
            app.nec.push_incoming_event(MessageErrorEvent(None, conn=self,
                fjid=obj.jid, error_code=-1, error_msg=_(
                'Contact is offline. Your message could not be sent.'),
                msg=None, time_=None, session=obj.session))
            # Dont propagate event
            return True

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
            if event == nbxmpp.transports_nb.DATA_ERROR:
                thread_id = data[1]
                frm = data[0]
                session = self.get_or_create_session(frm, thread_id)
                app.nec.push_incoming_event(MessageErrorEvent(
                    None, conn=self, fjid=frm, error_code=-1, error_msg=_(
                    'Connection to host could not be established: Timeout while '
                    'sending data.'), msg=None, time_=None, session=session))

# END ConnectionZeroconf
