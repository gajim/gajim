##	notify.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
## - Dimitur Kirov <dkirov@gmail.com>
## - Andrew Sayman <lorien420@myrealbox.com>
##
##	Copyright (C) 2003-2005 Gajim Team
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

HAS_DBUS = True

try:
	import dbus
except ImportError:
	HAS_DBUS = False

import os
import sys
import gajim
import dialogs

from common import gajim
from common import i18n
i18n.init()
_ = i18n._


def dbus_get_interface():
	try:
		session_bus = dbus.SessionBus()
		obj = session_bus.get_object('org.freedesktop.Notifications',
			'/org/freedesktop/Notifications')
		return dbus.Interface(obj, 'org.freedesktop.Notifications')
	except Exception, e:
		return None
	except dbus.DBusException, e:
		# This exception could give useful info about why notification breaks
		print >> sys.stderr, e
		return None

def dbus_available():
	if not HAS_DBUS:
		return False
	if dbus_get_interface() is None:
		return False
	else:
		return True
		
def dbus_notify(event_type, jid, account, msg_type = '', file_props = None):
	if jid in gajim.contacts[account]:
		actor = gajim.get_first_contact_instance_from_jid(account, jid).name
	else:
		actor = jid

	img = 'chat.png' # img to display
	ntype = 'im'     # Notification Type

	if event_type == _('Contact Signed In'):
		img = 'online.png'
		ntype = 'presence.online'
	elif event_type == _('Contact Signed Out'):
		img = 'offline.png'
		ntype = 'presence.offline'
	elif event_type in (_('New Message'), _('New Single Message'),
		_('New Private Message')):
		img = 'chat.png' # FIXME: better img and split events
		ntype = 'im.received'
		if event_type == _('New Private Message'):
			room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
			room_name,t = gajim.get_room_name_and_server_from_room_jid(room_jid)
			txt = _('%(nickname)s in room %(room_name)s has sent you a new message.')\
				% {'nickname': nick, 'room_name': room_name}
		else:
			#we talk about a name here
			txt = _('%s has sent you a new message.') % actor
	elif event_type == _('File Transfer Request'):
		img = 'requested.png' # FIXME: better img
		ntype = 'transfer'
		#we talk about a name here
		txt = _('%s wants to send you a file.') % actor
	elif event_type == _('File Transfer Error'):
		img = 'error.png' # FIXME: better img
		ntype = 'transfer.error'
	elif event_type in (_('File Transfer Completed'), _('File Transfer Stopped')):
		img = 'closed.png' # # FIXME: better img and split events
		ntype = 'transfer.complete'
		if file_props is not None:
			if file_props['type'] == 'r':
				# get the name of the sender, as it is in the roster
				sender = unicode(file_props['sender']).split('/')[0]
				name = gajim.get_first_contact_instance_from_jid( 
					account, sender).name
				filename = os.path.basename(file_props['file-name'])
				if event_type == _('File Transfer Completed'):
					txt = _('You successfully received %(filename)s from %(name)s.')\
						% {'filename': filename, 'name': name}
				else: # ft stopped
					txt = _('File transfer of %(filename)s from %(name)s stopped.')\
						% {'filename': filename, 'name': name}
			else:
				receiver = file_props['receiver']
				if hasattr(receiver, 'jid'):
					receiver = receiver.jid
				receiver = receiver.split('/')[0]
				# get the name of the contact, as it is in the roster
				name = gajim.get_first_contact_instance_from_jid( 
					account, receiver).name
				if event_type == _('File Transfer Completed'):
					txt = _('You successfully sent %(filename)s to %(name)s.')\
						% {'filename': filename, 'name': name}
				else: # ft stopped
					txt = _('File transfer of %(filename)s to %(name)s stopped.')\
						% {'filename': filename, 'name': name}
		else:
			txt = ''

	iconset = gajim.config.get('iconset')
	if not iconset:
		iconset = 'sun'
	# FIXME: use 32x32 or 48x48 someday
	path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset,	'16x16', img)
	path = os.path.abspath(path)
	notif = dbus_get_interface()
	if notif is None:
		raise dbus.DBusException()
	notif.Notify(dbus.String(_('Gajim')), 
		dbus.String(path), dbus.UInt32(0), ntype, dbus.Byte(0),
		dbus.String(event_type), dbus.String(txt),
		[dbus.String(path)], [''], [''], True, dbus.UInt32(3))

def notify(event_type, jid, account, msg_type = '', file_props = None):
	if dbus_available():
		try:
			dbus_notify(event_type, jid, account, msg_type, file_props)
			return
		except dbus.DBusException, e:
			# Connection to DBus failed, try popup
			pass
		except TypeError, e:
			# This means that we sent the message incorrectly
			print >> sys.stderr, e
	instance = dialogs.PopupNotificationWindow(event_type, jid, account,
		msg_type, file_props)
	#roster = roster_window.RosterWindow()
	gajim.interface.roster.popup_notification_windows.append(instance)


