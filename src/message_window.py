##	message_window.py
##
## Copyright (C) 2005-2006 Travis Shirk <travis@pobox.com>
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
import pango
import gobject

from common import gajim

####################
# FIXME: Can't this stuff happen once?
from common import i18n
_ = i18n._
APP = i18n.APP

GTKGUI_GLADE = 'gtkgui.glade'
####################

#import chat_widget
#TYPE_CHAT = 1
#TYPE_MUC  = 2

class MessageWindow:
	'''Class for windows which contain message like things; chats,
	groupchats, etc.'''

	def __init__(self):
		self._controls = {}

		self.widget_name = 'message_window'
		self.xml = gtk.glade.XML(GTKGUI_GLADE, self.widget_name, APP)
		self.window = self.xml.get_widget(self.widget_name)
		self.alignment = self.xml.get_widget('alignment')
		self.notebook = self.xml.get_widget('notebook')

	def new_tab(self, type, contact, acct):
		pass

class MessageWindowMgr:
	'''A manager and factory for MessageWindow objects'''

	def __init__(self):
		self._windows = {}

