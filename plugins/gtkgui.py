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
import gtk.glade
import gobject
import string
import common.optparser
CONFPATH = "~/.gajimrc"

class user:
	def __init__(self, *args):
		if len(args) == 0:
			self.name = ''
			self.server = ''
			self.resource = ''
			self.group = ''
			self.show = ''
			self.status = ''
		elif len(args) == 6:
			self.name = args[0]
			self.server = args[1]
			self.resource = args[2]
			self.group = args[3]
			self.show = args[4]
			self.status = args[5]
		elif ((len(args)) and (type (args[0]) == type (self)) and
			(self.__class__ == args[0].__class__)):
			self.name = args[0].name
			self.server = args[0].server
			self.resource = args[0].resource
			self.group = args[0].group
			self.show = args[0].show
			self.status = args[0].status
		else: raise TypeError, 'bad arguments'
#		self.jid = self.name + '@' + self.server + '/' + self.resource
		self.jid = self.name + '@' + self.server

class add:
	def delete_event(self, widget):
		self.Wadd.destroy()

	def on_subscribe(self, widget):
		who=self.xml.get_widget("entry_who").get_text()
		buf=self.xml.get_widget("textview_sub").get_buffer()
		start_iter = buf.get_start_iter()
		end_iter = buf.get_end_iter()
		txt = buf.get_text(start_iter, end_iter, 0)
		self.r.req_sub(who, txt)
		self.delete_event(self)
		
	def __init__(self, roster):
		self.r=roster
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'Add')
		self.Wadd=self.xml.get_widget("Add")
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_button_sub_clicked', self.on_subscribe)

class about:
	def delete_event(self, widget):
		self.Wabout.destroy()
		
	def __init__(self):
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'About')
		self.Wabout=self.xml.get_widget("About")
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)

class accounts:
	def delete_event(self, widget):
		self.window.destroy()
		
	def __init__(self):
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'Accounts')
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)

class message:
	def delete_event(self, widget):
		del self.roster.tab_messages[self.user.jid]
		self.window.destroy()
	
	def print_conversation(self, txt, contact = None):
		end_iter = self.convTxtBuffer.get_end_iter()
		if contact:
			self.convTxtBuffer.insert_with_tags_by_name(end_iter, '<moi> ', 'outgoing')
		else:
			self.convTxtBuffer.insert_with_tags_by_name(end_iter, '<' + self.user.name + '> ', 'incomming')
		self.convTxtBuffer.insert(end_iter, txt+'\n')
		self.conversation.scroll_to_mark(\
			self.convTxtBuffer.get_mark('end'), 0.1, 0, 0, 0)

	def on_msg_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Return:
			if (event.state & gtk.gdk.SHIFT_MASK):
				return 0
			txt_buffer = widget.get_buffer()
			start_iter = txt_buffer.get_start_iter()
			end_iter = txt_buffer.get_end_iter()
			txt = txt_buffer.get_text(start_iter, end_iter, 0)
			self.roster.queueOUT.put(('MSG',(self.user.jid, txt)))
			txt_buffer.set_text('', -1)
			self.print_conversation(txt, self.user.jid)
			widget.grab_focus()
			return 1
		return 0

	def __init__(self, user, roster):
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
		self.cfgParser.parseCfgFile()
		self.user = user
		self.roster = roster
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'Chat')
		self.window = self.xml.get_widget('Chat')
		self.window.set_title('Chat with ' + user.name)
		self.message = self.xml.get_widget('message')
		self.conversation = self.xml.get_widget('conversation')
		self.convTxtBuffer = self.conversation.get_buffer()
		end_iter=self.convTxtBuffer.get_end_iter()
		self.convTxtBuffer.create_mark('end', end_iter, 0)
		self.window.show()
		self.xml.signal_connect('gtk_widget_destroy', self.delete_event)
		self.xml.signal_connect('on_msg_key_press_event', self.on_msg_key_press_event)
		self.tag = self.convTxtBuffer.create_tag("incomming")
		color = self.cfgParser.GtkGui_inmsgcolor
		if not color : color = red
		self.tag.set_property("foreground", color)
		self.tag = self.convTxtBuffer.create_tag("outgoing")
		color = self.cfgParser.GtkGui_outmsgcolor
		if not color : color = blue
		self.tag.set_property("foreground", color)

class roster:
	def get_icon_pixbuf(self, stock):
		return self.tree.render_icon(stock, size = gtk.ICON_SIZE_MENU, detail = None)

	def mkl_group(self):
		""" l_group = {name:iter} """
		self.l_group = {}
		for d in self.l_contact.values():
			u=d['user']
			if not self.l_group.has_key(u.group):
				iterG = self.treestore.append(None, (self.pixbufs['online'], u.group, 'group'))
				self.l_group[u.group]=iterG

	def mkroster(self, tab):
		""" l_contact = {jid:{'user':_, 'iter':_] """
		self.l_contact = {}
		for jid in tab.keys():
			user1 = user(tab[jid]['nom'], tab[jid]['server'], tab[jid]['resource'], tab[jid]['group'], tab[jid]["show"], tab[jid]["status"])
			self.l_contact[user1.jid] = {'user': user1, 'iter': None}
		self.treestore.clear()
		self.mkl_group()
		for g in self.l_group.keys():
			for d in self.l_contact.values():
				c=d['user']
				if c.group == g:
					if c.show != 'offline' or self.showOffline:
						iterU = self.treestore.append(self.l_group[g], (self.pixbufs[c.show], c.name, c.jid))
						self.l_contact[c.jid]['iter'] = iterU
	
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
		self.found = 0
		self.treestore.foreach(self.update_iter, (jid, show))
		if self.found == 0:
			if not self.l_group.has_key(u.group):
				iterG = self.treestore.append(None, (self.pixbufs['online'], u.group, 'group'))
				self.l_group[u.group] = iterG
			iterU = self.treestore.append(self.l_group[u.group], (self.pixbufs[show], u.name, u.jid))
			self.l_contact[u.jid]['iter'] = iterU
		u.show = show
		u.status = status
		return 1
	
	def mk_menu_c(self, event, iter):
		self.menu_c = gtk.Menu()
		item = gtk.MenuItem("Remove")
		self.menu_c.append(item)
		item.connect("activate", self.on_req_usub, iter)
#		item = gtk.MenuItem("user2")
#		self.menu_c.append(item)
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
			else:
				self.mk_menu_c(event, iter)
			return gtk.TRUE
		return gtk.FALSE

	def on_req_usub(self, widget, iter):
		jid = self.treestore.get_value(iter, 2)
		self.queueOUT.put(('UNSUB', jid))
		del self.l_contact[jid]
		self.treestore.remove(iter)
	
	def req_sub(self, jid, txt):
		self.queueOUT.put(('SUB', (jid, txt)))
		if not self.l_contact.has_key(jid):
			user1 = user(jid, jid, jid, 'general', 'requested', 'requested')
			#TODO: ajouter un grp si necessaire
			iterU = self.treestore.append(self.l_group['general'], (self.pixbufs['requested'], jid, jid))
			self.l_contact[jid] = {'user':user1, 'iter':iterU}

	def on_status_changed(self, widget):
		self.queueOUT.put(('STATUS',widget.name))

	def on_add(self, widget):
		window_add = add(self)

	def on_about(self, widget):
		window_about = about()

	def on_accounts(self, widget):
		window_accounts = accounts()
	
	def on_quit(self, widget):
		self.queueOUT.put(('QUIT',''))
		gtk.mainquit()

	def on_row_activated(self, widget, path, col):
		iter = self.treestore.get_iter(path)
		jid = self.treestore.get_value(iter, 2)
		if self.tab_messages.has_key(jid):
			#NE FONCTIONNE PAS !
			self.tab_messages[jid].window.grab_focus()
		else:
			self.tab_messages[jid] = message(self.l_contact[jid]['user'], self)
		
	def __init__(self, queueOUT):
		#initialisation des variables
		# FIXME : handle no file ...
		self.cfgParser = common.optparser.OptionsParser(CONFPATH)
		self.cfgParser.parseCfgFile()
		self.xml = gtk.glade.XML('plugins/gtkgui.glade', 'Gajim')
		self.tree = self.xml.get_widget('treeview')
		self.treestore = gtk.TreeStore(gtk.gdk.Pixbuf, str, str)
		add_pixbuf = self.get_icon_pixbuf(gtk.STOCK_ADD)
		remove_pixbuf = self.get_icon_pixbuf(gtk.STOCK_REMOVE)
		requested_pixbuf = self.get_icon_pixbuf(gtk.STOCK_QUIT)
		self.pixbufs = {"online":add_pixbuf, "away":remove_pixbuf, \
			"xa":remove_pixbuf, "dnd":remove_pixbuf, "offline":remove_pixbuf, \
			"requested":requested_pixbuf}
		self.tree.set_model(self.treestore)
		self.queueOUT = queueOUT
		self.optionmenu = self.xml.get_widget('optionmenu')
		self.optionmenu.set_history(6)
		self.tab_messages = {}

		showOffline = self.cfgParser.GtkGui_showoffline
		if showOffline :
			self.showOffline = string.atoi(showOffline)
		else :
			self.showOffline = 0

		#colonnes
		self.col = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		self.col.pack_start(render_pixbuf, expand = False)
		self.col.add_attribute(render_pixbuf, 'pixbuf', 0)
		render_text = gtk.CellRendererText()
		self.col.pack_start(render_text, expand = True)
		self.col.add_attribute(render_text, 'text', 1)
		self.tree.append_column(self.col)

		#signals
		self.xml.signal_connect('gtk_main_quit', self.on_quit)
		self.xml.signal_connect('on_accounts_activate', self.on_accounts)
		self.xml.signal_connect('on_add_activate', self.on_add)
		self.xml.signal_connect('on_about_activate', self.on_about)
		self.xml.signal_connect('on_quit_activate', self.on_quit)
		self.xml.signal_connect('on_treeview_event', self.on_treeview_event)
		self.xml.signal_connect('on_status_changed', self.on_status_changed)
		self.xml.signal_connect('on_row_activated', self.on_row_activated)
#		self.mk_menu_c()

class plugin:
	def read_queue(self):
		while self.queueIN.empty() == 0:
			ev = self.queueIN.get()
#			print ev
			if ev[0] == 'ROSTER':
				self.r.mkroster(ev[1])
			elif ev[0] == 'NOTIFY':
				if self.r.l_contact.has_key(ev[1][0]):
					self.r.chg_status(ev[1][0], ev[1][1], ev[1][2])
			elif ev[0] == 'MSG':
				if not self.r.tab_messages.has_key(ev[1][0]):
					self.r.tab_messages[ev[1][0]] = message(self.r.l_contact[ev[1][0]]['user'], self.r)
				self.r.tab_messages[ev[1][0]].print_conversation(ev[1][1])
			elif ev[0] == 'SUBSCRIBED':
				u = self.r.l_contact[ev[1]['jid'][0]]
				u.name = ev[1]['nom']
				u.server = ev[1]['server']
				u.resource = ev[1]['resource']
				self.r.treestore.set_value(self.r.l_contact[u.jid]['iter'], 1, u.name)
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
