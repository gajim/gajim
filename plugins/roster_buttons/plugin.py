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
:since: 14th June 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import sys

import gtk
from common import gajim

from plugins import GajimPlugin
from plugins.helpers import log, log_calls

class RosterButtonsPlugin(GajimPlugin):

    @log_calls('RosterButtonsPlugin')
    def init(self):
        self.description = _('Adds quick action buttons to roster window.')
        self.GTK_BUILDER_FILE_PATH = self.local_file_path('roster_buttons.ui')
        self.roster_vbox = gajim.interface.roster.xml.get_object('roster_vbox2')
        self.show_offline_contacts_menuitem = gajim.interface.roster.xml.get_object('show_offline_contacts_menuitem')

        self.config_dialog = None

    @log_calls('RosterButtonsPlugin')
    def activate(self):
        self.xml = gtk.Builder()
        self.xml.set_translation_domain('gajim_plugins')
        self.xml.add_objects_from_file(self.GTK_BUILDER_FILE_PATH,
                ['roster_buttons_buttonbox'])
        self.buttonbox = self.xml.get_object('roster_buttons_buttonbox')

        self.roster_vbox.pack_start(self.buttonbox, expand=False)
        self.roster_vbox.reorder_child(self.buttonbox, 0)
        self.xml.connect_signals(self)

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
