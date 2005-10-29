##	message_textview.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Nikos Kouremenos <kourem@gmail.com>
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
import gobject

class MessageTextView(gtk.TextView):
	__gsignals__ = dict(
		mykeypress = (gobject.SIGNAL_RUN_LAST | gobject.SIGNAL_ACTION,
				None, # return value
				(str, int, gtk.gdk.ModifierType ) # arguments
			)
		)
		
	def __init__(self):
		self.set_left_margin(2)
		self.set_right_margin(2)
		self.set_pixels_above_lines(2)
		self.set_pixels_below_lines(2)

if gobject.pygtk_version < (2, 8, 0):
	gobject.type_register(MessageTextView)


# We register depending on keysym and modifier some bindings
# but we also pass those as param so we can construct fake Event

# CTRL + SHIFT + TAB
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.ISO_Left_Tab,
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.ISO_Left_Tab,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# CTRL + TAB
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Tab, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Tab,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# CTRL + PAGE DOWN
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Page_Down, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Page_Down,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# SHIFT + PAGE DOWN
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Page_Down, 
	gtk.gdk.SHIFT_MASK, 'mykeypress', int, gtk.keysyms.Page_Down,
	gtk.gdk.ModifierType, gtk.gdk.SHIFT_MASK)

# CTRL + PAGE UP
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Page_Up,
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Page_Up,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# SHIFT + PAGE UP
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Page_Up, 
	gtk.gdk.SHIFT_MASK, 'mykeypress', int, gtk.keysyms.Page_Up,
	gtk.gdk.ModifierType, gtk.gdk.SHIFT_MASK)

# CTRL + UP
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Up, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Up,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# CTRL + DOWN
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Down, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Down,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# ENTER
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Return, 
	0, 'mykeypress', int, gtk.keysyms.Return,
	gtk.gdk.ModifierType, 0)

# Ctrl+Enter
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.Return, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.Return,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)

# Keypad Enter
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.KP_Enter, 
	0, 'mykeypress', int, gtk.keysyms.KP_Enter,
	gtk.gdk.ModifierType, 0)

# Ctrl+ Keypad Enter
gtk.binding_entry_add_signal(MessageTextView, gtk.keysyms.KP_Enter, 
	gtk.gdk.CONTROL_MASK, 'mykeypress', int, gtk.keysyms.KP_Enter,
	gtk.gdk.ModifierType, gtk.gdk.CONTROL_MASK)
