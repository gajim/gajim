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
import message_control

from common import gajim
from chat_control import ChatControl
from chat_control import ChatControlBase
from conversation_textview import ConversationTextview
from message_textview import MessageTextView

class PrivateChatControl(ChatControl):
	TYPE_ID = message_control.TYPE_PM

	def __init__(self, parent_win, contact, acct):
		ChatControl.__init__(self, parent_win, contact, acct)
		self.TYPE_ID = 'pm'
		self.display_name = _('Private char')

class GroupchatControl(ChatControlBase):
	TYPE_ID = message_control.TYPE_GC

	def __init__(self, parent_win, contact, acct):
		ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
					'muc_child_vbox', _('Group Chat'), contact, acct);
		self.compact_view_always = gajim.config.get('always_compact_view_gc')
		# muc attention states (when we are mentioned in a muc)
		# if the room jid is in the list, the room has mentioned us
		self.muc_attentions = []

	def markup_tab_label(self, label_str, chatstate):
		'''Markup the label if necessary.  Returns a tuple such as:
		(new_label_str, color)
		either of which can be None
		if chatstate is given that means we have HE SENT US a chatstate'''
			
		num_unread = self.nb_unread

		has_focus = self.parent_win.get_property('has-toplevel-focus')
		current_tab = self.parent_win.get_active_control() == self
		color = None
		theme = gajim.config.get('roster_theme')
		if chatstate == 'attention' and (not has_focus or not current_tab):
			if jid not in self.muc_attentions:
				self.muc_attentions.append(jid)
			color = gajim.config.get_per('themes', theme,
							'state_muc_directed_msg')
		elif chatstate:
			if chatstate == 'active' or (current_tab and has_focus):
				if jid in self.muc_attentions:
					self.muc_attentions.remove(jid)
				color = gajim.config.get_per('themes', theme,
								'state_active_color')
			elif chatstate == 'newmsg' and (not has_focus or not current_tab) and\
			     jid not in self.muc_attentions:
				color = gajim.config.get_per('themes', theme, 'state_muc_msg')
		if color:
			color = gtk.gdk.colormap_get_system().alloc_color(color)
			# The widget state depend on whether this tab is the "current" tab
			if current_tab:
				nickname.modify_fg(gtk.STATE_NORMAL, color)
			else:
				nickname.modify_fg(gtk.STATE_ACTIVE, color)

		if num_unread: # if unread, text in the label becomes bold
			label_str = '<b>' + str(num_unread) + label_str + '</b>'
		return (label_str, color)

