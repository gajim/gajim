# -*- coding: utf-8 -*-
##	network_manager_listener.py
## Copyright (C) 2006 Jeffrey C. Ollie <jeff at ocjtech.us>
## Copyright (C) 2006 Stefan Bethge <stefan at lanpartei.de>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

from common import gajim

def device_now_active(self, *args):
	for connection in gajim.connections.itervalues():
		if gajim.config.get_per('accounts', connection.name,
		'listen_to_network_manager') and connection.time_to_reconnect:
			connection._reconnect()

def device_no_longer_active(self, *args):
	for connection in gajim.connections.itervalues():
		if gajim.config.get_per('accounts', connection.name,
		'listen_to_network_manager') and connection.connected > 1:
			connection._disconnectedReconnCB()

supported = False

try:
	from common.dbus_support import system_bus

	bus = system_bus.SystemBus()

	if 'org.freedesktop.NetworkManager' in bus.list_names():
		supported = True
		bus.add_signal_receiver(device_no_longer_active,
			'DeviceNoLongerActive',
			'org.freedesktop.NetworkManager',
			'org.freedesktop.NetworkManager',
			'/org/freedesktop/NetworkManager')

		bus.add_signal_receiver(device_now_active,
			'DeviceNowActive',
			'org.freedesktop.NetworkManager',
			'org.freedesktop.NetworkManager',
			'/org/freedesktop/NetworkManager')
except:
	pass
