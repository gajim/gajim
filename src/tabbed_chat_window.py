##	plugins/tabbed_chat_window.py
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
		self.users = {}
		self.encrypted = {}
		self.new_user(user)
		self.show_title()
		self.xml.signal_connect('on_tabbed_chat_window_destroy',
			self.on_tabbed_chat_window_destroy)
		self.xml.signal_connect('on_tabbed_chat_window_delete_event',
			self.on_tabbed_chat_window_delete_event)
		self.xml.signal_connect('on_tabbed_chat_window_focus_in_event',
			self.on_tabbed_chat_window_focus_in_event)
		self.xml.signal_connect('on_tabbed_chat_window_button_press_event',
			self.on_chat_window_button_press_event)
		self.xml.signal_connect('on_chat_notebook_key_press_event',
			self.on_chat_notebook_key_press_event)
		self.xml.signal_connect('on_chat_notebook_switch_page',
			self.on_chat_notebook_switch_page)

		if gajim.config.get('saveposition'):
		# get window position and size from config
			self.window.move(gajim.config.get('chat-x-position'),
					gajim.config.get('chat-y-position'))
			self.window.resize(gajim.config.get('chat-width'),
					gajim.config.get('chat-height'))

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
		
	def draw_widgets(self, user):
		"""draw the widgets in a tab (status_image, contact_button ...)
		according to the the information in the user variable"""
		jid = user.jid
		self.set_state_image(jid)
		contact_button = self.xmls[jid].get_widget('contact_button')
		contact_button.set_use_underline(False)
		if not user.keyID:
			self.xmls[jid].get_widget('gpg_togglebutton').set_sensitive(False)
		else:
			self.xmls[jid].get_widget('gpg_togglebutton').set_sensitive(True)

		# add the fat line at the top
		self.draw_name_banner(user.name, jid)

	def draw_name_banner(self, name, jid):
		'''Draw the fat line at the top of the window that 
		houses the status icon, name, jid, and avatar'''
		# this is the text for the big brown bar
		# some chars need to be escaped.. this fixes '&'
		name = name.replace('&', '&amp;')

		# composing full jid
		fulljid = jid
		if self.users[jid].resource:
			fulljid += '/' + self.users[jid].resource
		label_text = '<span weight="heavy" size="x-large">%s</span>\n%s' \
			% (name, fulljid)

		# setup the label that holds name and jid
		banner_name_label = self.xmls[jid].get_widget('banner_name_label')
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
		elif vcard[i].has_key('EXTVAL'):
			url = vcard[i]['EXTVAL']
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
			image = self.xmls[vcard['jid']].get_widget('avatar_image')
			image.set_from_pixbuf(scaled_buf)
			image.show_all()

	def set_state_image(self, jid):
		prio = 0
		if self.plugin.roster.contacts[self.account].has_key(jid):
			list_users = self.plugin.roster.contacts[self.account][jid]
		else:
			list_users = [self.users[jid]]
		user = list_users[0]
		show = user.show
		jid = user.jid
		keyID = user.keyID
		for u in list_users:
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
		for jid in self.users:
			if time.time() - self.last_message_time[jid] < 2: # 2 seconds
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

	def on_tabbed_chat_window_event(self, widget, event):
		if event.type != gtk.gdk.BUTTON_PRESS:
			return False
		self.on_chat_window_button_press_event(widget, event)
		return True

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

		message_buffer.set_text('', -1)

	def remove_tab(self, jid):
		if time.time() - self.last_message_time[jid] < 2:
			dialog = dialogs.ConfirmationDialog(
				_('You just received a new message from "%s"' % jid),
				_('If you close this tab, the message will be lost.'))
			if dialog.get_response() != gtk.RESPONSE_OK:
				return

		chat.Chat.remove_tab(self, jid, 'chats')
		if len(self.xmls) > 0:
			del self.users[jid]

	def new_user(self, user):
		'''when new tab is created'''
		self.names[user.jid] = user.name
		self.xmls[user.jid] = gtk.glade.XML(GTKGUI_GLADE, 'chats_vbox', APP)
		self.childs[user.jid] = self.xmls[user.jid].get_widget('chats_vbox')
		self.set_compact_view(self.get_compact_view())
		self.users[user.jid] = user
		self.encrypted[user.jid] = False
		
		chat.Chat.new_tab(self, user.jid)
		self.redraw_tab(user.jid)
		self.draw_widgets(user)
		
		uf_show = helpers.get_uf_show(user.show)
		s = _('%s is %s') % (user.name, uf_show)
		if user.status:
			s += ' (' + user.status + ')'
		self.print_conversation(s, user.jid, 'status')

		#restore previous conversation
		self.restore_conversation(user.jid)

		#print queued messages
		if self.plugin.queues[self.account].has_key(user.jid):
			self.read_queue(user.jid)

		gajim.connections[self.account].request_vcard(user.jid)

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
		elif event.keyval == gtk.keysyms.Return or \
			event.keyval == gtk.keysyms.KP_Enter: # ENTER
			if gajim.config.get('send_on_ctrl_enter'): 
				if not (event.state & gtk.gdk.CONTROL_MASK):
					return False
			elif (event.state & gtk.gdk.SHIFT_MASK):
					return False
			if gajim.connections[self.account].connected < 2: #we are not connected
				dialogs.ErrorDialog(_("A connection is not available"),
                        _("Your message can't be sent until you reconnect.")).get_response()
				return True

			# send the message
			self.send_message(message)

			message_buffer.set_text('', -1)
			return True
		elif event.keyval == gtk.keysyms.Up:
			if event.state & gtk.gdk.CONTROL_MASK: #Ctrl+UP
				self.sent_messages_scroll(jid, 'up', widget.get_buffer())
		elif event.keyval == gtk.keysyms.Down:
			if event.state & gtk.gdk.CONTROL_MASK: #Ctrl+Down
				self.sent_messages_scroll(jid, 'down', widget.get_buffer())

	def send_message(self, message):
		"""Send the message given in the args"""
		if not message:
			return
		jid = self.get_active_jid()
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
				self.set_compact_view(not self.get_compact_view())
				self.on_clear(None, message_textview)
				return True
			keyID = ''
			encrypted = False
			if self.xmls[jid].get_widget('gpg_togglebutton').get_active():
				keyID = self.users[jid].keyID
				encrypted = True
			gajim.connections[self.account].send_message(jid, message, keyID)
			message_buffer.set_text('', -1)
			self.print_conversation(message, jid, jid, encrypted = encrypted)

	def on_contact_button_clicked(self, widget):
		jid = self.get_active_jid()
		user = self.users[jid]
		self.plugin.roster.on_info(widget, user, self.account)

	def read_queue(self, jid):
		"""read queue and print messages containted in it"""
		l = self.plugin.queues[self.account][jid]
		user = self.users[jid]
		for event in l:
			self.print_conversation(event[0], jid, tim = event[1],
				encrypted = event[2])
			self.plugin.roster.nb_unread -= 1
		self.plugin.roster.show_title()
		del self.plugin.queues[self.account][jid]
		self.plugin.roster.draw_contact(jid, self.account)
		if self.plugin.systray_enabled:
			self.plugin.systray.remove_jid(jid, self.account)
		showOffline = gajim.config.get('showoffline')
		if (user.show == 'offline' or user.show == 'error') and \
			not showOffline:
			if len(self.plugin.roster.contacts[self.account][jid]) == 1:
				self.plugin.roster.really_remove_user(user, self.account)

	def print_conversation(self, text, jid, contact = '', tim = None,
		encrypted = False):
		"""Print a line in the conversation:
		if contact is set to status: it's a status message
		if contact is set to another value: it's an outgoing message
		if contact is not set: it's an incomming message"""
		user = self.users[jid]
		if contact == 'status':
			kind = 'status'
			name = ''
		else:
			if encrypted and not self.encrypted[jid]:
				chat.Chat.print_conversation_line(self, 'Encryption enabled', jid,
					'status', '', tim)
			if not encrypted and self.encrypted[jid]:
				chat.Chat.print_conversation_line(self, 'Encryption disabled', jid,
					'status', '', tim)
			self.encrypted[jid] = encrypted
			self.xmls[jid].get_widget('gpg_togglebutton').set_active(encrypted)
			if contact:
				kind = 'outgoing'
				name = self.plugin.nicks[self.account] 
			else:
				kind = 'incoming'
				name = user.name

		chat.Chat.print_conversation_line(self, text, jid, kind, name, tim)

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
		count		= gajim.logger.get_nb_line(jid)


		if self.plugin.queues[self.account].has_key(jid):
			pos = len(self.plugin.queues[self.account][jid])
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
				name = self.plugin.nicks[self.account]
			elif msg[1] == 'recv':
				kind = 'incoming'
				name = self.users[jid].name

			tim = time.gmtime(float(msg[0]))

			text = ':'.join(msg[2:])[0:-1] #remove the latest \n
			self.print_conversation_line(text, jid, kind, name, tim,
				['small'], ['small', 'grey'], ['small', 'grey'])

		if len(lines):
			self.print_empty_line(jid)

	def populate_popup_menu(self, menu):
		"""Add menuitems do popup menu"""

		# FIXME: add icons / use ItemFactory
		item = gtk.MenuItem(_('_History'))
		item.connect('activate', self.on_history_button_clicked)
		menu.append(item)

		item = gtk.MenuItem(_('_Information'))
		item.connect('activate', self.on_contact_button_clicked)
		menu.append(item)
		
		# FIXME: GPG stuff
