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
import gtk.glade,gobject
import os,string,time,Queue
import common.optparser,common.sleepy
browserWindow = 0
accountsWindow = 0

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
			self.sub == ''
			self.resource == ''
		elif len(args) == 7:
			self.jid = args[0]
			self.name = args[1]
			self.groups = args[2]
			self.show = args[3]
			self.status = args[4]
			self.sub = args[5]
			self.resource = args[6]
		else: raise TypeError, 'bad arguments'

class infoUser_Window:
	"""Class for user's information window"""
	def delete_event(self, widget):
		"""close window"""
		self.window.destroy()

	def add_grp_to_user(self, model, path, iter):
		"""Insert user to the group in inter"""
		self.user.groups.append(model.get_value(iter, 0))

	def on_close(self, widget):
		"""Save user's informations and update the roster on the Jabber server"""
		#update: to know if things have changed to send things 
		# to server only if changes are done
		update = 0
		#update user.name if it's not ""
		newName = self.entry_name.get_text()
		if newName != self.user.name:
			update = 1
			if newName != '':
				self.user.name = newName
		#update user.groups and redraw the user in the roster
		old_groups = self.user.groups
		self.r.remove_user(self.user)
		self.user.groups = []
		model = self.list2.get_model()
		model.foreach(self.add_grp_to_user)
		self.r.add_user(self.user)
		for g in old_groups:
			if not g in self.user.groups:
				update = 1
				break
		if not update:
			for g in self.user.groups:
				if not g in old_groups:
					update = 1
					break
		if update:
			self.r.queueOUT.put(('UPDUSER', (self.user.jid, self.user.name, \
				self.user.groups)))
		self.delete_event(self)

	def add_grp(self, model, path, iter, stors):
		"""Transfert the iter from stors[0] to stors[1]"""
		i = stors[1].append()
		stors[1].set(i, 0, stors[0].get_value(iter, 0))
		stors[0].remove(iter)

	def on_add(self, widget):
		"""When Add button is clicked"""
		model = self.list1.get_model()
		select = self.list1.get_selection()
		select.selected_foreach(self.add_grp, (model, self.list2.get_model()))

	def on_remove(self, widget):
		"""When Remove button is clicked"""
		model = self.list2.get_model()
		select = self.list2.get_selection()
		select.selected_foreach(self.add_grp, (model, self.list1.get_model()))

	def on_new_key_pressed(self, widget, event):
		"""If enter is pressed in new group entry, add the group"""
		if event.keyval == gtk.keysyms.Return:
			model = self.list1.get_model()
			txt = self.entry_new.get_text()
			iter = model.append()
			model.set(iter, 0, txt)
			self.entry_new.set_text('')
			return 1
		else:
			return 0

	def init_lists(self):
		"""Initialize both available and current listStores"""
		#list available
		store = gtk.ListStore(gobject.TYPE_STRING)
		for g in self.r.l_group.keys():
			if g != 'Agents' and g not in self.user.groups:
				iter = store.append()
				store.set(iter, 0, g)
		self.list1.set_model(store)
		column = gtk.TreeViewColumn('Available', gtk.CellRendererText(), text=0)
		self.list1.append_column(column)

		#list_current
		store = gtk.ListStore(gobject.TYPE_STRING)
		for g in self.user.groups:
			iter = store.append()
			store.set(iter, 0, g)
		self.list2.set_model(store)
		column = gtk.TreeViewColumn('Available', gtk.CellRendererText(), text=0)
		self.list2.append_column(column)

	def __init__(self, user, roster):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Info_user')
		self.window = xml.get_widget("Info_user")
		self.r = roster
		self.user = user
		self.list1 = xml.get_widget("treeview_available")
		self.list2 = xml.get_widget("treeview_current")
		self.entry_new = xml.get_widget("entry_new")

		xml.get_widget('label_name').set_text(user.name)
		xml.get_widget('label_id').set_text(user.jid)
		xml.get_widget('label_resource').set_text(user.resource)
		self.entry_name = xml.get_widget('entry_name')
		self.entry_name.set_text(user.name)
		if not user.status:
			user.status = ''
		xml.get_widget('label_status').set_text(user.show + ' : ' + \
			user.status)
		self.init_lists()
		
		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_close_clicked', self.on_close)
		xml.signal_connect('on_add_clicked', self.on_add)
		xml.signal_connect('on_remove_clicked', self.on_remove)
		xml.signal_connect('on_entry_new_key_press_event', \
			self.on_new_key_pressed)
		

class preference_Window:
	"""Class for Preferences window"""
	def delete_event(self, widget):
		"""close window"""
		self.window.destroy()

	def on_color_button_clicked(self, widget):
		"""Open a ColorSelectionDialog and change button's color"""
		if widget.name == 'colorIn':
			color = self.colorIn
			da = self.da_in
		elif widget.name == 'colorOut':
			color = self.colorOut
			da = self.da_out
		elif widget.name == 'colorStatus':
			color = self.colorStatus
			da = self.da_status
		colorseldlg = gtk.ColorSelectionDialog('Select Color')
		colorsel = colorseldlg.colorsel
		colorsel.set_previous_color(color)
		colorsel.set_current_color(color)
		colorsel.set_has_palette(gtk.TRUE)
		response = colorseldlg.run()
		if response == gtk.RESPONSE_OK:
			color = colorsel.get_current_color()
			da.modify_bg(gtk.STATE_NORMAL, color)
			if widget.name == 'colorIn':
				self.colorIn = color
			elif widget.name == 'colorOut':
				self.colorOut = color
			elif widget.name == 'colorStatus':
				self.colorStatus = color
		colorseldlg.destroy()
	
	def write_cfg(self):
		"""Save preferences in config File and apply them"""
		#Color for incomming messages
		colSt = '#'+(hex(self.colorIn.red)+'0')[2:4]\
			+(hex(self.colorIn.green)+'0')[2:4]\
			+(hex(self.colorIn.blue)+'0')[2:4]
		self.r.plugin.config['inmsgcolor'] = colSt
		for j in self.r.tab_messages.keys():
			self.r.tab_messages[j].tagIn.set_property("foreground", colSt)
		#Color for outgoing messages
		colSt = '#'+(hex(self.colorOut.red)+'0')[2:4]\
			+(hex(self.colorOut.green)+'0')[2:4]\
			+(hex(self.colorOut.blue)+'0')[2:4]
		self.r.plugin.config['outmsgcolor'] = colSt
		for j in self.r.tab_messages.keys():
			self.r.tab_messages[j].tagOut.set_property("foreground", colSt)
		#Color for status messages
		colSt = '#'+(hex(self.colorStatus.red)+'0')[2:4]\
			+(hex(self.colorStatus.green)+'0')[2:4]\
			+(hex(self.colorStatus.blue)+'0')[2:4]
		self.r.plugin.config['statusmsgcolor'] = colSt
		for j in self.r.tab_messages.keys():
			self.r.tab_messages[j].tagStatus.set_property("foreground", colSt)
		#IconStyle
		ist = self.combo_iconstyle.entry.get_text()
		self.r.plugin.config['iconstyle'] = ist
		self.r.iconstyle = ist
		self.r.mkpixbufs()
		#autopopup
		pp = self.chk_autopp.get_active()
		if pp == True:
			self.r.plugin.config['autopopup'] = 1
			self.r.autopopup = 1
		else:
			self.r.plugin.config['autopopup'] = 0
			self.r.autopopup = 0
		#autoaway
		aw = self.chk_autoaway.get_active()
		if aw == True:
			self.r.plugin.config['autoaway'] = 1
			self.r.plugin.autoaway = 1
		else:
			self.r.plugin.config['autoaway'] = 0
			self.r.plugin.autoaway = 0
		aat = self.spin_autoawaytime.get_value_as_int()
		self.r.plugin.autoawaytime = aat
		self.r.plugin.config['autoawaytime'] = aat
		#autoxa
		xa = self.chk_autoxa.get_active()
		if xa == True:
			self.r.plugin.config['autoxa'] = 1
			self.r.plugin.autoxa = 1
		else:
			self.r.plugin.config['autoxa'] = 0
			self.r.plugin.autoxa = 0
		axt = self.spin_autoxatime.get_value_as_int()
		self.r.plugin.autoxatime = axt
		self.r.plugin.config['autoxatime'] = axt
		if self.r.plugin.sleeper:
			self.r.plugin.sleeper = common.sleepy.Sleepy(\
				self.r.plugin.autoawaytime*60, self.r.plugin.autoxatime*60)
		self.r.queueOUT.put(('CONFIG', ('GtkGui', self.r.plugin.config)))

		self.r.redraw_roster()
		
	def on_ok(self, widget):
		"""When Ok button is clicked"""
		self.write_cfg()
		self.window.destroy()

	def change_notebook_page(self, number):
		self.notebook.set_current_page(number)

	def on_lookfeel_button_clicked(self, widget, data=None):
		self.change_notebook_page(0)
		
	def on_events_button_clicked(self, widget, data=None):
		self.change_notebook_page(1)
		
	def on_presence_button_clicked(self, widget, data=None):
		self.change_notebook_page(2)

	def __init__(self, roster):
		"""Initialize Preference window"""
		xml = gtk.glade.XML(GTKGUI_GLADE, 'preferences_window')
		self.window = xml.get_widget('preferences_window')
		self.r = roster
		self.da_in = xml.get_widget('drawing_in')
		self.da_out = xml.get_widget('drawing_out')
		self.da_status = xml.get_widget('drawing_status')
		self.combo_iconstyle = xml.get_widget('combo_iconstyle')
		self.chk_autopp = xml.get_widget('chk_autopopup')
		self.chk_autoaway = xml.get_widget('chk_autoaway')
		self.spin_autoawaytime = xml.get_widget('spin_autoawaytime')
		self.chk_autoxa = xml.get_widget('chk_autoxa')
		self.spin_autoxatime = xml.get_widget('spin_autoxatime')
		self.notebook = xml.get_widget('preferences_notebook')
		
		button = xml.get_widget('lookfeel_button')
		button.connect('clicked', self.on_lookfeel_button_clicked)
		button = xml.get_widget('events_button')
		button.connect('clicked', self.on_events_button_clicked)
		button = xml.get_widget('presence_button')
		button.connect('clicked', self.on_presence_button_clicked)

		#Color for incomming messages
		colSt = self.r.plugin.config['inmsgcolor']
		if not colSt:
			colSt = '#ff0000'
		cmapIn = self.da_in.get_colormap()
		self.colorIn = cmapIn.alloc_color(colSt)
		self.da_in.window.set_background(self.colorIn)
		
		#Color for outgoing messages
		colSt = self.r.plugin.config['outmsgcolor']
		if not colSt:
			colSt = '#0000ff'
		cmapOut = self.da_out.get_colormap()
		self.colorOut = cmapOut.alloc_color(colSt)
		self.da_out.window.set_background(self.colorOut)
		
		#Color for status messages
		colSt = self.r.plugin.config['statusmsgcolor']
		if not colSt:
			colSt = '#00ff00'
		cmapStatus = self.da_status.get_colormap()
		self.colorStatus = cmapStatus.alloc_color(colSt)
		self.da_status.window.set_background(self.colorStatus)
		
		#iconStyle
		list_style = os.listdir('plugins/gtkgui/icons/')
		l = []
		for i in list_style:
			if i != 'CVS':
				l.append(i)
		if l.count == 0:
			l.append(" ")
		self.combo_iconstyle.set_popdown_strings(l)
		if self.r.iconstyle in l:
			self.combo_iconstyle.entry.set_text(self.r.iconstyle)
		
		#Autopopup
		st = 0
		if self.r.plugin.config.has_key('autopopup'):
			st = self.r.plugin.config['autopopup']
		self.chk_autopp.set_active(st)

		#Autoaway
		st = 1
		if self.r.plugin.config.has_key('autoaway'):
			st = self.r.plugin.config['autoaway']
		self.chk_autoaway.set_active(st)

		#Autoawaytime
		st = 10
		if self.r.plugin.config.has_key('autoawaytime'):
			st = self.r.plugin.config['autoawaytime']
		self.spin_autoawaytime.set_value(st)

		#Autoxa
		st = 1
		if self.r.plugin.config.has_key('autoxa'):
			st = self.r.plugin.config['autoxa']
		self.chk_autoxa.set_active(st)

		#Autoxatime
		st = 20
		if self.r.plugin.config.has_key('autoxatime'):
			st = self.r.plugin.config['autoxatime']
		self.spin_autoxatime.set_value(st)

		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_but_col_clicked', \
			self.on_color_button_clicked)
		xml.signal_connect('on_ok_clicked', self.on_ok)

class awayMsg_Window:
	"""Class for Away Message Window"""
	def delete_event(self, widget):
		"""close window"""
		self.window.destroy()

	def on_ok(self):
		"""When Ok button is clicked"""
		beg, end = self.txtBuffer.get_bounds()
		self.msg = self.txtBuffer.get_text(beg, end, 0)
		self.window.destroy()
	
	def run(self):
		"""Wait for Ok button to be pressed and return away messsage"""
		rep = self.window.run()
		msg = ''
		if rep == gtk.RESPONSE_OK:
			beg, end = self.txtBuffer.get_bounds()
			msg = self.txtBuffer.get_text(beg, end, 0)
			self.window.destroy()
		return msg
	
	def __init__(self):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Away_msg')
		self.window = xml.get_widget("Away_msg")
		txt = xml.get_widget("textview")
		self.txtBuffer = txt.get_buffer()
		xml.signal_connect('gtk_widget_destroy', self.delete_event)

class addContact_Window:
	"""Class for Add user window"""
	def delete_event(self, widget):
		"""close window"""
		self.Wadd.destroy()

	def on_subscribe(self, widget):
		"""When Subscribe button is clicked"""
		who = self.entry_who.get_text()
		buf = self.textview_sub.get_buffer()
		start_iter = buf.get_start_iter()
		end_iter = buf.get_end_iter()
		txt = buf.get_text(start_iter, end_iter, 0)
		self.r.req_sub(self, who, txt)
		self.delete_event(self)
		
	def __init__(self, roster, jid=None):
		self.r = roster
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Add')
		self.entry_who = xml.get_widget('entry_who')
		self.textview_sub = xml.get_widget("textview_sub")
		if jid:
			 self.entry_who.set_text(jid)
		self.Wadd = xml.get_widget("Add")
		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_button_sub_clicked', self.on_subscribe)

class warning_Window:
	"""Class for warning window : print a warning message"""
	def delete_event(self, widget):
		"""close window"""
		self.window.destroy()
	
	def __init__(self, txt):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Warning')
		self.window = xml.get_widget("Warning")
		xml.get_widget('label').set_text(txt)
		xml.signal_connect('gtk_widget_destroy', self.delete_event)

class about_Window:
	"""Class for about window"""
	def delete_event(self, widget):
		"""close window"""
		self.Wabout.destroy()
		
	def __init__(self):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'About')
		self.Wabout = xml.get_widget("About")
		xml.signal_connect('gtk_widget_destroy', self.delete_event)

class accountPreference_Window:
	"""Class for account informations"""
	def delete_event(self, widget):
		"""close window"""
		self.window.destroy()
	
	def init_account(self, infos):
		"""Initialize window with defaults values"""
		if infos.has_key('name'):
			self.entryName.set_text(infos['name'])
		if infos.has_key('jid'):
			self.entryJid.set_text(infos['jid'])
		if infos.has_key('password'):
			self.entryPass.set_text(infos['password'])
		if infos.has_key('ressource'):
			self.entryRessource.set_text(infos['ressource'])

	def on_save_clicked(self, widget):
		"""When save button is clicked : Save informations in config file"""
		name = self.entryName.get_text()
		jid = self.entryJid.get_text()
		if (name == ''):
			warning_Window('You must enter a name for this account')
			return 0
		if (jid == '') or (string.count(jid, '@') != 1):
			warning_Window('You must enter a Jabber ID for this account\n\
				For example : login@hostname')
			return 0
		else:
			(login, hostname) = string.split(jid, '@')
		#if we are modifying an account
		if self.mod:
			#if we modify the name of the account
			if name != self.acc:
				del self.accs.r.plugin.accounts[self.acc]
		#if it's a new account
		else:
			if name in self.accs.r.accounts:
				warning_Window('An account already has this name')
				return 0
			#if we neeed to register a new account
			if self.check.get_active():
				self.accs.r.queueOUT.put(('NEW_ACC', (hostname, login, \
					self.entryPass.get_text(), name, \
					self.entryRessource.get_text())))
				self.check.set_active(FALSE)
				return 1
		self.accs.r.plugin.accounts[name] = {'name': login, 'hostname': hostname,\
			'password': self.entryPass.get_text(), 'ressource': \
			self.entryRessource.get_text()}
		self.accs.r.queueOUT.put(('CONFIG', ('accounts', \
			self.accs.r.plugin.accounts)))
		self.accs.init_accounts()
		self.delete_event(self)
	
	#info must be a dictionnary
	def __init__(self, accs, infos = {}):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Account')
		self.window = xml.get_widget("Account")
		self.entryPass = xml.get_widget("entry_password")
		self.entryRessource = xml.get_widget("entry_ressource")
		self.check = xml.get_widget("checkbutton")
		self.entryName = xml.get_widget("entry_name")
		self.entryJid = xml.get_widget("entry_jid")
		self.accs = accs
		self.mod = FALSE
		if infos:
			self.mod = TRUE
			self.acc = infos['name']
			self.init_account(infos)
			self.check.set_sensitive(FALSE)
		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_save_clicked', self.on_save_clicked)

class accounts_Window:
	"""Class for accounts window : lists of accounts"""
	def delete_event(self, widget):
		"""close window"""
		global accountsWindow
		accountsWindow = 0
		self.window.destroy()
		
	def init_accounts(self):
		"""initialize listStore with existing accounts"""
		model = self.treeview.get_model()
		model.clear()
		for account in self.r.plugin.accounts.keys():
			iter = model.append()
			model.set(iter, 0, account, 1, \
				self.r.plugin.accounts[account]["hostname"])

	def on_row_activated(self, widget):
		"""Activate delete and modify buttons when a row is selected"""
		self.modButt.set_sensitive(TRUE)
		self.delButt.set_sensitive(TRUE)

	def on_new_clicked(self, widget):
		"""When new button is clicked : open an account information window"""
		accountPreference_Window(self)

	def on_delete_clicked(self, widget):
		"""When delete button is clicked :
		Remove an account from the listStore and from the config file"""
		sel = self.treeview.get_selection()
		(mod, iter) = sel.get_selected()
		model = self.treeview.get_model()
		account = model.get_value(iter, 0)
		del self.r.plugin.accountsi[account]
		self.r.queueOUT.put(('CONFIG', ('accounts', self.r.plugin.accounts)))
		self.init_accounts()

	def on_modify_clicked(self, widget):
		"""When modify button is clicked :
		open the account information window for this account"""
		infos = {}
		sel = self.treeview.get_selection()
		model = self.treeview.get_model()
		(mod, iter) = sel.get_selected()
		account = model.get_value(iter, 0)
		infos['name'] = account
		infos['jid'] = self.r.plugin.accounts[account]["name"] + \
			'@' +  self.r.plugin.accounts[account]["hostname"]
		infos['password'] = self.r.plugin.accounts[account]["password"]
		infos['ressource'] = self.r.plugin.accounts[account]["ressource"]
		accountPreference_Window(self, infos)
		
	def __init__(self, roster):
		self.r = roster
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Accounts')
		self.window = xml.get_widget("Accounts")
		self.treeview = xml.get_widget("treeview")
		self.modButt = xml.get_widget("modify_button")
		self.delButt = xml.get_widget("delete_button")
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 0)
		self.treeview.insert_column_with_attributes(-1, 'Name', renderer, text=0)
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 1)
		self.treeview.insert_column_with_attributes(-1, 'Server', \
			renderer, text=1)
		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_row_activated', self.on_row_activated)
		xml.signal_connect('on_new_clicked', self.on_new_clicked)
		xml.signal_connect('on_delete_clicked', self.on_delete_clicked)
		xml.signal_connect('on_modify_clicked', self.on_modify_clicked)
		self.init_accounts()

class confirm_Window:
	"""Class for confirmation window :
	window that appears to confirm the removal of a contact"""
	def delete_event(self, widget):
		"""close window"""
		self.window.destroy()
		
	def req_usub(self, widget):
		"""When Ok button is clicked :
		Send a message to the core to remove the user
		and remove it from the roster"""
		model = self.r.tree.get_model()
		jid = model.get_value(self.iter, 2)
		self.r.queueOUT.put(('UNSUB', jid))
		self.r.remove_user(self.r.l_contact[jid]['user'])
		del self.r.l_contact[jid]
		self.delete_event(self)
	
	def __init__(self, roster, iter):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Confirm')
		self.window = xml.get_widget('Confirm')
		self.r = roster
		self.iter = iter
		jid = self.r.tree.get_model().get_value(iter, 2)
		xml.get_widget('label_confirm').set_text(\
			'Are you sure you want to remove ' + jid + ' from your roster ?')
		xml.signal_connect('on_okbutton_clicked', self.req_usub)
		xml.signal_connect('gtk_widget_destroy', self.delete_event)

class authorize_Window:
	"""Class for authorization window :
	window that appears when a user wants to add us to his/her roster"""
	def delete_event(self, widget):
		"""close window"""
		self.window.destroy()
		
	def auth(self, widget):
		"""Accept the request"""
		self.r.queueOUT.put(('AUTH', self.jid))
		self.delete_event(self)
		if not self.r.l_contact.has_key(self.jid):
			addContact_Window(self.r, self.jid)
	
	def deny(self, widget):
		"""refuse the request"""
		self.r.queueOUT.put(('DENY', self.jid))
		self.delete_event(self)
	
	def __init__(self, roster, jid):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Sub_req')
		self.window = xml.get_widget('Sub_req')
		self.r = roster
		self.jid = jid
		xml.get_widget('label').set_text('Subscription request from ' + self.jid)
		xml.signal_connect('on_button_auth_clicked', self.auth)
		xml.signal_connect('on_button_deny_clicked', self.deny)
		xml.signal_connect('on_button_close_clicked', self.delete_event)

class agentRegistration_Window:
	"""Class for agent registration window :
	window that appears when we want to subscribe to an agent"""
	def delete_event(self, widget):
		"""close window"""
		self.window.destroy()
	
	def draw_table(self):
		"""Draw the table in the window"""
		nbrow = 0
		for name in self.infos.keys():
			if name != 'key' and name != 'instructions' and name != 'x':
				nbrow = nbrow + 1
				self.table.resize(rows=nbrow, columns=2)
				label = gtk.Label(name)
				self.table.attach(label, 0, 1, nbrow-1, nbrow, 0, 0, 0, 0)
				entry = gtk.Entry()
				entry.set_text(self.infos[name])
				self.table.attach(entry, 1, 2, nbrow-1, nbrow, 0, 0, 0, 0)
				self.entries[name] = entry
				if nbrow == 1:
					entry.grab_focus()
		self.table.show_all()
	
	def on_ok(self, widget):
		"""When Ok button is clicked :
		send registration info to the core"""
		for name in self.entries.keys():
			self.infos[name] = self.entries[name].get_text()
		self.r.queueOUT.put(('REG_AGENT', self.agent))
		self.delete_event(self)
	
	def __init__(self, agent, infos, roster):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'agent_reg')
		self.agent = agent
		self.infos = infos
		self.r = roster
		self.window = xml.get_widget('agent_reg')
		self.table = xml.get_widget('table')
		self.window.set_title('Register to ' + agent)
		xml.get_widget('label').set_text(infos['instructions'])
		self.entries = {}
		self.draw_table()
		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_button_cancel_clicked', self.delete_event)
		xml.signal_connect('on_button_ok_clicked', self.on_ok)

class browseAgent_Window:
	"""Class for bowser agent window :
	to know the agents on the selected server"""
	def delete_event(self, widget):
		"""close window"""
		global browserWindow
		browserWindow = 0
		self.window.destroy()

	def browse(self):
		"""Send a request to the core to know the available agents"""
		self.r.queueOUT.put(('REQ_AGENTS', None))
	
	def agents(self, agents):
		"""When list of available agent arrive :
		Fill the treeview with it"""
		model = self.treeview.get_model()
		for jid in agents.keys():
			iter = model.append()
			model.set(iter, 0, agents[jid]['name'], 1, agents[jid]['service'])

	def on_refresh(self, widget):
		"""When refresh button is clicked :
		refresh list : clear and rerequest it"""
		self.treeview.get_model().clear()
		self.browse()

	def on_row_activated(self, widget, path, col=0):
		"""When a row is activated :
		Ask specific informations about the selected agent and close the window"""
		model = self.treeview.get_model()
		iter = model.get_iter(path)
		service = model.get_value(iter, 1)
		self.r.queueOUT.put(('REQ_AGENT_INFO', service))
		self.delete_event(self)
		
	def __init__(self, roster):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'browser')
		self.window = xml.get_widget('browser')
		self.treeview = xml.get_widget('treeview')
		self.r = roster
		model = gtk.ListStore(gobject.TYPE_STRING, gobject.TYPE_STRING)
		self.treeview.set_model(model)
		#columns
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 0)
		self.treeview.insert_column_with_attributes(-1, 'Name', renderer, text=0)
		renderer = gtk.CellRendererText()
		renderer.set_data('column', 1)
		self.treeview.insert_column_with_attributes(-1, 'Service', \
			renderer, text=1)

		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_refresh_clicked', self.on_refresh)
		xml.signal_connect('on_row_activated', self.on_row_activated)
		if self.r.connected:
			self.browse()
		else:
			warning_Window("You must be connected to view Agents")

class message_Window:
	"""Class for chat window"""
	def delete_event(self, widget):
		"""close window"""
		del self.r.tab_messages[self.user.jid]
		self.window.destroy()
	
	def print_conversation(self, txt, contact = None, tim = None):
		"""Print a line in the conversation :
		if contact is set to status : it's a status message
		if contact is set to another value : it's an outgoing message
		if contact is not set : it's an incomming message"""
		buffer = self.conversation.get_buffer()
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
				buffer.insert_with_tags_by_name(end_iter, '<moi> ', 'outgoing')
				buffer.insert(end_iter, txt+'\n')
		else:
			buffer.insert_with_tags_by_name(end_iter, '<' + \
				self.user.name + '> ', 'incoming')
			buffer.insert(end_iter, txt+'\n')
		#scroll to the end of the textview
		self.conversation.scroll_to_mark(\
			buffer.get_mark('end'), 0.1, 0, 0, 0)
	
	def read_queue(self, q):
		"""read queue and print messages containted in it"""
		while not q.empty():
			evt = q.get()
			self.print_conversation(evt[0], tim = evt[1])
		del self.r.tab_queues[self.user.jid]
		for i in self.r.l_contact[self.user.jid]['iter']:
			if self.r.pixbufs.has_key(self.user.show):
				self.r.tree.get_model().set_value(i, 0, \
					self.r.pixbufs[self.user.show])

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
				self.r.queueOUT.put(('MSG',(self.user.jid, txt)))
				txt_buffer.set_text('', -1)
				self.print_conversation(txt, self.user.jid)
				widget.grab_focus()
			return 1
		return 0

	def on_clear(self, widget):
		"""When clear button is pressed :
		clear the conversation"""
		buffer = self.conversation.get_buffer()
		deb, end = buffer.get_bounds()
		buffer.delete(deb, end)

	def __init__(self, user, roster):
		self.user = user
		self.r = roster
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Chat')
		self.hbox = xml.get_widget('hbox1')
		self.hbox.set_property('resize-mode', 2)
		self.window = xml.get_widget('Chat')
		self.window.set_title('Chat with ' + user.name)
		self.img = xml.get_widget('image')
		self.img.set_from_pixbuf(self.r.pixbufs[user.show])
		xml.get_widget('button_contact').set_label(user.name + ' <'\
			+ user.jid + '>')
		xml.get_widget('button_contact').set_resize_mode(gtk.RESIZE_QUEUE)
		self.message = xml.get_widget('message')
		self.message.grab_focus()
		self.conversation = xml.get_widget('conversation')
		buffer = self.conversation.get_buffer()
		end_iter = buffer.get_end_iter()
		buffer.create_mark('end', end_iter, 0)
		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_clear_button_clicked', self.on_clear)
		xml.signal_connect('on_msg_key_press_event', self.on_msg_key_press_event)
		self.tagIn = buffer.create_tag("incoming")
		color = self.r.plugin.config['inmsgcolor']
		if not color:
			color = '#ff0000' #red
		self.tagIn.set_property("foreground", color)
		self.tagOut = buffer.create_tag("outgoing")
		color = self.r.plugin.config['outmsgcolor']
		if not color:
			color = '#0000ff' #blue
		self.tagOut.set_property("foreground", color)
		self.tagStatus = buffer.create_tag("status")
		color = self.r.plugin.config['statusmsgcolor']
		if not color:
			color = '#00ff00' #green
		self.tagStatus.set_property("foreground", color)

class roster_Window:
	"""Class for main gtk window"""
	def add_user(self, u):
		"""Add a user to the roster and add groups if they aren't in roster"""
		newgrp = 0
		self.l_contact[u.jid] = {'user': u, 'iter': []}
		if u.groups == []:
			if string.find(u.jid, "@") <= 0:
				u.groups.append('Agents')
			else:
				u.groups.append('general')
		if u.show != 'offline' or self.showOffline or 'Agents' in u.groups:
			model = self.tree.get_model()
			for g in u.groups:
				if not self.l_group.has_key(g):
					self.l_group[g] = {'iter':None, 'hide':False}
				if not self.l_group[g]['iter']:
					iterG = model.append(None, (self.pixbufs['closed'], g, \
						'group', FALSE, self.grpbgcolor, TRUE))
					self.l_group[g] = {'iter':iterG, 'hide':False}
					newgrp = 1
				if g == 'Agents':
					iterU = model.append(self.l_group[g]['iter'], \
						(self.pixbufs[u.show], u.name, 'agent', FALSE, \
						self.userbgcolor, TRUE))
				else:
					iterU = model.append(self.l_group[g]['iter'], \
						(self.pixbufs[u.show], u.name, u.jid, TRUE, \
						self.userbgcolor, TRUE))
				self.l_contact[u.jid]['iter'].append(iterU)
				if newgrp == 1:
					#expand new groups
					self.tree.expand_row(model.get_path(iterG), FALSE)
	
	def remove_user(self, u):
		model = self.tree.get_model()
		for i in self.l_contact[u.jid]['iter']:
			parent_i = model.iter_parent(i)
			if model.iter_n_children(parent_i) == 1:
				model.remove(i)
				grp = model.get_value(parent_i, 1)
				model.remove(parent_i)
				self.l_group[grp]['iter'] = None
			else:
				model.remove(i)
		self.l_contact[u.jid]['iter'] = []
		

	def redraw_roster(self):
		"""clear l_contact and l_group's iter and redraw roster"""
		for j in self.l_contact.keys():
			self.l_contact[j]['iter'] = []
		for g in self.l_group.keys():
			self.l_group[g]['iter'] = None
		self.draw_roster()

	def draw_roster(self):
		"""Clear and draw roster"""
		self.tree.get_model().clear()
		for j in self.l_contact.keys():
			self.add_user(self.l_contact[j]['user'])
	
	def mklists(self, tab):
		"""fill l_contact and l_group"""
		for jid in tab.keys():
			#remove ressource from jid string
			ji = string.split(jid, '/')[0]
			name = tab[jid]['name']
			if not name:
				if string.find(ji, "@") <= 0:
					name = ji
				else:
					name = string.split(jid, '@')[0]
			show = tab[jid]['show']
			if not show:
				show = 'offline'
			user1 = user(ji, name, tab[jid]['groups'], show, \
				tab[jid]['status'], tab[jid]['sub'], '')
			self.l_contact[ji] = {'user':user1, 'iter':[]}
			for i in tab[jid]['groups'] :
				if not i in self.l_group.keys():
					self.l_group[i] = {'iter':None, 'hide':False}
			#update icon if chat window is oppened
			if self.tab_messages.has_key(jid):
				self.tab_messages[jid].user = user1
				self.tab_messages[jid].img.set_from_pixbuf(self.pixbufs[show])

	def chg_status(self, jid, show, status):
		"""When a user change his status remove or change its icon"""
		u = self.l_contact[jid]['user']
		if self.l_contact[jid]['iter'] == []:
			self.add_user(u)
		else:
			model = self.tree.get_model()
			if show == 'offline' and not self.showOffline:
				self.remove_user(u)
			else:
				for i in self.l_contact[jid]['iter']:
					if self.pixbufs.has_key(show):
						model.set_value(i, 0, self.pixbufs[show])
			#update icon in chat window
			if self.tab_messages.has_key(jid):
				self.tab_messages[jid].img.set_from_pixbuf(self.pixbufs[show])
		u.show = show
		u.status = status

	def on_info(self, widget, jid):
		"""Call infoUser_Window class to display user's information"""
		infoUser_Window(self.l_contact[jid]['user'], self)
	
	def mk_menu_c(self, event, iter):
		"""Make user's popup menu"""
		model = self.tree.get_model()
		jid = model.get_value(iter, 2)
		path = model.get_path(iter)
		self.menu_c = gtk.Menu()
		item = gtk.MenuItem("Start chat")
		self.menu_c.append(item)
		item.connect("activate", self.on_row_activated, path)
		item = gtk.MenuItem("Rename")
		self.menu_c.append(item)
		#item.connect("activate", self.on_rename, iter)
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
		item.connect("activate", self.req_sub, jid, \
			'I would like to add you to my contact list, please.')
		
		item = gtk.MenuItem()
		self.menu_c.append(item)
		item = gtk.MenuItem("Remove")
		self.menu_c.append(item)
		item.connect("activate", self.on_req_usub, iter)

		item = gtk.MenuItem()
		self.menu_c.append(item)
		item = gtk.MenuItem("Informations")
		self.menu_c.append(item)
		item.connect("activate", self.on_info, jid)

		self.menu_c.popup(None, None, None, event.button, event.time)
		self.menu_c.show_all()

	def mk_menu_g(self, event):
		"""Make group's popup menu"""
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
		"""Authorize a user"""
		self.queueOUT.put(('AUTH', jid))

	def req_sub(self, widget, jid, txt):
		"""Request subscription to a user"""
		self.queueOUT.put(('SUB', (jid, txt)))
		if not self.l_contact.has_key(jid):
			user1 = user(jid, jid, ['general'], 'requested', \
				'requested', 'sub', '')
			self.add_user(user1)
	
	def init_tree(self):
		"""initialize treeview, l_contact and l_group"""
		self.tree.get_model().clear()
		#l_contact = {jid:{'user':_, 'iter':[iter1, ...]]
		self.l_contact = {}
		#l_group = {name:{'iter':_, 'hide':Bool}
		self.l_group = {}

	def on_treeview_event(self, widget, event):
		"""popup user's group's or agent menu"""
		if (event.button == 3) & (event.type == gtk.gdk.BUTTON_PRESS):
			try:
				path, column, x, y = self.tree.get_path_at_pos(int(event.x), \
					int(event.y))
			except TypeError:
				return
			model = self.tree.get_model()
			iter = model.get_iter(path)
			data = model.get_value(iter, 2)
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
		"""Remove a user"""
		window_confirm = confirm_Window(self, iter)

	def on_status_changed(self, widget):
		"""When we change our status"""
		if widget.name != 'online' and widget.name != 'offline':
			w = awayMsg_Window()
			txt = w.run()
		else:
			txt = widget.name
		self.queueOUT.put(('STATUS',(widget.name, txt, \
			self.plugin.accounts.keys()[0])))

	def on_prefs(self, widget):
		"""When preferences is selected :
		call the preference_Window class"""
		window = preference_Window(self)

	def on_add(self, widget):
		"""When add user is selected :
		call the add class"""
		window_add = addContact_Window(self)

	def on_about(self, widget):
		"""When about is selected :
		call the about class"""
		window_about = about_Window()

	def on_accounts(self, widget):
		"""When accounts is seleted :
		call the accounts class to modify accounts"""
		global accountsWindow
		if not accountsWindow:
			accountsWindow = accounts_Window(self)
	
	def on_quit(self, widget):
		"""When we quit the gtk plugin :
		tell that to the core and exit gtk"""
		self.queueOUT.put(('QUIT',''))
		print "plugin gtkgui stopped"
		gtk.mainquit()

	def on_row_activated(self, widget, path, col=0):
		"""When an iter is dubble clicked :
		open the chat window"""
		model = self.tree.get_model()
		iter = model.get_iter(path)
		jid = model.get_value(iter, 2)
		if (jid == 'group'):
			if (self.tree.row_expanded(path)):
				self.tree.collapse_row(path)
			else:
				self.tree.expand_row(path, FALSE)
		else:
			if self.tab_messages.has_key(jid):
				self.tab_messages[jid].window.present()
			elif self.l_contact.has_key(jid):
				self.tab_messages[jid] = message_Window(self.l_contact[jid]['user'], self)
				if self.tab_queues.has_key(jid):
					self.tab_messages[jid].read_queue(self.tab_queues[jid])

	def on_row_expanded(self, widget, iter, path):
		"""When a row is expanded :
		change the icon of the arrow"""
		self.tree.get_model().set_value(iter, 0, self.pixbufs['opened'])
	
	def on_row_collapsed(self, widget, iter, path):
		"""When a row is collapsed :
		change the icon of the arrow"""
		self.tree.get_model().set_value(iter, 0, self.pixbufs['closed'])

	def on_cell_edited (self, cell, row, new_text):
		"""When an iter is editer :
		if text has changed, rename the user
		else open chat window"""
		model = self.tree.get_model()
		iter = model.get_iter_from_string(row)
		jid = model.get_value(iter, 2)
		old_text = self.l_contact[jid]['user'].name
		#If it is a double click, old_text == new_text
		if old_text == new_text:
			if self.tab_messages.has_key(jid):
				self.tab_messages[jid].window.present()
			elif self.l_contact.has_key(jid):
				self.tab_messages[jid] = message_Window(self.l_contact[jid]['user'], self)
				if self.tab_queues.has_key(jid):
					self.tab_messages[jid].read_queue(self.tab_queues[jid])
		else:
			model.set_value(iter, 1, new_text)
			self.l_contact[jid]['user'].name = new_text
			self.queueOUT.put(('UPDUSER', (jid, new_text, \
				self.l_contact[jid]['user'].groups)))
		
	def on_browse(self, widget):
		"""When browse agent is selected :
		Call browse class"""
		global browserWindow
		if not browserWindow:
			browserWindow = browseAgent_Window(self)

	def mkpixbufs(self):
		"""initialise pixbufs array"""
		self.path = 'plugins/gtkgui/icons/' + self.iconstyle + '/'
		self.pixbufs = {}
		for state in ('online', 'away', 'xa', 'dnd', 'offline', \
			'requested', 'message', 'opened', 'closed', 'not in list'):
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
					fct = gtk.gdk.pixbufAnimation
				pix = fct(file)
				self.pixbufs[state] = pix
				break

	def on_show_off(self, widget):
		"""when show offline option is changed :
		redraw the treeview"""
		self.showOffline = 1 - self.showOffline
		self.redraw_roster()

	def __init__(self, queueOUT, plug):
		# FIXME : handle no file ...
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Gajim')
		self.window =  xml.get_widget('Gajim')
		self.tree = xml.get_widget('treeview')
		self.plugin = plug
		self.connected = 0
		#(icon, name, jid, editable, background color, show_icon)
		model = gtk.TreeStore(gtk.gdk.Pixbuf, str, str, \
			gobject.TYPE_BOOLEAN, str, gobject.TYPE_BOOLEAN)
		self.tree.set_model(model)
		self.init_tree()
		self.iconstyle = self.plugin.config['iconstyle']
		if not self.iconstyle:
			self.iconstyle = 'sun'
		self.mkpixbufs()
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
		self.optionmenu = xml.get_widget('optionmenu')
		self.optionmenu.set_history(6)
		self.tab_messages = {}
		self.tab_queues = {}

		if self.plugin.config.has_key('showoffline'):
			self.showOffline = self.plugin.config['showoffline']
		else:
			self.showOffline = 0

		xml.get_widget('show_offline').set_active(self.showOffline)

		self.grpbgcolor = 'gray50'
		self.userbgcolor = 'white'

		#columns
		col = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand = False)
		col.add_attribute(render_pixbuf, 'pixbuf', 0)
		col.add_attribute(render_pixbuf, 'cell-background', 4)
		col.add_attribute(render_pixbuf, 'visible', 5)
		render_text = gtk.CellRendererText()
		render_text.connect('edited', self.on_cell_edited)
		col.pack_start(render_text, expand = True)
		col.add_attribute(render_text, 'text', 1)
		col.add_attribute(render_text, 'cell-background', 4)
		col.add_attribute(render_text, 'editable', 3)
		self.tree.append_column(col)
		col = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand = False)
		self.tree.append_column(col)
		col.set_visible(FALSE)
		self.tree.set_expander_column(col)

		#signals
		xml.signal_connect('gtk_main_quit', self.on_quit)
		xml.signal_connect('on_preferences_activate', self.on_prefs)
		xml.signal_connect('on_accounts_activate', self.on_accounts)
		xml.signal_connect('on_browse_agents_activate', self.on_browse)
		xml.signal_connect('on_add_activate', self.on_add)
		xml.signal_connect('on_show_offline_activate', self.on_show_off)
		xml.signal_connect('on_about_activate', self.on_about)
		xml.signal_connect('on_quit_activate', self.on_quit)
		xml.signal_connect('on_treeview_event', self.on_treeview_event)
		xml.signal_connect('on_status_changed', self.on_status_changed)
		xml.signal_connect('on_row_activated', self.on_row_activated)
		xml.signal_connect('on_row_expanded', self.on_row_expanded)
		xml.signal_connect('on_row_collapsed', self.on_row_collapsed)

class plugin:
	"""Class called by the core in a new thread"""
	def wait(self, what):
		"""Wait for a message from Core"""
		#TODO: timeout
		temp_q = Queue.Queue(50)
		while 1:
			if not self.queueIN.empty():
				ev = self.queueIN.get()
				if ev[0] == what and ev[1][0] == 'GtkGui':
					#Restore messages
					while not temp_q.empty():
						ev2 = temp_q.get()
						self.queueIN.put(ev)
					return ev[1][1]
				else:
					#Save messages
					temp_q.put(ev)
			time.sleep(0.1)
		
	def read_queue(self):
		"""Read queue from the core and execute commands from it"""
		global browserWindow
		model = self.r.tree.get_model()
		while self.queueIN.empty() == 0:
			ev = self.queueIN.get()
			if ev[0] == 'ROSTER':
				self.r.init_tree()
				self.r.mklists(ev[1])
				self.r.draw_roster()
			elif ev[0] == 'WARNING':
				warning_Window(ev[1])
			elif ev[0] == 'STATUS':
				st = ""
				for i in range(7):
					if self.r.optionmenu.get_menu().get_children()[i].name == ev[1]:
						st = self.r.optionmenu.get_menu().get_children()[i].name
						self.r.optionmenu.set_history(i)
						break
				if st == 'offline':
					self.r.connected = 0
					self.sleeper = None
					for j in self.r.l_contact.keys():
						self.r.chg_status(j, 'offline', 'Disconnected')
				elif self.r.connected == 0:
					self.r.connected = 1
					self.sleeper = None#common.sleepy.Sleepy(\
						#self.autoawaytime*60, self.autoxatime*60)

			elif ev[0] == 'NOTIFY':
				jid = string.split(ev[1][0], '/')[0]
				res = ev[1][3]
				if not res:
					res = ''
				if string.find(jid, "@") <= 0:
					#It must be an agent
					ji = string.replace(jid, '@', '')
				else:
					ji = jid
				#Update user
				if self.r.l_contact.has_key(ji):
					u = self.r.l_contact[ji]['user']
					u.show = ev[1][1]
					u.status = ev[1][2]
					u.resource = res
					#Print status in chat window
					if self.r.tab_messages.has_key(ji):
						self.r.tab_messages[ji].print_conversation(\
							"%s is now %s (%s)" % (u.name, ev[1][1], \
								ev[1][2]), 'status')
				if string.find(jid, "@") <= 0:
					#It must be an agent
					if not self.r.l_contact.has_key(ji):
						user1 = user(ji, ji, ['Agents'], ev[1][1], \
							ev[1][2], 'from', res)
						self.r.add_user(user1)
					else:
						#Update existing iter
						for i in self.r.l_contact[ji]['iter']:
							if self.r.pixbufs.has_key(ev[1][1]):
								model.set_value(i, 0, self.r.pixbufs[ev[1][1]])
				elif self.r.l_contact.has_key(ji):
					#It isn't an agent
					self.r.chg_status(jid, ev[1][1], ev[1][2])
			elif ev[0] == 'MSG':
				if string.find(ev[1][0], "@") <= 0:
					jid = string.replace(ev[1][0], '@', '')
				else:
					jid = ev[1][0]
				
				if self.config.has_key('autopopup'):
					self.autopopup = self.config['autopopup']
				else:
					self.autopopup = 0
				if not self.r.l_contact.has_key(jid):
					user1 = user(jid, jid, ['not in list'], \
						'not in list', 'not in list', 'none', '')
					self.r.add_user(user1)
				if self.autopopup == 0 and not self.r.tab_messages.has_key(jid):
					#We save it in a queue
					if not self.r.tab_queues.has_key(jid):
						self.r.tab_queues[jid] = Queue.Queue(50)
						for i in self.r.l_contact[jid]['iter']:
							model.set_value(i, 0, self.r.pixbufs['message'])
					tim = time.strftime("[%H:%M:%S]")
					self.r.tab_queues[jid].put((ev[1][1], tim))
				else:
					if not self.r.tab_messages.has_key(jid):
						if self.r.l_contact.has_key(jid):
							self.r.tab_messages[jid] = \
								message_Window(self.r.l_contact[jid]['user'], self.r)
					if self.r.tab_messages.has_key(jid):
						self.r.tab_messages[jid].print_conversation(ev[1][1])
					
			elif ev[0] == 'SUBSCRIBE':
				authorize_Window(self.r, ev[1])
			elif ev[0] == 'SUBSCRIBED':
				jid = ev[1]['jid']
				if self.r.l_contact.has_key(jid):
					u = self.r.l_contact[jid]['user']
					u.name = ev[1]['nom']
					for i in self.r.l_contact[u.jid]['iter']:
						model.set_value(i, 1, u.name)
				else:
					user1 = user(jid, jid, ['general'], 'online', \
						'online', 'to', ev[1]['ressource'])
					self.r.add_user(user1)
				warning_Window("You are now authorized by " + jid)
			elif ev[0] == 'UNSUBSCRIBED':
				warning_Window("You are now unsubscribed by " + jid)
				#TODO: change icon
			elif ev[0] == 'AGENTS':
				if browserWindow:
					browserWindow.agents(ev[1])
			elif ev[0] == 'AGENT_INFO':
				if not ev[1][1].has_key('instructions'):
					warning_Window('error contacting %s' % ev[1][0])
				else:
					Wreg = agentRegistration_Window(ev[1][0], ev[1][1], self.r)
			#('ACC_OK', (hostname, login, pasword, name, ressource))
			elif ev[0] == 'ACC_OK':
				self.accounts[ev[1][3]] =  {'ressource': ev[1][4], \
					'password': ev[1][2], 'hostname': ev[1][0], 'name': ev[1][1]}
				self.r.queueOUT.put(('CONFIG', ('accounts', self.r.plugin.accounts)))
				if (accountsWindow != 0):
					accountsWindow.init_accounts()
			elif ev[0] == 'QUIT':
				self.r.on_quit(self)
		return 1
	
	def read_sleepy(self):	
		"""Check if we are idle"""
		if self.sleeper and (self.autoaway or self.autoxa) and \
			(self.r.optionmenu.get_history()==0 or \
			self.sleeper_state!=common.sleepy.STATE_AWAKE):
			self.sleeper.poll()
			state = self.sleeper.getState()
			if state != self.sleeper_state:
				if state == common.sleepy.STATE_AWAKE:
					#we go online
					self.r.optionmenu.set_history(0)
					self.r.queueOUT.put(('STATUS',('online', '', \
						self.accounts.keys()[0])))
				if state == common.sleepy.STATE_AWAY and self.autoaway:
					#we go away
					self.r.optionmenu.set_history(1)
					self.r.queueOUT.put(('STATUS',('away', \
						'auto away (idle)', self.accounts.keys()[0])))
				if state == common.sleepy.STATE_XAWAY and self.autoxa:
					#we go extanded away
					self.r.optionmenu.set_history(2)
					self.r.queueOUT.put(('STATUS',('xa', \
						'auto away (idel)', self.accounts.keys[0])))
			self.sleeper_state = state
		return 1

	def __init__(self, quIN, quOUT):
		gtk.threads_init()
		gtk.threads_enter()
		self.queueIN = quIN
		quOUT.put(('ASK_CONFIG', ('GtkGui', 'GtkGui')))
		self.config = self.wait('CONFIG')
		quOUT.put(('ASK_CONFIG', ('GtkGui', 'accounts')))
		self.accounts = self.wait('CONFIG')
		#TODO: if no config : default config and save it
		self.r = roster_Window(quOUT, self)
		if self.config.has_key('autoaway'):
			self.autoaway = self.config['autoaway']
		else:
			self.autoaway = 1
		if self.config.has_key('autoawaytime'):
			self.autoawaytime = self.config['autoawaytime']
		else:
			self.autoawaytime = 10
		if self.config.has_key('autoxa'):
			self.autoxa = self.config['autoxa']
		else:
			self.autoxa = 1
		if self.config.has_key('autoxatime'):
			self.autoxatime = self.config['autoxatime']
		else:
			self.autoxatime = 20
		self.time = gtk.timeout_add(200, self.read_queue)
		gtk.timeout_add(1000, self.read_sleepy)
		self.sleeper = None
		self.sleeper_state = None
		gtk.main()
		gtk.threads_leave()

if __name__ == "__main__":
	plugin(None, None)

print "plugin gtkgui loaded"
