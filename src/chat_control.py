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

import gtk
import gtk.glade
import pango
import gobject
import gtkgui_helpers
import message_window

from common import gajim
from message_window import MessageControl
from conversation_textview import ConversationTextview
from message_textview import MessageTextView

####################
# FIXME: Can't this stuff happen once?
from common import i18n
_ = i18n._
APP = i18n.APP

GTKGUI_GLADE = 'gtkgui.glade'

class ChatControlBase(MessageControl):
	# FIXME
	'''TODO
	Contains a banner, ConversationTextview, MessageTextView
	'''
	
	def draw_banner(self):
		self._paint_banner()
		self._update_banner_state_image()
		# Derived types SHOULD implement this
	def update_state(self):
		self.draw_banner()
		# Derived types SHOULD implement this
	def draw_widgets(self):
		self.draw_banner()
		# Derived types MUST implement this
	def repaint_themed_widgets(self):
		self.draw_banner()
		# NOTE: Derived classes MAY implement this
	def _update_banner_state_image(self):
		pass # Derived types MAY implement this

	def __init__(self, widget_name, contact):
		MessageControl.__init__(self, widget_name, contact);

		# FIXME: These are hidden from 0.8 on, but IMO all these things need
		#        to be shown optionally.  Esp. the never-used Send button
		for w in ('bold_togglebutton', 'italic_togglebutton',
			'underline_togglebutton'):
			self.xml.get_widget(w).set_no_show_all(True)

		# Create textviews and connect signals
		self.conv_textview = ConversationTextview(None) # FIXME: remove account arg
		self.conv_textview.show_all()
		scrolledwindow = self.xml.get_widget('conversation_scrolledwindow')
		scrolledwindow.add(self.conv_textview)
		self.conv_textview.connect('key_press_event',
				self.on_conversation_textview_key_press_event)
		# add MessageTextView to UI and connect signals
		message_scrolledwindow = self.xml.get_widget('message_scrolledwindow')
		self.msg_textview = MessageTextView()
		self.msg_textview.connect('mykeypress',
					self.on_message_textview_mykeypress_event)
		message_scrolledwindow.add(self.msg_textview)
		self.msg_textview.connect('key_press_event',
					self.on_message_textview_key_press_event)

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


	def on_conversation_textview_key_press_event(self, widget, event):
		'''Handle events from the ConversationTextview'''
		print "ChatControl.on_conversation_textview_key_press_event", event
		if event.state & gtk.gdk.CONTROL_MASK:
			# CTRL + l|L
			if event.keyval == gtk.keysyms.l or event.keyval == gtk.keysyms.L:
				self.conv_textview.get_buffer().set_text('')
			# CTRL + v
			elif event.keyval == gtk.keysyms.v:
				if not self.msg_textview.is_focus():
					self.msg_textview.grab_focus()
				self.msg_textview.emit('key_press_event', event)

	def on_message_textview_key_press_event(self, widget, event):
		print "ChatControl.on_message_textview_key_press_event", event

		if event.keyval == gtk.keysyms.Page_Down: # PAGE DOWN
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE DOWN
				self.notebook.emit('key_press_event', event)
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE DOWN
				self.conv_textview.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Page_Up: # PAGE UP
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE UP
				self.notebook.emit('key_press_event', event)
			if event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE UP
				self.conv_textview.emit('key_press_event', event)

	def on_message_textview_mykeypress_event(self, widget, event_keyval,
						event_keymod):
		'''When a key is pressed:
		if enter is pressed without the shift key, message (if not empty) is sent
		and printed in the conversation'''
		# FIXME: Need send_message
		assert(False)

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
				self.sent_messages_scroll(jid, 'up', widget.get_buffer())
				return
		elif event.keyval == gtk.keysyms.Down:
			if event.state & gtk.gdk.CONTROL_MASK: # Ctrl+Down
				self.sent_messages_scroll(jid, 'down', widget.get_buffer())
				return
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

			# FIXME: Define send_message (base class??)
			if send_message:
				self.send_message(message) # send the message
		

class ChatControl(ChatControlBase):
	'''A control for standard 1-1 chat'''
	def __init__(self, contact):
		ChatControlBase.__init__(self, 'chat_child_vbox', contact);
		self.compact_view = gajim.config.get('always_compact_view_chat')

	def draw_widgets(self):
		# The name banner is drawn here
		ChatControlBase.draw_widgets(self)

	def _update_banner_state_image(self):
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

	def draw_banner(self):
		'''Draw the fat line at the top of the window that 
		houses the status icon, name, jid, and avatar'''
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



