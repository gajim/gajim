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

from common import gajim
from conversation_textview import ConversationTextview
from message_textview import MessageTextView

####################
# FIXME: Can't this stuff happen once?
from common import i18n
_ = i18n._
APP = i18n.APP

GTKGUI_GLADE = 'gtkgui.glade'
####################

class ChatControl(MessageControl):
	'''A MessageControl of standard 1-1 chat'''
	def __init__(self, contact):
		MessageControl.__init__(self, 'chat_child_vbox', contact);
		self.always_compact_view = gajim.config.get('always_compact_view_chat')


# FIXME: Move this to a muc_control.py
class MultiUserChatControl(MessageControl):
	def __init__(self, contact):
		MessageControl.__init__(self, 'muc_child_vbox', contact);
