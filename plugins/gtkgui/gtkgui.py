#!/usr/bin/env python
##	plugins/gtkgui.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@tuxfamily.org>
## 	- David Ferlier <david@yazzy.org>
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
import gtk.glade
import gobject
import os
import string
import Queue
import common.optparser
CONFPATH = "~/.gajimrc"
Wbrowser = 0
Waccounts = 0

class user:
	def __init__(self, *args):
		if len(args) == 0:
			self.jid = ''
			self.name = ''
			self.groups = []
			self.show = ''
			self.status = ''
			self.sub == ''
		elif len(args) == 6:
			self.jid = args[0]
			self.name = args[1]
			self.groups = args[2]
			self.show = args[3]
			self.status = args[4]
			self.sub = args[5]
#		elif ((len(args)) and (type (args[0]) == type (self)) and
#			(self.__class__ == args[0].__class__)):
#			self.name = args[0].name
#			self.groups = args[0].groups
#			self.show = args[0].show
#			self.status = args[0].status
#			self.sub = args[0].sub
		else: raise TypeError, 'bad arguments'

class add:
	def delete_event(self, widget):
		self.Wadd.destroy()

	def on_subscribe(self, widget):
		who = self.xml.get_widget("entry_who").get_text()
		buf = self.xml.get_widget("textview_sub").get_buffer()
		start_iter = buf.get_start_iter()
		end_iter = buf.get_end_iter()
		txt = buf.get_text(start_iter, end_iter, 0)
		self.r.req_sub(self, who, txt)
		self.delete_event(self)
		
	def __init__(self, roster, jid=None):
		self.r = roster
		self.xml = gtk.glade.XML('plugins/gtkgui/gtkgui.glade', 'Add')
		if jid:
			 self.xml.get_widget('entry_who').set_text(jid)
		self.Wadd = self.xml.get_widget("Add")
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_button_sub_clicked', self.on_subscribe)

class about:
	def delete_event(self, widget):
		self.Wabout.destroy()
		
	def __init__(self):
		self.xml = gtk.glade.XML('plugins/gtkgui/gtkgui.glade', 'About')
		self.Wabout = self.xml.get_widget("About")
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)

class account_pref:
	def delete_event(self, widget):
		self.window.destroy()
	
	def init_account(self, infos):
		if infos.has_key('name'):
			self.xml.get_widget("entry_name").set_text(infos['name'])
		if infos.has_key('jid'):
			self.xml.get_widget("entry_jid").set_text(infos['jid'])
		if infos.has_key('password'):
			self.xml.get_widget("entry_password").set_text(infos['password'])
		if infos.has_key('ressource'):
			self.xml.get_widget("entry_ressource").set_text(infos['ressource'])

	def on_save_clicked(self, widget):
#		accountsStr = self.cfgParser.Profile_accounts
#		accounts = string.split(accountsStr, ' ')
		name = self.xml.get_widget("entry_name").get_text()
		if (name == ''):
			return 0
		if self.mod:
			if name != self.acc:
				self.cfgParser.remove_section(self.acc)
				self.accs.accounts.remove(self.acc)
				self.cfgParser.add_section(name)
				self.accs.accounts.append(name)
				accountsStr = string.join(self.accs.accounts)
				self.cfgParser.set('Profile', 'accounts', accountsStr)
		else:
			if name in self.accs.accounts:
				return 0
			else:
				self.cfgParser.add_section(name)
				self.accs.accounts.append(name)
				accountsStr = string.join(self.accs.accounts)
				self.cfgParser.set('Profile', 'accounts', accountsStr)
		(login, hostname) = string.split(self.xml.get_widget("entry_jid").get_text(), '@')
		self.cfgParser.set(name, 'name', login)
		self.cfgParser.set(name, 'hostname', hostname)
		self.cfgParser.set(name, 'password', self.xml.get_widget("entry_password").get_text())
		self.cfgParser.set(name, 'ressource', self.xml.get_widget("entry_ressource").get_text())
		self.cfgParser.writeCfgFile()
		self.cfgParser.parseCfgFile()
		self.accs.init_accounts()
	
	#info must be a dictionnary
	def __init__(self, accs, infos = {}):
		self.xml = gtk.glade.XML('plugins/gtkgui/gtkgui.glade', 'Account')
		self.window = self.xml.get_widget("Account")
		self.cfgParser = accs.cfgParser
		self.accs = accs
		if infos:
			self.mod = TRUE
			self.acc = infos['name']
			self.init_account(infos)
		else:
			self.mod = FALSE
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_save_clicked', self.on_save_clicked)

class accounts:
	def delete_event(self, widget):
		global Waccounts
		Waccounts = 0
		self.window.destroy()
		
	def init_accounts(self):
		self.model.clear()
		for account in self.accounts:
			iter = self.model.append()
			self.model.set(iter, 0, account, 1, self.cfgParser.__getattr__("%s" % account+"_hostname"))

	def on_row_activated(self, widget):
		self.modButt.set_sensitive(TRUE)
		self.delButt.set_sensitive(TRUE)

	def on_new_clicked(self, widget):
		account_pref(self)

	def on_delete_clicked(self, widget):
		sel = self.treeview.get_selection()
		(mod, iter) = sel.get_selected()
		account = self.model.get_value(iter, 0)
		self.cfgParser.remove_section(account)
		self.accounts.remove(account)
		accountsStr = string.join(self.accounts)
		self.cfgParser.set('Profile', 'accounts', accountsStr)
		self.cfgParser.writeCfgFile()
		self.cfgParser.parseCfgFile()
		self.init_accounts()

	def on_modify_clicked(self, widget):
		infos = {}
		sel = self.treeview.get_selection()
		(mod, iter) = sel.get_selected()
		account = self.model.get_value(iter, 0)
		infos['name'] = account
		infos['jid'] = self.cfgParser.__getattr__("%s" % account+"_name") + \
			'@' +  self.cfgParser.__getattr__("%s" % account+"_hostname")
		infos['password'] = self.cfgParser.__getattr__("%s" % account+"_password")
		infos['ressource'] = self.cfgParser.__getattr__("%s" % account+"_ressource")
		account_pref(self, infos)
		
	def __init__(self, accounts):
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
		self.cfgParser.parseCfgFile()
		self.xml = gtk.glade.XML('plugins/gtkgui/gtkgui.glade', 'Accounts')
		self.window = self.xml.get_widget("Accounts")
		self.treeview = self.xml.get_widget("treeview")
		self.modButt = self.xml.get_widget("modify_button")
		self.delButt = self.xml.get_widget("delete_button")
		self.model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.treeview.set_model(self.model)
		#columns
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 0)
		self.treeview.insert_column_with_attributes(-1, 'Name', renderer, text=0)
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 1)
		self.treeview.insert_column_with_attributes(-1, 'Server', renderer, text=1)
		self.accounts = accounts
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_row_activated', self.on_row_activated)
		self.xml.signal_connect('on_new_clicked', self.on_new_clicked)
		self.xml.signal_connect('on_delete_clicked', self.on_delete_clicked)
		self.xml.signal_connect('on_modify_clicked', self.on_modify_clicked)
		self.init_accounts()

class confirm:
	def delete_event(self, widget):
		self.window.destroy()
		
	def req_usub(self, widget):
		self.r.queueOUT.put(('UNSUB', self.jid))
		del self.r.l_contact[self.jid]
		self.r.treestore.remove(self.iter)
		self.delete_event(self)
	
	def __init__(self, roster, iter):
		self.xml = gtk.glade.XML('plugins/gtkgui/gtkgui.glade', 'Confirm')
		self.window = self.xml.get_widget('Confirm')
		self.r = roster
		self.iter = iter
		self.jid = self.r.treestore.get_value(iter, 2)
		self.xml.get_widget('label_confirm').set_text('Are you sure you want to remove ' + self.jid + ' from your roster ?')
		self.xml.signal_connect('on_okbutton_clicked', self.req_usub)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)

class authorize:
	def delete_event(self, widget):
		self.window.destroy()
		
	def auth(self, widget):
		self.r.queueOUT.put(('AUTH', self.jid))
		self.delete_event(self)
		add(self.r, self.jid)
	
	def deny(self, widget):
		self.r.queueOUT.put(('DENY', self.jid))
		self.delete_event(self)
	
	def __init__(self, roster, jid):
		self.xml = gtk.glade.XML('plugins/gtkgui/gtkgui.glade', 'Sub_req')
		self.window = self.xml.get_widget('Sub_req')
		self.r = roster
		self.jid = jid
		self.xml.get_widget('label').set_text('Subscription request from ' + self.jid)
		self.xml.signal_connect('on_button_auth_clicked', self.auth)
		self.xml.signal_connect('on_button_deny_clicked', self.deny)
		self.xml.signal_connect('on_button_close_clicked', self.delete_event)

class agent_reg:
	def delete_event(self, widget):
		self.window.destroy()
	
	def draw_table(self):
		for name in self.infos.keys():
			if name != 'key' and name != 'instructions' and name != 'x':
				self.nbrow = self.nbrow + 1
				self.table.resize(rows=self.nbrow, columns=2)
				label = gtk.Label(name)
				self.table.attach(label, 0, 1, self.nbrow-1, self.nbrow, 0, 0, 0, 0)
				entry = gtk.Entry()
				entry.set_text(self.infos[name])
				self.table.attach(entry, 1, 2, self.nbrow-1, self.nbrow, 0, 0, 0, 0)
				self.entries[name] = entry
				if self.nbrow == 1:
					entry.grab_focus()
		self.table.show_all()
	
	def on_ok(self, widget):
		for name in self.entries.keys():
			self.infos[name] = self.entries[name].get_text()
		self.r.queueOUT.put(('REG_AGENT', self.agent))
		self.delete_event(self)
	
	def __init__(self, agent, infos, roster):
		self.xml = gtk.glade.XML('plugins/gtkgui/gtkgui.glade', 'agent_reg')
		self.infos = infos
		self.r = roster
		self.agent = agent
		self.window = self.xml.get_widget('agent_reg')
		self.table = self.xml.get_widget('table')
		self.window.set_title('Register to ' + agent)
		self.xml.get_widget('label').set_text(infos['instructions'])
		self.nbrow = 0
		self.entries = {}
		self.draw_table()
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_button_cancel_clicked', self.delete_event)
		self.xml.signal_connect('on_button_ok_clicked', self.on_ok)
		

class browser:
	def delete_event(self, widget):
		global Wbrowser
		Wbrowser = 0
		self.window.destroy()

	def browse(self):
		self.r.queueOUT.put(('REQ_AGENTS', None))
	
	def agents(self, agents):
		for jid in agents.keys():
			iter = self.model.append()
			self.model.set(iter, 0, agents[jid]['name'], 1, agents[jid]['service'])

	def on_refresh(self, widget):
		self.model.clear()
		self.browse()

	def on_row_activated(self, widget, path, col=0):
		iter = self.model.get_iter(path)
		service = self.model.get_value(iter, 1)
		self.r.queueOUT.put(('REQ_AGENT_INFO', service))
		self.delete_event(self)
		
	def __init__(self, roster):
		self.xml = gtk.glade.XML('plugins/gtkgui/gtkgui.glade', 'browser')
		self.window = self.xml.get_widget('browser')
		self.treeview = self.xml.get_widget('treeview')
		self.r = roster
		self.model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.treeview.set_model(self.model)
		#columns
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 0)
		self.treeview.insert_column_with_attributes(-1, 'Name', renderer, text=0)
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 1)
		self.treeview.insert_column_with_attributes(-1, 'Service', renderer, text=1)

		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_refresh_clicked', self.on_refresh)
		self.xml.signal_connect('on_row_activated', self.on_row_activated)
		#TODO: Si connecte
		self.browse()

class message:
	def delete_event(self, widget):
		del self.r.tab_messages[self.user.jid]
		self.window.destroy()
	
	def print_conversation(self, txt, contact = None):
		end_iter = self.convTxtBuffer.get_end_iter()
		if contact:
			if contact == 'status':
				self.convTxtBuffer.insert_with_tags_by_name(end_iter, txt+'\n', \
					'status')
			else:
				self.convTxtBuffer.insert_with_tags_by_name(end_iter, '<moi> ', 'outgoing')
				self.convTxtBuffer.insert(end_iter, txt+'\n')
		else:
			self.convTxtBuffer.insert_with_tags_by_name(end_iter, '<' + self.user.name + '> ', 'incoming')
			self.convTxtBuffer.insert(end_iter, txt+'\n')
		self.conversation.scroll_to_mark(\
			self.convTxtBuffer.get_mark('end'), 0.1, 0, 0, 0)
	
	def read_queue(self, q):
		while not q.empty():
			self.print_conversation(q.get(), 1)
		del self.r.tab_queues[self.user.jid]
		for i in self.r.l_contact[self.user.jid]['iter']:
			if self.r.pixbufs.has_key(self.user.show):
				self.r.treestore.set_value(i, 0, self.r.pixbufs[self.user.show])

	def on_msg_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Return:
			if (event.state & gtk.gdk.SHIFT_MASK):
				return 0
			txt_buffer = widget.get_buffer()
			start_iter = txt_buffer.get_start_iter()
			end_iter = txt_buffer.get_end_iter()
			txt = txt_buffer.get_text(start_iter, end_iter, 0)
			self.r.queueOUT.put(('MSG',(self.user.jid, txt)))
			txt_buffer.set_text('', -1)
			self.print_conversation(txt, self.user.jid)
			widget.grab_focus()
			return 1
		return 0

	def __init__(self, user, roster):
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
		self.cfgParser.parseCfgFile()
		self.user = user
		self.r = roster
		self.xml = gtk.glade.XML('plugins/gtkgui/gtkgui.glade', 'Chat')
		self.window = self.xml.get_widget('Chat')
		self.window.set_title('Chat with ' + user.name)
		self.img = self.xml.get_widget('image')
		self.img.set_from_pixbuf(self.r.pixbufs[user.show])
		self.xml.get_widget('label_contact').set_text(user.name + ' <'\
			+ user.jid + '>')
		self.message = self.xml.get_widget('message')
		self.message.grab_focus()
		self.conversation = self.xml.get_widget('conversation')
		self.convTxtBuffer = self.conversation.get_buffer()
		end_iter = self.convTxtBuffer.get_end_iter()
		self.convTxtBuffer.create_mark('end', end_iter, 0)
#		self.window.show()
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_msg_key_press_event', self.on_msg_key_press_event)
		self.tag = self.convTxtBuffer.create_tag("incoming")
		color = self.cfgParser.GtkGui_inmsgcolor
		if not color:
			color = 'red'
		self.tag.set_property("foreground", color)
		self.tag = self.convTxtBuffer.create_tag("outgoing")
		color = self.cfgParser.GtkGui_outmsgcolor
		if not color:
			color = 'blue'
		self.tag.set_property("foreground", color)
		self.tag = self.convTxtBuffer.create_tag("status")
		color = self.cfgParser.GtkGui_statusmsgcolor
		if not color:
			color = 'green'
		self.tag.set_property("foreground", color)

class roster:
	def get_icon_pixbuf(self, stock):
		return self.tree.render_icon(stock, size = gtk.ICON_SIZE_MENU, detail = None)

	def mkroster(self, tab):
		""" l_contact = {jid:{'user':_, 'iter':[iter1, ...]] """
		self.l_contact = {}
		""" l_group = {name:iter} """
		self.l_group = {}
		self.treestore.clear()
		for jid in tab.keys():
			#remove ressource from jid string
			ji = string.split(jid, '/')[0]
			name = tab[jid]['name']
			if not name:
				if string.find(ji, "@") <= 0:
					name = ji
				else:
					name = ''
			show = tab[jid]['show']
			if not show:
				show = 'offline'
			user1 = user(ji, name, tab[jid]['groups'], show, tab[jid]['status'], tab[jid]['sub'])
			self.l_contact[user1.jid] = {'user': user1, 'iter': []}
			if user1.groups == []:
				if string.find(ji, "@") <= 0:
					user1.groups.append('Agents')
				else:
					user1.groups.append('general')
			for g in user1.groups:
				if not self.l_group.has_key(g):
					iterG = self.treestore.append(None, (self.pixbufs['closed'], g, 'group', FALSE, self.grpbgcolor, TRUE))
					self.l_group[g] = iterG
				if user1.show != 'offline' or self.showOffline or g == 'Agents':
					if g == 'Agents':
						iterU = self.treestore.append(self.l_group[g], (self.pixbufs[user1.show], user1.name, 'agent', FALSE, self.userbgcolor, TRUE))
					else:
						iterU = self.treestore.append(self.l_group[g], (self.pixbufs[user1.show], user1.name, user1.jid, TRUE, self.userbgcolor, TRUE))
					self.l_contact[user1.jid]['iter'].append(iterU)
		self.tree.expand_all()

	def update_iter(self, widget, path, iter, data):
		jid = self.treestore.get_value(iter, 2)
		if jid == data[0]:
			if data[1] == 'offline':
				self.treestore.remove(iter)
				if not self.showOffline:
					self.found = 1
			else:
				self.treestore.set_value(iter, 0, self.pixbufs[data[1]])
				self.found = 1
			return 1
		return 0
	
	def chg_status(self, jid, show, status):
		u = self.l_contact[jid]['user']
		if self.l_contact[jid]['iter'] == []:
			for g in u.groups:
				if not self.l_group.has_key(g):
					iterG = self.treestore.append(None, (self.pixbufs['closed'], g, 'group', FALSE, self.grpbgcolor, TRUE))
					self.l_group[u.group] = iterG
				iterU = self.treestore.append(self.l_group[g], (self.pixbufs[show], u.name, u.jid, TRUE, self.userbgcolor, TRUE))
				self.l_contact[u.jid]['iter'].append(iterU)
		else:
			if show == 'offline' and not self.showOffline:
				for i in self.l_contact[jid]['iter']:
					self.treestore.remove(i)
				self.l_contact[jid]['iter'] = []
			else:
				for i in self.l_contact[jid]['iter']:
					if self.pixbufs.has_key(show):
						self.treestore.set_value(i, 0, self.pixbufs[show])
			#update icon in chat window
			if self.tab_messages.has_key(jid):
				self.tab_messages[jid].img.set_from_pixbuf(self.pixbufs[show])
		u.show = show
		u.status = status
	
	def mk_menu_c(self, event, iter):
		jid = self.treestore.get_value(iter, 2)
		path = self.treestore.get_path(iter)
		self.menu_c = gtk.Menu()
		item = gtk.MenuItem("Start chat")
		self.menu_c.append(item)
		item.connect("activate", self.on_row_activated, path)
		item = gtk.MenuItem("Rename")
		self.menu_c.append(item)
#		item.connect("activate", self.on_rename, iter)
		item = gtk.MenuItem()
		self.menu_c.append(item)
		item = gtk.MenuItem("Subscription")
		self.menu_c.append(item)
		
		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem("Resend authorization to")
		menu_sub.append(item)
		item.connect("activate", self.authorize, jid)
		item = gtk.MenuItem("Rerequest authorization from")
		menu_sub.append(item)
		item.connect("activate", self.req_sub, jid, 'I would like to add you to my contact list, please.')
		
		item = gtk.MenuItem()
		self.menu_c.append(item)
		item = gtk.MenuItem("Remove")
		self.menu_c.append(item)
		item.connect("activate", self.on_req_usub, iter)
		self.menu_c.popup(None, None, None, event.button, event.time)
		self.menu_c.show_all()

	def mk_menu_g(self, event):
		self.menu_c = gtk.Menu()
		item = gtk.MenuItem("grp1")
		self.menu_c.append(item)
		item = gtk.MenuItem("grp2")
		self.menu_c.append(item)
		item = gtk.MenuItem("grp3")
		self.menu_c.append(item)
		self.menu_c.popup(None, None, None, event.button, event.time)
		self.menu_c.show_all()
	
	def authorize(self, widget, jid):
		self.queueOUT.put(('AUTH', jid))

	def rename(self, widget, jid, name):
		u = self.r.l_contact[jid]['user']
		u.name = name
		for i in self.r.l_contact[jid]['iter']:
			self.r.treestore.set_value(i, 1, name)
	
	def req_sub(self, widget, jid, txt):
		self.queueOUT.put(('SUB', (jid, txt)))
		if not self.l_contact.has_key(jid):
			user1 = user(jid, jid, ['general'], 'requested', 'requested', 'sub')
			if not self.l_group.has_key('general'):
				iterG = self.treestore.append(None, (self.pixbufs['closed'], 'general', 'group', FALSE, self.grpbgcolor, TRUE))
				self.l_group['general'] = iterG
			iterU = self.treestore.append(self.l_group['general'], (self.pixbufs['requested'], jid, jid, TRUE, self.userbgcolor, TRUE))
			self.l_contact[jid] = {'user':user1, 'iter':[iterU]}

	def on_treeview_event(self, widget, event):
		if (event.button == 3) & (event.type == gtk.gdk.BUTTON_PRESS):
			try:
				path, column, x, y = self.tree.get_path_at_pos(int(event.x), int(event.y))
			except TypeError:
				return
			iter = self.treestore.get_iter(path)
			data = self.treestore.get_value(iter, 2)
			if data == 'group':
				self.mk_menu_g(event)
			elif data == 'agent':
				#TODO
				pass
			else:
				self.mk_menu_c(event, iter)
			return gtk.TRUE
		return gtk.FALSE
	
	def on_req_usub(self, widget, iter):
		window_confirm = confirm(self, iter)

	def on_status_changed(self, widget):
		accountsStr = self.cfgParser.Profile_accounts
		accounts = string.split(accountsStr, ' ')
		self.queueOUT.put(('STATUS',(widget.name, accounts[0])))
		if (not self.showOffline) and widget.name == 'offline':
			self.treestore.clear()

	def on_add(self, widget):
		window_add = add(self)

	def on_about(self, widget):
		window_about = about()

	def on_accounts(self, widget):
		global Waccounts
		if not Waccounts:
			Waccounts = accounts(self.accounts)
	
	def on_quit(self, widget):
		self.queueOUT.put(('QUIT',''))
		gtk.mainquit()

	def on_row_activated(self, widget, path, col=0):
		iter = self.treestore.get_iter(path)
		jid = self.treestore.get_value(iter, 2)
		if (jid == 'group'):
			if (self.tree.row_expanded(path)):
				self.tree.collapse_row(path)
			else:
				self.tree.expand_row(path, FALSE)
		else:
			if self.tab_messages.has_key(jid):
				self.tab_messages[jid].window.present()
			elif self.l_contact.has_key(jid):
				self.tab_messages[jid] = message(self.l_contact[jid]['user'], self)
				if self.tab_queues.has_key(jid):
					self.tab_messages[jid].read_queue(self.tab_queues[jid])

	def on_row_expanded(self, widget, iter, path):
		self.treestore.set_value(iter, 0, self.pixbufs['opened'])
	
	def on_row_collapsed(self, widget, iter, path):
		self.treestore.set_value(iter, 0, self.pixbufs['closed'])

	def on_cell_edited (self, cell, row, new_text):
		iter = self.treestore.get_iter_from_string(row)
		jid = self.treestore.get_value(iter, 2)
		old_text = self.l_contact[jid]['user'].name
		#If it is a double click, old_text == new_text
		if old_text == new_text:
			if self.tab_messages.has_key(jid):
				self.tab_messages[jid].window.present()
			elif self.l_contact.has_key(jid):
				self.tab_messages[jid] = message(self.l_contact[jid]['user'], self)
				if self.tab_queues.has_key(jid):
					self.tab_messages[jid].read_queue(self.tab_queues[jid])
		else:
			self.treestore.set_value(iter, 1, new_text)
			self.l_contact[jid]['user'].name = new_text
			self.queueOUT.put(('UPDUSER', (jid, new_text, self.l_contact[jid]['user'].groups)))
		
	def on_browse(self, widget):
		global Wbrowser
		if not Wbrowser:
			Wbrowser = browser(self)

	def __init__(self, queueOUT):
		# FIXME : handle no file ...
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
		self.cfgParser.parseCfgFile()
		self.xml = gtk.glade.XML('plugins/gtkgui/gtkgui.glade', 'Gajim')
		self.window =  self.xml.get_widget('Gajim')
		self.tree = self.xml.get_widget('treeview')
		#(icon, name, jid, editable, background color, show_icon)
		self.treestore = gtk.TreeStore(gtk.gdk.Pixbuf, str, str, gobject.TYPE_BOOLEAN, str, gobject.TYPE_BOOLEAN)
		iconstyle = self.cfgParser.GtkGui_iconstyle
		if not iconstyle:
			iconstyle = 'sun'
		self.path = 'plugins/gtkgui/icons/' + iconstyle + '/'
		self.pixbufs = {}
		for state in ('online', 'away', 'xa', 'dnd', 'offline', 'requested', 'message', 'opened', 'closed'):
			if not os.path.exists(self.path + state + '.xpm'):
				print 'No such file : ' + self.path + state + '.xpm'
				self.pixbufs[state] = None
			else:
				pix = gtk.gdk.pixbuf_new_from_file (self.path + state + '.xpm')
				self.pixbufs[state] = pix
		self.tree.set_model(self.treestore)
#		map = self.tree.get_colormap()
#		colour = map.alloc_color("red") # light red
#		colour2 = map.alloc_color("blue") # light red
#		colour = map.alloc_color("#FF9999") # light red
#		st = self.tree.get_style().copy()
#		st.bg[gtk.STATE_NORMAL] = colour
#		st.fg[gtk.STATE_NORMAL] = colour
#		st.bg[gtk.STATE_ACTIVE] = colour2
#		st.fg[gtk.STATE_ACTIVE] = colour2
#		st.bg[gtk.STATE_INSENSITIVE] = colour
#		st.bg[gtk.STATE_PRELIGHT] = colour
#		st.bg[gtk.STATE_SELECTED] = colour
#		st.fg[gtk.STATE_SELECTED] = colour2
#		st.white = colour
#		print st.bg
#		print self.tree.get_property('expander-column')
#		self.tree.set_style(st)
		self.queueOUT = queueOUT
		self.optionmenu = self.xml.get_widget('optionmenu')
		self.optionmenu.set_history(6)
		self.tab_messages = {}
		self.tab_queues = {}
		accountsStr = self.cfgParser.Profile_accounts
		self.accounts = string.split(accountsStr, ' ')

		showOffline = self.cfgParser.GtkGui_showoffline
		if showOffline:
			self.showOffline = string.atoi(showOffline)
		else:
			self.showOffline = 0

		self.grpbgcolor = 'gray50'
		self.userbgcolor = 'white'

		#columns
		self.col = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		self.col.pack_start(render_pixbuf, expand = False)
		self.col.add_attribute(render_pixbuf, 'pixbuf', 0)
		self.col.add_attribute(render_pixbuf, 'cell-background', 4)
		self.col.add_attribute(render_pixbuf, 'visible', 5)
		render_text = gtk.CellRendererText()
		render_text.connect('edited', self.on_cell_edited)
		self.col.pack_start(render_text, expand = True)
		self.col.add_attribute(render_text, 'text', 1)
		self.col.add_attribute(render_text, 'cell-background', 4)
		self.col.add_attribute(render_text, 'editable', 3)
		self.tree.append_column(self.col)
		col2 = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		col2.pack_start(render_pixbuf, expand = False)
		self.tree.append_column(col2)
		col2.set_visible(FALSE)
		self.tree.set_expander_column(col2)

		#signals
		self.xml.signal_connect('gtk_main_quit', self.on_quit)
		self.xml.signal_connect('on_accounts_activate', self.on_accounts)
		self.xml.signal_connect('on_browse_agents_activate', self.on_browse)
		self.xml.signal_connect('on_add_activate', self.on_add)
		self.xml.signal_connect('on_about_activate', self.on_about)
		self.xml.signal_connect('on_quit_activate', self.on_quit)
		self.xml.signal_connect('on_treeview_event', self.on_treeview_event)
		self.xml.signal_connect('on_status_changed', self.on_status_changed)
		self.xml.signal_connect('on_row_activated', self.on_row_activated)
		self.xml.signal_connect('on_row_expanded', self.on_row_expanded)
		self.xml.signal_connect('on_row_collapsed', self.on_row_collapsed)

class plugin:
	def read_queue(self):
		global Wbrowser
		while self.queueIN.empty() == 0:
			ev = self.queueIN.get()
			if ev[0] == 'ROSTER':
				self.r.mkroster(ev[1])
			elif ev[0] == 'NOTIFY':
				jid = string.split(ev[1][0], '/')[0]
				#Update user
				if self.r.l_contact.has_key(jid):
					u = self.r.l_contact[jid]['user']
					u.show = ev[1][1]
					u.status = ev[1][2]
					#Print status in chat window
					if self.r.tab_messages.has_key(jid):
						self.r.tab_messages[jid].print_conversation(\
							"%s is now %s (%s)" % (u.name, ev[1][1], ev[1][2]), 'status')
				if string.find(jid, "@") <= 0:
					#It must be an agent
					jid = string.replace(jid, '@', '')
					if not self.r.l_group.has_key('Agents'):
						iterG = self.r.treestore.append(None, (self.pixbufs['closed'], \
							'Agents', 'group', FALSE, self.r.grpbgcolor, TRUE))
						self.r.l_group['Agents'] = iterG
					if not self.r.l_contact.has_key(jid):
						user1 = user(jid, jid, ['Agents'], ev[1][1], ev[1][2], 'from')
						iterU = self.r.treestore.append(self.r.l_group['Agents'], \
							(self.r.pixbufs[ev[1][1]], jid, 'agent', FALSE, \
							self.userbgcolor, TRUE))
						self.r.l_contact[jid] = {'user':user1, 'iter':[iterU]}
					else:
						#Update existing line
						for i in self.r.l_contact[jid]['iter']:
							if self.r.pixbufs.has_key(ev[1][1]):
								self.r.treestore.set_value(i, 0, self.r.pixbufs[ev[1][1]])
				elif self.r.l_contact.has_key(jid):
					#It isn't an agent
					self.r.chg_status(jid, ev[1][1], ev[1][2])
			elif ev[0] == 'MSG':
				if string.find(ev[1][0], "@") <= 0:
					jid = string.replace(ev[1][0], '@', '')
				else:
					jid = ev[1][0]
				
				autopopup = self.r.cfgParser.GtkGui_autopopup
				if autopopup:
					autopopup = string.atoi(autopopup)
				else:
					self.autopopup = 0
				if autopopup == 0 and not self.r.tab_messages.has_key(jid):
					#We save it in a queue
					if not self.r.tab_queues.has_key(jid):
						self.r.tab_queues[jid] = Queue.Queue(50)
					self.r.tab_queues[jid].put(ev[1][1])
					for i in self.r.l_contact[jid]['iter']:
						self.r.treestore.set_value(i, 0, self.r.pixbufs['message'])
				else:
					if not self.r.tab_messages.has_key(jid):
						#FIXME:message from unknown
						if self.r.l_contact.has_key(jid):
							self.r.tab_messages[jid] = message(self.r.l_contact[jid]['user'], self.r)
					if self.r.tab_messages.has_key(jid):
						self.r.tab_messages[jid].print_conversation(ev[1][1])
					
			elif ev[0] == 'SUBSCRIBE':
				authorize(self.r, ev[1])
			elif ev[0] == 'SUBSCRIBED':
				jid = ev[1]['jid']
				if self.r.l_contact.has_key(jid):
					u = self.r.l_contact[jid]['user']
					u.name = ev[1]['nom']
					for i in self.r.l_contact[u.jid]['iter']:
						self.r.treestore.set_value(i, 1, u.name)
				else:
					user1 = user(jid, jid, ['general'], 'online', 'online', 'to')
					if not self.r.l_group.has_key('general'):
						iterG = self.r.treestore.append(None, (self.pixbufs['closed'], \
							'general', 'group', FALSE, self.r.grpbgcolor, TRUE))
						self.r.l_group['general'] = iterG
					iterU = self.r.treestore.append(self.r.l_group['general'], \
						(self.r.pixbufs['online'], jid, jid, TRUE, self.userbgcolor, TRUE))
					self.r.l_contact[jid] = {'user':user1, 'iter':[iterU]}
				#TODO: print 'you are now authorized'
			elif ev[0] == 'AGENTS':
				if Wbrowser:
					Wbrowser.agents(ev[1])
			elif ev[0] == 'AGENT_INFO':
				Wreg = agent_reg(ev[1][0], ev[1][1], self.r)
		return 1

	def __init__(self, quIN, quOUT):
		gtk.threads_init()
		gtk.threads_enter()
		self.queueIN = quIN
		self.r = roster(quOUT)
		self.time = gtk.timeout_add(200, self.read_queue)
		gtk.main()
		gtk.threads_leave()

if __name__ == "__main__":
	plugin(None, None)

print "plugin gtkgui loaded"
