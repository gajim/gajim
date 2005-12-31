##	groupchat_control.py
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
from chat_control import ChatControlBase
from conversation_textview import ConversationTextview
from message_textview import MessageTextView

class GroupchatControl(ChatControlBase):
	TYPE_ID = 2

	def __init__(self, parent_win, contact, acct):
		ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
					'muc_child_vbox', _('Group Chat'), contact, acct);
		self.compact_view_always = gajim.config.get('always_compact_view_gc')
		# muc attention states (when we are mentioned in a muc)
		# if the room jid is in the list, the room has mentioned us
		self.muc_attentions = []
