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

class vCard_Window:
	"""Class for window that show vCard information"""
	def delete_event(self, widget=None):
		"""close window"""
		del self.plugin.windows[self.account]['infos'][self.jid]

	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

	def set_value(self, entry_name, value):
		try:
			self.xml.get_widget(entry_name).set_text(value)
		except AttributeError, e:
			pass

	def set_values(self, vcard):
		for i in vcard.keys():
			if type(vcard[i]) == type({}):
				for j in vcard[i].keys():
					self.set_value('entry_'+i+'_'+j, vcard[i][j])
			else:
				if i == 'DESC':
					self.xml.get_widget('textview_DESC').get_buffer().\
						set_text(vcard[i], 0)
				else:
					self.set_value('entry_'+i, vcard[i])

	def add_to_vcard(self, vcard, entry, txt):
		"""Add an information to the vCard dictionary"""
		entries = string.split(entry, '_')
		loc = vcard
		while len(entries) > 1:
			if not loc.has_key(entries[0]):
				loc[entries[0]] = {}
			loc = loc[entries[0]]
			del entries[0]
		loc[entries[0]] = txt
		return vcard

	def make_vcard(self):
		"""make the vCard dictionary"""
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_USERID', 'URL', 'TEL_NUMBER',\
			'ADR_STREET', 'ADR_EXTADR', 'ADR_LOCALITY', 'ADR_REGION', 'ADR_PCODE',\
			'ADR_CTRY', 'ORG_ORGNAME', 'ORG_ORGUNIT', 'TITLE', 'ROLE']
		vcard = {}
		for e in entries:
			txt = self.xml.get_widget('entry_'+e).get_text()
			if txt != '':
				vcard = self.add_to_vcard(vcard, e, txt)
		buf = self.xml.get_widget('textview_DESC').get_buffer()
		start_iter = buf.get_start_iter()
		end_iter = buf.get_end_iter()
		txt = buf.get_text(start_iter, end_iter, 0)
		if txt != '':
			vcard['DESC']= txt
		return vcard


	def on_retrieve(self, widget):
		if self.plugin.connected[self.account]:
			self.plugin.send('ASK_VCARD', self.account, self.jid)
		else:
			warning_Window("You must be connected to get your informations")

	def on_publish(self, widget):
		if not self.plugin.connected[self.account]:
			warning_Window("You must be connected to publish your informations")
			return
		vcard = self.make_vcard()
		nick = ''
		if vcard.has_key('NICKNAME'):
			nick = vcard['NICKNAME']
		if nick == '':
			nick = self.plugin.accounts[self.account]['name']
		self.plugin.nicks[self.account] = nick
		self.plugin.send('VCARD', self.account, vcard)

	def __init__(self, jid, plugin, account):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'vcard')
		self.jid = jid
		self.plugin = plugin
		self.account = account
		
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_close_clicked', self.on_close)
		self.xml.signal_connect('on_retrieve_clicked', self.on_retrieve)
		self.xml.signal_connect('on_publish_clicked', self.on_publish)

class infoUser_Window:
	"""Class for user's information window"""
	def delete_event(self, widget=None):
		"""close window"""
		del self.plugin.windows[self.account]['infos'][self.user.jid]

	def add_grp_to_user(self, model, path, iter):
		"""Insert user to the group in inter"""
		self.user.groups.append(model.get_value(iter, 0))

	def on_close(self, widget):
		"""Save user's informations and update the roster on the Jabber server"""
		#update: to know if things have changed to send things 
		# to server only if changes are done
		update = 0
		#update user.groups and redraw the user in the roster
		old_groups = self.user.groups
		self.user.groups = []
		model = self.list2.get_model()
		model.foreach(self.add_grp_to_user)
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
			new_groups = self.user.groups
			self.user.groups = old_groups
			self.plugin.roster.remove_user(self.user, self.account)
			self.user.groups = new_groups
			self.plugin.roster.add_user_to_roster(self.user, self.account)
		#update user.name if it's not ""
		entry_name = self.xml.get_widget('entry_name')
		newName = entry_name.get_text()
		if newName != self.user.name:
			update = 1
			if newName != '':
				self.user.name = newName
		if update:
			self.plugin.send('UPDUSER', self.account, (self.user.jid, \
				self.user.name, self.user.groups))
		widget.get_toplevel().destroy()

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
			entry_new = self.xml.get_widget("entry_new")
			model = self.list1.get_model()
			txt = entry_new.get_text()
			iter = model.append()
			model.set(iter, 0, txt)
			entry_new.set_text('')
			return 1
		else:
			return 0

	def set_value(self, entry_name, value):
		try:
			self.xml.get_widget(entry_name).set_text(value)
		except AttributeError, e:
			pass

	def set_values(self, vcard):
		for i in vcard.keys():
			if type(vcard[i]) == type({}):
				for j in vcard[i].keys():
					self.set_value('entry_'+i+'_'+j, vcard[i][j])
			else:
				if i == 'DESC':
					self.xml.get_widget('textview_DESC').get_buffer().\
						set_text(vcard[i], 0)
				else:
					self.set_value('entry_'+i, vcard[i])

	def init_lists(self):
		"""Initialize both available and current listStores"""
		#list available
		store = gtk.ListStore(gobject.TYPE_STRING)
		for g in self.plugin.roster.groups[self.account].keys():
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

	def __init__(self, user, plugin, account):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Info_user')
		self.plugin = plugin
		self.user = user
		self.account = account
		self.list1 = self.xml.get_widget("treeview_available")
		self.list2 = self.xml.get_widget("treeview_current")

		self.xml.get_widget('label_name').set_text(user.name)
		self.xml.get_widget('label_id').set_text(user.jid)
		self.xml.get_widget('label_resource').set_text(user.resource)
		self.xml.get_widget('label_sub').set_text(user.sub)
		self.xml.get_widget('entry_name').set_text(user.name)
		if not user.status:
			user.status = ''
		self.xml.get_widget('label_status').set_text(user.show + ' : ' + \
			user.status)
		self.init_lists()
		plugin.send('ASK_VCARD', account, self.user.jid)
		
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_close_clicked', self.on_close)
		self.xml.signal_connect('on_add_clicked', self.on_add)
		self.xml.signal_connect('on_remove_clicked', self.on_remove)
		self.xml.signal_connect('on_entry_new_key_press_event', \
			self.on_new_key_pressed)
		

class preference_Window:
	"""Class for Preferences window"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['preferences']

	def on_cancel(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()

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
		colSt_in = '#'+(hex(self.colorIn.red)+'0')[2:4]\
			+(hex(self.colorIn.green)+'0')[2:4]\
			+(hex(self.colorIn.blue)+'0')[2:4]
		self.plugin.config['inmsgcolor'] = colSt_in
		#Color for outgoing messages
		colSt_out = '#'+(hex(self.colorOut.red)+'0')[2:4]\
			+(hex(self.colorOut.green)+'0')[2:4]\
			+(hex(self.colorOut.blue)+'0')[2:4]
		self.plugin.config['outmsgcolor'] = colSt_out
		#Color for status messages
		colSt_status = '#'+(hex(self.colorStatus.red)+'0')[2:4]\
			+(hex(self.colorStatus.green)+'0')[2:4]\
			+(hex(self.colorStatus.blue)+'0')[2:4]
		self.plugin.config['statusmsgcolor'] = colSt_status
		#update opened chat windows
		for a in self.plugin.accounts.keys():
			for w in self.plugin.windows[a]['chats'].keys():
				self.plugin.windows[a]['chats'][w].tagIn.\
					set_property("foreground", colSt_in)
				self.plugin.windows[a]['chats'][w].tagIn.\
					set_property("foreground", colSt_out)
				self.plugin.windows[a]['chats'][w].tagIn.\
					set_property("foreground", colSt_status)
		#IconStyle
		ist = self.combo_iconstyle.entry.get_text()
		self.plugin.config['iconstyle'] = ist
		self.plugin.roster.mkpixbufs()
		#autopopup
		pp = self.chk_autopp.get_active()
		if pp == True:
			self.plugin.config['autopopup'] = 1
		else:
			self.plugin.config['autopopup'] = 0
		#autoaway
		aw = self.chk_autoaway.get_active()
		if aw == True:
			self.plugin.config['autoaway'] = 1
		else:
			self.plugin.config['autoaway'] = 0
		aat = self.spin_autoawaytime.get_value_as_int()
		self.plugin.config['autoawaytime'] = aat
		#autoxa
		xa = self.chk_autoxa.get_active()
		if xa == True:
			self.plugin.config['autoxa'] = 1
		else:
			self.plugin.config['autoxa'] = 0
		axt = self.spin_autoxatime.get_value_as_int()
		self.plugin.config['autoxatime'] = axt
		if self.plugin.sleeper:
			self.plugin.sleeper = common.sleepy.Sleepy(\
				self.plugin['autoawaytime']*60, self.plugin['autoxatime']*60)
		self.plugin.send('CONFIG', None, ('GtkGui', self.plugin.config))
		self.plugin.roster.draw_roster()
		
	def on_ok(self, widget):
		"""When Ok button is clicked"""
		self.write_cfg()
		self.xml.get_widget('Preferences').destroy()

	def change_notebook_page(self, number):
		self.notebook.set_current_page(number)

	def on_lookfeel_button_clicked(self, widget, data=None):
		self.change_notebook_page(0)
		
	def on_events_button_clicked(self, widget, data=None):
		self.change_notebook_page(1)
		
	def on_presence_button_clicked(self, widget, data=None):
		self.change_notebook_page(2)

	def __init__(self, plugin):
		"""Initialize Preference window"""
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Preferences')
		self.plugin = plugin
		self.da_in = self.xml.get_widget('drawing_in')
		self.da_out = self.xml.get_widget('drawing_out')
		self.da_status = self.xml.get_widget('drawing_status')
		self.combo_iconstyle = self.xml.get_widget('combo_iconstyle')
		self.chk_autopp = self.xml.get_widget('chk_autopopup')
		self.chk_autoaway = self.xml.get_widget('chk_autoaway')
		self.spin_autoawaytime = self.xml.get_widget('spin_autoawaytime')
		self.chk_autoxa = self.xml.get_widget('chk_autoxa')
		self.spin_autoxatime = self.xml.get_widget('spin_autoxatime')
		self.notebook = self.xml.get_widget('preferences_notebook')
		
		button = self.xml.get_widget('lookfeel_button')
		button.connect('clicked', self.on_lookfeel_button_clicked)
		button = self.xml.get_widget('events_button')
		button.connect('clicked', self.on_events_button_clicked)
		button = self.xml.get_widget('presence_button')
		button.connect('clicked', self.on_presence_button_clicked)

		#Color for incomming messages
		colSt = self.plugin.config['inmsgcolor']
		if not colSt:
			colSt = '#ff0000'
		cmapIn = self.da_in.get_colormap()
		self.colorIn = cmapIn.alloc_color(colSt)
		self.da_in.window.set_background(self.colorIn)
		
		#Color for outgoing messages
		colSt = self.plugin.config['outmsgcolor']
		if not colSt:
			colSt = '#0000ff'
		cmapOut = self.da_out.get_colormap()
		self.colorOut = cmapOut.alloc_color(colSt)
		self.da_out.window.set_background(self.colorOut)
		
		#Color for status messages
		colSt = self.plugin.config['statusmsgcolor']
		if not colSt:
			colSt = '#00ff00'
		cmapStatus = self.da_status.get_colormap()
		self.colorStatus = cmapStatus.alloc_color(colSt)
		self.da_status.window.set_background(self.colorStatus)
		
		#iconStyle
		list_style = os.listdir('plugins/gtkgui/icons/')
		l = []
		for i in list_style:
			if i != 'CVS' and i[0] != '.':
				l.append(i)
		if l.count == 0:
			l.append(" ")
		self.combo_iconstyle.set_popdown_strings(l)
		if self.plugin.config['iconstyle'] in l:
			self.combo_iconstyle.entry.set_text(self.plugin.config['iconstyle'])
		
		#Autopopup
		st = 0
		if self.plugin.config.has_key('autopopup'):
			st = self.plugin.config['autopopup']
		self.chk_autopp.set_active(st)

		#Autoaway
		st = 1
		if self.plugin.config.has_key('autoaway'):
			st = self.plugin.config['autoaway']
		self.chk_autoaway.set_active(st)
		self.chk_autoaway.set_sensitive(0)

		#Autoawaytime
		st = 10
		if self.plugin.config.has_key('autoawaytime'):
			st = self.plugin.config['autoawaytime']
		self.spin_autoawaytime.set_value(st)
		self.spin_autoawaytime.set_sensitive(0)

		#Autoxa
		st = 1
		if self.plugin.config.has_key('autoxa'):
			st = self.plugin.config['autoxa']
		self.chk_autoxa.set_active(st)
		self.chk_autoxa.set_sensitive(0)

		#Autoxatime
		st = 20
		if self.plugin.config.has_key('autoxatime'):
			st = self.plugin.config['autoxatime']
		self.spin_autoxatime.set_value(st)
		self.spin_autoxatime.set_sensitive(0)

		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_but_col_clicked', \
			self.on_color_button_clicked)
		self.xml.signal_connect('on_ok_clicked', self.on_ok)
		self.xml.signal_connect('on_cancel_clicked', self.on_cancel)

class awayMsg_Window:
	"""Class for Away Message Window"""
	def on_ok(self):
		"""When Ok button is clicked"""
		beg, end = self.txtBuffer.get_bounds()
		self.msg = self.txtBuffer.get_text(beg, end, 0)
		self.xml.get_widget("Away_msg").destroy()
	
	def run(self):
		"""Wait for Ok button to be pressed and return away messsage"""
		rep = self.xml.get_widget("Away_msg").run()
		if rep == gtk.RESPONSE_OK:
			beg, end = self.txtBuffer.get_bounds()
			msg = self.txtBuffer.get_text(beg, end, 0)
		else:
			msg = -1
		self.xml.get_widget("Away_msg").destroy()
		return msg
	
	def __init__(self):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Away_msg')
		txt = self.xml.get_widget("textview")
		self.txtBuffer = txt.get_buffer()

class addContact_Window:
	"""Class for Add user window"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['add']

	def on_cancel(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()

	def on_subscribe(self, widget):
		"""When Subscribe button is clicked"""
		textview_sub = self.xml.get_widget("textview_sub")
		entry_who = self.xml.get_widget('entry_who')
		who = entry_who.get_text()
		buf = textview_sub.get_buffer()
		start_iter = buf.get_start_iter()
		end_iter = buf.get_end_iter()
		txt = buf.get_text(start_iter, end_iter, 0)
		self.plugin.roster.req_sub(self, who, txt, self.account)
		widget.get_toplevel().destroy()
		
	def __init__(self, plugin, account, jid=None):
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Add')
		if jid:
			self.xml.get_widget('entry_who').set_text(jid)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_button_sub_clicked', self.on_subscribe)
		self.xml.signal_connect('on_cancel_clicked', self.on_cancel)

class warning_Window:
	"""Class for warning window : print a warning message"""
	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

	def __init__(self, txt):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Warning')
		xml.get_widget('label').set_text(txt)
		xml.signal_connect('on_close_clicked', self.on_close)

class about_Window:
	"""Class for about window"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['about']
		
	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

	def __init__(self, plugin):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'About')
		self.plugin = plugin
		xml.signal_connect('gtk_widget_destroy', self.delete_event)
		xml.signal_connect('on_close_clicked', self.on_close)


class accountPreference_Window:
	"""Class for account informations"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['accountPreference']
	
	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

	def init_account(self, infos):
		"""Initialize window with defaults values"""
		if infos.has_key('name'):
			self.xml.get_widget("entry_name").set_text(infos['name'])
		if infos.has_key('jid'):
			self.xml.get_widget("entry_jid").set_text(infos['jid'])
		if infos.has_key('password'):
			self.xml.get_widget("entry_password").set_text(infos['password'])
		if infos.has_key('ressource'):
			self.xml.get_widget("entry_ressource").set_text(infos['ressource'])

	def on_save_clicked(self, widget):
		"""When save button is clicked : Save informations in config file"""
		entryPass = self.xml.get_widget("entry_password")
		entryRessource = self.xml.get_widget("entry_ressource")
		check = self.xml.get_widget("checkbutton")
		entryName = self.xml.get_widget("entry_name")
		entryJid = self.xml.get_widget("entry_jid")
		name = entryName.get_text()
		jid = entryJid.get_text()
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
		if self.modify:
			#if we modify the name of the account
			if name != self.account:
				#update variables
				self.plugin.windows[name] = self.plugin.windows[self.account]
				self.plugin.queues[name] = self.plugin.queues[self.account]
				self.plugin.connected[name] = self.plugin.connected[self.account]
				self.plugin.nicks[name] = self.plugin.nicks[self.account]
				self.plugin.roster.groups[name] = \
					self.plugin.roster.groups[self.account]
				self.plugin.roster.contacts[name] = \
					self.plugin.roster.contacts[self.account]
				del self.plugin.windows[self.account]
				del self.plugin.queues[self.account]
				del self.plugin.connected[self.account]
				del self.plugin.nicks[self.account]
				del self.plugin.roster.groups[self.account]
				del self.plugin.roster.contacts[self.account]
				del self.plugin.accounts[self.account]
				self.plugin.send('ACC_CHG', self.account, name)
				self.plugin.accounts[name] = {'name': login, 'hostname': hostname,\
					'password': entryPass.get_text(), 'ressource': \
					entryRessource.get_text()}
				self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts))
				#refresh accounts window
				if self.plugin.windows.has_key('accounts'):
					self.plugin.windows['accounts'].init_accounts()
				#refresh roster
				self.plugin.roster.draw_roster()
				widget.get_toplevel().destroy()
				return
		#if it's a new account
		else:
			if name in self.plugin.accounts.keys():
				warning_Window('An account already has this name')
				return
			#if we neeed to register a new account
			if check.get_active():
				self.plugin.send('NEW_ACC', None, (hostname, login, \
					entryPass.get_text(), name, entryRessource.get_text()))
				check.set_active(FALSE)
				return
		self.plugin.accounts[name] = {'name': login, 'hostname': hostname,\
			'password': entryPass.get_text(), 'ressource': \
			entryRessource.get_text()}
		self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts))
		#update variables
		self.plugin.windows[name] = {'infos': {}, 'chats': {}}
		self.plugin.queues[name] = {}
		self.plugin.connected[name] = 0
		self.plugin.roster.groups[name] = {}
		self.plugin.roster.contacts[name] = {}
		#refresh accounts window
		if self.plugin.windows.has_key('accounts'):
			self.plugin.windows['accounts'].init_accounts()
		#refresh roster
		self.plugin.roster.draw_roster()
		widget.get_toplevel().destroy()

	def on_edit_details_clicked(self, widget):
		entryJid = self.xml.get_widget("entry_jid")
		if not self.plugin.windows.has_key('vcard'):
			self.plugin.windows[self.account]['infos'][entryJid.get_text()] = \
				vCard_Window(entryJid.get_text(), self.plugin, self.account)
			if self.plugin.connected[self.account]:
				self.plugin.send('ASK_VCARD', self.account, entryJid.get_text())
			else:
				warning_Window("You must be connected to get your informations")
	
	#info must be a dictionnary
	def __init__(self, plugin, infos = {}):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Account')
		self.plugin = plugin
		self.account = ''
		self.modify = False
		if infos:
			self.modify = True
			self.account = infos['name']
			self.init_account(infos)
			self.xml.get_widget("checkbutton").set_sensitive(FALSE)
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_save_clicked', self.on_save_clicked)
		self.xml.signal_connect('on_edit_details_clicked', \
			self.on_edit_details_clicked)
		self.xml.signal_connect('on_close_clicked', self.on_close)

class accounts_Window:
	"""Class for accounts window : lists of accounts"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows['accounts']
		
#Not for the moment ... but maybe one day there will be a button	
#	def on_close(self, widget):
#		"""When Close button is clicked"""
#		widget.get_toplevel().destroy()
		
	def init_accounts(self):
		"""initialize listStore with existing accounts"""
		self.xml.get_widget("modify_button").set_sensitive(False)
		self.xml.get_widget("delete_button").set_sensitive(False)
		model = self.treeview.get_model()
		model.clear()
		for account in self.plugin.accounts:
			iter = model.append()
			model.set(iter, 0, account, 1, \
				self.plugin.accounts[account]["hostname"])

	def on_row_activated(self, widget):
		"""Activate delete and modify buttons when a row is selected"""
		self.xml.get_widget("modify_button").set_sensitive(True)
		self.xml.get_widget("delete_button").set_sensitive(True)

	def on_new_clicked(self, widget):
		"""When new button is clicked : open an account information window"""
		if not self.plugin.windows.has_key('accountPreference'):
			self.plugin.windows['accountPreference'] = \
				accountPreference_Window(self.plugin)

	def on_delete_clicked(self, widget):
		"""When delete button is clicked :
		Remove an account from the listStore and from the config file"""
		sel = self.treeview.get_selection()
		(model, iter) = sel.get_selected()
		account = model.get_value(iter, 0)
		window = confirm_Window('Are you sure you want to remove this account (' \
			+ account + ') ?')
		if window.wait() == gtk.RESPONSE_OK:
			if self.plugin.connected[account]:
				self.plugin.send('STATUS', account, ('offline', 'offline'))
			del self.plugin.accounts[account]
			self.plugin.send('CONFIG', None, ('accounts', self.plugin.accounts))
			del self.plugin.windows[account]
			del self.plugin.queues[account]
			del self.plugin.connected[account]
			del self.plugin.roster.groups[account]
			del self.plugin.roster.contacts[account]
			self.plugin.roster.draw_roster()
			self.init_accounts()

	def on_modify_clicked(self, widget):
		"""When modify button is clicked :
		open the account information window for this account"""
		if not self.plugin.windows.has_key('accountPreference'):
			infos = {}
			sel = self.treeview.get_selection()
			(model, iter) = sel.get_selected()
			account = model.get_value(iter, 0)
			infos['name'] = account
			infos['jid'] = self.plugin.accounts[account]["name"] + \
				'@' +  self.plugin.accounts[account]["hostname"]
			infos['password'] = self.plugin.accounts[account]["password"]
			infos['ressource'] = self.plugin.accounts[account]["ressource"]
			self.plugin.windows['accountPreference'] = \
				accountPreference_Window(self.plugin, infos)
		
	def __init__(self, plugin):
		self.plugin = plugin
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Accounts')
		self.treeview = self.xml.get_widget("treeview")
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
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_row_activated', self.on_row_activated)
		self.xml.signal_connect('on_new_clicked', self.on_new_clicked)
		self.xml.signal_connect('on_delete_clicked', self.on_delete_clicked)
		self.xml.signal_connect('on_modify_clicked', self.on_modify_clicked)
		self.init_accounts()

class confirm_Window:
	"""Class for confirmation window"""
	def wait(self):
		out = self.win.run()
		self.win.destroy()
		return out

	def __init__(self, label):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Confirm')
		xml.get_widget('label_confirm').set_text(label)
		self.win = xml.get_widget('Confirm')

class authorize_Window:
	"""Class for authorization window :
	window that appears when a user wants to add us to his/her roster"""
	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()
		
	def auth(self, widget):
		"""Accept the request"""
		self.plugin.send('AUTH', self.account, self.jid)
		widget.get_toplevel().destroy()
		if not self.plugin.roster.contacts[self.account].has_key(self.jid):
			addContact_Window(self.plugin, self.account, self.jid)
	
	def deny(self, widget):
		"""refuse the request"""
		self.plugin.send('DENY', self.account, self.jid)
		widget.get_toplevel().destroy()
	
	def __init__(self, plugin, jid, txt, account):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'Sub_req')
		self.plugin = plugin
		self.jid = jid
		self.account = account
		xml.get_widget('label').set_text('Subscription request from ' + self.jid)
		xml.get_widget("textview").get_buffer().set_text(txt)
		xml.signal_connect('on_button_auth_clicked', self.auth)
		xml.signal_connect('on_button_deny_clicked', self.deny)
		xml.signal_connect('on_button_close_clicked', self.on_close)

class agentRegistration_Window:
	"""Class for agent registration window :
	window that appears when we want to subscribe to an agent"""
	def on_cancel(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()
		
	def draw_table(self):
		"""Draw the table in the window"""
		nbrow = 0
		table = self.xml.get_widget('table')
		for name in self.infos.keys():
			if name != 'key' and name != 'instructions' and name != 'x':
				nbrow = nbrow + 1
				table.resize(rows=nbrow, columns=2)
				label = gtk.Label(name)
				table.attach(label, 0, 1, nbrow-1, nbrow, 0, 0, 0, 0)
				entry = gtk.Entry()
				entry.set_text(self.infos[name])
				table.attach(entry, 1, 2, nbrow-1, nbrow, 0, 0, 0, 0)
				self.entries[name] = entry
				if nbrow == 1:
					entry.grab_focus()
		table.show_all()
	
	def on_ok(self, widget):
		"""When Ok button is clicked :
		send registration info to the core"""
		for name in self.entries.keys():
			self.infos[name] = self.entries[name].get_text()
		self.plugin.send('REG_AGENT', self.account, self.agent)
		widget.get_toplevel().destroy()
	
	def __init__(self, agent, infos, plugin, account):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'agent_reg')
		self.agent = agent
		self.infos = infos
		self.plugin = plugin
		self.account = account
		self.xml.get_widget('agent_reg').set_title('Register to ' + agent)
		self.xml.get_widget('label').set_text(infos['instructions'])
		self.entries = {}
		self.draw_table()
		self.xml.signal_connect('on_cancel_clicked', self.on_cancel)
		self.xml.signal_connect('on_button_ok_clicked', self.on_ok)

class browseAgent_Window:
	"""Class for bowser agent window :
	to know the agents on the selected server"""
	def delete_event(self, widget):
		"""close window"""
		del self.plugin.windows[self.account]['browser']

	def on_cancel(self, widget):
		"""When Cancel button is clicked"""
		widget.get_toplevel().destroy()

	def on_close(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()
		
	def browse(self):
		"""Send a request to the core to know the available agents"""
		self.plugin.send('REQ_AGENTS', self.account, None)
	
	def agents(self, agents):
		"""When list of available agent arrive :
		Fill the treeview with it"""
		model = self.treeview.get_model()
		for jid in agents.keys():
			iter = model.append()
#			model.set(iter, 0, agents[jid]['name'], 1, agents[jid]['service'])
			model.set(iter, 0, agents[jid]['name'], 1, jid)

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
		self.plugin.send('REQ_AGENT_INFO', self.account, service)
		widget.get_toplevel().destroy()
		
	def __init__(self, plugin, account):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'browser')
		self.treeview = xml.get_widget('treeview')
		self.plugin = plugin
		self.account = account
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
		xml.signal_connect('on_close_clicked', self.on_close)
		if self.plugin.connected[account]:
			self.browse()
		else:
			warning_Window("You must be connected to view Agents")

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
		for i in self.plugin.roster.get_user_iter(self.user.jid, self.account):
			if self.plugin.roster.pixbufs.has_key(self.user.show):
				self.plugin.roster.tree.get_model().set_value(i, 0, \
					self.plugin.roster.pixbufs[self.user.show])

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
	
	def __init__(self, user, plugin, account):
		self.user = user
		self.plugin = plugin
		self.account = account
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Chat')
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
		self.xml.signal_connect('on_history_clicked', self.on_history)
		self.xml.signal_connect('on_msg_key_press_event', \
			self.on_msg_key_press_event)
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
			buffer.insert_with_tags_by_name(start_iter, 'Status is now : ' + \
				infos[3][0]+' : ' + msg, 'status')
	
	def set_nb_line(self, nb_line):
		self.nb_line = nb_line
		self.num_begin = nb_line

	def __init__(self, plugin, jid):
		self.plugin = plugin
		self.jid = jid
		self.nb_line = 0
		self.num_begin = 0
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Log')
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

	def add_user_to_roster(self, user, account):
		"""Add a user to the roster and add groups if they aren't in roster"""
		showOffline = self.plugin.config['showoffline']
		if not self.contacts[account].has_key(user.jid):
			self.contacts[account][user.jid] = user
		if user.groups == []:
			if string.find(user.jid, "@") <= 0:
				user.groups.append('Agents')
			else:
				user.groups.append('general')

		if (user.show == 'offline' or user.show == 'error') and not showOffline\
			and not 'Agents' in user.groups:
			return

		model = self.tree.get_model()
		for g in user.groups:
			iterG = self.get_group_iter(g, account)
			if not iterG:
				acct = self.get_account_iter(account)
				iterG = model.append(acct, \
					(self.pixbufs['closed'], g, 'group', \
					g, FALSE))
			if not self.groups[account].has_key(g):
				self.groups[account][g] = {'expand': True}
			self.tree.expand_row((model.get_path(iterG)[0]), False)

			typestr = 'user'
			if g == 'Agents':
				typestr = 'agent'

			model.append(iterG, (self.pixbufs[user.show], \
				user.name, typestr, user.jid, TRUE))
			
			if self.groups[account][g]['expand']:
				self.tree.expand_row(model.get_path(iterG), FALSE)
	
	def remove_user(self, user, account):
		"""Remove a user from the roster"""
		model = self.tree.get_model()
		for i in self.get_user_iter(user.jid, account):
			parent_i = model.iter_parent(i)
			model.remove(i)
			if model.iter_n_children(parent_i) == 0:
				model.remove(parent_i)
	
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
			for user in self.contacts[acct].values():
				self.add_user_to_roster(user, acct)
	
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
				array[jid]['status'], array[jid]['sub'], resource)
			self.contacts[account][ji] = user1
			for g in array[jid]['groups'] :
				if not g in self.groups[account].keys():
					self.groups[account][g] = {'expand':True}

	def chg_user_status(self, user, show, status, account):
		"""When a user change his status"""
		showOffline = self.plugin.config['showoffline']
		iters = self.get_user_iter(user.jid, account)
		if not iters:
			self.add_user_to_roster(user, account)
		else:
			model = self.tree.get_model()
			if (show == 'offline' or show == 'error') and not showOffline:
				self.remove_user(user, account)
			else:
				for i in iters:
					if self.pixbufs.has_key(show):
						model.set_value(i, 0, self.pixbufs[show])
		user.show = show
		user.status = status
		#Print status in chat window
		if self.plugin.windows[account]['chats'].has_key(user.jid):
			self.plugin.windows[account]['chats'][user.jid].\
				img.set_from_pixbuf(self.pixbufs[show])
			self.plugin.windows[account]['chats'][user.jid].print_conversation(\
				"%s is now %s (%s)" % (user.name, show, status), 'status')

	def on_info(self, widget, user, account):
		"""Call infoUser_Window class to display user's information"""
		if not self.plugin.windows[account]['infos'].has_key(user.jid):
			self.plugin.windows[account]['infos'][user.jid] = \
				infoUser_Window(user, self.plugin, account)

	def on_agent_logging(self, widget, jid, state, account):
		"""When an agent is requested to log in or off"""
		self.plugin.send('AGENT_LOGGING', account, (jid, state))
		
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
		user = self.contacts[account][jid]
		
		menu = gtk.Menu()
		item = gtk.MenuItem("Start chat")
		menu.append(item)
		item.connect("activate", self.on_row_activated, path)
		item = gtk.MenuItem("Rename")
		menu.append(item)
		#item.connect("activate", self.on_rename, iter)
		item = gtk.MenuItem()
		menu.append(item)
		item = gtk.MenuItem("Subscription")
		menu.append(item)
		
		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem("Resend authorization to")
		menu_sub.append(item)
		item.connect("activate", self.authorize, jid, account)
		item = gtk.MenuItem("Rerequest authorization from")
		menu_sub.append(item)
		item.connect("activate", self.req_sub, jid, \
			'I would like to add you to my contact list, please.', account)
		
		item = gtk.MenuItem()
		menu.append(item)
		item = gtk.MenuItem("Remove")
		menu.append(item)
		item.connect("activate", self.on_req_usub, user, account)

		item = gtk.MenuItem()
		menu.append(item)
		item = gtk.MenuItem("Informations")
		menu.append(item)
		item.connect("activate", self.on_info, user, account)
		item = gtk.MenuItem("History")
		menu.append(item)
		item.connect("activate", self.on_history, user)

		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()

	def mk_menu_g(self, event):
		"""Make group's popup menu"""
		menu = gtk.Menu()
		item = gtk.MenuItem("grp1")
#		menu.append(item)
		item = gtk.MenuItem("grp2")
#		menu.append(item)
		item = gtk.MenuItem("grp3")
#		menu.append(item)
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
	
	def mk_menu_agent(self, event, iter):
		"""Make agent's popup menu"""
		model = self.tree.get_model()
		jid = model.get_value(iter, 3)
		path = model.get_path(iter)
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		menu = gtk.Menu()
		item = gtk.MenuItem("Log on")
		if self.contacts[account][jid].show != 'offline':
			item.set_sensitive(FALSE)
		menu.append(item)
		item.connect("activate", self.on_agent_logging, jid, 'available', account)

		item = gtk.MenuItem("Log off")
		if self.contacts[account][jid].show == 'offline':
			item.set_sensitive(FALSE)
		menu.append(item)
		item.connect("activate", self.on_agent_logging, jid, 'unavailable', account)

		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()

	def on_edit_account(self, widget, account):
		if not self.plugin.windows.has_key('accountPreference'):
			infos = {}
			infos['name'] = account
			infos['jid'] = self.plugin.accounts[account]["name"] + \
				'@' +  self.plugin.accounts[account]["hostname"]
			infos['password'] = self.plugin.accounts[account]["password"]
			infos['ressource'] = self.plugin.accounts[account]["ressource"]
			self.plugin.windows['accountPreference'] = \
				accountPreference_Window(self.plugin, infos)

	def mk_menu_account(self, event, iter):
		"""Make account's popup menu"""
		model = self.tree.get_model()
		account = model.get_value(iter, 3)
		
		menu = gtk.Menu()
		item = gtk.MenuItem("Status")
		menu.append(item)
		
		menu_sub = gtk.Menu()
		item.set_submenu(menu_sub)
		item = gtk.MenuItem("Online")
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'online')
		item = gtk.MenuItem("Away")
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'away')
		item = gtk.MenuItem("NA")
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'na')
		item = gtk.MenuItem("DND")
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'dnd')
		item = gtk.MenuItem()
		menu_sub.append(item)
		item = gtk.MenuItem("Offline")
		menu_sub.append(item)
		item.connect("activate", self.change_status, account, 'offline')
		
		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem("Edit account")
		menu.append(item)
		item.connect("activate", self.on_edit_account, account)
		
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
	
	def authorize(self, widget, jid, account):
		"""Authorize a user"""
		self.plugin.send('AUTH', account, jid)

	def req_sub(self, widget, jid, txt, account):
		"""Request subscription to a user"""
		self.plugin.send('SUB', account, (jid, txt))
		if not self.contacts[account].has_key(jid):
			user1 = user(jid, jid, ['general'], 'requested', \
				'requested', 'sub', '')
			self.add_user_to_roster(user1, account)
	
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
		return gtk.FALSE

	def on_req_usub(self, widget, user, account):
		"""Remove a user"""
		window = confirm_Window('Are you sure you want to remove ' + user.name + \
			' (' + user.jid + ') from your roster ?')
		if window.wait() == gtk.RESPONSE_OK:
			self.plugin.send('UNSUB', account, user.jid)
			self.remove_user(user, account)
			del self.contacts[account][user.jid]

	def change_status(self, widget, account, status):
		if status != 'online' and status != 'offline':
			w = awayMsg_Window()
			txt = w.run()
			if txt != -1:
				self.plugin.send('STATUS', account, (status, txt))
		else:
			txt = status
			self.plugin.send('STATUS', account, (status, txt))

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
			warning_Window("You must setup an account before connecting to jabber network.")
			return
		for acct in accounts:
			self.plugin.send('STATUS', acct, (status, txt))
	
	def set_optionmenu(self):
		#table to change index in plugin.connected to index in optionmenu
		table = {0:6, 1:0, 2:1, 3:2, 4:3, 5:4}
		mini = min(self.plugin.connected.values())
		optionmenu = self.xml.get_widget('optionmenu')
		#temporarily block signal in order not to send status that we show
		#in the optionmenu
		optionmenu.handler_block(self.id_signal_optionmenu)
		optionmenu.set_history(table[mini])
		optionmenu.handler_unblock(self.id_signal_optionmenu)

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
				user = self.contacts[account][jid]
				self.chg_user_status(user, 'offline', 'Disconnected', account)
		elif self.plugin.connected[account] == 0:
			self.plugin.sleeper = None#common.sleepy.Sleepy(\
				#self.plugin.config['autoawaytime']*60, \
				#self.plugin.config['autoxatime']*60)
		self.plugin.connected[account] = statuss.index(status)
		self.set_optionmenu()

	def on_message(self, jid, msg, account):
		"""when we receive a message"""
		if not self.contacts[account].has_key(jid):
			user1 = user(jid, jid, ['not in list'], \
				'not in list', 'not in list', 'none', '')
			self.add_user_to_roster(user1, account)
		autopopup = self.plugin.config['autopopup']
		if autopopup == 0 and not \
			self.plugin.windows[account]['chats'].has_key(jid):
			#We save it in a queue
			if not self.plugin.queues[account].has_key(jid):
				model = self.tree.get_model()
				self.plugin.queues[account][jid] = Queue.Queue(50)
				for i in self.get_user_iter(jid, account):
					model.set_value(i, 0, self.pixbufs['message'])
			tim = time.strftime("[%H:%M:%S]")
			self.plugin.queues[account][jid].put((msg, tim))
		else:
			if not self.plugin.windows[account]['chats'].has_key(jid):
				self.plugin.windows[account]['chats'][jid] = \
					message_Window(self.contacts[account][jid], self.plugin, account)
			self.plugin.windows[account]['chats'][jid].print_conversation(msg)

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
		print "plugin gtkgui stopped"
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
					message_Window(self.contacts[account][jid], self.plugin, account)

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

	def on_cell_edited (self, cell, row, new_text):
		"""When an iter is editer :
		if text has changed, rename the user
		else open chat window"""
		model = self.tree.get_model()
		iter = model.get_iter_from_string(row)
		path = model.get_path(iter)
		acct_iter = model.get_iter((path[0]))
		account = model.get_value(acct_iter, 3)
		jid = model.get_value(iter, 3)
		old_text = self.contacts[account][jid].name
		#FIXME:If it is a double click, old_text == new_text
		if old_text == new_text:
			if self.plugin.windows[account]['chats'].has_key(jid):
				chat = self.plugin.windows[account]['chats'][jid]
				chat.xml.get_widget('Chat').present()
			elif self.contacts[account].has_key(jid):
				self.plugin.windows[account]['chats'][jid] = \
					message_Window(self.contacts[account][jid], self.plugin, account)
		else:
			model.set_value(iter, 1, new_text)
			self.contacts[account][jid].name = new_text
			self.plugin.send('UPDUSER', account, (jid, new_text, \
				self.contacts[account][jid].groups))
		
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
		for state in ('online', 'away', 'xa', 'dnd', 'offline', 'error', \
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
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'Gajim')
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
			if ev[0] == 'ROSTER':
				self.roster.mklists(ev[2], ev[1])
				self.roster.draw_roster()
			elif ev[0] == 'WARNING':
				warning_Window(ev[2])
			#('STATUS', account, status)
			elif ev[0] == 'STATUS':
				self.roster.on_status_changed(ev[1], ev[2])
			#('NOTIFY', account, (jid, status, message, resource))
			elif ev[0] == 'NOTIFY':
				jid = string.split(ev[2][0], '/')[0]
				resource = ev[2][3]
				if not resource:
					resource = ''
				if string.find(jid, "@") <= 0:
					#It must be an agent
					ji = string.replace(jid, '@', '')
				else:
					ji = jid
				#Update user
				if self.roster.contacts[ev[1]].has_key(ji):
					user = self.roster.contacts[ev[1]][ji]
					user.show = ev[2][1]
					user.status = ev[2][2]
					user.resource = resource
				if string.find(jid, "@") <= 0:
					#It must be an agent
					if not self.roster.contacts[ev[1]].has_key(ji):
						user1 = user(ji, ji, ['Agents'], ev[2][1], \
							ev[2][2], 'from', resource)
						self.roster.add_user_to_roster(user1, ev[1])
					else:
						#Update existing iter
						for i in self.roster.get_user_iter(ji, ev[1]):
							if self.roster.pixbufs.has_key(ev[2][1]):
								model.set_value(i, 0, self.roster.pixbufs[ev[2][1]])
				elif self.roster.contacts[ev[1]].has_key(ji):
					#It isn't an agent
					self.roster.chg_user_status(user, ev[2][1], ev[2][2], ev[1])
			#('MSG', account, (user, msg))
			elif ev[0] == 'MSG':
				if string.find(ev[2][0], "@") <= 0:
					jid = string.replace(ev[2][0], '@', '')
				else:
					jid = ev[2][0]
				self.roster.on_message(jid, ev[2][1], ev[1])
			#('SUBSCRIBE', account, (jid, text))
			elif ev[0] == 'SUBSCRIBE':
				authorize_Window(self, ev[2][0], ev[2][1], ev[1])
			#('SUBSCRIBED', account, (jid, nom, resource))
			elif ev[0] == 'SUBSCRIBED':
				if self.roster.contacts[ev[1]].has_key(ev[2][0]):
					u = self.roster.contacts[ev[1]][ev[2][0]]['user']
					u.name = ev[2][1]
					u.resource = ev[2][2]
					for i in self.roster.contacts[ev[1]][u.jid]['iter']:
						model.set_value(i, 1, u.name)
				else:
					user1 = user(ev[2][0], ev[2][0], ['general'], 'online', \
						'online', 'to', ev[2][2])
					self.roster.add_user(user1)
				warning_Window("You are now authorized by " + ev[2][0])
			elif ev[0] == 'UNSUBSCRIBED':
				warning_Window("You are now unsubscribed by " + ev[2])
				#TODO: change icon
			#('AGENTS', account, agents)
			elif ev[0] == 'AGENTS':
				if self.windows[ev[1]].has_key('browser'):
					self.windows[ev[1]]['browser'].agents(ev[2])
			#('AGENTS_INFO', account, (agent, infos))
			elif ev[0] == 'AGENT_INFO':
				if not ev[2][1].has_key('instructions'):
					warning_Window('error contacting %s' % ev[2][0])
				else:
					agentRegistration_Window(ev[2][0], ev[2][1], self, ev[1])
			#('ACC_OK', account, (hostname, login, pasword, name, ressource))
			elif ev[0] == 'ACC_OK':
				self.accounts[ev[2][3]] =  {'ressource': ev[2][4], \
					'password': ev[2][2], 'hostname': ev[2][0], 'name': ev[2][1]}
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
		if self.sleeper and (self.config['autoaway'] or self.config['autoxa'])\
			and (self.roster.optionmenu.get_history()==0 or \
			self.sleeper_state!=common.sleepy.STATE_AWAKE):
			self.sleeper.poll()
			state = self.sleeper.getState()
			if state != self.sleeper_state:
				if state == common.sleepy.STATE_AWAKE:
					#we go online
					self.roster.optionmenu.set_history(0)
					self.send('STATUS', None, ('online', ''))
				elif state == common.sleepy.STATE_AWAY and self.config['autoaway']:
					#we go away
					self.roster.optionmenu.set_history(1)
					self.send('STATUS', None, ('away', 'auto away (idle)'))
				elif state == common.sleepy.STATE_XAWAY and self.config['autoxa']:
					#we go extended away
					self.roster.optionmenu.set_history(2)
					self.send('STATUS',('xa', 'auto away (idel)'))
			self.sleeper_state = state
		return 1

	def __init__(self, quIN, quOUT):
		gtk.threads_init()
		gtk.threads_enter()
		self.queueIN = quIN
		self.queueOUT = quOUT
		self.send('ASK_CONFIG', None, ('GtkGui', 'GtkGui', {'autopopup':1,\
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
		for a in self.accounts.keys():
			self.windows[a] = {}
			self.windows[a]['infos'] = {}
			self.windows[a]['chats'] = {}
			self.queues[a] = {}
			self.connected[a] = 0
			self.nicks[a] = self.accounts[a]['name']
		self.roster = roster_Window(self)
		gtk.timeout_add(100, self.read_queue)
		gtk.timeout_add(1000, self.read_sleepy)
		self.sleeper = None
		self.sleeper_state = None
		gtk.main()
		gtk.threads_leave()

if __name__ == "__main__":
	plugin(None, None)

print "plugin gtkgui loaded"
