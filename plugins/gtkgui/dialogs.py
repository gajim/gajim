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
#import os,string,time,Queue
#import common.optparser,common.sleepy

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'


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
