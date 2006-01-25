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

import common
import gtkgui_helpers
import message_control
from chat_control import ChatControlBase

from common import gajim

####################
# FIXME: Can't this stuff happen once?
from common import i18n
_ = i18n._
APP = i18n.APP

GTKGUI_GLADE = 'gtkgui.glade'
####################

class MessageWindow:
	'''Class for windows which contain message like things; chats,
	groupchats, etc.'''

	# DND_TARGETS is the targets needed by drag_source_set and drag_dest_set
	DND_TARGETS = [('GAJIM_TAB', 0, 81)]
	hid = 0 # drag_data_received handler id
	
	def __init__(self, acct, type):
		# A dictionary of dictionaries where _contacts[account][jid] == A MessageControl
		self._controls = {}
		# If None, the window is not tied to any specific account
		self.account = acct
		# If None, the window is not tied to any specific type
		self.type = type

		self.widget_name = 'message_window'
		self.xml = gtk.glade.XML(GTKGUI_GLADE, self.widget_name, APP)
		self.xml.signal_autoconnect(self)
		self.window = self.xml.get_widget(self.widget_name)
		# I don't really understand, but get_property('visible') returns True at this point,
		# which seems way early.  Anyway, hide until first tab is shown
		self.window.hide()
		# gtk+ doesn't make use of the motion notify on gtkwindow by default
		# so this line adds that
		self.window.add_events(gtk.gdk.POINTER_MOTION_MASK)
		self.alignment = self.xml.get_widget('alignment')

		self.notebook = self.xml.get_widget('notebook')
		self.notebook.connect('switch-page',
					self._on_notebook_switch_page)
		self.notebook.connect('key-press-event',
					self._on_notebook_key_press)

		# Remove the glade pages
		while self.notebook.get_n_pages():
			self.notebook.remove_page(0)
		# Tab customizations
		pref_pos = gajim.config.get('tabs_position')
		if pref_pos == 'bottom':
			nb_pos = gtk.POS_BOTTOM
		elif pref_pos == 'left':
			nb_pos = gtk.POS_LEFT
		elif pref_pos == 'right':
			nb_pos = gtk.POS_RIGHT
		else:
			nb_pos = gtk.POS_TOP
		self.notebook.set_tab_pos(nb_pos)
		if gajim.config.get('tabs_always_visible'):
			self.notebook.set_show_tabs(True)
			self.alignment.set_property('top-padding', 2)
		else:
			self.notebook.set_show_tabs(False)
		self.notebook.set_show_border(gajim.config.get('tabs_border'))

		# set up DnD
		self.hid = self.notebook.connect('drag_data_received',
						self.on_tab_label_drag_data_received_cb)
		self.notebook.drag_dest_set(gtk.DEST_DEFAULT_ALL, self.DND_TARGETS,
						gtk.gdk.ACTION_MOVE)

	def get_num_controls(self):
		n = 0
		for dict in self._controls.values():
			n += len(dict)
		return n

	def _on_window_focus(self, widget, event):
		# window received focus, so if we had urgency REMOVE IT
		# NOTE: we do not have to read the message (it maybe in a bg tab)
		# to remove urgency hint so this functions does that
		gtkgui_helpers.set_unset_urgency_hint(self.window, False)

		ctrl = self.get_active_control()
		if ctrl:
			ctrl.set_control_active(True)
			# Undo "unread" state display, etc.
			if ctrl.type_id == message_control.TYPE_GC:
				self.redraw_tab(ctrl, 'active')
			else:
				# NOTE: we do not send any chatstate to preserve
				# inactive, gone, etc.
				self.redraw_tab(ctrl)

	def _on_window_delete(self, win, event):
		# Make sure all controls are okay with being deleted
		for ctrl in self.controls():
			if not ctrl.allow_shutdown():
				return True # halt the delete
		return False

	def _on_window_destroy(self, win):
		for ctrl in self.controls():
			ctrl.shutdown()
		self._controls.clear()

	def new_tab(self, control):
		if not self._controls.has_key(control.account):
			self._controls[control.account] = {}
		self._controls[control.account][control.contact.jid] = control

		if self.get_num_controls() > 1:
			self.notebook.set_show_tabs(True)
			self.alignment.set_property('top-padding', 2)

		# Add notebook page and connect up to the tab's close button
		xml = gtk.glade.XML(GTKGUI_GLADE, 'chat_tab_ebox', APP)
		tab_label_box = xml.get_widget('chat_tab_ebox')
		xml.signal_connect('on_close_button_clicked', self._on_close_button_clicked,
					control)
		xml.signal_connect('on_tab_eventbox_button_press_event',
				self.on_tab_eventbox_button_press_event, control.widget)
		self.notebook.append_page(control.widget, tab_label_box)

		self.setup_tab_dnd(control.widget)

		self.redraw_tab(control)
		self.window.show_all()
		# NOTE: we do not call set_control_active(True) since we don't know whether
		# the tab is the active one.
		self.show_title()

	def on_tab_eventbox_button_press_event(self, widget, event, child):
		if event.button == 3:
			n = self.notebook.page_num(child)
			self.notebook.set_current_page(n)
			self.popup_menu(event)

	def _on_message_textview_mykeypress_event(self, widget, event_keyval,
						event_keymod):
		# NOTE: handles mykeypress which is custom signal; see message_textview.py

		# construct event instance from binding
		event = gtk.gdk.Event(gtk.gdk.KEY_PRESS) # it's always a key-press here
		event.keyval = event_keyval
		event.state = event_keymod
		event.time = 0 # assign current time

		if event.state & gtk.gdk.CONTROL_MASK:
			# Tab switch bindings
			if event.keyval == gtk.keysyms.Tab: # CTRL + TAB
				self.move_to_next_unread_tab(True)
			elif event.keyval == gtk.keysyms.ISO_Left_Tab: # CTRL + SHIFT + TAB
				self.move_to_next_unread_tab(False)
			elif event.keyval == gtk.keysyms.Page_Down: # CTRL + PAGE DOWN
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.Page_Up: # CTRL + PAGE UP
				self.notebook.emit('key_press_event', event)

	def _on_close_button_clicked(self, button, control):
		'''When close button is pressed: close a tab'''
		self.remove_tab(control)

	def show_title(self, urgent = True, control = None):
		'''redraw the window's title'''
		unread = 0
		for ctrl in self.controls():
			if ctrl.type_id == message_control.TYPE_GC and not \
				gajim.config.get('notify_on_all_muc_messages') and not \
				ctrl.attention_flag:
				continue
			unread += ctrl.nb_unread
		unread_str = ''
		if unread > 1:
			unread_str = '[' + unicode(unread) + '] '
		elif unread == 1:
			unread_str = '* '
		else:
			urgent = False

		if not control:
			control = self.get_active_control()
		if control.type_id == message_control.TYPE_GC:
			title = unread_str + control.room_jid
			urgent = control.attention_flag
		else:
			title = unread_str + control.contact.get_shown_name()

		self.window.set_title(title)

		if urgent:
			gtkgui_helpers.set_unset_urgency_hint(self.window, unread)
		else:
			gtkgui_helpers.set_unset_urgency_hint(self.window, False)

	def set_active_tab(self, jid, acct):
		ctrl = self._controls[acct][jid]
		ctrl_page = self.notebook.page_num(ctrl.widget)
		self.notebook.set_current_page(ctrl_page)
	
	def remove_tab(self, ctrl):
		# Shutdown the MessageControl
		if not ctrl.allow_shutdown():
			return
		ctrl.shutdown()

		# Update external state
		if gajim.interface.systray_enabled:
			gajim.interface.systray.remove_jid(ctrl.contact.jid, ctrl.account,
								ctrl.type_id)
		del gajim.last_message_time[ctrl.account][ctrl.contact.jid]

		self.disconnect_tab_dnd(ctrl.widget)
		self.notebook.remove_page(self.notebook.page_num(ctrl.widget))

		del self._controls[ctrl.account][ctrl.contact.jid]
		if len(self._controls[ctrl.account]) == 0:
			del self._controls[ctrl.account]

		if self.get_num_controls() == 1: # we are going from two tabs to one
			show_tabs_if_one_tab = gajim.config.get('tabs_always_visible')
			self.notebook.set_show_tabs(show_tabs_if_one_tab)
			if not show_tabs_if_one_tab:
				self.alignment.set_property('top-padding', 0)
			self.show_title()
		elif self.get_num_controls() == 0:
			# These are not called when the window is destroyed like this, fake it
			gajim.interface.msg_win_mgr._on_window_delete(self.window, None)
			gajim.interface.msg_win_mgr._on_window_destroy(self.window)
			# dnd clean up
			self.notebook.disconnect(self.hid)
			self.notebook.drag_dest_unset()

			self.window.destroy()
			
	def redraw_tab(self, ctrl, chatstate = None):
		ctrl.update_ui()

		hbox = self.notebook.get_tab_label(ctrl.widget).get_children()[0]
		status_img = hbox.get_children()[0]
		nick_label = hbox.get_children()[1]

		# Optionally hide close button
		close_button = hbox.get_children()[2]
		if gajim.config.get('tabs_close_button'):
			close_button.show()
		else:
			close_button.hide()

		# Update nick
		nick_label.set_max_width_chars(10)
		(tab_label_str, tab_label_color) = ctrl.get_tab_label(chatstate)
		nick_label.set_markup(tab_label_str)
		if tab_label_color:
			nick_label.modify_fg(gtk.STATE_NORMAL, tab_label_color)
			nick_label.modify_fg(gtk.STATE_ACTIVE, tab_label_color)

		tab_img = ctrl.get_tab_image()
		if tab_img:
			if tab_img.get_storage_type() == gtk.IMAGE_ANIMATION:
				status_img.set_from_animation(tab_img.get_animation())
			else:
				status_img.set_from_pixbuf(tab_img.get_pixbuf())

	def repaint_themed_widgets(self):
		'''Repaint controls in the window with theme color'''
		# iterate through controls and repaint
		for ctrl in self.controls():
			ctrl.repaint_themed_widgets()

	def _widget_to_control(self, widget):
		for ctrl in self.controls():
			if ctrl.widget == widget:
				return ctrl
		return None

	def get_active_control(self):
		notebook = self.notebook
		active_widget = notebook.get_nth_page(notebook.get_current_page())
		return self._widget_to_control(active_widget)
	def get_active_contact(self):
		ctrl = self.get_active_control()
		if ctrl:
			return ctrl.contact
		return None
	def get_active_jid(self):
		contact = self.get_active_contact()
		if contact:
			return contact.jid
		return None

	def is_active(self):
		return self.window.is_active()
	def get_origin(self):
		return self.window.window.get_origin()

	def toggle_emoticons(self):
		for ctrl in self.controls():
			ctrl.toggle_emoticons()
	def update_font(self):
		for ctrl in self.controls():
			ctrl.update_font()
	def update_tags(self):
		for ctrl in self.controls():
			ctrl.update_tags()

	def get_control(self, key, acct):
		'''Return the MessageControl for jid or n, where n is a notebook page index.
		When key is an int index acct may be None'''
		if isinstance(key, str):
			key = unicode(key, 'utf-8')

		if isinstance(key, unicode):
			jid = key
			try:
				return self._controls[acct][jid]
			except:
				return None
		else:
			page_num = key
			notebook = self.notebook
			if page_num == None:
				page_num = notebook.get_current_page()
			nth_child = notebook.get_nth_page(page_num)
			return self._widget_to_control(nth_child)

	def controls(self):
		for ctrl_dict in self._controls.values():
			for ctrl in ctrl_dict.values():
				yield ctrl

	def update_print_time(self):
		if gajim.config.get('print_time') != 'sometimes':
			for ctrl in self.controls():
				if ctrl.print_time_timeout_id:
					gobject.source_remove(ctrl.print_time_timeout_id)
					del ctrl.print_time_timeout_id
		else:
			for ctrl in self.controls():
				if not ctrl.print_time_timeout_id:
					ctrl.print_time_timeout()
					ctrl.print_time_timeout_id = gobject.timeout_add(300000,
						ctrl.print_time_timeout, None)

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
			ctrl = self.get_control(ind, None)
			if ctrl.nb_unread > 0:
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
	def popup_menu(self, event):
		menu = self.get_active_control().prepare_context_menu()
		# common menuitems (tab switches)
		if self.get_num_controls() > 1: # if there is more than one tab
			menu.append(gtk.SeparatorMenuItem()) # seperator
			for ctrl in self.controls():
				jid = ctrl.contact.jid
				if jid != self.get_active_jid():
					item = gtk.ImageMenuItem(_('Switch to %s') %\
							ctrl.contact.get_shown_name())
					img = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
									gtk.ICON_SIZE_MENU)
					item.set_image(img)
					item.connect('activate',
						lambda obj, jid:self.set_active_tab(jid, ctrl.account),
						jid)
					menu.append(item)
		# show the menu
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()

	def _on_notebook_switch_page(self, notebook, page, page_num):
		old_no = notebook.get_current_page()
		if old_no >= 0:
			old_ctrl = self._widget_to_control(notebook.get_nth_page(old_no))
			old_ctrl.set_control_active(False)
		
		new_ctrl = self._widget_to_control(notebook.get_nth_page(page_num))
		new_ctrl.set_control_active(True)
		self.show_title(control = new_ctrl)

	def _on_notebook_key_press(self, widget, event):
		st = '1234567890' # alt+1 means the first tab (tab 0)
		ctrl = self.get_active_control()
		contact = ctrl.contact
		jid = ctrl.contact.jid

		# CTRL mask
		if event.state & gtk.gdk.CONTROL_MASK:
			# Tab switch bindings
			if event.keyval == gtk.keysyms.ISO_Left_Tab: # CTRL + SHIFT + TAB
				self.move_to_next_unread_tab(False)
			elif event.keyval == gtk.keysyms.Tab: # CTRL + TAB
				self.move_to_next_unread_tab(True)
			elif event.keyval == gtk.keysyms.F4: # CTRL + F4
				self.remove_tab(ctrl)
			elif event.keyval == gtk.keysyms.w: # CTRL + W
				self.remove_tab(ctrl)

		# MOD1 (ALT) mask
		elif event.state & gtk.gdk.MOD1_MASK:
			# Tab switch bindings
			if event.keyval == gtk.keysyms.Right: # ALT + RIGHT
				new = self.notebook.get_current_page() + 1
				if new >= self.notebook.get_n_pages(): 
					new = 0
				self.notebook.set_current_page(new)
			elif event.keyval == gtk.keysyms.Left: # ALT + LEFT
				new = self.notebook.get_current_page() - 1
				if new < 0:
					new = self.notebook.get_n_pages() - 1
				self.notebook.set_current_page(new)
			elif event.string and event.string in st and \
					(event.state & gtk.gdk.MOD1_MASK): # ALT + 1,2,3..
				self.notebook.set_current_page(st.index(event.string))
			elif event.keyval == gtk.keysyms.c: # ALT + C toggles compact view
				ctrl.set_compact_view(not ctrl.compact_view_current)
		# Close tab bindings
		elif event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.remove_tab(ctrl)
		else:
			# If the active control has a message_textview pass the event to it
			active_ctrl = self.get_active_control()
			if isinstance(active_ctrl, ChatControlBase):
				active_ctrl.msg_textview.emit('key_press_event', event)
				active_ctrl.msg_textview.grab_focus()

	def setup_tab_dnd(self, child):
		'''Set tab label as drag source and connect the drag_data_get signal'''
		tab_label = self.notebook.get_tab_label(child)
		tab_label.dnd_handler = tab_label.connect('drag_data_get', 
							  self.on_tab_label_drag_data_get_cb)
		tab_label.drag_source_set(gtk.gdk.BUTTON1_MASK, self.DND_TARGETS,
					 gtk.gdk.ACTION_MOVE)
		tab_label.page_num = self.notebook.page_num(child)

	def on_tab_label_drag_data_get_cb(self, widget, drag_context, selection, info, time):
		source_page_num = self.find_page_num_according_to_tab_label(widget)
		# 8 is the data size for the string
		selection.set(selection.target, 8, str(source_page_num))

	def on_tab_label_drag_data_received_cb(self, widget, drag_context, x, y, selection,
						type, time):
		'''Reorder the tabs according to the drop position'''
		source_page_num = int(selection.data)
		dest_page_num, to_right = self.get_tab_at_xy(x, y)
		source_child = self.notebook.get_nth_page(source_page_num)
		source_tab_label = self.notebook.get_tab_label(source_child)
		if dest_page_num != source_page_num:
			self.notebook.reorder_child(source_child, dest_page_num)
		
	def get_tab_at_xy(self, x, y):
		'''Thanks to Gaim
		Return the tab under xy and
		if its nearer from left or right side of the tab	
		'''
		page_num = -1
		to_right = False
		horiz = self.notebook.get_tab_pos() == gtk.POS_TOP or \
			self.notebook.get_tab_pos() == gtk.POS_BOTTOM
		for i in xrange(self.notebook.get_n_pages()):
			page = self.notebook.get_nth_page(i)
			tab = self.notebook.get_tab_label(page)
			tab_alloc = tab.get_allocation()
			if horiz:
				if (x >= tab_alloc.x) and \
					   (x <= (tab_alloc.x + tab_alloc.width)):
					page_num = i
					if x >= tab_alloc.x + (tab_alloc.width / 2.0):
						to_right = True
					break
			else:
				if (y >= tab_alloc.y) and \
					   (y <= (tab_alloc.y + tab_alloc.height)):
					page_num = i
				
					if y > tab_alloc.y + (tab_alloc.height / 2.0):
						to_right = True
					break
		return (page_num, to_right)

	def find_page_num_according_to_tab_label(self, tab_label):
		'''Find the page num of the tab label'''
		page_num = -1
		for i in xrange(self.notebook.get_n_pages()):
			page = self.notebook.get_nth_page(i)
			tab = self.notebook.get_tab_label(page)
			if tab == tab_label:
				page_num = i
				break
		return page_num

	def disconnect_tab_dnd(self, child):
		'''Clean up DnD signals, source and dest'''
		tab_label = self.notebook.get_tab_label(child)
		tab_label.drag_source_unset()
		tab_label.disconnect(tab_label.dnd_handler)

################################################################################
class MessageWindowMgr:
	'''A manager and factory for MessageWindow objects'''

	# These constants map to common.config.opt_one_window_types indices
	(
	ONE_MSG_WINDOW_NEVER,
	ONE_MSG_WINDOW_ALWAYS,
	ONE_MSG_WINDOW_PERACCT,
	ONE_MSG_WINDOW_PERTYPE
	) = range(4)
	# A key constant for the main window for all messages
	MAIN_WIN = 'main'

	def __init__(self):
		''' A dictionary of windows; the key depends on the config:
		 ONE_MSG_WINDOW_NEVER: The key is the contact JID
		 ONE_MSG_WINDOW_ALWAYS: The key is MessageWindowMgr.MAIN_WIN 
		 ONE_MSG_WINDOW_PERACCT: The key is the account name
		 ONE_MSG_WINDOW_PERTYPE: The key is a message type constant'''
		self._windows = {}
		# Map the mode to a int constant for frequent compares
		mode = gajim.config.get('one_message_window')
		self.mode = common.config.opt_one_window_types.index(mode)
	
	def _new_window(self, acct, type):
		win = MessageWindow(acct, type)
		# we track the lifetime of this window
		win.window.connect('delete-event', self._on_window_delete)
		win.window.connect('destroy', self._on_window_destroy)
		return win

	def _gtk_win_to_msg_win(self, gtk_win):
		for w in self.windows():
			if w.window == gtk_win:
				return w
		return None

	def get_window(self, jid, acct):
		for win in self.windows():
			if win.get_control(jid, acct):
				return win
		return None

	def has_window(self, jid, acct):
		return self.get_window(jid, acct) != None

	def one_window_opened(self, contact, acct, type):
		try:
			return self._windows[self._mode_to_key(contact, acct, type)] != None
		except KeyError:
			return False

	def _size_window(self, win, acct, type):
		'''Resizes window according to config settings'''
		if not gajim.config.get('saveposition'):
			return
			
		if self.mode == self.ONE_MSG_WINDOW_NEVER or self.mode == self.ONE_MSG_WINDOW_ALWAYS:
			size = (gajim.config.get('msgwin-width'),
				gajim.config.get('msgwin-height'))
		elif self.mode == self.ONE_MSG_WINDOW_PERACCT:
			size = (gajim.config.get_per('accounts', acct, 'msgwin-width'),
				gajim.config.get_per('accounts', acct, 'msgwin-height'))
		elif self.mode == self.ONE_MSG_WINDOW_PERTYPE:
			if type == message_control.TYPE_PM:
				type = message_control.TYPE_CHAT
			opt_width = type + '-msgwin-width'
			opt_height = type + '-msgwin-height'
			size = (gajim.config.get(opt_width),
					gajim.config.get(opt_height))
		else:
			return

		gtkgui_helpers.resize_window(win.window, size[0], size[1])
	
	def _position_window(self, win, acct, type):
		'''Moves window according to config settings'''
		if not gajim.config.get('saveposition') or self.mode == self.ONE_MSG_WINDOW_NEVER:
			return

		pos = (-1, -1)  # default is left up to the native window manager
		if self.mode == self.ONE_MSG_WINDOW_ALWAYS:
			pos = (gajim.config.get('msgwin-x-position'),
				gajim.config.get('msgwin-y-position'))
		elif self.mode == self.ONE_MSG_WINDOW_PERACCT:
			pos = (gajim.config.get_per('accounts', acct, 'msgwin-x-position'),
				gajim.config.get_per('accounts', acct, 'msgwin-y-position'))
		elif self.mode == self.ONE_MSG_WINDOW_PERTYPE:
			pos = (gajim.config.get(type + '-msgwin-x-position'),
				gajim.config.get(type + '-msgwin-y-position'))

		if pos[0] > 0 and pos[1] > 0:
			gtkgui_helpers.move_window(win.window, pos[0], pos[1])

	def _mode_to_key(self, contact, acct, type):
		if self.mode == self.ONE_MSG_WINDOW_NEVER:
			key = acct + contact.jid
		elif self.mode == self.ONE_MSG_WINDOW_ALWAYS:
			key = self.MAIN_WIN
		elif self.mode == self.ONE_MSG_WINDOW_PERACCT:
			key = acct
		elif self.mode == self.ONE_MSG_WINDOW_PERTYPE:
			key = type
		return key

	def create_window(self, contact, acct, type):
		key = None
		win_acct = None
		win_type = None

		key = self._mode_to_key(contact, acct, type)
		if self.mode == self.ONE_MSG_WINDOW_PERACCT:
			win_acct = acct
		elif self.mode == self.ONE_MSG_WINDOW_PERTYPE:
			win_type = type

		win = None
		try:
			win = self._windows[key]
		except KeyError:
			win = self._new_window(win_acct, win_type)

		# Position and size window based on saved state and window mode
		if not self.one_window_opened(contact, acct, type):
			self._position_window(win, acct, type)
			self._size_window(win, acct, type)

		self._windows[key] = win
		return win

	def _on_window_delete(self, win, event):
		self.save_state(self._gtk_win_to_msg_win(win))
		gajim.interface.save_config()
		return False

	def _on_window_destroy(self, win):
		for k in self._windows.keys():
			if self._windows[k].window == win:
				del self._windows[k]
				return

	def get_control(self, jid, acct):
		'''Amongst all windows, return the MessageControl for jid'''
		win = self.get_window(jid, acct)
		if win:
			return win.get_control(jid, acct)
		return None

	def get_controls(self, type):
		# FIXME: Optionally accept an account arg
		ctrls = []
		for c in self.controls():
			if c.type_id == type:
				ctrls.append(c)
		return ctrls

	def windows(self):
		for w in self._windows.values():
			yield w
	def controls(self):
		for w in self._windows.values():
			for c in w.controls():
				yield c

	def shutdown(self):
		for w in self.windows():
			self.save_state(w)
			w.window.hide()
			w.window.destroy()
		gajim.interface.save_config()

	def save_state(self, msg_win):
		if not gajim.config.get('saveposition'):
			return
		
		# Save window size and postion
		pos_x_key = 'msgwin-x-position'
		pos_y_key = 'msgwin-y-position'
		size_width_key = 'msgwin-width'
		size_height_key = 'msgwin-height'

		acct = None
		x, y = msg_win.window.get_position()
		width, height = msg_win.window.get_size()

		# If any of these values seem bogus don't update.
		if x < 0 or y < 0 or width < 0 or height < 0:
			return

		if self.mode == self.ONE_MSG_WINDOW_NEVER:
			# Use whatever is current to not overwrite the 'always' settings
			# when going from never->always
			x = y = -1
		elif self.mode == self.ONE_MSG_WINDOW_PERACCT:
			acct = msg_win.account
		elif self.mode == self.ONE_MSG_WINDOW_PERTYPE:
			type = msg_win.type
			pos_x_key = type + "-msgwin-x-position"
			pos_y_key = type + "-msgwin-y-position"
			size_width_key = type + "-msgwin-width"
			size_height_key = type + "-msgwin-height"

		if acct:
			if x >= 0 and y >= 0:
				gajim.config.set_per('accounts', acct, pos_x_key, x)
				gajim.config.set_per('accounts', acct, pos_y_key, y)
			gajim.config.set_per('accounts', acct, size_width_key, width)
			gajim.config.set_per('accounts', acct, size_height_key, height)
		else:
			if x >= 0 and y >= 0:
				gajim.config.set(pos_x_key, x)
				gajim.config.set(pos_y_key, y)
			gajim.config.set(size_width_key, width)
			gajim.config.set(size_height_key, height)

	def reconfig(self):
		for w in self.windows():
			self.save_state(w)
		gajim.interface.save_config()
		# Map the mode to a int constant for frequent compares
		mode = gajim.config.get('one_message_window')
		if self.mode == common.config.opt_one_window_types.index(mode):
			# No change
			return
		self.mode = common.config.opt_one_window_types.index(mode)

		controls = []
		for w in self.windows():
			w.window.hide()
			while w.notebook.get_n_pages():
				page = w.notebook.get_nth_page(0)
				ctrl = w._widget_to_control(page)
				w.notebook.remove_page(0)
				page.unparent()
				controls.append(ctrl)
			# Must clear _controls from window to prevent MessageControl.shutdown calls
			w._controls = {}
			w.window.destroy()

		self._windows = {}

		for ctrl in controls:
			mw = self.get_window(ctrl.contact.jid, ctrl.account)
			if not mw:
				mw = self.create_window(ctrl.contact, ctrl.account, ctrl.type_id)
			ctrl.parent_win = mw
			mw.new_tab(ctrl)
