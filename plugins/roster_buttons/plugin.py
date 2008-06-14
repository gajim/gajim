# -*- coding: utf-8 -*-

## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##

'''
Roster buttons plug-in.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 06/10/2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import sys

import gtk
from common import i18n
from common import gajim

from plugins import GajimPlugin
from plugins.helpers import log, log_calls

class RosterButtonsPlugin(GajimPlugin):
	name = u'Roster Buttons'
	short_name = u'roster_buttons'
	version = u'0.1'
	description = u'''Adds quick action buttons to roster window.'''
	authors = [u'Mateusz Biliński <mateusz@bilinski.it>']
	homepage = u'http://blog.bilinski.it'
	
	#@log_calls('RosterButtonsPlugin')
	#def __init__(self):
		#super(RosterButtonsPlugin, self).__init__()
		
	@log_calls('RosterButtonsPlugin')
	def activate(self):
		#log.debug('self.__path__==%s'%(self.__path__))
		self.GLADE_FILE_PATH = self.local_file_path('roster_buttons.glade')
		self.xml = gtk.glade.XML(self.GLADE_FILE_PATH, root='roster_buttons_buttonbox', domain=i18n.APP)
		self.buttonbox = self.xml.get_widget('roster_buttons_buttonbox')
		
		self.roster_vbox = gajim.interface.roster.xml.get_widget('roster_vbox2')
		self.roster_vbox.pack_start(self.buttonbox, expand=False)
		self.roster_vbox.reorder_child(self.buttonbox, 0)
		
		self.show_offline_contacts_menuitem = gajim.interface.roster.xml.get_widget('show_offline_contacts_menuitem')
		
		self.xml.signal_autoconnect(self)
		
		
	@log_calls('RosterButtonsPlugin')
	def deactivate(self):
		self.roster_vbox.remove(self.buttonbox)
		
		self.buttonbox = None
		self.xml = None
		
	@log_calls('RosterButtonsPlugin')
	def on_roster_button_1_clicked(self, button):
		#gajim.interface.roster.on_show_offline_contacts_menuitem_activate(None)
		self.show_offline_contacts_menuitem.set_active(not self.show_offline_contacts_menuitem.get_active())
		
	
	@log_calls('RosterButtonsPlugin')
	def on_roster_button_2_clicked(self, button):
		pass
	
	@log_calls('RosterButtonsPlugin')
	def on_roster_button_3_clicked(self, button):
		pass
	
	@log_calls('RosterButtonsPlugin')
	def on_roster_button_4_clicked(self, button):
		pass
	
