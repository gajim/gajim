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

from common import gajim
import dialogs
import history_window
import chat

from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class Tabbed_chat_window(chat.Chat):
	"""Class for tabbed chat window"""
	def __init__(self, user, plugin, account):
		chat.Chat.__init__(self, plugin, account, 'tabbed_chat_window')
		self.users = {}
		self.new_user(user)
		self.show_title()
		self.xml.signal_connect('on_tabbed_chat_window_destroy', 
			self.on_tabbed_chat_window_destroy)
		self.xml.signal_connect('on_tabbed_chat_window_delete_event', 
			self.on_tabbed_chat_window_delete_event)
		self.xml.signal_connect('on_tabbed_chat_window_focus_in_event', 
			self.on_tabbed_chat_window_focus_in_event)
		self.xml.signal_connect('on_chat_notebook_key_press_event', 
			self.on_chat_notebook_key_press_event)
		self.xml.signal_connect('on_chat_notebook_switch_page', 
			self.on_chat_notebook_switch_page)
		self.window.show_all()

	def save_var(self, jid):
		'''return the specific variable of a jid, like gpg_enabled
		the return value have to be compatible with wthe one given to load_var'''
		gpg_enabled = self.xmls[jid].get_widget('gpg_togglebutton').get_active()
		return {'gpg_enabled': gpg_enabled}
	
	def load_var(self, jid, var):
		if not self.xmls.has_key(jid):
			return
		self.xmls[jid].get_widget('gpg_togglebutton').set_active(
			var['gpg_enabled'])
		
	def draw_widgets(self, user):
		"""draw the widgets in a tab (status_image, contact_button ...)
		according to the the information in the user variable"""
		jid = user.jid
		self.set_state_image(jid)
		contact_button = self.xmls[jid].get_widget('contact_button')
		contact_button.set_use_underline(False)
		contact_button.set_label(user.name + ' <' + jid + '>')
		if not user.keyID:
			self.xmls[jid].get_widget('gpg_togglebutton').set_sensitive(False)

		nontabbed_status_image = self.xmls[jid].get_widget(
																	'nontabbed_status_image')
		if len(self.xmls) > 1:
			nontabbed_status_image.hide()
		else:
			nontabbed_status_image.show()

	def set_state_image(self, jid):
		prio = 0
		list_users = self.plugin.roster.contacts[self.account][jid]
		user = list_users[0]
		show = user.show
		jid = user.jid
		for u in list_users:
			if u.priority > prio:
				prio = u.priority
				show = u.show
		child = self.childs[jid]
		status_image = self.notebook.get_tab_label(child).get_children()[0]
		state_images = self.plugin.roster.get_appropriate_state_images(jid)
		image = state_images[show]
		non_tabbed_status_image = self.xmls[jid].get_widget(
																	'nontabbed_status_image')
		if image.get_storage_type() == gtk.IMAGE_ANIMATION:
			non_tabbed_status_image.set_from_animation(image.get_animation())
			status_image.set_from_animation(image.get_animation())
		elif image.get_storage_type() == gtk.IMAGE_PIXBUF:
			non_tabbed_status_image.set_from_pixbuf(image.get_pixbuf())
			status_image.set_from_pixbuf(image.get_pixbuf())

	def on_tabbed_chat_window_delete_event(self, widget, event):
		"""close window"""
		for jid in self.users:
			if time.time() - self.last_message_time[jid] < 2: # 2 seconds
				dialog = dialogs.Confirmation_dialog(_('You received a message from %s in the last two seconds.\nDo you still want to close this window?') % jid)
				if dialog.get_response() != gtk.RESPONSE_YES:
					return True #stop the propagation of the event

	def on_tabbed_chat_window_destroy(self, widget):
		#clean self.plugin.windows[self.account]['chats']
		chat.Chat.on_window_destroy(self, widget, 'chats')

	def on_tabbed_chat_window_focus_in_event(self, widget, event):
		chat.Chat.on_chat_window_focus_in_event(self, widget, event)

	def on_chat_notebook_key_press_event(self, widget, event):
		chat.Chat.on_chat_notebook_key_press_event(self, widget, event)

	def on_clear_button_clicked(self, widget):
		"""When clear button is pressed:	clear the conversation"""
		jid = self.get_active_jid()
		textview = self.xmls[jid].get_widget('conversation_textview')
		self.on_clear(None, textview)

	def on_history_button_clicked(self, widget):
		"""When history button is pressed: call history window"""
		jid = self.get_active_jid()
		if self.plugin.windows['logs'].has_key(jid):
			self.plugin.windows['logs'][jid].window.present()
		else:
			self.plugin.windows['logs'][jid] = history_window.\
				History_window(self.plugin, jid, self.account)

	def remove_tab(self, jid):
		if time.time() - self.last_message_time[jid] < 2:
			dialog = dialogs.Confirmation_dialog(_('You received a message from %s in the last two seconds.\nDo you still want to close this tab?') % jid)
			if dialog.get_response() != gtk.RESPONSE_YES:
				return

		chat.Chat.remove_tab(self, jid, 'chats')
		if len(self.xmls) > 0:
			del self.users[jid]

		jid = self.get_active_jid() # get the new active jid  
		if jid != '':
			nontabbed_status_image = self.xmls[jid].get_widget(
				'nontabbed_status_image')  
			if len(self.xmls) > 1:  
				nontabbed_status_image.hide()  
			else:
				nontabbed_status_image.show()

	def new_user(self, user):
		self.names[user.jid] = user.name
		self.xmls[user.jid] = gtk.glade.XML(GTKGUI_GLADE, 'chats_vbox', APP)
		self.childs[user.jid] = self.xmls[user.jid].get_widget('chats_vbox')
		chat.Chat.new_tab(self, user.jid)
		self.users[user.jid] = user
		
		self.redraw_tab(user.jid)
		self.draw_widgets(user)
		self.print_conversation(_('%s is %s (%s)') % (user.name, \
										user.show, user.status), user.jid, 'status')

		#print queued messages
		if self.plugin.queues[self.account].has_key(user.jid):
			self.read_queue(user.jid)

		if gajim.config.get('print_time') == 'sometimes':
			self.print_time_timeout(user.jid)
			self.print_time_timeout_id[user.jid] = gobject.timeout_add(300000, \
				self.print_time_timeout, user.jid)
		#FIXME: why show if already visible from glade?
		#self.childs[user.jid].show_all() 

	def on_message_textview_key_press_event(self, widget, event):
		"""When a key is pressed:
		if enter is pressed without the shit key, message (if not empty) is sent
		and printed in the conversation"""
		jid = self.get_active_jid()
		conversation_textview = self.xmls[jid].get_widget('conversation_textview')
		if event.keyval == gtk.keysyms.ISO_Left_Tab: # SHIFT + TAB
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + SHIFT + TAB
				self.notebook.emit('key_press_event', event)
		if event.keyval == gtk.keysyms.Tab:
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + TAB
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
			if gajim.connections[self.account].connected < 2: #we are not connected
				dialogs.Error_dialog(_('You are not connected, so you cannot send a message'))
				return True
			message_buffer = widget.get_buffer()
			start_iter = message_buffer.get_start_iter()
			end_iter = message_buffer.get_end_iter()
			message = message_buffer.get_text(start_iter, end_iter, 0)
			if message != '':
				if message == '/clear':
					self.on_clear(None, conversation_textview) # clear conversation
					self.on_clear(None, widget) # clear message textview too
					return True
				keyID = ''
				if self.xmls[jid].get_widget('gpg_togglebutton').get_active():
					keyID = self.users[jid].keyID
				gajim.connections[self.account].send_message(jid, message, keyID)
				message_buffer.set_text('', -1)
				self.print_conversation(message, jid, jid)
			return True
		return False

	def on_contact_button_clicked(self, widget):
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
		self.plugin.roster.draw_contact(jid, self.account)
		if self.plugin.systray_enabled:
			self.plugin.systray.remove_jid(jid, self.account)
		showOffline = gajim.config.get('showoffline')
		if (user.show == 'offline' or user.show == 'error') and \
			not showOffline:
			if len(self.plugin.roster.contacts[self.account][jid]) == 1:
				self.plugin.roster.really_remove_user(user, self.account)

	def print_conversation(self, text, jid, contact = '', tim = None):
		"""Print a line in the conversation:
		if contact is set to status: it's a status message
		if contact is set to another value: it's an outgoing message
		if contact is not set: it's an incomming message"""
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

		chat.Chat.print_conversation_line(self, text, jid, kind, name, tim)
