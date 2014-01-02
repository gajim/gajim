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
import random
random.seed()

import signal
if os.name != 'nt':
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
import getpass
from gi.repository import GLib

from common.connection import CommonConnection
from common import gajim
from common import ged
from common.zeroconf import client_zeroconf
from common.zeroconf import zeroconf
from common.zeroconf.connection_handlers_zeroconf import *
from common.connection_handlers_events import *

import locale

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

        gajim.ged.register_event_handler('message-outgoing', ged.OUT_CORE,
            self._nec_message_outgoing)

    def get_config_values_or_default(self):
        """
        Get name, host, port from config, or create zeroconf account with default
        values
        """
        if not gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME, 'name'):
            gajim.log.debug('Creating zeroconf account')
            gajim.config.add_per('accounts', gajim.ZEROCONF_ACC_NAME)
            gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
                    'autoconnect', True)
            gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'no_log_for',
                    '')
            gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'password',
                    'zeroconf')
            gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
                    'sync_with_global_status', True)

            gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
                    'custom_port', 5298)
            gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
                    'is_zeroconf', True)
            gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME,
                    'use_ft_proxies', False)
        self.host = socket.gethostname()
        gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'hostname',
                self.host)
        self.port = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
                'custom_port')
        self.autoconnect = gajim.config.get_per('accounts',
                gajim.ZEROCONF_ACC_NAME, 'autoconnect')
        self.sync_with_global_status = gajim.config.get_per('accounts',
                gajim.ZEROCONF_ACC_NAME, 'sync_with_global_status')
        self.first = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
                'zeroconf_first_name')
        self.last = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
                'zeroconf_last_name')
        self.jabber_id = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
                'zeroconf_jabber_id')
        self.email = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
                'zeroconf_email')

        if not self.username:
            self.username = getpass.getuser()
            gajim.config.set_per('accounts', gajim.ZEROCONF_ACC_NAME, 'name',
                self.username)
        else:
            self.username = gajim.config.get_per('accounts',
                gajim.ZEROCONF_ACC_NAME, 'name')
    # END __init__

    def check_jid(self, jid):
        return jid

    def _reconnect(self):
        # Do not try to reco while we are already trying
        self.time_to_reconnect = None
        gajim.log.debug('reconnect')

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
                gajim.nec.push_incoming_event(RosterInfoEvent(None, conn=self,
                    jid=key, nickname=self.roster.getName(key), sub='both',
                    ask='no', groups=self.roster.getGroups(key)))
                gajim.nec.push_incoming_event(ZeroconfPresenceReceivedEvent(
                    None, conn=self, fjid=key, show=self.roster.getStatus(key),
                    status=self.roster.getMessage(key)))
                #XXX open chat windows don't get refreshed (full name), add that
        return self.call_resolve_timeout

    # callbacks called from zeroconf
    def _on_new_service(self, jid):
        self.roster.setItem(jid)
        gajim.nec.push_incoming_event(RosterInfoEvent(None, conn=self,
            jid=jid, nickname=self.roster.getName(jid), sub='both',
            ask='no', groups=self.roster.getGroups(jid)))
        gajim.nec.push_incoming_event(ZeroconfPresenceReceivedEvent(
            None, conn=self, fjid=jid, show=self.roster.getStatus(jid),
            status=self.roster.getMessage(jid)))

    def _on_remove_service(self, jid):
        self.roster.delItem(jid)
        # 'NOTIFY' (account, (jid, status, status message, resource, priority,
        # keyID, timestamp, contact_nickname))
        gajim.nec.push_incoming_event(ZeroconfPresenceReceivedEvent(
            None, conn=self, fjid=jid, show='offline', status=''))

    def _disconnectedReconnCB(self):
        """
        Called when we are disconnected. Comes from network manager for example
        we don't try to reconnect, network manager will tell us when we can
        """
        if gajim.account_is_connected(self.name):
            # we cannot change our status to offline or connecting
            # after we auth to server
            self.old_show = STATUS_LIST[self.connected]
        self.connected = 0
        gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='offline'))
        # random number to show we wait network manager to send us a reconenct
        self.time_to_reconnect = 5
        self.on_purpose = False

    def _on_name_conflictCB(self, alt_name):
        self.disconnect()
        gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
            show='offline'))
        gajim.nec.push_incoming_event(ZeroconfNameConflictEvent(None, conn=self,
            alt_name=alt_name))

    def _on_error(self, message):
        gajim.nec.push_incoming_event(InformationEvent(None, conn=self,
            level='error', pri_txt=_('Avahi error'), sec_txt=_('%s\nLink-local '
            'messaging might not work properly.') % message))

    def connect(self, show='online', msg=''):
        self.get_config_values_or_default()
        if not self.connection:
            self.connection = client_zeroconf.ClientZeroconf(self)
            if not zeroconf.test_zeroconf():
                gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='offline'))
                self.status = 'offline'
                gajim.nec.push_incoming_event(ConnectionLostEvent(None,
                    conn=self, title=_('Could not connect to "%s"') % self.name,
                    msg=_('Please check if Avahi or Bonjour is installed.')))
                self.disconnect()
                return
            result = self.connection.connect(show, msg)
            if not result:
                gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                    show='offline'))
                self.status = 'offline'
                if result is False:
                    gajim.nec.push_incoming_event(ConnectionLostEvent(None,
                        conn=self, title=_('Could not start local service'),
                        msg=_('Unable to bind to port %d.' % self.port)))
                else: # result is None
                    gajim.nec.push_incoming_event(ConnectionLostEvent(None,
                        conn=self, title=_('Could not start local service'),
                        msg=_('Please check if avahi-daemon is running.')))
                self.disconnect()
                return
        else:
            self.connection.announce()
        self.roster = self.connection.getRoster()
        gajim.nec.push_incoming_event(RosterReceivedEvent(None, conn=self,
            xmpp_roster=self.roster))

        # display contacts already detected and resolved
        for jid in self.roster.keys():
            gajim.nec.push_incoming_event(RosterInfoEvent(None, conn=self,
                jid=jid, nickname=self.roster.getName(jid), sub='both',
                ask='no', groups=self.roster.getGroups(jid)))
            gajim.nec.push_incoming_event(ZeroconfPresenceReceivedEvent(
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
            txt['1st'] = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
                    'zeroconf_first_name')
            txt['last'] = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
                    'zeroconf_last_name')
            txt['jid'] = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
                    'zeroconf_jabber_id')
            txt['email'] = gajim.config.get_per('accounts',
                    gajim.ZEROCONF_ACC_NAME, 'zeroconf_email')
            self.connection.reannounce(txt)

    def update_details(self):
        if self.connection:
            port = gajim.config.get_per('accounts', gajim.ZEROCONF_ACC_NAME,
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
        gajim.nec.push_incoming_event(SignedInEvent(None, conn=self))

        # stay offline when zeroconf does something wrong
        if check:
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show=show))
        else:
            # show notification that avahi or system bus is down
            self.connected = 0
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            self.status = 'offline'
            gajim.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not change status of account "%s"') % self.name,
                msg=_('Please check if avahi-daemon is running.')))

    def _change_to_invisible(self, msg):
        if self.connection.remove_announce():
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='invisible'))
        else:
            # show notification that avahi or system bus is down
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            self.status = 'offline'
            gajim.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not change status of account "%s"') % self.name,
                msg=_('Please check if avahi-daemon is running.')))

    def _change_from_invisible(self):
        self.connection.announce()

    def _update_status(self, show, msg):
        if self.connection.set_show_msg(show, msg):
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show=show))
        else:
            # show notification that avahi or system bus is down
            gajim.nec.push_incoming_event(OurShowEvent(None, conn=self,
                show='offline'))
            self.status = 'offline'
            gajim.nec.push_incoming_event(ConnectionLostEvent(None, conn=self,
                title=_('Could not change status of account "%s"') % self.name,
                msg=_('Please check if avahi-daemon is running.')))

    def _nec_message_outgoing(self, obj):
        if obj.account != self.name:
            return

        def on_send_ok(msg_id):
            gajim.nec.push_incoming_event(MessageSentEvent(None, conn=self,
                jid=obj.jid, message=obj.message, keyID=obj.keyID,
                chatstate=None))
            if obj.callback:
                obj.callback(obj.msg_id, *obj.callback_args)

            if not obj.is_loggable:
                return
            self.log_message(obj.jid, obj.message, obj.forward_from,
                obj.session, obj.original_message, obj.subject, obj.type_)

        def on_send_not_ok(reason):
            reason += ' ' + _('Your message could not be sent.')
            gajim.nec.push_incoming_event(MessageErrorEvent(None, conn=self,
                fjid=obj.jid, error_code=-1, error_msg=reason, msg=None,
                time_=None, session=obj.session))

        def cb(jid, msg, keyID, forward_from, session, original_message, subject,
        type_, msg_iq, xhtml):
            ret = self.connection.send(msg_iq, msg is not None, on_ok=on_send_ok,
                    on_not_ok=on_send_not_ok)

            if ret == -1:
                # Contact Offline
                gajim.nec.push_incoming_event(MessageErrorEvent(None, conn=self,
                    fjid=jid, error_code=-1, error_msg=_(
                    'Contact is offline. Your message could not be sent.'),
                    msg=None, time_=None, session=session))

        self._prepare_message(obj.jid, obj.message, obj.keyID, type_=obj.type_,
            subject=obj.subject, chatstate=obj.chatstate, msg_id=obj.msg_id,
            resource=obj.resource, user_nick=obj.user_nick, xhtml=obj.xhtml,
            label=obj.label, session=obj.session, forward_from=obj.forward_from,
            form_node=obj.form_node, original_message=obj.original_message,
            delayed=obj.delayed, attention=obj.attention, callback=cb)

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
                gajim.nec.push_incoming_event(MessageErrorEvent(
                    None, conn=self, fjid=frm, error_code=-1, error_msg=_(
                    'Connection to host could not be established: Timeout while '
                    'sending data.'), msg=None, time_=None, session=session))

# END ConnectionZeroconf
