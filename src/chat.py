##	chat.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
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
import math
import os

import dialogs
import history_window
import gtkgui_helpers
import tooltips
import conversation_textview
import message_textview

try:
	import gtkspell
	HAS_GTK_SPELL = True
except:
	HAS_GTK_SPELL = False

from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class Chat:
	'''Class for chat/groupchat windows'''
	def __init__(self, account, widget_name):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, widget_name, APP)
		self.window = self.xml.get_widget(widget_name)

		self.widget_name = widget_name

		self.account = account
		self.xmls = {}
		self.conversation_textviews = {} # holds per jid conversation textview
		self.message_textviews = {} # holds per jid message (where we write) textview
		self.nb_unread = {}
		self.print_time_timeout_id = {}
		self.names = {} # what is printed in the tab (eg. contact.name)
		self.childs = {} # holds the contents for every tab (VBox)

		# the following vars are used to keep history of user's messages
		self.sent_history = {}
		self.sent_history_pos = {}
		self.typing_new = {}
		self.orig_msg = {}

		# alignment before notebook (to control top padding for when showing tabs)
		self.alignment = self.xml.get_widget('alignment')
		
		# notebook customizations
		self.notebook = self.xml.get_widget('chat_notebook')
		# Remove the page that is in glade
		self.notebook.remove_page(0)
		pref_pos = gajim.config.get('tabs_position')
		if pref_pos != 'top':
			if pref_pos == 'bottom':
				nb_pos = gtk.POS_BOTTOM
			elif pref_pos == 'left':
				nb_pos = gtk.POS_LEFT
			elif pref_pos == 'right':
				nb_pos = gtk.POS_RIGHT
			else:
				nb_pos = gtk.POS_TOP
		else:
			nb_pos = gtk.POS_TOP
		self.notebook.set_tab_pos(nb_pos)
		if gajim.config.get('tabs_always_visible'):
			self.notebook.set_show_tabs(True)
			self.alignment.set_property('top-padding', 2)
		else:
			self.notebook.set_show_tabs(False)
		self.notebook.set_show_border(gajim.config.get('tabs_border'))

		if gajim.config.get('useemoticons'):
			self.emoticons_menu = self.prepare_emoticons_menu()

		# muc attention states (when we are mentioned in a muc)
		# if the room jid is in the list, the room has mentioned us
		self.muc_attentions = []

	def toggle_emoticons(self):
		'''hide show emoticons_button and make sure emoticons_menu is always there
		when needed'''
		if gajim.config.get('useemoticons'):
			self.emoticons_menu = self.prepare_emoticons_menu()
		
		for jid in self.xmls:
			emoticons_button = self.xmls[jid].get_widget('emoticons_button')
			if gajim.config.get('useemoticons'):
				emoticons_button.show()
				emoticons_button.set_no_show_all(False)
			else:
				emoticons_button.hide()
				emoticons_button.set_no_show_all(True)

	def update_font(self):
		font = pango.FontDescription(gajim.config.get('conversation_font'))
		for jid in self.xmls:
			self.conversation_textviews[jid].modify_font(font)
			msg_textview = self.message_textviews[jid]
			msg_textview.modify_font(font)

	def update_tags(self):
		for jid in self.conversation_textviews:
			self.conversation_textviews[jid].update_tags()

	def update_print_time(self):
		if gajim.config.get('print_time') != 'sometimes':
			list_jid = self.print_time_timeout_id.keys()
			for jid in list_jid:
				gobject.source_remove(self.print_time_timeout_id[jid])
				del self.print_time_timeout_id[jid]
		else:
			for jid in self.xmls:
				if not self.print_time_timeout_id.has_key(jid):
					self.print_time_timeout(jid)
					self.print_time_timeout_id[jid] = gobject.timeout_add(300000,
						self.print_time_timeout, jid)

	def print_time_timeout(self, jid):
		if not jid in self.xmls.keys():
			return False
		if gajim.config.get('print_time') == 'sometimes':
			conv_textview = self.conversation_textviews[jid]
			buffer = conv_textview.get_buffer()
			end_iter = buffer.get_end_iter()
			tim = time.localtime()
			tim_format = time.strftime('%H:%M', tim)
			buffer.insert_with_tags_by_name(end_iter, '\n' + tim_format,
				'time_sometimes')
			# scroll to the end of the textview
			if conv_textview.at_the_end():
				# we are at the end
				conv_textview.scroll_to_end()
			return True # loop again
		if self.print_time_timeout_id.has_key(jid):
			del self.print_time_timeout_id[jid]
		return False

	def show_title(self, urgent = True):
		'''redraw the window's title'''
		unread = 0
		for jid in self.nb_unread:
			unread += self.nb_unread[jid]
		start = ''
		if unread > 1:
			start = '[' + unicode(unread) + '] '
		elif unread == 1:
			start = '* '
		if len(self.xmls) > 1: # if more than one tab in the same window
			if self.widget_name == 'tabbed_chat_window':
				add = _('Chat')
			elif self.widget_name == 'groupchat_window':
				add = _('Group Chat')
		elif len(self.xmls) == 1: # just one tab
			if self.widget_name == 'tabbed_chat_window':
				c = gajim.contacts.get_first_contact_from_jid(self.account, jid)
				if c is None:
					add = ''
				else:
					add = c.name
			elif self.widget_name == 'groupchat_window':
				name = gajim.get_nick_from_jid(jid)
				add = name

		title = start + add
		if len(gajim.connections) >= 2: # if we have 2 or more accounts
			title += ' (' + _('account: ') + self.account + ')'

		self.window.set_title(title)
		if urgent:
			gtkgui_helpers.set_unset_urgency_hint(self.window, unread)

	def redraw_tab(self, jid, chatstate = None):
		'''redraw the label of the tab
		if chatstate is given that means we have HE SENT US a chatstate'''
		# Update status images
		self.set_state_image(jid)
			
		unread = ''
		num_unread = 0
		child = self.childs[jid]
		hb = self.notebook.get_tab_label(child).get_children()[0]
		if self.widget_name == 'tabbed_chat_window':
			nickname = hb.get_children()[1]
			close_button = hb.get_children()[2]

			num_unread = self.nb_unread[jid]
			if num_unread == 1 and not gajim.config.get('show_unread_tab_icon'):
				unread = '*'
			elif num_unread > 1:
				unread = '[' + unicode(num_unread) + ']'

			# Draw tab label using chatstate 
			theme = gajim.config.get('roster_theme')
			color = None
			if chatstate is not None:
				if chatstate == 'composing':
					color = gajim.config.get_per('themes', theme,
						'state_composing_color')
				elif chatstate == 'inactive':
					color = gajim.config.get_per('themes', theme,
						'state_inactive_color')
				elif chatstate == 'gone':
					color = gajim.config.get_per('themes', theme, 'state_gone_color')
				elif chatstate == 'paused':
					color = gajim.config.get_per('themes', theme, 'state_paused_color')
				else:
					color = gajim.config.get_per('themes', theme, 'state_active_color')
			if color:
				color = gtk.gdk.colormap_get_system().alloc_color(color)
				# We set the color for when it's the current tab or not
				nickname.modify_fg(gtk.STATE_NORMAL, color)
				if chatstate in ('inactive', 'gone'):
					# Adjust color to be lighter against the darker inactive
					# background
					p = 0.4
					mask = 0
					color.red = int((color.red * p) + (mask * (1 - p)))
					color.green = int((color.green * p) + (mask * (1 - p)))
					color.blue = int((color.blue * p) + (mask * (1 - p)))
				nickname.modify_fg(gtk.STATE_ACTIVE, color)
		elif self.widget_name == 'groupchat_window':
			nickname = hb.get_children()[0]
			close_button = hb.get_children()[1]

			has_focus = self.window.get_property('has-toplevel-focus')
			current_tab = (self.notebook.page_num(child) == self.notebook.get_current_page())
			color = None
			theme = gajim.config.get('roster_theme')
			if chatstate == 'attention' and (not has_focus or not current_tab):
				if jid not in self.muc_attentions:
					self.muc_attentions.append(jid)
				color = gajim.config.get_per('themes', theme, 'state_muc_directed_msg')
			elif chatstate:
				if chatstate == 'active' or (current_tab and has_focus):
					if jid in self.muc_attentions:
						self.muc_attentions.remove(jid)
					color = gajim.config.get_per('themes', theme, 'state_active_color')
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

		if gajim.config.get('tabs_close_button'):
			close_button.show()
		else:
			close_button.hide()

		nickname.set_max_width_chars(10)
		lbl = self.names[jid]
		if num_unread: # if unread, text in the label becomes bold
			lbl = '<b>' + unread + lbl + '</b>'
		nickname.set_markup(lbl)

	def get_message_type(self, jid):
		if self.widget_name == 'groupchat_window':
			return 'gc'
		if gajim.contacts.is_pm_from_jid(self.account, jid):
			return 'pm'
		return 'chat'

	def get_nth_jid(self, page_number = None):
		notebook = self.notebook
		if page_number == None:
			page_number = notebook.get_current_page()
		nth_child = notebook.get_nth_page(page_number)
		nth_jid = ''
		for jid in self.xmls:
			if self.childs[jid] == nth_child:
				nth_jid = jid
				break
		return nth_jid

	def move_to_next_unread_tab(self, forward):
		ind = self.notebook.get_current_page()
		current = ind
		found = False
		# loop until finding an unread tab or having done a complete cycle
		while True: 
			if forward == True: # look for the first unread tab on the right
				ind = ind + 1
				if ind >= self.notebook.get_n_pages():
					ind = 0
			else: # look for the first unread tab on the right
				ind = ind - 1
				if ind < 0:
					ind = self.notebook.get_n_pages() - 1
			if ind == current:
				break # a complete cycle without finding an unread tab 
			jid = self.get_nth_jid(ind)
			if self.nb_unread[jid] > 0:
				found = True
				break # found
		if found:
			self.notebook.set_current_page(ind)
		else: # not found
			if forward: # CTRL + TAB
				if current < (self.notebook.get_n_pages() - 1):
					self.notebook.next_page()
				else: # traverse for ever (eg. don't stop at last tab)
					self.notebook.set_current_page(0)
			else: # CTRL + SHIFT + TAB
				if current > 0:
					self.notebook.prev_page()
				else: # traverse for ever (eg. don't stop at first tab)
					self.notebook.set_current_page(
						self.notebook.get_n_pages() - 1)
		
	def on_window_destroy(self, widget, kind): #kind is 'chats' or 'gc'
		'''clean gajim.interface.instances[self.account][kind]'''
		for jid in self.xmls:
			windows = gajim.interface.instances[self.account][kind]
			if kind == 'chats':
				# send 'gone' chatstate to every tabbed chat tab
				windows[jid].send_chatstate('gone', jid)
				gobject.source_remove(self.possible_paused_timeout_id[jid])
				gobject.source_remove(self.possible_inactive_timeout_id[jid])
			if gajim.interface.systray_enabled and self.nb_unread[jid] > 0:
				gajim.interface.systray.remove_jid(jid, self.account,
					self.get_message_type(jid))
			del windows[jid]
			if self.print_time_timeout_id.has_key(jid):
				gobject.source_remove(self.print_time_timeout_id[jid])
		if windows.has_key('tabbed'):
			del windows['tabbed']

	def get_active_jid(self):
		return self.get_nth_jid()

	def on_close_button_clicked(self, button, jid):
		'''When close button is pressed: close a tab'''
		self.remove_tab(jid)

	def on_history_menuitem_clicked(self, widget = None, jid = None):
		'''When history menuitem is pressed: call history window'''
		if jid is None: # None when viewing room and tc history
			jid = self.get_active_jid()
		if gajim.interface.instances['logs'].has_key(jid):
			gajim.interface.instances['logs'][jid].window.present()
		else:
			gajim.interface.instances['logs'][jid] = history_window.HistoryWindow(
				jid, self.account)

	def on_chat_window_focus_in_event(self, widget, event):
		'''When window gets focus'''
		jid = self.get_active_jid()
		
		textview = self.conversation_textviews[jid]
		if textview.at_the_end():
			#we are at the end
			if self.nb_unread[jid] > 0:
				self.nb_unread[jid] = 0 + self.get_specific_unread(jid)
				self.show_title()
				if gajim.interface.systray_enabled:
					gajim.interface.systray.remove_jid(jid, self.account,
						self.get_message_type(jid))
		
		'''TC/GC window received focus, so if we had urgency REMOVE IT
		NOTE: we do not have to read the message (it maybe in a bg tab)
		to remove urgency hint so this functions does that'''
		if gtk.gtk_version >= (2, 8, 0) and gtk.pygtk_version >= (2, 8, 0):
			if widget.props.urgency_hint:
				widget.props.urgency_hint = False
		# Undo "unread" state display, etc.
		if self.widget_name == 'groupchat_window':
			self.redraw_tab(jid, 'active')
		else:
			# NOTE: we do not send any chatstate to preserve inactive, gone, etc.
			self.redraw_tab(jid)
	
	def on_compact_view_menuitem_activate(self, widget):
		isactive = widget.get_active()
		self.set_compact_view(isactive)

	def on_actions_button_clicked(self, widget):
		'''popup action menu'''
		#FIXME: BUG http://bugs.gnome.org/show_bug.cgi?id=316786
		self.button_clicked = widget
		
		menu = self.prepare_context_menu()
		menu.show_all()
		menu.popup(None, None, self.position_menu_under_button, 1, 0)

	def on_emoticons_button_clicked(self, widget):
		'''popup emoticons menu'''
		#FIXME: BUG http://bugs.gnome.org/show_bug.cgi?id=316786
		self.button_clicked = widget
		self.emoticons_menu.popup(None, None, self.position_menu_under_button, 1, 0)

	def position_menu_under_button(self, menu):
		#FIXME: BUG http://bugs.gnome.org/show_bug.cgi?id=316786
		# pass btn instance when this bug is over
		button = self.button_clicked
		# here I get the coordinates of the button relative to
		# window (self.window)
		button_x, button_y = button.allocation.x, button.allocation.y
		
		# now convert them to X11-relative
		window_x, window_y = self.window.window.get_origin()
		x = window_x + button_x
		y = window_y + button_y

		menu_width, menu_height = menu.size_request()

		## should we pop down or up?
		if (y + button.allocation.height + menu_height
		    < gtk.gdk.screen_height()):
			# now move the menu below the button
			y += button.allocation.height
		else:
			# now move the menu above the button
			y -= menu_height


		# push_in is True so all the menuitems are always inside screen
		push_in = True
		return (x, y, push_in)

	def remove_possible_switch_to_menuitems(self, menu):
		''' remove duplicate 'Switch to' if they exist and return clean menu'''
		childs = menu.get_children()

		if self.widget_name == 'tabbed_chat_window':
			jid = self.get_active_jid()
			c = gajim.contacts.get_first_contact_from_jid(self.account, jid)
			if _('not in the roster') in c.groups: # for add_to_roster_menuitem
				childs[5].show()
				childs[5].set_no_show_all(False)
			else:
				childs[5].hide()
				childs[5].set_no_show_all(True)
			
			start_removing_from = 6 # this is from the seperator and after
			
		else:
			start_removing_from = 7 # # this is from the seperator and after
				
		for child in childs[start_removing_from:]:
			menu.remove(child)

		return menu
	
	def prepare_context_menu(self):
		'''sets compact view menuitem active state
		sets active and sensitivity state for toggle_gpg_menuitem
		and remove possible 'Switch to' menuitems'''
		if self.widget_name == 'groupchat_window':
			menu = self.gc_popup_menu
			childs = menu.get_children()
			# compact_view_menuitem
			childs[5].set_active(self.compact_view_current_state)
		elif self.widget_name == 'tabbed_chat_window':
			menu = self.tabbed_chat_popup_menu
			childs = menu.get_children()
			# check if gpg capabitlies or else make gpg toggle insensitive
			jid = self.get_active_jid()
			gpg_btn = self.xmls[jid].get_widget('gpg_togglebutton')
			isactive = gpg_btn.get_active()
			issensitive = gpg_btn.get_property('sensitive')
			childs[3].set_active(isactive)
			childs[3].set_property('sensitive', issensitive)
			# If we don't have resource, we can't do file transfert
			c = gajim.contacts.get_first_contact_from_jid(self.account, jid)
			if not c.resource:
				childs[2].set_sensitive(False)
			else:
				childs[2].set_sensitive(True)
			# compact_view_menuitem
			childs[4].set_active(self.compact_view_current_state)
		menu = self.remove_possible_switch_to_menuitems(menu)
		
		return menu

	def prepare_emoticons_menu(self):
		menu = gtk.Menu()
	
		def append_emoticon(w, d):
			jid = self.get_active_jid()
			message_textview = self.message_textviews[jid]
			buffer = message_textview.get_buffer()
			if buffer.get_char_count():
				buffer.insert_at_cursor(' %s ' % d)
			else: # we are the beginning of buffer
				buffer.insert_at_cursor('%s ' % d)
			message_textview.grab_focus()
	
		counter = 0
		# Calculate the side lenght of the popup to make it a square
		size = int(round(math.sqrt(len(gajim.interface.emoticons_images))))
		for image in gajim.interface.emoticons_images:
			item = gtk.MenuItem()
			img = gtk.Image()
			if type(image[1]) == gtk.gdk.PixbufAnimation:
				img.set_from_animation(image[1])
			else:
				img.set_from_pixbuf(image[1])
			item.add(img)
			item.connect('activate', append_emoticon, image[0])
			#FIXME: add tooltip with ascii
			menu.attach(item,
					counter % size, counter % size + 1,
					counter / size, counter / size + 1)
			counter += 1
		menu.show_all()
		return menu

	def popup_menu(self, event):
		menu = self.prepare_context_menu()
		# common menuitems (tab switches)
		if len(self.xmls) > 1: # if there is more than one tab
			menu.append(gtk.SeparatorMenuItem()) # seperator
			for jid in self.xmls:
				if jid != self.get_active_jid():
					item = gtk.ImageMenuItem(_('Switch to %s') % self.names[jid])
					img = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
						gtk.ICON_SIZE_MENU)
					item.set_image(img)
					item.connect('activate', lambda obj, jid:self.set_active_tab(
						jid), jid)
					menu.append(item)

		# show the menu
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()

	def on_banner_eventbox_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3: # right click
			self.popup_menu(event)

	def on_chat_notebook_switch_page(self, notebook, page, page_num):
		# get the index of the page and then the page that we're leaving
		old_no = notebook.get_current_page()
		old_child = notebook.get_nth_page(old_no)
		
		new_child = notebook.get_nth_page(page_num)
		
		old_jid = ''
		new_jid = ''
		for jid in self.xmls:
			if self.childs[jid] == new_child:
				new_jid = jid
			elif self.childs[jid] == old_child:
				old_jid = jid
			
			if old_jid != '' and new_jid != '': # we found both jids
				break # so stop looping
		
		if self.widget_name == 'tabbed_chat_window':
			# send chatstate inactive to the one we're leaving
			# and active to the one we visit
			if old_jid != '':
				self.send_chatstate('inactive', old_jid)
			self.send_chatstate('active', new_jid)

		conv_textview = self.conversation_textviews[new_jid]
		if conv_textview.at_the_end():
			#we are at the end
			if self.nb_unread[new_jid] > 0:
				self.nb_unread[new_jid] = 0 + self.get_specific_unread(new_jid)
				self.redraw_tab(new_jid)
				self.show_title()
				if gajim.interface.systray_enabled:
					gajim.interface.systray.remove_jid(new_jid, self.account,
						self.get_message_type(new_jid))

		conv_textview.grab_focus()

	def set_active_tab(self, jid):
		self.notebook.set_current_page(self.notebook.page_num(self.childs[jid]))

	def remove_tab(self, jid, kind): #kind is 'chats' or 'gc'
		if len(self.xmls) == 1: # only one tab when we asked to remove
			# so destroy window

			# we check and possibly save positions here, because Ctrl+W, Escape
			# etc.. call remove_tab so similar code in delete_event callbacks
			# is not enough
			if gajim.config.get('saveposition'):
				if kind == 'chats':
					x, y = self.window.get_position()
					gajim.config.set('chat-x-position', x)
					gajim.config.set('chat-y-position', y)
					width, height = self.window.get_size()
					gajim.config.set('chat-width', width)
					gajim.config.set('chat-height', height)
				elif kind == 'gc':
					gajim.config.set('gc-hpaned-position', self.hpaned_position)
					x, y = self.window.get_position()
					gajim.config.set('gc-x-position', x)
					gajim.config.set('gc-y-position', y)
					width, height = self.window.get_size()
					gajim.config.set('gc-width', width)
					gajim.config.set('gc-height', height)

			self.window.destroy()
		else:
			if self.nb_unread[jid] > 0:
				self.nb_unread[jid] = 0
				if gajim.interface.systray_enabled:
					gajim.interface.systray.remove_jid(jid, self.account,
						self.get_message_type(jid))
			if self.print_time_timeout_id.has_key(jid):
				gobject.source_remove(self.print_time_timeout_id[jid])
				del self.print_time_timeout_id[jid]

			self.notebook.remove_page(self.notebook.page_num(self.childs[jid]))

		if gajim.interface.instances[self.account][kind].has_key(jid):
			del gajim.interface.instances[self.account][kind][jid]
		del self.nb_unread[jid]
		del gajim.last_message_time[self.account][jid]
		del self.xmls[jid]
		del self.childs[jid]
		del self.sent_history[jid]
		del self.sent_history_pos[jid]
		del self.typing_new[jid]
		del self.orig_msg[jid]

		if len(self.xmls) == 1: # we now have only one tab
			show_tabs_if_one_tab = gajim.config.get('tabs_always_visible')
			self.notebook.set_show_tabs(show_tabs_if_one_tab)
			
			if not show_tabs_if_one_tab:
				self.alignment.set_property('top-padding', 0)
			
			self.show_title()

	def bring_scroll_to_end(self, textview, diff_y = 0):
		''' scrolls to the end of textview if end is not visible '''
		buffer = textview.get_buffer()
		end_iter = buffer.get_end_iter()
		end_rect = textview.get_iter_location(end_iter)
		visible_rect = textview.get_visible_rect()
		# scroll only if expected end is not visible
		if end_rect.y >= (visible_rect.y + visible_rect.height + diff_y):
			gobject.idle_add(self.scroll_to_end_iter, textview)

	def scroll_to_end_iter(self, textview):
		buffer = textview.get_buffer()
		end_iter = buffer.get_end_iter()
		textview.scroll_to_iter(end_iter, 0, False, 1, 1)
		return False

	def size_request(self, msg_textview , requisition, xml_top):
		''' When message_textview changes its size. If the new height
		will enlarge the window, enable the scrollbar automatic policy
		Also enable scrollbar automatic policy for horizontal scrollbar
		if message we have in message_textview is too big'''
		if msg_textview.window is None:
			return
		message_scrolledwindow = xml_top.get_widget('message_scrolledwindow')

		conversation_scrolledwindow = xml_top.get_widget(
			'conversation_scrolledwindow')
		conv_textview = conversation_scrolledwindow.get_children()[0]

		min_height = conversation_scrolledwindow.get_property('height-request')
		conversation_height = conv_textview.window.get_size()[1]
		message_height = msg_textview.window.get_size()[1]
		message_width = msg_textview.window.get_size()[0]
		# new tab is not exposed yet
		if conversation_height < 2:
			return

		if conversation_height < min_height:
			min_height = conversation_height

		# we don't want to always resize in height the message_textview
		# so we have minimum on conversation_textview's scrolled window
		# but we also want to avoid window resizing so if we reach that 
		# minimum for conversation_textview and maximum for message_textview
		# we set to automatic the scrollbar policy
		diff_y =  message_height - requisition.height
		if diff_y != 0:
			if conversation_height + diff_y < min_height:
				if message_height + conversation_height - min_height > min_height:
					message_scrolledwindow.set_property('vscrollbar-policy', 
						gtk.POLICY_AUTOMATIC)
					message_scrolledwindow.set_property('height-request', 
						message_height + conversation_height - min_height)
					self.bring_scroll_to_end(msg_textview)
			else:
				message_scrolledwindow.set_property('vscrollbar-policy', 
					gtk.POLICY_NEVER)
				message_scrolledwindow.set_property('height-request', -1)

		conv_textview.bring_scroll_to_end(diff_y - 18)
		
		# enable scrollbar automatic policy for horizontal scrollbar
		# if message we have in message_textview is too big
		if requisition.width > message_width:
			message_scrolledwindow.set_property('hscrollbar-policy', 
				gtk.POLICY_AUTOMATIC)
		else:
			message_scrolledwindow.set_property('hscrollbar-policy', 
				gtk.POLICY_NEVER)

		return True

	def on_tab_eventbox_button_press_event(self, widget, event, child):
		if event.button == 3:
			n = self.notebook.page_num(child)
			self.notebook.set_current_page(n)
			self.popup_menu(event)

	def new_tab(self, jid):
		#FIXME: text formating buttons will be hidden in 0.8 release
		for w in ('bold_togglebutton', 'italic_togglebutton',
			'underline_togglebutton'):
			self.xmls[jid].get_widget(w).set_no_show_all(True)

		# add ConversationTextView to UI and connect signals
		conv_textview = self.conversation_textviews[jid] = \
			conversation_textview.ConversationTextview(self.account)
		conv_textview.show_all()
		conversation_scrolledwindow = self.xmls[jid].get_widget(
			'conversation_scrolledwindow')
		conversation_scrolledwindow.add(conv_textview)
		conv_textview.connect('key_press_event', self.on_conversation_textview_key_press_event)
		
		# add MessageTextView to UI and connect signals
		message_scrolledwindow = self.xmls[jid].get_widget(
			'message_scrolledwindow')
		msg_textview = self.message_textviews[jid] = \
			message_textview.MessageTextView()
		msg_textview.connect('mykeypress',
			self.on_message_textview_mykeypress_event)
		message_scrolledwindow.add(msg_textview)
		msg_textview.connect('key_press_event',
			self.on_message_textview_key_press_event)
		
		self.set_compact_view(self.always_compact_view)
		self.nb_unread[jid] = 0
		gajim.last_message_time[self.account][jid] = 0
		font = pango.FontDescription(gajim.config.get('conversation_font'))
		
		if gajim.config.get('use_speller') and HAS_GTK_SPELL:
			try:
				gtkspell.Spell(msg_textview)
			except gobject.GError, msg:
				#FIXME: add a ui for this use spell.set_language()
				dialogs.ErrorDialog(unicode(msg), _('If that is not your language for which you want to highlight misspelled words, then please set your $LANG as appropriate. Eg. for French do export LANG=fr_FR or export LANG=fr_FR.UTF-8 in ~/.bash_profile or to make it global in /etc/profile.\n\nHighlighting misspelled words feature will not be used')).get_response()
				gajim.config.set('use_speller', False)
		
		emoticons_button = self.xmls[jid].get_widget('emoticons_button')
		# set image no matter if user wants at this time emoticons or not
		# (so toggle works ok)
		img = self.xmls[jid].get_widget('emoticons_button_image')
		img.set_from_file(os.path.join(gajim.DATA_DIR, 'emoticons', 'smile.png'))
		if gajim.config.get('useemoticons'):
			emoticons_button.show()
			emoticons_button.set_no_show_all(False)
		else:
			emoticons_button.hide()
			emoticons_button.set_no_show_all(True)

		conv_textview.modify_font(font)
		conv_buffer = conv_textview.get_buffer()
		end_iter = conv_buffer.get_end_iter()

		self.xmls[jid].signal_autoconnect(self)
		conversation_scrolledwindow.get_vadjustment().connect('value-changed',
			self.on_conversation_vadjustment_value_changed)

		if len(self.xmls) > 1:
			self.notebook.set_show_tabs(True)
			self.alignment.set_property('top-padding', 2)

		if self.widget_name == 'tabbed_chat_window':
			xm = gtk.glade.XML(GTKGUI_GLADE, 'chats_eventbox', APP)
			tab_hbox = xm.get_widget('chats_eventbox')
		elif self.widget_name == 'groupchat_window':
			xm = gtk.glade.XML(GTKGUI_GLADE, 'gc_eventbox', APP)
			tab_hbox = xm.get_widget('gc_eventbox')

		child = self.childs[jid]

		xm.signal_connect('on_close_button_clicked',
			self.on_close_button_clicked, jid)
		xm.signal_connect('on_tab_eventbox_button_press_event',
			self.on_tab_eventbox_button_press_event, child)

		self.notebook.append_page(child, tab_hbox)
		
		msg_textview.modify_font(font)
		msg_textview.connect('size-request', self.size_request, self.xmls[jid])
		# init new sent history for this conversation
		self.sent_history[jid] = []
		self.sent_history_pos[jid] = 0
		self.typing_new[jid] = True
		self.orig_msg[jid] = ''

		self.show_title()

	def on_message_textview_key_press_event(self, widget, event):
		jid = self.get_active_jid()
		conv_textview = self.conversation_textviews[jid]
		
		if self.widget_name == 'groupchat_window':
			if event.keyval not in (gtk.keysyms.ISO_Left_Tab, gtk.keysyms.Tab):
				room_jid = self.get_active_jid()
				self.last_key_tabs[room_jid] = False
		
		if event.keyval == gtk.keysyms.Page_Down: # PAGE DOWN
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE DOWN
				self.notebook.emit('key_press_event', event)
			elif event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE DOWN
				conv_textview.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Page_Up: # PAGE UP
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE UP
				self.notebook.emit('key_press_event', event)
			elif event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE UP
				conv_textview.emit('key_press_event', event)
	
	def on_conversation_textview_key_press_event(self, widget, event):
		'''Do not block these events and send them to the notebook'''
		if event.state & gtk.gdk.CONTROL_MASK:
			if event.keyval == gtk.keysyms.Tab: # CTRL + TAB
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.ISO_Left_Tab: # CTRL + SHIFT + TAB
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.Page_Down: # CTRL + PAGE DOWN
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.Page_Up: # CTRL + PAGE UP
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.l or \
				event.keyval == gtk.keysyms.L: # CTRL + L
				jid = self.get_active_jid()
				conv_textview = self.conversation_textviews[jid]
				conv_textview.get_buffer().set_text('')
			elif event.keyval == gtk.keysyms.v: # CTRL + V
				jid = self.get_active_jid()
				msg_textview = self.message_textviews[jid]
				if not msg_textview.is_focus():
					msg_textview.grab_focus()
				msg_textview.emit('key_press_event', event)

	def on_chat_notebook_key_press_event(self, widget, event):
		st = '1234567890' # alt+1 means the first tab (tab 0)
		jid = self.get_active_jid()
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			if self.widget_name == 'tabbed_chat_window':
				self.remove_tab(jid)
		elif event.keyval == gtk.keysyms.F4 and \
			(event.state & gtk.gdk.CONTROL_MASK): # CTRL + F4
				self.remove_tab(jid)
		elif event.keyval == gtk.keysyms.w and \
			(event.state & gtk.gdk.CONTROL_MASK): # CTRL + W
				self.remove_tab(jid)
		elif event.string and event.string in st and \
			(event.state & gtk.gdk.MOD1_MASK): # alt + 1,2,3..
			self.notebook.set_current_page(st.index(event.string))
		elif event.keyval == gtk.keysyms.c and \
			(event.state & gtk.gdk.MOD1_MASK): # alt + C toggles compact view
			self.set_compact_view(not self.compact_view_current_state)
		elif event.keyval == gtk.keysyms.e and \
			(event.state & gtk.gdk.MOD1_MASK): # alt + E opens emoticons menu
			if gajim.config.get('useemoticons'):
				msg_tv = self.message_textviews[jid]
				def set_emoticons_menu_position(w, msg_tv = msg_tv):
					window = msg_tv.get_window(gtk.TEXT_WINDOW_WIDGET)
					# get the window position
					origin = window.get_origin()
					size = window.get_size()
					buf = msg_tv.get_buffer()
					# get the cursor position
					cursor = msg_tv.get_iter_location(buf.get_iter_at_mark(
						buf.get_insert()))
					cursor =  msg_tv.buffer_to_window_coords(gtk.TEXT_WINDOW_TEXT,
						cursor.x, cursor.y)
					x = origin[0] + cursor[0]
					y = origin[1] + size[1]
					menu_width, menu_height = self.emoticons_menu.size_request()
					#FIXME: get_line_count is not so good
					#get the iter of cursor, then tv.get_line_yrange
					# so we know in which y we are typing (not how many lines we have
					# then go show just above the current cursor line for up
					# or just below the current cursor line for down
					#TEST with having 3 lines and writing in the 2nd
					if y + menu_height > gtk.gdk.screen_height():
						# move menu just above cursor
						y -= menu_height + (msg_tv.allocation.height / buf.get_line_count())
					#else: # move menu just below cursor
					#	y -= (msg_tv.allocation.height / buf.get_line_count())
					return (x, y, True) # push_in True
				self.emoticons_menu.popup(None, None, set_emoticons_menu_position, 1, 0)
		elif event.keyval == gtk.keysyms.Page_Down:
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE DOWN
				conv_textview = self.conversation_textviews[jid]
				rect = conv_textview.get_visible_rect()
				iter = conv_textview.get_iter_at_location(rect.x,
					rect.y + rect.height)
				conv_textview.scroll_to_iter(iter, 0.1, True, 0, 0)
		elif event.keyval == gtk.keysyms.Page_Up: 
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE UP
				conv_textview = self.conversation_textviews[jid]
				rect = conv_textview.get_visible_rect()
				iter = conv_textview.get_iter_at_location(rect.x, rect.y)
				conv_textview.scroll_to_iter(iter, 0.1, True, 0, 1)
		elif event.keyval == gtk.keysyms.Up: 
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + UP
				conversation_scrolledwindow = self.xml.get_widget('conversation_scrolledwindow')
				conversation_scrolledwindow.emit('scroll-child',
					gtk.SCROLL_PAGE_BACKWARD, False)
		elif event.keyval == gtk.keysyms.ISO_Left_Tab: # SHIFT + TAB
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + SHIFT + TAB
				self.move_to_next_unread_tab(False)
		elif event.keyval == gtk.keysyms.Tab: # TAB
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + TAB
				self.move_to_next_unread_tab(True)
		elif (event.keyval == gtk.keysyms.l or event.keyval == gtk.keysyms.L) \
				and event.state & gtk.gdk.CONTROL_MASK: # CTRL + L
			conv_textview = self.conversation_textviews[jid]
			conv_textview.get_buffer().set_text('')
		elif event.keyval == gtk.keysyms.v and event.state & gtk.gdk.CONTROL_MASK:
			# CTRL + V
			msg_textview = self.message_textviews[jid]
			if not msg_textview.is_focus():
				msg_textview.grab_focus()
			msg_textview.emit('key_press_event', event)
		elif event.state & gtk.gdk.CONTROL_MASK or \
			  (event.keyval == gtk.keysyms.Control_L) or \
			  (event.keyval == gtk.keysyms.Control_R):
			# we pressed a control key or ctrl+sth: we don't block
			# the event in order to let ctrl+c (copy text) and
			# others do their default work
			pass
		else: # it's a normal key press make sure message_textview has focus
			msg_textview = self.message_textviews[jid]
			if msg_textview.get_property('sensitive'):
				if not msg_textview.is_focus():
					msg_textview.grab_focus()
				msg_textview.emit('key_press_event', event)

	def on_conversation_vadjustment_value_changed(self, widget):
		jid = self.get_active_jid()
		if not self.nb_unread[jid]:
			return
		conv_textview = self.conversation_textviews[jid]
		if conv_textview.at_the_end() and self.window.is_active():
			#we are at the end
			self.nb_unread[jid] = self.get_specific_unread(jid)
			self.redraw_tab(jid)
			self.show_title()
			if gajim.interface.systray_enabled:
				gajim.interface.systray.remove_jid(jid, self.account,
					self.get_message_type(jid))

	def clear(self, tv):
		buffer = tv.get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)

	def print_conversation_line(self, text, jid, kind, name, tim,
			other_tags_for_name = [], other_tags_for_time = [], 
			other_tags_for_text = [], count_as_new = True, subject = None):
		'''prints 'chat' type messages'''
		textview = self.conversation_textviews[jid]
		end = False
		if textview.at_the_end() or kind == 'outgoing':
			end = True
		textview.print_conversation_line(text, jid, kind, name, tim,
			other_tags_for_name, other_tags_for_time, other_tags_for_text, subject)

		if not count_as_new:
			return
		if kind == 'incoming_queue':
			gajim.last_message_time[self.account][jid] = time.time()
		urgent = True
		if (jid != self.get_active_jid() or \
		   not self.window.is_active() or \
		   not end) and kind in ('incoming', 'incoming_queue'):
			if self.widget_name == 'groupchat_window':
				if not self.needs_visual_notification(text, self.nicks[jid]):
					# Do not notify us for gc messages that are not for us
					urgent = False
					if not gajim.config.get('notify_on_all_muc_messages'):
						return
			self.nb_unread[jid] += 1
			if gajim.interface.systray_enabled and gajim.config.get(
				'trayicon_notification_on_new_messages'):
				gajim.interface.systray.add_jid(jid, self.account, self.get_message_type(jid))
			self.redraw_tab(jid)
			self.show_title(urgent)

	def save_sent_message(self, jid, message):
		#save the message, so user can scroll though the list with key up/down
		size = len(self.sent_history[jid])
		#we don't want size of the buffer to grow indefinately
		max_size = gajim.config.get('key_up_lines')
		if size >= max_size:
			for i in xrange(0, size - 1): 
				self.sent_history[jid][i] = self.sent_history[jid][i+1]
			self.sent_history[jid][max_size - 1] = message
		else:
			self.sent_history[jid].append(message)
			self.sent_history_pos[jid] = size + 1

		self.typing_new[jid] = True
		self.orig_msg[jid] = ''
	
	def sent_messages_scroll(self, jid, direction, conv_buf):
		size = len(self.sent_history[jid]) 
		if self.typing_new[jid]:
			#user was typing something and then went into history, so save
			#whatever is already typed
			start_iter = conv_buf.get_start_iter()
			end_iter = conv_buf.get_end_iter()
			self.orig_msg[jid] = conv_buf.get_text(start_iter, end_iter, 0).decode('utf-8')
			self.typing_new[jid] = False
		if direction == 'up':
			if self.sent_history_pos[jid] == 0:
				return
			self.sent_history_pos[jid] = self.sent_history_pos[jid] - 1
			conv_buf.set_text(self.sent_history[jid][self.sent_history_pos[jid]])

		elif direction == 'down':
			if self.sent_history_pos[jid] >= size - 1:
				conv_buf.set_text(self.orig_msg[jid]);
				self.typing_new[jid] = True
				self.sent_history_pos[jid] = size
				return

			self.sent_history_pos[jid] = self.sent_history_pos[jid] + 1
			conv_buf.set_text(self.sent_history[jid][self.sent_history_pos[jid]])

	def paint_banner(self, jid):
		theme = gajim.config.get('roster_theme')
		bgcolor = gajim.config.get_per('themes', theme, 'bannerbgcolor')
		textcolor = gajim.config.get_per('themes', theme, 'bannertextcolor')
		# the backgrounds are colored by using an eventbox by
		# setting the bg color of the eventbox and the fg of the name_label
		banner_eventbox = self.xmls[jid].get_widget('banner_eventbox')
		banner_name_label = self.xmls[jid].get_widget('banner_name_label')
		if bgcolor:
			banner_eventbox.modify_bg(gtk.STATE_NORMAL, 
				gtk.gdk.color_parse(bgcolor))
		else:
			banner_eventbox.modify_bg(gtk.STATE_NORMAL, None)
		if textcolor:
			banner_name_label.modify_fg(gtk.STATE_NORMAL,
				gtk.gdk.color_parse(textcolor))
		else:
			banner_name_label.modify_fg(gtk.STATE_NORMAL, None)

	def repaint_colored_widgets(self):
		'''Repaint widgets (banner) in the window/tab with theme color'''
		# iterate through tabs/windows and repaint
		for jid in self.xmls:
			self.paint_banner(jid)

	def set_compact_view(self, state):
		'''Toggle compact view. state is bool'''
		self.compact_view_current_state = state

		for jid in self.xmls:
			if self.widget_name == 'tabbed_chat_window':
				widgets = [
				self.xmls[jid].get_widget('banner_eventbox'),
				self.xmls[jid].get_widget('actions_hbox'),
				]
			elif self.widget_name == 'groupchat_window':
				widgets = [self.xmls[jid].get_widget('banner_eventbox'),
					self.xmls[jid].get_widget('gc_actions_hbox'),
					self.xmls[jid].get_widget('list_scrolledwindow'),
					 ]

			for widget in widgets:
				if state:
					widget.set_no_show_all(True)
					widget.hide()
				else:
					widget.set_no_show_all(False)
					widget.show_all()
			# make the last message visible, when changing to "full view"
			if not state:
				conv_textview = self.conversation_textviews[jid]
				gobject.idle_add(conv_textview.scroll_to_end_iter)
