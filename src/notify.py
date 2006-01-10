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

def notify(event_type, jid, account, msg_type = '', file_props = None):
	'''Notifies a user of an event. It first tries to a valid implementation of
	the Desktop Notification Specification. If that fails, then we fall back to
	the older style PopupNotificationWindow method.'''
	if gajim.config.get('use_notif_daemon') and dbus_support.supported:
		try:
			DesktopNotification(event_type, jid, account, msg_type, file_props)
			return
		except dbus.dbus_bindings.DBusException, e:
			# Connection to D-Bus failed, try popup
			gajim.log.debug(str(e))
		except TypeError, e:
			# This means that we sent the message incorrectly
			gajim.log.debug(str(e))
	instance = dialogs.PopupNotificationWindow(event_type, jid, account,
		msg_type, file_props)
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
	def __init__(self, event_type, jid, account, msg_type = '', file_props = None):
		self.account = account
		self.jid = jid
		self.msg_type = msg_type
		self.file_props = file_props

		contact = gajim.contacts.get_first_contact_from_jid(account, jid)
		if contact:
			actor = contact.get_shown_name()
		else:
			actor = jid

		txt = actor # default value of txt
		transport_name = gajim.get_transport_name_from_jid(jid)
		
		if transport_name in ('aim', 'icq', 'msn', 'yahoo'):
			prefix = transport_name
		else:
			prefix = 'jabber'
		'''
		if transport_name == 'aim':
			prefix = 'aim'
		elif transport_name == 'icq':
			prefix = 'icq'
		elif transport_name == 'msn':
			prefix = 'msn'
		elif transport_name == 'yahoo':
			prefix = 'yahoo'
		else:
			prefix = 'jabber'
		'''

		if event_type == _('Contact Signed In'):
			img = prefix + '_online.png'
			ntype = 'presence.online'
		elif event_type == _('Contact Signed Out'):
			img = prefix + '_offline.png'
			ntype = 'presence.offline'
		elif event_type in (_('New Message'), _('New Single Message'),
			_('New Private Message')):
			ntype = 'im.received'
			if event_type == _('New Private Message'):
				room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
				room_name,t = gajim.get_room_name_and_server_from_room_jid(room_jid)
				txt = _('%(nickname)s in room %(room_name)s has sent you a new message.')\
					% {'nickname': nick, 'room_name': room_name}
				img = 'priv_msg_recv.png'
			else:
				#we talk about a name here
				txt = _('%s has sent you a new message.') % actor
				if event_type == _('New Message'):
					img = 'chat_msg_recv.png'
				else: # New Single Message
					img = 'single_msg_recv.png'
		elif event_type == _('File Transfer Request'):
			img = 'ft_request.png'
			ntype = 'transfer'
			#we talk about a name here
			txt = _('%s wants to send you a file.') % actor
		elif event_type == _('File Transfer Error'):
			img = 'ft_stopped.png'
			ntype = 'transfer.error'
		elif event_type in (_('File Transfer Completed'), _('File Transfer Stopped')):
			ntype = 'transfer.complete'
			if file_props is not None:
				if file_props['type'] == 'r':
					# get the name of the sender, as it is in the roster
					sender = unicode(file_props['sender']).split('/')[0]
					name = gajim.contacts.get_first_contact_from_jid(account,
						sender).get_shown_name()
					filename = os.path.basename(file_props['file-name'])
					if event_type == _('File Transfer Completed'):
						txt = _('You successfully received %(filename)s from %(name)s.')\
							% {'filename': filename, 'name': name}
						img = 'ft_done.png'
					else: # ft stopped
						txt = _('File transfer of %(filename)s from %(name)s stopped.')\
							% {'filename': filename, 'name': name}
						img = 'ft_stopped.png'
				else:
					receiver = file_props['receiver']
					if hasattr(receiver, 'jid'):
						receiver = receiver.jid
					receiver = receiver.split('/')[0]
					# get the name of the contact, as it is in the roster
					name = gajim.contacts.get_first_contact_from_jid(account,
						receiver).get_shown_name()
					filename = os.path.basename(file_props['file-name'])
					if event_type == _('File Transfer Completed'):
						txt = _('You successfully sent %(filename)s to %(name)s.')\
							% {'filename': filename, 'name': name}
						img = 'ft_done.png'
					else: # ft stopped
						txt = _('File transfer of %(filename)s to %(name)s stopped.')\
							% {'filename': filename, 'name': name}
						img = 'ft_stopped.png'
			else:
				txt = ''
		elif event_type == _('New Email'):
			txt = _('You have new E-mail on %s.') % (jid)
			ntype = 'gmail.notify'
		else:
			# defaul failsafe values
			img = 'chat_msg_recv.png' # img to display
			ntype = 'im'	 # Notification Type

		path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'events', img)
		path = os.path.abspath(path)

		self.notif = dbus_support.get_notifications_interface()
		if self.notif is None:
			raise dbus.dbus_bindings.DBusException()
		timeout = gajim.config.get('notification_timeout') # in seconds
		try: self.id = self.notif.Notify(dbus.String(_('Gajim')),
			dbus.String(path), dbus.UInt32(0), ntype, dbus.Byte(0),
			dbus.String(event_type), dbus.String(txt),
			[dbus.String(path)], {'default': 0}, [''], True, dbus.UInt32(timeout))
		except AttributeError: # For libnotify 0.3.x
			self.id = self.notif.Notify(dbus.String(_('Gajim')),
				dbus.String(path), dbus.UInt32(0), dbus.String(event_type),
				dbus.String(txt), dbus.String(""), {}, dbus.UInt32(timeout/1000))
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
