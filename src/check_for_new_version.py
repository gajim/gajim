##	check_for_new_version.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
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

import gtk
import gtk.glade

from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE='gtkgui.glade'

class Check_for_new_version_dialog:
	def __init__(self, plugin):
		self.plugin = plugin
		try:
			self.check_for_new_version()
		except:
			pass

	def parse_glade(self):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'new_version_available_dialog', APP)
		self.window = xml.get_widget('new_version_available_dialog')
		self.information_label = xml.get_widget('information_label')
		self.changes_textview = xml.get_widget('changes_textview')
		xml.signal_autoconnect(self)

	def on_new_version_available_dialog_delete_event(self, widget, event):
		self.window.destroy()

	def on_open_download_page_button_clicked(self, widget):
		url = 'http://www.gajim.org/downloads.php?lang='
		helpers.launch_browser_mailer('url', url)
		self.window.destroy()

	def check_for_new_version(self):
		'''parse online Changelog to find out last version
		and the changes for that latest version'''
		import urllib2
		import socket
		dto = socket.getdefaulttimeout()
		socket.setdefaulttimeout(5)

		url = 'http://trac.gajim.org/file/trunk/Changelog?rev=latest&format=txt'
		changelog = urllib2.urlopen(url)

		socket.setdefaulttimeout(dto)

		# format is 'Gajim version (date)'
		first_line = changelog.readline()
		finish_version = first_line.find(' ', 6) # start search after 'Gajim'
		latest_version = first_line[6:finish_version]
		if latest_version > gajim.version:
			start_date = finish_version + 2 # one space and one (
			date = first_line[start_date:-2] # remove the last ) and \n
			info = 'Gajim ' + latest_version + ' was released in ' + date + '!'
			changes = ''
			while True:
				line = changelog.readline().lstrip()
				if line.startswith('Gajim'):
					break
				else:
					if line != '\n' or line !='': # line has some content
						if not line.startswith('*'):
							# the is not a new *real* line
							# but a continuation from previous line.
							# So remove \n from previous 'line' beforing adding it
							changes = changes[:-1]

						changes += line
			
			self.parse_glade()
			self.information_label.set_text(info)
			buf = self.changes_textview.get_buffer()
			buf.set_text(changes)
			self.window.show_all()
