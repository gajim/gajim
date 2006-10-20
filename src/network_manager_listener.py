# -*- coding: utf-8 -*-
##	network_manager_listener.py
##
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
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

import dbus
import dbus.glib

NM_OBJ_PATH = '/org/freedesktop/NetworkManager'
NM_INTERFACE = 'org.freedesktop.NetworkManager'
NM_SERVICE = 'org.freedesktop.NetworkManager'

class NetworkManagerListener:
	def __init__(self, nm_activated_CB, nm_deactivated_CB):
		sys_bus = dbus.SystemBus()
		proxy_obj = sys_bus.get_object(NM_SERVICE, NM_OBJ_PATH)
		self._nm_iface = dbus.Interface(proxy_obj, NM_INTERFACE)

		self._devices = self._nm_iface.getDevices()

		self._nm_iface.connect_to_signal('DeviceNowActive',
			nm_activated_CB)
		self._nm_iface.connect_to_signal('DeviceNoLongerActive',
			nm_deactivated_CB)
