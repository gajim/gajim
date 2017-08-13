# -*- coding: utf-8 -*-
## src/network_watcher.py
##
## Copyright (C) 2017 Philipp Hoerist <philipp AT hoerist.com>
## Copyright © 2017 Jörg Sommer <joerg@alea.gnuu.de>
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


import logging

from gi.repository import Gio, GLib

from gajim.common import app

log = logging.getLogger('gajim.network_watcher')


supported = False


def watch_name(name):
    Gio.bus_watch_name(
        Gio.BusType.SYSTEM,
        name,
        Gio.BusNameWatcherFlags.NONE,
        appeared,
        None)


def signal_received(connection, sender_name, object_path,
                    interface_name, signal_name, parameters, *user_data):
    connected = None
    log.info('Signal received: %s - %s', interface_name, parameters)
    if interface_name == 'org.freedesktop.NetworkManager':
        # https://people.freedesktop.org/~lkundrak/nm-docs/nm-dbus-types.html
        connected = parameters[0] == 70
    elif interface_name == 'org.freedesktop.DBus.Properties' and len(parameters) >= 2 \
         and parameters[0] == 'org.freedesktop.network1.Manager' \
         and 'OperationalState' in parameters[1]:
        connected = parameters[1]['OperationalState'] == 'routable'

    if connected is not None:
        GLib.timeout_add_seconds(
            2, update_connection_state,
            connected)


def appeared(connection, name, name_owner, *user_data):
    global supported
    supported = True
    log.info('%s appeared', name)
    if name == 'org.freedesktop.NetworkManager':
        connection.signal_subscribe(
            'org.freedesktop.NetworkManager',
            None,
            'StateChanged',
            '/org/freedesktop/NetworkManager',
            None,
            Gio.DBusSignalFlags.NONE,
            signal_received,
            None)
    elif name == 'org.freedesktop.network1':
        connection.signal_subscribe(
            'org.freedesktop.network1',
            None,
            'PropertiesChanged',
            '/org/freedesktop/network1',
            None,
            Gio.DBusSignalFlags.NONE,
            signal_received,
            None)


def update_connection_state(connected):
    if connected:
        for connection in app.connections.values():
            log.info('Connect %s', connection.name)
            connection.reconnect()
    else:
        for connection in app.connections.values():
            if connection.connected > 1:
                log.info('Disconnect %s', connection.name)
                connection.disconnectedReconnCB()


watch_name('org.freedesktop.NetworkManager')
watch_name('org.freedesktop.network1')
