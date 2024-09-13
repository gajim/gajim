# Copyright (C) 2014 Kamil Paral <kamil.paral AT gmail.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

'''
Watch for system shutdown using systemd-logind.
Documentation: https://www.freedesktop.org/wiki/Software/systemd/inhibit
'''
from __future__ import annotations

from typing import Any

import logging
import os

from gi.repository import Gio
from gi.repository import GLib

from gajim.common import app
from gajim.common.i18n import _

log = logging.getLogger('gajim.c.dbus.logind')


class LogindListener:
    _instance: LogindListener | None = None

    @classmethod
    def get(cls) -> LogindListener:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        # file descriptor object of the inhibitor
        self._inhibit_fd: int | None = None

        Gio.bus_watch_name(
            Gio.BusType.SYSTEM,
            'org.freedesktop.login1',
            Gio.BusNameWatcherFlags.NONE,
            self._on_logind_appeared,
            self._on_logind_vanished)

    def _on_prepare_for_shutdown(self,
                                 _connection: Gio.DBusConnection,
                                 _sender_name: str,
                                 _object_path: str,
                                 interface_name: str,
                                 signal_name: str,
                                 parameters: tuple[str, str, str],
                                 *_user_data: Any
                                 ) -> None:
        '''Signal handler for PrepareForShutdown event'''
        log.debug('Received signal %s.%s%s',
                  interface_name, signal_name, parameters)

        if self._inhibit_fd is None:
            log.warning('Preparing for shutdown by quitting Gajim, '
                        'without holding a shutdown inhibitor')
        else:
            log.info('Preparing for shutdown by quitting Gajim')

        app.window.quit()

    def _obtain_delay_inhibitor(self, connection: Gio.DBusConnection) -> None:
        '''Obtain a shutdown delay inhibitor from logind'''
        if self._inhibit_fd is not None:
            # Something is wrong, we have an inhibitor fd, and we are asking for
            # yet another one.
            log.warning('Trying to obtain a shutdown inhibitor '
                        'while already holding one.')
            return

        try:
            result = connection.call_with_unix_fd_list_sync(
                'org.freedesktop.login1',
                '/org/freedesktop/login1',
                'org.freedesktop.login1.Manager',
                'Inhibit',
                GLib.Variant('(ssss)', (
                    'shutdown',
                    app.get_default_app_id(),
                    _('Shutting down Gajim'),
                    'delay'  # Inhibitor will delay but not block shutdown
                )),
                GLib.VariantType.new('(h)'),
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                None)
        except GLib.Error as error:
            log.warning(
                'Could not obtain a shutdown delay inhibitor from '
                'logind: %s', error)
            return

        ret, ret_fdlist = result
        if ret_fdlist is None:  # pyright: ignore
            # This can happen as reported by users
            log.warning('Unable to obtain inhibitor, fdlist is None')
            return

        self._inhibit_fd = ret_fdlist.get(ret.unpack()[0])
        log.info('Obtained shutdown delay inhibitor')

    def release_delay_inhibitor(self) -> None:
        '''Release our shutdown delay inhibitor'''
        if self._inhibit_fd is not None:
            os.close(self._inhibit_fd)
            self._inhibit_fd = None
        log.info('Released shutdown delay inhibitor')

    def _on_logind_appeared(self,
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
            'PrepareForShutdown',
            '/org/freedesktop/login1',
            None,
            Gio.DBusSignalFlags.NONE,
            self._on_prepare_for_shutdown,
            None)
        self._obtain_delay_inhibitor(connection)

    def _on_logind_vanished(self,
                            _connection: Gio.DBusConnection,
                            name: str,
                            *_user_data: Any
                            ) -> None:
        '''Release remaining resources related to org.freedesktop.login1'''
        log.info('Name %s vanished', name)
        self.release_delay_inhibitor()


def enable() -> None:
    LogindListener.get()


def shutdown() -> None:
    LogindListener.get().release_delay_inhibitor()
