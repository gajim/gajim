# -*- coding:utf-8 -*-
## src/common/dbus_support.py
##
## Copyright (C) 2005 Andrew Sayman <lorien420 AT myrealbox.com>
##                    Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2005-2007 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
##                    Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

import os, sys

from common import gajim
from common import exceptions

_GAJIM_ERROR_IFACE = 'org.gajim.dbus.Error'

try:
	import dbus
	import dbus.glib
except ImportError:
	supported = False
	if not os.name == 'nt': # only say that to non Windows users
		print _('D-Bus python bindings are missing in this computer')
		print _('D-Bus capabilities of Gajim cannot be used')
else:
	try:
		# test if dbus-x11 is installed
		bus = dbus.SessionBus()
		supported = True # does user have D-Bus bindings?
	except dbus.DBusException:
		supported = False
		if not os.name == 'nt': # only say that to non Windows users
			print _('D-Bus does not run correctly on this machine')
			print _('D-Bus capabilities of Gajim cannot be used')

class SystemBus:
	'''A Singleton for the DBus SystemBus'''
	def __init__(self):
		self.system_bus = None

	def SystemBus(self):
		if not supported:
			raise exceptions.DbusNotSupported

		if not self.present():
				raise exceptions.SystemBusNotPresent
		return self.system_bus

	def bus(self):
		return self.SystemBus()

	def present(self):
		if not supported:
			return False
		if self.system_bus is None:
			try:
				self.system_bus = dbus.SystemBus()
			except dbus.DBusException:
				self.system_bus = None
				return False
			if self.system_bus is None:
				return False
			# Don't exit Gajim when dbus is stopped
			self.system_bus.set_exit_on_disconnect(False)
		return True

system_bus = SystemBus()

class SessionBus:
	'''A Singleton for the D-Bus SessionBus'''
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
			except dbus.DBusException:
				self.session_bus = None
				return False
			if self.session_bus is None:
				return False
		return True

session_bus = SessionBus()

def get_interface(interface, path, start_service=True):
	'''Returns an interface on the current SessionBus. If the interface isn\'t
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
			if start_service and dbus_iface.StartServiceByName(interface, dbus.UInt32(0)) == 1:
				started = True
			else:
				started = False
		if not started:
			return None
		obj = bus.get_object(interface, path)
		return dbus.Interface(obj, interface)
	except Exception, e:
		gajim.log.debug(str(e))
		return None


def get_notifications_interface(notif=None):
	'''Returns the notifications interface.

	:param notif: DesktopNotification instance'''
	# try to see if KDE notifications are available
	iface = get_interface('org.kde.VisualNotifications', '/VisualNotifications',
		start_service=False)
	if iface != None:
		if notif != None:
			notif.kde_notifications = True
		return iface
	# KDE notifications don't seem to be available, falling back to
	# notification-daemon
	else:
		if notif != None:
			notif.kde_notifications = False
		return get_interface('org.freedesktop.Notifications',
			'/org/freedesktop/Notifications')

if supported:
	class MissingArgument(dbus.DBusException):
		_dbus_error_name = _GAJIM_ERROR_IFACE + '.MissingArgument'

	class InvalidArgument(dbus.DBusException):
		'''Raised when one of the provided arguments is invalid.'''
		_dbus_error_name = _GAJIM_ERROR_IFACE + '.InvalidArgument'

# vim: se ts=3:
