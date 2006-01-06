##	chat_control.py
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

import os, os.path
import math
import time
import gtk
import gtk.glade
import pango
import gobject
import gtkgui_helpers
import message_control
import dialogs

from common import gajim
from common import helpers
from message_control import MessageControl
from conversation_textview import ConversationTextview
from message_textview import MessageTextView
from common.logger import Constants
constants = Constants()

try:
	import gtkspell
	HAS_GTK_SPELL = True
except:
	HAS_GTK_SPELL = False

####################
# FIXME: Can't this stuff happen once?
from common import i18n
_ = i18n._
APP = i18n.APP

GTKGUI_GLADE = 'gtkgui.glade'

################################################################################
class ChatControlBase(MessageControl):
	# FIXME
	'''TODO
	Contains a banner, ConversationTextview, MessageTextView
	'''
	
	def draw_widgets(self):
		self.draw_banner()
		# Derived types MUST implement this
	def draw_banner(self):
		self._paint_banner()
		self._update_banner_state_image()
		# Derived types SHOULD implement this
	def update_state(self):
		self.draw_banner()
		# Derived types SHOULD implement this
	def repaint_themed_widgets(self):
		self.draw_banner()
		# NOTE: Derived classes MAY implement this
	def _update_banner_state_image(self):
		pass # Derived types MAY implement this

	def __init__(self, type_id, parent_win, widget_name, display_name, contact, acct):
		MessageControl.__init__(self, type_id, parent_win, widget_name, display_name,
					contact, acct);

		# FIXME: These are hidden from 0.8 on, but IMO all these things need
		#        to be shown optionally.  Esp. the never-used Send button
		for w in ('bold_togglebutton', 'italic_togglebutton',
			'underline_togglebutton'):
			self.xml.get_widget(w).set_no_show_all(True)

		self.widget.connect('key_press_event', self._on_keypress_event)

		# Create textviews and connect signals
		self.conv_textview = ConversationTextview(None) # FIXME: remove account arg
		self.conv_textview.show_all()
		self.conv_scrolledwindow = self.xml.get_widget('conversation_scrolledwindow')
		self.conv_scrolledwindow.add(self.conv_textview)
		self.conv_scrolledwindow.get_vadjustment().connect('value-changed',
			self.on_conversation_vadjustment_value_changed)
		# add MessageTextView to UI and connect signals
		self.msg_scrolledwindow = self.xml.get_widget('message_scrolledwindow')
		self.msg_textview = MessageTextView()
		self.msg_textview.connect('mykeypress',
					self._on_message_textview_mykeypress_event)
		self.msg_scrolledwindow.add(self.msg_textview)
		self.msg_textview.connect('key_press_event',
					self._on_message_textview_key_press_event)
		self.msg_textview.connect('size-request', self.size_request, self.xml)
		self.update_font()

		# Hook up send button
		self.xml.get_widget('send_button').connect('clicked',
							self._on_send_button_clicked)

		# the following vars are used to keep history of user's messages
		self.sent_history = []
		self.sent_history_pos = 0
		self.typing_new = False
		self.orig_msg = ''

		self.nb_unread = 0

		# Emoticons menu
		# set image no matter if user wants at this time emoticons or not
		# (so toggle works ok)
		img = self.xml.get_widget('emoticons_button_image')
		img.set_from_file(os.path.join(gajim.DATA_DIR, 'emoticons', 'smile.png'))
		self.toggle_emoticons()

		# Attach speller
		if gajim.config.get('use_speller') and HAS_GTK_SPELL:
			try:
				gtkspell.Spell(self.msg_textview)
			except gobject.GError, msg:
				#FIXME: add a ui for this use spell.set_language()
				dialogs.ErrorDialog(unicode(msg), _('If that is not your language for which you want to highlight misspelled words, then please set your $LANG as appropriate. Eg. for French do export LANG=fr_FR or export LANG=fr_FR.UTF-8 in ~/.bash_profile or to make it global in /etc/profile.\n\nHighlighting misspelled words feature will not be used')).get_response()
				gajim.config.set('use_speller', False)

		self.print_time_timeout_id = None

	def _on_send_button_clicked(self, widget):
		'''When send button is pressed: send the current message'''
		message_buffer = self.msg_textview.get_buffer()
		start_iter = message_buffer.get_start_iter()
		end_iter = message_buffer.get_end_iter()
		message = message_buffer.get_text(start_iter, end_iter, 0).decode('utf-8')

		# send the message
		self.send_message(message)

	def _paint_banner(self):
		'''Repaint banner with theme color'''
		theme = gajim.config.get('roster_theme')
		bgcolor = gajim.config.get_per('themes', theme, 'bannerbgcolor')
		textcolor = gajim.config.get_per('themes', theme, 'bannertextcolor')
		# the backgrounds are colored by using an eventbox by
		# setting the bg color of the eventbox and the fg of the name_label
		banner_eventbox = self.xml.get_widget('banner_eventbox')
		banner_name_label = self.xml.get_widget('banner_name_label')
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


	def _on_keypress_event(self, widget, event):
		if event.state & gtk.gdk.CONTROL_MASK:
			# CTRL + l|L: clear conv_textview
			if event.keyval == gtk.keysyms.l or event.keyval == gtk.keysyms.L:
				self.conv_textview.get_buffer().set_text('')
				return True
			# CTRL + v: Paste into msg_textview
			elif event.keyval == gtk.keysyms.v:
				if not self.msg_textview.is_focus():
					self.msg_textview.grab_focus()
				# Paste into the msg textview
				self.msg_textview.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.e and \
			(event.state & gtk.gdk.MOD1_MASK): # alt + E opens emoticons menu
			if gajim.config.get('useemoticons'):
				msg_tv = self.msg_textview
				def set_emoticons_menu_position(w, msg_tv = self.msg_textview):
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
						y -= menu_height +\
							(msg_tv.allocation.height / buf.get_line_count())
					#else: # move menu just below cursor
					#	y -= (msg_tv.allocation.height / buf.get_line_count())
					return (x, y, True) # push_in True
				self.emoticons_menu.popup(None, None, set_emoticons_menu_position, 1, 0)
		return False

	def _on_message_textview_key_press_event(self, widget, event):
		if event.state & gtk.gdk.SHIFT_MASK:
			# SHIFT + PAGE_[UP|DOWN]: send to conv_textview
			if event.keyval == gtk.keysyms.Page_Down or \
						event.keyval == gtk.keysyms.Page_Up:
				self.conv_textview.emit('key_press_event', event)
				return True
		elif event.state & gtk.gdk.CONTROL_MASK or \
			  (event.keyval == gtk.keysyms.Control_L) or \
			  (event.keyval == gtk.keysyms.Control_R):
			# we pressed a control key or ctrl+sth: we don't block
			# the event in order to let ctrl+c (copy text) and
			# others do their default work
			self.conv_textview.emit('key_press_event', event)
		return False

	def _on_message_textview_mykeypress_event(self, widget, event_keyval,
						event_keymod):
		'''When a key is pressed:
		if enter is pressed without the shift key, message (if not empty) is sent
		and printed in the conversation'''

		# NOTE: handles mykeypress which is custom signal connected to this
		# CB in new_tab(). for this singal see message_textview.py
		jid = self.contact.jid
		message_textview = widget
		message_buffer = message_textview.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()
		message = message_buffer.get_text(start_iter, end_iter, False).decode('utf-8')

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
				
			if gajim.connections[self.account].connected < 2: # we are not connected
				dialogs.ErrorDialog(_('A connection is not available'),
					_('Your message can not be sent until you are connected.')).get_response()
				send_message = False

			if send_message:
				self.send_message(message) # send the message

	def _process_command(self, message):
		if not message:
			return False
		if message == '/clear':
			self.conv_textview.clear() # clear conversation
			# FIXME: Need this function
			self.clear(self.msg_textview) # clear message textview too
			return True
		elif message == '/compact':
			self.set_compact_view(not self.compact_view_current)
			# FIXME: Need this function
			self.clear(self.msg_textview)
			return True
		else:
			return False

	def send_message(self, message, keyID = '', type = 'chat', chatstate = None):
		'''Send the given message to the active tab'''
		if not message or message == '\n':
			return

		if not self._process_command(message):
			MessageControl.send_message(self, message, keyID, type = type,
					chatstate = chatstate)
			# Record message history
			self.save_sent_message(message)

		# Clear msg input
		message_buffer = self.msg_textview.get_buffer()
		message_buffer.set_text('') # clear message buffer (and tv of course)
# FIXME GC ONLY
#		if contact is None:
#			# contact was from pm in MUC
#			room, nick = gajim.get_room_and_nick_from_fjid(jid)
#			gc_contact = gajim.contacts.get_gc_contact(self.account, room, nick)
#			if not gc_contact:
#				# contact left the room, or we left the room
#				dialogs.ErrorDialog(_('Sending private message failed'),
#					#in second %s code replaces with nickname
#					_('You are no longer in room "%s" or "%s" has left.') % \
#					(room, nick)).get_response()
#				return


	def save_sent_message(self, message):
		#save the message, so user can scroll though the list with key up/down
		size = len(self.sent_history)
		#we don't want size of the buffer to grow indefinately
		max_size = gajim.config.get('key_up_lines')
		if size >= max_size:
			for i in xrange(0, size - 1): 
				self.sent_history[i] = self.sent_history[i + 1]
			self.sent_history[max_size - 1] = message
		else:
			self.sent_history.append(message)
			self.sent_history_pos = size + 1

		self.typing_new = True
		self.orig_msg = ''

	def print_conversation_line(self, text, kind, name, tim,
				other_tags_for_name = [], other_tags_for_time = [], 
				other_tags_for_text = [], count_as_new = True, subject = None):
		'''prints 'chat' type messages'''
		jid = self.contact.jid
		textview = self.conv_textview
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
		if (not self.parent_win.get_active_jid() or\
		jid != self.parent_win.get_active_jid() or \
		not self.parent_win.is_active() or not end) and\
	   	kind in ('incoming', 'incoming_queue'):
			self.nb_unread += 1
			if gajim.interface.systray_enabled and\
				gajim.config.get('trayicon_notification_on_new_messages'):
				gajim.interface.systray.add_jid(jid, self.account, self.type_id)
			self.parent_win.redraw_tab(self.contact)
			self.parent_win.show_title(urgent)

	def toggle_emoticons(self):
		'''hide show emoticons_button and make sure emoticons_menu is always there
		when needed'''
		emoticons_button = self.xml.get_widget('emoticons_button')
		if gajim.config.get('useemoticons'):
			self.emoticons_menu = self.prepare_emoticons_menu()
			emoticons_button.show()
			emoticons_button.set_no_show_all(False)
		else:
			self.emoticons_menu = None
			emoticons_button.hide()
			emoticons_button.set_no_show_all(True)

	def prepare_emoticons_menu(self):
		menu = gtk.Menu()
	
		def append_emoticon(w, d):
			buffer = self.msg_textview.get_buffer()
			if buffer.get_char_count():
				buffer.insert_at_cursor(' %s ' % d)
			else: # we are the beginning of buffer
				buffer.insert_at_cursor('%s ' % d)
			self.msg_textview.grab_focus()
	
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

	def on_emoticons_button_clicked(self, widget):
		'''popup emoticons menu'''
		#FIXME: BUG http://bugs.gnome.org/show_bug.cgi?id=316786
		self.button_clicked = widget
		self.emoticons_menu.popup(None, None, self.position_menu_under_button, 1, 0)

	def on_actions_button_clicked(self, widget):
		'''popup action menu'''
		#FIXME: BUG http://bugs.gnome.org/show_bug.cgi?id=316786
		self.button_clicked = widget
		
		menu = self.prepare_context_menu()
		menu.show_all()
		menu.popup(None, None, self.position_menu_under_button, 1, 0)

	def update_font(self):
		font = pango.FontDescription(gajim.config.get('conversation_font'))
		self.conv_textview.modify_font(font)
		self.msg_textview.modify_font(font)

	def update_tags(self):
		self.conv_textview.update_tags()

	def set_compact_view(self, state):
		'''Toggle compact view. state is bool'''
		MessageControl.set_compact_view(self, state)
		# make the last message visible, when changing to "full view"
		if not state:
			gobject.idle_add(self.conv_textview.scroll_to_end_iter)

	def clear(self, tv):
		buffer = tv.get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)

	def print_time_timeout(self, arg):
		if gajim.config.get('print_time') == 'sometimes':
			conv_textview = self.conv_textview
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
		if self.print_time_timeout_id:
			del self.print_time_timeout_id
		return False

	def on_history_menuitem_clicked(self, widget = None, jid = None):
		'''When history menuitem is pressed: call history window'''
		# FIXME for GC, jid is None
		print widget, jid
		if gajim.interface.instances['logs'].has_key(jid):
			gajim.interface.instances['logs'][jid].window.present()
		else:
			gajim.interface.instances['logs'][jid] = history_window.HistoryWindow(
				jid, self.account)

	def set_control_active(self, state):
		if state:
			jid = self.contact.jid
			if self.conv_textview.at_the_end():
				#we are at the end
				if self.nb_unread > 0:
					self.nb_unread = 0 + self.get_specific_unread()
					self.parent_win.redraw_tab(self.contact)
					self.parent_win.show_title()
					if gajim.interface.systray_enabled:
						gajim.interface.systray.remove_jid(jid,
										self.account,
										self.type_id)
			self.msg_textview.grab_focus()

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

		min_height = self.conv_scrolledwindow.get_property('height-request')
		conversation_height = self.conv_textview.window.get_size()[1]
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
					self.msg_scrolledwindow.set_property('vscrollbar-policy', 
						gtk.POLICY_AUTOMATIC)
					self.msg_scrolledwindow.set_property('height-request', 
						message_height + conversation_height - min_height)
					self.bring_scroll_to_end(msg_textview)
			else:
				self.msg_scrolledwindow.set_property('vscrollbar-policy', 
					gtk.POLICY_NEVER)
				self.msg_scrolledwindow.set_property('height-request', -1)

		self.conv_textview.bring_scroll_to_end(diff_y - 18)
		
		# enable scrollbar automatic policy for horizontal scrollbar
		# if message we have in message_textview is too big
		if requisition.width > message_width:
			self.msg_scrolledwindow.set_property('hscrollbar-policy', 
				gtk.POLICY_AUTOMATIC)
		else:
			self.msg_scrolledwindow.set_property('hscrollbar-policy', 
				gtk.POLICY_NEVER)

		return True

	def on_conversation_vadjustment_value_changed(self, widget):
		if not self.nb_unread:
			return
		jid = self.contact.jid
		if self.conv_textview.at_the_end() and self.window.is_active():
			#we are at the end
			self.nb_unread = self.get_specific_unread()
			self.parent_win.redraw_tab(jid)
			self.parent_win.show_title()
			if gajim.interface.systray_enabled:
				gajim.interface.systray.remove_jid(jid, self.account,
									self.type_id)

	def sent_messages_scroll(self, direction, conv_buf):
		size = len(self.sent_history) 
		if self.typing_new:
			#user was typing something and then went into history, so save
			#whatever is already typed
			start_iter = conv_buf.get_start_iter()
			end_iter = conv_buf.get_end_iter()
			self.orig_msg = conv_buf.get_text(start_iter, end_iter, 0).decode('utf-8')
			self.typing_new = False
		if direction == 'up':
			if self.sent_history_pos == 0:
				return
			self.sent_history_pos = self.sent_history_pos - 1
			conv_buf.set_text(self.sent_history[self.sent_history_pos])
		elif direction == 'down':
			if self.sent_history_pos >= size - 1:
				conv_buf.set_text(self.orig_msg);
				self.typing_new = True
				self.sent_history_pos = size
				return

			self.sent_history_pos = self.sent_history_pos + 1
			conv_buf.set_text(self.sent_history[self.sent_history_pos])

	def lighten_color(self, color):
		p = 0.4
		mask = 0
		color.red = int((color.red * p) + (mask * (1 - p)))
		color.green = int((color.green * p) + (mask * (1 - p)))
		color.blue = int((color.blue * p) + (mask * (1 - p)))
		return color

################################################################################
class ChatControl(ChatControlBase):
	'''A control for standard 1-1 chat'''
	TYPE_ID = message_control.TYPE_CHAT

	def __init__(self, parent_win, contact, acct):
		ChatControlBase.__init__(self, self.TYPE_ID, parent_win, 'chat_child_vbox',
				         _('Chat'), contact, acct)
		self.compact_view_always = gajim.config.get('always_compact_view_chat')
		self.set_compact_view(self.compact_view_always)

		xm = gtk.glade.XML(GTKGUI_GLADE, 'chat_control_popup_menu', APP)
		xm.signal_autoconnect(self)
		self.popup_menu = xm.get_widget('chat_control_popup_menu')

		# Initialize drag-n-drop
		self.TARGET_TYPE_URI_LIST = 80
		self.dnd_list = [ ( 'text/uri-list', 0, self.TARGET_TYPE_URI_LIST ) ]
		self.widget.connect('drag_data_received', self._on_drag_data_received)
		self.widget.drag_dest_set(gtk.DEST_DEFAULT_MOTION | gtk.DEST_DEFAULT_HIGHLIGHT |
					gtk.DEST_DEFAULT_DROP,
					self.dnd_list, gtk.gdk.ACTION_COPY)

		# keep timeout id and window obj for possible big avatar
		# it is on enter-notify and leave-notify so no need to be per jid
		self.show_bigger_avatar_timeout_id = None
		self.bigger_avatar_window = None
		self.show_avatar(self.contact.resource)			

		# chatstate timers and state
		self.reset_kbd_mouse_timeout_vars()
		self._schedule_activity_timers()

		# Hook up signals
		# FIXME: This does not seem to be working
		self.parent_win.window.connect('motion-notify-event',
						self._on_window_motion_notify)
		message_tv_buffer = self.msg_textview.get_buffer()
		message_tv_buffer.connect('changed', self._on_message_tv_buffer_changed)

		self.xml.get_widget('banner_eventbox').connect('button-press-event',
					self._on_banner_eventbox_button_press_event)
		self.xml.get_widget('banner_eventbox').connect('button-press-event',
					self._on_banner_eventbox_button_press_event)
		xm = gtk.glade.XML(GTKGUI_GLADE, 'avatar_eventbox', APP)
		xm.signal_autoconnect(self)

		if self.contact.jid in gajim.encrypted_chats[self.account]:
			self.xml.get_widget('gpg_togglebutton').set_active(True)

		self.draw_widgets()
		# restore previous conversation
		self.restore_conversation()

	def on_avatar_eventbox_enter_notify_event(self, widget, event):
		'''we enter the eventbox area so we under conditions add a timeout
		to show a bigger avatar after 0.5 sec'''
		jid = self.contact.jid
		real_jid = gajim.get_real_jid_from_fjid(self.account, jid)
		if not real_jid: # this can happend if we're in a moderate room
			return
		avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(real_jid)
		if avatar_pixbuf in ('ask', None):
			return
		avatar_w = avatar_pixbuf.get_width()
		avatar_h = avatar_pixbuf.get_height()
		
		scaled_buf = self.xmls[jid].get_widget('avatar_image').get_pixbuf()
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

	def save_var(self, jid):
		gpg_enabled = self.xmls[jid].get_widget('gpg_togglebutton').get_active()
		return {'gpg_enabled': gpg_enabled}

	def load_var(self, jid, var):
		if not self.xmls.has_key(jid):
			return
		self.xmls[jid].get_widget('gpg_togglebutton').set_active(
			var['gpg_enabled'])

	def _on_window_motion_notify(self, widget, event):
		'''it gets called no matter if it is the active window or not'''
		# FIXME NOT WORKING
		print "_on_window_motion_notify"
		if widget.get_property('has-toplevel-focus'):
			# change chatstate only if window is the active one
			self.mouse_over_in_last_5_secs = True
			self.mouse_over_in_last_30_secs = True


	def _schedule_activity_timers(self):
		self.possible_paused_timeout_id = gobject.timeout_add(5000,
				self.check_for_possible_paused_chatstate, None)
		self.possible_inactive_timeout_id = gobject.timeout_add(30000,
				self.check_for_possible_inactive_chatstate, None)

	def draw_widgets(self):
		# The name banner is drawn here
		ChatControlBase.draw_widgets(self)

	def _update_banner_state_image(self):
		# FIXME: The cyling of contact_list ... is this necessary if I have the contact
		contact = self.contact
		show = contact.show
		jid = contact.jid

		# Set banner image
		img_32 = gajim.interface.roster.get_appropriate_state_images(jid,
									size = '32')
		img_16 = gajim.interface.roster.get_appropriate_state_images(jid)
		if img_32.has_key(show) and img_32[show].get_pixbuf():
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
			if use_size_32:
				banner_status_img.set_from_pixbuf(pix)
			else: # we need to scale 16x16 to 32x32
				scaled_pix = pix.scale_simple(32, 32,
								gtk.gdk.INTERP_BILINEAR)
				banner_status_img.set_from_pixbuf(scaled_pix)

		self._update_gpg()

	def draw_banner(self, chatstate = None):
		'''Draw the fat line at the top of the window that 
		houses the status icon, name, jid, and avatar.  The chatstate arg should
		only be used if the control's chatstate member is NOT to be use, such as
		composing, paused, etc.
		'''
		ChatControlBase.draw_banner(self)

		contact = self.contact
		jid = contact.jid

		banner_name_label = self.xml.get_widget('banner_name_label')
		name = gtkgui_helpers.escape_for_pango_markup(contact.name)
		
		status = contact.status
		if status is not None:
			banner_name_label.set_ellipsize(pango.ELLIPSIZE_END)
			status = gtkgui_helpers.reduce_chars_newlines(status, 0, 2)
		status = gtkgui_helpers.escape_for_pango_markup(status)

		#FIXME: uncomment me when we support sending messages to specific resource
		# composing full jid
		#fulljid = jid
		#if self.contacts[jid].resource:
		#	fulljid += '/' + self.contacts[jid].resource
		#label_text = '<span weight="heavy" size="x-large">%s</span>\n%s' \
		#	% (name, fulljid)
		
		st = gajim.config.get('chat_state_notifications')
		cs = contact.chatstate
		if cs and st in ('composing_only', 'all'):
			if contact.show == 'offline':
				chatstate = ''
			elif st == 'all':
				chatstate = helpers.get_uf_chatstate(cs)
			else: # 'composing_only'
				if chatstate in ('composing', 'paused'):
					# only print composing, paused
					chatstate = helpers.get_uf_chatstate(cs)
				else:
					chatstate = ''
			label_text = \
			'<span weight="heavy" size="x-large">%s</span> %s' % (name,
										chatstate)
		else:
			label_text = '<span weight="heavy" size="x-large">%s</span>' % name
		
		if status is not None:
			label_text += '\n%s' % status

		# setup the label that holds name and jid
		banner_name_label.set_markup(label_text)

	def _update_gpg(self):
		tb = self.xml.get_widget('gpg_togglebutton')
		if self.contact.keyID: # we can do gpg
			tb.set_sensitive(True)
			tt = _('OpenPGP Encryption')
		else:
			tb.set_sensitive(False)
			#we talk about a contact here
			tt = _('%s has not broadcasted an OpenPGP key nor you have '\
				'assigned one') % self.contact.name
		gtk.Tooltips().set_tip(self.xml.get_widget('gpg_eventbox'), tt)

	def send_message(self, message, keyID = '', chatstate = None):
		'''Send a message to contact'''
		if not message or message == '\n' or self._process_command(message):
			return

		# refresh timers
		self.reset_kbd_mouse_timeout_vars()

		contact = self.contact
		jid = self.contact.jid

		keyID = ''
		encrypted = False
		if self.xml.get_widget('gpg_togglebutton').get_active():
			keyID = contact.keyID
			encrypted = True


		chatstates_on = gajim.config.get('chat_state_notifications') != 'disabled'
		chatstate_to_send = None
		if chatstates_on and contact is not None:
			if contact.our_chatstate is None:
				# no info about peer
				# send active to discover chat state capabilities
				# this is here (and not in send_chatstate)
				# because we want it sent with REAL message
				# (not standlone) eg. one that has body
				chatstate_to_send = 'active'
				contact.our_chatstate = 'ask' # pseudo state
			# if peer supports jep85 and we are not 'ask', send 'active'
			# NOTE: first active and 'ask' is set in gajim.py
			elif contact.our_chatstate not in (False, 'ask'):
				#send active chatstate on every message (as JEP says)
				chatstate_to_send = 'active'
				contact.our_chatstate = 'active'

				gobject.source_remove(self.possible_paused_timeout_id)
				gobject.source_remove(self.possible_inactive_timeout_id)
				self._schedule_activity_timers()
				
		ChatControlBase.send_message(self, message, keyID, type = 'chat',
				chatstate = chatstate_to_send)
		self.print_conversation(message, self.contact.jid, encrypted = encrypted)

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
			# FIXME: Need send_chatstate
			self.send_chatstate('composing')
		elif self.mouse_over_in_last_5_secs and\
			jid == self.parent_win.get_active_jid():
			self.send_chatstate('active')
		else:
			if current_state == 'composing':
				self.send_chatstate('paused') # pause composing

		# assume no activity and let the motion-notify or 'insert-text' make them True
		# refresh 30 seconds vars too or else it's 30 - 5 = 25 seconds!
		self.reset_kbd_mouse_timeout_vars()
		return True # loop forever		

	def check_for_possible_inactive_chatstate(self, arg):
		''' did we move mouse over that window or wrote something in message
		textview in the last 30 seconds?
		if yes we go active
		if no we go inactive '''
		contact = self.contact
		jid = contact.jid

		current_state = contact.our_chatstate
		if current_state is False: # jid doesn't support chatstates
			return False # stop looping

		if self.mouse_over_in_last_5_secs or self.kbd_activity_in_last_5_secs:
			return True # loop forever

		if not self.mouse_over_in_last_30_secs or self.kbd_activity_in_last_30_secs:
			self.send_chatstate('inactive', contact)

		# assume no activity and let the motion-notify or 'insert-text' make them True
		# refresh 30 seconds too or else it's 30 - 5 = 25 seconds!
		self.reset_kbd_mouse_timeout_vars()
		return True # loop forever

	def reset_kbd_mouse_timeout_vars(self):
		self.kbd_activity_in_last_5_secs = False
		self.mouse_over_in_last_5_secs = False
		self.mouse_over_in_last_30_secs = False
		self.kbd_activity_in_last_30_secs = False

	def print_conversation(self, text, frm = '', tim = None,
				encrypted = False, subject = None):
		'''Print a line in the conversation:
		if contact is set to status: it's a status message
		if contact is set to another value: it's an outgoing message
		if contact is set to print_queue: it is incomming from queue
		if contact is not set: it's an incomming message'''
		contact = self.contact
		jid = contact.jid

		if frm == 'status':
			kind = 'status'
			name = ''
		else:
			ec = gajim.encrypted_chats[self.account]
			if encrypted and jid not in ec:
				msg = _('Encryption enabled')
				ChatControlBase.print_conversation_line(self, msg, 
					'status', '', tim)
				ec.append(jid)
			if not encrypted and jid in ec:
				msg = _('Encryption disabled')
				ChatControlBase.print_conversation_line(self, msg,
					'status', '', tim)
				ec.remove(jid)
			self.xml.get_widget('gpg_togglebutton').set_active(encrypted)
			if not frm:
				kind = 'incoming'
				name = contact.name
			elif frm == 'print_queue': # incoming message, but do not update time
				kind = 'incoming_queue'
				name = contact.name
			else:
				kind = 'outgoing'
				name = gajim.nicks[self.account] 
		ChatControlBase.print_conversation_line(self, text, kind, name, tim,
			subject = subject)

	def get_tab_label(self, chatstate):
		unread = ''
		num_unread = self.nb_unread
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
				color = gajim.config.get_per('themes', theme,
						'state_gone_color')
			elif chatstate == 'paused':
				color = gajim.config.get_per('themes', theme,
						'state_paused_color')
			else:
				color = gajim.config.get_per('themes', theme,
						'state_active_color')
		if color:
			color = gtk.gdk.colormap_get_system().alloc_color(color)
			# We set the color for when it's the current tab or not
			# FIXME: why was this only happening for inactive or gone
			#if chatstate in ('inactive', 'gone'):
			# In inactive tab color to be lighter against the darker inactive
			# background
			if self.parent_win.get_active_control() != self:
				color = self.lighten_color(color)

		label_str = self.contact.name
		if num_unread: # if unread, text in the label becomes bold
			label_str = '<b>' + unread + label_str + '</b>'
		return (label_str, color)

	def get_tab_image(self):
		num_unread = self.nb_unread
		# Set tab image (always 16x16); unread messages show the 'message' image
		img_16 = gajim.interface.roster.get_appropriate_state_images(self.contact.jid)
		tab_img = None
		
		if num_unread and gajim.config.get('show_unread_tab_icon'):
			tab_img = img_16['message']
		else:
			tab_img = img_16[self.contact.show]

		return tab_img

	def remove_possible_switch_to_menuitems(self, menu):
		''' remove duplicate 'Switch to' if they exist and return clean menu'''
		childs = menu.get_children()

		contact = self.parent_win.get_active_contact()
		jid = contact.jid
		if _('not in the roster') in contact.groups: # for add_to_roster_menuitem
			childs[5].show()
			childs[5].set_no_show_all(False)
		else:
			childs[5].hide()
			childs[5].set_no_show_all(True)
		start_removing_from = 6 # this is from the seperator and after
			
# FIXME: GC only
#		elif :
#			start_removing_from = 7 # # this is from the seperator and after
				
		for child in childs[start_removing_from:]:
			menu.remove(child)
		return menu

	def prepare_context_menu(self):
		'''sets compact view menuitem active state
		sets active and sensitivity state for toggle_gpg_menuitem
		and remove possible 'Switch to' menuitems'''
		menu = self.popup_menu
		childs = menu.get_children()
		# check if gpg capabitlies or else make gpg toggle insensitive
		contact = self.parent_win.get_active_contact()
		jid = contact.jid
		gpg_btn = self.xml.get_widget('gpg_togglebutton')
		isactive = gpg_btn.get_active()
		issensitive = gpg_btn.get_property('sensitive')
		childs[3].set_active(isactive)
		childs[3].set_property('sensitive', issensitive)
		# If we don't have resource, we can't do file transfer
		if not contact.resource:
			childs[2].set_sensitive(False)
		else:
			childs[2].set_sensitive(True)
		# compact_view_menuitem
		childs[4].set_active(self.compact_view_current)
		menu = self.remove_possible_switch_to_menuitems(menu)
		
		return menu

	def set_compact_view(self, state):
		'''Toggle compact view. state is bool'''
		ChatControlBase.set_compact_view(self, state)

		widgets = [
		self.xml.get_widget('banner_eventbox'),
		self.xml.get_widget('actions_hbox'),
		]
# FIXME GC only
#		elif self.widget_name == 'groupchat_window':
#			widgets = [self.xmls[jid].get_widget('banner_eventbox'),
#				self.xmls[jid].get_widget('gc_actions_hbox'),
#				self.xmls[jid].get_widget('list_scrolledwindow'),
#				 ]
		for widget in widgets:
			if state:
				widget.set_no_show_all(True)
				widget.hide()
			else:
				widget.set_no_show_all(False)
				widget.show_all()

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
		chatstate_setting = gajim.config.get('chat_state_notifications')
		if chatstate_setting == 'disabled':
			return
		elif chatstate_setting == 'composing_only' and state != 'active' and\
			state != 'composing':
			return

		if contact is None:
			contact = self.parent_win.get_active_contact()
			jid = contact.jid
		else:
			jid = contact.jid

		if contact is None:
			# contact was from pm in MUC, and left the room so contact is None
			# so we cannot send chatstate anymore
			return

		# Don't send chatstates to offline contacts
		if contact.show == 'offline':
			return

		if contact.our_chatstate is False: # jid cannot do jep85
			return

		# if the new state we wanna send (state) equals 
		# the current state (contact.our_chatstate) then return
		if contact.our_chatstate == state:
			return

		if contact.our_chatstate is None:
			# we don't know anything about jid, so return
			# NOTE:
			# send 'active', set current state to 'ask' and return is done
			# in self.send_message() because we need REAL message (with <body>)
			# for that procedure so return to make sure we send only once
			# 'active' until we know peer supports jep85
			return 

		if contact.our_chatstate == 'ask':
			return

		# prevent going paused if we we were not composing (JEP violation)
		if state == 'paused' and not contact.our_chatstate == 'composing':
			MessageControl.send_message(self, None, chatstate = 'active') # go active before
			contact.our_chatstate = 'active'
			self.reset_kbd_mouse_timeout_vars()
		
		# if we're inactive prevent composing (JEP violation)
		if contact.our_chatstate == 'inactive' and state == 'composing':
			MessageControl.send_message(self, None, chatstate = 'active') # go active before
			contact.our_chatstate = 'active'
			self.reset_kbd_mouse_timeout_vars()

		MessageControl.send_message(self, None, chatstate = state)
		contact.our_chatstate = state
		if contact.our_chatstate == 'active':
			self.reset_kbd_mouse_timeout_vars()

	def shutdown(self):
		# Send 'gone' chatstate
		self.send_chatstate('gone', self.contact)
		self.contact.chatstate = None
		self.contact.our_chatstate = None
		# Disconnect timer callbacks
		gobject.source_remove(self.possible_paused_timeout_id)
		gobject.source_remove(self.possible_inactive_timeout_id)
		if self.print_time_timeout_id:
			gobject.source_remove(self.print_time_timeout_id)
		# Clean up systray
		if gajim.interface.systray_enabled and self.nb_unread > 0:
			gajim.interface.systray.remove_jid(self.contact.jid, self.account,
								self.type)

	def allow_shutdown(self):
		jid = self.contact.jid
		if time.time() - gajim.last_message_time[self.account][jid] < 2:
			# 2 seconds
			dialog = dialogs.ConfirmationDialog(
				#%s is being replaced in the code with JID
				_('You just received a new message from "%s"' % jid),
				_('If you close this tab and you have history disabled, '\
				'this message will be lost.'))
			if dialog.get_response() != gtk.RESPONSE_OK:
				return False #stop the propagation of the event
		return True

	def handle_incoming_chatstate(self):
		''' handle incoming chatstate that jid SENT TO us '''
		self.draw_banner()
		# update chatstate in tab for this chat
		self.parent_win.redraw_tab(self.contact, self.contact.chatstate)

	def _on_banner_eventbox_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3: # right click
			self.parent_win.popup_menu(event)

	def set_control_active(self, state):
		ChatControlBase.set_control_active(self, state)
		# send chatstate inactive to the one we're leaving
		# and active to the one we visit
		if state:
			self.send_chatstate('active', self.contact)
		else:
			self.send_chatstate('inactive', self.contact)

	def show_avatar(self, resource = None):
		jid = self.contact.jid
		jid_with_resource = jid
		if resource:
			jid_with_resource += '/' + resource

		# we assume contact has no avatar
		scaled_pixbuf = None

		real_jid = gajim.get_real_jid_from_fjid(self.account, jid)
		pixbuf = None
		if real_jid:
			pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(real_jid)
		if not real_jid or pixbuf == 'ask':
			# we don't have the vcard or it's pm and we don't have the real jid
			gajim.connections[self.account].request_vcard(jid_with_resource)
			return
		if pixbuf is not None:
			scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'chat')

		image = self.xml.get_widget('avatar_image')
		image.set_from_pixbuf(scaled_pixbuf)
		image.show_all()

	def _on_drag_data_received(self, widget, context, x, y, selection, target_type,
				timestamp):
		# If not resource, we can't send file
		if not self.contact.resource:
			return
		if target_type == self.TARGET_TYPE_URI_LIST:
			uri = selection.data.strip()
			uri_splitted = uri.split() # we may have more than one file dropped
			for uri in uri_splitted:
				path = helpers.get_file_path_from_dnd_dropped_uri(uri)
				if os.path.isfile(path): # is it file?
					ft = gajim.interface.instances['file_transfers']
					ft.send_file(self.account, self.contact, path)

	def _on_message_tv_buffer_changed(self, textbuffer):
		self.kbd_activity_in_last_5_secs = True
		self.kbd_activity_in_last_30_secs = True
		if textbuffer.get_char_count():
			self.send_chatstate('composing', self.contact)
		else:
			self.send_chatstate('active', self.contact)

	def restore_conversation(self):
		jid = self.contact.jid
		# don't restore lines if it's a transport
		if gajim.jid_is_transport(jid):
			return
		
		# How many lines to restore and when to time them out
		restore_how_many = gajim.config.get('restore_lines')
		timeout = gajim.config.get('restore_timeout') # in minutes
		# number of messages that are in queue and are already logged
		pending_how_many = 0 # we want to avoid duplication
		
		if gajim.awaiting_events[self.account].has_key(jid):
			events = gajim.awaiting_events[self.account][jid]
			for event in events:
				if event[0] == 'chat':
					pending_how_many += 1

		rows = gajim.logger.get_last_conversation_lines(jid, restore_how_many,
			pending_how_many, timeout)
		
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
				name = self.contact.name

			tim = time.localtime(float(row[0]))

			ChatControlBase.print_conversation_line(self, row[2], kind, name, tim,
								['small'],
								['small', 'restored_message'],
								['small', 'restored_message'],
								False)
		if len(rows):
			self.conv_textview.print_empty_line()

	def read_queue(self):
		'''read queue and print messages containted in it'''
		jid = self.contact.jid
		l = gajim.awaiting_events[self.account][jid]

		# Is it a pm ?
		is_pm = False
		room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
		# FIXME: Accessing gc's, here? 
		gcs = gajim.interface.instances[self.account]['gc']
		if gcs.has_key(room_jid):
			is_pm = True
		events_to_keep = []
		for event in l:
			typ = event[0]
			if typ != 'chat':
				events_to_keep.append(event)
				continue
			data = event[1]
			kind = data[2]
			if kind == 'error':
				kind = 'status'
			else:
				kind = 'print_queue'
			self.print_conversation(data[0], kind, tim = data[3],
				encrypted = data[4], subject = data[1])

			# remove from gc nb_unread if it's pm or from roster
			if is_pm:
				gcs[room_jid].nb_unread[room_jid] -= 1
			else:
				gajim.interface.roster.nb_unread -= 1

		if is_pm:
			gcs[room_jid].show_title()
		else:
			gajim.interface.roster.show_title()
		# Keep only non-messages events
		if len(events_to_keep):
			gajim.awaiting_events[self.account][jid] = events_to_keep
		else:
			del gajim.awaiting_events[self.account][jid]
		typ = 'chat' # Is it a normal chat or a pm ?
#		# reset to status image in gc if it is a pm
#		# FIXME: New data structure
#		gcs = gajim.interface.instances[self.account]['gc']
#		if gcs.has_key(room_jid):
#			gcs[room_jid].draw_all_roster()
#			typ = 'pm'

		gajim.interface.roster.draw_contact(jid, self.account)
		if gajim.interface.systray_enabled:
			gajim.interface.systray.remove_jid(jid, self.account, typ)
		if (self.contact.show == 'offline' or self.contact.show == 'error'):
			showOffline = gajim.config.get('showoffline')
			if not showOffline and typ == 'chat' and \
				len(gajim.contacts[self.account][jid]) == 1:
				gajim.interface.roster.really_remove_contact(self.contact,
										self.account)
			elif typ == 'pm':
				gcs[room_jid].remove_contact(room_jid, nick)

	def show_bigger_avatar(self, small_avatar):
		'''resizes the avatar, if needed, so it has at max half the screen size
		and shows it'''
		real_jid = gajim.get_real_jid_from_fjid(self.account, self.contact.jid)
		if not real_jid: # this can happend if we're in a moderate room
			return
		avatar_pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(real_jid)
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

	def _on_window_motion_notify_event(self, widget, event):
		'''we just moved the mouse so show the cursor'''
		cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
		self.bigger_avatar_window.window.set_cursor(cursor)

	def _on_compact_view_menuitem_activate(self, widget):
		isactive = widget.get_active()
		self.set_compact_view(isactive)

	def _on_send_file_menuitem_activate(self, widget):
		gajim.interface.instances['file_transfers'].show_file_send_request( 
			self.account, self.contact)

	def _on_add_to_roster_menuitem_activate(self, widget):
		dialogs.AddNewContactWindow(self.account, self.contact.jid)

	def _on_contact_information_menuitem_clicked(self, widget):
		gajim.interface.roster.on_info(widget, self.contact, self.account)

