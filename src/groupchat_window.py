## plugins/groupchat_window.py
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
from gajim import User
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
		self.muc_cmds = ['chat', 'clear', 'compact', 'me', 'msg', 'nick'] # alphanum sorted
		self.nicks = {} # our nick for each groupchat we are in
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
		self.xml.signal_connect('on_groupchat_window_event',
			self.on_groupchat_window_event)
		self.xml.signal_connect('on_chat_notebook_key_press_event', 
			self.on_chat_notebook_key_press_event)
		self.xml.signal_connect('on_chat_notebook_switch_page', 
			self.on_chat_notebook_switch_page)
		self.xml.signal_connect('on_close_window_activate',
			self.on_close_window_activate)

		# needed for popup menu
		self.xml.get_widget('groupchat_window').add_events(
			gtk.gdk.BUTTON_PRESS_MASK)

		# get size and position from config
		if gajim.config.get('saveposition'):
			self.window.move(gajim.config.get('gc-x-position'),
					gajim.config.get('gc-y-position'))
			self.window.resize(gajim.config.get('gc-width'),
					gajim.config.get('gc-height'))

		self.window.show_all()

	def save_var(self, jid):
		if not jid in self.nicks:
			return {}
		return {
			'nick': self.nicks[jid],
			'model': self.list_treeview[jid].get_model(),
			'subject': self.subjects[jid],
		}
		
	def load_var(self, jid, var):
		if not self.xmls.has_key(jid):
			return
		self.list_treeview[jid].set_model(var['model'])
		self.list_treeview[jid].expand_all()
		self.set_subject(jid, var['subject'])

	def on_close_window_activate(self, widget):
		if not self.on_groupchat_window_delete_event(widget, None):
			self.window.destroy()

	def on_groupchat_window_delete_event(self, widget, event):
		"""close window"""
		for room_jid in self.xmls:
			if time.time() - self.last_message_time[room_jid] < 2:
				dialog = dialogs.ConfirmationDialog(
		_('You just received a new message in room "%s"') %room_jid.split('@')[0],
			_('If you close this window, this message will be lost.')
					)
				if dialog.get_response() != gtk.RESPONSE_OK:
					return True #stop the propagation of the event
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

	def on_groupchat_window_event(self,widget,event):
		if event.type != gtk.gdk.BUTTON_PRESS:
			return False
		self.on_chat_window_button_press_event(widget, event)
		return True

	def on_groupchat_window_key_press_event(self, widget, event):
		self.on_chat_window_button_press_event(widget, event)
		return True

	def on_chat_notebook_key_press_event(self, widget, event):
		chat.Chat.on_chat_notebook_key_press_event(self, widget, event)
	
	def on_chat_notebook_switch_page(self, notebook, page, page_num):
		new_child = notebook.get_nth_page(page_num)
		new_jid = ''
		for jid in self.xmls:
			if self.childs[jid] == new_child: 
				new_jid = jid
				break
		subject = self.subjects[new_jid]

		# escape chars when necessary
		subject = subject.replace('&', '&amp;')
		new_jid = new_jid.replace('&', '&amp;')

		name_label = self.name_labels[new_jid]
		name_label.set_markup('<span weight="heavy" size="x-large">%s</span>\n%s' % (new_jid, subject))
		event_box = name_label.get_parent()
		self.subject_tooltip[new_jid].set_tip(event_box, subject)
		chat.Chat.on_chat_notebook_switch_page(self, notebook, page, page_num)

	def get_role_iter(self, room_jid, role):
		model = self.list_treeview[room_jid].get_model()
		fin = False
		iter = model.get_iter_root()
		if not iter:
			return None
		while not fin:
			role_name = model.get_value(iter, 2)
			if role == role_name:
				return iter
			iter = model.iter_next(iter)
			if not iter:
				fin = True
		return None

	def get_user_iter(self, room_jid, nick):
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
		model = self.list_treeview[room_jid].get_model()
		list = []
		fin = False
		role = model.get_iter_root()
		if not role:
			return list
		while not fin:
			fin2 = False
			user = model.iter_children(role)
			if not user:
				fin2 = True
			while not fin2:
				nick = unicode(model.get_value(user, 1))
				list.append(nick)
				user = model.iter_next(user)
				if not user:
					fin2 = True
			role = model.iter_next(role)
			if not role:
				fin = True
		return list

	def remove_user(self, room_jid, nick):
		"""Remove a user from the list_users"""
		model = self.list_treeview[room_jid].get_model()
		iter = self.get_user_iter(room_jid, nick)
		if not iter:
			return
		parent_iter = model.iter_parent(iter)
		model.remove(iter)
		if model.iter_n_children(parent_iter) == 0:
			model.remove(parent_iter)
	
	def add_user_to_roster(self, room_jid, nick, show, role, jid, affiliation):
		model = self.list_treeview[room_jid].get_model()
		image = self.plugin.roster.jabber_state_images[show]
		role_iter = self.get_role_iter(room_jid, role)
		if not role_iter:
			role_iter = model.append(None,
				(self.plugin.roster.jabber_state_images['closed'], '<b>%ss</b>' % role.capitalize(),
				 role, '', ''))
		iter = model.append(role_iter, (image, nick, jid, show, affiliation))
		self.list_treeview[room_jid].expand_row((model.get_path(role_iter)),
			False)
		return iter
	
	def get_role(self, room_jid, jid_iter):
		model = self.list_treeview[room_jid].get_model()
		path = model.get_path(jid_iter)[0]
		iter = model.get_iter(path)
		return model.get_value(iter, 2)

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
					show = model.get_value(user_iter, 3)
					state_images = roster.get_appropriate_state_images(room_jid)
					image = state_images[show] #FIXME: always Jabber why?
					model.set_value(user_iter, 0, image)
					user_iter = model.iter_next(user_iter)
				role_iter = model.iter_next(role_iter)

	def chg_user_status(self, room_jid, nick, show, status, role, affiliation, \
		jid, reason, actor, statusCode, new_nick, account):
		"""When a user changes his status"""
		if not role:
			role = 'visitor'
		model = self.list_treeview[room_jid].get_model()
		if show == 'offline' or show == 'error':
			if statusCode == '307':
				self.print_conversation(_('%s has been kicked by %s: %s') % (nick,
					actor, reason), room_jid)
			elif statusCode == '303': # Someone changed his nick
				self.print_conversation(_('%s is now known as %s') % (nick,
					new_nick), room_jid)
				if nick == self.nicks[room_jid]: # We changed our nick
					self.nicks[room_jid] = new_nick
			self.remove_user(room_jid, nick)
			if nick == self.nicks[room_jid] and statusCode != '303': # We became offline
				model.clear()
		else:
			iter = self.get_user_iter(room_jid, nick)
			ji = jid
			if jid:
				ji = jid.split('/')[0]
			if not iter:
				iter = self.add_user_to_roster(room_jid, nick, show, role, ji, affiliation)
			else:
				actual_role = self.get_role(room_jid, iter)
				if role != actual_role:
					self.remove_user(room_jid, nick)
					self.add_user_to_roster(room_jid, nick, show, role, ji, affiliation)
				else:
					roster = self.plugin.roster
					state_images = roster.get_appropriate_state_images(ji)
					image = state_images[show]
					model.set_value(iter, 0, image)
					model.set_value(iter, 3, show)
					model.set_value(iter, 4, affiliation)
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
		name_label.set_markup('<span weight="heavy" size="x-large">%s</span>\n%s' % (room_jid, subject))
		event_box = name_label.get_parent()
		self.subject_tooltip[room_jid].set_tip(event_box, subject)

	def on_change_subject_menuitem_activate(self, widget):
		room_jid = self.get_active_jid()
		label_text = self.name_labels[room_jid].get_text() # whole text (including JID)
		subject = label_text[label_text.find('\n') + 1:] # just the text after the newline
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
		response = response = instance.get_response()
		if response == gtk.RESPONSE_OK:
			nick = instance.input_entry.get_text()
			gajim.connections[self.account].change_gc_nick(room_jid, nick)

	def on_configure_room_menuitem_activate(self, widget):
		room_jid = self.get_active_jid()
		gajim.connections[self.account].request_gc_config(room_jid)

	def on_bookmark_room_menuitem_activate(self, widget):
		room_jid = self.get_active_jid()
		bm = { 'name': room_jid,
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
			message_buffer.set_text('', -1)
			return True
		elif event.keyval == gtk.keysyms.Up:
			if event.state & gtk.gdk.CONTROL_MASK: #Ctrl+UP
				self.sent_messages_scroll(room_jid, 'up', widget.get_buffer())
		elif event.keyval == gtk.keysyms.Down:
			if event.state & gtk.gdk.CONTROL_MASK: #Ctrl+Down
				self.sent_messages_scroll(room_jid, 'down', widget.get_buffer())
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

		message_buffer.set_text('', -1)

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
				self.set_compact_view(not self.get_compact_view())
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

		gajim.connections[self.account].send_gc_message(room_jid, message)
		message_buffer.set_text('', -1)
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
		gajim.connections[self.account].gc_set_role(room_jid, nick, 'none')

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
		gajim.connections[self.account].gc_set_affiliation(room_jid, jid,
			'outcast')

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

	def on_info(self, widget, jid):
		"""Call vcard_information_window class to display user's information"""
		if self.plugin.windows[self.account]['infos'].has_key(jid):
			self.plugin.windows[self.account]['infos'][jid].window.present()
		else:
			self.plugin.windows[self.account]['infos'][jid] = \
				dialogs.VcardWindow(jid, self.plugin, self.account, True)
			# FIXME: when we'll have a user for each contact, this won't be needed
			# cause we'll user real information window
			vcard_xml = self.plugin.windows[self.account]['infos'][jid].xml
			hbuttonbox = vcard_xml.get_widget('information_hbuttonbox')
			children = hbuttonbox.get_children()
			hbuttonbox.remove(children[0])
			hbuttonbox.remove(children[1])
			vcard_xml.get_widget('nickname_label').set_text(jid)
			gajim.connections[self.account].request_vcard(jid)
			
			#FIXME: we need the resource but it's not saved
			#self.plugin.send('ASK_OS_INFO', self.account, jid, resource)

	def on_add_to_roster(self, widget, jid):
		dialogs.AddNewContactWindow(self.plugin, self.account, jid)

	def on_send_pm(self, widget=None, model=None, iter=None, nick=None, msg=None):
		'''opens a chat window and optionally sends private message to a 
		contact in a room'''
		if nick is None:
			nick = model.get_value(iter, 1)
		room_jid = self.get_active_jid()
		fjid = room_jid + '/' + nick # 'fake' jid
		if not self.plugin.windows[self.account]['chats'].has_key(fjid):
			#show = model.get_value(iter, 3) #FIXME: be able to get show from nick
			show = 'chat'
			u = User(fjid, nick, ['none'], show, '', 'none', None, '', 0, '')
			self.plugin.roster.new_chat(u, self.account)
		if msg:
			self.plugin.windows[self.account]['chats'][fjid].send_message(msg)
		self.plugin.windows[self.account]['chats'][fjid].set_active_tab(fjid)
		self.plugin.windows[self.account]['chats'][fjid].window.present()

	def mk_menu(self, room_jid, event, iter):
		"""Make user's popup menu"""
		model = self.list_treeview[room_jid].get_model()
		nick = model.get_value(iter, 1)
		jid = model.get_value(iter, 2)
		target_affiliation = model.get_value(iter, 4)
		target_role = self.get_role(room_jid, iter)

		# looking for user's affiliation and role
		user_iter = self.get_user_iter(room_jid, self.nicks[room_jid])
		user_affiliation = model.get_value(user_iter, 4)
		user_role = self.get_role(room_jid, user_iter)
		
		menu = gtk.Menu()
		item = gtk.MenuItem(_('_Privileges'))
		menu.append(item)
		
		sub_menu = gtk.Menu()
		item.set_submenu(sub_menu)

		# these conditions were taken from JEP 0045
		if (user_role == 'moderator'):
			if (target_role in ('visitor','participant')):
				item = gtk.MenuItem(_('_Kick'))
				sub_menu.append(item)
				item.connect('activate', self.kick, room_jid, nick)
	
			if (target_role == 'visitor'):
				item = gtk.MenuItem(_('_Grant Voice'))
				sub_menu.append(item)
				item.connect('activate', self.grant_voice, room_jid, nick)
			# I know it is complicated, but this is how does JEP0045 descibe
			# 'revoking voice' privilege
			elif (user_affiliation=='member' and target_affiliation=='none') or \
			     ((user_affiliation in ('admin','owner')) and \
			      (target_affiliation in ('none','member'))):
				item = gtk.MenuItem(_('_Revoke Voice'))
				sub_menu.append(item)
				item.connect('activate', self.revoke_voice, room_jid, nick)

		if (user_affiliation in ('admin','owner')):
			item = gtk.MenuItem()
			sub_menu.append(item)

			if not target_role == 'moderator':
				item = gtk.MenuItem(_('_Grant Moderator'))
				sub_menu.append(item)
				item.connect('activate', self.grant_moderator, room_jid, nick)
			elif target_affiliation in ('none','member'):
				item = gtk.MenuItem(_('_Revoke Moderator'))
				sub_menu.append(item)
				item.connect('activate', self.revoke_moderator, room_jid, nick)

			if (target_affiliation in ('none','member')) or \
			    (user_affiliation=='owner'):
				item = gtk.MenuItem(_('_Ban'))
				sub_menu.append(item)
				item.connect('activate', self.ban, room_jid, jid)

			if target_affiliation=='none':
				item = gtk.MenuItem(_('_Grant Membership'))
				sub_menu.append(item)
				item.connect('activate', self.grant_membership, room_jid, jid)
			if (target_affiliation in ('member')) or \
			   (target_affiliation in ('admin','owner') and (user_affiliation=='owner')):
				item = gtk.MenuItem(_('_Revoke Membership'))
				sub_menu.append(item)
				item.connect('activate', self.revoke_membership, room_jid, jid)

		if user_affiliation=='owner':
			if (not target_affiliation=='admin'):
				item = gtk.MenuItem(_('_Grant Admin'))
				sub_menu.append(item)
				item.connect('activate', self.grant_admin, room_jid, jid)
			else:
				item = gtk.MenuItem(_('_Revoke Admin'))
				sub_menu.append(item)
				item.connect('activate', self.revoke_admin, room_jid, jid)

			if (not target_affiliation=='owner'):
				item = gtk.MenuItem(_('_Grant Owner'))
				sub_menu.append(item)
				item.connect('activate', self.grant_owner, room_jid, jid)
			else:
				item = gtk.MenuItem(_('_Revoke Owner'))
				sub_menu.append(item)
				item.connect('activate', self.revoke_owner, room_jid, jid)

		item = gtk.MenuItem(_('_Information'))
		menu.append(item)
		item.connect('activate', self.on_info, jid and jid or (room_jid+'/'+nick))

		if jid:
			item = gtk.MenuItem(_('_Add to Roster'))
			menu.append(item)
			item.connect('activate', self.on_add_to_roster, jid)
		
		item = gtk.MenuItem(_('Send _Private Message'))
		menu.append(item)
		item.connect('activate', self.on_send_pm, model, iter)
		
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()
	
	def populate_popup_menu(self, menu):
		"""Add menuitems do popup menu"""

		# FIXME: add icons / use ItemFactory
		item = gtk.MenuItem(_('_History'))
		item.connect('activate', self.on_history_button_clicked)
		menu.append(item)

		item = gtk.MenuItem(_('Configure _Room'))
		item.connect('activate', self.on_configure_room_menuitem_activate)
		menu.append(item)

		item = gtk.MenuItem(_('Change _Subject'))
		item.connect('activate', self.on_change_subject_menuitem_activate)
		menu.append(item)

		item = gtk.MenuItem(_('Change _Nickname'))
		item.connect('activate', self.on_change_nick_menuitem_activate)
		menu.append(item)

		item = gtk.MenuItem(_('_Bookmark This Room'))
		item.connect('activate', self.on_bookmark_room_menuitem_activate)
		menu.append(item)

		item=gtk.MenuItem(_('_Toggle compact view'))
		item.connect('activate', lambda obj:self.set_compact_view(
			not self.get_compact_view()))
		menu.append(item)

	def remove_tab(self, room_jid):
		if time.time() - self.last_message_time[room_jid] < 2:
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
			del self.list_treeview[room_jid]
			del self.subjects[room_jid]
			del self.name_labels[room_jid]
			del self.hpaneds[room_jid]

	def new_room(self, room_jid, nick):
		self.names[room_jid] = room_jid.split('@')[0]
		self.xmls[room_jid] = gtk.glade.XML(GTKGUI_GLADE, 'gc_vbox', APP)
		self.childs[room_jid] = self.xmls[room_jid].get_widget('gc_vbox')
		self.set_compact_view(self.get_compact_view())
		chat.Chat.new_tab(self, room_jid)
		self.nicks[room_jid] = nick
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
		self.list_treeview[room_jid].connect('size-allocate', self.on_treeview_size_allocate)
		conversation_textview = self.xmls[room_jid].get_widget(
			'conversation_textview')
		self.name_labels[room_jid] = self.xmls[room_jid].get_widget(
			'banner_name_label')
		self.paint_banner(room_jid)
		#FIXME: when gtk2.4 is OOOOLD do it via glade2.10+  
		if gtk.pygtk_version >= (2, 6, 0) and gtk.gtk_version >= (2, 6, 0):
			self.name_labels[room_jid].set_ellipsize(pango.ELLIPSIZE_END)
		
		# connect the menuitems to their respective functions
		xm = gtk.glade.XML(GTKGUI_GLADE, 'gc_actions_menu', APP)
		xm.signal_autoconnect(self)
		self.gc_actions_menu = xm.get_widget('gc_actions_menu')

		#status_image, nickname, real_jid, show, affiliation
		store = gtk.TreeStore(gtk.Image, str, str, str, str)
		store.set_sort_column_id(1, gtk.SORT_ASCENDING)
		column = gtk.TreeViewColumn('contacts')
		renderer_image = cell_renderer_image.CellRendererImage()
		renderer_image.set_property('width', 20)
		column.pack_start(renderer_image, expand = False)
		column.add_attribute(renderer_image, 'image', 0)
		renderer_text = gtk.CellRendererText()
		column.pack_start(renderer_text, expand = True)
		column.set_attributes(renderer_text, markup=1)
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
		conversation_textview.grab_focus()

	def on_treeview_size_allocate(self, widget, allocation):
		"""The MUC treeview has resized. Move the hpaneds in all tabs to match"""
		thisroom_jid = self.get_active_jid()
		self.hpaned_position = self.hpaneds[thisroom_jid].get_position()
		for room_jid in self.xmls:
			self.hpaneds[room_jid].set_position(self.hpaned_position)

	def tree_cell_data_func(self, column, renderer, model, iter, data=None):
		if model.iter_parent(iter):
			bgcolor = gajim.config.get('userbgcolor')
			renderer.set_property('cell-background', bgcolor)
		else: # it is root (eg. group)
			bgcolor = gajim.config.get('groupbgcolor')
			renderer.set_property('cell-background', bgcolor)
			
	def on_actions_button_clicked(self, button):
		"""popup action menu"""
		self.gc_actions_menu.popup(None, None, None, 1, 0)
		self.gc_actions_menu.show_all()

	def on_list_treeview_button_press_event(self, widget, event):
		"""popup user's group's or agent menu"""
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
				room_jid = self.get_active_jid()
				self.mk_menu(room_jid, event, iter)
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
			status = model.get_value(iter, 3) # if no status: it's a group
			if not status:
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
			nick = model.get_value(iter, 1)
			fjid = room_jid + '/' + nick
			if not self.plugin.windows[self.account]['chats'].has_key(fjid):
				show = model.get_value(iter, 3)
				u = User(fjid, nick, ['none'], show, '', 'none', None, '', 0, 
					'')
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

	def get_compact_view(self):
		'''Is compact view turned on?'''
		return self.compact_view

	def set_compact_view(self,state):
		'''Toggle compact view'''

		self.compact_view = state
		
		for jid in self.xmls:
			widgets = [self.xmls[jid].get_widget('banner_eventbox'),
				 self.xmls[jid].get_widget('gc_actions_hbox'),
				 self.xmls[jid].get_widget('list_scrolledwindow'),
				 ]

			for widget in widgets:
				if state:
					widget.set_no_show_all(True)
					widget.hide()
				else:
					widget.set_no_show_all(False)
					widget.show()
