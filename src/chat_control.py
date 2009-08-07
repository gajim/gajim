# -*- coding:utf-8 -*-
## src/chat_control.py
##
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2008 Yann Leboulanger <asterix AT lagaule.org>
##                         Jean-Marie Traissard <jim AT lapin.org>
##                         Nikos Kouremenos <kourem AT gmail.com>
##                         Travis Shirk <travis AT pobox.com>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Brendan Taylor <whateley AT gmail.com>
##                         Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import os
import time
import gtk
import pango
import gobject
import gtkgui_helpers
import message_control
import dialogs
import history_window
import notify
import re

from common import gajim
from common import helpers
from common import exceptions
from message_control import MessageControl
from conversation_textview import ConversationTextview
from message_textview import MessageTextView
from common.contacts import GC_Contact
from common.logger import constants
from common.pep import MOODS, ACTIVITIES
from common.xmpp.protocol import NS_XHTML, NS_XHTML_IM, NS_FILE, NS_MUC
from common.xmpp.protocol import NS_RECEIPTS, NS_ESESSION

try:
	import gtkspell
	HAS_GTK_SPELL = True
except ImportError:
	HAS_GTK_SPELL = False

# the next script, executed in the "po" directory,
# generates the following list.
##!/bin/sh
#LANG=$(for i in *.po; do j=${i/.po/}; echo -n "_('"$j"')":" '"$j"', " ; done)
#echo "{_('en'):'en'",$LANG"}"
langs = {_('English'): 'en', _('Belarusian'): 'be', _('Bulgarian'): 'bg', _('Breton'): 'br', _('Czech'): 'cs', _('German'): 'de', _('Greek'): 'el', _('British'): 'en_GB', _('Esperanto'): 'eo', _('Spanish'): 'es', _('Basque'): 'eu', _('French'): 'fr', _('Croatian'): 'hr', _('Italian'): 'it', _('Norwegian (b)'): 'nb', _('Dutch'): 'nl', _('Norwegian'): 'no', _('Polish'): 'pl', _('Portuguese'): 'pt', _('Brazilian Portuguese'): 'pt_BR', _('Russian'): 'ru', _('Serbian'): 'sr', _('Slovak'): 'sk', _('Swedish'): 'sv', _('Chinese (Ch)'): 'zh_CN'}

################################################################################
class ChatControlBase(MessageControl):
	'''A base class containing a banner, ConversationTextview, MessageTextView
	'''
	def make_href(self, match):
		url_color = gajim.config.get('urlmsgcolor')
		return '<a href="%s"><span color="%s">%s</span></a>' % (match.group(),
			url_color, match.group())

	def get_font_attrs(self):
		''' get pango font attributes for banner from theme settings '''
		theme = gajim.config.get('roster_theme')
		bannerfont = gajim.config.get_per('themes', theme, 'bannerfont')
		bannerfontattrs = gajim.config.get_per('themes', theme, 'bannerfontattrs')

		if bannerfont:
			font = pango.FontDescription(bannerfont)
		else:
			font = pango.FontDescription('Normal')
		if bannerfontattrs:
			# B attribute is set by default
			if 'B' in bannerfontattrs:
				font.set_weight(pango.WEIGHT_HEAVY)
			if 'I' in bannerfontattrs:
				font.set_style(pango.STYLE_ITALIC)

		font_attrs = 'font_desc="%s"' % font.to_string()

		# in case there is no font specified we use x-large font size
		if font.get_size() == 0:
			font_attrs = '%s size="x-large"' % font_attrs
		font.set_weight(pango.WEIGHT_NORMAL)
		font_attrs_small = 'font_desc="%s" size="small"' % font.to_string()
		return (font_attrs, font_attrs_small)

	def get_nb_unread(self):
		jid = self.contact.jid
		if self.resource:
			jid += '/' + self.resource
		type_ = self.type_id
		return len(gajim.events.get_events(self.account, jid, ['printed_' + type_,
			type_]))

	def draw_banner(self):
		'''Draw the fat line at the top of the window that
		houses the icon, jid, ...
		'''
		self.draw_banner_text()
		self._update_banner_state_image()
		# Derived types MAY implement this

	def draw_banner_text(self):
		pass # Derived types SHOULD implement this

	def update_ui(self):
		self.draw_banner()
		# Derived types SHOULD implement this

	def repaint_themed_widgets(self):
		self._paint_banner()
		self.draw_banner()
		# Derived classes MAY implement this

	def _update_banner_state_image(self):
		pass # Derived types MAY implement this

	def handle_message_textview_mykey_press(self, widget, event_keyval,
	event_keymod):
		# Derived should implement this rather than connecting to the event
		# itself.
		pass

	def status_url_clicked(self, widget, url):
		helpers.launch_browser_mailer('url', url)

	def __init__(self, type_id, parent_win, widget_name, contact, acct,
	resource = None):
		if resource is None:
			# We very likely got a contact with a random resource.
			# This is bad, we need the highest for caps etc.
			c = gajim.contacts.get_contact_with_highest_priority(
				acct, contact.jid)
			if c and not isinstance(c, GC_Contact):
				contact = c

		MessageControl.__init__(self, type_id, parent_win, widget_name,
			contact, acct, resource = resource)

		widget = self.xml.get_widget('history_button')
		id_ = widget.connect('clicked', self._on_history_menuitem_activate)
		self.handlers[id_] = widget

		# when/if we do XHTML we will put formatting buttons back
		widget = self.xml.get_widget('emoticons_button')
		id_ = widget.connect('clicked', self.on_emoticons_button_clicked)
		self.handlers[id_] = widget

		# Create banner and connect signals
		widget = self.xml.get_widget('banner_eventbox')
		id_ = widget.connect('button-press-event',
			self._on_banner_eventbox_button_press_event)
		self.handlers[id_] = widget

		self.urlfinder = re.compile(
			r"(www\.(?!\.)|[a-z][a-z0-9+.-]*://)[^\s<>'\"]+[^!,\.\s<>\)'\"\]]")

		if gajim.HAVE_PYSEXY:
			import sexy
			self.banner_status_label = sexy.UrlLabel()
			self.banner_status_label.connect('url_activated',
				self.status_url_clicked)
		else:
			self.banner_status_label = gtk.Label()
		self.banner_status_label.set_selectable(True)
		self.banner_status_label.set_alignment(0,0.5)
		self.banner_status_label.connect('populate_popup',
			self.on_banner_label_populate_popup)

		banner_vbox = self.xml.get_widget('banner_vbox')
		banner_vbox.pack_start(self.banner_status_label)
		self.banner_status_label.show()

		# Init DND
		self.TARGET_TYPE_URI_LIST = 80
		self.dnd_list = [ ( 'text/uri-list', 0, self.TARGET_TYPE_URI_LIST ),
				('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_APP, 0)]
		id_ = self.widget.connect('drag_data_received',
			self._on_drag_data_received)
		self.handlers[id_] = self.widget
		self.widget.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
			gtk.DEST_DEFAULT_HIGHLIGHT |
			gtk.DEST_DEFAULT_DROP,
			self.dnd_list, gtk.gdk.ACTION_COPY)

		# Create textviews and connect signals
		self.conv_textview = ConversationTextview(self.account)
		id_ = self.conv_textview.connect('quote', self.on_quote)
		self.handlers[id_] = self.conv_textview.tv
		id_ = self.conv_textview.tv.connect('key_press_event',
			self._conv_textview_key_press_event)
		self.handlers[id_] = self.conv_textview.tv
		# FIXME: DND on non editable TextView, find a better way
		self.drag_entered = False
		id_ = self.conv_textview.tv.connect('drag_data_received',
			self._on_drag_data_received)
		self.handlers[id_] = self.conv_textview.tv
		id_ = self.conv_textview.tv.connect('drag_motion', self._on_drag_motion)
		self.handlers[id_] = self.conv_textview.tv
		id_ = self.conv_textview.tv.connect('drag_leave', self._on_drag_leave)
		self.handlers[id_] = self.conv_textview.tv
		self.conv_textview.tv.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
			gtk.DEST_DEFAULT_HIGHLIGHT |
			gtk.DEST_DEFAULT_DROP,
			self.dnd_list, gtk.gdk.ACTION_COPY)

		self.conv_scrolledwindow = self.xml.get_widget(
			'conversation_scrolledwindow')
		self.conv_scrolledwindow.add(self.conv_textview.tv)
		widget = self.conv_scrolledwindow.get_vadjustment()
		id_ = widget.connect('value-changed',
			self.on_conversation_vadjustment_value_changed)
		self.handlers[id_] = widget
		id_ = widget.connect('changed',
			self.on_conversation_vadjustment_changed)
		self.handlers[id_] = widget
		self.scroll_to_end_id = None
		self.was_at_the_end = True

		# add MessageTextView to UI and connect signals
		self.msg_scrolledwindow = self.xml.get_widget('message_scrolledwindow')
		self.msg_textview = MessageTextView()
		id_ = self.msg_textview.connect('mykeypress',
			self._on_message_textview_mykeypress_event)
		self.handlers[id_] = self.msg_textview
		self.msg_scrolledwindow.add(self.msg_textview)
		id_ = self.msg_textview.connect('key_press_event',
			self._on_message_textview_key_press_event)
		self.handlers[id_] = self.msg_textview
		id_ = self.msg_textview.connect('size-request', self.size_request)
		self.handlers[id_] = self.msg_textview
		id_ = self.msg_textview.connect('populate_popup',
			self.on_msg_textview_populate_popup)
		self.handlers[id_] = self.msg_textview
		# Setup DND
		id_ = self.msg_textview.connect('drag_data_received',
			self._on_drag_data_received)
		self.handlers[id_] = self.msg_textview
		self.msg_textview.drag_dest_set(gtk.DEST_DEFAULT_MOTION |
			gtk.DEST_DEFAULT_HIGHLIGHT,
			self.dnd_list, gtk.gdk.ACTION_COPY)

		self.update_font()

		# Hook up send button
		widget = self.xml.get_widget('send_button')
		id_ = widget.connect('clicked', self._on_send_button_clicked)
		self.handlers[id_] = widget

		widget = self.xml.get_widget('formattings_button')
		id_ = widget.connect('clicked', self.on_formattings_button_clicked)
		self.handlers[id_] = widget

		# the following vars are used to keep history of user's messages
		self.sent_history = []
		self.sent_history_pos = 0
		self.orig_msg = None

		# Emoticons menu
		# set image no matter if user wants at this time emoticons or not
		# (so toggle works ok)
		img = self.xml.get_widget('emoticons_button_image')
		img.set_from_file(os.path.join(gajim.DATA_DIR, 'emoticons', 'static',
			'smile.png'))
		self.toggle_emoticons()

		# Attach speller
		if gajim.config.get('use_speller') and HAS_GTK_SPELL:
			self.set_speller()
		self.conv_textview.tv.show()
		self._paint_banner()

		# For XEP-0172
		self.user_nick = None

		self.smooth = True
		self.msg_textview.grab_focus()

	def set_speller(self):
		try:
			lang = gajim.config.get('speller_language')
			if not lang:
				lang = gajim.LANG
			spell = gtkspell.Spell(self.msg_textview, lang)
			# loop removing non-existant dictionaries
			# iterating on a copy
			for lang in dict(langs):
				try:
					spell.set_language(langs[lang])
				except OSError:
					del langs[lang]
			# now set the one the user selected
			per_type = 'contacts'
			if self.type_id == message_control.TYPE_GC:
				per_type = 'rooms'
			lang = gajim.config.get_per(per_type, self.contact.jid,
				'speller_language')
			if not lang:
				# use the default one
				lang = gajim.config.get('speller_language')
			if lang:
				self.msg_textview.lang = lang
				spell.set_language(lang)
		except (gobject.GError, RuntimeError, TypeError, OSError):
			dialogs.AspellDictError(lang)

	def on_banner_label_populate_popup(self, label, menu):
		'''We override the default context menu and add our own menutiems'''
		item = gtk.SeparatorMenuItem()
		menu.prepend(item)

		menu2 = self.prepare_context_menu()
		i = 0
		for item in menu2:
			menu2.remove(item)
			menu.prepend(item)
			menu.reorder_child(item, i)
			i += 1
		menu.show_all()

	def on_msg_textview_populate_popup(self, textview, menu):
		'''we override the default context menu and we prepend an option to switch
		languages'''
		def _on_select_dictionary(widget, lang):
			per_type = 'contacts'
			if self.type_id == message_control.TYPE_GC:
				per_type = 'rooms'
			if not gajim.config.get_per(per_type, self.contact.jid):
				gajim.config.add_per(per_type, self.contact.jid)
			gajim.config.set_per(per_type, self.contact.jid, 'speller_language',
				lang)
			spell = gtkspell.get_from_text_view(self.msg_textview)
			self.msg_textview.lang = lang
			spell.set_language(lang)
			widget.set_active(True)

		item = gtk.SeparatorMenuItem()
		menu.prepend(item)

		item = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
		menu.prepend(item)
		id_ = item.connect('activate', self.msg_textview.clear)
		self.handlers[id_] = item

		if gajim.config.get('use_speller') and HAS_GTK_SPELL:
			item = gtk.MenuItem(_('Spelling language'))
			menu.prepend(item)
			submenu = gtk.Menu()
			item.set_submenu(submenu)
			for lang in sorted(langs):
				item = gtk.CheckMenuItem(lang)
				if langs[lang] == self.msg_textview.lang:
					item.set_active(True)
				submenu.append(item)
				id_ = item.connect('activate', _on_select_dictionary, langs[lang])
				self.handlers[id_] = item

		menu.show_all()

	def on_quote(self, widget, text):
		text = '>' + text.replace('\n', '\n>') + '\n'
		message_buffer = self.msg_textview.get_buffer()
		message_buffer.insert_at_cursor(text)

	# moved from ChatControl
	def _on_banner_eventbox_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3: # right click
			self.parent_win.popup_menu(event)

	def _on_send_button_clicked(self, widget):
		'''When send button is pressed: send the current message'''
		if gajim.connections[self.account].connected < 2: # we are not connected
			dialogs.ErrorDialog(_('A connection is not available'),
				_('Your message can not be sent until you are connected.'))
			return
		message_buffer = self.msg_textview.get_buffer()
		start_iter = message_buffer.get_start_iter()
		end_iter = message_buffer.get_end_iter()
		message = message_buffer.get_text(start_iter, end_iter, 0).decode('utf-8')
		xhtml = self.msg_textview.get_xhtml()

		# send the message
		self.send_message(message, xhtml=xhtml)

	def _paint_banner(self):
		'''Repaint banner with theme color'''
		theme = gajim.config.get('roster_theme')
		bgcolor = gajim.config.get_per('themes', theme, 'bannerbgcolor')
		textcolor = gajim.config.get_per('themes', theme, 'bannertextcolor')
		# the backgrounds are colored by using an eventbox by
		# setting the bg color of the eventbox and the fg of the name_label
		banner_eventbox = self.xml.get_widget('banner_eventbox')
		banner_name_label = self.xml.get_widget('banner_name_label')
		self.disconnect_style_event(banner_name_label)
		self.disconnect_style_event(self.banner_status_label)
		if bgcolor:
			banner_eventbox.modify_bg(gtk.STATE_NORMAL,
				gtk.gdk.color_parse(bgcolor))
			default_bg = False
		else:
			default_bg = True
		if textcolor:
			banner_name_label.modify_fg(gtk.STATE_NORMAL,
				gtk.gdk.color_parse(textcolor))
			self.banner_status_label.modify_fg(gtk.STATE_NORMAL,
				gtk.gdk.color_parse(textcolor))
			default_fg = False
		else:
			default_fg = True
		if default_bg or default_fg:
			self._on_style_set_event(banner_name_label, None, default_fg,
				default_bg)
			if self.banner_status_label.flags() & gtk.REALIZED:
				# Widget is realized
				self._on_style_set_event(self.banner_status_label, None, default_fg,
					default_bg)

	def disconnect_style_event(self, widget):
		# Try to find the event_id
		for id_ in self.handlers.keys():
			if self.handlers[id_] == widget:
				widget.disconnect(id_)
				del self.handlers[id_]
				break

	def connect_style_event(self, widget, set_fg = False, set_bg = False):
		self.disconnect_style_event(widget)
		id_ = widget.connect('style-set', self._on_style_set_event, set_fg,
			set_bg)
		self.handlers[id_] = widget

	def _on_style_set_event(self, widget, style, *opts):
		'''set style of widget from style class *.Frame.Eventbox
			opts[0] == True -> set fg color
			opts[1] == True -> set bg color'''
		banner_eventbox = self.xml.get_widget('banner_eventbox')
		self.disconnect_style_event(widget)
		if opts[1]:
			bg_color = widget.style.bg[gtk.STATE_SELECTED]
			banner_eventbox.modify_bg(gtk.STATE_NORMAL, bg_color)
		if opts[0]:
			fg_color = widget.style.fg[gtk.STATE_SELECTED]
			widget.modify_fg(gtk.STATE_NORMAL, fg_color)
		self.connect_style_event(widget, opts[0], opts[1])

	def _conv_textview_key_press_event(self, widget, event):
		if (event.state & gtk.gdk.CONTROL_MASK and event.keyval in (gtk.keysyms.c,
		gtk.keysyms.Insert)) or (event.state & gtk.gdk.SHIFT_MASK and \
		event.keyval in (gtk.keysyms.Page_Down, gtk.keysyms.Page_Up)):
			return False
		self.parent_win.notebook.emit('key_press_event', event)
		return True

	def show_emoticons_menu(self):
		if not gajim.config.get('emoticons_theme'):
			return
		def set_emoticons_menu_position(w, msg_tv = self.msg_textview):
			window = msg_tv.get_window(gtk.TEXT_WINDOW_WIDGET)
			# get the window position
			origin = window.get_origin()
			size = window.get_size()
			buf = msg_tv.get_buffer()
			# get the cursor position
			cursor = msg_tv.get_iter_location(buf.get_iter_at_mark(
				buf.get_insert()))
			cursor = msg_tv.buffer_to_window_coords(gtk.TEXT_WINDOW_TEXT,
				cursor.x, cursor.y)
			x = origin[0] + cursor[0]
			y = origin[1] + size[1]
			menu_height = gajim.interface.emoticons_menu.size_request()[1]
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
		gajim.interface.emoticon_menuitem_clicked = self.append_emoticon
		gajim.interface.emoticons_menu.popup(None, None,
			set_emoticons_menu_position, 1, 0)

	def _on_message_textview_key_press_event(self, widget, event):
		# Ctrl [+ Shift] + Tab are not forwarded to notebook. We handle it here
		if self.widget_name == 'muc_child_vbox':
			if event.keyval not in (gtk.keysyms.ISO_Left_Tab, gtk.keysyms.Tab):
				self.last_key_tabs = False
		if event.state & gtk.gdk.SHIFT_MASK:
			# CTRL + SHIFT + TAB
			if event.state & gtk.gdk.CONTROL_MASK and \
					event.keyval == gtk.keysyms.ISO_Left_Tab:
				self.parent_win.move_to_next_unread_tab(False)
				return True
			# SHIFT + PAGE_[UP|DOWN]: send to conv_textview
			elif event.keyval == gtk.keysyms.Page_Down or \
					event.keyval == gtk.keysyms.Page_Up:
				self.conv_textview.tv.emit('key_press_event', event)
				return True
		elif event.state & gtk.gdk.CONTROL_MASK:
			if event.keyval == gtk.keysyms.Tab: # CTRL + TAB
				self.parent_win.move_to_next_unread_tab(True)
				return True
		return False

	def _on_message_textview_mykeypress_event(self, widget, event_keyval,
		event_keymod):
		'''When a key is pressed:
		if enter is pressed without the shift key, message (if not empty) is sent
		and printed in the conversation'''

		# NOTE: handles mykeypress which is custom signal connected to this
		# CB in new_tab(). for this singal see message_textview.py
		message_textview = widget
		message_buffer = message_textview.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()
		message = message_buffer.get_text(start_iter, end_iter, False).decode(
			'utf-8')
		xhtml = self.msg_textview.get_xhtml()

		# construct event instance from binding
		event = gtk.gdk.Event(gtk.gdk.KEY_PRESS) # it's always a key-press here
		event.keyval = event_keyval
		event.state = event_keymod
		event.time = 0 # assign current time

		if event.keyval == gtk.keysyms.Up:
			if event.state & gtk.gdk.CONTROL_MASK: # Ctrl+UP
				self.sent_messages_scroll('up', widget.get_buffer())
		elif event.keyval == gtk.keysyms.Down:
			if event.state & gtk.gdk.CONTROL_MASK: # Ctrl+Down
				self.sent_messages_scroll('down', widget.get_buffer())
		elif event.keyval == gtk.keysyms.Return or \
			event.keyval == gtk.keysyms.KP_Enter: # ENTER
			# NOTE: SHIFT + ENTER is not needed to be emulated as it is not
			# binding at all (textview's default action is newline)

			if gajim.config.get('send_on_ctrl_enter'):
				# here, we emulate GTK default action on ENTER (add new line)
				# normally I would add in keypress but it gets way to complex
				# to get instant result on changing this advanced setting
				if event.state == 0: # no ctrl, no shift just ENTER add newline
					end_iter = message_buffer.get_end_iter()
					message_buffer.insert_at_cursor('\n')
					send_message = False
				elif event.state & gtk.gdk.CONTROL_MASK: # CTRL + ENTER
					send_message = True
			else: # send on Enter, do newline on Ctrl Enter
				if event.state & gtk.gdk.CONTROL_MASK: # Ctrl + ENTER
					end_iter = message_buffer.get_end_iter()
					message_buffer.insert_at_cursor('\n')
					send_message = False
				else: # ENTER
					send_message = True

			if gajim.connections[self.account].connected < 2 and send_message:
				# we are not connected
				dialogs.ErrorDialog(_('A connection is not available'),
					_('Your message can not be sent until you are connected.'))
				send_message = False

			if send_message:
				self.send_message(message, xhtml=xhtml) # send the message
		else:
			# Give the control itself a chance to process
			self.handle_message_textview_mykey_press(widget, event_keyval,
				event_keymod)

	def _on_drag_data_received(self, widget, context, x, y, selection,
		target_type, timestamp):
		pass # Derived classes SHOULD implement this method

	def _on_drag_leave(self, widget, context, time):
		# FIXME: DND on non editable TextView, find a better way
		self.drag_entered = False
		self.conv_textview.tv.set_editable(False)

	def _on_drag_motion(self, widget, context, x, y, time):
		# FIXME: DND on non editable TextView, find a better way
		if not self.drag_entered:
			# We drag new data over the TextView, make it editable to catch dnd
			self.drag_entered_conv = True
			self.conv_textview.tv.set_editable(True)

	def _process_command(self, message):
		if not message or message[0] != '/':
			return False

		message = message[1:]
		message_array = message.split(' ', 1)
		command = message_array.pop(0).lower()
		if message_array == ['']:
			message_array = []

		if command == 'clear' and not len(message_array):
			self.conv_textview.clear() # clear conversation
			self.clear(self.msg_textview) # clear message textview too
			return True
		elif message == 'compact' and not len(message_array):
			self.chat_buttons_set_visible(not self.hide_chat_buttons)
			self.clear(self.msg_textview)
			return True
		return False

	def send_message(self, message, keyID='', type_='chat', chatstate=None,
	msg_id=None, composing_xep=None, resource=None, process_command=True,
	xhtml=None, callback=None, callback_args=[]):
		'''Send the given message to the active tab. Doesn't return None if error
		'''
		if not message or message == '\n':
			return None

		if not process_command or not self._process_command(message):
			MessageControl.send_message(self, message, keyID, type_=type_,
				chatstate=chatstate, msg_id=msg_id, composing_xep=composing_xep,
				resource=resource, user_nick=self.user_nick, xhtml=xhtml,
				callback=callback, callback_args=callback_args)

			# Record message history
			self.save_sent_message(message)

			# Be sure to send user nickname only once according to JEP-0172
			self.user_nick = None

		# Clear msg input
		message_buffer = self.msg_textview.get_buffer()
		message_buffer.set_text('') # clear message buffer (and tv of course)

	def save_sent_message(self, message):
		# save the message, so user can scroll though the list with key up/down
		size = len(self.sent_history)
		# we don't want size of the buffer to grow indefinately
		max_size = gajim.config.get('key_up_lines')
		if size >= max_size:
			for i in xrange(0, size - 1):
				self.sent_history[i] = self.sent_history[i + 1]
			self.sent_history[max_size - 1] = message
			# self.sent_history_pos has changed if we browsed sent_history,
			# reset to real value
			self.sent_history_pos = max_size
		else:
			self.sent_history.append(message)
			self.sent_history_pos = size + 1
		self.orig_msg = None

	def print_conversation_line(self, text, kind, name, tim,
	other_tags_for_name=[], other_tags_for_time=[], other_tags_for_text=[],
	count_as_new=True, subject=None, old_kind=None, xhtml=None, simple=False, xep0184_id = None):
		'''prints 'chat' type messages'''
		jid = self.contact.jid
		full_jid = self.get_full_jid()
		textview = self.conv_textview
		end = False
		if self.was_at_the_end or kind == 'outgoing':
			end = True
		textview.print_conversation_line(text, jid, kind, name, tim,
			other_tags_for_name, other_tags_for_time, other_tags_for_text,
			subject, old_kind, xhtml, simple=simple)

		if xep0184_id is not None:
			textview.show_xep0184_warning(xep0184_id)

		if not count_as_new:
			return
		if kind == 'incoming':
			if not self.type_id == message_control.TYPE_GC or \
			gajim.config.get('notify_on_all_muc_messages') or \
			'marked' in other_tags_for_text:
				# it's a normal message, or a muc message with want to be
				# notified about if quitting just after
				# other_tags_for_text == ['marked'] --> highlighted gc message
				gajim.last_message_time[self.account][full_jid] = time.time()

		if kind in ('incoming', 'incoming_queue', 'error'):
			gc_message = False
			if self.type_id == message_control.TYPE_GC:
				gc_message = True

			if ((self.parent_win and (not self.parent_win.get_active_control() or \
			self != self.parent_win.get_active_control() or \
			not self.parent_win.is_active() or not end)) or \
			(gc_message and \
			jid in gajim.interface.minimized_controls[self.account])) and \
			kind in ('incoming', 'incoming_queue', 'error'):
				# we want to have save this message in events list
				# other_tags_for_text == ['marked'] --> highlighted gc message
				if gc_message:
					if 'marked' in other_tags_for_text:
						type_ = 'printed_marked_gc_msg'
					else:
						type_ = 'printed_gc_msg'
					event = 'gc_message_received'
				else:
					type_ = 'printed_' + self.type_id
					event = 'message_received'
				show_in_roster = notify.get_show_in_roster(event,
					self.account, self.contact, self.session)
				show_in_systray = notify.get_show_in_systray(event,
					self.account, self.contact, type_)

				event = gajim.events.create_event(type_, (self,),
					show_in_roster = show_in_roster,
					show_in_systray = show_in_systray)
				gajim.events.add_event(self.account, full_jid, event)
				# We need to redraw contact if we show in roster
				if show_in_roster:
					gajim.interface.roster.draw_contact(self.contact.jid,
						self.account)

		if not self.parent_win:
			return

		if (not self.parent_win.get_active_control() or \
		self != self.parent_win.get_active_control() or \
		not self.parent_win.is_active() or not end) and \
		kind in ('incoming', 'incoming_queue', 'error'):
			self.parent_win.redraw_tab(self)
			if not self.parent_win.is_active():
				self.parent_win.show_title(True, self) # Enabled Urgent hint
			else:
				self.parent_win.show_title(False, self) # Disabled Urgent hint

	def toggle_emoticons(self):
		'''hide show emoticons_button and make sure emoticons_menu is always there
		when needed'''
		emoticons_button = self.xml.get_widget('emoticons_button')
		if gajim.config.get('emoticons_theme'):
			emoticons_button.show()
			emoticons_button.set_no_show_all(False)
		else:
			emoticons_button.hide()
			emoticons_button.set_no_show_all(True)

	def append_emoticon(self, str_):
		buffer_ = self.msg_textview.get_buffer()
		if buffer_.get_char_count():
			buffer_.insert_at_cursor(' %s ' % str_)
		else: # we are the beginning of buffer
			buffer_.insert_at_cursor('%s ' % str_)
		self.msg_textview.grab_focus()

	def on_emoticons_button_clicked(self, widget):
		'''popup emoticons menu'''
		gajim.interface.emoticon_menuitem_clicked = self.append_emoticon
		gajim.interface.popup_emoticons_under_button(widget, self.parent_win)

	def on_formattings_button_clicked(self, widget):
		'''popup formattings menu'''
		menu = gtk.Menu()

		menuitems = ((_('Bold'), 'bold'),
		(_('Italic'), 'italic'),
		(_('Underline'), 'underline'),
		(_('Strike'), 'strike'))

		active_tags = self.msg_textview.get_active_tags()

		for menuitem in menuitems:
			item = gtk.CheckMenuItem(menuitem[0])
			if menuitem[1] in active_tags:
				item.set_active(True)
			else:
				item.set_active(False)
			item.connect('activate', self.msg_textview.set_tag,
				menuitem[1])
			menu.append(item)

		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		item = gtk.ImageMenuItem(_('Color'))
		icon = gtk.image_new_from_stock(gtk.STOCK_SELECT_COLOR, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		item.connect('activate', self.on_color_menuitem_activale)
		menu.append(item)

		item = gtk.ImageMenuItem(_('Font'))
		icon = gtk.image_new_from_stock(gtk.STOCK_SELECT_FONT, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		item.connect('activate', self.on_font_menuitem_activale)
		menu.append(item)

		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		item = gtk.ImageMenuItem(_('Clear formating'))
		icon = gtk.image_new_from_stock(gtk.STOCK_CLEAR, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		item.connect('activate', self.msg_textview.clear_tags)
		menu.append(item)

		menu.show_all()
		gtkgui_helpers.popup_emoticons_under_button(menu, widget,
			self.parent_win)

	def on_color_menuitem_activale(self, widget):
		color_dialog = gtk.ColorSelectionDialog('Select a color')
		color_dialog.connect('response', self.msg_textview.color_set,
			color_dialog.colorsel)
		color_dialog.show_all()

	def on_font_menuitem_activale(self, widget):
		font_dialog = gtk.FontSelectionDialog('Select a font')
		font_dialog.connect('response', self.msg_textview.font_set,
			font_dialog.fontsel)
		font_dialog.show_all()


	def on_actions_button_clicked(self, widget):
		'''popup action menu'''
		menu = self.prepare_context_menu(True)
		menu.show_all()
		gtkgui_helpers.popup_emoticons_under_button(menu, widget,
			self.parent_win)

	def update_font(self):
		font = pango.FontDescription(gajim.config.get('conversation_font'))
		self.conv_textview.tv.modify_font(font)
		self.msg_textview.modify_font(font)

	def update_tags(self):
		self.conv_textview.update_tags()

	def clear(self, tv):
		buffer_ = tv.get_buffer()
		start, end = buffer_.get_bounds()
		buffer_.delete(start, end)

	def _on_history_menuitem_activate(self, widget = None, jid = None):
		'''When history menuitem is pressed: call history window'''
		if not jid:
			jid = self.contact.jid

		if 'logs' in gajim.interface.instances:
			gajim.interface.instances['logs'].window.present()
			gajim.interface.instances['logs'].open_history(jid, self.account)
		else:
			gajim.interface.instances['logs'] = \
				history_window.HistoryWindow(jid, self.account)

	def _on_send_file(self, gc_contact=None):
		'''gc_contact can be set when we are in a groupchat control'''
		def _on_ok(c):
			gajim.interface.instances['file_transfers'].show_file_send_request(
				self.account, c)
		if self.TYPE_ID == message_control.TYPE_PM:
			gc_contact = self.gc_contact
		if gc_contact:
			# gc or pm
			gc_control = gajim.interface.msg_win_mgr.get_gc_control(
				gc_contact.room_jid, self.account)
			self_contact = gajim.contacts.get_gc_contact(self.account,
				gc_control.room_jid, gc_control.nick)
			if gc_control.is_anonymous and gc_contact.affiliation not in ['admin',
			'owner'] and self_contact.affiliation in ['admin', 'owner']:
				contact = gajim.contacts.get_contact(self.account, gc_contact.jid)
				if not contact or contact.sub not in ('both', 'to'):
					prim_text = _('Really send file?')
					sec_text = _('If you send a file to %s, he/she will know your '
						'real Jabber ID.') % gc_contact.name
					dialog = dialogs.NonModalConfirmationDialog(prim_text, sec_text,
						on_response_ok = (_on_ok, gc_contact))
					dialog.popup()
					return
			_on_ok(gc_contact)
			return
		_on_ok(self.contact)

	def on_minimize_menuitem_toggled(self, widget):
		'''When a grouchat is minimized, unparent the tab, put it in roster etc'''
		old_value = False
		minimized_gc = gajim.config.get_per('accounts', self.account,
			'minimized_gc').split()
		if self.contact.jid in minimized_gc:
			old_value = True
		minimize = widget.get_active()
		if minimize and not self.contact.jid in minimized_gc:
			minimized_gc.append(self.contact.jid)
		if not minimize and self.contact.jid in minimized_gc:
			minimized_gc.remove(self.contact.jid)
		if old_value != minimize:
			gajim.config.set_per('accounts', self.account, 'minimized_gc',
				' '.join(minimized_gc))

	def set_control_active(self, state):
		if state:
			jid = self.contact.jid
			if self.was_at_the_end:
				# we are at the end
				type_ = ['printed_' + self.type_id]
				if self.type_id == message_control.TYPE_GC:
					type_ = ['printed_gc_msg', 'printed_marked_gc_msg']
				if not gajim.events.remove_events(self.account, self.get_full_jid(),
				types = type_):
					# There were events to remove
					self.redraw_after_event_removed(jid)


	def bring_scroll_to_end(self, textview, diff_y = 0):
		''' scrolls to the end of textview if end is not visible '''
		if self.scroll_to_end_id:
			# a scroll is already planned
			return
		buffer_ = textview.get_buffer()
		end_iter = buffer_.get_end_iter()
		end_rect = textview.get_iter_location(end_iter)
		visible_rect = textview.get_visible_rect()
		# scroll only if expected end is not visible
		if end_rect.y >= (visible_rect.y + visible_rect.height + diff_y):
			self.scroll_to_end_id = gobject.idle_add(self.scroll_to_end_iter,
				textview)

	def scroll_to_end_iter(self, textview):
		buffer_ = textview.get_buffer()
		end_iter = buffer_.get_end_iter()
		textview.scroll_to_iter(end_iter, 0, False, 1, 1)
		self.scroll_to_end_id = None
		return False

	def size_request(self, msg_textview , requisition):
		''' When message_textview changes its size. If the new height
		will enlarge the window, enable the scrollbar automatic policy
		Also enable scrollbar automatic policy for horizontal scrollbar
		if message we have in message_textview is too big'''
		if msg_textview.window is None:
			return

		min_height = self.conv_scrolledwindow.get_property('height-request')
		conversation_height = self.conv_textview.tv.window.get_size()[1]
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
		diff_y = message_height - requisition.height
		if diff_y != 0:
			if conversation_height + diff_y < min_height:
				if message_height + conversation_height - min_height > min_height:
					policy = self.msg_scrolledwindow.get_property(
						'vscrollbar-policy')
					# scroll only when scrollbar appear
					if policy != gtk.POLICY_AUTOMATIC:
						self.msg_scrolledwindow.set_property('vscrollbar-policy',
							gtk.POLICY_AUTOMATIC)
						self.msg_scrolledwindow.set_property('height-request',
							message_height + conversation_height - min_height)
						self.bring_scroll_to_end(msg_textview)
			else:
				self.msg_scrolledwindow.set_property('vscrollbar-policy',
					gtk.POLICY_NEVER)
				self.msg_scrolledwindow.set_property('height-request', -1)
			self.conv_textview.bring_scroll_to_end(diff_y - 18, False)
		else:
			self.conv_textview.bring_scroll_to_end(diff_y - 18, self.smooth)
		self.smooth = True # reinit the flag
		# enable scrollbar automatic policy for horizontal scrollbar
		# if message we have in message_textview is too big
		if requisition.width > message_width:
			self.msg_scrolledwindow.set_property('hscrollbar-policy',
				gtk.POLICY_AUTOMATIC)
		else:
			self.msg_scrolledwindow.set_property('hscrollbar-policy',
				gtk.POLICY_NEVER)

		return True

	def on_conversation_vadjustment_changed(self, adjustment):
		# used to stay at the end of the textview when we shrink conversation
		# textview.
		if self.was_at_the_end:
			self.conv_textview.bring_scroll_to_end(-18)
		self.was_at_the_end = (adjustment.upper - adjustment.value - adjustment.page_size) < 18

	def on_conversation_vadjustment_value_changed(self, adjustment):
		# stop automatic scroll when we manually scroll
		if not self.conv_textview.auto_scrolling:
			self.conv_textview.stop_scrolling()
		self.was_at_the_end = (adjustment.upper - adjustment.value - adjustment.page_size) < 18
		if self.resource:
			jid = self.contact.get_full_jid()
		else:
			jid = self.contact.jid
		types_list = []
		type_ = self.type_id
		if type_ == message_control.TYPE_GC:
			type_ = 'gc_msg'
			types_list = ['printed_' + type_, type_, 'printed_marked_gc_msg']
		else: # Not a GC
			types_list = ['printed_' + type_, type_]

		if not len(gajim.events.get_events(self.account, jid, types_list)):
			return
		if not self.parent_win:
			return
		if self.conv_textview.at_the_end() and \
		self.parent_win.get_active_control() == self and \
		self.parent_win.window.is_active():
			# we are at the end
			if self.type_id == message_control.TYPE_GC:
				if not gajim.events.remove_events(self.account, jid,
				types=types_list):
					self.redraw_after_event_removed(jid)
			elif self.session and self.session.remove_events(types_list):
				# There were events to remove
				self.redraw_after_event_removed(jid)

	def redraw_after_event_removed(self, jid):
		''' We just removed a 'printed_*' event, redraw contact in roster or
		gc_roster and titles in	roster and msg_win '''
		self.parent_win.redraw_tab(self)
		self.parent_win.show_title()
		# TODO : get the contact and check notify.get_show_in_roster()
		if self.type_id == message_control.TYPE_PM:
			room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
			groupchat_control = gajim.interface.msg_win_mgr.get_gc_control(
				room_jid, self.account)
			if room_jid in gajim.interface.minimized_controls[self.account]:
				groupchat_control = \
					gajim.interface.minimized_controls[self.account][room_jid]
			contact = \
				gajim.contacts.get_contact_with_highest_priority(self.account, \
				room_jid)
			if contact:
				gajim.interface.roster.draw_contact(room_jid, self.account)
			if groupchat_control:
				groupchat_control.draw_contact(nick)
				if groupchat_control.parent_win:
					groupchat_control.parent_win.redraw_tab(groupchat_control)
		else:
			gajim.interface.roster.draw_contact(jid, self.account)
			gajim.interface.roster.show_title()

	def sent_messages_scroll(self, direction, conv_buf):
		size = len(self.sent_history)
		if self.orig_msg is None:
			# user was typing something and then went into history, so save
			# whatever is already typed
			start_iter = conv_buf.get_start_iter()
			end_iter = conv_buf.get_end_iter()
			self.orig_msg = conv_buf.get_text(start_iter, end_iter, 0).decode(
				'utf-8')
		if direction == 'up':
			if self.sent_history_pos == 0:
				return
			self.sent_history_pos = self.sent_history_pos - 1
			self.smooth = False
			conv_buf.set_text(self.sent_history[self.sent_history_pos])
		elif direction == 'down':
			if self.sent_history_pos >= size - 1:
				conv_buf.set_text(self.orig_msg)
				self.orig_msg = None
				self.sent_history_pos = size
				return

			self.sent_history_pos = self.sent_history_pos + 1
			self.smooth = False
			conv_buf.set_text(self.sent_history[self.sent_history_pos])

	def lighten_color(self, color):
		p = 0.4
		mask = 0
		color.red = int((color.red * p) + (mask * (1 - p)))
		color.green = int((color.green * p) + (mask * (1 - p)))
		color.blue = int((color.blue * p) + (mask * (1 - p)))
		return color

	def widget_set_visible(self, widget, state):
		'''Show or hide a widget. state is bool'''
		# make the last message visible, when changing to "full view"
		if not state:
			gobject.idle_add(self.conv_textview.scroll_to_end_iter)

		widget.set_no_show_all(state)
		if state:
			widget.hide()
		else:
			widget.show_all()

	def chat_buttons_set_visible(self, state):
		'''Toggle chat buttons. state is bool'''
		MessageControl.chat_buttons_set_visible(self, state)
		self.widget_set_visible(self.xml.get_widget('actions_hbox'), state)

	def got_connected(self):
		self.msg_textview.set_sensitive(True)
		self.msg_textview.set_editable(True)
		# FIXME: Set sensitivity for toolbar

	def got_disconnected(self):
		self.msg_textview.set_sensitive(False)
		self.msg_textview.set_editable(False)
		self.conv_textview.tv.grab_focus()

		self.no_autonegotiation = False
		# FIXME: Set sensitivity for toolbar

################################################################################
class ChatControl(ChatControlBase):
	'''A control for standard 1-1 chat'''
	TYPE_ID = message_control.TYPE_CHAT
	old_msg_kind = None # last kind of the printed message
	CHAT_CMDS = ['clear', 'compact', 'help', 'me', 'ping', 'say']

	def __init__(self, parent_win, contact, acct, session, resource = None):
		ChatControlBase.__init__(self, self.TYPE_ID, parent_win,
			'chat_child_vbox', contact, acct, resource)

		self.gpg_is_active = False
		# for muc use:
		# widget = self.xml.get_widget('muc_window_actions_button')
		self.actions_button = self.xml.get_widget('message_window_actions_button')
		id_ = self.actions_button.connect('clicked',
			self.on_actions_button_clicked)
		self.handlers[id_] = self.actions_button

		self._formattings_button = self.xml.get_widget('formattings_button')

		self._add_to_roster_button = self.xml.get_widget(
			'add_to_roster_button')
		id_ = self._add_to_roster_button.connect('clicked',
			self._on_add_to_roster_menuitem_activate)
		self.handlers[id_] = self._add_to_roster_button

		self._send_file_button = self.xml.get_widget('send_file_button')
		# add a special img for send file button
		path_to_upload_img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'upload.png')
		img = gtk.Image()
		img.set_from_file(path_to_upload_img)
		self._send_file_button.set_image(img)
		id_ = self._send_file_button.connect('clicked',
			self._on_send_file_menuitem_activate)
		self.handlers[id_] = self._send_file_button

		self._convert_to_gc_button = self.xml.get_widget(
			'convert_to_gc_button')
		id_ = self._convert_to_gc_button.connect('clicked',
			self._on_convert_to_gc_menuitem_activate)
		self.handlers[id_] = self._convert_to_gc_button

		contact_information_button = self.xml.get_widget(
			'contact_information_button')
		id_ = contact_information_button.connect('clicked',
			self._on_contact_information_menuitem_activate)
		self.handlers[id_] = contact_information_button

		compact_view = gajim.config.get('compact_view')
		self.chat_buttons_set_visible(compact_view)
		self.widget_set_visible(self.xml.get_widget('banner_eventbox'),
			gajim.config.get('hide_chat_banner'))

		self.authentication_button = self.xml.get_widget(
			'authentication_button')
		id_ = self.authentication_button.connect('clicked',
			self._on_authentication_button_clicked)
		self.handlers[id_] = self.authentication_button

		# Add lock image to show chat encryption
		self.lock_image = self.xml.get_widget('lock_image')
		self.lock_tooltip = gtk.Tooltips()

		# Convert to GC icon
		img = self.xml.get_widget('convert_to_gc_button_image')
		img.set_from_pixbuf(gtkgui_helpers.load_icon(
			'muc_active').get_pixbuf())

		self.update_toolbar()

		self._mood_image = self.xml.get_widget('mood_image')
		self._activity_image = self.xml.get_widget('activity_image')
		self._tune_image = self.xml.get_widget('tune_image')

		self.update_mood()
		self.update_activity()
		self.update_tune()

		# keep timeout id and window obj for possible big avatar
		# it is on enter-notify and leave-notify so no need to be
		# per jid
		self.show_bigger_avatar_timeout_id = None
		self.bigger_avatar_window = None
		self.show_avatar(self.contact.resource)

		# chatstate timers and state
		self.reset_kbd_mouse_timeout_vars()
		self._schedule_activity_timers()

		# Hook up signals
		id_ = self.parent_win.window.connect('motion-notify-event',
			self._on_window_motion_notify)
		self.handlers[id_] = self.parent_win.window
		message_tv_buffer = self.msg_textview.get_buffer()
		id_ = message_tv_buffer.connect('changed',
			self._on_message_tv_buffer_changed)
		self.handlers[id_] = message_tv_buffer

		widget = self.xml.get_widget('avatar_eventbox')
		widget.set_property('height-request', gajim.config.get(
			'chat_avatar_height'))
		id_ = widget.connect('enter-notify-event',
			self.on_avatar_eventbox_enter_notify_event)
		self.handlers[id_] = widget

		id_ = widget.connect('leave-notify-event',
			self.on_avatar_eventbox_leave_notify_event)
		self.handlers[id_] = widget

		id_ = widget.connect('button-press-event',
			self.on_avatar_eventbox_button_press_event)
		self.handlers[id_] = widget

		if not session:
			session = gajim.connections[self.account]. \
				find_controlless_session(self.contact.jid)
			if session:
				# Don't use previous session if we want to a specific resource
				# and it's not the same
				r = gajim.get_room_and_nick_from_fjid(str(session.jid))[1]
				if resource and resource != r:
					session = None

		if session:
			session.control = self
			self.session = session

			if session.enable_encryption:
				self.print_esession_details()

		# Enable encryption if needed
		self.no_autonegotiation = False
		e2e_is_active = self.session and self.session.enable_encryption
		gpg_pref = gajim.config.get_per('contacts', contact.jid,
			'gpg_enabled')

		# try GPG first
		if not e2e_is_active and gpg_pref and \
		gajim.config.get_per('accounts', self.account, 'keyid') and \
		gajim.connections[self.account].USE_GPG:
			self.gpg_is_active = True
			gajim.encrypted_chats[self.account].append(contact.jid)
			msg = _('GPG encryption enabled')
			ChatControlBase.print_conversation_line(self, msg,
				'status', '', None)

			if self.session:
				self.session.loggable = gajim.config.get_per('accounts',
					self.account, 'log_encrypted_sessions')
			# GPG is always authenticated as we use GPG's WoT
			self._show_lock_image(self.gpg_is_active, 'GPG', self.gpg_is_active,
				self.session and self.session.is_loggable(), True)

		self.status_tooltip = gtk.Tooltips()

		self.update_ui()
		# restore previous conversation
		self.restore_conversation()
		self.msg_textview.grab_focus()

	def update_toolbar(self):
		# Formatting
		if gajim.capscache.is_supported(self.contact, NS_XHTML_IM) \
		and not gajim.capscache.is_supported(self.contact, 'notexistant') \
		and not self.gpg_is_active:
			self._formattings_button.set_sensitive(True)
		else:
			self._formattings_button.set_sensitive(False)

		# Add to roster
		if not isinstance(self.contact, GC_Contact) \
		and _('Not in Roster') in self.contact.groups:
			self._add_to_roster_button.show()
		else:
			self._add_to_roster_button.hide()

		# Send file
		if gajim.capscache.is_supported(self.contact, NS_FILE) and \
		self.contact.resource:
			self._send_file_button.set_sensitive(True)
		else:
			self._send_file_button.set_sensitive(False)
			if not gajim.capscache.is_supported(self.contact, NS_FILE):
				self._send_file_button.set_tooltip_text(_(
					"This contact does not support file transfer."))
			else:
				self._send_file_button.set_tooltip_text(
					_("You need to know the real JID of the contact to send him or "
					"her a file."))

		# Convert to GC
		if gajim.capscache.is_supported(self.contact, NS_MUC):
			self._convert_to_gc_button.set_sensitive(True)
		else:
			self._convert_to_gc_button.set_sensitive(False)

	def update_mood(self):
		mood = None
		text = None

		if isinstance(self.contact, GC_Contact):
			return

		if 'mood' in self.contact.mood:
			mood = self.contact.mood['mood'].strip()
		if 'text' in self.contact.mood:
			text = self.contact.mood['text'].strip()

		if mood is not None:
			if mood in MOODS:
				self._mood_image.set_from_pixbuf(gtkgui_helpers.load_mood_icon(
						mood).get_pixbuf())
				# Translate standard moods
				mood = MOODS[mood]
			else:
				self._mood_image.set_from_pixbuf(gtkgui_helpers.load_mood_icon(
					'unknown').get_pixbuf())

			mood = gobject.markup_escape_text(mood)

			tooltip = '<b>%s</b>' % mood
			if text:
				text = gobject.markup_escape_text(text)
				tooltip += '\n' + text
			self._mood_image.set_tooltip_markup(tooltip)
			self._mood_image.show()
		else:
			self._mood_image.hide()

	def update_activity(self):
		activity = None
		subactivity = None
		text = None

		if isinstance(self.contact, GC_Contact):
			return

		if 'activity' in self.contact.activity:
			activity = self.contact.activity['activity'].strip()
		if 'subactivity' in self.contact.activity:
			subactivity = self.contact.activity['subactivity'].strip()
		if 'text' in self.contact.activity:
			text = self.contact.activity['text'].strip()

		if activity is not None:
			if activity in ACTIVITIES:
				# Translate standard activities
				if subactivity in ACTIVITIES[activity]:
					self._activity_image.set_from_pixbuf(
						gtkgui_helpers.load_activity_icon(activity, subactivity). \
						get_pixbuf())
					subactivity = ACTIVITIES[activity][subactivity]
				else:
					self._activity_image.set_from_pixbuf(
						gtkgui_helpers.load_activity_icon(activity).get_pixbuf())
				activity = ACTIVITIES[activity]['category']
			else:
				self._activity_image.set_from_pixbuf(
					gtkgui_helpers.load_activity_icon('unknown').get_pixbuf())

			# Translate standard subactivities

			tooltip = '<b>' + gobject.markup_escape_text(activity)
			if subactivity:
				tooltip += ': ' + gobject.markup_escape_text(subactivity)
			tooltip += '</b>'
			if text:
				tooltip += '\n' + gobject.markup_escape_text(text)
			self._activity_image.set_tooltip_markup(tooltip)

			self._activity_image.show()
		else:
			self._activity_image.hide()

	def update_tune(self):
		artist = None
		title = None
		source = None

		if isinstance(self.contact, GC_Contact):
			return

		if 'artist' in self.contact.tune:
			artist = self.contact.tune['artist'].strip()
			artist = gobject.markup_escape_text(artist)
		if 'title' in self.contact.tune:
			title = self.contact.tune['title'].strip()
			title = gobject.markup_escape_text(title)
		if 'source' in self.contact.tune:
			source = self.contact.tune['source'].strip()
			source = gobject.markup_escape_text(source)

		if artist or title:
			if not artist:
				artist = _('Unknown Artist')
			if not title:
				title = _('Unknown Title')
			if not source:
				source = _('Unknown Source')

			self._tune_image.set_tooltip_markup(
				_('<b>"%(title)s"</b> by <i>%(artist)s</i>\n'
				'from <i>%(source)s</i>') % {'title': title, 'artist': artist,
				'source': source})
			self._tune_image.show()
		else:
			self._tune_image.hide()

	def on_avatar_eventbox_enter_notify_event(self, widget, event):
		'''
		we enter the eventbox area so we under conditions add a timeout
		to show a bigger avatar after 0.5 sec
		'''
		jid = self.contact.jid
		is_fake = False
		if self.type_id == message_control.TYPE_PM:
			is_fake = True
		avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid,
			is_fake)
		if avatar_pixbuf in ('ask', None):
			return
		avatar_w = avatar_pixbuf.get_width()
		avatar_h = avatar_pixbuf.get_height()

		scaled_buf = self.xml.get_widget('avatar_image').get_pixbuf()
		scaled_buf_w = scaled_buf.get_width()
		scaled_buf_h = scaled_buf.get_height()

		# do we have something bigger to show?
		if avatar_w > scaled_buf_w or avatar_h > scaled_buf_h:
			# wait for 0.5 sec in case we leave earlier
			self.show_bigger_avatar_timeout_id = gobject.timeout_add(500,
				self.show_bigger_avatar, widget)

	def on_avatar_eventbox_leave_notify_event(self, widget, event):
		'''we left the eventbox area that holds the avatar img'''
		# did we add a timeout? if yes remove it
		if self.show_bigger_avatar_timeout_id is not None:
			gobject.source_remove(self.show_bigger_avatar_timeout_id)

	def on_avatar_eventbox_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3: # right click
			menu = gtk.Menu()
			menuitem = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS)
			id_ = menuitem.connect('activate',
				gtkgui_helpers.on_avatar_save_as_menuitem_activate,
				self.contact.jid, self.account, self.contact.get_shown_name() + \
					'.jpeg')
			self.handlers[id_] = menuitem
			menu.append(menuitem)
			menu.show_all()
			menu.connect('selection-done', lambda w:w.destroy())
			# show the menu
			menu.show_all()
			menu.popup(None, None, None, event.button, event.time)
		return True

	def _on_window_motion_notify(self, widget, event):
		'''it gets called no matter if it is the active window or not'''
		if self.parent_win.get_active_jid() == self.contact.jid:
			# if window is the active one, change vars assisting chatstate
			self.mouse_over_in_last_5_secs = True
			self.mouse_over_in_last_30_secs = True

	def _schedule_activity_timers(self):
		self.possible_paused_timeout_id = gobject.timeout_add_seconds(5,
			self.check_for_possible_paused_chatstate, None)
		self.possible_inactive_timeout_id = gobject.timeout_add_seconds(30,
			self.check_for_possible_inactive_chatstate, None)

	def update_ui(self):
		# The name banner is drawn here
		ChatControlBase.update_ui(self)
		self.update_toolbar()

	def _update_banner_state_image(self):
		contact = gajim.contacts.get_contact_with_highest_priority(self.account,
			self.contact.jid)
		if not contact or self.resource:
			# For transient contacts
			contact = self.contact
		show = contact.show
		jid = contact.jid

		# Set banner image
		img_32 = gajim.interface.roster.get_appropriate_state_images(jid,
			size = '32', icon_name = show)
		img_16 = gajim.interface.roster.get_appropriate_state_images(jid,
			icon_name = show)
		if show in img_32 and img_32[show].get_pixbuf():
			# we have 32x32! use it!
			banner_image = img_32[show]
			use_size_32 = True
		else:
			banner_image = img_16[show]
			use_size_32 = False

		banner_status_img = self.xml.get_widget('banner_status_image')
		if banner_image.get_storage_type() == gtk.IMAGE_ANIMATION:
			banner_status_img.set_from_animation(banner_image.get_animation())
		else:
			pix = banner_image.get_pixbuf()
			if pix is not None:
				if use_size_32:
					banner_status_img.set_from_pixbuf(pix)
				else: # we need to scale 16x16 to 32x32
					scaled_pix = pix.scale_simple(32, 32,
									gtk.gdk.INTERP_BILINEAR)
					banner_status_img.set_from_pixbuf(scaled_pix)

	def draw_banner_text(self):
		'''Draw the text in the fat line at the top of the window that
		houses the name, jid.
		'''
		contact = self.contact
		jid = contact.jid

		banner_name_label = self.xml.get_widget('banner_name_label')
		banner_name_tooltip = gtk.Tooltips()

		name = contact.get_shown_name()
		if self.resource:
			name += '/' + self.resource
		if self.TYPE_ID == message_control.TYPE_PM:
			name = _('%(nickname)s from group chat %(room_name)s') %\
				{'nickname': name, 'room_name': self.room_name}
		name = gobject.markup_escape_text(name)

		# We know our contacts nick, but if another contact has the same nick
		# in another account we need to also display the account.
		# except if we are talking to two different resources of the same contact
		acct_info = ''
		for account in gajim.contacts.get_accounts():
			if account == self.account:
				continue
			if acct_info: # We already found a contact with same nick
				break
			for jid in gajim.contacts.get_jid_list(account):
				other_contact_ = \
					gajim.contacts.get_first_contact_from_jid(account, jid)
				if other_contact_.get_shown_name() == self.contact.get_shown_name():
					acct_info = ' (%s)' % \
						gobject.markup_escape_text(self.account)
					break

		status = contact.status
		if status is not None:
			banner_name_label.set_ellipsize(pango.ELLIPSIZE_END)
			self.banner_status_label.set_ellipsize(pango.ELLIPSIZE_END)
			status_reduced = helpers.reduce_chars_newlines(status, max_lines = 1)
		status_escaped = gobject.markup_escape_text(status_reduced)

		font_attrs, font_attrs_small = self.get_font_attrs()
		st = gajim.config.get('displayed_chat_state_notifications')
		cs = contact.chatstate
		if cs and st in ('composing_only', 'all'):
			if contact.show == 'offline':
				chatstate = ''
			elif contact.composing_xep == 'XEP-0085':
				if st == 'all' or cs == 'composing':
					chatstate = helpers.get_uf_chatstate(cs)
				else:
					chatstate = ''
			elif contact.composing_xep == 'XEP-0022':
				if cs in ('composing', 'paused'):
					# only print composing, paused
					chatstate = helpers.get_uf_chatstate(cs)
				else:
					chatstate = ''
			else:
				# When does that happen ? See [7797] and [7804]
				chatstate = helpers.get_uf_chatstate(cs)

			label_text = '<span %s>%s</span><span %s>%s %s</span>' \
				% (font_attrs, name, font_attrs_small,
				acct_info, chatstate)
			if acct_info:
				acct_info = ' ' + acct_info
			label_tooltip = '%s%s %s' % (name, acct_info, chatstate)
		else:
			# weight="heavy" size="x-large"
			label_text = '<span %s>%s</span><span %s>%s</span>' % \
				(font_attrs, name, font_attrs_small, acct_info)
			if acct_info:
				acct_info = ' ' + acct_info
			label_tooltip = '%s%s' % (name, acct_info)

		if status_escaped:
			if gajim.HAVE_PYSEXY:
				status_text = self.urlfinder.sub(self.make_href, status_escaped)
				status_text = '<span %s>%s</span>' % (font_attrs_small, status_text)
			else:
				status_text = '<span %s>%s</span>' % (font_attrs_small, status_escaped)
			self.status_tooltip.set_tip(self.banner_status_label,
					status)
			self.banner_status_label.show()
			self.banner_status_label.set_no_show_all(False)
		else:
			status_text = ''
			self.banner_status_label.hide()
			self.banner_status_label.set_no_show_all(True)

		self.banner_status_label.set_markup(status_text)
		# setup the label that holds name and jid
		banner_name_label.set_markup(label_text)
		banner_name_tooltip.set_tip(banner_name_label, label_tooltip)

	def _toggle_gpg(self):
		if not self.gpg_is_active and not self.contact.keyID:
			dialogs.ErrorDialog(_('No GPG key assigned'),
				_('No GPG key is assigned to this contact. So you cannot '
					'encrypt messages with GPG.'))
			return
		ec = gajim.encrypted_chats[self.account]
		if self.gpg_is_active:
			# Disable encryption
			ec.remove(self.contact.jid)
			self.gpg_is_active = False
			loggable = False
			msg = _('GPG encryption disabled')
			ChatControlBase.print_conversation_line(self, msg,
				'status', '', None)
			if self.session:
				self.session.loggable = True

		else:
			# Enable encryption
			ec.append(self.contact.jid)
			self.gpg_is_active = True
			msg = _('GPG encryption enabled')
			ChatControlBase.print_conversation_line(self, msg,
				'status', '', None)

			loggable = gajim.config.get_per('accounts', self.account,
				'log_encrypted_sessions')

			if self.session:
				self.session.loggable = loggable

				loggable = self.session.is_loggable()
			else:
				loggable = loggable and gajim.config.should_log(self.account,
					self.contact.jid)

			if loggable:
				msg = _('Session WILL be logged')
			else:
				msg = _('Session WILL NOT be logged')

			ChatControlBase.print_conversation_line(self, msg,
				'status', '', None)

		gajim.config.set_per('contacts', self.contact.jid,
			'gpg_enabled', self.gpg_is_active)

		self._show_lock_image(self.gpg_is_active, 'GPG',
			self.gpg_is_active, loggable, True)

	def _show_lock_image(self, visible, enc_type = '', enc_enabled = False, chat_logged = False, authenticated = False):
		'''Set lock icon visibility and create tooltip'''
		#encryption %s active
		status_string = enc_enabled and _('is') or _('is NOT')
		#chat session %s be logged
		logged_string = chat_logged and _('will') or _('will NOT')

		if authenticated:
			#About encrypted chat session
			authenticated_string = _('and authenticated')
			self.lock_image.set_from_file(os.path.join(gajim.DATA_DIR, 'pixmaps', 'security-high.png'))
		else:
			#About encrypted chat session
			authenticated_string = _('and NOT authenticated')
			self.lock_image.set_from_file(os.path.join(gajim.DATA_DIR, 'pixmaps', 'security-low.png'))

		#status will become 'is' or 'is not', authentificaed will become
		#'and authentificated' or 'and not authentificated', logged will become
		#'will' or 'will not'
		tooltip = _('%(type)s encryption %(status)s active %(authenticated)s.\n'
			'Your chat session %(logged)s be logged.') % {'type': enc_type,
			'status': status_string, 'authenticated': authenticated_string,
			'logged': logged_string}

		self.lock_tooltip.set_tip(self.authentication_button, tooltip)
		self.widget_set_visible(self.authentication_button, not visible)
		self.lock_image.set_sensitive(enc_enabled)

	def _on_authentication_button_clicked(self, widget):
		if self.gpg_is_active:
			dialogs.GPGInfoWindow(self)
		elif self.session and self.session.enable_encryption:
			dialogs.ESessionInfoWindow(self.session)

	def _process_command(self, message):
		if message[0] != '/':
			return False

		# Handle common commands
		if ChatControlBase._process_command(self, message):
			return True

		message = message[1:]
		message_array = message.split(' ', 1)
		command = message_array.pop(0).lower()
		if message_array == ['']:
			message_array = []

		if command == 'me':
			if len(message_array):
				return False # /me is not really a command
			else:
				self.get_command_help(command)
				return True # do not send "/me" as message

		if command == 'help':
			if len(message_array):
				subcommand = message_array.pop(0)
				self.get_command_help(subcommand)
			else:
				self.get_command_help(command)
			self.clear(self.msg_textview)
			return True
		elif command == 'ping':
			if not len(message_array):
				if self.account == gajim.ZEROCONF_ACC_NAME:
					self.print_conversation(
						_('Command not supported for zeroconf account.'), 'info')
				else:
					gajim.connections[self.account].sendPing(self.contact)
			else:
				self.get_command_help(command)
			self.clear(self.msg_textview)
			return True
		return False

	def get_command_help(self, command):
		if command == 'help':
			self.print_conversation(_('Commands: %s') % ChatControl.CHAT_CMDS,
				'info')
		elif command == 'clear':
			self.print_conversation(_('Usage: /%s, clears the text window.') % \
				command, 'info')
		elif command == 'compact':
			self.print_conversation(_('Usage: /%s, hide the chat buttons.') % \
				command, 'info')
		elif command == 'me':
			self.print_conversation(_('Usage: /%(command)s <action>, sends action '
				'to the current group chat. Use third person. (e.g. /%(command)s '
				'explodes.)'
				) % {'command': command}, 'info')
		elif command == 'ping':
			self.print_conversation(_('Usage: /%s, sends a ping to the contact') %\
				command, 'info')
		elif command == 'say':
			self.print_conversation(_('Usage: /%s, send the message to the contact') %\
				command, 'info')
		else:
			self.print_conversation(_('No help info for /%s') % command, 'info')

	def send_message(self, message, keyID='', chatstate=None, xhtml=None):
		'''Send a message to contact'''
		if message in ('', None, '\n') or self._process_command(message):
			return None

		# Do we need to process command for the message ?
		process_command = True
		if message.startswith('/say'):
			message = message[5:]
			process_command = False

		# refresh timers
		self.reset_kbd_mouse_timeout_vars()

		contact = self.contact

		encrypted = bool(self.session) and self.session.enable_encryption

		keyID = ''
		if self.gpg_is_active:
			keyID = contact.keyID
			encrypted = True
			if not keyID:
				keyID = 'UNKNOWN'

		chatstates_on = gajim.config.get('outgoing_chat_state_notifications') != \
			'disabled'
		composing_xep = contact.composing_xep
		chatstate_to_send = None
		if chatstates_on and contact is not None:
			if composing_xep is None:
				# no info about peer
				# send active to discover chat state capabilities
				# this is here (and not in send_chatstate)
				# because we want it sent with REAL message
				# (not standlone) eg. one that has body

				if contact.our_chatstate:
					# We already asked for xep 85, don't ask it twice
					composing_xep = 'asked_once'

				chatstate_to_send = 'active'
				contact.our_chatstate = 'ask' # pseudo state
			# if peer supports jep85 and we are not 'ask', send 'active'
			# NOTE: first active and 'ask' is set in gajim.py
			elif composing_xep is not False:
				# send active chatstate on every message (as XEP says)
				chatstate_to_send = 'active'
				contact.our_chatstate = 'active'

				gobject.source_remove(self.possible_paused_timeout_id)
				gobject.source_remove(self.possible_inactive_timeout_id)
				self._schedule_activity_timers()

		def _on_sent(id_, contact, message, encrypted, xhtml):
			# XXX: Once we have fallback to disco, remove notexistant check
			if gajim.capscache.is_supported(contact, NS_RECEIPTS) \
			and not gajim.capscache.is_supported(contact,
			'notexistant') and gajim.config.get_per('accounts',
			self.account, 'request_receipt'):
				xep0184_id = id_
			else:
				xep0184_id = None

			self.print_conversation(message, self.contact.jid, encrypted=encrypted,
				xep0184_id=xep0184_id, xhtml=xhtml)

		ChatControlBase.send_message(self, message, keyID, type_='chat',
			chatstate=chatstate_to_send, composing_xep=composing_xep,
			process_command=process_command, xhtml=xhtml, callback=_on_sent,
			callback_args=[contact, message, encrypted, xhtml])

	def check_for_possible_paused_chatstate(self, arg):
		''' did we move mouse of that window or write something in message
		textview in the last 5 seconds?
		if yes we go active for mouse, composing for kbd
		if no we go paused if we were previously composing '''
		contact = self.contact
		jid = contact.jid
		current_state = contact.our_chatstate
		if current_state is False: # jid doesn't support chatstates
			return False # stop looping

		message_buffer = self.msg_textview.get_buffer()
		if self.kbd_activity_in_last_5_secs and message_buffer.get_char_count():
			# Only composing if the keyboard activity was in text entry
			self.send_chatstate('composing')
		elif self.mouse_over_in_last_5_secs and\
			jid == self.parent_win.get_active_jid():
			self.send_chatstate('active')
		else:
			if current_state == 'composing':
				self.send_chatstate('paused') # pause composing

		# assume no activity and let the motion-notify or 'insert-text' make them
		# True refresh 30 seconds vars too or else it's 30 - 5 = 25 seconds!
		self.reset_kbd_mouse_timeout_vars()
		return True # loop forever

	def check_for_possible_inactive_chatstate(self, arg):
		''' did we move mouse over that window or wrote something in message
		textview in the last 30 seconds?
		if yes we go active
		if no we go inactive '''
		contact = self.contact

		current_state = contact.our_chatstate
		if current_state is False: # jid doesn't support chatstates
			return False # stop looping

		if self.mouse_over_in_last_5_secs or self.kbd_activity_in_last_5_secs:
			return True # loop forever

		if not self.mouse_over_in_last_30_secs or \
		self.kbd_activity_in_last_30_secs:
			self.send_chatstate('inactive', contact)

		# assume no activity and let the motion-notify or 'insert-text' make them
		# True refresh 30 seconds too or else it's 30 - 5 = 25 seconds!
		self.reset_kbd_mouse_timeout_vars()
		return True # loop forever

	def reset_kbd_mouse_timeout_vars(self):
		self.kbd_activity_in_last_5_secs = False
		self.mouse_over_in_last_5_secs = False
		self.mouse_over_in_last_30_secs = False
		self.kbd_activity_in_last_30_secs = False

	def on_cancel_session_negotiation(self):
		msg = _('Session negotiation cancelled')
		ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

	def print_esession_details(self):
		'''print esession settings to textview'''
		e2e_is_active = bool(self.session) and self.session.enable_encryption
		if e2e_is_active:
			msg = _('This session is encrypted')

			if self.session.is_loggable():
				msg += _(' and WILL be logged')
			else:
				msg += _(' and WILL NOT be logged')

			ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

			if not self.session.verified_identity:
				ChatControlBase.print_conversation_line(self, _("Remote contact's identity not verified. Click the shield button for more details."), 'status', '', None)
		else:
			msg = _('E2E encryption disabled')
			ChatControlBase.print_conversation_line(self, msg, 'status', '', None)

		self._show_lock_image(e2e_is_active, 'E2E', e2e_is_active, self.session and \
				self.session.is_loggable(), self.session and self.session.verified_identity)

	def print_conversation(self, text, frm='', tim=None, encrypted=False,
	subject=None, xhtml=None, simple=False, xep0184_id=None):
		'''Print a line in the conversation:
		if frm is set to status: it's a status message
		if frm is set to error: it's an error message
			The difference between status and error is mainly that with error, msg
			count as a new message (in systray and in control).
		if frm is set to info: it's a information message
		if frm is set to print_queue: it is incomming from queue
		if frm is set to another value: it's an outgoing message
		if frm is not set: it's an incomming message'''
		contact = self.contact

		if frm == 'status':
			if not gajim.config.get('print_status_in_chats'):
				return
			kind = 'status'
			name = ''
		elif frm == 'error':
			kind = 'error'
			name = ''
		elif frm == 'info':
			kind = 'info'
			name = ''
		else:
			if self.session and self.session.enable_encryption:
				# ESessions
				if not encrypted:
					msg = _('The following message was NOT encrypted')
					ChatControlBase.print_conversation_line(self, msg, 'status', '',
						tim)
			else:
				# GPG encryption
				if encrypted and not self.gpg_is_active:
					msg = _('The following message was encrypted')
					ChatControlBase.print_conversation_line(self, msg, 'status', '',
						tim)
					# turn on OpenPGP if this was in fact a XEP-0027 encrypted message
					if encrypted == 'xep27':
						self._toggle_gpg()
				elif not encrypted and self.gpg_is_active:
					msg = _('The following message was NOT encrypted')
					ChatControlBase.print_conversation_line(self, msg, 'status', '',
						tim)
			if not frm:
				kind = 'incoming'
				name = contact.get_shown_name()
			elif frm == 'print_queue': # incoming message, but do not update time
				kind = 'incoming_queue'
				name = contact.get_shown_name()
			else:
				kind = 'outgoing'
				name = gajim.nicks[self.account]
				if not xhtml and not encrypted and gajim.config.get(
				'rst_formatting_outgoing_messages'):
					from common.rst_xhtml_generator import create_xhtml
					xhtml = create_xhtml(text)
					if xhtml:
						xhtml = '<body xmlns="%s">%s</body>' % (NS_XHTML, xhtml)
		ChatControlBase.print_conversation_line(self, text, kind, name, tim,
			subject=subject, old_kind=self.old_msg_kind, xhtml=xhtml,
			simple=simple, xep0184_id=xep0184_id)
		if text.startswith('/me ') or text.startswith('/me\n'):
			self.old_msg_kind = None
		else:
			self.old_msg_kind = kind

	def get_tab_label(self, chatstate):
		unread = ''
		if self.resource:
			jid = self.contact.get_full_jid()
		else:
			jid = self.contact.jid
		num_unread = len(gajim.events.get_events(self.account, jid,
			['printed_' + self.type_id, self.type_id]))
		if num_unread == 1 and not gajim.config.get('show_unread_tab_icon'):
			unread = '*'
		elif num_unread > 1:
			unread = '[' + unicode(num_unread) + ']'

		# Draw tab label using chatstate
		theme = gajim.config.get('roster_theme')
		color = None
		if not chatstate:
			chatstate = self.contact.chatstate
		if chatstate is not None:
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
		if color:
			# We set the color for when it's the current tab or not
			color = gtk.gdk.colormap_get_system().alloc_color(color)
			# In inactive tab color to be lighter against the darker inactive
			# background
			if chatstate in ('inactive', 'gone') and\
			self.parent_win.get_active_control() != self:
				color = self.lighten_color(color)
		else: # active or not chatstate, get color from gtk
			color = self.parent_win.notebook.style.fg[gtk.STATE_ACTIVE]


		name = self.contact.get_shown_name()
		if self.resource:
			name += '/' + self.resource
		label_str = gobject.markup_escape_text(name)
		if num_unread: # if unread, text in the label becomes bold
			label_str = '<b>' + unread + label_str + '</b>'
		return (label_str, color)

	def get_tab_image(self):
		if self.resource:
			jid = self.contact.get_full_jid()
		else:
			jid = self.contact.jid
		num_unread = len(gajim.events.get_events(self.account, jid,
			['printed_' + self.type_id, self.type_id]))
		# Set tab image (always 16x16); unread messages show the 'event' image
		tab_img = None

		if num_unread and gajim.config.get('show_unread_tab_icon'):
			img_16 = gajim.interface.roster.get_appropriate_state_images(
				self.contact.jid, icon_name = 'event')
			tab_img = img_16['event']
		else:
			contact = gajim.contacts.get_contact_with_highest_priority(
				self.account, self.contact.jid)
			if not contact or self.resource:
				# For transient contacts
				contact = self.contact
			img_16 = gajim.interface.roster.get_appropriate_state_images(
				self.contact.jid, icon_name = contact.show)
			tab_img = img_16[contact.show]

		return tab_img

	def prepare_context_menu(self, hide_buttonbar_entries = False):
		'''sets compact view menuitem active state
		sets active and sensitivity state for toggle_gpg_menuitem
		sets sensitivity for history_menuitem (False for tranasports)
		and file_transfer_menuitem
		and hide()/show() for add_to_roster_menuitem
		'''
		xml = gtkgui_helpers.get_glade('chat_control_popup_menu.glade')
		menu = xml.get_widget('chat_control_popup_menu')

		add_to_roster_menuitem = xml.get_widget('add_to_roster_menuitem')
		history_menuitem = xml.get_widget('history_menuitem')
		toggle_gpg_menuitem = xml.get_widget('toggle_gpg_menuitem')
		toggle_e2e_menuitem = xml.get_widget('toggle_e2e_menuitem')
		send_file_menuitem = xml.get_widget('send_file_menuitem')
		information_menuitem = xml.get_widget('information_menuitem')
		convert_to_gc_menuitem = xml.get_widget('convert_to_groupchat')
		separatormenuitem1 = xml.get_widget('separatormenuitem1')
		separatormenuitem2 = xml.get_widget('separatormenuitem2')

		# add a special img for send file menuitem
		path_to_upload_img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'upload.png')
		img = gtk.Image()
		img.set_from_file(path_to_upload_img)
		send_file_menuitem.set_image(img)

		muc_icon = gtkgui_helpers.load_icon('muc_active')
		if muc_icon:
			convert_to_gc_menuitem.set_image(muc_icon)

		if not hide_buttonbar_entries:
			history_menuitem.show()
			send_file_menuitem.show()
			information_menuitem.show()
			convert_to_gc_menuitem.show()
			separatormenuitem1.show()
			separatormenuitem2.show()

		ag = gtk.accel_groups_from_object(self.parent_win.window)[0]
		send_file_menuitem.add_accelerator('activate', ag, gtk.keysyms.f, gtk.gdk.CONTROL_MASK,
			gtk.ACCEL_VISIBLE)
		convert_to_gc_menuitem.add_accelerator('activate', ag, gtk.keysyms.g, gtk.gdk.CONTROL_MASK,
			gtk.ACCEL_VISIBLE)
		history_menuitem.add_accelerator('activate', ag, gtk.keysyms.h, gtk.gdk.CONTROL_MASK,
			gtk.ACCEL_VISIBLE)
		information_menuitem.add_accelerator('activate', ag, gtk.keysyms.i,
			gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)

		contact = self.parent_win.get_active_contact()
		jid = contact.jid

		e2e_is_active = self.session is not None and self.session.enable_encryption

		# check if we support and use gpg
		if not gajim.config.get_per('accounts', self.account, 'keyid') or\
		not gajim.connections[self.account].USE_GPG or\
		gajim.jid_is_transport(jid):
			toggle_gpg_menuitem.set_sensitive(False)
		else:
			toggle_gpg_menuitem.set_sensitive(self.gpg_is_active or not e2e_is_active)
			toggle_gpg_menuitem.set_active(self.gpg_is_active)

		# disable esessions if we or the other client don't support them
		# XXX: Once we have fallback to disco, remove notexistant check
		if not gajim.HAVE_PYCRYPTO or \
		not gajim.capscache.is_supported(contact, NS_ESESSION) or \
		gajim.capscache.is_supported(contact, 'notexistant'):
			toggle_e2e_menuitem.set_sensitive(False)
		else:
			toggle_e2e_menuitem.set_active(e2e_is_active)
			toggle_e2e_menuitem.set_sensitive(e2e_is_active or not self.gpg_is_active)

		# add_to_roster_menuitem
		if not hide_buttonbar_entries and _('Not in Roster') in contact.groups:
			add_to_roster_menuitem.show()

		# check if it's possible to send a file
		if gajim.capscache.is_supported(contact, NS_FILE):
			send_file_menuitem.set_sensitive(True)
		else:
			send_file_menuitem.set_sensitive(False)

		# check if it's possible to convert to groupchat
		if gajim.capscache.is_supported(contact, NS_MUC):
			convert_to_gc_menuitem.set_sensitive(True)
		else:
			convert_to_gc_menuitem.set_sensitive(False)

		# connect signals
		id_ = history_menuitem.connect('activate',
			self._on_history_menuitem_activate)
		self.handlers[id_] = history_menuitem
		id_ = send_file_menuitem.connect('activate',
			self._on_send_file_menuitem_activate)
		self.handlers[id_] = send_file_menuitem
		id_ = add_to_roster_menuitem.connect('activate',
			self._on_add_to_roster_menuitem_activate)
		self.handlers[id_] = add_to_roster_menuitem
		id_ = toggle_gpg_menuitem.connect('activate',
			self._on_toggle_gpg_menuitem_activate)
		self.handlers[id_] = toggle_gpg_menuitem
		id_ = toggle_e2e_menuitem.connect('activate',
			self._on_toggle_e2e_menuitem_activate)
		self.handlers[id_] = toggle_e2e_menuitem
		id_ = information_menuitem.connect('activate',
			self._on_contact_information_menuitem_activate)
		self.handlers[id_] = information_menuitem
		id_ = convert_to_gc_menuitem.connect('activate',
			self._on_convert_to_gc_menuitem_activate)
		self.handlers[id_] = convert_to_gc_menuitem

		menu.connect('selection-done', self.destroy_menu,
			send_file_menuitem, convert_to_gc_menuitem,
			information_menuitem, history_menuitem)
		return menu

	def destroy_menu(self, menu, send_file_menuitem,
	convert_to_gc_menuitem, information_menuitem, history_menuitem):
		# destroy accelerators
		ag = gtk.accel_groups_from_object(self.parent_win.window)[0]
		send_file_menuitem.remove_accelerator(ag, gtk.keysyms.f,
			gtk.gdk.CONTROL_MASK)
		convert_to_gc_menuitem.remove_accelerator(ag, gtk.keysyms.g,
			gtk.gdk.CONTROL_MASK)
		information_menuitem.remove_accelerator(ag, gtk.keysyms.i,
			gtk.gdk.CONTROL_MASK)
		history_menuitem.remove_accelerator(ag, gtk.keysyms.h,
			gtk.gdk.CONTROL_MASK)
		# destroy menu
		menu.destroy()

	def send_chatstate(self, state, contact = None):
		''' sends OUR chatstate as STANDLONE chat state message (eg. no body)
		to contact only if new chatstate is different from the previous one
		if jid is not specified, send to active tab'''
		# JEP 85 does not allow resending the same chatstate
		# this function checks for that and just returns so it's safe to call it
		# with same state.

		# This functions also checks for violation in state transitions
		# and raises RuntimeException with appropriate message
		# more on that http://www.jabber.org/jeps/jep-0085.html#statechart

		# do not send nothing if we have chat state notifications disabled
		# that means we won't reply to the <active/> from other peer
		# so we do not broadcast jep85 capabalities
		chatstate_setting = gajim.config.get('outgoing_chat_state_notifications')
		if chatstate_setting == 'disabled':
			return
		elif chatstate_setting == 'composing_only' and state != 'active' and\
			state != 'composing':
			return

		if contact is None:
			contact = self.parent_win.get_active_contact()
			if contact is None:
				# contact was from pm in MUC, and left the room so contact is None
				# so we cannot send chatstate anymore
				return

		# Don't send chatstates to offline contacts
		if contact.show == 'offline':
			return

		if contact.composing_xep is False: # jid cannot do xep85 nor xep22
			return

		# if the new state we wanna send (state) equals
		# the current state (contact.our_chatstate) then return
		if contact.our_chatstate == state:
			return

		if contact.composing_xep is None:
			# we don't know anything about jid, so return
			# NOTE:
			# send 'active', set current state to 'ask' and return is done
			# in self.send_message() because we need REAL message (with <body>)
			# for that procedure so return to make sure we send only once
			# 'active' until we know peer supports jep85
			return

		if contact.our_chatstate == 'ask':
			return

		# in JEP22, when we already sent stop composing
		# notification on paused, don't resend it
		if contact.composing_xep == 'XEP-0022' and \
		contact.our_chatstate in ('paused', 'active', 'inactive') and \
		state is not 'composing': # not composing == in (active, inactive, gone)
			contact.our_chatstate = 'active'
			self.reset_kbd_mouse_timeout_vars()
			return

		# prevent going paused if we we were not composing (JEP violation)
		if state == 'paused' and not contact.our_chatstate == 'composing':
			# go active before
			MessageControl.send_message(self, None, chatstate = 'active')
			contact.our_chatstate = 'active'
			self.reset_kbd_mouse_timeout_vars()

		# if we're inactive prevent composing (JEP violation)
		elif contact.our_chatstate == 'inactive' and state == 'composing':
			# go active before
			MessageControl.send_message(self, None, chatstate = 'active')
			contact.our_chatstate = 'active'
			self.reset_kbd_mouse_timeout_vars()

		MessageControl.send_message(self, None, chatstate = state,
			msg_id = contact.msg_id, composing_xep = contact.composing_xep)
		contact.our_chatstate = state
		if contact.our_chatstate == 'active':
			self.reset_kbd_mouse_timeout_vars()

	def shutdown(self):
		# destroy banner tooltip - bug #pygtk for that!
		self.status_tooltip.destroy()

		# Send 'gone' chatstate
		self.send_chatstate('gone', self.contact)
		self.contact.chatstate = None
		self.contact.our_chatstate = None

		# disconnect self from session
		if self.session:
			self.session.control = None

		# Disconnect timer callbacks
		gobject.source_remove(self.possible_paused_timeout_id)
		gobject.source_remove(self.possible_inactive_timeout_id)
		# Remove bigger avatar window
		if self.bigger_avatar_window:
			self.bigger_avatar_window.destroy()
		# Clean events
		gajim.events.remove_events(self.account, self.get_full_jid(),
			types = ['printed_' + self.type_id, self.type_id])
		# Remove contact instance if contact has been removed
		key = (self.contact.jid, self.account)
		roster = gajim.interface.roster
		if key in roster.contacts_to_be_removed.keys() and \
		not roster.contact_has_pending_roster_events(self.contact, self.account):
			backend = roster.contacts_to_be_removed[key]['backend']
			del roster.contacts_to_be_removed[key]
			roster.remove_contact(self.contact.jid, self.account, force=True,
				backend=backend)
		# remove all register handlers on widgets, created by self.xml
		# to prevent circular references among objects
		for i in self.handlers.keys():
			if self.handlers[i].handler_is_connected(i):
				self.handlers[i].disconnect(i)
			del self.handlers[i]
		self.conv_textview.del_handlers()
		self.msg_textview.destroy()

	def minimizable(self):
		return False

	def safe_shutdown(self):
		return False

	def allow_shutdown(self, method, on_yes, on_no, on_minimize):
		if time.time() - gajim.last_message_time[self.account]\
		[self.get_full_jid()] < 2:
			# 2 seconds
			def on_ok():
				on_yes(self)

			def on_cancel():
				on_no(self)

			dialogs.ConfirmationDialog(
				# %s is being replaced in the code with JID
				_('You just received a new message from "%s"') % self.contact.jid,
				_('If you close this tab and you have history disabled, '\
				'this message will be lost.'), on_response_ok=on_ok,
				on_response_cancel=on_cancel)
			return
		on_yes(self)

	def handle_incoming_chatstate(self):
		''' handle incoming chatstate that jid SENT TO us '''
		self.draw_banner_text()
		# update chatstate in tab for this chat
		self.parent_win.redraw_tab(self, self.contact.chatstate)

	def set_control_active(self, state):
		ChatControlBase.set_control_active(self, state)
		# send chatstate inactive to the one we're leaving
		# and active to the one we visit
		if state:
			self.send_chatstate('active', self.contact)
		else:
			self.send_chatstate('inactive', self.contact)
		# Hide bigger avatar window
		if self.bigger_avatar_window:
			self.bigger_avatar_window.destroy()
			self.bigger_avatar_window = None
			# Re-show the small avatar
			self.show_avatar()

	def show_avatar(self, resource = None):
		if not gajim.config.get('show_avatar_in_chat'):
			return

		is_fake = False
		if self.TYPE_ID == message_control.TYPE_PM:
			is_fake = True
			jid_with_resource = self.contact.jid # fake jid
		else:
			jid_with_resource = self.contact.jid
			if resource:
				jid_with_resource += '/' + resource

		# we assume contact has no avatar
		scaled_pixbuf = None

		pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid_with_resource,
			is_fake)
		if pixbuf == 'ask':
			# we don't have the vcard
			if self.TYPE_ID == message_control.TYPE_PM:
				if self.gc_contact.jid:
					# We know the real jid of this contact
					real_jid = self.gc_contact.jid
					if self.gc_contact.resource:
						real_jid += '/' + self.gc_contact.resource
				else:
					real_jid = jid_with_resource
				gajim.connections[self.account].request_vcard(real_jid,
					jid_with_resource)
			else:
				gajim.connections[self.account].request_vcard(jid_with_resource)
			return
		if pixbuf is not None:
			scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'chat')

		image = self.xml.get_widget('avatar_image')
		image.set_from_pixbuf(scaled_pixbuf)
		image.show_all()

	def _on_drag_data_received(self, widget, context, x, y, selection,
		target_type, timestamp):
		if not selection.data:
			return
		if self.TYPE_ID == message_control.TYPE_PM:
			c = self.gc_contact
		else:
			c = self.contact
		if target_type == self.TARGET_TYPE_URI_LIST:
			if not c.resource: # If no resource is known, we can't send a file
				return
			uri = selection.data.strip()
			uri_splitted = uri.split() # we may have more than one file dropped
			for uri in uri_splitted:
				path = helpers.get_file_path_from_dnd_dropped_uri(uri)
				if os.path.isfile(path): # is it file?
					ft = gajim.interface.instances['file_transfers']
					ft.send_file(self.account, c, path)
			return

		# chat2muc
		treeview = gajim.interface.roster.tree
		model = treeview.get_model()
		data = selection.data
		path = treeview.get_selection().get_selected_rows()[1][0]
		iter_ = model.get_iter(path)
		type_ = model[iter_][2]
		if type_ != 'contact': # source is not a contact
			return
		dropped_jid = data.decode('utf-8')

		dropped_transport = gajim.get_transport_name_from_jid(dropped_jid)
		c_transport = gajim.get_transport_name_from_jid(c.jid)
		if dropped_transport or c_transport:
			return # transport contacts cannot be invited

		dialogs.TransformChatToMUC(self.account, [c.jid], [dropped_jid])

	def _on_message_tv_buffer_changed(self, textbuffer):
		self.kbd_activity_in_last_5_secs = True
		self.kbd_activity_in_last_30_secs = True
		if textbuffer.get_char_count():
			self.send_chatstate('composing', self.contact)

			e2e_is_active = self.session and \
				self.session.enable_encryption
			e2e_pref = gajim.config.get_per('accounts', self.account,
				'enable_esessions') and gajim.config.get_per('accounts',
				self.account, 'autonegotiate_esessions') and gajim.config.get_per(
				'contacts', self.contact.jid, 'autonegotiate_esessions')
			want_e2e = not e2e_is_active and not self.gpg_is_active \
				and e2e_pref

			# XXX: Once we have fallback to disco, remove notexistant check
			if want_e2e and not self.no_autonegotiation \
			and gajim.HAVE_PYCRYPTO \
			and gajim.capscache.is_supported(self.contact,
			NS_ESESSION) and not gajim.capscache.is_supported(
			self.contact, 'notexistant'):
				self.begin_e2e_negotiation()
		else:
			self.send_chatstate('active', self.contact)

	def restore_conversation(self):
		jid = self.contact.jid
		# don't restore lines if it's a transport
		if gajim.jid_is_transport(jid):
			return

		# How many lines to restore and when to time them out
		restore_how_many = gajim.config.get('restore_lines')
		if restore_how_many <= 0:
			return
		timeout = gajim.config.get('restore_timeout') # in minutes

		# number of messages that are in queue and are already logged, we want
		# to avoid duplication
		pending_how_many = len(gajim.events.get_events(self.account, jid,
			['chat', 'pm']))
		if self.resource:
			pending_how_many += len(gajim.events.get_events(self.account,
				self.contact.get_full_jid(), ['chat', 'pm']))

		try:
			rows = gajim.logger.get_last_conversation_lines(jid, restore_how_many,
				pending_how_many, timeout, self.account)
		except exceptions.DatabaseMalformed:
			import common.logger
			dialogs.ErrorDialog(_('Database Error'),
				_('The database file (%s) cannot be read. Try to repair it or remove it (all history will be lost).') % common.logger.LOG_DB_PATH)
			rows = []
		local_old_kind = None
		for row in rows: # row[0] time, row[1] has kind, row[2] the message
			if not row[2]: # message is empty, we don't print it
				continue
			if row[1] in (constants.KIND_CHAT_MSG_SENT,
					constants.KIND_SINGLE_MSG_SENT):
				kind = 'outgoing'
				name = gajim.nicks[self.account]
			elif row[1] in (constants.KIND_SINGLE_MSG_RECV,
					constants.KIND_CHAT_MSG_RECV):
				kind = 'incoming'
				name = self.contact.get_shown_name()
			elif row[1] == constants.KIND_ERROR:
				kind = 'status'
				name = self.contact.get_shown_name()

			tim = time.localtime(float(row[0]))

			if gajim.config.get('restored_messages_small'):
				small_attr = ['small']
			else:
				small_attr = []
			ChatControlBase.print_conversation_line(self, row[2], kind, name, tim,
								small_attr,
								small_attr + ['restored_message'],
								small_attr + ['restored_message'],
								False, old_kind = local_old_kind)
			if row[2].startswith('/me ') or row[2].startswith('/me\n'):
				local_old_kind = None
			else:
				local_old_kind = kind
		if len(rows):
			self.conv_textview.print_empty_line()

	def read_queue(self):
		'''read queue and print messages containted in it'''

		jid = self.contact.jid
		jid_with_resource = jid
		if self.resource:
			jid_with_resource += '/' + self.resource
		events = gajim.events.get_events(self.account, jid_with_resource)

		# list of message ids which should be marked as read
		message_ids = []
		for event in events:
			if event.type_ != self.type_id:
				continue
			data = event.parameters
			kind = data[2]
			if kind == 'error':
				kind = 'info'
			else:
				kind = 'print_queue'
			self.print_conversation(data[0], kind, tim = data[3],
				encrypted = data[4], subject = data[1], xhtml = data[7])
			if len(data) > 6 and isinstance(data[6], int):
				message_ids.append(data[6])

			if len(data) > 8:
				self.set_session(data[8])
		if message_ids:
			gajim.logger.set_read_messages(message_ids)
		gajim.events.remove_events(self.account, jid_with_resource,
			types = [self.type_id])

		typ = 'chat' # Is it a normal chat or a pm ?

		# reset to status image in gc if it is a pm
		# Is it a pm ?
		room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
		control = gajim.interface.msg_win_mgr.get_gc_control(room_jid,
			self.account)
		if control and control.type_id == message_control.TYPE_GC:
			control.update_ui()
			control.parent_win.show_title()
			typ = 'pm'

		self.redraw_after_event_removed(jid)
		if (self.contact.show in ('offline', 'error')):
			show_offline = gajim.config.get('showoffline')
			show_transports = gajim.config.get('show_transports_group')
			if (not show_transports and gajim.jid_is_transport(jid)) or \
			(not show_offline and typ == 'chat' and \
			len(gajim.contacts.get_contacts(self.account, jid)) < 2):
				gajim.interface.roster.remove_to_be_removed(self.contact.jid,
					self.account)
			elif typ == 'pm':
				control.remove_contact(nick)

	def show_bigger_avatar(self, small_avatar):
		'''resizes the avatar, if needed, so it has at max half the screen size
		and shows it'''
		if not small_avatar.window:
			# Tab has been closed since we hovered the avatar
			return
		is_fake = False
		if self.type_id == message_control.TYPE_PM:
			is_fake = True
		avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(
			self.contact.jid, is_fake)
		if avatar_pixbuf in ('ask', None):
			return
		# Hide the small avatar
		# this code hides the small avatar when we show a bigger one in case
		# the avatar has a transparency hole in the middle
		# so when we show the big one we avoid seeing the small one behind.
		# It's why I set it transparent.
		image = self.xml.get_widget('avatar_image')
		pixbuf = image.get_pixbuf()
		pixbuf.fill(0xffffff00L) # RGBA
		image.queue_draw()

		screen_w = gtk.gdk.screen_width()
		screen_h = gtk.gdk.screen_height()
		avatar_w = avatar_pixbuf.get_width()
		avatar_h = avatar_pixbuf.get_height()
		half_scr_w = screen_w / 2
		half_scr_h = screen_h / 2
		if avatar_w > half_scr_w:
			avatar_w = half_scr_w
		if avatar_h > half_scr_h:
			avatar_h = half_scr_h
		window = gtk.Window(gtk.WINDOW_POPUP)
		self.bigger_avatar_window = window
		pixmap, mask = avatar_pixbuf.render_pixmap_and_mask()
		window.set_size_request(avatar_w, avatar_h)
		# we should make the cursor visible
		# gtk+ doesn't make use of the motion notify on gtkwindow by default
		# so this line adds that
		window.set_events(gtk.gdk.POINTER_MOTION_MASK)
		window.set_app_paintable(True)
		window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_TOOLTIP)

		window.realize()
		window.window.set_back_pixmap(pixmap, False) # make it transparent
		window.window.shape_combine_mask(mask, 0, 0)

		# make the bigger avatar window show up centered
		x0, y0 = small_avatar.window.get_origin()
		x0 += small_avatar.allocation.x
		y0 += small_avatar.allocation.y
		center_x= x0 + (small_avatar.allocation.width / 2)
		center_y = y0 + (small_avatar.allocation.height / 2)
		pos_x, pos_y = center_x - (avatar_w / 2), center_y - (avatar_h / 2)
		window.move(pos_x, pos_y)
		# make the cursor invisible so we can see the image
		invisible_cursor = gtkgui_helpers.get_invisible_cursor()
		window.window.set_cursor(invisible_cursor)

		# we should hide the window
		window.connect('leave_notify_event',
			self._on_window_avatar_leave_notify_event)
		window.connect('motion-notify-event',
			self._on_window_motion_notify_event)

		window.show_all()

	def _on_window_avatar_leave_notify_event(self, widget, event):
		'''we just left the popup window that holds avatar'''
		self.bigger_avatar_window.destroy()
		self.bigger_avatar_window = None
		# Re-show the small avatar
		self.show_avatar()

	def _on_window_motion_notify_event(self, widget, event):
		'''we just moved the mouse so show the cursor'''
		cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
		self.bigger_avatar_window.window.set_cursor(cursor)

	def _on_send_file_menuitem_activate(self, widget):
		self._on_send_file()

	def _on_add_to_roster_menuitem_activate(self, widget):
		dialogs.AddNewContactWindow(self.account, self.contact.jid)

	def _on_contact_information_menuitem_activate(self, widget):
		gajim.interface.roster.on_info(widget, self.contact, self.account)

	def _on_toggle_gpg_menuitem_activate(self, widget):
		self._toggle_gpg()

	def _on_convert_to_gc_menuitem_activate(self, widget):
		'''user want to invite some friends to chat'''
		dialogs.TransformChatToMUC(self.account, [self.contact.jid])

	def _on_toggle_e2e_menuitem_activate(self, widget):
		if self.session and self.session.enable_encryption:
			# e2e was enabled, disable it
			jid = str(self.session.jid)
			thread_id = self.session.thread_id

			self.session.terminate_e2e()

			gajim.connections[self.account].delete_session(jid, thread_id)

			# presumably the user had a good reason to shut it off, so
			# disable autonegotiation too
			self.no_autonegotiation = True
		else:
			self.begin_e2e_negotiation()

	def begin_e2e_negotiation(self):
		self.no_autonegotiation = True

		if not self.session:
			fjid = self.contact.get_full_jid()
			new_sess = gajim.connections[self.account].make_new_session(fjid, type_=self.type_id)
			self.set_session(new_sess)

		self.session.negotiate_e2e(False)

	def got_connected(self):
		ChatControlBase.got_connected(self)
		# Refreshing contact
		contact = gajim.contacts.get_contact_with_highest_priority(
			self.account, self.contact.jid)
		if isinstance(contact, GC_Contact):
			contact = gajim.contacts.contact_from_gc_contact(contact)
		if contact:
			self.contact = contact
		self.draw_banner()

	def update_status_display(self, name, uf_show, status):
		'''print the contact's status and update the status/GPG image'''
		self.update_ui()
		self.parent_win.redraw_tab(self)

		self.print_conversation(_('%(name)s is now %(status)s') % {'name': name,
			'status': uf_show}, 'status')

		if status:
			self.print_conversation(' (', 'status', simple=True)
			self.print_conversation('%s' % (status), 'status', simple=True)
			self.print_conversation(')', 'status', simple=True)

# vim: se ts=3:
