##	plugins/tabbed_chat_window.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Alex Podaras <bigpod@gmail.com>
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
import sre

from dialogs import *
from history_window import *

from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'

class tabbed_chat_window:
	"""Class for tabbed chat window"""
	def __init__(self, user, plugin, account):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'tabbed_chat_window', APP)
		self.chat_notebook = self.xml.get_widget('chat_notebook')
		self.chat_notebook.remove_page(0)
		self.plugin = plugin
		self.account = account
		self.change_cursor = None
		self.xmls = {}
		self.tagIn = {}
		self.tagOut = {}
		self.tagStatus = {}
		self.users = {}
		self.nb_unread = {}
		self.last_message_time = {}
		self.print_time_timeout_id = {}
		self.window = self.xml.get_widget('tabbed_chat_window')
		self.new_user(user)
		self.show_title()
		self.xml.signal_connect('on_tabbed_chat_window_destroy', \
			self.on_tabbed_chat_window_destroy)
		self.xml.signal_connect('on_tabbed_chat_window_delete_event', \
			self.on_tabbed_chat_window_delete_event)
		self.xml.signal_connect('on_tabbed_chat_window_focus_in_event', \
			self.on_tabbed_chat_window_focus_in_event)
		self.xml.signal_connect('on_tabbed_chat_window_key_press_event', \
			self.on_tabbed_chat_window_key_press_event)
		self.xml.signal_connect('on_chat_notebook_switch_page', \
			self.on_chat_notebook_switch_page)
		
	def update_tags(self):
		for jid in self.tagIn:
			self.tagIn[jid].set_property("foreground", \
				self.plugin.config['inmsgcolor'])
			self.tagOut[jid].set_property("foreground", \
				self.plugin.config['outmsgcolor'])
			self.tagStatus[jid].set_property("foreground", \
				self.plugin.config['statusmsgcolor'])

	def update_print_time(self):
		if self.plugin.config['print_time'] != 'sometimes':
			list_jid = self.print_time_timeout_id.keys()
			for jid in list_jid:
				gobject.source_remove(self.print_time_timeout_id[jid])
				del self.print_time_timeout_id[jid]
		else:
			for jid in self.xmls:
				if not self.print_time_timeout_id.has_key(jid):
					self.print_time_timeout(jid)
					self.print_time_timeout_id[jid] = gobject.timeout_add(300000, \
						self.print_time_timeout, jid)

	def show_title(self):
		"""redraw the window's title"""
		unread = 0
		for jid in self.nb_unread:
			unread += self.nb_unread[jid]
		start = ""
		if unread > 1:
			start = "[" + str(unread) + "] "
		elif unread == 1:
			start = "* "
		chat = self.users[jid].name
		if len(self.xmls) > 1:
			chat = 'Chat'
		self.window.set_title(start + chat + ' (' + self.account + ')')

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

	def redraw_tab(self, jid):
		"""redraw the label of the tab"""
		start = ''
		if self.nb_unread[jid] > 1:
			start = "[" + str(self.nb_unread[jid]) + "] "
		elif self.nb_unread[jid] == 1:
			start = "* "
		child = self.xmls[jid].get_widget('chat_vbox')
		self.chat_notebook.set_tab_label_text(child, start + self.users[jid].name)

	def set_image(self, image, jid):
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
		for jid in self.users:
			del self.plugin.windows[self.account]['chats'][jid]
			if self.print_time_timeout_id.has_key(jid):
				gobject.source_remove(self.print_time_timeout_id[jid])
		if self.plugin.windows[self.account]['chats'].has_key('tabbed'):
			del self.plugin.windows[self.account]['chats']['tabbed']

	def get_active_jid(self):
		active_child = self.chat_notebook.get_nth_page(\
			self.chat_notebook.get_current_page())
		active_jid = ''
		for jid in self.xmls:
			child = self.xmls[jid].get_widget('chat_vbox')
			if child == active_child:
				active_jid = jid
				break
		return active_jid

	def on_clear_button_clicked(self, widget):
		"""When clear button is pressed :
		clear the conversation"""
		jid = self.get_active_jid()
		conversation_buffer = self.xmls[jid].get_widget('conversation_textview').\
			get_buffer()
		start, end = conversation_buffer.get_bounds()
		conversation_buffer.delete(start, end)

	def on_close_button_clicked(self, button):
		"""When close button is pressed :
		close a tab"""
		jid = self.get_active_jid()
		self.remove_tab(jid)

	def on_tabbed_chat_window_focus_in_event(self, widget, event):
		"""When window get focus"""
		jid = self.get_active_jid()
		conversation_textview = self.xmls[jid].\
			get_widget('conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		end_iter = conversation_buffer.get_end_iter()
		end_rect = conversation_textview.get_iter_location(end_iter)
		visible_rect = conversation_textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			#we are at the end
			if self.nb_unread[jid] > 0:
				self.nb_unread[jid] = 0
				self.redraw_tab(jid)
				self.show_title()
				self.plugin.systray.remove_jid(jid, self.account)

	def on_history_button_clicked(self, widget):
		"""When history button is pressed : call history window"""
		jid = self.get_active_jid()
		if not self.plugin.windows['logs'].has_key(jid):
			self.plugin.windows['logs'][jid] = history_window(self.plugin, jid)

	def on_chat_notebook_switch_page(self, notebook, page, page_num):
		new_child = notebook.get_nth_page(page_num)
		new_jid = ''
		for jid in self.xmls:
			child = self.xmls[jid].get_widget('chat_vbox')
			if child == new_child:
				new_jid = jid
				break
		conversation_textview = self.xmls[new_jid].\
			get_widget('conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		end_iter = conversation_buffer.get_end_iter()
		end_rect = conversation_textview.get_iter_location(end_iter)
		visible_rect = conversation_textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			#we are at the end
			if self.nb_unread[new_jid] > 0:
				self.nb_unread[new_jid] = 0
				self.redraw_tab(new_jid)
				self.show_title()
				self.plugin.systray.remove_jid(new_jid, self.account)

	def active_tab(self, jid):
		child = self.xmls[jid].get_widget('chat_vbox')
		self.chat_notebook.set_current_page(\
			self.chat_notebook.page_num(child))

	def remove_tab(self, jid):
		if time.time() - self.last_message_time[jid] < 2:
			dialog = Confirmation_dialog(_('You received a message from %s in the last two seconds.\nDo you still want to close this tab ?') % jid)
			if dialog.get_response() != gtk.RESPONSE_YES:
				return

		if len(self.xmls) == 1:
			self.window.destroy()
		else:
			if self.print_time_timeout_id.has_key(jid):
				gobject.source_remove(self.print_time_timeout_id[jid])
				del self.print_time_timeout_id[jid]
			self.chat_notebook.remove_page(\
				self.chat_notebook.get_current_page())
			del self.plugin.windows[self.account]['chats'][jid]
			del self.users[jid]
			del self.nb_unread[jid]
			del self.last_message_time[jid]
			del self.xmls[jid]
			del self.tagIn[jid]
			del self.tagOut[jid]
			del self.tagStatus[jid]
			if len(self.xmls) == 1:
				self.chat_notebook.set_show_tabs(False)
			self.show_title()

	def new_user(self, user):
		self.nb_unread[user.jid] = 0
		self.last_message_time[user.jid] = 0
		self.users[user.jid] = user
		self.xmls[user.jid] = gtk.glade.XML(GTKGUI_GLADE, 'chat_vbox', APP)
		
		conversation_textview = \
			self.xmls[user.jid].get_widget('conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		end_iter = conversation_buffer.get_end_iter()
		conversation_buffer.create_mark('end', end_iter, 0)
		self.tagIn[user.jid] = conversation_buffer.create_tag('incoming')
		color = self.plugin.config['inmsgcolor']
		self.tagIn[user.jid].set_property('foreground', color)
		self.tagOut[user.jid] = conversation_buffer.create_tag('outgoing')
		color = self.plugin.config['outmsgcolor']
		self.tagOut[user.jid].set_property('foreground', color)
		self.tagStatus[user.jid] = conversation_buffer.create_tag('status')
		color = self.plugin.config['statusmsgcolor']
		self.tagStatus[user.jid].set_property('foreground', color)
		
		tag = conversation_buffer.create_tag('time_sometimes')
		tag.set_property('foreground', '#9e9e9e')
		tag.set_property('scale', pango.SCALE_SMALL)
		tag.set_property('justification', gtk.JUSTIFY_CENTER)
		
		tag = conversation_buffer.create_tag('url')
		tag.set_property('foreground', '#0000ff')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)
		tag.connect('event', self.hyperlink_handler, 'url')

		tag = conversation_buffer.create_tag('mail')
		tag.set_property('foreground', '#0000ff')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)
		tag.connect('event', self.hyperlink_handler, 'mail')
		
		tag = conversation_buffer.create_tag('bold')
		tag.set_property('weight', pango.WEIGHT_BOLD)
		
		tag = conversation_buffer.create_tag('italic')
		tag.set_property('style', pango.STYLE_ITALIC)
		
		tag = conversation_buffer.create_tag('underline')
		tag.set_property('underline', pango.UNDERLINE_SINGLE)
		
		self.xmls[user.jid].signal_autoconnect(self)
		conversation_scrolledwindow = self.xmls[user.jid].\
			get_widget('conversation_scrolledwindow')
		conversation_scrolledwindow.get_vadjustment().connect('value-changed', \
			self.on_conversation_vadjustment_value_changed)
		
		self.chat_notebook.append_page(self.xmls[user.jid].\
			get_widget('chat_vbox'))
		if len(self.xmls) > 1:
			self.chat_notebook.set_show_tabs(True)

		self.redraw_tab(user.jid)
		self.draw_widgets(user)
		self.show_title()

		#print queued messages
		if self.plugin.queues[self.account].has_key(user.jid):
			self.read_queue(user.jid)
		if user.show != 'online':
			self.print_conversation(_("%s is now %s (%s)") % (user.name, \
				user.show, user.status), user.jid, 'status')

		if self.plugin.config['print_time'] == 'sometimes':
			self.print_time_timeout(user.jid)
			self.print_time_timeout_id[user.jid] = gobject.timeout_add(300000, \
				self.print_time_timeout, user.jid)

	def on_message_textview_key_press_event(self, widget, event):
		"""When a key is pressed :
		if enter is pressed without the shit key, message (if not empty) is sent
		and printed in the conversation"""
		if event.keyval == gtk.keysyms.Return:
			if (event.state & gtk.gdk.SHIFT_MASK):
				return 0
			message_buffer = widget.get_buffer()
			start_iter = message_buffer.get_start_iter()
			end_iter = message_buffer.get_end_iter()
			message = message_buffer.get_text(start_iter, end_iter, 0)
			if message != '':
				keyID = ''
				jid = self.get_active_jid()
				if self.xmls[jid].get_widget('gpg_togglebutton').get_active():
					keyID = self.users[jid].keyID
				self.plugin.send('MSG', self.account, (jid, message, keyID))
				message_buffer.set_text('', -1)
				self.print_conversation(message, jid, jid)
			return 1
		return 0

	def on_tabbed_chat_window_key_press_event(self, widget, event):
		st = '1234567890' # zero is here cause humans count from 1, pc from 0 :P
		jid = self.get_active_jid()
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.remove_tab(jid)
		elif event.string and event.string in st \
			and (event.state & gtk.gdk.MOD1_MASK): # alt + 1,2,3..
			self.chat_notebook.set_current_page(st.index(event.string))
		elif event.keyval == gtk.keysyms.Page_Down: # PAGE DOWN
			if event.state & gtk.gdk.CONTROL_MASK:
				current = self.chat_notebook.get_current_page()
				if current > 0:
					self.chat_notebook.set_current_page(current-1)
#				else:
#					self.chat_notebook.set_current_page(\
#						self.chat_notebook.get_n_pages()-1)
			elif event.state & gtk.gdk.SHIFT_MASK:
				conversation_textview = self.xmls[jid].\
					get_widget('conversation_textview')
				rect = conversation_textview.get_visible_rect()
				iter = conversation_textview.get_iter_at_location(rect.x,\
					rect.y + rect.height)
				conversation_textview.scroll_to_iter(iter, 0.1, True, 0, 0)
		elif event.keyval == gtk.keysyms.Page_Up: # PAGE UP
			if event.state & gtk.gdk.CONTROL_MASK:
				current = self.chat_notebook.get_current_page()
				if current < (self.chat_notebook.get_n_pages()-1):
					self.chat_notebook.set_current_page(current+1)
#				else:
#					self.chat_notebook.set_current_page(0)
			elif event.state & gtk.gdk.SHIFT_MASK:
				conversation_textview = self.xmls[jid].\
					get_widget('conversation_textview')
				rect = conversation_textview.get_visible_rect()
				iter = conversation_textview.get_iter_at_location(rect.x, rect.y)
				conversation_textview.scroll_to_iter(iter, 0.1, True, 0, 1)
		elif event.keyval == gtk.keysyms.Tab and \
			(event.state & gtk.gdk.CONTROL_MASK): # CTRL + TAB
			current = self.chat_notebook.get_current_page()
			if current < (self.chat_notebook.get_n_pages()-1):
				self.chat_notebook.set_current_page(current+1)
			else:
				self.chat_notebook.set_current_page(0)
		elif (event.state & gtk.gdk.CONTROL_MASK) or (event.keyval ==\
			gtk.keysyms.Control_L) or (event.keyval == gtk.keysyms.Control_R):
			# we pressed a control key or ctrl+sth : we don't block the event
			# in order to let ctrl+c do its work
			pass
		else: # it's a normal key press make sure message_textview has focus
			message_textview = self.xmls[jid].get_widget('message_textview')
			if not message_textview.is_focus():
				message_textview.grab_focus()

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
		self.plugin.systray.remove_jid(jid, self.account)
		showOffline = self.plugin.config['showoffline']
		if (user.show == 'offline' or user.show == 'error') and \
			not showOffline:
			if len(self.plugin.roster.contacts[self.account][jid]) == 1:
				self.plugin.roster.remove_user(user, self.account)

	def on_conversation_vadjustment_value_changed(self, widget):
		jid = self.get_active_jid()
		if not self.nb_unread[jid]:
			return
		conversation_textview = self.xmls[jid].get_widget('conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		end_iter = conversation_buffer.get_end_iter()
		end_rect = conversation_textview.get_iter_location(end_iter)
		visible_rect = conversation_textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height) and \
			self.window.is_active():
			#we are at the end
			self.nb_unread[jid] = 0
			self.redraw_tab(jid)
			self.show_title()
			self.plugin.systray.remove_jid(jid, self.account)
	
	def on_conversation_textview_motion_notify_event(self, widget, event):
		"""change the cursor to a hand when we are on a mail or an url"""
		x, y, spam = widget.window.get_pointer()
		x, y = widget.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, x, y)
		tags = widget.get_iter_at_location(x, y).get_tags()
		if self.change_cursor:
			widget.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(\
				gtk.gdk.Cursor(gtk.gdk.XTERM))
			self.change_cursor = None
		for tag in tags:
			if tag == widget.get_buffer().get_tag_table().lookup('url') or \
				tag == widget.get_buffer().get_tag_table().lookup('mail'):
				widget.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(\
					gtk.gdk.Cursor(gtk.gdk.HAND2))
				self.change_cursor = tag
		return False
			
	def on_conversation_textview_button_press_event(self, widget, event):
		# Do not open the standard popup menu, so we block right button click
		# on a taged text
		if event.button == 3:
			win = widget.get_window(gtk.TEXT_WINDOW_TEXT)
			x, y = widget.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,\
				int(event.x), int(event.y))
			iter = widget.get_iter_at_location(x, y)
			tags = iter.get_tags()
			if tags:
				return True
	
	def print_time_timeout(self, jid):
		if not jid in self.xmls.keys():
			return 0
		if self.plugin.config['print_time'] == 'sometimes':
			conversation_textview = self.xmls[jid].\
				get_widget('conversation_textview')
			conversation_buffer = conversation_textview.get_buffer()
			end_iter = conversation_buffer.get_end_iter()
			tim = time.localtime()
			tim_format = time.strftime('%H:%M', tim)
			conversation_buffer.insert_with_tags_by_name(end_iter, tim_format + \
				'\n', 'time_sometimes')
			#scroll to the end of the textview
			end_rect = conversation_textview.get_iter_location(end_iter)
			visible_rect = conversation_textview.get_visible_rect()
			if end_rect.y <= (visible_rect.y + visible_rect.height):
				#we are at the end
				conversation_textview.scroll_to_mark(conversation_buffer.\
					get_mark('end'), 0.1, 0, 0, 0)
			return 1
		if self.print_time_timeout_id.has_key(jid):
			del self.print_time_timeout_id[jid]
		return 0

	def on_open_link_activated(self, widget, kind, text):
		self.plugin.launch_browser_mailer(kind, text)

	def on_copy_link_activated(self, widget, text):
		clip = gtk.clipboard_get()
		clip.set_text(text)

	def make_link_menu(self, event, kind, text):
		menu = gtk.Menu()
		if kind == 'mail':
			item = gtk.MenuItem(_('_Open email composer'))
		else:
			item = gtk.MenuItem(_('_Open link'))
		item.connect('activate', self.on_open_link_activated, kind, text)
		menu.append(item)
		if kind == 'mail':
			item = gtk.MenuItem(_('_Copy email address'))
		else: # It's an url
			item = gtk.MenuItem(_('_Copy link address'))
		item.connect('activate', self.on_copy_link_activated, text)
		menu.append(item)

		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def hyperlink_handler(self, texttag, widget, event, iter, kind):
		if event.type == gtk.gdk.BUTTON_RELEASE:
			begin_iter = iter.copy()
			#we get the begining of the tag
			while not begin_iter.begins_tag(texttag):
				begin_iter.backward_char()
			end_iter = iter.copy()
			#we get the end of the tag
			while not end_iter.ends_tag(texttag):
				end_iter.forward_char()
			word = begin_iter.get_text(end_iter)
			if event.button == 3:
				self.make_link_menu(event, kind, word)
			else:
				#we launch the correct application
				self.plugin.launch_browser_mailer(kind, word)

	def print_special_text(self, text, jid, other_tag):
		conversation_textview = self.xmls[jid].get_widget('conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		
		# make it CAPS (emoticons keys are all CAPS)
		possible_emot_ascii_caps = text.upper()
		if possible_emot_ascii_caps in self.plugin.emoticons.keys():
			#it's an emoticon
			emot_ascii = possible_emot_ascii_caps
			print 'emoticon:', emot_ascii
			end_iter = conversation_buffer.get_end_iter()
			conversation_buffer.insert_pixbuf(end_iter, \
				self.plugin.emoticons[emot_ascii])
			return
		elif text.startswith('mailto:'):
			#it's a mail
			tag = 'mail'
			print tag
		elif self.plugin.sth_at_sth_dot_sth_re.match(text): #returns match object
																			#or None
			#it's a mail
			tag = 'mail'
			print tag
		elif text.startswith('*') and text.endswith('*'):
			#it's a bold text
			tag = 'bold'
			text = text[1:-1] # remove * *
		elif text.startswith('/') and text.endswith('/'):
			#it's an italic text
			tag = 'italic'
			text = text[1:-1] # remove / /
			print tag
		elif text.startswith('_') and text.endswith('_'):
			#it's an underlined text
			tag = 'underline'
			text = text[1:-1] # remove _ _
			print tag
		else:
			#it's a url
			tag = 'url'
			print tag

		end_iter = conversation_buffer.get_end_iter()
		if tag in ['bold', 'italic', 'underline'] and other_tag:
			conversation_buffer.insert_with_tags_by_name(end_iter, text,\
				other_tag, tag)
		else:
			conversation_buffer.insert_with_tags_by_name(end_iter, text, tag)
		
	def print_conversation(self, text, jid, contact = '', tim = None):
		"""Print a line in the conversation :
		if contact is set to status : it's a status message
		if contact is set to another value : it's an outgoing message
		if contact is not set : it's an incomming message"""
		user = self.users[jid]
		conversation_textview = self.xmls[jid].get_widget('conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		print_all_special = False
		if not text:
			text = ''
		end_iter = conversation_buffer.get_end_iter()
		if self.plugin.config['print_time'] == 'always':
			if not tim:
				tim = time.localtime()
			tim_format = time.strftime("[%H:%M:%S]", tim)
			conversation_buffer.insert(end_iter, tim_format + ' ')
		
		otext = ''
		ttext = ''
		if contact == 'status':
			tag = 'status'
			ttext = text + '\n'
			print_all_special = True
		else:
			if contact:
				tag = 'outgoing'
				name = self.plugin.nicks[self.account] 
			else:
				tag = 'incoming'
				name = user.name
				self.last_message_time[jid] = time.time()
				
			if text.startswith('/me'):
				ttext = name + text[3:] + '\n'
				print_all_special = True
			else:
				ttext = '<' + name + '> '
				otext = text + '\n'
		#if it's a status we print special words
		if not print_all_special:
			conversation_buffer.insert_with_tags_by_name(end_iter, ttext, tag)
		else:
			otext = ttext

		start = 0
		end = 0
		index = 0
		
		if self.plugin.config['useemoticons']: # search for emoticons & urls
			my_re = sre.compile(self.plugin.emot_and_basic_pattern, sre.IGNORECASE)
			iterator = my_re.finditer(otext)
		else: # search for just urls
			my_re = sre.compile(self.plugin.basic_pattern, sre.IGNORECASE)
			iterator = my_re.finditer(otext)
		for match in iterator:
			start, end = match.span()
			special_text = otext[start:end]
			if start != 0:
				text_before_special_text = otext[index:start]
				end_iter = conversation_buffer.get_end_iter()
				if print_all_special:
					conversation_buffer.insert_with_tags_by_name(end_iter, \
						text_before_special_text, tag)
				else:
					conversation_buffer.insert(end_iter, text_before_special_text)
			if print_all_special:
				self.print_special_text(special_text, jid, tag)
			else:
				self.print_special_text(special_text, jid, '')
			index = end # update index

		#add the rest in the index and after
		end_iter = conversation_buffer.get_end_iter()
		if print_all_special:
			conversation_buffer.insert_with_tags_by_name(end_iter, \
				otext[index:], tag)
		else:
			conversation_buffer.insert(end_iter, otext[index:])
		
		#scroll to the end of the textview
		end_rect = conversation_textview.get_iter_location(end_iter)
		visible_rect = conversation_textview.get_visible_rect()
		end = False
		if end_rect.y <= (visible_rect.y + visible_rect.height) or \
			(contact and contact != 'status'):
			#we are at the end or we are sending something
			end = True
			conversation_textview.scroll_to_mark(conversation_buffer.\
				get_mark('end'), 0.1, 0, 0, 0)
		if ((jid != self.get_active_jid()) or (not self.window.is_active()) or \
			(not end)) and contact == '':
			self.nb_unread[jid] += 1
			self.redraw_tab(jid)
			self.show_title()
