##	notify.py
##
## Contributors for this file:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Nikos Kouremenos <kourem@gmail.com>
## - Dimitur Kirov <dkirov@gmail.com>
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
## DBUS/libnotify connection code:
## Copyright (C) 2005 by Sebastian Estienne
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
import gajim
import dialogs
import gobject

from common import gajim
from common import exceptions
from common import i18n
i18n.init()
_ = i18n._

import dbus_support
if dbus_support.supported:
	import dbus
	if dbus_support.version >= (0, 41, 0):
		import dbus.glib
		import dbus.service

def notify(event_type, jid, account, msg_type = '', path_to_image = None,
	text = None):
	'''Notifies a user of an event. It first tries to a valid implementation of
	the Desktop Notification Specification. If that fails, then we fall back to
	the older style PopupNotificationWindow method.'''
	if gajim.config.get('use_notif_daemon') and dbus_support.supported:
		try:
			DesktopNotification(event_type, jid, account, msg_type, path_to_image,
				text)
			return
		except dbus.dbus_bindings.DBusException, e:
			# Connection to D-Bus failed, try popup
			gajim.log.debug(str(e))
		except TypeError, e:
			# This means that we sent the message incorrectly
			gajim.log.debug(str(e))
	instance = dialogs.PopupNotificationWindow(event_type, jid, account, msg_type, path_to_image, text)
	gajim.interface.roster.popup_notification_windows.append(instance)

class NotificationResponseManager:
	'''Collects references to pending DesktopNotifications and manages there
	signalling. This is necessary due to a bug in DBus where you can't remove
	a signal from an interface once it's connected.'''
	def __init__(self):
		self.pending = {}
		self.interface = None

	def attach_to_interface(self):
		if self.interface is not None:
			return
		self.interface = dbus_support.get_notifications_interface()
		self.interface.connect_to_signal('ActionInvoked', self.on_action_invoked)
		self.interface.connect_to_signal('NotificationClosed', self.on_closed)

	def on_action_invoked(self, id, reason):
		if self.pending.has_key(id):
			notification = self.pending[id]
			notification.on_action_invoked(id, reason)
			del self.pending[id]
		else:
			# This happens in the case of a race condition where the user clicks
			# on a popup before the program finishes registering this callback
			gobject.timeout_add(1000, self.on_action_invoked, id, reason)

	def on_closed(self, id, reason):
		if self.pending.has_key(id):
			del self.pending[id]

notification_response_manager = NotificationResponseManager()

class DesktopNotification:
	'''A DesktopNotification that interfaces with DBus via the Desktop
	Notification specification'''
	def __init__(self, event_type, jid, account, msg_type = '',
		path_to_image = None, text = None):
		self.account = account
		self.jid = jid
		self.msg_type = msg_type

		if not text:
			text = gajim.get_actor(account, jid) # default value of text
			
		if event_type == _('Contact Signed In'):
			ntype = 'presence.online'
		elif event_type == _('Contact Signed Out'):
			ntype = 'presence.offline'
		elif event_type in (_('New Message'), _('New Single Message'),
			_('New Private Message')):
			ntype = 'im.received'
		elif event_type == _('File Transfer Request'):
			ntype = 'transfer'
		elif event_type == _('File Transfer Error'):
			ntype = 'transfer.error'
		elif event_type in (_('File Transfer Completed'), _('File Transfer Stopped')):
			ntype = 'transfer.complete'
		elif event_type == _('New E-mail'):
			ntype = 'gmail.notify'
		else:
			# default failsafe values
			path_to_image = os.path.abspath(
				os.path.join(gajim.DATA_DIR, 'pixmaps', 'events',
					'chat_msg_recv.png')) # img to display
			ntype = 'im' # Notification Type

		self.notif = dbus_support.get_notifications_interface()
		if self.notif is None:
			raise dbus.dbus_bindings.DBusException()
		timeout = gajim.config.get('notification_timeout') # in seconds
		# Determine the version of notifications
		# FIXME: This code is blocking, as is the next set. That should be fixed
		# now that we have a class to encapsulate this behavior
		try:
			(name, vendor, version) = self.notif.GetServerInfo()
		except:
			# No way to determine the version number, set it to the latest
			# since it doesn't properly support the version number
			version = '0.3.1'
		if version.startswith('0.2'):
			try:
				self.id = self.notif.Notify(dbus.String(_('Gajim')),
					dbus.String(path_to_image), dbus.UInt32(0), ntype, dbus.Byte(0),
					dbus.String(event_type), dbus.String(text),
					[dbus.String(path_to_image)], {'default': 0}, [''], True,
						dbus.UInt32(timeout))
			except AttributeError:
				version = '0.3.1' # we're actually dealing with the newer version
		if version.startswith('0.3'):
			self.id = self.notif.Notify(dbus.String(_('Gajim')),
				dbus.String(path_to_image), dbus.UInt32(0), dbus.String(event_type),
				dbus.String(text), dbus.String(''), {}, dbus.UInt32(timeout*1000))
		notification_response_manager.attach_to_interface()
		notification_response_manager.pending[self.id] = self

	def on_action_invoked(self, id, reason):
		if self.notif is None:
			return
		self.notif.CloseNotification(dbus.UInt32(id))
		self.notif = None
		if not self.msg_type:
			self.msg_type = 'chat'
		gajim.interface.handle_event(self.account, self.jid, self.msg_type)
