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

	def __init__(self, acct, type):
		self._controls = {}
		# If None, the window is not tied to any specific account
		self.account = acct
		# If None, the window is not tied to any specific type
		self.type = type

		self.widget_name = 'message_window'
		self.xml = gtk.glade.XML(GTKGUI_GLADE, self.widget_name, APP)
		self.window = self.xml.get_widget(self.widget_name)
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

		# Connect event handling for this Window
		self.window.connect('delete-event', self._on_window_delete)
		self.window.connect('destroy', self._on_window_destroy)
		self.window.connect('focus-in-event', self._on_window_focus)

		self.window.show_all()

	def _on_window_focus(self, widget, event):
		# window received focus, so if we had urgency REMOVE IT
		# NOTE: we do not have to read the message (it maybe in a bg tab)
		# to remove urgency hint so this functions does that
		if gtk.gtk_version >= (2, 8, 0) and gtk.pygtk_version >= (2, 8, 0):
			if widget.props.urgency_hint:
				widget.props.urgency_hint = False

		ctl = self.get_active_control()
		if ctl:
			ctl.set_control_active(True)
			# Undo "unread" state display, etc.
			if ctl.type_id == message_control.TYPE_GC:
				self.redraw_tab(ctl.contact, 'active')
			else:
				# NOTE: we do not send any chatstate to preserve
				# inactive, gone, etc.
				self.redraw_tab(ctl.contact)

	def _on_window_delete(self, win, event):
		# Make sure all controls are okay with being deleted
		for ctl in self._controls.values():
			if not ctl.allow_shutdown():
				return True # halt the delete
		return False

	def _on_window_destroy(self, win):
		for ctl in self._controls.values():
			ctl.shutdown()
		self._controls.clear()

	def new_tab(self, control):
		assert(not self._controls.has_key(control.contact.jid))
		self._controls[control.contact.jid] = control
		if len(self._controls) > 1:
			self.notebook.set_show_tabs(True)
			self.alignment.set_property('top-padding', 2)

		# Connect to keyboard events
		#if isinstance(control, ChatControlBase):
		#	control.msg_textview.connect('mykeypress',
		#				self._on_message_textview_mykeypress_event)

		# Add notebook page and connect up to the tab's close button
		xml = gtk.glade.XML(GTKGUI_GLADE, 'chat_tab_ebox', APP)
		tab_label_box = xml.get_widget('chat_tab_ebox')
		xml.signal_connect('on_close_button_clicked', self.on_close_button_clicked,
					control.contact)
		xml.signal_connect('on_tab_eventbox_button_press_event',
				self.on_tab_eventbox_button_press_event, control.widget)
		self.notebook.append_page(control.widget, tab_label_box)


		self.redraw_tab(control.contact)
		control.draw_widgets()
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
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.ISO_Left_Tab: # CTRL + SHIFT + TAB
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.Page_Down: # CTRL + PAGE DOWN
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.Page_Up: # CTRL + PAGE UP
				self.notebook.emit('key_press_event', event)

	def on_close_button_clicked(self, button, contact):
		'''When close button is pressed: close a tab'''
		self.remove_tab(contact)

	def show_title(self, urgent = True, control = None):
		'''redraw the window's title'''
		unread = 0
		for ctl in self._controls.values():
			unread += ctl.nb_unread
		unread_str = ''
		if unread > 1:
			unread_str = '[' + unicode(unread) + '] '
		elif unread == 1:
			unread_str = '* '

		if not control:
			control = self.get_active_control()
		if control.type_id == message_control.TYPE_GC:
			title = control.room_jid
		elif control.contact.name:
			title = control.contact.name
		else:
			title = control.contact.jid

		title = unread_str + title
		self.window.set_title(title)

		if urgent:
			gtkgui_helpers.set_unset_urgency_hint(self.window, unread)

	def set_active_tab(self, jid):
		ctl = self._controls[jid]
		ctl_page = self.notebook.page_num(ctl.widget)
		self.notebook.set_current_page(ctl_page)
	
	def remove_tab(self, contact):
		# Shutdown the MessageControl
		ctl = self.get_control(contact.jid)
		if not ctl.allow_shutdown():
			return
		ctl.shutdown()

		# Update external state
		if gajim.interface.systray_enabled:
			gajim.interface.systray.remove_jid(contact.jid, ctl.account,
								ctl.type_id)
		del gajim.last_message_time[ctl.account][ctl.contact.jid]

		self.notebook.remove_page(self.notebook.page_num(ctl.widget))

		del self._controls[contact.jid]
		if len(self._controls) == 1: # we are going from two tabs to one
			show_tabs_if_one_tab = gajim.config.get('tabs_always_visible')
			self.notebook.set_show_tabs(show_tabs_if_one_tab)
			if not show_tabs_if_one_tab:
				self.alignment.set_property('top-padding', 0)
			self.show_title()
		elif len(self._controls) == 0:
			# FIXME: These are not called when the window is destroyed like this, fake it
			gajim.interface.msg_win_mgr._on_window_delete(self.window, None)
			gajim.interface.msg_win_mgr._on_window_destroy(self.window)
			self.window.destroy()

	def redraw_tab(self, contact, chatstate = None):
		ctl = self._controls[contact.jid]
		ctl.update_state()

		hbox = self.notebook.get_tab_label(ctl.widget).get_children()[0]
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
		(tab_label_str, tab_label_color) = ctl.get_tab_label(chatstate)
		nick_label.set_markup(tab_label_str)
		if tab_label_color:
			nick_label.modify_fg(gtk.STATE_NORMAL, tab_label_color)
			nick_label.modify_fg(gtk.STATE_ACTIVE, tab_label_color)

		tab_img = ctl.get_tab_image()
		if tab_img:
			if tab_img.get_storage_type() == gtk.IMAGE_ANIMATION:
				status_img.set_from_animation(tab_img.get_animation())
			else:
				status_img.set_from_pixbuf(tab_img.get_pixbuf())

	def repaint_themed_widgets(self):
		'''Repaint controls in the window with theme color'''
		# iterate through controls and repaint
		for ctl in self._controls.values():
			ctl.repaint_themed_widgets()

	def _widget_to_control(self, widget):
		for ctl in self._controls.values():
			if ctl.widget == widget:
				return ctl
		return None

	def get_active_control(self):
		notebook = self.notebook
		active_widget = notebook.get_nth_page(notebook.get_current_page())
		return self._widget_to_control(active_widget)
	def get_active_contact(self):
		ctl = self.get_active_control()
		if ctl:
			return ctl.contact
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
		for ctl in self._controls.values():
			ctl.toggle_emoticons()
	def update_font(self):
		for ctl in self._controls.values():
			ctl.update_font()
	def update_tags(self):
		for ctl in self._controls.values():
			ctl.update_tags()

	def get_control(self, key):
		'''Return the MessageControl for jid or n, where n is the notebook page index'''
		if isinstance(key, unicode):
			jid = key
			for ctl in self._controls.values():
				if ctl.contact.jid == jid:
					return ctl
			return None
		else:
			page_num = key
			notebook = self.notebook
			if page_num == None:
				page_num = notebook.get_current_page()
			nth_child = notebook.get_nth_page(page_num)
			return self._widget_to_control(nth_child)

	def controls(self):
		for ctl in self._controls.values():
			yield ctl

	def update_print_time(self):
		if gajim.config.get('print_time') != 'sometimes':
			for ctl in self.controls():
				if ctl.print_time_timeout_id:
					gobject.source_remove(ctl.print_time_timeout_id)
					del ctl.print_time_timeout_id
		else:
			for ctl in self.controls():
				if not ctl.print_time_timeout_id:
					ctl.print_time_timeout()
					ctl.print_time_timeout_id = gobject.timeout_add(300000,
						ctl.print_time_timeout, None)

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
			ctl = self.get_control(ind)
			if ctl.nb_unread > 0:
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
		if len(self._controls) > 1: # if there is more than one tab
			menu.append(gtk.SeparatorMenuItem()) # seperator
			for ctl in self._controls.values():
				jid = ctl.contact.jid
				if jid != self.get_active_jid():
					item = gtk.ImageMenuItem(_('Switch to %s') %\
							ctl.contact.name)
					img = gtk.image_new_from_stock(gtk.STOCK_JUMP_TO,
									gtk.ICON_SIZE_MENU)
					item.set_image(img)
					item.connect('activate',
						lambda obj, jid:self.set_active_tab(jid), jid)
					menu.append(item)
		# show the menu
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()

	def _on_notebook_switch_page(self, notebook, page, page_num):
		old_no = notebook.get_current_page()
		old_ctl = self._widget_to_control(notebook.get_nth_page(old_no))
		old_ctl.set_control_active(False)
		
		new_ctl = self._widget_to_control(notebook.get_nth_page(page_num))
		new_ctl.set_control_active(True)
		self.show_title(control = new_ctl)

	def _on_notebook_key_press(self, widget, event):
		st = '1234567890' # alt+1 means the first tab (tab 0)
		ctl = self.get_active_control()
		contact = ctl.contact
		jid = ctl.contact.jid

		# CTRL mask
		if event.state & gtk.gdk.CONTROL_MASK:
			# Tab switch bindings
			if event.keyval == gtk.keysyms.ISO_Left_Tab: # CTRL + SHIFT + TAB
				self.move_to_next_unread_tab(False)
			elif event.keyval == gtk.keysyms.Tab: # CTRL + TAB
				self.move_to_next_unread_tab(True)
			elif event.keyval == gtk.keysyms.Page_Down or\
			event.keyval == gtk.keysyms.Page_Up: # CTRL + PAGE UP|DOWN
				# construct event instance from binding
				event = gtk.gdk.Event(gtk.gdk.KEY_PRESS)
				event.keyval = event_keyval
				event.state = event_keymod
				event.time = 0 # assign current time
				self.notebook.emit('key_press_event', event)
			elif event.keyval == gtk.keysyms.F4: # CTRL + F4
				self.remove_tab(contact)
			elif event.keyval == gtk.keysyms.w: # CTRL + W
				self.remove_tab(contact)

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
				ctl.set_compact_view(not ctl.compact_view_current)
		# Close tab bindings
		elif event.keyval == gtk.keysyms.Escape: # ESCAPE
			if ctl.type_id == message_control.TYPE_CHAT:
				self.remove_tab(contact)

################################################################################
class MessageWindowMgr:
	'''A manager and factory for MessageWindow objects'''

	# These constants map to common.config.opt_one_window_types indices
	CONFIG_NEVER   = 0
	CONFIG_ALWAYS  = 1
	CONFIG_PERACCT = 2
	CONFIG_PERTYPE = 3
	# A key constant for the main window for all messages
	MAIN_WIN = 'main'

	def __init__(self):
		''' A dictionary of windows; the key depends on the config:
		 CONFIG_NEVER: The key is the contact JID
		 CONFIG_ALWAYS: The key is MessageWindowMgr.MAIN_WIN 
		 CONFIG_PERACCT: The key is the account name
		 CONFIG_PERTYPE: The key is a message type constant'''
		self._windows = {}
		# Map the mode to a int constant for frequent compares
		mode = gajim.config.get('one_message_window')
		self.mode = common.config.opt_one_window_types.index(mode)
		assert(self.mode != -1)
	
	def _new_window(self, acct, type):
		win = MessageWindow(acct, type)
		# we track the lifetime of this window
		win.window.connect('delete-event', self._on_window_delete)
		win.window.connect('destroy', self._on_window_destroy)
		return win

	def _gtk_win_to_msg_win(self, gtk_win):
		for w in self._windows.values():
			if w.window == gtk_win:
				return w
		return None

	def get_window(self, jid):
		for win in self._windows.values():
			if win.get_control(jid):
				return win
		return None
	def has_window(self, jid):
		return self.get_window(jid)

	def one_window_opened(self, contact, acct, type):
		return self._windows[self._mode_to_key(contact, acct, type)] != None

	def _size_window(self, win, acct, type):
		'''Returns the size tuple: (width, height)'''
		size = None
		if not gajim.config.get('saveposition'):
			size = (common.config.DEFAULT_WINDOW_WIDTH,
				common.config.DEFAULT_WINDOW_HEIGHT)
		else:
			if self.mode == self.CONFIG_NEVER or self.mode == self.CONFIG_ALWAYS:
				size = (gajim.config.get('msgwin-width'),
					gajim.config.get('msgwin-height'))
			elif self.mode == self.CONFIG_PERACCT:
				size = (gajim.config.get_per('msgwin-width', acct),
					gajim.config.get_per('msgwin-height', acct))
			elif self.mode == self.CONFIG_PERTYPE:
				if type == message_control.TYPE_PM:
					type = message_control.TYPE_CHAT
				opt_width = type + '-msgwin-width'
				opt_height = type + '-msgwin-height'
				size = (gajim.config.get(opt_width),
					gajim.config.get(opt_height))
		print "Window size:", size
		gtkgui_helpers.resize_window(win.window, size[0], size[1])
	
	def _position_window(self, win, acct, type):
		'''Returns the position tuple: (x, y)'''
		if not gajim.config.get('saveposition') or self.mode == self.CONFIG_NEVER:
			return

		pos = (-1, -1)  # default is left up to the native window manager
		if self.mode == self.CONFIG_ALWAYS:
			pos = (gajim.config.get('msgwin-x-position'),
				gajim.config.get('msgwin-y-position'))
		elif self.mode == self.CONFIG_PERACCT:
			pos = (gajim.config.get_per('msgwin-x-position', acct),
				gajim.config.get_per('msgwin-y-position', acct))
		elif self.mode == self.CONFIG_PERTYPE:
			pos = (gajim.config.get(type + '-msgwin-x-position'),
				gajim.config.get(type + '-msgwin-y-position'))

		print "Window position:", pos
		if pos[0] != -1 and pos[1] != -1:
			gtkgui_helpers.move_window(win.window, pos[0], pos[1])

	def _mode_to_key(self, contact, acct, type):
		if self.mode == self.CONFIG_NEVER:
			key = contact.jid
		elif self.mode == self.CONFIG_ALWAYS:
			key = self.MAIN_WIN
		elif self.mode == self.CONFIG_PERACCT:
			key = acct
		elif self.mode == self.CONFIG_PERTYPE:
			key = type

	def create_window(self, contact, acct, type):
		key = None
		win_acct = None
		win_type = None

		key = self._mode_to_key(contact, acct, type)
		if self.mode == self.CONFIG_PERACCT:
			win_acct = acct
		elif self.mode == self.CONFIG_PERTYPE:
			win_type = type

		win = None
		try:
			win = self._windows[key]
		except KeyError:
			win = self._new_window(win_acct, win_type)
			self._windows[key] = win

		# Postion and size window based on saved state and window mode
		self._position_window(win, acct, type)
		self._size_window(win, acct, type)
		return win

	def _on_window_delete(self, win, event):
		if not gajim.config.get('saveposition'):
			return False
		msg_win = self._gtk_win_to_msg_win(win)
		
		# Save widnow size and postion
		pos_x_key = 'msgwin-x-position'
		pos_y_key = 'msgwin-y-position'
		size_width_key = 'msgwin-width'
		size_height_key = 'msgwin-height'

		acct = None
		x, y = win.get_position()
		width, height = win.get_size()

		if self.mode == self.CONFIG_NEVER:
			x = y = -1
		elif self.mode == self.CONFIG_PERACCT:
			acct = msg_win.account
		elif self.mode == self.CONFIG_PERTYPE:
			type = msg_win.type_id
			pos_x_key = type + "-msgwin-x-position"
			pos_y_key = type + "-msgwin-y-position"
			size_width_key = type + "-msgwin-width"
			size_height_key = type + "-msgwin-height"

		print "saving acct:", acct
		print "saving %s=%d" % (pos_x_key, x)
		print "saving %s=%d" % (pos_y_key, y)
		print "saving %s=%d" % (size_width_key, width)
		print "saving %s=%d" % (size_height_key, height)
		if acct:
			gajim.config.set_per(pos_x_key, x, acct)
			gajim.config.set_per(pos_y_key, y, acct)
			gajim.config.set_per(size_width_key, width, acct)
			gajim.config.set_per(size_height_key, height, acct)
		else:
			gajim.config.set(pos_x_key, x)
			gajim.config.set(pos_y_key, y)
			gajim.config.set(size_width_key, width)
			gajim.config.set(size_height_key, height)

		return False

	def _on_window_destroy(self, win):
		for k in self._windows.keys():
			if self._windows[k].window == win:
				del self._windows[k]
				return

	def get_control(self, jid):
		'''Amongst all windows, return the MessageControl for jid'''
		win = self.get_window(jid)
		if win:
			return win.get_control(jid)
		return None

	def get_controls(self, type):
		ctls = []
		for c in self.controls():
			if c.type_id == type:
				ctls.append(c)
		return ctls

	def windows(self):
		for w in self._windows.values():
			yield w
	def controls(self):
		for w in self._windows.values():
			for c in w.controls():
				yield c

