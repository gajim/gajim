##	tabbed_chat_window.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Travis Shirk <travis@pobox.com>
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
import os

import dialogs
import chat
import gtkgui_helpers

from common import gajim
from common import helpers
from common.logger import Constants
constants = Constants()

from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class TabbedChatWindow(chat.Chat):
	'''Class for tabbed chat window'''
	def __init__(self, contact, account):
		# we check that on opening new windows
		self.always_compact_view = gajim.config.get('always_compact_view_chat')
		chat.Chat.__init__(self, account, 'tabbed_chat_window')
		self.contacts = {}
		# keep check for possible paused timeouts per jid
		self.possible_paused_timeout_id = {}
		# keep check for possible inactive timeouts per jid
		self.possible_inactive_timeout_id = {}
		
		# keep timeout id and window obj for possible big avatar
		# it is on enter-notify and leave-notify so no need to be per jid
		self.show_bigger_avatar_timeout_id = None
		self.bigger_avatar_window = None
		
		self.TARGET_TYPE_URI_LIST = 80
		self.dnd_list = [ ( 'text/uri-list', 0, self.TARGET_TYPE_URI_LIST ) ]
		self.new_tab(contact)
		self.show_title()
	
		# NOTE: if it not a window event, do not connect here (new_tab() autoconnects)
		signal_dict = {
'on_tabbed_chat_window_destroy': self.on_tabbed_chat_window_destroy,
'on_tabbed_chat_window_delete_event': self.on_tabbed_chat_window_delete_event,
'on_tabbed_chat_window_focus_in_event': self.on_tabbed_chat_window_focus_in_event,
'on_chat_notebook_key_press_event': self.on_chat_notebook_key_press_event,
'on_chat_notebook_switch_page': self.on_chat_notebook_switch_page, # in chat.py
'on_tabbed_chat_window_motion_notify_event': self.on_tabbed_chat_window_motion_notify_event,
		}

		self.xml.signal_autoconnect(signal_dict)


		if gajim.config.get('saveposition') and \
			not gtkgui_helpers.one_window_opened('chats'):
			# get window position and size from config
			gtkgui_helpers.move_window(self.window, gajim.config.get('chat-x-position'),
				gajim.config.get('chat-y-position'))
			gtkgui_helpers.resize_window(self.window, gajim.config.get('chat-width'),
					gajim.config.get('chat-height'))

		# gtk+ doesn't make use of the motion notify on gtkwindow by default
		# so this line adds that
		self.window.set_events(gtk.gdk.POINTER_MOTION_MASK)
		
		self.window.show_all()
	
	def save_var(self, jid):
		'''return the specific variable of a jid, like gpg_enabled
		the return value have to be compatible with wthe one given to load_var'''
		gpg_enabled = self.xmls[jid].get_widget('gpg_togglebutton').get_active()
		return {'gpg_enabled': gpg_enabled}
	
	def load_var(self, jid, var):
		if not self.xmls.has_key(jid):
			return
		self.xmls[jid].get_widget('gpg_togglebutton').set_active(
			var['gpg_enabled'])
		
	def on_tabbed_chat_window_motion_notify_event(self, widget, event):
		'''it gets called no matter if it is the active window or not'''
		if widget.get_property('has-toplevel-focus'):
			# change chatstate only if window is the active one
			self.mouse_over_in_last_5_secs = True
			self.mouse_over_in_last_30_secs = True

	def on_drag_data_received(self, widget, context, x, y, selection,
		target_type, timestamp, contact):
		# If not resource, we can't send file
		if not contact.resource:
			return
		if target_type == self.TARGET_TYPE_URI_LIST:
			uri = selection.data.strip()
			uri_splitted = uri.split() # we may have more than one file dropped
			for uri in uri_splitted:
				path = helpers.get_file_path_from_dnd_dropped_uri(uri)
				if os.path.isfile(path): # is it file?
					gajim.interface.instances['file_transfers'].send_file(self.account,
						contact, path)

	def on_avatar_eventbox_enter_notify_event(self, widget, event):
		'''we enter the eventbox area so we under conditions add a timeout
		to show a bigger avatar after 0.5 sec'''
		jid = self.get_active_jid()
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

	def show_bigger_avatar(self, small_avatar):
		'''resizes the avatar, if needed, so it has at max half the screen size
		and shows it'''
		jid = self.get_active_jid()
		real_jid = gajim.get_real_jid_from_fjid(self.account, jid)
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
			self.on_window_avatar_leave_notify_event)
		window.connect('motion-notify-event',
			self.on_window_motion_notify_event)

		window.show_all()

	def on_window_avatar_leave_notify_event(self, widget, event):
		'''we just left the popup window that holds avatar'''
		self.bigger_avatar_window.destroy()

	def on_window_motion_notify_event(self, widget, event):
		'''we just moved the mouse so show the cursor'''
		cursor = gtk.gdk.Cursor(gtk.gdk.LEFT_PTR)
		self.bigger_avatar_window.window.set_cursor(cursor)

	def draw_widgets(self, contact):
		'''draw the widgets in a tab (f.e. gpg togglebutton)
		according to the the information in the contact variable'''
		jid = contact.jid
		self.set_state_image(jid)
		tb = self.xmls[jid].get_widget('gpg_togglebutton')
		if contact.keyID: # we can do gpg
			tb.set_sensitive(True)
			tt = _('OpenPGP Encryption')
		else:
			tb.set_sensitive(False)
			#we talk about a contact here
			tt = _('%s has not broadcasted an OpenPGP key nor you have assigned one') % contact.name
		tip = gtk.Tooltips()
		tip.set_tip(self.xmls[jid].get_widget('gpg_eventbox'), tt)

		# add the fat line at the top
		self.draw_name_banner(contact)

	def draw_name_banner(self, contact, chatstate = None):
		'''Draw the fat line at the top of the window that 
		houses the status icon, name, jid, and avatar'''
		# this is the text for the big brown bar
		# some chars need to be escaped..
		jid = contact.jid
		banner_name_label = self.xmls[jid].get_widget('banner_name_label')
		
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
		if contact.chatstate and st in ('composing_only', 'all'):
			if contact.show == 'offline':
				chatstate = ''
			elif st == 'all':
				chatstate = helpers.get_uf_chatstate(contact.chatstate)
			else: # 'composing_only'
				if chatstate in ('composing', 'paused'):
					# only print composing, paused
					chatstate = helpers.get_uf_chatstate(contact.chatstate)
				else:
					chatstate = ''
			label_text = \
			'<span weight="heavy" size="x-large">%s</span> %s' % (name, chatstate)
		else:
			label_text = '<span weight="heavy" size="x-large">%s</span>' % name
		
		if status is not None:
			label_text += '\n%s' % status

		# setup the label that holds name and jid
		banner_name_label.set_markup(label_text)
		self.paint_banner(jid)

	def get_specific_unread(self, jid):
		# return the number of unread (private) msgs with contacts in the room
		# when gc, and that is 0 in tc
		# FIXME: maybe refactor so this func is not called at all if TC?
		return 0

	def show_avatar(self, jid, resource):
		# Get the XML instance
		jid_with_resource = jid
		if resource:
			jid_with_resource += '/' + resource

		xml = None
		if self.xmls.has_key(jid):
			xml = self.xmls[jid]
		else:
			# it can be xmls[jid/resource] if it's a vcard from pm
			if self.xmls.has_key(jid_with_resource):
				xml = self.xmls[jid_with_resource]
		if not xml:
			return
		
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
			

		image = xml.get_widget('avatar_image')
		image.set_from_pixbuf(scaled_pixbuf)
		image.show_all()

	def set_state_image(self, jid):
		prio = 0
		contact_list = gajim.contacts.get_contact(self.account, jid)
		if not contact_list:
			contact_list = [self.contacts[jid]]

		contact = contact_list[0]
		show = contact.show
		jid = contact.jid
		keyID = contact.keyID

		for u in contact_list:
			if u.priority > prio:
				prio = u.priority
				show = u.show
				keyID = u.keyID
		child = self.childs[jid]
		hb = self.notebook.get_tab_label(child).get_children()[0]
		status_image = hb.get_children()[0]
		
		state_images_32 = gajim.interface.roster.get_appropriate_state_images(jid,
			size = '32')
		state_images_16 = gajim.interface.roster.get_appropriate_state_images(jid)

		# Set banner image
		if state_images_32.has_key(show) and state_images_32[show].get_pixbuf():
			# we have 32x32! use it!
			banner_image = state_images_32[show]
			use_size_32 = True
		else:
			banner_image = state_images_16[show]
			use_size_32 = False

		banner_status_image = self.xmls[jid].get_widget('banner_status_image')
		if banner_image.get_storage_type() == gtk.IMAGE_ANIMATION:
			banner_status_image.set_from_animation(banner_image.get_animation())
		else:
			pix = banner_image.get_pixbuf()
			if use_size_32:
				banner_status_image.set_from_pixbuf(pix)
			else: # we need to scale 16x16 to 32x32
				scaled_pix = pix.scale_simple(32, 32, gtk.gdk.INTERP_BILINEAR)
				banner_status_image.set_from_pixbuf(scaled_pix)

		# Set tab image (always 16x16); unread messages show the 'message' image
		if self.nb_unread[jid] and gajim.config.get('show_unread_tab_icon'):
			tab_image = state_images_16['message']
		else:
			tab_image = state_images_16[show]
		if tab_image.get_storage_type() == gtk.IMAGE_ANIMATION:
			status_image.set_from_animation(tab_image.get_animation())
		else:
			status_image.set_from_pixbuf(tab_image.get_pixbuf())

		if keyID:
			self.xmls[jid].get_widget('gpg_togglebutton').set_sensitive(True)
		else:
			self.xmls[jid].get_widget('gpg_togglebutton').set_sensitive(False)

	def on_tabbed_chat_window_delete_event(self, widget, event):
		'''close window'''
		for jid in self.contacts:
			if time.time() - gajim.last_message_time[self.account][jid] < 2:
				# 2 seconds
				dialog = dialogs.ConfirmationDialog(
					#%s is being replaced in the code with JID
					_('You just received a new message from "%s"' % jid),
					_('If you close this tab and you have history disabled, this message will be lost.'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return True #stop the propagation of the event

		if gajim.config.get('saveposition'):
			# save the window size and position
			x, y = self.window.get_position()
			gajim.config.set('chat-x-position', x)
			gajim.config.set('chat-y-position', y)
			width, height = self.window.get_size()
			gajim.config.set('chat-width', width)
			gajim.config.set('chat-height', height)

	def on_tabbed_chat_window_destroy(self, widget):
		# Reset contact chatstates to all open tabs
		for jid in self.xmls:
			self.send_chatstate('gone', jid)
			self.contacts[jid].chatstate = None
			self.contacts[jid].our_chatstate = None
		#clean gajim.interface.instances[self.account]['chats']
		chat.Chat.on_window_destroy(self, widget, 'chats')

	def on_tabbed_chat_window_focus_in_event(self, widget, event):
		chat.Chat.on_chat_window_focus_in_event(self, widget, event)
		# on focus in, send 'active' chatstate to current tab
		self.send_chatstate('active')
		
	def on_chat_notebook_key_press_event(self, widget, event):
		chat.Chat.on_chat_notebook_key_press_event(self, widget, event)

	def on_send_file_menuitem_activate(self, widget):
		jid = self.get_active_jid()
		contact = gajim.contacts.get_first_contact_from_jid(self.account, jid)
		gajim.interface.instances['file_transfers'].show_file_send_request( 
			self.account, contact)

	def on_add_to_roster_menuitem_activate(self, widget):
		jid = self.get_active_jid()
		dialogs.AddNewContactWindow(self.account, jid)

	def on_send_button_clicked(self, widget):
		'''When send button is pressed: send the current message'''
		jid = self.get_active_jid()
		message_textview = self.message_textviews[jid]
		message_buffer = message_textview.get_buffer()
		start_iter = message_buffer.get_start_iter()
		end_iter = message_buffer.get_end_iter()
		message = message_buffer.get_text(start_iter, end_iter, 0).decode('utf-8')

		# send the message
		self.send_message(message)

	def remove_tab(self, jid):
		if time.time() - gajim.last_message_time[self.account][jid] < 2:
			dialog = dialogs.ConfirmationDialog(
				_('You just received a new message from "%s"' % jid),
				_('If you close this tab and you have history disabled, the message will be lost.'))
			if dialog.get_response() != gtk.RESPONSE_OK:
				return

		# chatstates - tab is destroyed, send gone and reset
		self.send_chatstate('gone', jid)
		self.contacts[jid].chatstate = None
		self.contacts[jid].our_chatstate = None
		
		chat.Chat.remove_tab(self, jid, 'chats')
		del self.contacts[jid]

	def new_tab(self, contact):
		'''when new tab is created'''
		self.names[contact.jid] = contact.name
		self.xmls[contact.jid] = gtk.glade.XML(GTKGUI_GLADE, 'chats_vbox', APP)
		self.childs[contact.jid] = self.xmls[contact.jid].get_widget('chats_vbox')
		self.contacts[contact.jid] = contact

		self.show_avatar(contact.jid, contact.resource)			

		self.childs[contact.jid].connect('drag_data_received',
			self.on_drag_data_received, contact)
		self.childs[contact.jid].drag_dest_set( gtk.DEST_DEFAULT_MOTION |
			gtk.DEST_DEFAULT_HIGHLIGHT | gtk.DEST_DEFAULT_DROP,
			self.dnd_list, gtk.gdk.ACTION_COPY)

		chat.Chat.new_tab(self, contact.jid)

		msg_textview = self.message_textviews[contact.jid]
		message_tv_buffer = msg_textview.get_buffer()
		message_tv_buffer.connect('changed',
			self.on_message_tv_buffer_changed, contact)

		if contact.jid in gajim.encrypted_chats[self.account]:
			self.xmls[contact.jid].get_widget('gpg_togglebutton').set_active(True)

		xm = gtk.glade.XML(GTKGUI_GLADE, 'chat_control_popup_menu', APP)
		xm.signal_autoconnect(self)
		self.tabbed_chat_popup_menu = xm.get_widget('chat_control_popup_menu')

		self.redraw_tab(contact.jid)
		self.draw_widgets(contact)

		# restore previous conversation
		self.restore_conversation(contact.jid)

		if gajim.awaiting_events[self.account].has_key(contact.jid):
			self.read_queue(contact.jid)

		self.childs[contact.jid].show_all()

		# chatstates
		self.reset_kbd_mouse_timeout_vars()

		self.possible_paused_timeout_id[contact.jid] = gobject.timeout_add(
			5000, self.check_for_possible_paused_chatstate, contact.jid)
		self.possible_inactive_timeout_id[contact.jid] = gobject.timeout_add(
			30000, self.check_for_possible_inactive_chatstate, contact.jid)

	def handle_incoming_chatstate(self, account, contact):
		''' handle incoming chatstate that jid SENT TO us '''
		self.draw_name_banner(contact, contact.chatstate)
		# update chatstate in tab for this chat
		self.redraw_tab(contact.jid, contact.chatstate)

	def check_for_possible_paused_chatstate(self, jid):
		''' did we move mouse of that window or write something in message
		textview
		in the last 5 seconds?
		if yes we go active for mouse, composing for kbd
		if no we go paused if we were previously composing '''
		contact = gajim.contacts.get_first_contact_from_jid(self.account, jid)
		if jid not in self.xmls or contact is None:
			# the tab with jid is no longer open or contact left
			# stop timer
			return False # stop looping

		current_state = contact.our_chatstate
		if current_state is False: # jid doesn't support chatstates
			return False # stop looping

		message_textview = self.message_textviews[jid]
		message_buffer = message_textview.get_buffer()
		if self.kbd_activity_in_last_5_secs and message_buffer.get_char_count():
			# Only composing if the keyboard activity was in text entry
			self.send_chatstate('composing', jid)
		elif self.mouse_over_in_last_5_secs and jid == self.get_active_jid():
			self.send_chatstate('active', jid)
		else:
			if current_state == 'composing':
				self.send_chatstate('paused', jid) # pause composing

		# assume no activity and let the motion-notify or 'insert-text' make them True
		# refresh 30 seconds vars too or else it's 30 - 5 = 25 seconds!
		self.reset_kbd_mouse_timeout_vars()
		return True # loop forever

	def check_for_possible_inactive_chatstate(self, jid):
		''' did we move mouse over that window or wrote something in message
		textview
		in the last 30 seconds?
		if yes we go active
		if no we go inactive '''
		contact = gajim.contacts.get_first_contact_from_jid(self.account, jid)
		if jid not in self.xmls or contact is None:
			# the tab with jid is no longer open or contact left
			return False # stop looping

		current_state = contact.our_chatstate
		if current_state is False: # jid doesn't support chatstates
			return False # stop looping

		if self.mouse_over_in_last_5_secs or self.kbd_activity_in_last_5_secs:
			return True # loop forever

		if not (self.mouse_over_in_last_30_secs or\
			self.kbd_activity_in_last_30_secs):
			self.send_chatstate('inactive', jid)

		# assume no activity and let the motion-notify or 'insert-text' make them True
		# refresh 30 seconds too or else it's 30 - 5 = 25 seconds!
		self.reset_kbd_mouse_timeout_vars()

		return True # loop forever

	def on_message_tv_buffer_changed(self, textbuffer, contact):
		self.kbd_activity_in_last_5_secs = True
		self.kbd_activity_in_last_30_secs = True
		if textbuffer.get_char_count():
			self.send_chatstate('composing', contact.jid)
		else:
			self.send_chatstate('active', contact.jid)

	def reset_kbd_mouse_timeout_vars(self):
		self.kbd_activity_in_last_5_secs = False
		self.mouse_over_in_last_5_secs = False
		self.mouse_over_in_last_30_secs = False
		self.kbd_activity_in_last_30_secs = False

	def on_message_textview_mykeypress_event(self, widget, event_keyval,
	event_keymod):
		'''When a key is pressed:
		if enter is pressed without the shift key, message (if not empty) is sent
		and printed in the conversation'''
		# NOTE: handles mykeypress which is custom signal connected to this
		# CB in new_tab(). for this singal see message_textview.py
		jid = self.get_active_jid()
		conv_textview = self.conversation_textviews[jid]
		message_textview = widget
		message_buffer = message_textview.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()
		message = message_buffer.get_text(start_iter, end_iter, False).decode(
			'utf-8')

		# construct event instance from binding
		event = gtk.gdk.Event(gtk.gdk.KEY_PRESS) # it's always a key-press here
		event.keyval = event_keyval
		event.state = event_keymod
		event.time = 0 # assign current time

		if event.keyval == gtk.keysyms.ISO_Left_Tab: # SHIFT + TAB
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + SHIFT + TAB
				self.notebook.emit('key_press_event', event)
		if event.keyval == gtk.keysyms.Tab:
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + TAB
				self.notebook.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Up:
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

			if send_message:
				self.send_message(message) # send the message

	def send_chatstate(self, state, jid = None):
		''' sends OUR chatstate as STANDLONE chat state message (eg. no body)
		to jid only if new chatstate is different
		from the previous one
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
		elif chatstate_setting == 'composing_only' and state != 'active' and state != 'composing':
			return

		if jid is None:
			jid = self.get_active_jid()
			
		contact = gajim.contacts.get_first_contact_from_jid(self.account, jid)

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
			gajim.connections[self.account].send_message(jid, None, None,
				chatstate = 'active') # go active before
			contact.our_chatstate = 'active'
			self.reset_kbd_mouse_timeout_vars()
		
		# if we're inactive prevent composing (JEP violation)
		if contact.our_chatstate == 'inactive' and state == 'composing':
			gajim.connections[self.account].send_message(jid, None, None,
				chatstate = 'active') # go active before
			contact.our_chatstate = 'active'
			self.reset_kbd_mouse_timeout_vars()

		gajim.connections[self.account].send_message(jid, None, None,
			chatstate = state)
		contact.our_chatstate = state
		if contact.our_chatstate == 'active':
			self.reset_kbd_mouse_timeout_vars()

	def send_message(self, message):
		'''Send the given message to the active tab'''
		if not message:
			return

		jid = self.get_active_jid()
		contact = gajim.contacts.get_first_contact_from_jid(self.account, jid)
		if contact is None:
			# contact was from pm in MUC
			room, nick = gajim.get_room_and_nick_from_fjid(jid)
			gc_contact = gajim.contacts.get_gc_contact(self.account, room, nick)
			if not gc_contact:
				# contact left the room, or we left the room
				dialogs.ErrorDialog(_('Sending private message failed'),
					#in second %s code replaces with nickname
					_('You are no longer in room "%s" or "%s" has left.') % \
					(room, nick)).get_response()
				return

		conv_textview = self.conversation_textviews[jid]
		message_textview = self.message_textviews[jid]
		message_buffer = message_textview.get_buffer()

		if message != '' or message != '\n':
			self.save_sent_message(jid, message)
			if message == '/clear':
				conv_textview.clear() # clear conversation
				self.clear(message_textview) # clear message textview too
				return True
			elif message == '/compact':
				self.set_compact_view(not self.compact_view_current_state)
				self.clear(message_textview)
				return True
			keyID = ''
			encrypted = False
			if self.xmls[jid].get_widget('gpg_togglebutton').get_active():
				keyID = self.contacts[jid].keyID
				encrypted = True

			chatstates_on = gajim.config.get(
				'chat_state_notifications') != 'disabled'

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
					
					# refresh timers
					# avoid sending composing in less than 5 seconds
					# if we just send a message
					gobject.source_remove(self.possible_paused_timeout_id[jid])
					gobject.source_remove(self.possible_inactive_timeout_id[jid])
					self.possible_paused_timeout_id[jid] =\
			gobject.timeout_add(5000, self.check_for_possible_paused_chatstate,
				jid)
					self.possible_inactive_timeout_id[jid] =\
			gobject.timeout_add(30000, self.check_for_possible_inactive_chatstate,
				jid)
					self.reset_kbd_mouse_timeout_vars()
			
			gajim.connections[self.account].send_message(jid, message, keyID,
				chatstate = chatstate_to_send)

			message_buffer.set_text('') # clear message buffer (and tv of course)
			self.print_conversation(message, jid, jid, encrypted = encrypted)

	def on_contact_information_menuitem_clicked(self, widget):
		jid = self.get_active_jid()
		contact = self.contacts[jid]
		gajim.interface.roster.on_info(widget, contact, self.account)

	def read_queue(self, jid):
		'''read queue and print messages containted in it'''
		l = gajim.awaiting_events[self.account][jid]
		contact = self.contacts[jid]
		# Is it a pm ?
		is_pm = False
		room_jid, nick = gajim.get_room_and_nick_from_fjid(jid)
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
			self.print_conversation(data[0], jid, kind, tim = data[3],
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
		# reset to status image in gc if it is a pm
		gcs = gajim.interface.instances[self.account]['gc']
		if gcs.has_key(room_jid):
			gcs[room_jid].draw_all_roster()
			typ = 'pm'

		gajim.interface.roster.draw_contact(jid, self.account)
		if gajim.interface.systray_enabled:
			gajim.interface.systray.remove_jid(jid, self.account, typ)
		if (contact.show == 'offline' or contact.show == 'error'):
			showOffline = gajim.config.get('showoffline')
			if not showOffline and typ == 'chat' and \
				len(gajim.contacts.get_contact(self.account, jid)) == 1:
				gajim.interface.roster.really_remove_contact(contact, self.account)
			elif typ == 'pm':
				gcs[room_jid].remove_contact(room_jid, nick)

	def print_conversation(self, text, jid, frm = '', tim = None,
		encrypted = False, subject = None):
		'''Print a line in the conversation:
		if contact is set to status: it's a status message
		if contact is set to another value: it's an outgoing message
		if contact is set to print_queue: it is incomming from queue
		if contact is not set: it's an incomming message'''
		contact = self.contacts[jid]
		if frm == 'status':
			kind = 'status'
			name = ''
		else:
			ec = gajim.encrypted_chats[self.account]
			if encrypted and jid not in ec:
				msg = _('Encryption enabled')
				chat.Chat.print_conversation_line(self, msg, jid,
					'status', '', tim)
				ec.append(jid)
			if not encrypted and jid in ec:
				msg = _('Encryption disabled')
				chat.Chat.print_conversation_line(self, msg, jid,
					'status', '', tim)
				ec.remove(jid)
			self.xmls[jid].get_widget('gpg_togglebutton').set_active(encrypted)
			if not frm:
				kind = 'incoming'
				name = contact.name
			elif frm == 'print_queue': # incoming message, but do not update time
				kind = 'incoming_queue'
				name = contact.name
			else:
				kind = 'outgoing'
				name = gajim.nicks[self.account] 
		chat.Chat.print_conversation_line(self, text, jid, kind, name, tim,
			subject = subject)

	def restore_conversation(self, jid):
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
			if row[1] in (constants.KIND_CHAT_MSG_SENT, constants.KIND_SINGLE_MSG_SENT):
				kind = 'outgoing'
				name = gajim.nicks[self.account]
			elif row[1] in (constants.KIND_SINGLE_MSG_RECV, constants.KIND_CHAT_MSG_RECV):
				kind = 'incoming'
				name = self.contacts[jid].name

			tim = time.localtime(float(row[0]))

			chat.Chat.print_conversation_line(self, row[2], jid, kind, name, tim,
				['small'], ['small', 'restored_message'], ['small', 'restored_message'], False)

		if len(rows):
			conv_textview = self.conversation_textviews[jid]
			conv_textview.print_empty_line()
