#!/usr/bin/env python
##	plugins/gtkgui.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@tuxfamily.org>
##
##	Copyright (C) 2003 Gajim Team
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

import pygtk
pygtk.require('2.0')
import gtk
from gtk import TRUE, FALSE
import trayicon
import gtk.glade,gobject
import os,string,time,Queue
import common.optparser,common.sleepy
from common import i18n
_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

from config import *
from dialogs import *

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'

class user:
	"""Informations concerning each users"""
	def __init__(self, *args):
		if len(args) == 0:
			self.jid = ''
			self.name = ''
			self.groups = []
			self.show = ''
			self.status = ''
			self.sub = ''
			self.resource = ''
			self.priority = 0
		elif len(args) == 8:
			self.jid = args[0]
			self.name = args[1]
			self.groups = args[2]
			self.show = args[3]
			self.status = args[4]
			self.sub = args[5]
			self.resource = args[6]
			self.priority = args[7]
		else: raise TypeError, _('bad arguments')


class message_Window:
	"""Class for chat window"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows[self.account]['chats'][self.user.jid]
	
	def print_conversation(self, txt, contact = None, tim = None):
		"""Print a line in the conversation :
		if contact is set to status : it's a status message
		if contact is set to another value : it's an outgoing message
		if contact is not set : it's an incomming message"""
		conversation = self.xml.get_widget('conversation')
		buffer = conversation.get_buffer()
		if not txt:
			txt = ""
		end_iter = buffer.get_end_iter()
		if not tim:
			tim = time.strftime("[%H:%M:%S]")
		buffer.insert(end_iter, tim)
		if contact:
			if contact == 'status':
				buffer.insert_with_tags_by_name(end_iter, txt+'\n', \
					'status')
			else:
				buffer.insert_with_tags_by_name(end_iter, '<'+self.plugin.nicks[self.account]+'> ', 'outgoing')
				buffer.insert(end_iter, txt+'\n')
		else:
			buffer.insert_with_tags_by_name(end_iter, '<' + \
				self.user.name + '> ', 'incoming')
			buffer.insert(end_iter, txt+'\n')
		#scroll to the end of the textview
		conversation.scroll_to_mark(buffer.get_mark('end'), 0.1, 0, 0, 0)
	
	def read_queue(self, q):
		"""read queue and print messages containted in it"""
		while not q.empty():
			evt = q.get()
			self.print_conversation(evt[0], tim = evt[1])
		del self.plugin.queues[self.account][self.user.jid]
		self.plugin.roster.redraw_jid(self.user.jid, self.account)
		self.plugin.systray.remove_jid(self.user.jid, self.account)
		showOffline = self.plugin.config['showoffline']
		if (self.user.show == 'offline' or self.user.show == 'error') and \
			not showOffline:
			if len(self.plugin.roster.contacts[self.account][self.user.jid]) == 1:
				self.plugin.roster.remove_user(self.user, self.account)

	def on_msg_key_press_event(self, widget, event):
		"""When a key is pressed :
		if enter is pressed without the shit key, message (if not empty) is sent
		and printed in the conversation"""
		if event.keyval == gtk.keysyms.Return:
			if (event.state & gtk.gdk.SHIFT_MASK):
				return 0
			txt_buffer = widget.get_buffer()
			start_iter = txt_buffer.get_start_iter()
			end_iter = txt_buffer.get_end_iter()
			txt = txt_buffer.get_text(start_iter, end_iter, 0)
			if txt != '':
				self.plugin.send('MSG', self.account, (self.user.jid, txt))
				txt_buffer.set_text('', -1)
				self.print_conversation(txt, self.user.jid)
				widget.grab_focus()
			return 1
		return 0

	def on_clear(self, widget):
		"""When clear button is pressed :
		clear the conversation"""
		buffer = self.xml.get_widget('conversation').get_buffer()
		deb, end = buffer.get_bounds()
		buffer.delete(deb, end)

	def on_history(self, widget):
		"""When history button is pressed : call log window"""
		if not self.plugin.windows['logs'].has_key(self.user.jid):
			self.plugin.windows['logs'][self.user.jid] = log_Window(self.plugin, self.user.jid)

	def on_focus(self, widget, event):
		"""When window get focus"""
		self.plugin.systray.remove_jid(self.user.jid, self.account)
	
	def __init__(self, user, plugin, account):
		self.user = user
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Chat', APP)
		self.window = self.xml.get_widget('Chat')
#		hbox = xml.get_widget('hbox1')
#		hbox.set_property('resize-mode', 2)
		self.window.set_title('Chat with ' + user.name)
		self.img = self.xml.get_widget('image')
		self.img.set_from_pixbuf(self.plugin.roster.pixbufs[user.show])
		self.xml.get_widget('button_contact').set_label(user.name + ' <'\
			+ user.jid + '>')
		self.xml.get_widget('button_contact').set_resize_mode(gtk.RESIZE_QUEUE)
		message = self.xml.get_widget('message')
		message.grab_focus()
		conversation = self.xml.get_widget('conversation')
		buffer = conversation.get_buffer()
		end_iter = buffer.get_end_iter()
		buffer.create_mark('end', end_iter, 0)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_clear_clicked', self.on_clear)
		self.xml.signal_connect('on_focus', self.on_focus)
		self.xml.signal_connect('on_history_clicked', self.on_history)
		self.xml.signal_connect('on_msg_key_press_event', \
			self.on_msg_key_press_event)
		self.tagIn = buffer.create_tag("incoming")
		color = self.plugin.config['inmsgcolor']
		if not color:
			color = 'red'
		self.tagIn.set_property("foreground", color)
		self.tagOut = buffer.create_tag("outgoing")
		color = self.plugin.config['outmsgcolor']
		if not color:
			color = 'blue'
		self.tagOut.set_property("foreground", color)
		self.tagStatus = buffer.create_tag("status")
		color = self.plugin.config['statusmsgcolor']
		if not color:
			color = 'green'
		self.tagStatus.set_property("foreground", color)
		#print queued messages
		if plugin.queues[account].has_key(user.jid):
			self.read_queue(plugin.queues[account][user.jid])

class log_Window:
	"""Class for bowser agent window :
	to know the agents on the selected server"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['logs'][self.jid]

	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

	def on_earliest(self, widget):
		buffer = self.xml.get_widget('textview').get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)
		self.xml.get_widget('earliest_button').set_sensitive(False)
		self.xml.get_widget('previous_button').set_sensitive(False)
		self.xml.get_widget('forward_button').set_sensitive(True)
		self.xml.get_widget('latest_button').set_sensitive(True)
		end = 50
		if end > self.nb_line:
			end = self.nb_line
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, 0, end))
		self.num_begin = self.nb_line

	def on_previous(self, widget):
		buffer = self.xml.get_widget('textview').get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)
		self.xml.get_widget('earliest_button').set_sensitive(True)
		self.xml.get_widget('previous_button').set_sensitive(True)
		self.xml.get_widget('forward_button').set_sensitive(True)
		self.xml.get_widget('latest_button').set_sensitive(True)
		begin = self.num_begin - 50
		if begin < 0:
			begin = 0
		end = begin + 50
		if end > self.nb_line:
			end = self.nb_line
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, begin, end))
		self.num_begin = self.nb_line

	def on_forward(self, widget):
		buffer = self.xml.get_widget('textview').get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)
		self.xml.get_widget('earliest_button').set_sensitive(True)
		self.xml.get_widget('previous_button').set_sensitive(True)
		self.xml.get_widget('forward_button').set_sensitive(True)
		self.xml.get_widget('latest_button').set_sensitive(True)
		begin = self.num_begin + 50
		if begin > self.nb_line:
			begin = self.nb_line
		end = begin + 50
		if end > self.nb_line:
			end = self.nb_line
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, begin, end))
		self.num_begin = self.nb_line

	def on_latest(self, widget):
		buffer = self.xml.get_widget('textview').get_buffer()
		start, end = buffer.get_bounds()
		buffer.delete(start, end)
		self.xml.get_widget('earliest_button').set_sensitive(True)
		self.xml.get_widget('previous_button').set_sensitive(True)
		self.xml.get_widget('forward_button').set_sensitive(False)
		self.xml.get_widget('latest_button').set_sensitive(False)
		begin = self.nb_line - 50
		if begin < 0:
			begin = 0
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, begin, self.nb_line))
		self.num_begin = self.nb_line

	def new_line(self, infos):
		"""write a new line"""
		#infos = [num_line, date, type, data]
		if infos[0] < self.num_begin:
			self.num_begin = infos[0]
		if infos[0] == 0:
			self.xml.get_widget('earliest_button').set_sensitive(False)
			self.xml.get_widget('previous_button').set_sensitive(False)
		if infos[0] == self.nb_line:
			self.xml.get_widget('forward_button').set_sensitive(False)
			self.xml.get_widget('latest_button').set_sensitive(False)
		buffer = self.xml.get_widget('textview').get_buffer()
		start_iter = buffer.get_start_iter()
		end_iter = buffer.get_end_iter()
		tim = time.strftime("[%x %X] ", time.localtime(float(infos[1])))
		buffer.insert(start_iter, tim)
		if infos[2] == 'recv':
			msg = string.join(infos[3][0:], ':')
			msg = string.replace(msg, '\\n', '\n')
			buffer.insert_with_tags_by_name(start_iter, msg, 'incoming')
		elif infos[2] == 'sent':
			msg = string.join(infos[3][0:], ':')
			msg = string.replace(msg, '\\n', '\n')
			buffer.insert_with_tags_by_name(start_iter, msg, 'outgoing')
		else:
			msg = string.join(infos[3][1:], ':')
			msg = string.replace(msg, '\\n', '\n')
			buffer.insert_with_tags_by_name(start_iter, _('Status is now : ') + \
				infos[3][0]+' : ' + msg, 'status')
	
	def set_nb_line(self, nb_line):
		self.nb_line = nb_line
		self.num_begin = nb_line

	def __init__(self, plugin, jid):
		self.plugin = plugin
		self.jid = jid
		self.nb_line = 0
		self.num_begin = 0
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Log', APP)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_close_clicked', self.on_close)
		self.xml.signal_connect('on_earliest_clicked', self.on_earliest)
		self.xml.signal_connect('on_previous_clicked', self.on_previous)
		self.xml.signal_connect('on_forward_clicked', self.on_forward)
		self.xml.signal_connect('on_latest_clicked', self.on_latest)
		buffer = self.xml.get_widget('textview').get_buffer()
		tagIn = buffer.create_tag("incoming")
		color = self.plugin.config['inmsgcolor']
		if not color:
			color = 'red'
		tagIn.set_property("foreground", color)
		tagOut = buffer.create_tag("outgoing")
		color = self.plugin.config['outmsgcolor']
		if not color:
			color = 'blue'
		tagOut.set_property("foreground", color)
		tagStatus = buffer.create_tag("status")
		color = self.plugin.config['statusmsgcolor']
		if not color:
			color = 'green'
		tagStatus.set_property("foreground", color)
		self.plugin.send('LOG_NB_LINE', None, jid)

class roster_Window:
	"""Class for main gtk window"""

	def get_account_iter(self, name):
		model = self.tree.get_model()
		fin = False
		account = model.get_iter_root()
		if not account:
			return None
		while not fin:
			account_name = model.get_value(account, 3)
			if name == account_name:
				return account
			account = model.iter_next(account)
			if not account:
				fin = True
		return None

	def get_group_iter(self, name, account):
		model = self.tree.get_model()
		root = self.get_account_iter(account)
		fin = False
		group = model.iter_children(root)
		if not group:
			fin = True
		while not fin:
			group_name = model.get_value(group, 3)
			if name == group_name:
				return group
			group = model.iter_next(group)
			if not group:
				fin = True
		return None

	def get_user_iter(self, jid, account):
		model = self.tree.get_model()
		acct = self.get_account_iter(account)
		found = []
		fin = False
		group = model.iter_children(acct)
		if not group:
			return found
		while not fin:
			fin2 = False
			user = model.iter_children(group)
			if not user:
				fin2=True
			while not fin2:
				if jid == model.get_value(user, 3):
					found.append(user)
				user = model.iter_next(user)
				if not user:
					fin2 = True
			group = model.iter_next(group)
			if not group:
				fin = True
		return found

	def add_account_to_roster(self, account):
		model = self.tree.get_model()
		if self.get_account_iter(account):
			return
		statuss = ['offline', 'online', 'away', 'xa', 'dnd', 'invisible']
		status = statuss[self.plugin.connected[account]]
		model.append(None, (self.pixbufs[status], account, 'account', account,\
			FALSE))

	def add_user_to_roster(self, jid, account):
		"""Add a user to the roster and add groups if they aren't in roster"""
		showOffline = self.plugin.config['showoffline']
		if not self.contacts[account].has_key(jid):
			return
		users = self.contacts[account][jid]
		user = users[0]
#		else:
#			resources = []
#			for u in self.contacts[account][user.jid]:
#				resources.append(u.resource)
#			if resources == ['']:
#				self.contacts[account][user.jid][0].resource = user.resource
#			else:
#				if not user.resource in resources:
#					self.contacts[account][user.jid].append(user)
		if user.groups == []:
			if string.find(user.jid, "@") <= 0:
				user.groups.append('Agents')
			else:
				user.groups.append('general')

		if (user.show == 'offline' or user.show == 'error') and not showOffline\
			and not 'Agents' in user.groups and \
			not self.plugin.queues[account].has_key(user.jid):
			return

		model = self.tree.get_model()
		for g in user.groups:
			iterG = self.get_group_iter(g, account)
			if not iterG:
				IterAcct = self.get_account_iter(account)
				iterG = model.append(IterAcct, \
					(self.pixbufs['closed'], g, 'group', \
					g, FALSE))
			if not self.groups[account].has_key(g):
				self.groups[account][g] = {'expand': True}
			self.tree.expand_row((model.get_path(iterG)[0]), False)

			typestr = 'user'
			if g == 'Agents':
				typestr = 'agent'

			model.append(iterG, (self.pixbufs[user.show], \
				user.name, typestr, user.jid, False))
			
			if self.groups[account][g]['expand']:
				self.tree.expand_row(model.get_path(iterG), False)
		self.redraw_jid(jid, account)
	
	def remove_user(self, user, account):
		"""Remove a user from the roster"""
		model = self.tree.get_model()
		for i in self.get_user_iter(user.jid, account):
			parent_i = model.iter_parent(i)
			model.remove(i)
			if model.iter_n_children(parent_i) == 0:
				model.remove(parent_i)

	def update_anim(self, iteration, iter, jid, account):
		"""Update animation in the treeview"""
		if not self.plugin.queues[account].has_key(jid):
			return
		model = self.tree.get_model()
		iteration.advance()
		pix = iteration.get_pixbuf()
		model.set_value(iter, 0, pix)
		gobject.timeout_add(iteration.get_delay_time(), self.update_anim, \
			iteration, iter, jid, account)

	def redraw_jid(self, jid, account):
		"""draw the correct pixbuf and name"""
		model = self.tree.get_model()
		iters = self.get_user_iter(jid, account)
		if len(iters) == 0:
			return
		users = self.contacts[account][jid]
		name = users[0].name
		if len(users) > 1:
			name += " (" + str(len(users)) + ")"
		prio = 0
		show = users[0].show
		for u in users:
			if u.priority > prio:
				prio = u.priority
				show = u.show
		for iter in iters:
			if self.plugin.queues[account].has_key(jid):
				pix = self.pixbufs['message']
			else:
				pix = self.pixbufs[show]
			if isinstance(pix, gtk.gdk.PixbufAnimation):
				iteration = pix.get_iter()
				pix = iteration.get_pixbuf()
				gobject.timeout_add(iteration.get_delay_time(), self.update_anim, \
					iteration, iter, jid, account)
			model.set_value(iter, 0, pix)
			model.set_value(iter, 1, name)
	
	def mkmenu(self):
		"""create the browse agents and add sub menus"""
		if len(self.plugin.accounts.keys()) > 0:
			self.xml.get_widget('add').set_sensitive(True)
			self.xml.get_widget('browse_agents').set_sensitive(True)
		else:
			self.xml.get_widget('add').set_sensitive(False)
			self.xml.get_widget('browse_agents').set_sensitive(False)
		if len(self.plugin.accounts.keys()) > 1:
			#add
			menu_sub = gtk.Menu()
			self.xml.get_widget('add').set_submenu(menu_sub)
			for a in self.plugin.accounts.keys():
				item = gtk.MenuItem(a)
				menu_sub.append(item)
				item.connect("activate", self.on_add, a)
			menu_sub.show_all()
			#agents
			menu_sub = gtk.Menu()
			self.xml.get_widget('browse_agents').set_submenu(menu_sub)
			for a in self.plugin.accounts.keys():
				item = gtk.MenuItem(a)
				menu_sub.append(item)
				item.connect("activate", self.on_browse, a)
			menu_sub.show_all()
		elif len(self.plugin.accounts.keys()) == 1:
			#add
			self.xml.get_widget('add').connect("activate", self.on_add, \
				self.plugin.accounts.keys()[0])
			#agents
			self.xml.get_widget('browse_agents').connect("activate", \
				self.on_browse, self.plugin.accounts.keys()[0])

	def draw_roster(self):
		"""Clear and draw roster"""
		self.mkmenu()
		self.tree.get_model().clear()
		for acct in self.contacts.keys():
			self.add_account_to_roster(acct)
			for jid in self.contacts[acct].keys():
				self.add_user_to_roster(jid, acct)
	
	def mklists(self, array, account):
		"""fill self.contacts and self.groups"""
		if not self.contacts.has_key(account):
			self.contacts[account] = {}
		if not self.groups.has_key(account):
			self.groups[account] = {}
		for jid in array.keys():
			jids = string.split(jid, '/')
			#get jid
			ji = jids[0]
			#get resource
			resource = ''
			if len(jids) > 1:
				resource = jids[1:]
			#get name
			name = array[jid]['name']
			if not name:
				if string.find(ji, "@") <= 0:
					name = ji
				else:
					name = string.split(jid, '@')[0]
			#get show
			show = array[jid]['show']
			if not show:
				show = 'offline'

			user1 = user(ji, name, array[jid]['groups'], show, \
				array[jid]['status'], array[jid]['sub'], resource, 0)
			#when we draw the roster, we can't have twice the same user with 
			# 2 resources
			self.contacts[account][ji] = [user1]
			for g in array[jid]['groups'] :
				if not g in self.groups[account].keys():
					self.groups[account][g] = {'expand':True}

	def chg_user_status(self, user, show, status, account):
		"""When a user change his status"""
		showOffline = self.plugin.config['showoffline']
		model = self.tree.get_model()
		if (show == 'offline' or show == 'error') and not showOffline and \
			not self.plugin.queues[account].has_key(user.jid):
			if len(self.contacts[account][user.jid]) > 1:
				luser = self.contacts[account][user.jid]
				for u in luser:
					if u.resource == user.resource:
						luser.remove(u)
						self.redraw_jid(user.jid, account)
						break
			else:
				self.remove_user(user, account)
				iters = []
		else:
			if not self.get_user_iter(user.jid, account):
				self.add_user_to_roster(user.jid, account)
			self.redraw_jid(user.jid, account)
		for u in self.contacts[account][user.jid]:
			if u.resource == user.resource:
				u.show = show
				u.status = status
				break
		#Print status in chat window
		if self.plugin.windows[account]['chats'].has_key(user.jid):
			#TODO: should show pibuf of the prioritest resource
			if len(self.contacts[account][user.jid]) < 2:
				self.plugin.windows[account]['chats'][user.jid].\
					img.set_from_pixbuf(self.pixbufs[show])
			name = user.name
			if user.resource != '':
				name += '/'+user.resource
			self.plugin.windows[account]['chats'][user.jid].print_conversation(\
				_("%s is now %s (%s)") % (name, show, status), 'status')

	def on_info(self, widget, user, account):
		"""Call infoUser_Window class to display user's information"""
		if not self.plugin.windows[account]['infos'].has_key(user.jid):
			self.plugin.windows[account]['infos'][user.jid] = \
				infoUser_Window(user, self.plugin, account)

	def on_agent_logging(self, widget, jid, state, account):
		"""When an agent is requested to log in or off"""
		self.plugin.send('AGENT_LOGGING', account, (jid, state))

	def on_rename(self, widget, iter, path, user):
		model = self.tree.get_model()
		model.set_value(iter, 1, user.name)
		model.set_value(iter, 4, True)
		self.tree.set_cursor(path, self.tree.get_column(0), True)
		
	def on_history(self, widget, user):
		"""When history button is pressed : call log window"""
		if not self.plugin.windows['logs'].has_key(user.jid):
			self.plugin.windows['logs'][user.jid] = log_Window(self.plugin, \
				user.jid)
	
	def mk_menu_user(self, event, iter):
		"""Make user's popup menu"""
		model = self.tree.get_model()
		jid = model.get_value(iter, 3)
		path = model.get_path(iter)
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		user = self.contacts[account][jid][0]
		
		menu = gtk.Menu()
		item = gtk.MenuItem(_("Start chat"))
		menu.append(item)
		item.connect("activate", self.on_row_activated, path)
		item = gtk.MenuItem(_("Rename"))
		menu.append(item)
		item.connect("activate", self.on_rename, iter, path, user)
		item = gtk.MenuItem()
		menu.append(item)
		item = gtk.MenuItem(_("Subscription"))
		menu.append(item)
		
		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem(_("Resend authorization to"))
		menu_sub.append(item)
		item.connect("activate", self.authorize, jid, account)
		item = gtk.MenuItem(_("Rerequest authorization from"))
		menu_sub.append(item)
		item.connect("activate", self.req_sub, jid, \
			_('I would like to add you to my contact list, please.'), account)
		
		item = gtk.MenuItem()
		menu.append(item)
		item = gtk.MenuItem(_("Remove"))
		menu.append(item)
		item.connect("activate", self.on_req_usub, user, account)

		item = gtk.MenuItem()
		menu.append(item)
		item = gtk.MenuItem(_("Informations"))
		menu.append(item)
		item.connect("activate", self.on_info, user, account)
		item = gtk.MenuItem(_("History"))
		menu.append(item)
		item.connect("activate", self.on_history, user)

		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def mk_menu_g(self, event):
		"""Make group's popup menu"""
		menu = gtk.Menu()
		item = gtk.MenuItem(_("grp1"))
#		menu.append(item)
		item = gtk.MenuItem(_("grp2"))
#		menu.append(item)
		item = gtk.MenuItem(_("grp3"))
#		menu.append(item)
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()
	
	def mk_menu_agent(self, event, iter):
		"""Make agent's popup menu"""
		model = self.tree.get_model()
		jid = model.get_value(iter, 3)
		path = model.get_path(iter)
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		menu = gtk.Menu()
		item = gtk.MenuItem(_("Log on"))
		if self.contacts[account][jid][0].show != 'offline':
			item.set_sensitive(FALSE)
		menu.append(item)
		item.connect("activate", self.on_agent_logging, jid, 'available', account)

		item = gtk.MenuItem(_("Log off"))
		if self.contacts[account][jid][0].show == 'offline':
			item.set_sensitive(FALSE)
		menu.append(item)
		item.connect("activate", self.on_agent_logging, jid, 'unavailable', account)

		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def on_edit_account(self, widget, account):
		if not self.plugin.windows.has_key('accountPreference'):
			infos = {}
			infos['name'] = account
			if self.plugin.accounts[account].has_key("name"):
				infos['jid'] = self.plugin.accounts[account]["name"] + \
					'@' +  self.plugin.accounts[account]["hostname"]
			if self.plugin.accounts[account].has_key("password"):
				infos['password'] = self.plugin.accounts[account]["password"]
			if self.plugin.accounts[account].has_key("ressource"):
				infos['ressource'] = self.plugin.accounts[account]["ressource"]
			if self.plugin.accounts[account].has_key("priority"):
				infos['priority'] = self.plugin.accounts[account]["priority"]
			if self.plugin.accounts[account].has_key("use_proxy"):
				infos['use_proxy'] = self.plugin.accounts[account]["use_proxy"]
			if self.plugin.accounts[account].has_key("proxyhost"):
				infos['proxyhost'] = self.plugin.accounts[account]["proxyhost"]
			if self.plugin.accounts[account].has_key("proxyport"):
				infos['proxyport'] = self.plugin.accounts[account]["proxyport"]
			self.plugin.windows['accountPreference'] = \
				accountPreference_Window(self.plugin, infos)

	def mk_menu_account(self, event, iter):
		"""Make account's popup menu"""
		model = self.tree.get_model()
		account = model.get_value(iter, 3)
		
		menu = gtk.Menu()
		item = gtk.MenuItem(_("Status"))
		menu.append(item)
		
		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem(_("Online"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'online')
		item = gtk.MenuItem(_("Away"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'away')
		item = gtk.MenuItem(_("NA"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'xa')
		item = gtk.MenuItem(_("DND"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'dnd')
		item = gtk.MenuItem(_("Invisible"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'invisible')
		item = gtk.MenuItem()
		menu_sub.append(item)
		item = gtk.MenuItem(_("Offline"))
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'offline')
		
		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem(_("Edit account"))
		menu.append(item)
		item.connect("activate", self.on_edit_account, account)
		
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()
	
	def authorize(self, widget, jid, account):
		"""Authorize a user"""
		self.plugin.send('AUTH', account, jid)

	def req_sub(self, widget, jid, txt, account):
		"""Request subscription to a user"""
		self.plugin.send('SUB', account, (jid, txt))
		if not self.contacts[account].has_key(jid):
			user1 = user(jid, jid, ['general'], 'requested', \
				'requested', 'sub', '', 0)
			self.contacts[account][jid] = [user1]
			self.add_user_to_roster(jid, account)
	
	def on_treeview_event(self, widget, event):
		"""popup user's group's or agent menu"""
		if event.type == gtk.gdk.BUTTON_PRESS:
			if event.button == 3:
				try:
					path, column, x, y = self.tree.get_path_at_pos(int(event.x), \
						int(event.y))
				except TypeError:
					self.tree.get_selection().unselect_all()
					return
				model = self.tree.get_model()
				iter = model.get_iter(path)
				type = model.get_value(iter, 2)
				if type == 'group':
					self.mk_menu_g(event)
				elif type == 'agent':
					self.mk_menu_agent(event, iter)
				elif type == 'user':
					self.mk_menu_user(event, iter)
				elif type == 'account':
					self.mk_menu_account(event, iter)
				return gtk.TRUE
			if event.button == 1:
				try:
					path, column, x, y = self.tree.get_path_at_pos(int(event.x), \
						int(event.y))
				except TypeError:
					self.tree.get_selection().unselect_all()
		if event.type == gtk.gdk.KEY_RELEASE:
			if event.keyval == gtk.keysyms.Escape:
				self.tree.get_selection().unselect_all()
		return gtk.FALSE

	def on_req_usub(self, widget, user, account):
		"""Remove a user"""
		window = confirm_Window(_("Are you sure you want to remove %s (%s) from your roster ?") % (user.name, user.jid))
		if window.wait() == gtk.RESPONSE_OK:
			self.plugin.send('UNSUB', account, user.jid)
			for u in self.contacts[account][user.jid]:
				self.remove_user(u, account)
			del self.contacts[account][u.jid]

	def change_status(self, widget, account, status):
		if status != 'online' and status != 'offline':
			w = awayMsg_Window()
			txt = w.run()
			if txt != -1:
				self.plugin.send('STATUS', account, (status, txt))
		else:
			txt = status
			self.plugin.send('STATUS', account, (status, txt))
		if status == 'online':
			self.plugin.sleeper_state[account] = 1
		else:
			self.plugin.sleeper_state[account] = 0

	def on_optionmenu_changed(self, widget):
		"""When we change our status"""
		optionmenu =  self.xml.get_widget('optionmenu')
		history = optionmenu.get_history()
		status = optionmenu.get_menu().get_children()[history].name
		if status != 'online' and status != 'offline':
			w = awayMsg_Window()
			txt = w.run()
			if txt == -1:
				self.set_optionmenu()
				return
		else:
			txt = status
		accounts = self.plugin.accounts.keys()
		if len(accounts) == 0:
			warning_Window(_("You must setup an account before connecting to jabber network."))
			return
		for acct in accounts:
			self.plugin.send('STATUS', acct, (status, txt))
			if status == 'online':
				self.plugin.sleeper_state[acct] = 1
			else:
				self.plugin.sleeper_state[acct] = 0
	
	def set_optionmenu(self):
		#table to change index in plugin.connected to index in optionmenu
		table = {0:6, 1:0, 2:1, 3:2, 4:3, 5:4}
		maxi = max(self.plugin.connected.values())
		optionmenu = self.xml.get_widget('optionmenu')
		#temporarily block signal in order not to send status that we show
		#in the optionmenu
		optionmenu.handler_block(self.id_signal_optionmenu)
		optionmenu.set_history(table[maxi])
		optionmenu.handler_unblock(self.id_signal_optionmenu)
		statuss = ['offline', 'online', 'away', 'xa', 'dnd', 'invisible']
		self.plugin.systray.set_status(statuss[maxi])

	def on_status_changed(self, account, status):
		"""the core tells us that our status has changed"""
		if not self.contacts.has_key(account):
			return
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if accountIter:
			model.set_value(accountIter, 0, self.pixbufs[status])
		statuss = ['offline', 'online', 'away', 'xa', 'dnd', 'invisible']
		if status == 'offline':
			self.plugin.sleeper = None
			for jid in self.contacts[account]:
				luser = self.contacts[account][jid]
				for user in luser:
					self.chg_user_status(user, 'offline', 'Disconnected', account)
		elif self.plugin.connected[account] == 0:
			if (self.plugin.config['autoaway'] or self.plugin.config['autoxa']):
				self.plugin.sleeper = common.sleepy.Sleepy(\
					self.plugin.config['autoawaytime']*60, \
					self.plugin.config['autoxatime']*60)
		self.plugin.connected[account] = statuss.index(status)
		self.set_optionmenu()

	def on_message(self, jid, msg, account):
		"""when we receive a message"""
		if not self.contacts[account].has_key(jid):
			user1 = user(jid, jid, ['not in list'], \
				'not in list', 'not in list', 'none', '', 0)
			self.contacts[account][jid] = [user1]
			self.add_user_to_roster(jid, account)
		iters = self.get_user_iter(jid, account)
		if iters:
			path = self.tree.get_model().get_path(iters[0])
		else:
			path = None
		autopopup = self.plugin.config['autopopup']
		autopopupaway = self.plugin.config['autopopupaway']
		if (autopopup == 0 or ( not autopopupaway and \
			self.plugin.connected[account] > 1)) and not \
			self.plugin.windows[account]['chats'].has_key(jid):
			#We save it in a queue
			if not self.plugin.queues[account].has_key(jid):
				model = self.tree.get_model()
				self.plugin.queues[account][jid] = Queue.Queue(50)
				self.redraw_jid(jid, account)
				self.plugin.systray.add_jid(jid, account)
			tim = time.strftime("[%H:%M:%S]")
			self.plugin.queues[account][jid].put((msg, tim))
			if not path:
				self.add_user_to_roster(jid, account)
				iters = self.get_user_iter(jid, account)
				path = self.tree.get_model().get_path(iters[0])
			self.tree.expand_row(path[0:1], FALSE)
			self.tree.expand_row(path[0:2], FALSE)
			self.tree.scroll_to_cell(path)
			self.tree.set_cursor(path)
		else:
			if not self.plugin.windows[account]['chats'].has_key(jid):
				self.plugin.windows[account]['chats'][jid] = \
					message_Window(self.contacts[account][jid][0], self.plugin, \
						account)
				if path:
					self.tree.expand_row(path[0:1], FALSE)
					self.tree.expand_row(path[0:2], FALSE)
					self.tree.scroll_to_cell(path)
					self.tree.set_cursor(path)
			self.plugin.windows[account]['chats'][jid].print_conversation(msg)
			if not self.plugin.windows[account]['chats'][jid].window.\
				get_property('is-active'):
				self.plugin.systray.add_jid(jid, account)

	def on_prefs(self, widget):
		"""When preferences is selected :
		call the preference_Window class"""
		if not self.plugin.windows.has_key('preferences'):
			self.plugin.windows['preferences'] = preference_Window(self.plugin)

	def on_add(self, widget, account):
		"""When add user is selected :
		call the add class"""
		addContact_Window(self.plugin, account)

	def on_about(self, widget):
		"""When about is selected :
		call the about class"""
		if not self.plugin.windows.has_key('about'):
			self.plugin.windows['about'] = about_Window(self.plugin)

	def on_accounts(self, widget):
		"""When accounts is seleted :
		call the accounts class to modify accounts"""
		if not self.plugin.windows.has_key('accounts'):
			self.plugin.windows['accounts'] = accounts_Window(self.plugin)
	
	def on_quit(self, widget):
		"""When we quit the gtk plugin :
		tell that to the core and exit gtk"""
		self.plugin.send('QUIT', None, '')
		print _("plugin gtkgui stopped")
		gtk.mainquit()

	def on_row_activated(self, widget, path, col=0):
		"""When an iter is dubble clicked :
		open the chat window"""
		model = self.tree.get_model()
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		iter = model.get_iter(path)
		type = model.get_value(iter, 2)
		jid = model.get_value(iter, 3)
		if (type == 'group') or (type == 'account'):
			if (self.tree.row_expanded(path)):
				self.tree.collapse_row(path)
			else:
				self.tree.expand_row(path, False)
		else:
			if self.plugin.windows[account]['chats'].has_key(jid):
				self.plugin.windows[account]['chats'][jid].window.present()
			elif self.contacts[account].has_key(jid):
				self.plugin.windows[account]['chats'][jid] = \
					message_Window(self.contacts[account][jid][0], self.plugin, account)

	def on_row_expanded(self, widget, iter, path):
		"""When a row is expanded :
		change the icon of the arrow"""
		model = self.tree.get_model()
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		type = model.get_value(iter, 2)
		if type == 'group':
			model.set_value(iter, 0, self.pixbufs['opened'])
			jid = model.get_value(iter, 3)
			self.groups[account][jid]['expand'] = True
		elif type == 'account':
			for g in self.groups[account]:
				groupIter = self.get_group_iter(g, account)
				if groupIter and self.groups[account][g]['expand']:
					pathG = model.get_path(groupIter)
					self.tree.expand_row(pathG, False)
			
	
	def on_row_collapsed(self, widget, iter, path):
		"""When a row is collapsed :
		change the icon of the arrow"""
		model = self.tree.get_model()
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		type = model.get_value(iter, 2)
		if type == 'group':
			model.set_value(iter, 0, self.pixbufs['closed'])
			jid = model.get_value(iter, 3)
			self.groups[account][jid]['expand'] = False

	def on_editing_canceled (self, cell):
		"""editing have been canceled"""
		#TODO: get iter
		#model.set_value(iter, 4, False)
		pass

	def on_cell_edited (self, cell, row, new_text):
		"""When an iter is editer :
		if text has changed, rename the user"""
		model = self.tree.get_model()
		iter = model.get_iter_from_string(row)
		path = model.get_path(iter)
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		jid = model.get_value(iter, 3)
		old_text = self.contacts[account][jid][0].name
		if old_text != new_text:
			for u in self.contacts[account][jid]:
				u.name = new_text
			self.plugin.send('UPDUSER', account, (jid, new_text, \
				self.contacts[account][jid][0].groups))
		model.set_value(iter, 4, False)
		self.redraw_jid(jid, account)
		
	def on_browse(self, widget, account):
		"""When browse agent is selected :
		Call browse class"""
		if not self.plugin.windows[account].has_key('browser'):
			self.plugin.windows[account]['browser'] = browseAgent_Window(self.plugin, account)

	def mkpixbufs(self):
		"""initialise pixbufs array"""
		iconstyle = self.plugin.config['iconstyle']
		if not iconstyle:
			iconstyle = 'sun'
		self.path = 'plugins/gtkgui/icons/' + iconstyle + '/'
		self.pixbufs = {}
		for state in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible', \
			'offline', 'error', 'requested', 'message', 'opened', 'closed', \
			'not in list'):
			# try to open a pixfile with the correct method
			files = []
			files.append(self.path + state + '.gif')
			files.append(self.path + state + '.png')
			files.append(self.path + state + '.xpm')
			self.pixbufs[state] = None
			for file in files:
				if not os.path.exists(file):
					continue
				fct = gtk.gdk.pixbuf_new_from_file
				if file.find('.gif') != -1:
					fct = gtk.gdk.PixbufAnimation
				pix = fct(file)
				self.pixbufs[state] = pix
				break
		for state in ('online', 'away', 'xa', 'dnd', 'invisible', 'offline'):
			image = gtk.Image()
			image.set_from_pixbuf(self.pixbufs[state])
			image.show()
			self.xml.get_widget(state).set_image(image)

	def on_show_off(self, widget):
		"""when show offline option is changed :
		redraw the treeview"""
		self.plugin.config['showoffline'] = 1 - self.plugin.config['showoffline']
		self.plugin.send('CONFIG', None, ('GtkGui', self.plugin.config))
		self.draw_roster()

	def iconCellDataFunc(self, column, renderer, model, iter, data=None):
		"""When a row is added, set properties for icon renderer"""
		if model.get_value(iter, 2) == 'account':
			renderer.set_property('cell-background', '#9fdfff')
			renderer.set_property('xalign', 0)
		elif model.get_value(iter, 2) == 'group':
			renderer.set_property('cell-background-set', False)
			renderer.set_property('xalign', 0.3)
		else:
			renderer.set_property('cell-background-set', False)
			renderer.set_property('xalign', 1)
		renderer.set_property('width', 30)
	
	def nameCellDataFunc(self, column, renderer, model, iter, data=None):
		"""When a row is added, set properties for name renderer"""
		if model.get_value(iter, 2) == 'account':
			renderer.set_property('foreground', 'red')
			renderer.set_property('cell-background', '#9fdfff')
			renderer.set_property('font', 'Normal')
			renderer.set_property('weight', 700)
			renderer.set_property('xpad', 0)
		elif model.get_value(iter, 2) == 'group':
			renderer.set_property('foreground', 'blue')
			renderer.set_property('cell-background-set', False)
			renderer.set_property('font', 'Italic')
			renderer.set_property('weight-set', False)
			renderer.set_property('xpad', 8)
		else:
			renderer.set_property('foreground-set', False)
			renderer.set_property('cell-background-set', False)
			renderer.set_property('font', 'Normal')
			renderer.set_property('weight-set', False)
			renderer.set_property('xpad', 16)

	def compareIters(self, model, iter1, iter2, data = None):
		"""Compare two iters to sort them"""
		name1 = model.get_value(iter1, 1)
		name2 = model.get_value(iter2, 1)
		if not name1 or not name2:
			return 0
		type = model.get_value(iter1, 2)
		if type == 'group':
			if name1 == 'Agents':
				return 1
			if name2 == 'Agents':
				return -1
		if name1.lower() < name2.lower():
			return -1
		if name2.lower < name1.lower():
			return 1
		return 0

	def __init__(self, plugin):
		# FIXME : handle no file ...
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Gajim', APP)
		self.tree = self.xml.get_widget('treeview')
		self.plugin = plugin
		self.groups = {}
		self.contacts = {}
		for a in self.plugin.accounts.keys():
			self.contacts[a] = {}
			self.groups[a] = {}
		#(icon, name, type, jid, editable)
		model = gtk.TreeStore(gtk.gdk.Pixbuf, str, str, str, \
			gobject.TYPE_BOOLEAN)
		model.set_sort_func(1, self.compareIters)
		model.set_sort_column_id(1, gtk.SORT_ASCENDING)
		self.tree.set_model(model)
		self.mkpixbufs()
		self.xml.get_widget('optionmenu').set_history(6)

		showOffline = self.plugin.config['showoffline']
		self.xml.get_widget('show_offline').set_active(showOffline)

		#columns
		col = gtk.TreeViewColumn()
		self.tree.append_column(col)
		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand = False)
		col.add_attribute(render_pixbuf, 'pixbuf', 0)
		col.set_cell_data_func(render_pixbuf, self.iconCellDataFunc, None)

		render_text = gtk.CellRendererText()
		render_text.connect('edited', self.on_cell_edited)
		#need gtk2.4
		#render_text.connect('editing-canceled', self.on_editing_canceled)
		col.pack_start(render_text, expand = True)
		col.add_attribute(render_text, 'text', 1)
		col.add_attribute(render_text, 'editable', 4)
		col.set_cell_data_func(render_text, self.nameCellDataFunc, None)
		
		col = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand = False)
		self.tree.append_column(col)
		col.set_visible(FALSE)
		self.tree.set_expander_column(col)

		#signals
		self.xml.signal_connect('gtk_main_quit', self.on_quit)
		self.xml.signal_connect('on_preferences_activate', self.on_prefs)
		self.xml.signal_connect('on_accounts_activate', self.on_accounts)
		self.xml.signal_connect('on_show_offline_activate', self.on_show_off)
		self.xml.signal_connect('on_about_activate', self.on_about)
		self.xml.signal_connect('on_quit_activate', self.on_quit)
		self.xml.signal_connect('on_treeview_event', self.on_treeview_event)
		self.xml.signal_connect('on_status_changed', self.on_status_changed)
		optionmenu = self.xml.get_widget('optionmenu')
		self.id_signal_optionmenu = optionmenu.connect('changed', \
			self.on_optionmenu_changed)
		self.xml.signal_connect('on_row_activated', self.on_row_activated)
		self.xml.signal_connect('on_row_expanded', self.on_row_expanded)
		self.xml.signal_connect('on_row_collapsed', self.on_row_collapsed)

		self.draw_roster()

class systray:
	"""Class for icon in the systray"""
	def set_img(self):
		if len(self.jids) > 0:
			status = 'message'
		else:
			status = self.status
		pix = self.plugin.roster.pixbufs[status]
		if isinstance(pix, gtk.gdk.PixbufAnimation):
			self.img_tray.set_from_animation(pix)
		else:
			self.img_tray.set_from_pixbuf(pix)

	def add_jid(self, jid, account):
		list = [account, jid]
		if not list in self.jids:
			self.jids.append(list)
			self.set_img()

	def remove_jid(self, jid, account):
		list = [account, jid]
		if list in self.jids:
			self.jids.remove(list)
			self.set_img()

	def set_status(self, status):
		self.status = status
		self.set_img()

	def set_optionmenu(self, widget, status):
		optionmenu = self.plugin.roster.xml.get_widget('optionmenu')
		statuss = ['online', 'away', 'xa', 'dnd', 'invisible', 'vide', 'offline']
		optionmenu.set_history(statuss.index(status))

	def start_chat(self, widget, account, jid):
		if self.plugin.windows[account]['chats'].has_key(jid):
			self.plugin.windows[account]['chats'][jid].window.present()
		elif self.plugin.roster.contacts[account].has_key(jid):
			self.plugin.windows[account]['chats'][jid] = \
				message_Window(self.plugin.roster.contacts[account][jid][0], \
				self.plugin, account)

	def mk_menu(self, event):
		menu = gtk.Menu()
		item = gtk.MenuItem(_("Status"))
		menu.append(item)

		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem(_("Online"))
		menu_sub.append(item)
		item.connect("activate", self.set_optionmenu, 'online')
		item = gtk.MenuItem(_("Away"))
		menu_sub.append(item)
		item.connect("activate", self.set_optionmenu, 'away')
		item = gtk.MenuItem(_("NA"))
		menu_sub.append(item)
		item.connect("activate", self.set_optionmenu, 'xa')
		item = gtk.MenuItem(_("DND"))
		menu_sub.append(item)
		item.connect("activate", self.set_optionmenu, 'dnd')
		item = gtk.MenuItem(_("Invisible"))
		menu_sub.append(item)
		item.connect("activate", self.set_optionmenu, 'invisible')
		item = gtk.MenuItem()
		menu_sub.append(item)
		item = gtk.MenuItem(_("Offline"))
		menu_sub.append(item)
		item.connect("activate", self.set_optionmenu, 'offline')
		
		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem(_("Chat with"))
		menu.append(item)
		menu_account = gtk.Menu()
		item.set_submenu(menu_account)
		for account in self.plugin.accounts.keys():
			item = gtk.MenuItem(account)
			menu_account.append(item)
			menu_group = gtk.Menu()
			item.set_submenu(menu_group)
			for group in self.plugin.roster.groups[account].keys():
				if group == 'Agents':
					continue
				item = gtk.MenuItem(group)
				menu_group.append(item)
				menu_user = gtk.Menu()
				item.set_submenu(menu_user)
				for users in self.plugin.roster.contacts[account].values():
					user = users[0]
					if group in user.groups and user.show != 'offline' and \
						user.show != 'error':
						item = gtk.MenuItem(user.name)
						menu_user.append(item)
						item.connect("activate", self.start_chat, account, user.jid)

		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem(_("Quit"))
		menu.append(item)
		item.connect("activate", self.plugin.roster.on_quit)
		
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def on_clicked(self, widget, event):
		if event.type == gtk.gdk._2BUTTON_PRESS and event.button == 1:
			if len(self.jids) == 0:
				win = self.plugin.roster.xml.get_widget('Gajim')
				if self.iconified:
					win.deiconify()
				else:
					win.iconify()
			else:
				account = self.jids[0][0]
				jid = self.jids[0][1]
				if self.plugin.windows[account]['chats'].has_key(jid):
					self.plugin.windows[account]['chats'][jid].window.present()
				else:
					self.plugin.windows[account]['chats'][jid] = message_Window(\
						self.plugin.roster.contacts[account][jid][0], self.plugin, \
						account)
		if event.button == 3:
			self.mk_menu(event)

	def state_changed(self, widget, event):
		if event.new_window_state & gtk.gdk.WINDOW_STATE_ICONIFIED:
			self.iconified = 1
		else:
			self.iconified = 0

	def __init__(self, plugin):
		self.plugin = plugin
		self.jids = []
		self.iconified = 0
		win = self.plugin.roster.xml.get_widget('Gajim')
		win.connect("window-state-event", self.state_changed)
		t = trayicon.TrayIcon("Gajim")
		eb = gtk.EventBox()
		eb.connect("button-press-event", self.on_clicked)
		self.tip = gtk.Tooltips()
		self.tip.set_tip(t, 'Gajim')
		self.img_tray = gtk.Image()
		eb.add(self.img_tray)
		t.add(eb)
		t.show_all()
		self.status = 'offline'
		self.set_img()

	
class plugin:
	"""Class called by the core in a new thread"""

	class accounts:
		"""Class where are stored the accounts and users in them"""
		def __init__(self):
			self.__accounts = {}

		def add_account(self, account, users=()):
			#users must be like (user1, user2)
			self.__accounts[account] = users

		def add_user_to_account(self, account, user):
			if self.__accounts.has_key(account):
				self.__accounts[account].append(user)
			else :
				return 1

		def get_accounts(self):
			return self.__accounts.keys();

		def get_users(self, account):
			if self.__accounts.has_key(account):
				return self.__accounts[account]
			else :
				return None

		def which_account(self, user):
			for a in self.__accounts.keys():
				if user in self.__accounts[a]:
					return a
			return None

	def send(self, event, account, data):
		self.queueOUT.put((event, account, data))

	def wait(self, what):
		"""Wait for a message from Core"""
		#TODO: timeout
		temp_q = Queue.Queue(50)
		while 1:
			if not self.queueIN.empty():
				ev = self.queueIN.get()
				if ev[0] == what and ev[2][0] == 'GtkGui':
					#Restore messages
					while not temp_q.empty():
						ev2 = temp_q.get()
						self.queueIN.put(ev2)
					return ev[2][1]
				else:
					#Save messages
					temp_q.put(ev)
		
	def read_queue(self):
		"""Read queue from the core and execute commands from it"""
		model = self.roster.tree.get_model()
		while self.queueIN.empty() == 0:
			ev = self.queueIN.get()
			#('ROSTER', account, array)
			if ev[0] == 'ROSTER':
				self.roster.mklists(ev[2], ev[1])
				self.roster.draw_roster()
			elif ev[0] == 'WARNING':
				warning_Window(ev[2])
			#('STATUS', account, status)
			elif ev[0] == 'STATUS':
				self.roster.on_status_changed(ev[1], ev[2])
			#('NOTIFY', account, (jid, status, message, resource, priority))
			elif ev[0] == 'NOTIFY':
				jid = string.split(ev[2][0], '/')[0]
				resource = ev[2][3]
				if not resource:
					resource = ''
				priority = ev[2][4]
				if string.find(jid, "@") <= 0:
					#It must be an agent
					ji = string.replace(jid, '@', '')
				else:
					ji = jid
				#Update user
				if self.roster.contacts[ev[1]].has_key(ji):
					luser = self.roster.contacts[ev[1]][ji]
					user1 = None
					resources = []
					for u in luser:
						resources.append(u.resource)
						if u.resource == resource:
							user1 = u
							break
					if not user1:
						user1 = self.roster.contacts[ev[1]][ji][0]
						if resources != [''] and (len(luser) != 1 or 
							luser[0].show != 'offline'):
							user1 = user(user1.jid, user1.name, user1.groups, \
								user1.show, user1.status, user1.sub, user1.resource, \
								user1.priority)
							luser.append(user1)
						user1.resource = resource
					user1.show = ev[2][1]
					user1.status = ev[2][2]
					user1.priority = priority
				if string.find(jid, "@") <= 0:
					#It must be an agent
					if not self.roster.contacts[ev[1]].has_key(ji):
						user1 = user(ji, ji, ['Agents'], ev[2][1], \
							ev[2][2], 'from', resource, 0)
						self.roster.contacts[ev[1]][ji] = [user1]
						self.roster.add_user_to_roster(ji, ev[1])
					else:
						#Update existing iter
						self.roster.redraw_jid(ji, ev[1])
				elif self.roster.contacts[ev[1]].has_key(ji):
					#It isn't an agent
					self.roster.chg_user_status(user1, ev[2][1], ev[2][2], ev[1])
			#('MSG', account, (user, msg))
			elif ev[0] == 'MSG':
				jid = string.split(ev[2][0], '/')[0]
				if string.find(jid, "@") <= 0:
					jid = string.replace(jid, '@', '')
				self.roster.on_message(jid, ev[2][1], ev[1])
			#('SUBSCRIBE', account, (jid, text))
			elif ev[0] == 'SUBSCRIBE':
				authorize_Window(self, ev[2][0], ev[2][1], ev[1])
			#('SUBSCRIBED', account, (jid, nom, resource))
			elif ev[0] == 'SUBSCRIBED':
				jid = ev[2][0]
				if self.roster.contacts[ev[1]].has_key(jid):
					u = self.roster.contacts[ev[1]][jid][0]
					u.name = ev[2][1]
					u.resource = ev[2][2]
					self.roster.redraw_jid(u.jid, ev[1])
				else:
					user1 = user(jid, jid, ['general'], 'online', \
						'online', 'to', ev[2][2], 0)
					self.roster.contacts[ev[1]][jid] = [user1]
					self.roster.add_user_to_roster(jid, ev[1])
				warning_Window(_("You are now authorized by %s") % jid)
			elif ev[0] == 'UNSUBSCRIBED':
				warning_Window(_("You are now unsubscribed by %s") % ev[2])
				#TODO: change icon
			#('AGENTS', account, agents)
			elif ev[0] == 'AGENTS':
				if self.windows[ev[1]].has_key('browser'):
					self.windows[ev[1]]['browser'].agents(ev[2])
			#('AGENTS_INFO', account, (agent, infos))
			elif ev[0] == 'AGENT_INFO':
				if not ev[2][1].has_key('instructions'):
					warning_Window(_("error contacting %s") % ev[2][0])
				else:
					agentRegistration_Window(ev[2][0], ev[2][1], self, ev[1])
			#('ACC_OK', account, (hostname, login, pasword, name, ressource, prio,
			#use_proxy, proxyhost, proxyport))
			elif ev[0] == 'ACC_OK':
				self.accounts[ev[2][3]] =  {'name': ev[2][1], 'hostname': ev[2][0],\
					'password': ev[2][2], 'ressource': ev[2][4], 'priority': \
					ev[2][5], 'use_proxy': ev[2][6], 'proxyhost': ev[2][7], \
					'proxyport': ev[2][8]}
				self.send('CONFIG', None, ('accounts', self.accounts))
				self.windows[name] = {'infos': {}, 'chats': {}}
				self.queues[name] = {}
				self.connected[name] = 0
				self.roster.groups[name] = {}
				self.roster.contacts[name] = {}
				if self.windows.has_key('accounts'):
					self.windows['accounts'].init_accounts()
			elif ev[0] == 'QUIT':
				self.roster.on_quit(self)
			elif ev[0] == 'MYVCARD':
				nick = ''
				if ev[2].has_key('NICKNAME'):
					nick = ev[2]['NICKNAME']
				if nick == '':
					nick = self.accounts[ev[1]]['name']
				self.nicks[ev[1]] = nick
			elif ev[0] == 'VCARD':
				if self.windows[ev[1]]['infos'].has_key(ev[2]['jid']):
					self.windows[ev[1]]['infos'][ev[2]['jid']].set_values(ev[2])
			#('LOG_NB_LINE', account, (jid, nb_line))
			elif ev[0] == 'LOG_NB_LINE':
				if self.windows['logs'].has_key(ev[2][0]):
					self.windows['logs'][ev[2][0]].set_nb_line(ev[2][1])
					begin = 0
					if ev[2][1] > 50:
						begin = ev[2][1] - 50
					self.send('LOG_GET_RANGE', None, (ev[2][0], begin, ev[2][1]))
			#('LOG_LINE', account, (jid, num_line, date, type, data))
			# if type = 'recv' or 'sent' data = [msg]
			# else type = jid and data = [status, away_msg]
			elif ev[0] == 'LOG_LINE':
				if self.windows['logs'].has_key(ev[2][0]):
					self.windows['logs'][ev[2][0]].new_line(ev[2][1:])
		return 1
	
	def read_sleepy(self):	
		"""Check if we are idle"""
		if not self.sleeper:
			return 1
		self.sleeper.poll()
		state = self.sleeper.getState()
		for account in self.accounts.keys():
			if not self.sleeper_state[account]:
				continue
			if state == common.sleepy.STATE_AWAKE and \
				self.sleeper_state[account] > 1:
				#we go online
				self.send('STATUS', account, ('online', ''))
				self.sleeper_state[account] = 1
			elif state == common.sleepy.STATE_AWAY and \
				self.sleeper_state[account] == 1 and \
				self.config['autoaway']:
				#we go away
				self.send('STATUS', account, ('away', 'auto away (idle)'))
				self.sleeper_state[account] = 2
			elif state == common.sleepy.STATE_XAWAY and (\
				self.sleeper_state[account] == 2 or \
				self.sleeper_state[account] == 1) and \
				self.config['autoxa']:
				#we go extended away
				self.send('STATUS', account, ('xa', 'auto away (idle)'))
				self.sleeper_state[account] = 3
		return 1

	def __init__(self, quIN, quOUT):
		gtk.threads_init()
		gtk.threads_enter()
		self.queueIN = quIN
		self.queueOUT = quOUT
		self.send('ASK_CONFIG', None, ('GtkGui', 'GtkGui', {'autopopup':1,\
			'autopopupaway':1,\
			'showoffline':0,\
			'autoaway':0,\
			'autoawaytime':10,\
			'autoxa':0,\
			'autoxatime':20,\
			'iconstyle':'sun',\
			'inmsgcolor':'#ff0000',\
			'outmsgcolor': '#0000ff',\
			'statusmsgcolor':'#1eaa1e'}))
		self.config = self.wait('CONFIG')
		self.send('ASK_CONFIG', None, ('GtkGui', 'accounts'))
		self.accounts = self.wait('CONFIG')
		self.windows = {'logs':{}}
		self.queues = {}
		self.connected = {}
		self.nicks = {}
		self.sleeper_state = {} #whether we pass auto away / xa or not
		for a in self.accounts.keys():
			self.windows[a] = {}
			self.windows[a]['infos'] = {}
			self.windows[a]['chats'] = {}
			self.queues[a] = {}
			self.connected[a] = 0
			self.nicks[a] = self.accounts[a]['name']
			self.sleeper_state[a] = 0	#0:don't use sleeper for this account
												#1:online and use sleeper
												#2:autoaway and use sleeper
												#3:autoxa and use sleeper
		self.roster = roster_Window(self)
		gtk.timeout_add(100, self.read_queue)
		gtk.timeout_add(1000, self.read_sleepy)
		self.sleeper = None
		self.systray = systray(self)
		gtk.main()
		gtk.threads_leave()

if __name__ == "__main__":
	plugin(None, None)

print _("plugin gtkgui loaded")
