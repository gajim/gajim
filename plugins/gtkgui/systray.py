##	plugins/systray.py
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

from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'

class systrayDummy:
	"""Class when we don't want icon in the systray"""
	def add_jid(self, jid, account):
		pass
	def remove_jid(self, jid, account):
		pass
	def set_status(self, status):
		pass
	def show_icon(self):
		pass
	def hide_icon(self):
		pass
	def __init__(self):
		self.t = gtk.Button()
	

class systray:
	"""Class for icon in the systray"""
	def set_img(self):
		if len(self.jids) > 0:
			status = 'message'
		else:
			status = self.status
		image = self.plugin.roster.pixbufs[status]
		if image.get_storage_type() == gtk.IMAGE_ANIMATION:
			self.img_tray.set_from_animation(image.get_animation())
		elif image.get_storage_type() == gtk.IMAGE_PIXBUF:
			self.img_tray.set_from_pixbuf(image.get_pixbuf())

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

	def set_cb(self, widget, status):
		statuss = ['online', 'away', 'xa', 'dnd', 'invisible', 'offline']
		self.plugin.roster.cb.set_active(statuss.index(status))

	def start_chat(self, widget, account, jid):
		if self.plugin.windows[account]['chats'].has_key(jid):
			self.plugin.windows[account]['chats'][jid].window.present()
		elif self.plugin.roster.contacts[account].has_key(jid):
			self.plugin.roster.new_chat(
				self.plugin.roster.contacts[account][jid][0], account)

	def mk_menu(self, event):
		menu = gtk.Menu()
		item = gtk.TearoffMenuItem()
		menu.append(item)
		
		item = gtk.MenuItem(_("Status"))
		menu.append(item)
		sub_menu = gtk.Menu()
		item.set_submenu(sub_menu)
		item = gtk.MenuItem(_("Online"))
		sub_menu.append(item)
		item.connect("activate", self.set_cb, 'online')
		item = gtk.MenuItem(_("Away"))
		sub_menu.append(item)
		item.connect("activate", self.set_cb, 'away')
		item = gtk.MenuItem(_("NA"))
		sub_menu.append(item)
		item.connect("activate", self.set_cb, 'xa')
		item = gtk.MenuItem(_("DND"))
		sub_menu.append(item)
		item.connect("activate", self.set_cb, 'dnd')
		item = gtk.MenuItem(_("Invisible"))
		sub_menu.append(item)
		item.connect("activate", self.set_cb, 'invisible')
		item = gtk.MenuItem()
		sub_menu.append(item)
		item = gtk.MenuItem(_("Offline"))
		sub_menu.append(item)
		item.connect("activate", self.set_cb, 'offline')
		
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
						item = gtk.MenuItem(user.name.replace('_', '__'))
						menu_user.append(item)
						item.connect("activate", self.start_chat, account, user.jid)

		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem(_("Quit"))
		menu.append(item)
		item.connect("activate", self.plugin.roster.on_quit_menuitem_activate)
		
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def on_clicked(self, widget, event):
		if event.type == gtk.gdk.BUTTON_PRESS and event.button == 1:
			if len(self.jids) == 0:
				win = self.plugin.roster.window
				if win.iconify_initially:
					win.deiconify()
				else:
					if win.is_active():
						win.iconify()
					else:
						win.present()
			else:
				account = self.jids[0][0]
				jid = self.jids[0][1]
				if self.plugin.windows[account]['gc'].has_key(jid):
					self.plugin.windows[account]['gc'][jid].active_tab(jid)
					self.plugin.windows[account]['gc'][jid].window.present()
				elif self.plugin.windows[account]['chats'].has_key(jid):
					self.plugin.windows[account]['chats'][jid].active_tab(jid)
					self.plugin.windows[account]['chats'][jid].window.present()
				else:
					self.plugin.roster.new_chat(
						self.plugin.roster.contacts[account][jid][0], account)
		if event.button == 3:
			self.mk_menu(event)

	def show_icon(self):
		if not self.t:
			self.t = trayicon.TrayIcon("Gajim")
			eb = gtk.EventBox()
			eb.connect("button-press-event", self.on_clicked)
			self.tip = gtk.Tooltips()
			self.tip.set_tip(self.t, 'Gajim')
			self.img_tray = gtk.Image()
			eb.add(self.img_tray)
			self.t.add(eb)
			self.set_img()
		self.t.show_all()
	
	def hide_icon(self):
		if self.t:
			self.t.destroy()
			self.t = None

	def __init__(self, plugin):
		self.plugin = plugin
		self.jids = []
		self.t = None
		self.img_tray = gtk.Image()
		self.status = 'offline'
		global trayicon
		import trayicon
