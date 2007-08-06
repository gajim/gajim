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

import random
from tempfile import gettempdir
from subprocess import Popen

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
				_('A library used to validate server certificates to ensure a secure connection.'),
				_('Requires python-pyopenssl.'),
				_('Requires python-pyopenssl.')),
			_('Bonjour / Zeroconf'): (self.zeroconf_available,
				_('Serverless chatting with autodetected clients in a local network.'),
				_('Requires python-avahai.'),
				_('Requires pybonjour (http://o2s.csail.mit.edu/o2s-wiki/pybonjour).')),
			_('gajim-remote'): (self.dbus_available,
				_('A script to controle gajim via commandline.'),
				_('Requires python-dbus.'),
				_('Feature not available under Windows.')),
			_('OpenGPG'): (self.gpg_available,
				_('Encrypting chatmessages with gpg keys.'),
				_('Requires gpg and python-GnuPGInterface.'),
				_('Feature not available under Windows.')),
			_('network-manager'): (self.network_manager_available,
				_('Autodetection of network status.'),
				_('Requires gnome-network-manager and python-dbus.'),
				_('Feature not available under Windows.')),
			_('Session Management'): (self.session_management_available,
				_('Gajim session is stored on logout and restored on login.'),
				_('Requires python-gnome2.'),
				_('Feature not available under Windows.')),
			_('gnome-keyring'): (self.gnome_keyring_available,
				_('Passwords can be stored securely and not just in plaintext.'),
				_('Requires gnome-keyring and python-gnome2-desktop.'),
				_('Feature not available under Windows.')),
			_('SRV'): (self.srv_available,
				_('Ability to connect to servers which is using SRV records.'),
				_('Requires dnsutils.'),
				_('Requires nslookup to use SRV records.')),
			_('Spell Checker'): (self.speller_available,
				_('Spellchecking of composed messages.'),
				_('Requires python-gnome2-extras or compilation of gtkspell module from Gajim sources.'),
				_('Feature not available under Windows.')),
			_('Notification-daemon'): (self.notification_available,
				_('Passive popups notifying for new events.'),	
				_('Requires python-notify or instead python-dbus in conjunction with notification-daemon.'),
				_('Feature not available under Windows.')),
			_('Trayicon'): (self.trayicon_available,
				_('A icon in systemtray reflecting the current presence.'), 
				_('Requires python-gnome2-extras or compiled  trayicon module from Gajim sources.'),
				_('Requires PyGTK >= 2.10.')),
			_('Idle'): (self.idle_available,
				_('Ability to measure idle time, in order to set auto status.'),
				_('Requires compilation of the idle module from Gajim sources.'),
				_('Requires compilation of the idle module from Gajim sources.')),
			_('LaTeX'): (self.latex_available,
				_('Transform LaTeX espressions between $$ $$.'),
				_('Requires texlive-latex-base, dvips and imagemagick. You have to set \'use_latex\' to True in the Advanced Configuration Editor.'),
				_('Feature not available under Windows.')),
		}

		# name, supported
		self.model = gtk.ListStore(str, bool)
		treeview.set_model(self.model)

		col = gtk.TreeViewColumn(_('Available'))
		treeview.append_column(col)
		cell = gtk.CellRendererToggle()
		cell.set_property('radio', True)
		col.pack_start(cell)
		col.set_attributes(cell, active = 1)

		col = gtk.TreeViewColumn(_('Feature'))
		treeview.append_column(col)
		cell = gtk.CellRendererText()
		col.pack_start(cell, expand = True)
		col.add_attribute(cell, 'text', 0)

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

	def on_features_treeview_cursor_changed(self, widget):
		selection = widget.get_selection()
		path = selection.get_selected_rows()[1][0]
		available = self.model[path][1]
		feature = self.model[path][0]
		text = self.features[feature][1] + '\n'
		if os.name == 'nt':
			text = text + self.features[feature][3]
		else:
			text = text + self.features[feature][2]
		self.desc_label.set_text(text)

	def pyopenssl_available(self):
		try:
			import OpenSSL.SSL
			import OpenSSL.crypto
		except:
			return False
		return True

	def zeroconf_available(self):
		try:
			import avahi
		except:
			try:
				import pybonjour
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

	def latex_available(self):
		'''check is latex is available and if it can create a picture.'''

		if os.name == 'nt':
			return False

		exitcode = 0
		random.seed()
		tmpfile = os.path.join(gettempdir(), "gajimtex_" + \
			random.randint(0,100).__str__())

		# build latex string
		texstr = '\\documentclass[12pt]{article}\\usepackage[dvips]{graphicx}'
		texstr += '\\usepackage{amsmath}\\usepackage{amssymb}\\pagestyle{empty}'
		texstr += '\\begin{document}\\begin{large}\\begin{gather*}test'
		texstr += '\\end{gather*}\\end{large}\\end{document}'

		file = open(os.path.join(tmpfile + ".tex"), "w+")
		file.write(texstr)
		file.flush()
		file.close()
		try:
			p = Popen(['latex', '--interaction=nonstopmode', tmpfile + '.tex'],
				cwd=gettempdir())
			exitcode = p.wait()
		except:
			exitcode = 1
		if exitcode == 0:
			try:
				p = Popen(['dvips', '-E', '-o', tmpfile + '.ps', tmpfile + '.dvi'],
					cwd=gettempdir())
				exitcode = p.wait()
			except:
				exitcode = 1
		if exitcode == 0:
			try:
				p = Popen(['convert', tmpfile + '.ps', tmpfile + '.png'],
					cwd=gettempdir())
				exitcode = p.wait()
			except:
				exitcode = 1
		extensions = [".tex", ".log", ".aux", ".dvi", ".ps", ".png"]
		for ext in extensions:
			try:
				os.remove(tmpfile + ext)
			except Exception:
				pass
		if exitcode == 0:
			return True
		return False
