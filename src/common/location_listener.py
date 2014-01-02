# -*- coding: utf-8 -*-
## src/common/location_listener.py
##
## Copyright (C) 2009-2014 Yann Leboulanger <asterix AT lagaule.org>
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

from datetime import datetime

from common import gajim
from common import pep
from common import dbus_support
if dbus_support.supported:
    import dbus

class LocationListener:
    _instance = None
    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._data = {}

    def get_data(self):
        bus = dbus.SessionBus()
        try:
            # Initializes Geoclue.
            obj = bus.get_object('org.freedesktop.Geoclue.Master',
                    '/org/freedesktop/Geoclue/Master')
            # get MasterClient path
            path = obj.Create()
            # get MasterClient
            cli = bus.get_object('org.freedesktop.Geoclue.Master', path)
            cli.SetRequirements(1, 0, True, 1023)
    
            self._get_address(cli)
            self._get_position(cli)
        except:
            self._on_geoclue_position_changed()
            return
        

    def _get_address(self, cli):
        bus = dbus.SessionBus()
        cli.AddressStart()
        # Check that there is a provider
        name, description, service, path = cli.GetAddressProvider()
        if path:
            provider = bus.get_object(service, path)
            timestamp, address, accuracy = provider.GetAddress()
            self._on_geoclue_address_changed(timestamp, address, accuracy)

    def _get_position(self, cli):
        bus = dbus.SessionBus()
        cli.PositionStart()
        # Check that there is a provider
        name, description, service, path = cli.GetPositionProvider()
        if path:
            provider = bus.get_object(service, path)
            fields, timestamp, lat, lon, alt, accuracy = provider.GetPosition()
            self._on_geoclue_position_changed(fields, timestamp, lat, lon, alt,
                    accuracy)

    def start(self):
        self.location_info = {}
        self.get_data()
        bus = dbus.SessionBus()
        # Geoclue
        bus.add_signal_receiver(self._on_geoclue_address_changed,
                'AddressChanged', 'org.freedesktop.Geoclue.Address')
        bus.add_signal_receiver(self._on_geoclue_position_changed,
                'PositionChanged', 'org.freedesktop.Geoclue.Position')

    def shut_down(self):
        pass

    def _on_geoclue_address_changed(self, timestamp=None, address={},
    accuracy=None):
        # update data with info we just received
        for field in ['country', 'countrycode', 'locality', 'postalcode',
        'region', 'street']:
            self._data[field] = address.get(field, None)
        if timestamp:
            self._data['timestamp'] = self._timestamp_to_utc(timestamp)
        if accuracy:
            # in PEP it's horizontal accuracy
            self._data['accuracy'] = accuracy[1]
        self._send_location()

    def _on_geoclue_position_changed(self, fields=[], timestamp=None, lat=None,
    lon=None, alt=None, accuracy=None):
        # update data with info we just received
        _dict = {'lat': lat, 'lon': lon, 'alt': alt}
        for field in _dict:
            if _dict[field] is not None:
                self._data[field] = _dict[field]
        if timestamp:
            self._data['timestamp'] = self._timestamp_to_utc(timestamp)
        if accuracy:
            # in PEP it's horizontal accuracy
            self._data['accuracy'] = accuracy[1]
        self._send_location()

    def _send_location(self):
        accounts = gajim.connections.keys()
        for acct in accounts:
            if not gajim.account_is_connected(acct):
                continue
            if not gajim.config.get_per('accounts', acct, 'publish_location'):
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
            gajim.connections[acct].send_location(self._data)
            self.location_info = self._data.copy()

    def _timestamp_to_utc(self, timestamp):
        time = datetime.utcfromtimestamp(timestamp)
        return time.strftime('%Y-%m-%dT%H:%MZ')

def enable():
    listener = LocationListener.get()
    listener.start()

def disable():
    listener = LocationListener.get()
    listener.shut_down()
