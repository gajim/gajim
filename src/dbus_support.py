##  dbus_support.py
##
## Contributors for this file:
## - Andrew Sayman <lorien420@myrealbox.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
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

import os
import sys

from common import exceptions
from common import i18n
_ = i18n._

try:
	import dbus
	version = getattr(dbus, 'version', (0, 20, 0))
except ImportError:
	version = (0, 0, 0)
	
if version >= (0, 41, 0):
	import dbus.service
	import dbus.glib # cause dbus 0.35+ doesn't return signal replies without it

supported = True
if 'dbus' not in globals() and not os.name == 'nt':
	print _('D-Bus python bindings are missing in this computer')
	print _('D-Bus capabilities of Gajim cannot be used')
	supported = False
# dbus 0.23 leads to segfault with threads_init()
if sys.version[:4] >= '2.4' and version[1] < 30:
	supported = False

class SessionBus:
	'''A Singleton for the DBus SessionBus'''
	def __init__(self):
		self.session_bus = None
	
	def SessionBus(self):
		if not supported:
			raise exceptions.DbusNotSupported

		if not self.present():
				raise exceptions.SessionBusNotPresent
		return self.session_bus

	def bus(self):
		return self.SessionBus()

	def present(self):
		if not supported:
			return False
		if self.session_bus is None:
			try:
				self.session_bus = dbus.SessionBus()
			except dbus.dbus_bindings.DBusException:
				self.session_bus = None
				return False
			if self.session_bus is None:
				return False
		return True

session_bus = SessionBus()

def get_interface(interface, path):
	'''Returns an interface on the current SessionBus. If the interface isn't 
	running, it tries to start it first.'''
	if not supported:
		return None
	if session_bus.present():
		bus = session_bus.SessionBus()
	else:
		return None
	try:
		obj = bus.get_object('org.freedesktop.DBus', '/org/freedesktop/DBus')
		dbus_iface = dbus.Interface(obj, 'org.freedesktop.DBus')
		running_services = dbus_iface.ListNames()
		started = True
		if interface not in running_services:
			# try to start the service
			if dbus_iface.StartServiceByName(interface, dbus.UInt32(0)) == 1:
				started = True
			else:
				started = False
		if not started:
			return None
		obj = bus.get_object(interface, path)
		return dbus.Interface(obj, interface)
	except Exception, e:
		print >> sys.stderr, e
		return None
	except dbus.dbus_bindings.DBusException, e:
		# This exception could give useful info about why notification breaks
		print >> sys.stderr, e
		return None


def get_notifications_interface():
	'''Returns the notifications interface.'''
	return get_interface('org.freedesktop.Notifications','/org/freedesktop/Notifications')
