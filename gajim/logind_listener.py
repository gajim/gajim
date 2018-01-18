## src/logind_listener.py
##
## Copyright (C) 2014 Kamil Paral <kamil.paral AT gmail.com>
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

'''
Watch for system suspend using systemd-logind.
Documentation: http://www.freedesktop.org/wiki/Software/systemd/inhibit
'''

import os
import logging

from gi.repository import Gio, GLib

from gajim.common import app

log = logging.getLogger('gajim.logind_listener')

# file descriptor of the inhibitor; negative number means we don't
# hold any (yet)
fd = None


def signal_received(connection, sender_name, object_path,
                    interface_name, signal_name, parameters, *user_data):
    '''Signal handler for suspend event'''

    global fd

    connected = None
    log.info('Signal received: %s - %s', interface_name, parameters)

    # signal is sent right before (with the parameter True) and after
    # (with the parameter False) the system goes down for suspend/hibernate
    if not parameters[0]:
        return

    # we're going for suspend, let's disconnect
    log.debug('System suspend detected, disconnecting from network…')
    for name, conn in app.connections.items():
        if app.account_is_connected(name):
            conn.old_show = app.SHOW_LIST[conn.connected]
            st = conn.status
            conn.change_status('offline', _('Machine going to sleep'))
            conn.status = st
            conn.time_to_reconnect = 5

    # close the file descriptor and let the computer suspend
    if fd is not None:
        os.close(fd)
        fd = None
    else:
        # something is wrong, the system is suspending but we don't have
        # a lock file
        log.warning("System suspend detected, but we don't seem to be holding "
                    "a file descriptor for sleep inihibitor")


def get_inhibitor(connection):
    '''Ask for a suspend delay inhibitor'''

    global fd

    if fd is not None:
        # someting is wrong, we haven't closed the previous file descriptor
        # and we ask for yet another one
        log.warning('We are about to ask for a sleep inhibitor, but we seem '
                    'to be holding one already')

    ret = connection.call_with_unix_fd_list_sync(
        'org.freedesktop.login1',
        '/org/freedesktop/login1',
        'org.freedesktop.login1.Manager',
        'Inhibit',
        GLib.Variant('(ssss)', ('sleep', 'org.gajim.Gajim',
                                'Disconnect from the network', 'delay')),
        GLib.VariantType.new('(h)'),
        Gio.DBusCallFlags.NONE, -1, None, None)

    fd = ret.out_fd_list.get(0)


def appeared(connection, name, name_owner, *user_data):
    '''Set up a listener for suspend signals'''
    global supported
    supported = True
    log.info('%s appeared', name)
    if name == 'org.freedesktop.login1':
        connection.signal_subscribe(
            'org.freedesktop.login1',
            'org.freedesktop.login1.Manager',
            'PrepareForSleep',
            '/org/freedesktop/login1',
            None,
            Gio.DBusSignalFlags.NONE,
            signal_received,
            None)
        get_inhibitor(connection)


Gio.bus_watch_name(
    Gio.BusType.SYSTEM,
    'org.freedesktop.login1',
    Gio.BusNameWatcherFlags.NONE,
    appeared,
    None)
