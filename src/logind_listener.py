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

from common import dbus_support
from common import gajim

log = logging.getLogger('gajim.logind_listener')
supported = False
fd = -1  # file descriptor of the inhibitor; negative number means we don't
         # hold any (yet)


def on_suspend(active):
    '''Signal handler for suspend event'''

    global fd

    if not active:
        # we just resumed, we should take another inhibitor
        get_inhibitor()
        return

    # we're going for suspend, let's disconnect
    log.debug('System suspend detected, disconnecting from network...')
    for name, conn in gajim.connections.items():
        if gajim.account_is_connected(name):
            conn.old_show = gajim.SHOW_LIST[conn.connected]
            st = conn.status
            conn.change_status('offline', _('Machine going to sleep'))
            conn.status = st
            conn.time_to_reconnect = 5

    # close the file descriptor and let the computer suspend
    if fd >= 0:
        os.close(fd)
        fd = -1;
    else:
        # something is wrong, the system is suspending but we don't have
        # a lock file
        log.warning("System suspend detected, but we don't seem to be holding "
            "a file descriptor for sleep inihibitor")

def get_inhibitor():
    '''Ask for a suspend delay inhibitor'''

    from common.dbus_support import system_bus, dbus
    bus = system_bus.bus()
    global fd

    if fd >= 0:
        # someting is wrong, we haven't closed the previous file descriptor
        # and we ask for yet another one
        log.warning('We are about to ask for a sleep inhibitor, but we seem '
            'to be holding one already')

    login_object = bus.get_object('org.freedesktop.login1',
        '/org/freedesktop/login1')
    login_manager = dbus.Interface(login_object,
        'org.freedesktop.login1.Manager')

    ret = login_manager.Inhibit('sleep', 'Gajim', 'Disconnect from the network',
        'delay')
    fd = ret.take()

def set_listener():
    '''Set up a listener for suspend signals

    @return bool whether it succeeded
    '''
    from common.dbus_support import system_bus
    bus = system_bus.bus()

    if not 'org.freedesktop.login1' in bus.list_names():
        # logind is not present
        log.debug("logind is not on D-Bus, not activating logind listener")
        return False

    bus.add_signal_receiver(on_suspend, signal_name='PrepareForSleep',
        bus_name='org.freedesktop.login1',
        path='/org/freedesktop/login1',
        dbus_interface='org.freedesktop.login1.Manager')
    return True

if dbus_support.supported:
    try:
        if set_listener():
            get_inhibitor()
            supported = True
    except Exception as ex:
        log.error("A problem occured while activating logind listener")
