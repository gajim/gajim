## statusicon.py
##
## Copyright (C) 2006 Nikos Kouremenos <kourem@gmail.com>
##
## This program is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License
## as published by the Free Software Foundation; either version 2
## of the License, or (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import gtk
import systray

class StatusIcon(systray.Systray):
	'''Class for the notification area icon'''
	#FIXME: when we migrate to GTK 2.10 stick only to this class
	# (remove systraywin32.py and systray.py)
	def __init__(self):
		self.status_icon = gtk.StatusIcon()
	
	def show_icon(self):
		self.status_icon.props.visible = True

	def hide_icon(self):
		self.status_icon.props.visible = False

	def on_clicked(self, widget, event):
		self.on_tray_leave_notify_event(widget, None)
		if event.button == 1: # Left click
			self.on_left_click()
		elif event.button == 2: # middle click
			self.on_middle_click()
		elif event.button == 3: # right click
			self.make_menu(event)

	def add_jid(self, jid, account, typ):
		systray.Systray.add_jid(self, jid, account, typ)

		unread_messages = gajim.interface.roster.nb_unread
		for acct in gajim.connections:
			# in chat / groupchat windows
			for kind in ('chats', 'gc'):
				jids = gajim.interface.instances[acct][kind]
				for jid in jids:
					if jid != 'tabbed':
						unread_messages += jids[jid].nb_unread[jid]
		
		text = i18n.ngettext(
			'Gajim - %d unread message',
			'Gajim - %d unread messages',
			unread_messages, unread_messages, unread_messages)

		self.status_icon.set_tooltip(text)

	def remove_jid(self, jid, account, typ):
		systray.Systray.remove_jid(self, jid, account, typ)

		unread_messages = gajim.interface.roster.nb_unread
		for acct in gajim.connections:
			# in chat / groupchat windows
			for kind in ('chats', 'gc'):
				for jid in gajim.interface.instances[acct][kind]:
					if jid != 'tabbed':
						unread_messages += gajim.interface.instances[acct][kind][jid].nb_unread[jid]
		
		if unread_messages > 0:
			text = i18n.ngettext(
				'Gajim - %d unread message',
				'Gajim - %d unread messages',
				unread_messages, unread_messages, unread_messages)
		else:
			text = 'Gajim'
		self.status_icon.set_tooltip(text)

	def set_img(self):
		if not gajim.interface.systray_enabled:
			return
		if len(self.jids) > 0:
			state = 'message'
		else:
			state = self.status
		image = gajim.interface.roster.jabber_state_images['16'][state]
		if image.get_storage_type() == gtk.IMAGE_PIXBUF:
			self.status_icon.props.pixbuf = image.get_pixbuf()
		#FIXME: oops they forgot to support GIF animation?
		#or they were lazy to get it to work under Windows! WTF!
		#elif image.get_storage_type() == gtk.IMAGE_ANIMATION:
		#	self.img_tray.set_from_animation(image.get_animation())
