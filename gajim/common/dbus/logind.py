# Copyright (C) 2014 Kamil Paral <kamil.paral AT gmail.com>
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

'''
Watch for system sleep using systemd-logind.
Documentation: http://www.freedesktop.org/wiki/Software/systemd/inhibit
'''
from __future__ import annotations

from typing import Any
from typing import Optional

import os
import logging

from gi.repository import Gio
from gi.repository import GLib

from gajim.common import app
from gajim.common.i18n import _

log = logging.getLogger('gajim.c.dbus.logind')


class LogindListener:
    _instance: Optional[LogindListener] = None

    @classmethod
    def get(cls) -> LogindListener:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        # file descriptor object of the inhibitor
        self._inhibit_fd: Optional[int] = None

        Gio.bus_watch_name(
            Gio.BusType.SYSTEM,
            'org.freedesktop.login1',
            Gio.BusNameWatcherFlags.NONE,
            self._on_appear_logind,
            self._on_vanish_logind)

    def _on_prepare_for_sleep(self,
                              connection: Gio.DBusConnection,
                              _sender_name: str,
                              _object_path: str,
                              interface_name: str,
                              signal_name: str,
                              parameters: tuple[str, str, str],
                              *_user_data: Any
                              ) -> None:
        '''Signal handler for PrepareForSleep event'''
        log.debug('Received signal %s.%s%s',
                  interface_name, signal_name, parameters)

        before = parameters[0]  # Signal is either before or after sleep occurs
        if before:
            warn = self._inhibit_fd is None
            log.log(
                logging.WARNING if warn else logging.INFO,
                'Preparing for sleep by disconnecting from network%s',
                ', without holding a sleep inhibitor' if warn else '')

            for name, conn in app.connections.items():
                if app.account_is_connected(name):
                    st = conn.status_message
                    conn.change_status('offline',
                                       _('Machine is going to sleep'))
                    # TODO: Make this nicer
                    conn._status_message = st  # pylint: disable=protected-access
                    conn.time_to_reconnect = 5

            self._disinhibit_sleep()
        else:
            try:
                self._inhibit_sleep(connection)
            except GLib.Error as error:
                log.warning('Inhibit failed: %s', error)

            for conn in app.connections.values():
                if conn.state.is_disconnected and conn.time_to_reconnect:
                    conn.reconnect()

    def _inhibit_sleep(self, connection: Gio.DBusConnection) -> None:
        '''Obtain a sleep delay inhibitor from logind'''
        if self._inhibit_fd is not None:
            # Something is wrong, we have an inhibitor fd, and we are asking for
            # yet another one.
            log.warning('Trying to obtain a sleep inhibitor '
                        'while already holding one.')

        try:
            result = connection.call_with_unix_fd_list_sync(
                'org.freedesktop.login1',
                '/org/freedesktop/login1',
                'org.freedesktop.login1.Manager',
                'Inhibit',
                GLib.Variant('(ssss)', (
                    'sleep',
                    'org.gajim.Gajim',
                    _('Disconnect from the network'),
                    'delay'  # Inhibitor will delay but not block sleep
                    )),
                GLib.VariantType.new('(h)'),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                None)
            if result is None:
                log.warning(
                    'Cannot obtain a sleep delay inhibitor from logind')
                return
            ret, ret_fdlist = result
        except GLib.Error as error:
            log.warning(
                'Cannot obtain a sleep delay inhibitor from logind: %s', error)
            return

        log.info('Inhibit sleep')
        self._inhibit_fd = ret_fdlist.get(ret.unpack()[0])

    def _disinhibit_sleep(self) -> None:
        '''Relinquish our sleep delay inhibitor'''
        if self._inhibit_fd is not None:
            os.close(self._inhibit_fd)
            self._inhibit_fd = None
        log.info('Disinhibit sleep')

    def _on_appear_logind(self,
                          connection: Gio.DBusConnection,
                          name: str,
                          name_owner: str,
                          *_user_data: Any
                          ) -> None:
        '''Use signal and locks provided by org.freedesktop.login1'''
        log.info('Name %s appeared, owned by %s', name, name_owner)

        connection.signal_subscribe(
            'org.freedesktop.login1',
            'org.freedesktop.login1.Manager',
            'PrepareForSleep',
            '/org/freedesktop/login1',
            None,
            Gio.DBusSignalFlags.NONE,
            self._on_prepare_for_sleep,
            None)
        self._inhibit_sleep(connection)

    def _on_vanish_logind(self,
                          _connection: Gio.DBusConnection,
                          name: str,
                          *_user_data: Any
                          ) -> None:
        '''Release remaining resources related to org.freedesktop.login1'''
        log.info('Name %s vanished', name)
        self._disinhibit_sleep()


def enable() -> None:
    # Module should be rewritten
    # Its not useful to know when the computer goes to sleep.
    # Because of stream management we don’t need to do anything in that case.
    # It would be useful to know when the computer powers off, in this case
    # Gajim is shutdown and we should correctly disconnect.
    return
    # LogindListener.get()
