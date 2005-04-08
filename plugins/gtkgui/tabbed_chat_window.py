##	plugins/tabbed_chat_window.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
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
import pango
import gobject
import time

from dialogs import *
from history_window import *
from chat import *

from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'

class Tabbed_chat_window(Chat):
	"""Class for tabbed chat window"""
	def __init__(self, user, plugin, account):
		Chat.__init__(self, plugin, account, 'tabbed_chat_window')
		self.users = {}
		self.new_user(user)
		self.show_title()
		self.xml.signal_connect('on_tabbed_chat_window_destroy', \
			self.on_tabbed_chat_window_destroy)
		self.xml.signal_connect('on_tabbed_chat_window_delete_event', \
			self.on_tabbed_chat_window_delete_event)
		self.xml.signal_connect('on_tabbed_chat_window_focus_in_event', \
			self.on_tabbed_chat_window_focus_in_event)
		self.xml.signal_connect('on_chat_notebook_key_press_event', \
			self.on_chat_notebook_key_press_event)
		self.xml.signal_connect('on_chat_notebook_switch_page', \
			self.on_chat_notebook_switch_page)
		
	def draw_widgets(self, user):
		"""draw the widgets in a tab (status_image, contact_button ...)
		according to the the information in the user variable"""
		jid = user.jid
		status_image = self.xmls[jid].get_widget('status_image')
		image = self.plugin.roster.pixbufs[user.show]
		if image.get_storage_type() == gtk.IMAGE_ANIMATION:
			status_image.set_from_animation(image.get_animation())
		elif image.get_storage_type() == gtk.IMAGE_PIXBUF:
			status_image.set_from_pixbuf(image.get_pixbuf())
		contact_button = self.xmls[jid].get_widget('contact_button')
		contact_button.set_label(user.name + ' <' + jid + '>')
		if not user.keyID:
			self.xmls[jid].get_widget('gpg_togglebutton').set_sensitive(False)

	def set_image(self, jid):
		prio = 0
		list_users = self.plugin.roster.contacts[self.account][jid]
		sho = list_users[0].show
		for u in list_users:
			if u.priority > prio:
				prio = u.priority
				sho = u.show
		image = self.plugin.roster.pixbufs[sho]
		if image.get_storage_type() == gtk.IMAGE_ANIMATION:
			self.xmls[jid].get_widget('status_image').\
				set_from_animation(image.get_animation())
		elif image.get_storage_type() == gtk.IMAGE_PIXBUF:
			self.xmls[jid].get_widget('status_image').\
				set_from_pixbuf(image.get_pixbuf())

	def on_tabbed_chat_window_delete_event(self, widget, event):
		"""close window"""
		for jid in self.users:
			if time.time() - self.last_message_time[jid] < 2: # 2 seconds
				dialog = Confirmation_dialog(_('You received a message from %s in the last two seconds.\nDo you still want to close this window ?') % jid)
				if dialog.get_response() != gtk.RESPONSE_YES:
					return True #stop the propagation of the event

	def on_tabbed_chat_window_destroy(self, widget):
		#clean self.plugin.windows[self.account]['chats']
		Chat.on_window_destroy(self, widget, 'chats')

	def on_tabbed_chat_window_focus_in_event(self, widget, event):
		Chat.on_chat_window_focus_in_event(self, widget, event)

	def on_chat_notebook_key_press_event(self, widget, event):
		Chat.on_chat_notebook_key_press_event(self, widget, event)

	def on_clear_button_clicked(self, widget):
		"""When clear button is pressed :
		clear the conversation"""
		jid = self.get_active_jid()
		conversation_buffer = self.xmls[jid].get_widget('conversation_textview').\
			get_buffer()
		start, end = conversation_buffer.get_bounds()
		conversation_buffer.delete(start, end)

	def on_history_button_clicked(self, widget):
		"""When history button is pressed : call history window"""
		jid = self.get_active_jid()
		if not self.plugin.windows['logs'].has_key(jid):
			self.plugin.windows['logs'][jid] = history_window(self.plugin, jid)

	def remove_tab(self, jid):
		if time.time() - self.last_message_time[jid] < 2:
			dialog = Confirmation_dialog(_('You received a message from %s in the last two seconds.\nDo you still want to close this tab?') % jid)
			if dialog.get_response() != gtk.RESPONSE_YES:
				return

		Chat.remove_tab(self, jid, 'chats')
		if len(self.xmls) > 0:
			del self.users[jid]

	def new_user(self, user):
		self.names[user.jid] = user.name
		self.xmls[user.jid] = gtk.glade.XML(GTKGUI_GLADE, 'chats_vbox', APP)
		self.childs[user.jid] = self.xmls[user.jid].get_widget('chats_vbox')
		Chat.new_tab(self, user.jid)
		self.users[user.jid] = user
		
		self.redraw_tab(user.jid)
		self.draw_widgets(user)
		self.print_conversation(_("%s is %s (%s)") % (user.name, \
										user.show, user.status), user.jid, 'status')

		#print queued messages
		if self.plugin.queues[self.account].has_key(user.jid):
			self.read_queue(user.jid)

		if self.plugin.config['print_time'] == 'sometimes':
			self.print_time_timeout(user.jid)
			self.print_time_timeout_id[user.jid] = gobject.timeout_add(300000, \
				self.print_time_timeout, user.jid)

	def on_message_textview_key_press_event(self, widget, event):
		"""When a key is pressed:
		if enter is pressed without the shit key, message (if not empty) is sent
		and printed in the conversation"""
		jid = self.get_active_jid()
		print 'jid', jid
		conversation_textview = self.xmls[jid].get_widget('conversation_textview')
		if event.keyval == gtk.keysyms.Tab and \
         (event.state & gtk.gdk.CONTROL_MASK): # CTRL + TAB
			self.notebook.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Page_Down: # PAGE DOWN
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE DOWN
				self.notebook.emit('key_press_event', event)
			elif event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE DOWN
				conversation_textview.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Page_Up: # PAGE UP
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE UP
				self.notebook.emit('key_press_event', event)
			elif event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE UP
				conversation_textview.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Return or \
			event.keyval == gtk.keysyms.KP_Enter: # ENTER
			if (event.state & gtk.gdk.SHIFT_MASK):
				return False
			if self.plugin.connected[self.account] < 2: #we are not connected
				Error_dialog(_('You are not connected, so you cannot send a message'))
				return True
			message_buffer = widget.get_buffer()
			start_iter = message_buffer.get_start_iter()
			end_iter = message_buffer.get_end_iter()
			message = message_buffer.get_text(start_iter, end_iter, 0)
			if message != '':
				keyID = ''
				if self.xmls[jid].get_widget('gpg_togglebutton').get_active():
					keyID = self.users[jid].keyID
				self.plugin.send('MSG', self.account, (jid, message, keyID))
				message_buffer.set_text('', -1)
				self.print_conversation(message, jid, jid)
			return True
		return False

	def on_contact_button_clicked(self, widget):
		"""When button contact is clicked"""
		jid = self.get_active_jid()
		user = self.users[jid]
		self.plugin.roster.on_info(widget, user, self.account)

	def read_queue(self, jid):
		"""read queue and print messages containted in it"""
		q = self.plugin.queues[self.account][jid]
		user = self.users[jid]
		while not q.empty():
			event = q.get()
			self.print_conversation(event[0], jid, tim = event[1])
			self.plugin.roster.nb_unread -= 1
		self.plugin.roster.show_title()
		del self.plugin.queues[self.account][jid]
		self.plugin.roster.redraw_jid(jid, self.account)
		if self.plugin.systray_enabled:
			self.plugin.systray.remove_jid(jid, self.account)
		showOffline = self.plugin.config['showoffline']
		if (user.show == 'offline' or user.show == 'error') and \
			not showOffline:
			if len(self.plugin.roster.contacts[self.account][jid]) == 1:
				self.plugin.roster.remove_user(user, self.account)

	def print_conversation(self, text, jid, contact = '', tim = None):
		"""Print a line in the conversation :
		if contact is set to status : it's a status message
		if contact is set to another value : it's an outgoing message
		if contact is not set : it's an incomming message"""
		user = self.users[jid]
		if contact == 'status':
			kind = 'status'
			name = ''
		else:
			if contact:
				kind = 'outgoing'
				name = self.plugin.nicks[self.account] 
			else:
				kind = 'incoming'
				name = user.name

		Chat.print_conversation_line(self, text, jid, kind, name, tim)
