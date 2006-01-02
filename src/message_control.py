##	message_control.py
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

from common import gajim

# Derived types MUST register their type IDs here if custom behavor is required
TYPE_CHAT = 'chat'
TYPE_GC = 'gc'
TYPE_PM = 'pm'

####################
# FIXME: Can't this stuff happen once?
from common import i18n
_ = i18n._
APP = i18n.APP

GTKGUI_GLADE = 'gtkgui.glade'
####################

class MessageControl:
	'''An abstract base widget that can embed in the gtk.Notebook of a MessageWindow'''

	def __init__(self, type_id, parent_win, widget_name, display_name, contact, account):
		self.type_id = type_id
		self.parent_win = parent_win
		self.widget_name = widget_name
		self.display_name = display_name
		self.contact = contact
		self.account = account
		self.compact_view_always = False
		self.compact_view_current = False
		self.nb_unread = 0
		self.print_time_timeout_id = None
		# FIXME: Make this a member
		gajim.last_message_time[self.account][contact.jid] = 0

		self.xml = gtk.glade.XML(GTKGUI_GLADE, widget_name, APP)
		self.widget = self.xml.get_widget(widget_name)
		# Autoconnect glade signals
		self.xml.signal_autoconnect(self)

	def set_control_active(self, state):
		'''Called when the control becomes active (state is True)
		or inactive (state is False)'''
		pass  # Derived types MUST implement this method

	def shutdown(self):
		# NOTE: Derived classes MUST implement this
		assert(False)
	def draw_widgets(self):
		pass # NOTE: Derived classes SHOULD implement this
	def repaint_themed_widgets(self, theme):
		pass # NOTE: Derived classes SHOULD implement this
	def update_state(self):
		pass # NOTE: Derived classes SHOULD implement this
	def toggle_emoticons(self):
		pass # NOTE: Derived classes MAY implement this
	def update_font(self):
		pass # NOTE: Derived classes SHOULD implement this
	def update_tags(self):
		pass # NOTE: Derived classes SHOULD implement this
	def print_time_timeout(self, arg):
		# NOTE: Derived classes SHOULD implement this
		if self.print_time_timeout_id:
			gobject.source_remove(self.print_time_timeout_id)
			del self.print_time_timeout_id
		return False
	def markup_tab_label(self, label_str, chatstate):
		# NOTE: Derived classes SHOULD implement this
		# Reurn a markup'd label and optional gtk.Color
		return (label_str, None)
	def prepare_context_menu(self):
		# NOTE: Derived classes SHOULD implement this
		return None
	def set_compact_view(self, state):
		# NOTE: Derived classes MAY implement this
		self.compact_view_current = state
	def allow_shutdown(self):
		'''Called to check is a control is allowed to shutdown.
		If a control is not in a suitable shutdown state this method
		should return False'''
		# NOTE: Derived classes MAY implement this
		return True

	def save_var(self, jid):
		'''When called, the derived type should serialize it's state in the form of a
		name/value (i.e. dict) result.
		the return value must be compatible with wthe one given to load_var'''
		pass # Derived classes SHOULD implement this
	def load_var(self, jid, var):
		pass # Derived classes SHOULD implement this

	def send_message(self, message, keyID = '', type = 'chat', chatstate = None):
		'''Send the given message to the active tab'''
		# refresh timers
		self.reset_kbd_mouse_timeout_vars()

		jid = self.contact.jid
		# Send and update history
		gajim.connections[self.account].send_message(jid, message, keyID,
						type = type, chatstate = chatstate)

	def position_menu_under_button(self, menu):
		#FIXME: BUG http://bugs.gnome.org/show_bug.cgi?id=316786
		# pass btn instance when this bug is over
		button = self.button_clicked
		# here I get the coordinates of the button relative to
		# window (self.window)
		button_x, button_y = button.allocation.x, button.allocation.y
		
		# now convert them to X11-relative
		window_x, window_y = self.parent_win.get_origin()
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

