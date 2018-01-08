# -*- coding: utf-8 -*-
## gajim/screensaver_listener.py
##
## Copyright (C) 2018 André Apitzsch <git AT apitzsch.eu>
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

log = logging.getLogger('gajim.screensaver_listener')


def signal_received(connection, sender_name, object_path,
                    interface_name, signal_name, parameters, *user_data):
    '''Signal handler for screensaver active change'''

    log.info('Signal received: %s - %s', interface_name, parameters)

    roster = app.interface.roster

    if not parameters[0]:
        for account in app.connections:
            if app.account_is_connected(account) and \
                    app.sleeper_state[account] == 'autoaway-forced':
                # We came back online after screensaver
                # autoaway
                roster.send_status(account, 'online',
                                   app.status_before_autoaway[account])
                app.status_before_autoaway[account] = ''
                app.sleeper_state[account] = 'online'
        return
    if not app.config.get('autoaway'):
        # Don't go auto away if user disabled the option
        return
    for account in app.connections:
        if account not in app.sleeper_state or not app.sleeper_state[account]:
            continue
        if app.sleeper_state[account] == 'online':
            if not app.account_is_connected(account):
                continue
            # we save our online status
            app.status_before_autoaway[account] = \
                app.connections[account].status
            # we go away (no auto status) [we pass True to auto param]
            auto_message = app.config.get('autoaway_message')
            if not auto_message:
                auto_message = app.connections[account].status
            else:
                auto_message = auto_message.replace('$S', '%(status)s')
                auto_message = auto_message.replace('$T', '%(time)s')
                auto_message = auto_message % {
                    'status': app.status_before_autoaway[account],
                    'time': app.config.get('autoxatime')}
            roster.send_status(account, 'away', auto_message, auto=True)
            app.sleeper_state[account] = 'autoaway-forced'


def appeared(connection, name, name_owner, *user_data):
    '''Set up a listener for screensaver signals'''
    log.info('%s appeared', name)
    connection.signal_subscribe(
        'org.gnome.ScreenSaver',
        'org.gnome.ScreenSaver',
        'ActiveChanged',
        '/org/gnome/ScreenSaver',
        None,
        Gio.DBusSignalFlags.NONE,
        signal_received,
        None)


Gio.bus_watch_name(
    Gio.BusType.SESSION,
    'org.gnome.ScreenSaver',
    Gio.BusNameWatcherFlags.NONE,
    appeared,
    None)
