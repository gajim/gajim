##	plugins/groupchat_window.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Alex Podaras <bigpod@gmail.com>
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
import sre #usefull later

from dialogs import *

from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'

class Groupchat_window:
	def on_groupchat_window_delete_event(self, widget, event):
		"""close window"""
		for room_jid in self.xmls:
			if time.time() - self.last_message_time[room_jid] < 2:
				dialog = Confirmation_dialog(_('You received a message in the room %s in the last two seconds.\nDo you still want to close this window ?') % \
					room_jid.split('@')[0])
				if dialog.get_response() != gtk.RESPONSE_YES:
					return True #stop the propagation of the event
	
	def on_groupchat_window_destroy(self, widget):
		for room_jid in self.xmls:
			self.plugin.send('GC_STATUS', self.account, (self.nicks[room_jid], \
				room_jid, 'offline', 'offline'))
			del self.plugin.windows[self.account]['gc'][room_jid]
		if self.plugin.windows[self.account]['gc'].has_key('tabbed'):
			del self.plugin.windows[self.account]['gc']['tabbed']

	def update_tags(self):
		for room_jid in self.tagIn:
			self.tagIn[room_jid].set_property('foreground', \
				self.plugin.config['inmsgcolor'])
			self.tagInBold[room_jid].set_property('foreground', \
				self.plugin.config['inmsgcolor'])
			self.tagOut[room_jid].set_property('foreground', \
				self.plugin.config['outmsgcolor'])
			self.tagStatus[room_jid].set_property('foreground', \
				self.plugin.config['statusmsgcolor'])

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
				fin2=True
			while not fin2:
				if nick == model.get_value(user, 1):
					return user_iter
				user_iter = model.iter_next(user_iter)
				if not user_iter:
					fin2 = True
			role_iter = model.iter_next(role_iter)
			if not role_iter:
				fin = True
		return None

	def get_nick_list(self, room_jid):
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
				fin2=True
			while not fin2:
				nick = model.get_value(user, 1)
				list.append(nick)
				user = model.iter_next(user)
				if not user:
					fin2 = True
			role = model.iter_next(role)
			if not role:
				fin = True
		return list

	def remove_user(self, room_jid, nick):
		"""Remove a user from the roster"""
		model = self.list_treeview[room_jid].get_model()
		iter = self.get_user_iter(room_jid, nick)
		if not iter:
			return
		parent_iter = model.iter_parent(iter)
		model.remove(iter)
		if model.iter_n_children(parent_iter) == 0:
			model.remove(parent_iter)
	
	def add_user_to_roster(self, room_jid, nick, show, role, jid):
		model = self.list_treeview[room_jid].get_model()
		img = self.plugin.roster.pixbufs[show]
		role_iter = self.get_role_iter(room_jid, role)
		if not role_iter:
			role_iter = model.append(None, (self.plugin.roster.pixbufs['closed']\
				, role + 's', role))
		iter = model.append(role_iter, (img, nick, jid))
		self.list_treeview[room_jid].expand_row((model.get_path(role_iter)), \
			False)
		return iter
	
	def get_role(self, room_jid, jid_iter):
		model = self.list_treeview[room_jid].get_model()
		path = model.get_path(jid_iter)[0]
		iter = model.get_iter(path)
		return model.get_value(iter, 2)

	def chg_user_status(self, room_jid, nick, show, status, role, affiliation, \
		jid, reason, actor, statusCode, account):
		"""When a user change his status"""
		model = self.list_treeview[room_jid].get_model()
		if show == 'offline' or show == 'error':
			if statusCode == '307':
				self.print_conversation(_('%s has been kicked by %s: %s') % (nick, \
					jid, actor, reason))
			self.remove_user(room_jid, nick)
		else:
			iter = self.get_user_iter(room_jid, nick)
			ji = jid
			if jid:
				ji = jid.split('/')[0]
			if not iter:
				iter = self.add_user_to_roster(room_jid, nick, show, role, ji)
			else:
				actual_role = self.get_role(room_jid, iter)
				if role != actual_role:
					self.remove_user(room_jid, nick)
					self.add_user_to_roster(room_jid, nick, show, role, ji)
				else:
					img = self.plugin.roster.pixbufs[show]
					model.set_value(iter, 0, img)
	
	def show_title(self):
		"""redraw the window's title"""
		unread = 0
		for room_jid in self.nb_unread:
			unread += self.nb_unread[room_jid]
		start = ""
		if unread > 1:
			start = "[" + str(unread) + "] "
		elif unread == 1:
			start = "* "
		chat = 'Groupchat in ' + room_jid
		if len(self.xmls) > 1:
			chat = 'Groupchat'
		self.window.set_title(start + chat + ' (' + self.account + ')')
	
	def redraw_tab(self, room_jid):
		"""redraw the label of the tab"""
		start = ''
		if self.nb_unread[room_jid] > 1:
			start = "[" + str(self.nb_unread[room_jid]) + "] "
		elif self.nb_unread[room_jid] == 1:
			start = "* "
		room = room_jid.split('@')[0]
		child = self.xmls[room_jid].get_widget('group_vbox')
		self.chat_notebook.set_tab_label_text(child, start + room)

	def get_active_jid(self):
		active_child = self.chat_notebook.get_nth_page(\
			self.chat_notebook.get_current_page())
		active_jid = ''
		for room_jid in self.xmls:
			child = self.xmls[room_jid].get_widget('group_vbox')
			if child == active_child:
				active_jid = room_jid
				break
		return active_jid

	def set_subject(self, room_jid, subject):
		self.subjects[room_jid] = subject
		self.xml.get_widget('subject_entry').set_text(subject)

	def on_set_button_clicked(self, widget):
		room_jid = self.get_active_jid()
		subject = self.xml.get_widget('subject_entry').get_text()
		self.plugin.send('GC_SUBJECT', self.account, (room_jid, subject))

	def on_close_button_clicked(self, button):
		room_jid = self.get_active_jid()
		self.remove_tab(room_jid)

	def on_message_textview_key_press_event(self, widget, event):
		"""When a key is pressed:
		if enter is pressed without the shit key, message (if not empty) is sent
		and printed in the conversation. Tab does autocompete in nickames"""
		if event.keyval == gtk.keysyms.Return: # ENTER
			if (event.state & gtk.gdk.SHIFT_MASK):
				return 0
			message_buffer = widget.get_buffer()
			start_iter = message_buffer.get_start_iter()
			end_iter = message_buffer.get_end_iter()
			txt = message_buffer.get_text(start_iter, end_iter, 0)
			if txt != '':
				room_jid = self.get_active_jid()
				self.plugin.send('GC_MSG', self.account, (room_jid, txt))
				message_buffer.set_text('', -1)
				widget.grab_focus()
			return 1
		elif event.keyval == gtk.keysyms.Tab: # TAB
			room_jid = self.get_active_jid()
			list_nick = self.get_nick_list(room_jid)
			message_buffer = widget.get_buffer()
			start_iter = message_buffer.get_start_iter()
			cursor_position = message_buffer.get_insert()
			end_iter = message_buffer.get_iter_at_mark(cursor_position)
			text = message_buffer.get_text(start_iter, end_iter, 0)
			if not text:
				return 0
			splited_text = text.split()
			begin = splited_text[-1]
			for nick in list_nick:
				if nick.find(begin) == 0:
					if len(splited_text) == 1:
						add = ': '
					else:
						add = ' '
					message_buffer.insert_at_cursor(nick[len(begin):] + add)
					return 1
		return 0

	def on_groupchat_window_key_press_event(self, widget, event):
		st = "1234567890" # humans count from 1, pc from 0 :P
		room_jid = self.get_active_jid()
		if event.keyval == gtk.keysyms.Escape: #ESCAPE
			self.remove_tab(room_jid)
		elif event.string and event.string in st \
			and (event.state & gtk.gdk.MOD1_MASK): # alt + 1,2,3 ...
			self.chat_notebook.set_current_page(st.index(event.string))
		elif event.keyval == gtk.keysyms.Page_Down: # PAGEDOWN
			if event.state & gtk.gdk.CONTROL_MASK:
				current = self.chat_notebook.get_current_page()
				if current > 0:
					self.chat_notebook.set_current_page(current-1)
#				else:
#					self.chat_notebook.set_current_page(\
#						self.chat_notebook.get_n_pages()-1)
			elif event.state & gtk.gdk.SHIFT_MASK:
				conversation_textview = self.xmls[room_jid].\
					get_widget('conversation_textview')
				rect = conversation_textview.get_visible_rect()
				iter = conversation_textview.get_iter_at_location(rect.x,\
					rect.y + rect.height)
				conversation_textview.scroll_to_iter(iter, 0.1, True, 0, 0)
		elif event.keyval == gtk.keysyms.Page_Up: # PAGEUP
			if event.state & gtk.gdk.CONTROL_MASK:
				current = self.chat_notebook.get_current_page()
				if current < (self.chat_notebook.get_n_pages()-1):
					self.chat_notebook.set_current_page(current+1)
#				else:
#					self.chat_notebook.set_current_page(0)
			elif event.state & gtk.gdk.SHIFT_MASK:
				conversation_textview = self.xmls[room_jid].\
					get_widget('conversation_textview')
				rect = conversation_textview.get_visible_rect()
				iter = conversation_textview.get_iter_at_location(rect.x, rect.y)
				conversation_textview.scroll_to_iter(iter, 0.1, True, 0, 1)
		elif event.keyval == gtk.keysyms.Tab and \
			(event.state & gtk.gdk.CONTROL_MASK): # CTRL+TAB
			current = self.chat_notebook.get_current_page()
			if current < (self.chat_notebook.get_n_pages()-1):
				self.chat_notebook.set_current_page(current+1)
			else:
				self.chat_notebook.set_current_page(0)
		
		'''FIXME:
		NOT GOOD steals focus from Subject entry and I cannot find a way to prevent this
		
		else: # it's a normal key press make sure message_textview has focus
			message_textview = self.xmls[room_jid].get_widget('message_textview')
			if not message_textview.is_focus():
				message_textview.grab_focus()
		'''

	def print_conversation(self, text, room_jid, contact = '', tim = None):
		"""Print a line in the conversation :
		if contact is set : it's a message from someone
		if contact is not set : it's a message from the server"""
		conversation_textview = self.xmls[room_jid].\
			get_widget('conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		if not text:
			text = ''
		end_iter = conversation_buffer.get_end_iter()
		if self.plugin.config['print_time'] == 'always':
			if not tim:
				tim = time.localtime()
			tim_format = time.strftime('[%H:%M:%S]', tim)
			conversation_buffer.insert(end_iter, tim_format + ' ')

		otext = ''
		ttext = ''
		if contact:
			if contact == self.nicks[room_jid]:
				tag = 'outgoing'
			else:
				if self.nicks[room_jid].lower() in text.lower().split():
					tag = 'incoming_bold'
				else:
					tag = 'incoming'
				self.last_message_time[room_jid] = time.time()

			if text.startswith('/me'):
				ttext = contact + text[3:] + '\n'
			else:
				ttext = '<' + contact + '> '
				otext = text + '\n'
		else:
			tag = 'status'
			ttext = text + '\n'

		conversation_buffer.insert_with_tags_by_name(end_iter, ttext, tag)
		#TODO: emoticons, url grabber
		conversation_buffer.insert(end_iter, otext)
		#scroll to the end of the textview
		conversation_textview.scroll_to_mark(conversation_buffer.get_mark('end'),\
			0.1, 0, 0, 0)
		if not self.window.is_active() and contact != '':
			self.nb_unread[room_jid] += 1
			self.redraw_tab(room_jid)
			self.show_title()

	def kick(self, widget, room_jid, nick):
		"""kick a user"""
		self.plugin.send('GC_SET_ROLE', self.account, (room_jid, nick, 'none'))

	def grant_voice(self, widget, room_jid, nick):
		"""grant voice privilege to a user"""
		self.plugin.send('GC_SET_ROLE', self.account, (room_jid, nick, \
			'participant'))

	def revoke_voice(self, widget, room_jid, nick):
		"""revoke voice privilege to a user"""
		self.plugin.send('GC_SET_ROLE', self.account, (room_jid, nick, 'visitor'))

	def grant_moderator(self, widget, room_jid, nick):
		"""grant moderator privilege to a user"""
		self.plugin.send('GC_SET_ROLE', self.account, (room_jid, nick,\
			'moderator'))

	def revoke_moderator(self, widget, room_jid, nick):
		"""revoke moderator privilege to a user"""
		self.plugin.send('GC_SET_ROLE', self.account, (room_jid, nick, \
			'participant'))

	def ban(self, widget, room_jid, jid):
		"""ban a user"""
		self.plugin.send('GC_SET_AFFILIATION', self.account, (room_jid, jid, \
			'outcast'))

	def grant_membership(self, widget, room_jid, jid):
		"""grant membership privilege to a user"""
		self.plugin.send('GC_SET_AFFILIATION', self.account, (room_jid, jid, \
			'member'))

	def revoke_membership(self, widget, room_jid, jid):
		"""revoke membership privilege to a user"""
		self.plugin.send('GC_SET_AFFILIATION', self.account, (room_jid, jid, \
			'none'))

	def grant_admin(self, widget, room_jid, jid):
		"""grant administrative privilege to a user"""
		self.plugin.send('GC_SET_AFFILIATION', self.account, (room_jid, jid, \
			'admin'))

	def revoke_admin(self, widget, room_jid, jid):
		"""revoke administrative privilege to a user"""
		self.plugin.send('GC_SET_AFFILIATION', self.account, (room_jid, jid, \
			'member'))

	def grant_owner(self, widget, room_jid, jid):
		"""grant owner privilege to a user"""
		self.plugin.send('GC_SET_AFFILIATION', self.account, (room_jid, jid, \
			'owner'))

	def revoke_owner(self, widget, room_jid, jid):
		"""revoke owner privilege to a user"""
		self.plugin.send('GC_SET_AFFILIATION', self.account, (room_jid, jid, \
			'admin'))

	def on_info(self, widget, jid):
		"""Call vcard_information_window class to display user's information"""
		if not self.plugin.windows[self.account]['infos'].has_key(jid):
			self.plugin.windows[self.account]['infos'][jid] = \
				vcard_information_window(jid, self.plugin, self.account, True)
			self.plugin.send('ASK_VCARD', self.account, jid)

	def mk_menu(self, room_jid, event, iter):
		"""Make user's popup menu"""
		model = self.list_treeview[room_jid].get_model()
		nick = model.get_value(iter, 1)
		jid = model.get_value(iter, 2)
		
		menu = gtk.Menu()
		item = gtk.MenuItem(_('Privileges'))
		menu.append(item)
		
		sub_menu = gtk.Menu()
		item.set_submenu(sub_menu)
		item = gtk.MenuItem(_('Kick'))
		sub_menu.append(item)
		item.connect('activate', self.kick, room_jid, nick)
		item = gtk.MenuItem(_('Grant voice'))
		sub_menu.append(item)
		item.connect('activate', self.grant_voice, room_jid, nick)
		item = gtk.MenuItem(_('Revoke voice'))
		sub_menu.append(item)
		item.connect('activate', self.revoke_voice, room_jid, nick)
		item = gtk.MenuItem(_('Grant moderator'))
		sub_menu.append(item)
		item.connect('activate', self.grant_moderator, room_jid, nick)
		item = gtk.MenuItem(_('Revoke moderator'))
		sub_menu.append(item)
		item.connect('activate', self.revoke_moderator, room_jid, nick)
		if jid:
			item = gtk.MenuItem()
			sub_menu.append(item)

			item = gtk.MenuItem(_('Ban'))
			sub_menu.append(item)
			item.connect('activate', self.ban, room_jid, jid)
			item = gtk.MenuItem(_('Grant membership'))
			sub_menu.append(item)
			item.connect('activate', self.grant_membership, room_jid, jid)
			item = gtk.MenuItem(_('Revoke membership'))
			sub_menu.append(item)
			item.connect('activate', self.revoke_membership, room_jid, jid)
			item = gtk.MenuItem(_('Grant admin'))
			sub_menu.append(item)
			item.connect('activate', self.grant_admin, room_jid, jid)
			item = gtk.MenuItem(_('Revoke admin'))
			sub_menu.append(item)
			item.connect('activate', self.revoke_admin, room_jid, jid)
			item = gtk.MenuItem(_('Grant owner'))
			sub_menu.append(item)
			item.connect('activate', self.grant_owner, room_jid, jid)
			item = gtk.MenuItem(_('Revoke owner'))
			sub_menu.append(item)
			item.connect('activate', self.revoke_owner, room_jid, jid)

			item = gtk.MenuItem()
			menu.append(item)

			item = gtk.MenuItem(_('Information'))
			menu.append(item)
			item.connect('activate', self.on_info, jid)
		
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def on_groupchat_window_focus_in_event(self, widget, event):
		"""When window get focus"""
		room_jid = self.get_active_jid()
		if self.nb_unread[room_jid] > 0:
			self.nb_unread[room_jid] = 0
			self.redraw_tab(room_jid)
			self.show_title()
			self.plugin.systray.remove_jid(room_jid, self.account)

	def on_chat_notebook_switch_page(self, notebook, page, page_num):
		new_child = notebook.get_nth_page(page_num)
		new_jid = ''
		for room_jid in self.xmls:
			child = self.xmls[room_jid].get_widget('group_vbox')
			if child == new_child:
				new_jid = room_jid
				break
		self.xml.get_widget('subject_entry').set_text(self.subjects[new_jid])
		if self.nb_unread[new_jid] > 0:
			self.nb_unread[new_jid] = 0
			self.redraw_tab(new_jid)
			self.show_title()
			self.plugin.systray.remove_jid(new_jid, self.account)

	def active_tab(self, room_jid):
		child = self.xmls[room_jid].get_widget('group_vbox')
		self.chat_notebook.set_current_page(self.chat_notebook.page_num(child))
		self.xmls[room_jid].get_widget('message_textview').grab_focus()

	def remove_tab(self, room_jid):
		if time.time() - self.last_message_time[room_jid] < 2:
			dialog = Confirmation_dialog(_('You received a message in the room %s in the last two seconds.\nDo you still want to close this tab ?') % \
				room_jid.split('@')[0])
			if dialog.get_response() != gtk.RESPONSE_YES:
				return
		if len(self.xmls) == 1:
			self.window.destroy()
		else:
			self.plugin.send('GC_STATUS', self.account, (self.nicks[room_jid], \
				room_jid, 'offline', 'offline'))
			self.chat_notebook.remove_page(self.chat_notebook.get_current_page())
			del self.plugin.windows[self.account]['gc'][room_jid]
			del self.nicks[room_jid]
			del self.nb_unread[room_jid]
			del self.last_message_time[room_jid]
			del self.xmls[room_jid]
			del self.tagIn[room_jid]
			del self.tagInBold[room_jid]
			del self.tagOut[room_jid]
			del self.tagStatus[room_jid]
			del self.list_treeview[room_jid]
			del self.subjects[room_jid]
			if len(self.xmls) == 1:
				self.chat_notebook.set_show_tabs(False)
			self.show_title()

	def new_group(self, room_jid, nick):
		self.nb_unread[room_jid] = 0
		self.last_message_time[room_jid] = 0
		self.nicks[room_jid] = nick
		self.subjects[room_jid] = ''
		self.xmls[room_jid] = gtk.glade.XML(GTKGUI_GLADE, 'group_vbox', APP)
		self.list_treeview[room_jid] = self.xmls[room_jid].\
			get_widget('list_treeview')

		#status_image, nickname, real_jid
		store = gtk.TreeStore(gtk.Image, str, str)
		column = gtk.TreeViewColumn('contacts')
		render_text = ImageCellRenderer()
		column.pack_start(render_text, expand = False)
		column.add_attribute(render_text, 'image', 0)
		render_text = gtk.CellRendererText()
		column.pack_start(render_text, expand = True)
		column.add_attribute(render_text, 'text', 1)

		self.list_treeview[room_jid].append_column(column)
		self.list_treeview[room_jid].set_model(store)

		column = gtk.TreeViewColumn()
		render = gtk.CellRendererPixbuf()
		column.pack_start(render, expand = False)
		self.list_treeview[room_jid].append_column(column)
		column.set_visible(False)
		self.list_treeview[room_jid].set_expander_column(column)

		conversation_textview = self.xmls[room_jid].\
			get_widget('conversation_textview')
		conversation_buffer = conversation_textview.get_buffer()
		end_iter = conversation_buffer.get_end_iter()
		conversation_buffer.create_mark('end', end_iter, 0)
		self.tagIn[room_jid] = conversation_buffer.create_tag('incoming')
		# (nk) what is this?
		self.tagInBold[room_jid] = conversation_buffer.create_tag('incoming_bold')
		color = self.plugin.config['inmsgcolor']
		self.tagIn[room_jid].set_property('foreground', color)
		self.tagInBold[room_jid].set_property('foreground', color)
		self.tagInBold[room_jid].set_property('weight', 700)
		self.tagOut[room_jid] = conversation_buffer.create_tag('outgoing')
		color = self.plugin.config['outmsgcolor']
		self.tagOut[room_jid].set_property('foreground', color)
		self.tagStatus[room_jid] = conversation_buffer.create_tag('status')
		color = self.plugin.config['statusmsgcolor']
		self.tagStatus[room_jid].set_property('foreground', color)

		self.xmls[room_jid].signal_autoconnect(self)

		self.chat_notebook.append_page(self.xmls[room_jid].\
			get_widget('group_vbox'))
		if len(self.xmls) > 1:
			self.chat_notebook.set_show_tabs(True)

		self.redraw_tab(room_jid)
		self.show_title()

	def on_list_treeview_button_press_event(self, widget, event):
		"""popup user's group's or agent menu"""
		if event.type == gtk.gdk.BUTTON_PRESS:
			if event.button == 3:
				try:
					path, column, x, y = widget.get_path_at_pos(int(event.x), \
						int(event.y))
				except TypeError:
					widget.get_selection().unselect_all()
					return False
				model = widget.get_model()
				iter = model.get_iter(path)
				if len(path) == 2:
					room_jid = self.get_active_jid()
					self.mk_menu(room_jid, event, iter)
				return True
			if event.button == 1:
				try:
					path, column, x, y = widget.get_path_at_pos(int(event.x), \
						int(event.y))
				except TypeError:
					widget.get_selection().unselect_all()
		return False

	def on_list_treeview_key_release_event(self, widget, event):
		if event.type == gtk.gdk.KEY_RELEASE:
			if event.keyval == gtk.keysyms.Escape:
				widget.get_selection().unselect_all()
		return False

	def on_list_treeview_row_activated(self, widget, path, col=0):
		"""When an iter is dubble clicked :
		open the chat window"""
		model = widget.get_model()
		iter = model.get_iter(path)
		if len(path) == 1:
			if (widget.row_expanded(path)):
				widget.collapse_row(path)
			else:
				widget.expand_row(path, False)

	def on_list_treeview_row_expanded(self, widget, iter, path):
		"""When a row is expanded :
		change the icon of the arrow"""
		model = widget.get_model()
		model.set_value(iter, 0, self.plugin.roster.pixbufs['opened'])
	
	def on_list_treeview_row_collapsed(self, widget, iter, path):
		"""When a row is collapsed :
		change the icon of the arrow"""
		model = widget.get_model()
		model.set_value(iter, 0, self.plugin.roster.pixbufs['closed'])

	def __init__(self, room_jid, nick, plugin, account):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'groupchat_window', APP)
		self.chat_notebook = self.xml.get_widget('chat_notebook')
		self.chat_notebook.remove_page(0)
		self.plugin = plugin
		self.account = account
		self.xmls = {}
		self.tagIn = {}
		self.tagInBold = {}
		self.tagOut = {}
		self.tagStatus = {}
		self.nicks = {}
		self.nb_unread = {}
		self.last_message_time = {}
		self.list_treeview = {}
		self.subjects = {}
		self.window = self.xml.get_widget('groupchat_window')
		self.new_group(room_jid, nick)
		self.show_title()
		self.xml.signal_connect('on_groupchat_window_destroy', \
			self.on_groupchat_window_destroy)
		self.xml.signal_connect('on_groupchat_window_delete_event', \
			self.on_groupchat_window_delete_event)
		self.xml.signal_connect('on_groupchat_window_focus_in_event', \
			self.on_groupchat_window_focus_in_event)
		self.xml.signal_connect('on_groupchat_window_key_press_event', \
			self.on_groupchat_window_key_press_event)
		self.xml.signal_connect('on_chat_notebook_switch_page', \
			self.on_chat_notebook_switch_page)
		self.xml.signal_connect('on_set_button_clicked', \
			self.on_set_button_clicked)
