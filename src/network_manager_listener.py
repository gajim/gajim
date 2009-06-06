# -*- coding: utf-8 -*-
## src/network_manager_listener.py
##
## Copyright (C) 2006 Jeffrey C. Ollie <jeff AT ocjtech.us>
##                    Nikos Kouremenos <kourem AT gmail.com>
##                    Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2007 Yann Leboulanger <asterix AT lagaule.org>
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

import sys
from common import gajim

def device_now_active(self, *args):
	'''For Network Manager 0.6'''
	for connection in gajim.connections.itervalues():
		if gajim.config.get_per('accounts', connection.name,
		'listen_to_network_manager') and connection.time_to_reconnect:
			connection._reconnect()

def device_no_longer_active(self, *args):
	'''For Network Manager 0.6'''
	for connection in gajim.connections.itervalues():
		if gajim.config.get_per('accounts', connection.name,
		'listen_to_network_manager') and connection.connected > 1:
			connection._disconnectedReconnCB()

def state_changed(state): 
	'''For Network Manager 0.7'''
	if props.Get("org.freedesktop.NetworkManager", "State") == 3: 
		for connection in gajim.connections.itervalues(): 
			if gajim.config.get_per('accounts', connection.name, 
			'listen_to_network_manager') and connection.time_to_reconnect: 
				connection._reconnect() 
	else: 
		for connection in gajim.connections.itervalues(): 
			if gajim.config.get_per('accounts', connection.name, 
			'listen_to_network_manager') and connection.connected > 1: 
				connection._disconnectedReconnCB()

supported = False

if sys.platform == 'darwin':
	supported = True
else:
	try:
		from common.dbus_support import system_bus

		bus = system_bus.bus()

		if 'org.freedesktop.NetworkManager' in bus.list_names():
			nm_object = bus.get_object('org.freedesktop.NetworkManager', 
				'/org/freedesktop/NetworkManager') 
			props = dbus.Interface(nm_object,"org.freedesktop.DBus.Properties") 
			bus.add_signal_receiver(state_changed, 
				'StateChanged', 
				'org.freedesktop.NetworkManager', 
				'org.freedesktop.NetworkManager', 
				'/org/freedesktop/NetworkManager')
			supported = True

	except Exception:
		try:
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
		except Exception:
			pass

# vim: se ts=3:
