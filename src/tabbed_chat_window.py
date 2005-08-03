##	tabbed_chat_window.py
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
import urllib
import base64

import dialogs
import chat
import gtkgui_helpers

from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class TabbedChatWindow(chat.Chat):
	"""Class for tabbed chat window"""
	def __init__(self, user, plugin, account):
		chat.Chat.__init__(self, plugin, account, 'tabbed_chat_window')
		self.contacts = {}
		self.chatstates = {}
		# keep check for possible paused timeouts per jid
		self.possible_paused_timeout_id = {}
		# keep check for possible inactive timeouts per jid
		self.possible_inactive_timeout_id = {}
		self.new_user(user)
		self.show_title()
		self.xml.signal_connect('on_tabbed_chat_window_destroy',
			self.on_tabbed_chat_window_destroy)
		self.xml.signal_connect('on_tabbed_chat_window_delete_event',
			self.on_tabbed_chat_window_delete_event)
		self.xml.signal_connect('on_tabbed_chat_window_focus_in_event',
			self.on_tabbed_chat_window_focus_in_event)
		self.xml.signal_connect('on_tabbed_chat_window_focus_out_event',
			self.on_tabbed_chat_window_focus_out_event)
		self.xml.signal_connect('on_tabbed_chat_window_button_press_event',
			self.on_chat_window_button_press_event)
		self.xml.signal_connect('on_chat_notebook_key_press_event',
			self.on_chat_notebook_key_press_event)
		self.xml.signal_connect('on_chat_notebook_switch_page',
			self.on_chat_notebook_switch_page)
		self.xml.signal_connect('on_tabbed_chat_window_motion_notify_event',
			self.on_tabbed_chat_window_motion_notify_event)

		if gajim.config.get('saveposition'):
			# get window position and size from config
			self.window.move(gajim.config.get('chat-x-position'),
					gajim.config.get('chat-y-position'))
			self.window.resize(gajim.config.get('chat-width'),
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

	def draw_widgets(self, contact):
		"""draw the widgets in a tab (status_image, contact_button ...)
		according to the the information in the contact variable"""
		jid = contact.jid
		self.set_state_image(jid)
		contact_button = self.xmls[jid].get_widget('contact_button')
		contact_button.set_use_underline(False)
		tb = self.xmls[jid].get_widget('gpg_togglebutton')
		if contact.keyID: # we can do gpg
			tb.set_sensitive(True)
			tt = _('OpenPGP Encryption')
		else:
			tb.set_sensitive(False)
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
		#FIXME: when gtk2.4 is OOOOLD do it via glade2.10+  
		if gtk.pygtk_version >= (2, 6, 0) and gtk.gtk_version >= (2, 6, 0):
			banner_name_label.set_ellipsize(pango.ELLIPSIZE_END)
		#FIXME: do me with pango ellipseEND when gtk24 is OLD
		elif status is not None and len(status) > 50:
				status = status[:47] + '...'
		status = gtkgui_helpers.escape_for_pango_markup(status)

		#FIXME: uncomment me when we support sending messages to specific resource
		# composing full jid
		#fulljid = jid
		#if self.contacts[jid].resource:
		#	fulljid += '/' + self.contacts[jid].resource
		#label_text = '<span weight="heavy" size="x-large">%s</span>\n%s' \
		#	% (name, fulljid)
		
		if chatstate:
			chatstate = helpers.get_uf_chatstate(chatstate)
			label_text = \
			'<span weight="heavy" size="x-large">%s</span> %s' % (name, chatstate)
		else:
			label_text = '<span weight="heavy" size="x-large">%s</span>' % name
		
		if status is not None:
			label_text += '\n%s' % status

		# setup the label that holds name and jid
		banner_name_label.set_markup(label_text)
		self.paint_banner(jid)

	def set_avatar(self, vcard):
		if not vcard.has_key('PHOTO'):
			return
		if type(vcard['PHOTO']) != type({}):
			return
		img_decoded = None
		if vcard['PHOTO'].has_key('BINVAL'):
			try:
				img_decoded = base64.decodestring(vcard['PHOTO']['BINVAL'])
			except:
				pass
		elif vcard['PHOTO'].has_key('EXTVAL'):
			url = vcard['PHOTO']['EXTVAL']
			try:
				fd = urllib.urlopen(url)
				img_decoded = fd.read()
			except:
				pass
		if img_decoded:
			pixbufloader = gtk.gdk.PixbufLoader()
			pixbufloader.write(img_decoded)
			pixbuf = pixbufloader.get_pixbuf()
			pixbufloader.close()
			scaled_buf = pixbuf.scale_simple(52, 52, gtk.gdk.INTERP_HYPER)
			x = None
			if self.xmls.has_key(vcard['jid']):
				x = self.xmls[vcard['jid']]
			# it can be xmls[jid/resource] if it's a vcard from pm
			elif self.xmls.has_key(vcard['jid'] + '/' + vcard['resource']):
				x = self.xmls[vcard['jid'] + '/' + vcard['resource']]
			image = x.get_widget('avatar_image')
			image.set_from_pixbuf(scaled_buf)
			image.show_all()

	def set_state_image(self, jid):
		prio = 0
		if gajim.contacts[self.account].has_key(jid):
			contacts_list = gajim.contacts[self.account][jid]
		else:
			contacts_list = [self.contacts[jid]]
		user = contacts_list[0]
		show = user.show
		jid = user.jid
		keyID = user.keyID
		for u in contacts_list:
			if u.priority > prio:
				prio = u.priority
				show = u.show
				keyID = u.keyID
		child = self.childs[jid]
		status_image = self.notebook.get_tab_label(child).get_children()[0]
		state_images = self.plugin.roster.get_appropriate_state_images(jid)
		image = state_images[show]
		banner_status_image = self.xmls[jid].get_widget('banner_status_image')
		if keyID:
			self.xmls[jid].get_widget('gpg_togglebutton').set_sensitive(True)
		else:
			self.xmls[jid].get_widget('gpg_togglebutton').set_sensitive(False)
		if image.get_storage_type() == gtk.IMAGE_ANIMATION:
			banner_status_image.set_from_animation(image.get_animation())
			status_image.set_from_animation(image.get_animation())
		elif image.get_storage_type() == gtk.IMAGE_PIXBUF:
			# make a copy because one will be scaled, one not (tab icon)
			pix = image.get_pixbuf()
			scaled_pix = pix.scale_simple(32, 32, gtk.gdk.INTERP_BILINEAR)
			banner_status_image.set_from_pixbuf(scaled_pix)
			status_image.set_from_pixbuf(pix)

	def on_tabbed_chat_window_delete_event(self, widget, event):
		"""close window"""
		for jid in self.contacts:
			if time.time() - gajim.last_message_time[self.account][jid] < 2:
				# 2 seconds
				dialog = dialogs.ConfirmationDialog(
					_('You just received a new message from "%s"' % jid),
					_('If you close the window, this message will be lost.'))
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
		#clean self.plugin.windows[self.account]['chats']
		chat.Chat.on_window_destroy(self, widget, 'chats')

	def on_tabbed_chat_window_focus_in_event(self, widget, event):
		chat.Chat.on_chat_window_focus_in_event(self, widget, event)
		# on focus in, send 'active' chatstate
		self.send_chatstate('active')

	def on_tabbed_chat_window_focus_out_event(self, widget, event):
		'''catch focus out and minimized and send inactive chatstate;
		minimize action also focuses out first so it's catched here'''
		window_state = widget.window.get_state()
		if window_state is None:
			return
		
		# focus-out is also emitted by showing context menu
		# so check to see if we're really not paying attention to window/tab
		x, y, width, height, depth = widget.window.get_geometry()
		mouse_x, mouse_y, state = widget.window.get_pointer()
		# mouse_x, mouse_y are relative to window that is:
		# (0, 0) is the left upper corner of the window
		#  so just check if mouse_x is inside width value to see where the pointer
		# is at the time of focus-out
		# NOTE: if the user changes tab, (switch-tab send inactive to current tab
		# so that's not a problem)
		if mouse_x < 0 or mouse_x > width: # it's outside of window
			# so no context menu, so sent inactive
			self.send_chatstate('inactive')

	def on_chat_notebook_key_press_event(self, widget, event):
		chat.Chat.on_chat_notebook_key_press_event(self, widget, event)

	def on_send_button_clicked(self, widget):
		"""When send button is pressed: send the current message"""
		jid = self.get_active_jid()
		message_textview = self.xmls[jid].get_widget('message_textview')
		message_buffer = message_textview.get_buffer()
		start_iter = message_buffer.get_start_iter()
		end_iter = message_buffer.get_end_iter()
		message = message_buffer.get_text(start_iter, end_iter, 0)

		# send the message
		self.send_message(message)

		message_buffer.set_text('')

	def remove_tab(self, jid):
		if time.time() - gajim.last_message_time[self.account][jid] < 2:
			dialog = dialogs.ConfirmationDialog(
				_('You just received a new message from "%s"' % jid),
				_('If you close this tab, the message will be lost.'))
			if dialog.get_response() != gtk.RESPONSE_OK:
				return

		# chatstates - window is destroyed, send gone
		self.send_chatstate('gone', jid)
		
		chat.Chat.remove_tab(self, jid, 'chats')
		del self.contacts[jid]

	def new_user(self, contact):
		'''when new tab is created'''
		self.names[contact.jid] = contact.name
		self.xmls[contact.jid] = gtk.glade.XML(GTKGUI_GLADE, 'chats_vbox', APP)
		self.childs[contact.jid] = self.xmls[contact.jid].get_widget('chats_vbox')
		self.contacts[contact.jid] = contact

		if contact.jid in gajim.encrypted_chats[self.account]:
			self.xmls[contact.jid].get_widget('gpg_togglebutton').set_active(True)
		
		xm = gtk.glade.XML(GTKGUI_GLADE, 'tabbed_chat_popup_menu', APP)
		xm.signal_autoconnect(self)
		self.tabbed_chat_popup_menu = xm.get_widget('tabbed_chat_popup_menu')
		
		chat.Chat.new_tab(self, contact.jid)
		self.redraw_tab(contact.jid)
		self.draw_widgets(contact)

		#restore previous conversation
		self.restore_conversation(contact.jid)

		#print queued messages
		if gajim.awaiting_messages[self.account].has_key(contact.jid):
			self.read_queue(contact.jid)

		gajim.connections[self.account].request_vcard(contact.jid)
		self.childs[contact.jid].show_all()

		# chatstates
		self.kbd_activity_in_last_5_secs = False
		self.mouse_over_in_last_5_secs = False
		self.mouse_over_in_last_30_secs = False
		self.kbd_activity_in_last_30_secs = False
		
		self.chatstates[contact.jid] = None # our current chatstate with contact
		self.possible_paused_timeout_id[contact.jid] =\
			gobject.timeout_add(5000, self.check_for_possible_paused_chatstate,
				contact)
		self.possible_inactive_timeout_id[contact.jid] =\
			gobject.timeout_add(30000, self.check_for_possible_inactive_chatstate,
				contact)
		
	def handle_incoming_chatstate(self, account, jid, chatstate):
		''' handle incoming chatstate that jid SENT TO us '''
		contact = gajim.get_first_contact_instance_from_jid(account, jid)
		self.draw_name_banner(contact, chatstate)

	def check_for_possible_paused_chatstate(self, contact):
		''' did we move mouse of that window or kbd activity in that window
		in the last 5 seconds?
		if yes we go active
		if no we go paused if we were previously composing '''
		current_state = self.chatstates[contact.jid]
		if current_state == False: # jid doesn't support chatstates
			return False # stop looping
		
		if self.mouse_over_in_last_5_secs:
			self.send_chatstate('active')
		elif self.kbd_activity_in_last_5_secs:
			self.send_chatstate('composing')
		else:
			if self.chatstates[contact.jid] == 'composing':
				self.send_chatstate('paused') # pause composing
		
		# assume no activity and let the motion-notify or key_press make them True
		self.mouse_over_in_last_5_secs = False
		self.kbd_activity_in_last_5_secs = False
		
		# refresh 30 seconds or else it's 30 - 5 = 25 seconds!
		self.mouse_over_in_last_30_secs = True
		self.kbd_activity_in_last_30_secs = True
		
		return True # loop forever

	def check_for_possible_inactive_chatstate(self, contact):
		''' did we move mouse over that window or kbd activity in that window
		in the last 30 seconds?
		if yes we go active if not already
		if no we go inactive if not already '''
		current_state = self.chatstates[contact.jid]
		if current_state == False: # jid doesn't support chatstates
			return False # stop looping
		
		if not (self.mouse_over_in_last_30_secs or\
		self.kbd_activity_in_last_30_secs):
			self.send_chatstate('inactive')

		# assume no activity and let the motion-notify or key_press make them True
		self.mouse_over_in_last_5_secs = False
		self.kbd_activity_in_last_5_secs = False
		
		self.mouse_over_in_last_30_secs = False
		self.kbd_activity_in_last_30_secs = False
		
		return True # loop forever

	def on_message_textview_key_press_event(self, widget, event):
		"""When a key is pressed:
		if enter is pressed without the shift key, message (if not empty) is sent
		and printed in the conversation"""

		jid = self.get_active_jid()
		conversation_textview = self.xmls[jid].get_widget('conversation_textview')
		message_buffer = widget.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()
		message = message_buffer.get_text(start_iter, end_iter, False)

		if event.keyval == gtk.keysyms.ISO_Left_Tab: # SHIFT + TAB
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + SHIFT + TAB
				self.notebook.emit('key_press_event', event)
		if event.keyval == gtk.keysyms.Tab:
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + TAB
				self.notebook.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Page_Down: # PAGE DOWN
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE DOWN
				self.notebook.emit('key_press_event', event)
			elif event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE DOWN
				conversation_textview.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Page_Up: # PAGE UP
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + PAGE UP
				self.notebook.emit('key_press_event', event)
			elif event.state & gtk.gdk.SHIFT_MASK: # SHIFT + PAGE UP
				conversation_textview.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Up:
			if event.state & gtk.gdk.CONTROL_MASK: #Ctrl+UP
				self.sent_messages_scroll(jid, 'up', widget.get_buffer())
				return True # override the default gtk+ thing for ctrl+up
		elif event.keyval == gtk.keysyms.Down:
			if event.state & gtk.gdk.CONTROL_MASK: #Ctrl+Down
				self.sent_messages_scroll(jid, 'down', widget.get_buffer())
				return True # override the default gtk+ thing for ctrl+down
		elif event.keyval == gtk.keysyms.Return or \
			event.keyval == gtk.keysyms.KP_Enter: # ENTER
			if gajim.config.get('send_on_ctrl_enter'): 
				if not (event.state & gtk.gdk.CONTROL_MASK):
					return False
			elif (event.state & gtk.gdk.SHIFT_MASK):
					return False
			if gajim.connections[self.account].connected < 2: #we are not connected
				dialogs.ErrorDialog(_("A connection is not available"),
					_("Your message can't be sent until you are connected.")).get_response()
				return True

			# send the message
			self.send_message(message)

			message_buffer.set_text('')
			return True
			
		else:
			# chatstates
			# if really composing (eg. no Ctrl, or alt modifier, send chatstate
			if not (event.state & gtk.gdk.CONTROL_MASK) and not\
				(event.state & gtk.gdk.MOD1_MASK):
				self.kbd_activity_in_last_5_secs = True
				self.kbd_activity_in_last_30_secs = True
				self.send_chatstate('composing')

	def send_chatstate(self, state, jid = None):
		''' sends our chatstate as STANDLONE chat state message (eg. no body)
		to the current tab only if new chatstate is different
		from the previous one'''
		# JEP 85 does not allow resending the same chatstate
		# this function checks for that and just returns so it's safe to call it
		# with same state.
		
		# This functions also checks for violation in state transitions
		# and raises RuntimeException with appropriate message
		# more on that http://www.jabber.org/jeps/jep-0085.html#statechart

		# do not send nothing if we have chat state notifications disabled
		# that means we won't reply to the <active/> from other peer
		# so we do not broadcast jep85 capabalities
		if not gajim.config.get('send_receive_chat_state_notifications'):
			return

		if jid is None:
			jid = self.get_active_jid()
		
		# this happens sometime when we close  fastly all tabs
		if jid is '':
			return 
			
		contact = gajim.get_first_contact_instance_from_jid(self.account, jid)

		if contact is None:
			# contact was from pm in MUC, and left the room so contact is None
			# so we cannot send chatstate anymore
			return

		if contact.chatstate is False: # jid cannot do jep85
			return

		# if current state equals previous state, return
		if contact.chatstate == state:
			return

		if contact.chatstate is None:
			# we don't know anything about jid, so return
			# NOTE:
			# send 'active', set current state to 'ask' and return is done
			# in send_message because we need REAL message (with <body>)
			# for that procedure so return to make sure we send only once 'active'
			# until we know peer supports jep85
			return 

		if contact.chatstate == 'ask':
			return

		# prevent going paused if we we were not composing (JEP violation)
		if state == 'paused' and not contact.chatstate == 'composing':
			gajim.connections[self.account].send_message(jid, None, None,
				chatstate = 'active') # go active before
		
		# if we're inactive prevent composing (JEP violation)
		if contact.chatstate == 'inactive' and state == 'composing':
			gajim.connections[self.account].send_message(jid, None, None,
				chatstate = 'active') # go active before

		contact.chatstate = state
		gajim.connections[self.account].send_message(jid, None, None,
			chatstate = state)
		
	def send_message(self, message):
		"""Send the given message to the active tab"""
		if not message:
			return
		
		jid = self.get_active_jid()
		contact = gajim.get_first_contact_instance_from_jid(self.account, jid)
		conversation_textview = self.xmls[jid].get_widget('conversation_textview')
		message_textview = self.xmls[jid].get_widget('message_textview')
		message_buffer = message_textview.get_buffer()

		if message != '' or message != '\n':
			self.save_sent_message(jid, message)
			if message == '/clear':
				self.on_clear(None, conversation_textview) # clear conversation
				self.on_clear(None, message_textview) # clear message textview too
				return True
			elif message == '/compact':
				self.set_compact_view(not self.compact_view_current_state)
				self.on_clear(None, message_textview)
				return True
			keyID = ''
			encrypted = False
			if self.xmls[jid].get_widget('gpg_togglebutton').get_active():
				keyID = self.contacts[jid].keyID
				encrypted = True

			chatstates_on = gajim.config.get(
				'send_receive_chat_state_notifications')

			chatstate_to_send = None
			
			if chatstates_on and contact is not None:
				if contact.chatstate is None:
					# no info about peer
					# send active to discover chat state capabilities
					# this is here (and not in send_chatstate)
					# because we want it sent with REAL message
					# (not standlone) eg. one that has body
					chatstate_to_send = 'active'
					contact.chatstate = 'ask' # pseudo state

				# if peer supports jep85, send 'active'
				elif contact.chatstate is not False:
					#send active chatstate on every message (as JEP says)
					chatstate_to_send = 'active'
			
			gajim.connections[self.account].send_message(jid, message, keyID,
				chatstate = chatstate_to_send)

			message_buffer.set_text('')
			self.print_conversation(message, jid, jid, encrypted = encrypted)

	def on_contact_button_clicked(self, widget):
		jid = self.get_active_jid()
		contact = self.contacts[jid]
		self.plugin.roster.on_info(widget, contact, self.account)

	def read_queue(self, jid):
		"""read queue and print messages containted in it"""
		l = gajim.awaiting_messages[self.account][jid]
		user = self.contacts[jid]
		for event in l:
			self.print_conversation(event[0], jid, tim = event[1],
				encrypted = event[2], contact='print_queue')
			self.plugin.roster.nb_unread -= 1
		self.plugin.roster.show_title()
		del gajim.awaiting_messages[self.account][jid]
		self.plugin.roster.draw_contact(jid, self.account)
		if self.plugin.systray_enabled:
			self.plugin.systray.remove_jid(jid, self.account)
		showOffline = gajim.config.get('showoffline')
		if (user.show == 'offline' or user.show == 'error') and \
			not showOffline:
			if len(gajim.contacts[self.account][jid]) == 1:
				self.plugin.roster.really_remove_contact(user, self.account)

	def print_conversation(self, text, jid, contact = '', tim = None,
		encrypted = False, subject = None):
		"""Print a line in the conversation:
		if contact is set to status: it's a status message
		if contact is set to another value: it's an outgoing message
		if contact is set to print_queue: it is incomming from queue
		if contact is not set: it's an incomming message"""
		user = self.contacts[jid]
		if contact == 'status':
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
			if not contact:
				kind = 'incoming'
				name = user.name
			elif contact == 'print_queue': # incoming message, but do not update time
				kind = 'incoming_queue'
				name = user.name
			else:
				kind = 'outgoing'
				name = gajim.nicks[self.account] 
		chat.Chat.print_conversation_line(self, text, jid, kind, name, tim,
			subject = subject)

	def restore_conversation(self, jid):
		# don't restore lines if it's a transport
		is_transport = jid.startswith('aim') or jid.startswith('gadugadu') or\
			jid.startswith('irc') or jid.startswith('icq') or\
			jid.startswith('msn') or jid.startswith('sms') or\
			jid.startswith('yahoo')

		if is_transport:
			return	

		#How many lines to restore and when to time them out
		restore	= gajim.config.get('restore_lines')
		time_out = gajim.config.get('restore_timeout')
		pos		= 0	#position, while reading from history
		size		= 0	#how many lines we alreay retreived
		lines		= []	#we'll need to reverse the lines from history
		count		= gajim.logger.get_no_of_lines(jid)


		if gajim.awaiting_messages[self.account].has_key(jid):
			pos = len(gajim.awaiting_messages[self.account][jid])
		else:
			pos = 0

		now = time.time()
		while size <= restore:
			if pos == count or size > restore - 1:
				#don't try to read beyond history, not read more than required
				break
			
			nb, line = gajim.logger.read(jid, count - 1 - pos, count - pos)
			pos = pos + 1

			if (now - float(line[0][0]))/60 >= time_out:
				#stop looking for messages if we found something too old
				break

			if line[0][1] != 'sent' and line[0][1] != 'recv':
				# we don't want to display status lines, do we?
				continue

			lines.append(line[0])
			size = size + 1

		lines.reverse()
		
		for msg in lines:
			if msg[1] == 'sent':
				kind = 'outgoing'
				name = gajim.nicks[self.account]
			elif msg[1] == 'recv':
				kind = 'incoming'
				name = self.contacts[jid].name

			tim = time.localtime(float(msg[0]))

			text = ':'.join(msg[2:])[:-1] #remove the latest \n
			self.print_conversation_line(text, jid, kind, name, tim,
				['small'], ['small', 'grey'], ['small', 'grey'], False)

		if len(lines):
			self.print_empty_line(jid)
