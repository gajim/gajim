##	chat_control.py
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
import gtkgui_helpers
import message_window

from common import gajim
from message_window import MessageControl
from conversation_textview import ConversationTextview
from message_textview import MessageTextView

####################
# FIXME: Can't this stuff happen once?
from common import i18n
_ = i18n._
APP = i18n.APP

GTKGUI_GLADE = 'gtkgui.glade'
####################

class ChatControl(message_window.MessageControl):
	'''A MessageControl for standard 1-1 chat'''
	def __init__(self, contact):
		MessageControl.__init__(self, 'chat_child_vbox', contact);
		self.compact_view = gajim.config.get('always_compact_view_chat')

	def draw_widgets(self):
		# The name banner is drawn here
		MessageControl.draw_widgets(self)

# FIXME: Move this to a muc_control.py
class MultiUserChatControl(message_window.MessageControl):
	def __init__(self, contact):
		MessageControl.__init__(self, 'muc_child_vbox', contact);
		self.compact_view = gajim.config.get('always_compact_view_gc')
