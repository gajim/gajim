## groupchat_window.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
##
## Copyright (C) 2003-2005 Gajim Team
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
import dialogs
import chat
import cell_renderer_image
import gtkgui_helpers

from gajim import Contact
from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class GroupchatWindow(chat.Chat):
	"""Class for Groupchat window"""
	def __init__(self, room_jid, nick, plugin, account):
		chat.Chat.__init__(self, plugin, account, 'groupchat_window')
		
		# alphanum sorted
		self.muc_cmds = ['ban', 'chat', 'clear', 'compact', 'kick', 
			'me', 'msg', 'nick',	'topic']
		
		self.nicks = {} # our nick for each groupchat we are in
		gajim.gc_contacts[account] = {} # contact instances for each room
		self.list_treeview = {}
		self.subjects = {}
		self.name_labels = {}
		self.subject_tooltip = {}
		self.room_creation = {}
		self.nick_hits = {} # possible candidates for nick completion
		self.cmd_hits = {} # possible candidates for command completion
		self.last_key_tabs = {}
		self.hpaneds = {} # used for auto positioning
		self.hpaned_position = gajim.config.get('gc-hpaned-position')
		self.gc_refer_to_nick_char = gajim.config.get('gc_refer_to_nick_char')
		self.new_room(room_jid, nick)
		self.show_title()
		self.xml.signal_connect('on_groupchat_window_destroy', 
			self.on_groupchat_window_destroy)
		self.xml.signal_connect('on_groupchat_window_delete_event', 
			self.on_groupchat_window_delete_event)
		self.xml.signal_connect('on_groupchat_window_focus_in_event', 
			self.on_groupchat_window_focus_in_event)
		self.xml.signal_connect('on_groupchat_window_button_press_event',
			self.on_chat_window_button_press_event)
		self.xml.signal_connect('on_chat_notebook_key_press_event', 
			self.on_chat_notebook_key_press_event)
		self.xml.signal_connect('on_chat_notebook_switch_page', 
			self.on_chat_notebook_switch_page)
		self.xml.signal_connect('on_close_window_activate',
			self.on_close_window_activate)

		# get size and position from config
		if gajim.config.get('saveposition'):
			self.window.move(gajim.config.get('gc-x-position'),
					gajim.config.get('gc-y-position'))
			self.window.resize(gajim.config.get('gc-width'),
					gajim.config.get('gc-height'))
		self.confirm_close = gajim.config.get('confirm_close_muc')
		self.confirm_close = True
		self.window.show_all()

	def save_var(self, room_jid):
		if not room_jid in self.nicks:
			return {}
		return {
			'nick': self.nicks[room_jid],
			'model': self.list_treeview[room_jid].get_model(),
			'subject': self.subjects[room_jid],
		}
		
	def load_var(self, room_jid, var):
		if not self.xmls.has_key(room_jid):
			return
		self.list_treeview[room_jid].set_model(var['model'])
		self.list_treeview[room_jid].expand_all()
		self.set_subject(room_jid, var['subject'])
		self.subjects[room_jid] = var['subject']

	def on_close_window_activate(self, widget):
		if not self.on_groupchat_window_delete_event(widget, None):
			self.window.destroy()

	def on_groupchat_window_delete_event(self, widget, event):
		"""close window"""
		stop_propagation = False
		for room_jid in self.xmls:
			if time.time() - gajim.last_message_time[self.account][room_jid] < 2:
				dialog = dialogs.ConfirmationDialog(
		_('You just received a new message in room "%s"') %room_jid.split('@')[0],
			_('If you close this window, this message will be lost.')
					)
				if dialog.get_response() != gtk.RESPONSE_OK:
					stop_propagation = True #stop the propagation of the event
		if not stop_propagation and self.confirm_close:
			dialog = dialogs.ConfirmationDialogCheck(
			_('Do you want to leave room "%s"') %room_jid.split('@')[0],
			_('If you close this window, you will be disconnected from the room.'),
			_('Do not ask me again')
				)
			if dialog.get_response() != gtk.RESPONSE_OK:
				stop_propagation = True 
			if dialog.is_checked():
				gajim.config.set('confirm_close_muc', False)
			dialog.destroy()
		if stop_propagation:
			return True
		for room_jid in self.xmls:
			gajim.connections[self.account].send_gc_status(self.nicks[room_jid],
				room_jid, 'offline', 'offline')

		if gajim.config.get('saveposition'):
		# save window position and size
			gajim.config.set('gc-hpaned-position', self.hpaned_position)
			x, y = self.window.get_position()
			gajim.config.set('gc-x-position', x)
			gajim.config.set('gc-y-position', y)
			width, height = self.window.get_size()
			gajim.config.set('gc-width', width)
			gajim.config.set('gc-height', height)
	
	def on_groupchat_window_destroy(self, widget):
		chat.Chat.on_window_destroy(self, widget, 'gc')

	def on_groupchat_window_focus_in_event(self, widget, event):
		"""When window get focus"""
		chat.Chat.on_chat_window_focus_in_event(self, widget, event)

	def on_groupchat_window_key_press_event(self, widget, event):
		self.on_chat_window_button_press_event(widget, event)
		return True

	def on_chat_notebook_key_press_event(self, widget, event):
		chat.Chat.on_chat_notebook_key_press_event(self, widget, event)
	
	def on_chat_notebook_switch_page(self, notebook, page, page_num):
		new_child = notebook.get_nth_page(page_num)
		new_jid = ''
		for room_jid in self.xmls:
			if self.childs[room_jid] == new_child: 
				new_jid = room_jid
				break
		subject = self.subjects[new_jid]

		# escape chars when necessary
		subject = subject.replace('&', '&amp;')
		new_jid = new_jid.replace('&', '&amp;')

		name_label = self.name_labels[new_jid]
		name_label.set_markup('<span weight="heavy" size="x-large">%s</span>\n%s' % (new_jid, subject))
		event_box = name_label.get_parent()
		if subject == '':
			subject = _('This room has no subject')
		self.subject_tooltip[new_jid].set_tip(event_box, subject)
		chat.Chat.on_chat_notebook_switch_page(self, notebook, page, page_num)

	def get_role_iter(self, room_jid, role):
		model = self.list_treeview[room_jid].get_model()
		fin = False
		iter = model.get_iter_root()
		if not iter:
			return None
		while not fin:
			role_name = model.get_value(iter, 1)
			if role == role_name:
				return iter
			iter = model.iter_next(iter)
			if not iter:
				fin = True
		return None

	def get_contact_iter(self, room_jid, nick):
		model = self.list_treeview[room_jid].get_model()
		fin = False
		role_iter = model.get_iter_root()
		if not role_iter:
			return None
		while not fin:
			fin2 = False
			user_iter = model.iter_children(role_iter)
			if not user_iter:
				fin2 = True
			while not fin2:
				if nick == model.get_value(user_iter, 1):
					return user_iter
				user_iter = model.iter_next(user_iter)
				if not user_iter:
					fin2 = True
			role_iter = model.iter_next(role_iter)
			if not role_iter:
				fin = True
		return None

	def get_nick_list(self, room_jid):
		'''get nicks of contacts in a room'''
		return gajim.gc_contacts[self.account][room_jid].keys()

	def remove_contact(self, room_jid, nick):
		"""Remove a user from the contacts_list"""
		model = self.list_treeview[room_jid].get_model()
		iter = self.get_contact_iter(room_jid, nick)
		if not iter:
			return
		if gajim.gc_contacts[self.account][room_jid].has_key(nick):
			del gajim.gc_contacts[self.account][room_jid][nick]
		parent_iter = model.iter_parent(iter)
		model.remove(iter)
		if model.iter_n_children(parent_iter) == 0:
			model.remove(parent_iter)

	def escape(self, s):
		return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
	
	def add_contact_to_roster(self, room_jid, nick, show, role, jid, affiliation):
		model = self.list_treeview[room_jid].get_model()
		image = self.plugin.roster.jabber_state_images[show]
		resource = ''
		if role == 'none':
			role_name = _('None')
		elif role == 'moderator':
			role_name = _('Moderators')
		elif role == 'participant':
			role_name = _('Participants')
		elif role == 'visitor':
			role_name = _('Visitors')

		if jid:
			jids = jid.split('/', 1)
			j = jids[0]
			if len(jids) > 1:
				resource = jids[1]
		else:
			j = ''
		role_iter = self.get_role_iter(room_jid, role)
		if not role_iter:
			role_iter = model.append(None,
				(self.plugin.roster.jabber_state_images['closed'], role,
				'<b>%s</b>' % role_name))
		iter = model.append(role_iter, (image, nick, self.escape(nick)))
		gajim.gc_contacts[self.account][room_jid][nick] = \
			Contact(jid = j, name = nick, show = show, resource = resource,
			role = role, affiliation = affiliation)
		self.list_treeview[room_jid].expand_row((model.get_path(role_iter)),
			False)
		return iter
	
	def get_role(self, room_jid, nick):
		if gajim.gc_contacts[self.account][room_jid].has_key(nick):
			return gajim.gc_contacts[self.account][room_jid][nick].role
		else:
			return 'visitor'

	def update_state_images(self):
		roster = self.plugin.roster
		for room_jid in self.list_treeview:
			model = self.list_treeview[room_jid].get_model()
			role_iter = model.get_iter_root()
			if not role_iter:
				continue
			while role_iter:
				user_iter = model.iter_children(role_iter)
				if not user_iter:
					continue
				while user_iter:
					nick = model.get_value(user_iter, 1)
					show = gajim.gc_contacts[self.account][room_jid][nick].show
					state_images = roster.get_appropriate_state_images(room_jid)
					image = state_images[show] #FIXME: always Jabber why?
					model.set_value(user_iter, 0, image)
					user_iter = model.iter_next(user_iter)
				role_iter = model.iter_next(role_iter)

	def chg_contact_status(self, room_jid, nick, show, status, role, affiliation,
		jid, reason, actor, statusCode, new_nick, account):
		"""When a user changes his status"""
		if show == 'invisible':
			return
		if not role:
			role = 'visitor'
		model = self.list_treeview[room_jid].get_model()
		if show in ('offline', 'error'):
			if statusCode == '307':
				self.print_conversation(_('%s has been kicked by %s: %s') % (nick,
					actor, reason), room_jid)
					#FIXME: this produced foo has been kciked by JID: reason
					#Should we show the JID to everyone? the same for ban
					#I propose we use nick
			elif statusCode == '301':
				self.print_conversation(_('%s has been banned by %s: %s') % (nick,
					actor, reason), room_jid)
			elif statusCode == '303': # Someone changed his nick
				self.print_conversation(_('%s is now known as %s') % (nick,
					new_nick), room_jid)
				if nick == self.nicks[room_jid]: # We changed our nick
					self.nicks[room_jid] = new_nick
			self.remove_contact(room_jid, nick)
			if nick == self.nicks[room_jid] and statusCode != '303': # We became offline
				model.clear()
				gajim.gc_contacts[self.account][room_jid] = {}
		else:
			iter = self.get_contact_iter(room_jid, nick)
			if not iter:
				iter = self.add_contact_to_roster(room_jid, nick, show, role, jid, affiliation)
			else:
				actual_role = self.get_role(room_jid, nick)
				if role != actual_role:
					self.remove_contact(room_jid, nick)
					self.add_contact_to_roster(room_jid, nick, show, role, jid,
						affiliation)
				else:
					c = gajim.gc_contacts[self.account][room_jid][nick]
					if c.show == show and c.status == status and \
						c.affiliation == affiliation: #no change
						return
					c.show = show
					c.affiliation = affiliation
					roster = self.plugin.roster
					state_images = roster.get_appropriate_state_images(jid)
					image = state_images[show]
					model.set_value(iter, 0, image)
		if (time.time() - self.room_creation[room_jid]) > 30 and \
				nick != self.nicks[room_jid] and statusCode != '303':
			if show == 'offline':
				st = _('%s has left') % nick
			else:
				st = _('%s is now %s') % (nick, helpers.get_uf_show(show))
			if status:
				st += ' (' + status + ')'
			self.print_conversation(st, room_jid)

	
	def set_subject(self, room_jid, subject):
		self.subjects[room_jid] = subject
		name_label = self.name_labels[room_jid]
		subject = gtkgui_helpers.escape_for_pango_markup(subject)
		name_label.set_markup('<span weight="heavy" size="x-large">%s</span>\n%s' % (room_jid, subject))
		event_box = name_label.get_parent()
		if subject == '':
			subject = _('This room has no subject')
		self.subject_tooltip[room_jid].set_tip(event_box, subject)

	def on_change_subject_menuitem_activate(self, widget):
		room_jid = self.get_active_jid()
		subject = self.subjects[room_jid]
		instance = dialogs.InputDialog(_('Changing Subject'),
			_('Please specify the new subject:'), subject)
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			subject = instance.input_entry.get_text()
			gajim.connections[self.account].send_gc_subject(room_jid, subject)

	def on_change_nick_menuitem_activate(self, widget):
		room_jid = self.get_active_jid()
		nick = self.nicks[room_jid]
		instance = dialogs.InputDialog(_('Changing Nickname'),
			_('Please specify the new nickname you want to use:'), nick)
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			nick = instance.input_entry.get_text()
			gajim.connections[self.account].change_gc_nick(room_jid, nick)

	def on_configure_room_menuitem_activate(self, widget):
		room_jid = self.get_active_jid()
		gajim.connections[self.account].request_gc_config(room_jid)

	def on_bookmark_room_menuitem_activate(self, widget):
		room_jid = self.get_active_jid()
		bm = {
				'name': room_jid,
			   'jid': room_jid,
			   'autojoin': '0',
			   'password': '',
			   'nick': self.nicks[room_jid]
			 }
		
		for bookmark in gajim.connections[self.account].bookmarks:
			if bookmark['jid'] == bm['jid']:
				dialogs.ErrorDialog(
					_('Bookmark already set'),
					_('Room "%s" is already in your bookmarks.') %bm['jid']).get_response()
				return

		gajim.connections[self.account].bookmarks.append(bm)
		gajim.connections[self.account].store_bookmarks()

		self.plugin.roster.make_menu()

		dialogs.InformationDialog(
				_('Bookmark has been added successfully'),
				_('You can manage your bookmarks via Actions menu in your roster.')).get_response()

	def on_message_textview_key_press_event(self, widget, event):
		"""When a key is pressed:
		if enter is pressed without the shift key, message (if not empty) is sent
		and printed in the conversation. Tab does autocomplete in nicknames"""
		room_jid = self.get_active_jid()
		conversation_textview = self.xmls[room_jid].get_widget(
			'conversation_textview')
		message_buffer = widget.get_buffer()
		start_iter, end_iter = message_buffer.get_bounds()
		message = message_buffer.get_text(start_iter, end_iter, False)

		if event.keyval == gtk.keysyms.ISO_Left_Tab: # SHIFT + TAB
			if (event.state & gtk.gdk.CONTROL_MASK): # CTRL + SHIFT + TAB  
				self.notebook.emit('key_press_event', event)
		elif event.keyval == gtk.keysyms.Tab: # TAB
			if event.state & gtk.gdk.CONTROL_MASK: # CTRL + TAB
				self.notebook.emit('key_press_event', event)
			else:
				cursor_position = message_buffer.get_insert()
				end_iter = message_buffer.get_iter_at_mark(cursor_position)
				text = message_buffer.get_text(start_iter, end_iter, False)
				if not text or text.endswith(' '):
					if not self.last_key_tabs[room_jid]: # if we are nick cycling, last char will always be space
						return False

				splitted_text = text.split()
				# command completion
				if text.startswith('/') and len(splitted_text) == 1:
					text = splitted_text[0]
					if len(text) == 1: # user wants to cycle all commands
						self.cmd_hits[room_jid] = self.muc_cmds
					else:
						# cycle possible commands depending on what the user typed
						if self.last_key_tabs[room_jid] and \
								self.cmd_hits[room_jid][0].startswith(text.lstrip('/')):
							self.cmd_hits[room_jid].append(self.cmd_hits[room_jid][0])
							self.cmd_hits[room_jid].pop(0)
						else: # find possible commands
							self.cmd_hits[room_jid] = []
							for cmd in self.muc_cmds:
								if cmd.startswith(text.lstrip('/')):
									self.cmd_hits[room_jid].append(cmd)
					if len(self.cmd_hits[room_jid]):
						message_buffer.delete(start_iter, end_iter)
						message_buffer.insert_at_cursor('/' + \
							self.cmd_hits[room_jid][0] + ' ')
						self.last_key_tabs[room_jid] = True
					return True

				# nick completion
				# check if tab is pressed with empty message
				if len(splitted_text): # if there are any words
					begin = splitted_text[-1] # last word we typed

				if len(self.nick_hits[room_jid]) and \
						self.nick_hits[room_jid][0].startswith(begin.replace(
						self.gc_refer_to_nick_char, '')) and \
						self.last_key_tabs[room_jid]: # we should cycle
					self.nick_hits[room_jid].append(self.nick_hits[room_jid][0])
					self.nick_hits[room_jid].pop(0)
				else:
					self.nick_hits[room_jid] = [] # clear the hit list
					list_nick = self.get_nick_list(room_jid)
					for nick in list_nick: 
						if nick.lower().startswith(begin.lower()): # the word is the begining of a nick
							self.nick_hits[room_jid].append(nick)
				if len(self.nick_hits[room_jid]):
					if len(splitted_text) == 1: # This is the 1st word of the line
						add = self.gc_refer_to_nick_char + ' '
					else:
						add = ' '
					start_iter = end_iter.copy()
					if self.last_key_tabs[room_jid] and begin.endswith(', '):
						start_iter.backward_chars(len(begin) + 2) # have to accomodate for the added space from last completion
					elif self.last_key_tabs[room_jid]:
						start_iter.backward_chars(len(begin) + 1) # have to accomodate for the added space from last completion
					else:
						start_iter.backward_chars(len(begin))

					message_buffer.delete(start_iter, end_iter)
					message_buffer.insert_at_cursor(self.nick_hits[room_jid][0] + add)
					self.last_key_tabs[room_jid] = True
					return True
				self.last_key_tabs[room_jid] = False
				return False
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
			if (event.state & gtk.gdk.SHIFT_MASK):
				self.last_key_tabs[room_jid] = False
				return False
			self.send_gc_message(message)
			message_buffer.set_text('')
			return True
		elif event.keyval == gtk.keysyms.Up:
			if event.state & gtk.gdk.CONTROL_MASK: #Ctrl+UP
				self.sent_messages_scroll(room_jid, 'up', widget.get_buffer())
				return True # override the default gtk+ thing for ctrl+up
		elif event.keyval == gtk.keysyms.Down:
			if event.state & gtk.gdk.CONTROL_MASK: #Ctrl+Down
				self.sent_messages_scroll(room_jid, 'down', widget.get_buffer())
				return True # override the default gtk+ thing for ctrl+down
		else:
			self.last_key_tabs[room_jid] = False

	def on_send_button_clicked(self, widget):
		"""When send button is pressed: send the current message"""
		room_jid = self.get_active_jid()
		message_textview = self.xmls[room_jid].get_widget(
			'message_textview')
		message_buffer = message_textview.get_buffer()
		start_iter = message_buffer.get_start_iter()
		end_iter = message_buffer.get_end_iter()
		message = message_buffer.get_text(start_iter, end_iter, 0)

		# send the message
		self.send_gc_message(message)

		message_buffer.set_text('')

	def send_gc_message(self, message):
		'''call this function to send our message'''
		if not message:
			return
		room_jid = self.get_active_jid()
		message_textview = self.xmls[room_jid].get_widget(
			'message_textview')
		conversation_textview = self.xmls[room_jid].get_widget(
			'conversation_textview')
		message_buffer = message_textview.get_buffer()
		if message != '' or message != '\n':
			self.save_sent_message(room_jid, message)
			if message in ['/clear', '/clear ']:
				self.on_clear(None, conversation_textview) # clear conversation
				self.on_clear(None, message_textview) # clear message textview too
				return

			elif message in ('/compact', '/compact '):
				# toggle compact
				self.set_compact_view(not self.compact_view_current_state)
				self.on_clear(None, message_textview)
				return

			elif message.startswith('/nick '):
				new_nick = message[6:].strip() # 6 is len('/nick ')
				if len(new_nick.split()) == 1: #dont accept /nick foo bar
					gajim.connections[self.account].change_gc_nick(room_jid,
						new_nick)
				return # don't print the command

			elif message.startswith('/chat '):#eg. /chat fooman
				to_whom_nick = message[6:].strip() # 6 is len('/nick ')
				if len(to_whom_nick.split()) == 1: #dont accept /chat foo bar
					nicks = self.get_nick_list(room_jid)
					if to_whom_nick in nicks:
						self.on_send_pm(nick=to_whom_nick)
				return # don't print the command
				
			elif message.startswith('/msg '): #eg. /msg fooman hello man what's up
				text_after_msg_command = message[5:].strip() # 5 is len('/msg ')
				splitted_text_after_msg_command = text_after_msg_command.split()
				if len(splitted_text_after_msg_command) >= 2: #dont accept /msg foo
					nicks = self.get_nick_list(room_jid)
					to_whom_nick = splitted_text_after_msg_command[0]
					if to_whom_nick in nicks:
						message = ' '.join(splitted_text_after_msg_command[1:])
						self.on_send_pm(nick=to_whom_nick, msg=message)
				return # don't print the command
			
			elif message.startswith('/topic'):
				# eg. /topic Peace allover!
				# or /topic to get the subject printed
				after_command = message[6:] # 6 is len('/topic')
				splitted_arg = after_command.split()
				if not message[6].isspace() and len(message) > 6:
					# he wrote /topicA so do not accept that
					return
				if len(splitted_arg): # we set subject
					new_subj = ' '.join(splitted_arg).strip()
					gajim.connections[self.account].send_gc_subject(room_jid,
						new_subj)
				else:
					 # print it as green text
					self.print_conversation(self.subjects[room_jid], room_jid)
				return # don't print the command
			
			elif message.startswith('/ban '): #eg. /ban fooman he was a bad boy
				text_after_ban_command = message[5:].strip() # 5 is len('/ban ')
				splitted_text_after_ban_command = text_after_ban_command.split()
				if len(splitted_text_after_ban_command) == 1:
					# reason is optional so accept just nick
					nick_to_ban = splitted_text_after_msg_command[0]
					if nick_to_ban in nicks:
						fjid = get_fjid_from_nick(room_jid, nick_to_ban)
						gajim.connections[self.account].gc_set_affiliation(room_jid,
							fjid, 'outcast')
				elif len(splitted_text_after_ban_command) >= 2:
					# a reason was given
					nick_to_ban = splitted_text_after_msg_command[0]
					if nick_to_ban in nicks:
						reason = splitted_text_after_msg_command[1:]
						fjid = get_fjid_from_nick(room_jid, nick_to_ban)
						gajim.connections[self.account].gc_set_affiliation(room_jid,
							fjid, 'outcast', reason)
				return # don't print the command

		gajim.connections[self.account].send_gc_message(room_jid, message)
		message_buffer.set_text('')
		message_textview.grab_focus()

	def print_conversation(self, text, room_jid, contact = '', tim = None):
		"""Print a line in the conversation:
		if contact is set: it's a message from someone
		if contact is not set: it's a message from the server"""
		other_tags_for_name = []
		other_tags_for_text = []
		if contact:
			if contact == self.nicks[room_jid]: # it's us
				kind = 'outgoing'
			else:
				kind = 'incoming'
		else:
			kind = 'status'

		if kind == 'incoming' and \
				text.lower().find(self.nicks[room_jid].lower()) != -1:
			other_tags_for_name.append('bold')
			other_tags_for_text.append('marked')
		
		chat.Chat.print_conversation_line(self, text, room_jid, kind, contact,
			tim, other_tags_for_name, [], other_tags_for_text)

	def kick(self, widget, room_jid, nick):
		"""kick a user"""
		# ask for reason
		instance = dialogs.InputDialog(_('Kicking %s') % nick,
			_('You may specify a reason below:'))
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			reason = instance.input_entry.get_text()
		else:
			return # stop kicking procedure
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'none',
			reason)

	def grant_voice(self, widget, room_jid, nick):
		"""grant voice privilege to a user"""
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'participant')

	def revoke_voice(self, widget, room_jid, nick):
		"""revoke voice privilege to a user"""
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'visitor')

	def grant_moderator(self, widget, room_jid, nick):
		"""grant moderator privilege to a user"""
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'moderator')

	def revoke_moderator(self, widget, room_jid, nick):
		"""revoke moderator privilege to a user"""
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'participant')

	def ban(self, widget, room_jid, jid):
		"""ban a user"""
		# to ban we know the real jid. so jid is not fakejid
		nick = gajim.get_nick_from_jid(jid)
		# ask for reason
		instance = dialogs.InputDialog(_('Banning %s') % nick,
			_('You may specify a reason below:'))
		response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			reason = instance.input_entry.get_text()
		else:
			return # stop banning procedure
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid,
			'outcast', reason)

	def grant_membership(self, widget, room_jid, jid):
		"""grant membership privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid,
			'member')

	def revoke_membership(self, widget, room_jid, jid):
		"""revoke membership privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid,
			'none')

	def grant_admin(self, widget, room_jid, jid):
		"""grant administrative privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid, 'admin')

	def revoke_admin(self, widget, room_jid, jid):
		"""revoke administrative privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid,
			'member')

	def grant_owner(self, widget, room_jid, jid):
		"""grant owner privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid, 'owner')

	def revoke_owner(self, widget, room_jid, jid):
		"""revoke owner privilege to a user"""
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid, 'admin')

	def on_info(self, widget, room_jid, nick):
		"""Call vcard_information_window class to display user's information"""
		c = gajim.gc_contacts[self.account][room_jid][nick]
		if c.jid and c.resource: # on GC, we know resource only if we're mod and up
			jid = c.jid
			fjid = c.jid + '/' + c.resource
		else:
			fjid = gajim.construct_fjid(room_jid, nick)
			jid = fjid
		if self.plugin.windows[self.account]['infos'].has_key(jid):
			self.plugin.windows[self.account]['infos'][jid].window.present()
		else:
			# we copy contact because c.jid must contain the fakeJid for vcard
			c2 = Contact(jid = jid, name = c.name, groups = c.groups, 
				show = c.show, status = c.status, sub = c.sub, 
				resource = c.resource, role = c.role, affiliation = c.affiliation)
			self.plugin.windows[self.account]['infos'][jid] = \
				dialogs.VcardWindow(c2, self.plugin, self.account, False)

	def on_add_to_roster(self, widget, jid):
		dialogs.AddNewContactWindow(self.plugin, self.account, jid)

	def on_send_pm(self, widget=None, model=None, iter=None, nick=None, msg=None):
		'''opens a chat window and msg is not None sends private message to a 
		contact in a room'''
		if nick is None:
			nick = model[iter][1]
		room_jid = self.get_active_jid()
		fjid = gajim.construct_fjid(room_jid, nick) # 'fake' jid
		if not self.plugin.windows[self.account]['chats'].has_key(fjid):
			show = gajim.gc_contacts[self.account][room_jid][nick].show
			u = Contact(jid = fjid, name =  nick, groups = ['none'], show = show,
				sub = 'none')
			self.plugin.roster.new_chat(u, self.account)
		
		#make active here in case we need to send a message
		self.plugin.windows[self.account]['chats'][fjid].set_active_tab(fjid)

		if msg:
			self.plugin.windows[self.account]['chats'][fjid].send_message(msg)
		self.plugin.windows[self.account]['chats'][fjid].window.present()

	def on_voice_checkmenuitem_activate(self, widget, room_jid, nick):
		if widget.get_active():
			self.grant_voice(widget, room_jid, nick)
		else:
			self.revoke_voice(widget, room_jid, nick)

	def on_moderator_checkmenuitem_activate(self, widget, room_jid, nick):
		if widget.get_active():
			self.grant_moderator(widget, room_jid, nick)
		else:
			self.revoke_moderator(widget, room_jid, nick)

	def on_member_checkmenuitem_activate(self, widget, room_jid, jid):
		if widget.get_active():
			self.grant_membership(widget, room_jid, jid)
		else:
			self.revoke_membership(widget, room_jid, jid)

	def on_admin_checkmenuitem_activate(self, widget, room_jid, jid):
		if widget.get_active():
			self.grant_admin(widget, room_jid, jid)
		else:
			self.revoke_admin(widget, room_jid, jid)

	def on_owner_checkmenuitem_activate(self, widget, room_jid, jid):
		if widget.get_active():
			self.grant_owner(widget, room_jid, jid)
		else:
			self.revoke_owner(widget, room_jid, jid)

	def mk_menu(self, room_jid, event, iter):
		"""Make user's popup menu"""
		model = self.list_treeview[room_jid].get_model()
		nick = model[iter][1]
		c = gajim.gc_contacts[self.account][room_jid][nick]
		jid = c.jid
		target_affiliation = c.affiliation
		target_role = c.role

		# looking for user's affiliation and role
		user_nick = self.nicks[room_jid]
		user_affiliation = gajim.gc_contacts[self.account][room_jid][user_nick].\
			affiliation
		user_role = self.get_role(room_jid, user_nick)
		
		# making menu from glade
		xml = gtk.glade.XML(GTKGUI_GLADE, 'gc_occupants_menu', APP)

		# these conditions were taken from JEP 0045
		item = xml.get_widget('kick_menuitem')
		item.connect('activate', self.kick, room_jid, nick)
		if user_role != 'moderator' or target_role == 'moderator':
			item.set_sensitive(False)

		item = xml.get_widget('voice_checkmenuitem')
		item.set_active(target_role != 'visitor')
		if user_role != 'moderator' or \
		   user_affiliation == 'none' or \
		   (user_affiliation=='member' and target_affiliation!='none') or \
		   target_affiliation in ('admin', 'owner'):
			item.set_sensitive(False)
		item.connect('activate', self.on_voice_checkmenuitem_activate, room_jid,
			nick)

		item = xml.get_widget('moderator_checkmenuitem')
		item.set_active(target_role == 'moderator')
		if not user_affiliation in ('admin', 'owner') or \
		   target_affiliation in ('admin', 'owner'):
			item.set_sensitive(False)
		item.connect('activate', self.on_moderator_checkmenuitem_activate,
			room_jid, nick)

		item = xml.get_widget('ban_menuitem')
		if not user_affiliation in ('admin', 'owner') or \
		   (target_affiliation in ('admin', 'owner') and\
		   user_affiliation != 'owner'):
			item.set_sensitive(False)
		item.connect('activate', self.ban, room_jid, jid)

		item = xml.get_widget('member_checkmenuitem')
		item.set_active(target_affiliation != 'none')
		if not user_affiliation in ('admin', 'owner') or \
		   (user_affiliation != 'owner' and target_affiliation in ('admin','owner')):
			item.set_sensitive(False)
		item.connect('activate', self.on_member_checkmenuitem_activate,
			room_jid, jid)

		item = xml.get_widget('admin_checkmenuitem')
		item.set_active(target_affiliation in ('admin', 'owner'))
		if not user_affiliation == 'owner':
			item.set_sensitive(False)
		item.connect('activate', self.on_admin_checkmenuitem_activate,
			room_jid, jid)

		item = xml.get_widget('owner_checkmenuitem')
		item.set_active(target_affiliation == 'owner')
		if not user_affiliation == 'owner':
			item.set_sensitive(False)
		item.connect('activate', self.on_owner_checkmenuitem_activate,
			room_jid, jid)

		item = xml.get_widget('information_menuitem')
		item.connect('activate', self.on_info, room_jid, nick)

		item = xml.get_widget('add_to_roster_menuitem')
		if not jid:
			item.set_sensitive(False)
		item.connect('activate', self.on_add_to_roster, jid)

		item = xml.get_widget('send_private_message_menuitem')
		item.connect('activate', self.on_send_pm, model, iter)

		# show the popup now!
		menu = xml.get_widget('gc_occupants_menu')
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()

	def remove_tab(self, room_jid):
		if time.time() - gajim.last_message_time[self.account][room_jid] < 2:
			dialog = dialogs.ConfirmationDialog(
				_('You just received a new message in room "%s"'),
				_('If you close this tab, the message will be lost.') % \
				room_jid.split('@')[0])
			if dialog.get_response() != gtk.RESPONSE_OK:
				return

		chat.Chat.remove_tab(self, room_jid, 'gc')
		if len(self.xmls) > 0:
			gajim.connections[self.account].send_gc_status(self.nicks[room_jid],
				room_jid, 'offline', 'offline')
			del self.nicks[room_jid]
			del gajim.gc_contacts[self.account][room_jid]
			del self.list_treeview[room_jid]
			del self.subjects[room_jid]
			del self.name_labels[room_jid]
			del self.hpaneds[room_jid]

	def new_room(self, room_jid, nick):
		self.names[room_jid] = room_jid.split('@')[0]
		self.xmls[room_jid] = gtk.glade.XML(GTKGUI_GLADE, 'gc_vbox', APP)
		self.childs[room_jid] = self.xmls[room_jid].get_widget('gc_vbox')
		chat.Chat.new_tab(self, room_jid)
		self.nicks[room_jid] = nick
		gajim.gc_contacts[self.account][room_jid] = {}
		self.subjects[room_jid] = ''
		self.room_creation[room_jid] = time.time()
		self.nick_hits[room_jid] = []
		self.cmd_hits[room_jid] = []
		self.last_key_tabs[room_jid] = False
		self.hpaneds[room_jid] = self.xmls[room_jid].get_widget('hpaned')
		self.list_treeview[room_jid] = self.xmls[room_jid].get_widget(
			'list_treeview')
		self.subject_tooltip[room_jid] = gtk.Tooltips()
		
		# we want to know when the the widget resizes, because that is
		# an indication that the hpaned has moved...
		# FIXME: Find a better indicator that the hpaned has moved.
		self.list_treeview[room_jid].connect('size-allocate',
			self.on_treeview_size_allocate)
		conversation_textview = self.xmls[room_jid].get_widget(
			'conversation_textview')
		self.name_labels[room_jid] = self.xmls[room_jid].get_widget(
			'banner_name_label')
		self.paint_banner(room_jid)
		#FIXME: when gtk2.4 is OOOOLD do it via glade2.10+  
		if gtk.pygtk_version >= (2, 6, 0) and gtk.gtk_version >= (2, 6, 0):
			self.name_labels[room_jid].set_ellipsize(pango.ELLIPSIZE_END)
		
		# connect the menuitems to their respective functions
		xm = gtk.glade.XML(GTKGUI_GLADE, 'gc_popup_menu', APP)
		xm.signal_autoconnect(self)
		self.gc_popup_menu = xm.get_widget('gc_popup_menu')
		# don't show history_menuitem on show_all()
		self.gc_popup_menu.get_children()[0].set_no_show_all(True)

		#status_image, nickname, shown_nick
		store = gtk.TreeStore(gtk.Image, str, str)
		store.set_sort_column_id(1, gtk.SORT_ASCENDING)
		column = gtk.TreeViewColumn('contacts')
		renderer_image = cell_renderer_image.CellRendererImage()
		renderer_image.set_property('width', 20)
		column.pack_start(renderer_image, expand = False)
		column.add_attribute(renderer_image, 'image', 0)
		renderer_text = gtk.CellRendererText()
		column.pack_start(renderer_text, expand = True)
		column.set_attributes(renderer_text, markup = 2)
		column.set_cell_data_func(renderer_image, self.tree_cell_data_func, None)
		column.set_cell_data_func(renderer_text, self.tree_cell_data_func, None)

		self.list_treeview[room_jid].append_column(column)
		self.list_treeview[room_jid].set_model(store)
		
		# workaround to avoid gtk arrows to be shown
		column = gtk.TreeViewColumn() # 2nd COLUMN
		renderer = gtk.CellRendererPixbuf()
		column.pack_start(renderer, expand = False)
		self.list_treeview[room_jid].append_column(column)
		column.set_visible(False)
		self.list_treeview[room_jid].set_expander_column(column)

		# set the position of the current hpaned
		self.hpaneds[room_jid] = self.xmls[room_jid].get_widget(
			'hpaned')
		self.hpaneds[room_jid].set_position(self.hpaned_position)

		self.redraw_tab(room_jid)
		self.show_title()
		self.set_subject(room_jid, '') # Set an empty subject to show the room_jid
		conversation_textview.grab_focus()
		self.childs[room_jid].show_all()

	def on_treeview_size_allocate(self, widget, allocation):
		"""The MUC treeview has resized. Move the hpaneds in all tabs to match"""
		thisroom_jid = self.get_active_jid()
		self.hpaned_position = self.hpaneds[thisroom_jid].get_position()
		for room_jid in self.xmls:
			self.hpaneds[room_jid].set_position(self.hpaned_position)

	def tree_cell_data_func(self, column, renderer, model, iter, data=None):
		theme = gajim.config.get('roster_theme')
		if model.iter_parent(iter):
			bgcolor = gajim.config.get_per('themes', theme, 'contactbgcolor')
		else: # it is root (eg. group)
			bgcolor = gajim.config.get_per('themes', theme, 'groupbgcolor')
		renderer.set_property('cell-background', bgcolor)
			
	def on_actions_button_clicked(self, widget):
		"""popup action menu"""
		menu = self.gc_popup_menu
		menu.get_children()[0].hide() # hide history_menuitem
		menu = self.remove_possible_switch_to_menuitems(menu)
		menu.popup(None, None, None, 1, 0)
		menu.show_all()

	def on_list_treeview_button_press_event(self, widget, event):
		"""popup user's group's or agent menu"""
		room_jid = self.get_active_jid()
		if event.button == 3: # right click
			try:
				path, column, x, y = widget.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				widget.get_selection().unselect_all()
				return False
			widget.get_selection().select_path(path)
			model = widget.get_model()
			iter = model.get_iter(path)
			if len(path) == 2:
				self.mk_menu(room_jid, event, iter)
			return True
		if event.button == 2: # middle click
			try:
				path, column, x, y = widget.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				widget.get_selection().unselect_all()
				return False
			widget.get_selection().select_path(path)
			model = widget.get_model()
			iter = model.get_iter(path)
			if len(path) == 2:
				nick = model[iter][1]
				fjid = gajim.construct_fjid(room_jid, nick)
				if not self.plugin.windows[self.account]['chats'].has_key(fjid):
					show = gajim.gc_contacts[self.account][room_jid][nick].show
					u = Contact(jid = fjid, name = nick, groups = ['none'],
						show = show, sub = 'none')
					self.plugin.roster.new_chat(u, self.account)
				self.plugin.windows[self.account]['chats'][fjid].set_active_tab(fjid)
				self.plugin.windows[self.account]['chats'][fjid].window.present()
			return True
		if event.button == 1: # left click
			try:
				path, column, x, y = widget.get_path_at_pos(int(event.x),
					int(event.y))
			except TypeError:
				widget.get_selection().unselect_all()
				return False

			model = widget.get_model()
			iter = model.get_iter(path)
			nick = model[iter][1]
			if not nick in gajim.gc_contacts[self.account][room_jid]: #it's a group
				if x < 20: # first cell in 1st column (the arrow SINGLE clicked)
					if (widget.row_expanded(path)):
						widget.collapse_row(path)
					else:
						widget.expand_row(path, False)
		
		return False

	def on_list_treeview_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			widget.get_selection().unselect_all()
		return False

	def on_list_treeview_row_activated(self, widget, path, col = 0):
		"""When an iter is double clicked: open the chat window"""
		model = widget.get_model()
		iter = model.get_iter(path)
		if len(path) == 1: # It's a group
			if (widget.row_expanded(path)):
				widget.collapse_row(path)
			else:
				widget.expand_row(path, False)
		else: # We want to send a private message
			room_jid = self.get_active_jid()
			nick = model[iter][1]
			fjid = gajim.construct_fjid(room_jid, nick)
			if not self.plugin.windows[self.account]['chats'].has_key(fjid):
				show = gajim.gc_contacts[self.account][room_jid][nick].show
				u = Contact(jid = fjid, name = nick, groups = ['none'], show = show,
					sub = 'none')
				self.plugin.roster.new_chat(u, self.account)
			self.plugin.windows[self.account]['chats'][fjid].set_active_tab(fjid)
			self.plugin.windows[self.account]['chats'][fjid].window.present()

	def on_list_treeview_row_expanded(self, widget, iter, path):
		"""When a row is expanded: change the icon of the arrow"""
		model = widget.get_model()
		image = self.plugin.roster.jabber_state_images['opened']
		model.set_value(iter, 0, image)
	
	def on_list_treeview_row_collapsed(self, widget, iter, path):
		"""When a row is collapsed: change the icon of the arrow"""
		model = widget.get_model()
		image = self.plugin.roster.jabber_state_images['closed']
		model.set_value(iter, 0, image)
