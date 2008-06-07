## statusicon.py
##
## Copyright (C) 2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2007 Lukas Petrovicky <lukas@petrovicky.net>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or
## modify it under the terms of the GNU General Public License
## as published by the Free Software Foundation; either version 2
## of the License, or (at your option) any later version.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

import sys
import gtk
import systray

from common import gajim
from common import helpers

if sys.platform == 'darwin':
	try:
		import osx
	except:
		pass

class StatusIcon(systray.Systray):
	'''Class for the notification area icon'''
	#FIXME: when we migrate to GTK 2.10 stick only to this class
	# (move base stuff from systray.py and rm it)
	#NOTE: gtk api does NOT allow:
	# leave, enter motion notify
	# and can't do cool tooltips we use
	def __init__(self):
		systray.Systray.__init__(self)
		self.status_icon = None
		
	def show_icon(self):
		if not self.status_icon:
			self.status_icon = gtk.StatusIcon()
			self.status_icon.connect('activate', self.on_status_icon_left_clicked)
			self.status_icon.connect('popup-menu',
				self.on_status_icon_right_clicked)

		self.set_img()
		self.status_icon.set_visible(True)
		self.subscribe_events()

	def on_status_icon_right_clicked(self, widget, event_button, event_time):
		self.make_menu(event_button, event_time)

	def hide_icon(self):
		self.status_icon.set_visible(False)
		self.unsubscribe_events()

	def on_status_icon_left_clicked(self, widget):
		self.on_left_click()

	def set_img(self):
		'''apart from image, we also update tooltip text here'''
		if not gajim.interface.systray_enabled:
			return
		text = helpers.get_notification_icon_tooltip_text()
		self.status_icon.set_tooltip(text)
		if gajim.events.get_nb_systray_events():
			if sys.platform == 'darwin':
				osx.nsapp.requestUserAttention()
			state = 'event'
			self.status_icon.set_blinking(True)
		else:
			state = self.status
			self.status_icon.set_blinking(False)
		
		#FIXME: do not always use 16x16 (ask actually used size and use that)
		image = gajim.interface.jabber_state_images['16'][state]
		if image.get_storage_type() == gtk.IMAGE_PIXBUF:
			self.status_icon.set_from_pixbuf(image.get_pixbuf())
		#FIXME: oops they forgot to support GIF animation?
		#or they were lazy to get it to work under Windows! WTF!
		#elif image.get_storage_type() == gtk.IMAGE_ANIMATION:
		#	self.img_tray.set_from_animation(image.get_animation())
