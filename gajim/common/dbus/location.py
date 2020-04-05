# Copyright (C) 2009-2014 Yann Leboulanger <asterix AT lagaule.org>
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

import logging
from datetime import datetime

from gi.repository import GLib
from nbxmpp.structs import LocationData

from gajim.common import app

if app.is_installed('GEOCLUE'):
    from gi.repository import Geoclue  # pylint: disable=ungrouped-imports,no-name-in-module

log = logging.getLogger('gajim.c.dbus.location')


class LocationListener:
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._data = {}
        self.location_info = {}
        self.simple = None

    # Note: do not remove third parameter `param`
    #       because notify signal expects three parameters
    def _on_location_update(self, simple, _param=None):
        location = simple.get_location()
        timestamp = location.get_property("timestamp")[0]
        lat = location.get_property("latitude")
        lon = location.get_property("longitude")
        alt = location.get_property("altitude")
        # in XEP-0080 it's horizontal accuracy
        acc = location.get_property("accuracy")

        # update data with info we just received
        self._data = {'lat': lat, 'lon': lon, 'alt': alt, 'accuracy': acc}
        self._data['timestamp'] = self._timestamp_to_utc(timestamp)
        self._send_location()

    def _on_simple_ready(self, _obj, result):
        try:
            self.simple = Geoclue.Simple.new_finish(result)
        except GLib.Error as error:
            if error.domain == 'g-dbus-error-quark':
                log.warning("Could not enable geolocation: %s", error.message)
            else:
                raise
        else:
            self.simple.connect('notify::location', self._on_location_update)
            self._on_location_update(self.simple)

    def get_data(self):
        Geoclue.Simple.new("org.gajim.Gajim",
                           Geoclue.AccuracyLevel.EXACT,
                           None,
                           self._on_simple_ready)

    def start(self):
        self.location_info = {}
        self.get_data()

    def _send_location(self):
        accounts = app.connections.keys()
        for acct in accounts:
            if not app.account_is_available(acct):
                continue
            if not app.config.get_per('accounts', acct, 'publish_location'):
                continue
            if self.location_info == self._data:
                continue
            if 'timestamp' in self.location_info and 'timestamp' in self._data:
                last_data = self.location_info.copy()
                del last_data['timestamp']
                new_data = self._data.copy()
                del new_data['timestamp']
                if last_data == new_data:
                    continue
            app.connections[acct].get_module('UserLocation').set_location(
                LocationData(**self._data))
            self.location_info = self._data.copy()

    @staticmethod
    def _timestamp_to_utc(timestamp):
        time = datetime.utcfromtimestamp(timestamp)
        return time.strftime('%Y-%m-%dT%H:%MZ')


def enable():
    if not app.is_installed('GEOCLUE'):
        log.warning('GeoClue not installed')
        return

    listener = LocationListener.get()
    listener.start()
