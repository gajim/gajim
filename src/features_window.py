##	features_window.py
##
## Copyright (C) 2007 Yann Le Boulanger <asterix@lagaule.org>
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
import gtk
import gobject
import gtkgui_helpers

import dialogs

from common import gajim
from common import helpers

class FeaturesWindow:
	'''Class for features window'''

	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('features_window.glade')
		self.window = self.xml.get_widget('features_window')
		treeview = self.xml.get_widget('features_treeview')
		self.desc_label = self.xml.get_widget('feature_desc_label')

		# {name: (available_function, unix_text, windows_text)}
		self.features = {
			_('PyOpenSSL'): (self.pyopenssl_available,
				_('You need to install python-pyopenssl to have a more secure connection.'),
				_('You need to install python-pyopenssl to have a more secure connection.')),
			_('Bonjour / Zeroconf'): (self.zeroconf_available,
				_('You need to install python-avahai to use Zeroconf network.'),
				_('This feature is not available under Windows.')),
			_('Gajim-remote'): (self.dbus_available,
				_('You need to install python-dbus to control gajim from a script.'),
				_('This feature is not available under Windows.')),
			_('OpenGPG'): (self.gpg_available,
				_('You need to install gpg and python-GnuPGIntergace to use OpenGPG.'),
				_('This feature is not available under Windows.')),
			_('Network Manager'): (self.network_manager_available,
				_('You need to install network-manager and python-dbus to use Network Manager.'),
				_('This feature is not available under Windows.')),
			_('Session Management'): (self.session_management_available,
				_('You need to install python-gnome2 to use Session Management.'),
				_('This feature is not available under Windows.')),
			_('Gnome-Keyring'): (self.gnome_keyring_available,
				_('You need to install python-gnome2-desktop to use Gnome Keyring.'),
				_('This feature is not available under Windows.')),
			_('SRV'): (self.srv_available,
				_('You need to install dnsutils to have nslookup to use SRV records.'),
				_('You need to have nslookup to use SRV records.')),
			_('Spell Checker'): (self.speller_available,
				_('You need to install python-gnome2-extras or compile gtkspell module from Gajim sources to use spell checker.'),
				_('This feature is not available under Windows.')),
			_('Notification-daemon'): (self.notification_available,
				_('You need to have dbus available and to install notification-daemon. Another solution is to install python-notify.'),
				_('This feature is not available under Windows.')),
			_('Trayicon'): (self.trayicon_available,
				_('You need to install python-gnome2-extras or compile trayicon module from Gajim sources to use the trayicon.'),
				_('You need PyGTK >= 2.10 to use the trayicon.')),
			_('Idle'): (self.idle_available,
				_('You need to compile idle module from Gajim sources to use it.'),
				_('You need to compile idle module from Gajim sources to use it.')),
		}

		# name, supported
		self.model = gtk.ListStore(str, bool)
		treeview.set_model(self.model)

		col = gtk.TreeViewColumn(_('Feature'))
		treeview.append_column(col)
		cell = gtk.CellRendererText()
		col.pack_start(cell, expand = True)
		col.add_attribute(cell, 'text', 0)

		col = gtk.TreeViewColumn(_('Available'))
		treeview.append_column(col)
		cell = gtk.CellRendererToggle()
		cell.set_property('sensitive', False)
		col.pack_start(cell)
		col.set_attributes(cell, active = 1)

		# Fill model
		for feature in self.features:
			func = self.features[feature][0]
			rep = func()
			self.model.append([feature, rep])
		self.xml.signal_autoconnect(self)
		self.window.show_all()
		self.xml.get_widget('close_button').grab_focus()

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_features_treeview_row_activated(self, widget, path, col):
		available = self.model[path][1]
		feature = self.model[path][0]
		if os.name == 'nt':
			text = self.features[feature][2]
		else:
			text = self.features[feature][1]
		self.desc_label.set_text(text)

	def pyopenssl_available(self):
		try:
			import OpenSSL.SSL
			import OpenSSL.crypto
		except:
			return False
		return True

	def zeroconf_available(self):
		if os.name == 'nt':
			return False
		try:
			import avahi
		except:
			return False
		return True

	def dbus_available(self):
		if os.name == 'nt':
			return False
		from common import dbus_support
		return dbus_support.supported

	def gpg_available(self):
		if os.name == 'nt':
			return False
		from common import GnuPG
		return GnuPG.USE_GPG

	def network_manager_available(self):
		if os.name == 'nt':
			return False
		import network_manager_listener
		return network_manager_listener.supported

	def session_management_available(self):
		if os.name == 'nt':
			return False
		try:
			import gnome.ui
		except:
			return False
		return True

	def gnome_keyring_available(self):
		if os.name == 'nt':
			return False
		try:
			import gnomekeyring
		except:
			return False
		return True

	def srv_available(self):
		return helpers.is_in_path('nslookup')

	def speller_available(self):
		if os.name == 'nt':
			return False
		try:
			import gtkspell
		except:
			return False
		return True

	def notification_available(self):
		if os.name == 'nt':
			return False
		from common import dbus_support
		if self.dbus_available() and dbus_support.get_notifications_interface():
			return True
		try:
			import pynotify
		except:
			return False
		return True

	def trayicon_available(self):
		if os.name == 'nt' and gtk.pygtk_version >= (2, 10, 0) and \
		gtk.gtk_version >= (2, 10, 0):
			return True
		try:
			import systray
		except:
			return False
		return True

	def idle_available(self):
		from common import sleepy
		return sleepy.SUPPORTED
