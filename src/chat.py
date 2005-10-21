##	chat.py
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
import dialogs
import history_window
import gtkgui_helpers
import tooltips

try:
	import gtkspell
except:
	pass

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
		self.change_cursor = None
		self.xmls = {}
		self.tagIn = {} # holds tag for nick that talks to us
		self.tagOut = {} # holds tag for our nick
		self.tagStatus = {} # holds status messages
		self.nb_unread = {}
		self.last_time_printout = {}
		self.print_time_timeout_id = {}
		self.names = {} # what is printed in the tab (eg. contact.name)
		self.childs = {} # holds the contents for every tab (VBox)

		# the following vars are used to keep history of user's messages
		self.sent_history = {}
		self.sent_history_pos = {}
		self.typing_new = {}
		self.orig_msg = {}

		# notebook customizations
		self.notebook = self.xml.get_widget('chat_notebook')
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
		self.notebook.set_show_tabs(gajim.config.get('tabs_always_visible'))
		self.notebook.set_show_border(gajim.config.get('tabs_border'))

		# muc attention states (when we are mentioned in a muc)
		# if the room jid is in the list, the room has mentioned us
		self.muc_attentions = []
		self.line_tooltip = tooltips.BaseTooltip()

	def update_font(self):
		font = pango.FontDescription(gajim.config.get('conversation_font'))
		for jid in self.tagIn:
			conversation_textview = self.xmls[jid].get_widget(
				'conversation_textview')
			conversation_textview.modify_font(font)
			message_textview = self.xmls[jid].get_widget('message_textview')
			message_textview.modify_font(font)

	def update_tags(self):
		for jid in self.tagIn:
			self.tagIn[jid].set_property('foreground',
					gajim.config.get('inmsgcolor'))
			self.tagOut[jid].set_property('foreground',
					gajim.config.get('outmsgcolor'))
			self.tagStatus[jid].set_property('foreground',
					gajim.config.get('statusmsgcolor'))

	def update_print_time(self):
		if gajim.config.get('print_time') != 'sometimes':
			list_jid = self.print_time_timeout_id.keys()
			for jid in list_jid:
				gobject.source_remove(self.print_time_timeout_id[jid])
				del self.print_time_timeout_id[jid]
		else:
			for jid in self.xmls:
				if self.print_time_timeout_id.has_key(jid):
					continue
				self.print_time_timeout(jid)
				self.print_time_timeout_id[jid] = \
						gobject.timeout_add(300000,
							self.print_time_timeout,
							jid)

	def show_title(self, urgent = True):
		'''redraw the window's title'''
		unread = 0
		for jid in self.nb_unread:
			unread += self.nb_unread[jid]
		start = ""
		if unread > 1:
			start = '[' + unicode(unread) + '] '
		elif unread == 1:
			start = '* '
		chat = self.names[jid]
		if len(self.xmls) > 1: # if more than one tab in the same window
			if self.widget_name == 'tabbed_chat_window':
				add = _('Chat')
			elif self.widget_name == 'groupchat_window':
				add = _('Group Chat')
		elif len(self.xmls) == 1: # just one tab
			if self.widget_name == 'tabbed_chat_window':
				c = gajim.get_first_contact_instance_from_jid(self.account, jid)
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
			
		child = self.childs[jid]
		hb = self.notebook.get_tab_label(child).get_children()[0]
		if self.widget_name == 'tabbed_chat_window':
			nickname = hb.get_children()[1]
			close_button = hb.get_children()[2]

			unread = ''
			num_unread = self.nb_unread[jid]
			if num_unread == 1 and not gajim.config.get('show_unread_tab_icon'):
				unread = '* '
			elif num_unread > 1:
				unread = '[' + unicode(num_unread) + '] '

			# Draw tab label using chatstate 
			theme = gajim.config.get('roster_theme')
			color = None
			if unread and chatstate == 'active':
				color = gajim.config.get_per('themes', theme,
							     'state_unread_color')
			elif chatstate is not None:
				if chatstate == 'composing':
					color = gajim.config.get_per('themes', theme,
								     'state_composing_color')
				elif chatstate == 'inactive':
					color = gajim.config.get_per('themes', theme,
								     'state_inactive_color')
				elif chatstate == 'gone':
					color = gajim.config.get_per('themes', theme,
								     'state_gone_color')
				elif chatstate == 'paused':
					color = gajim.config.get_per('themes', theme,
								     'state_paused_color')
				elif unread and self.window.get_property('has-toplevel-focus'):
					color = gajim.config.get_per('themes', theme,
								     'state_active_color')
				elif unread:
					color = gajim.config.get_per('themes', theme,
								     'state_unread_color')
				else:
					color = gajim.config.get_per('themes', theme,
								     'state_active_color')
			if color:
				color = gtk.gdk.colormap_get_system().alloc_color(color)
				# We set the color for when it's the current tab or not
				nickname.modify_fg(gtk.STATE_NORMAL, color)
				if chatstate in ['inactive', 'gone']:
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

			unread = ''
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
		nickname.set_text(unread + self.names[jid])

	def get_message_type(self, jid):
		if self.widget_name == 'groupchat_window':
			return 'gc'
		if gajim.contacts[self.account].has_key(jid):
			return 'chat'
		return 'pm'

	def on_window_destroy(self, widget, kind): #kind is 'chats' or 'gc'
		'''clean gajim.interface.windows[self.account][kind]'''
		for jid in self.xmls:
			windows = gajim.interface.windows[self.account][kind]
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
		notebook = self.notebook
		active_child = notebook.get_nth_page(notebook.get_current_page())
		active_jid = ''
		for jid in self.xmls:
			if self.childs[jid] == active_child:
				active_jid = jid
				break
		return active_jid

	def on_close_button_clicked(self, button, jid):
		'''When close button is pressed: close a tab'''
		self.remove_tab(jid)

	def on_history_menuitem_clicked(self, widget = None, jid = None):
		'''When history menuitem is pressed: call history window'''
		if jid is None:
			jid = self.get_active_jid()
		if gajim.interface.windows['logs'].has_key(jid):
			gajim.interface.windows['logs'][jid].window.present()
		else:
			gajim.interface.windows['logs'][jid] = history_window.HistoryWindow(jid,
				self.account)

	def on_chat_window_focus_in_event(self, widget, event):
		'''When window gets focus'''
		jid = self.get_active_jid()
		
		textview = self.xmls[jid].get_widget('conversation_textview')
		buffer = textview.get_buffer()
		end_iter = buffer.get_end_iter()
		end_rect = textview.get_iter_location(end_iter)
		visible_rect = textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
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
		self.actions_button = widget
		
		menu = self.prepare_context_menu()
		menu.popup(None, None, self.position_actions_menu, 1, 0)
		menu.show_all()

	def position_actions_menu(self, menu):
		# here I get the coordinates of the button relative to
		# window (self.window)
		button_x, button_y = self.actions_button.allocation.x, self.actions_button.allocation.y
		
		# now convert them to X11-relative
		window_x, window_y = self.window.window.get_origin()
		x = window_x + button_x
		y = window_y + button_y
		
		# now move the menu below the button
		y += self.actions_button.allocation.height

		# push_in is True so all menu is always inside screen
		push_in = True
		return (x, y, push_in)

	def remove_possible_switch_to_menuitems(self, menu):
		''' remove duplicate 'Switch to' if they exist and return clean menu'''
		childs = menu.get_children()

		if self.widget_name == 'tabbed_chat_window':
			jid = self.get_active_jid()
			c = gajim.get_first_contact_instance_from_jid(self.account, jid)
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
			c = gajim.get_first_contact_instance_from_jid(self.account, jid)
			if not c.resource:
				childs[2].set_sensitive(False)
			else:
				childs[2].set_sensitive(True)
			# compact_view_menuitem
			childs[4].set_active(self.compact_view_current_state)
		menu = self.remove_possible_switch_to_menuitems(menu)
		
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

		conversation_textview = self.xmls[new_jid].get_widget(
			'conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		end_iter = conversation_buffer.get_end_iter()
		end_rect = conversation_textview.get_iter_location(end_iter)
		visible_rect = conversation_textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			#we are at the end
			if self.nb_unread[new_jid] > 0:
				self.nb_unread[new_jid] = 0 + self.get_specific_unread(new_jid)
				self.redraw_tab(new_jid)
				self.show_title()
				if gajim.interface.systray_enabled:
					gajim.interface.systray.remove_jid(new_jid, self.account,
						self.get_message_type(new_jid))

		conversation_textview.grab_focus()

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

		if gajim.interface.windows[self.account][kind].has_key(jid):
			del gajim.interface.windows[self.account][kind][jid]
		del self.nb_unread[jid]
		del gajim.last_message_time[self.account][jid]
		del self.last_time_printout[jid]
		del self.xmls[jid]
		del self.childs[jid]
		del self.tagIn[jid]
		del self.tagOut[jid]
		del self.tagStatus[jid]
		del self.sent_history[jid]
		del self.sent_history_pos[jid]
		del self.typing_new[jid]
		del self.orig_msg[jid]

		if len(self.xmls) == 1: # we now have only one tab
			show_tabs_if_one_tab = gajim.config.get('tabs_always_visible')
			self.notebook.set_show_tabs(show_tabs_if_one_tab)
			self.show_title()

	def bring_scroll_to_end(self, textview, diff_y = 0):
		''' scrolls to the end of textview if end is not visible '''
		buffer = textview.get_buffer()
		at_the_end = False
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

	def size_request(self, message_textview , requisition, xml_top):
		''' When message_textview changes its size. If the new height
		will enlarge the window, enable the scrollbar automatic policy'''
		if message_textview.window is None:
			return
		message_scrolledwindow = xml_top.get_widget('message_scrolledwindow')
		conversation_scrolledwindow = \
			xml_top.get_widget('conversation_scrolledwindow')
		conversation_textview = \
			xml_top.get_widget('conversation_textview')

		min_height = conversation_scrolledwindow.get_property('height-request')
		conversation_height = conversation_textview.window.get_size()[1]
		message_height = message_textview.window.get_size()[1]
		# new tab is not exposed yet
		if conversation_height < 2:
			return

		if conversation_height < min_height:
			min_height = conversation_height

		diff_y =  message_height - requisition.height
		if diff_y is not 0:
			if  conversation_height + diff_y < min_height:
				if message_height + conversation_height - min_height > min_height:
					message_scrolledwindow.set_property('vscrollbar-policy', 
						gtk.POLICY_AUTOMATIC)
					message_scrolledwindow.set_property('hscrollbar-policy', 
						gtk.POLICY_AUTOMATIC)
					message_scrolledwindow.set_property('height-request', 
						message_height + conversation_height - min_height)
					self.bring_scroll_to_end(message_textview)
			else:
				message_scrolledwindow.set_property('vscrollbar-policy', 
					gtk.POLICY_NEVER)
				message_scrolledwindow.set_property('hscrollbar-policy', 
					gtk.POLICY_NEVER)
				message_scrolledwindow.set_property('height-request', -1)
		self.bring_scroll_to_end(conversation_textview, diff_y - 18)
		return True

	def on_tab_eventbox_button_press_event(self, widget, event, child):
		if event.button == 3:
			n = self.notebook.page_num(child)
			self.notebook.set_current_page(n)
			self.popup_menu(event)

	def new_tab(self, jid):
		#FIXME: text formating buttons will be hidden in 0.8 release
		for w in ['bold_togglebutton', 'italic_togglebutton', 'underline_togglebutton']:
			self.xmls[jid].get_widget(w).set_no_show_all(True)

		self.set_compact_view(self.always_compact_view)
		self.nb_unread[jid] = 0
		gajim.last_message_time[self.account][jid] = 0
		self.last_time_printout[jid] = 0.
		font = pango.FontDescription(gajim.config.get('conversation_font'))
		
		if gajim.config.get('use_speller') and 'gtkspell' in globals():
			message_textview = self.xmls[jid].get_widget('message_textview')
			try:
				gtkspell.Spell(message_textview)
			except gobject.GError, msg:
				#FIXME: add a ui for this use spell.set_language()
				dialogs.ErrorDialog(unicode(msg), _('If that is not your language for which you want to highlight misspelled words, then please set your $LANG as appropriate. Eg. for French do export LANG=fr_FR or export LANG=fr_FR.UTF-8 in ~/.bash_profile or to make it global in /etc/profile.\n\nHighlighting misspelled words feature will not be used')).get_response()
				gajim.config.set('use_speller', False)
		
		conversation_textview = self.xmls[jid].get_widget(
			'conversation_textview')
		conversation_textview.modify_font(font)
		conversation_buffer = conversation_textview.get_buffer()
		end_iter = conversation_buffer.get_end_iter()
		
		conversation_buffer.create_mark('end', end_iter, False)
		
		self.tagIn[jid] = conversation_buffer.create_tag('incoming')
		color = gajim.config.get('inmsgcolor')
		self.tagIn[jid].set_property('foreground', color)
		self.tagOut[jid] = conversation_buffer.create_tag('outgoing')
		color = gajim.config.get('outmsgcolor')
		self.tagOut[jid].set_property('foreground', color)
		self.tagStatus[jid] = conversation_buffer.create_tag('status')
		color = gajim.config.get('statusmsgcolor')
		self.tagStatus[jid].set_property('foreground', color)

		tag = conversation_buffer.create_tag('marked')
		color = gajim.config.get('markedmsgcolor')
		tag.set_property('foreground', color)
		tag.set_property('weight', pango.WEIGHT_BOLD)

		tag = conversation_buffer.create_tag('time_sometimes')
		tag.set_property('foreground', '#9e9e9e')
		tag.set_property('scale', pango.SCALE_SMALL)
		tag.set_property('justification', gtk.JUSTIFY_CENTER)
		
		tag = conversation_buffer.create_tag('small')
		tag.set_property('scale', pango.SCALE_SMALL)
		
		tag = conversation_buffer.create_tag('grey')
		tag.set_property('foreground', '#9e9e9e')
		
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
		
		conversation_buffer.create_tag('focus-out-line', 
			justification = gtk.JUSTIFY_CENTER) # FIXME: make it gtk.JUSTIFY_FILL when GTK+ REALLY supports it
		
		self.xmls[jid].signal_autoconnect(self)
		conversation_scrolledwindow = self.xmls[jid].get_widget(
			'conversation_scrolledwindow')
		conversation_scrolledwindow.get_vadjustment().connect('value-changed',
			self.on_conversation_vadjustment_value_changed)

		if len(self.xmls) > 1:
			self.notebook.set_show_tabs(True)

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
		message_textview = self.xmls[jid].get_widget('message_textview')
		message_textview.modify_font(font)
		message_textview.connect('size-request', self.size_request, 
			self.xmls[jid])
		#init new sent history for this conversation
		self.sent_history[jid] = []
		self.sent_history_pos[jid] = 0
		self.typing_new[jid] = True
		self.orig_msg[jid] = ''

		self.show_title()

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
				conversation_textview = self.xmls[jid].get_widget('conversation_textview')
				conversation_textview.get_buffer().set_text('')
			elif event.keyval == gtk.keysyms.v: # CTRL + V
				jid = self.get_active_jid()
				message_textview = self.xmls[jid].get_widget('message_textview')
				if not message_textview.is_focus():
					message_textview.grab_focus()
				message_textview.emit('key_press_event', event)
				
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
		elif event.keyval == gtk.keysyms.Page_Down:
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE DOWN
				conversation_textview = self.xmls[jid].\
					get_widget('conversation_textview')
				rect = conversation_textview.get_visible_rect()
				iter = conversation_textview.get_iter_at_location(rect.x,\
					rect.y + rect.height)
				conversation_textview.scroll_to_iter(iter, 0.1, True, 0, 0)
		elif event.keyval == gtk.keysyms.Page_Up: 
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE UP
				conversation_textview = self.xmls[jid].\
					get_widget('conversation_textview')
				rect = conversation_textview.get_visible_rect()
				iter = conversation_textview.get_iter_at_location(rect.x, rect.y)
				conversation_textview.scroll_to_iter(iter, 0.1, True, 0, 1)
				# or event.keyval == gtk.keysyms.KP_Up
		elif event.keyval == gtk.keysyms.Up: 
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + UP
				conversation_scrolledwindow = self.xml.get_widget('conversation_scrolledwindow')
				conversation_scrolledwindow.emit('scroll-child',
					gtk.SCROLL_PAGE_BACKWARD, False)
		elif event.keyval == gtk.keysyms.ISO_Left_Tab: # SHIFT + TAB
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + SHIFT + TAB
				current = self.notebook.get_current_page()
				if current > 0:
					self.notebook.prev_page()
				else: # traverse for ever (eg. don't stop at first tab)
					self.notebook.set_current_page(self.notebook.get_n_pages()-1)
		elif event.keyval == gtk.keysyms.Tab: # TAB
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + TAB
				current = self.notebook.get_current_page()
				if current < (self.notebook.get_n_pages()-1):
					self.notebook.next_page()
				else: # traverse for ever (eg. don't stop at last tab)
					self.notebook.set_current_page(0)
		elif (event.keyval == gtk.keysyms.l or event.keyval == gtk.keysyms.L) \
				and event.state & gtk.gdk.CONTROL_MASK: # CTRL + L
			conversation_textview = self.xmls[jid].\
				get_widget('conversation_textview')
			conversation_textview.get_buffer().set_text('')
		elif event.keyval == gtk.keysyms.v and event.state & gtk.gdk.CONTROL_MASK:
			# CTRL + V
			jid = self.get_active_jid()
			message_textview = self.xmls[jid].get_widget('message_textview')
			if not message_textview.is_focus():
				message_textview.grab_focus()
			message_textview.emit('key_press_event', event)
		elif event.state & gtk.gdk.CONTROL_MASK or \
			  (event.keyval == gtk.keysyms.Control_L) or \
			  (event.keyval == gtk.keysyms.Control_R):
			# we pressed a control key or ctrl+sth: we don't block
			# the event in order to let ctrl+c (copy text) and
			# others do their default work
			pass
		else: # it's a normal key press make sure message_textview has focus
			message_textview = self.xmls[jid].get_widget('message_textview')
			if message_textview.get_property('sensitive'):
				if not message_textview.is_focus():
					message_textview.grab_focus()
				message_textview.emit('key_press_event', event)

	def on_conversation_vadjustment_value_changed(self, widget):
		jid = self.get_active_jid()
		if not self.nb_unread[jid]:
			return
		textview = self.xmls[jid].get_widget('conversation_textview')
		buffer = textview.get_buffer()
		end_iter = buffer.get_end_iter()
		end_rect = textview.get_iter_location(end_iter)
		visible_rect = textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height) and \
		   self.window.is_active():
			#we are at the end
			self.nb_unread[jid] = 0 + self.get_specific_unread(jid)
			self.redraw_tab(jid)
			self.show_title()
			if gajim.interface.systray_enabled:
				gajim.interface.systray.remove_jid(jid, self.account,
					self.get_message_type(jid))
	
	def show_line_tooltip(self):
		jid = self.get_active_jid()
		textview = self.xmls[jid].get_widget('conversation_textview')
		pointer = textview.get_pointer()
		x, y = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, pointer[0],
			pointer[1])
		tags = textview.get_iter_at_location(x, y).get_tags()
		tag_table = textview.get_buffer().get_tag_table()
		over_line = False
		for tag in tags:
			if tag == tag_table.lookup('focus-out-line'):
				over_line = True
				break
		if over_line and not self.line_tooltip.win:
			# check if the current pointer is still over the line
			pointer_x, pointer_y, spam = textview.window.get_pointer()
			x, y = textview.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, pointer_x,
				pointer_y)
			position = textview.window.get_origin()
			self.line_tooltip.show_tooltip(_('Below this ruler is what is new since you last payed attention to this group chat'), (0, 8),
				(self.window.get_screen().get_display().get_pointer()[1],
				position[1] + pointer_y))

	def on_conversation_textview_motion_notify_event(self, widget, event):
		'''change the cursor to a hand when we are over a mail or an url'''
		jid = self.get_active_jid()
		pointer_x, pointer_y, spam = widget.window.get_pointer()
		x, y = widget.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT, pointer_x,
			pointer_y)
		tags = widget.get_iter_at_location(x, y).get_tags()
		if self.change_cursor:
			widget.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
				gtk.gdk.Cursor(gtk.gdk.XTERM))
			self.change_cursor = None
		tag_table = widget.get_buffer().get_tag_table()
		over_line = False
		for tag in tags:
			if tag in (tag_table.lookup('url'), tag_table.lookup('mail')):
				widget.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
					gtk.gdk.Cursor(gtk.gdk.HAND2))
				self.change_cursor = tag
			elif self.widget_name == 'groupchat_window' and \
			tag == tag_table.lookup('focus-out-line'):
				over_line = True
				# FIXME: found out (dkirov can help) what those params are supposed to be

		if self.line_tooltip.timeout != 0:
			# Check if we should hide the line tooltip
			if not over_line:
				self.line_tooltip.hide_tooltip()
		if over_line and not self.line_tooltip.win:
			self.line_tooltip.timeout = gobject.timeout_add(500,
				self.show_line_tooltip)
			widget.get_window(gtk.TEXT_WINDOW_TEXT).set_cursor(
				gtk.gdk.Cursor(gtk.gdk.LEFT_PTR))
			self.change_cursor = tag

	def on_clear(self, widget, textview):
		'''clear text in the given textview'''
		buffer = textview.get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)

	def visit_url_from_menuitem(self, widget, link):
		'''basically it filters out the widget instance'''
		helpers.launch_browser_mailer('url', link)

	def on_conversation_textview_populate_popup(self, textview, menu):
		'''we override the default context menu and we prepend Clear
		and if we have sth selected we show a submenu with actions on the phrase
		(see on_conversation_textview_button_press_event)'''
		item = gtk.SeparatorMenuItem()
		menu.prepend(item)
		item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
		menu.prepend(item)
		item.connect('activate', self.on_clear, textview)
		if self.selected_phrase:
			s = self.selected_phrase
			if len(s) > 25:
				s = s[:21] + '...'
			item = gtk.MenuItem(_('Actions for "%s"') % s)
			menu.prepend(item)
			submenu = gtk.Menu()
			item.set_submenu(submenu)
			
			always_use_en = gajim.config.get('always_english_wikipedia')
			if always_use_en:
				link = 'http://en.wikipedia.org/wiki/Special:Search?search=%s'\
					% self.selected_phrase
			else:
				link = 'http://%s.wikipedia.org/wiki/Special:Search?search=%s'\
					% (gajim.LANG, self.selected_phrase)
			item = gtk.MenuItem(_('Read _Wikipedia Article'))
			item.connect('activate', self.visit_url_from_menuitem, link)
			submenu.append(item)

			item = gtk.MenuItem(_('Look it up in _Dictionary'))
			dict_link = gajim.config.get('dictionary_url')
			if dict_link == 'WIKTIONARY':
				# special link (yeah undocumented but default)
				always_use_en = gajim.config.get('always_english_wiktionary')
				if always_use_en:
					link = 'http://en.wiktionary.org/wiki/Special:Search?search=%s'\
						% self.selected_phrase
				else:
					link = 'http://%s.wiktionary.org/wiki/Special:Search?search=%s'\
						% (gajim.LANG, self.selected_phrase)
				item.connect('activate', self.visit_url_from_menuitem, link)
			else:
				if dict_link.find('%s') == -1:
					#we must have %s in the url if not WIKTIONARY
					item = gtk.MenuItem(_('Dictionary URL is missing an "%s" and it is not WIKTIONARY'))
					item.set_property('sensitive', False)
				else:
					link = dict_link % self.selected_phrase
					item.connect('activate', self.visit_url_from_menuitem, link)
			submenu.append(item)
			
			
			search_link = gajim.config.get('search_engine')
			if search_link.find('%s') == -1:
				#we must have %s in the url
				item = gtk.MenuItem(_('Web Search URL is missing an "%s"'))
				item.set_property('sensitive', False)
			else:
				item = gtk.MenuItem(_('Web _Search for it'))
				link =  search_link % self.selected_phrase
				item.connect('activate', self.visit_url_from_menuitem, link)
			submenu.append(item)
			
		menu.show_all()
			
	def on_conversation_textview_button_press_event(self, widget, event):
		# If we clicked on a taged text do NOT open the standard popup menu
		# if normal text check if we have sth selected

		self.selected_phrase = ''

		if event.button != 3: # if not right click
			return False

		win = widget.get_window(gtk.TEXT_WINDOW_TEXT)
		x, y = widget.window_to_buffer_coords(gtk.TEXT_WINDOW_TEXT,
			int(event.x), int(event.y))
		iter = widget.get_iter_at_location(x, y)
		tags = iter.get_tags()


		if tags: # we clicked on sth special (it can be status message too)
			for tag in tags:
				tag_name = tag.get_property('name')
				if 'url' in tag_name or 'mail' in tag_name:
					return True # we block normal context menu

		# we check if sth was selected and if it was we assign
		# selected_phrase variable
		# so on_conversation_textview_populate_popup can use it
		buffer = widget.get_buffer()
		return_val = buffer.get_selection_bounds()
		if return_val: # if sth was selected when we right-clicked
			# get the selected text
			start_sel, finish_sel = return_val[0], return_val[1]
			self.selected_phrase = buffer.get_text(start_sel, finish_sel).decode('utf-8')

	def print_time_timeout(self, jid):
		if not jid in self.xmls.keys():
			return False
		if gajim.config.get('print_time') == 'sometimes':
			textview = self.xmls[jid].get_widget('conversation_textview')
			buffer = textview.get_buffer()
			end_iter = buffer.get_end_iter()
			tim = time.localtime()
			tim_format = time.strftime('%H:%M', tim)
			buffer.insert_with_tags_by_name(end_iter,
						'\n' + tim_format,
						'time_sometimes')
			#scroll to the end of the textview
			end_rect = textview.get_iter_location(end_iter)
			visible_rect = textview.get_visible_rect()
			if end_rect.y <= (visible_rect.y + visible_rect.height):
				#we are at the end
				self.scroll_to_end(textview)
			return True # loop again
		if self.print_time_timeout_id.has_key(jid):
			del self.print_time_timeout_id[jid]
		return False

	def on_open_link_activate(self, widget, kind, text):
		helpers.launch_browser_mailer(kind, text)

	def on_copy_link_activate(self, widget, text):
		clip = gtk.clipboard_get()
		clip.set_text(text)

	def on_start_chat_activate(self, widget, jid):
		gajim.interface.roster.new_chat_from_jid(self.account, jid)

	def on_join_group_chat_menuitem_activate(self, widget, jid):
		room, server = jid.split('@')
		if gajim.interface.windows[self.account].has_key('join_gc'):
			instance = gajim.interface.windows[self.account]['join_gc']
			instance.xml.get_widget('server_entry').set_text(server)
			instance.xml.get_widget('room_entry').set_text(room)
			gajim.interface.windows[self.account]['join_gc'].window.present()		
		else:
			try:
				gajim.interface.windows[self.account]['join_gc'] = \
				dialogs.JoinGroupchatWindow(self.account, server, room)
			except RuntimeError:
				pass

	def on_add_to_roster_activate(self, widget, jid):
		dialogs.AddNewContactWindow(self.account, jid)

	def make_link_menu(self, event, kind, text):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'chat_context_menu', APP)
		menu = xml.get_widget('chat_context_menu')
		childs = menu.get_children()
		if kind == 'url':
			childs[0].connect('activate', self.on_copy_link_activate, text)
			childs[1].connect('activate', self.on_open_link_activate, kind, text)
			childs[2].hide() # copy mail address
			childs[3].hide() # open mail composer
			childs[4].hide() # jid section seperator
			childs[5].hide() # start chat
			childs[6].hide() # join group chat
			childs[7].hide() # add to roster
		else: # It's a mail or a JID
			childs[2].connect('activate', self.on_copy_link_activate, text)
			childs[3].connect('activate', self.on_open_link_activate, kind, text)
			childs[5].connect('activate', self.on_start_chat_activate, text)
			childs[6].connect('activate',
				self.on_join_group_chat_menuitem_activate, text)
				
			allow_add = False
			if gajim.contacts[self.account].has_key(text):
				c = gajim.contacts[self.account][text][0]
				if _('not in the roster') in c.groups:
					allow_add = True
			else: # he's not at all in the account contacts
				allow_add = True
			
			if allow_add:
				childs[7].connect('activate', self.on_add_to_roster_activate, text)
				childs[7].show() # show add to roster menuitem
			else:
				childs[7].hide() # hide add to roster menuitem
				
			childs[0].hide() # copy link location
			childs[1].hide() # open link in browser

		menu.popup(None, None, None, event.button, event.time)

	def hyperlink_handler(self, texttag, widget, event, iter, kind):
		if event.type == gtk.gdk.BUTTON_PRESS:
			begin_iter = iter.copy()
			#we get the begining of the tag
			while not begin_iter.begins_tag(texttag):
				begin_iter.backward_char()
			end_iter = iter.copy()
			#we get the end of the tag
			while not end_iter.ends_tag(texttag):
				end_iter.forward_char()
			word = widget.get_buffer().get_text(begin_iter, end_iter).decode(
				'utf-8')
			if event.button == 3: # right click
				self.make_link_menu(event, kind, word)
			else:
				#we launch the correct application
				helpers.launch_browser_mailer(kind, word)

	def detect_and_print_special_text(self, otext, jid, other_tags):
		textview = self.xmls[jid].get_widget('conversation_textview')
		buffer = textview.get_buffer()
		
		start = 0
		end = 0
		index = 0
		
		# basic: links + mail + formatting is always checked (we like that)
		if gajim.config.get('useemoticons'): # search for emoticons & urls
			iterator = gajim.interface.emot_and_basic_re.finditer(otext)
		else: # search for just urls + mail + formatting
			iterator = gajim.interface.basic_pattern_re.finditer(otext)
		for match in iterator:
			start, end = match.span()
			special_text = otext[start:end]
			if start != 0:
				text_before_special_text = otext[index:start]
				end_iter = buffer.get_end_iter()
				buffer.insert_with_tags_by_name(end_iter,
					text_before_special_text, *other_tags)
			index = end # update index
			
			# now print it
			self.print_special_text(special_text, other_tags, textview)
					
		return index
		
	def print_special_text(self, special_text, other_tags, textview):
		tags = []
		use_other_tags = True
		show_ascii_formatting_chars=gajim.config.get('show_ascii_formatting_chars')
		buffer = textview.get_buffer()

		possible_emot_ascii_caps = special_text.upper() # emoticons keys are CAPS
		if possible_emot_ascii_caps in gajim.interface.emoticons.keys():
			#it's an emoticon
			emot_ascii = possible_emot_ascii_caps
			end_iter = buffer.get_end_iter()
			anchor = buffer.create_child_anchor(end_iter)
			img = gtk.Image()
			img.set_from_file(gajim.interface.emoticons[emot_ascii])
			img.show()
			#add with possible animation
			textview.add_child_at_anchor(img, anchor)
		elif special_text.startswith('mailto:'):
			#it's a mail
			tags.append('mail')
			use_other_tags = False
		elif gajim.interface.sth_at_sth_dot_sth_re.match(special_text):
			#it's a mail
			tags.append('mail')
			use_other_tags = False
		elif special_text.startswith('*'): # it's a bold text
			tags.append('bold')
			if special_text[1] == '/': # it's also italic
				tags.append('italic')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove */ /*
			elif special_text[1] == '_': # it's also underlined
				tags.append('underline')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove *_ _*
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove * *
		elif special_text.startswith('/'): # it's an italic text
			tags.append('italic')
			if special_text[1] == '*': # it's also bold
				tags.append('bold')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove /* */
			elif special_text[1] == '_': # it's also underlined
				tags.append('underline')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove /_ _/
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove / /
		elif special_text.startswith('_'): # it's an underlined text
			tags.append('underline')
			if special_text[1] == '*': # it's also bold
				tags.append('bold')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove _* *_
			elif special_text[1] == '/': # it's also italic
				tags.append('italic')
				if not show_ascii_formatting_chars:
					special_text = special_text[2:-2] # remove _/ /_
			else:
				if not show_ascii_formatting_chars:
					special_text = special_text[1:-1] # remove _ _
		else:
			#it's a url
			tags.append('url')
			use_other_tags = False

		if len(tags) > 0:
			end_iter = buffer.get_end_iter()
			all_tags = tags[:]
			if use_other_tags:
				all_tags += other_tags
			buffer.insert_with_tags_by_name(end_iter, special_text, *all_tags)

	def scroll_to_end(self, textview):
		parent = textview.get_parent()
		buffer = textview.get_buffer()
		textview.scroll_to_mark(buffer.get_mark('end'), 0, True, 0, 1)
		adjustment = parent.get_hadjustment()
		adjustment.set_value(0)
		return False

	def print_empty_line(self, jid):
		textview = self.xmls[jid].get_widget('conversation_textview')
		buffer = textview.get_buffer()
		end_iter = buffer.get_end_iter()
		buffer.insert(end_iter, '\n')

	def print_conversation_line(self, text, jid, kind, name, tim,
			other_tags_for_name = [], other_tags_for_time = [], 
			other_tags_for_text = [], count_as_new = True, subject = None):
		'''prints 'chat' type messages'''
		textview = self.xmls[jid].get_widget('conversation_textview')
		buffer = textview.get_buffer()
		buffer.begin_user_action()
		at_the_end = False
		end_iter = buffer.get_end_iter()
		end_rect = textview.get_iter_location(end_iter)
		visible_rect = textview.get_visible_rect()
		if end_rect.y <= (visible_rect.y + visible_rect.height):
			at_the_end = True

		if buffer.get_char_count() > 0:
			buffer.insert(end_iter, '\n')
		update_time = True
		if kind == 'incoming_queue':
			kind = 'incoming'
			update_time  = False
		# print the time stamp
		if gajim.config.get('print_time') == 'always':
			if not tim:
				tim = time.localtime()
			before_str = gajim.config.get('before_time')
			after_str = gajim.config.get('after_time')
			format = before_str + '%H:%M:%S' + after_str
			tim_format = time.strftime(format, tim)
			buffer.insert_with_tags_by_name(end_iter, tim_format + ' ',
				*other_tags_for_time)
		elif gajim.config.get('print_time') == 'sometimes':
			every_foo_seconds = 60 * gajim.config.get(
				'print_ichat_every_foo_minutes')
			seconds_passed = time.time() - self.last_time_printout[jid]
			if seconds_passed > every_foo_seconds:
				self.last_time_printout[jid] = time.time()
				end_iter = buffer.get_end_iter()
				tim = time.localtime()
				tim_format = time.strftime('%H:%M', tim)
				buffer.insert_with_tags_by_name(end_iter,
							tim_format + '\n',
							'time_sometimes')
				# scroll to the end of the textview
				end_rect = textview.get_iter_location(end_iter)
				visible_rect = textview.get_visible_rect()

		text_tags = other_tags_for_text[:] # create a new list
		if kind == 'status':
			text_tags.append(kind)
		elif text.startswith('/me ') or text.startswith('/me\n'):
			text = '* ' + name + text[3:]
			text_tags.append(kind)

		if name and len(text_tags) == len(other_tags_for_text):
			# not status nor /me
			name_tags = other_tags_for_name[:] # create a new list
			name_tags.append(kind)
			before_str = gajim.config.get('before_nickname')
			after_str = gajim.config.get('after_nickname')
			format = before_str + name + after_str + ' ' 
			buffer.insert_with_tags_by_name(end_iter, format, *name_tags)

		# detect urls formatting and if the user has it on emoticons
		index = self.detect_and_print_special_text(text, jid, text_tags)

		if subject: # if we have subject, show it too!
			subject = _('Subject: %s\n') % subject
			end_iter = buffer.get_end_iter()
			buffer.insert(end_iter, subject)
		
		# add the rest of text located in the index and after
		end_iter = buffer.get_end_iter()
		buffer.insert_with_tags_by_name(end_iter, text[index:], *text_tags)

		#scroll to the end of the textview
		end = False
		if at_the_end or kind == 'outgoing':
			# we are at the end or we are sending something
			end = True
			# scroll to the end (via idle in case the scrollbar has appeared)
			gobject.idle_add(self.scroll_to_end, textview)

		buffer.end_user_action()

		if not count_as_new:
			return
		if kind == 'incoming' and update_time:
			gajim.last_message_time[self.account][jid] = time.time()
		urgent = True
		if (jid != self.get_active_jid() or \
		   not self.window.is_active() or \
		   not end) and kind == 'incoming':
			if self.widget_name == 'groupchat_window':
				if text.find(self.nicks[jid]) == -1:
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
			for i in range(0, size - 1): 
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
				conversation_textview = \
					self.xmls[jid].get_widget('conversation_textview')
				gobject.idle_add(self.scroll_to_end_iter, conversation_textview)
