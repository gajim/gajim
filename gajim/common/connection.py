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

import time
import logging

from gajim.common import helpers
from gajim.common import app
from gajim.common import idle
from gajim.common import modules
from gajim.common.nec import NetworkEvent
from gajim.common.const import ClientState


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
        self.connection = None # xmpppy ClientCommon instance
        self.is_zeroconf = False
        self.password = None
        self.server_resource = helpers.get_resource(self.name)
        self.priority = app.get_priority(name, 'offline')
        self.time_to_reconnect = None
        self._reconnect_timer_source = None

        self._state = ClientState.DISCONNECTED
        self._status = 'offline'
        self._status_message = ''

        # If handlers have been registered
        self.handlers_registered = False

        self.pep = {}

        self.roster_supported = True

        self._stun_servers = [] # STUN servers of our jabber server

        # Tracks the calls of the connect_machine() method
        self._connect_machine_calls = 0

        self.get_config_values_or_default()

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

    def _register_new_handlers(self, con):
        for handler in modules.get_handlers(self):
            if len(handler) == 5:
                name, func, typ, ns, priority = handler
                con.RegisterHandler(name, func, typ, ns, priority=priority)
            else:
                con.RegisterHandler(*handler)
        self.handlers_registered = True

    def _unregister_new_handlers(self, con):
        if not con:
            return
        for handler in modules.get_handlers(self):
            if len(handler) > 4:
                handler = handler[:4]
            con.UnregisterHandler(*handler)
        self.handlers_registered = False

    def get_module(self, name):
        return modules.get(self.name, name)

    def reconnect(self):
        """
        To be implemented by derived classes
        """
        raise NotImplementedError

    def quit(self, kill_core):
        if kill_core and app.account_is_connected(self.name):
            self.disconnect(reconnect=False)

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

    def _event_dispatcher(self, realm, event, data):
        if realm == '':
            if event == 'STANZA RECEIVED':
                app.nec.push_incoming_event(
                    NetworkEvent('stanza-received',
                                 conn=self,
                                 stanza_str=str(data)))
            elif event == 'DATA SENT':
                app.nec.push_incoming_event(
                    NetworkEvent('stanza-sent',
                                 conn=self,
                                 stanza_str=str(data)))

    def change_status(self, show, msg, auto=False):
        if not msg:
            msg = ''

        self._status = show
        self._status_message = msg

        if self._state.is_disconnected:
            if show == 'offline':
                return

            self.server_resource = helpers.get_resource(self.name)
            self.connect_and_init(show, msg)
            return

        if self._state.is_connecting or self._state.is_reconnect_scheduled:
            if show == 'offline':
                self.disconnect(reconnect=False)
            elif self._state.is_reconnect_scheduled:
                self.reconnect()
            return

        # We are connected
        if show == 'offline':
            presence = self.get_module('Presence').get_presence(
                typ='unavailable',
                status=msg,
                caps=False)

            self.connection.send(presence, now=True)
            self.disconnect(reconnect=False)
            return

        idle_time = None
        if auto:
            if app.is_installed('IDLE') and app.settings.get('autoaway'):
                idle_sec = idle.Monitor.get_idle_sec()
                idle_time = time.strftime(
                    '%Y-%m-%dT%H:%M:%SZ',
                    time.gmtime(time.time() - idle_sec))

        self._update_status(show, msg, idle_time=idle_time)
