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
from dialogs import *

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
		self.jids = []

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
		#we look for the number of unread messages
		#in roster
		nb = self.plugin.roster.nb_unread
		for acct in self.plugin.accounts:
			#in chat / groupchat windows
			for kind in ['chats', 'gc']:
				for jid in self.plugin.windows[acct][kind]:
					if jid != 'tabbed':
						nb += self.plugin.windows[acct][kind][jid].nb_unread[jid]
		if nb > 1:
			label = _('Gajim - %s unread messages') % nb
		else:
			label = _('Gajim - 1 unread message')
		self.tip.set_tip(self.t, label)

	def remove_jid(self, jid, account):
		list = [account, jid]
		if list in self.jids:
			self.jids.remove(list)
			self.set_img()
		#we look for the number of unread messages
		#in roster
		nb = self.plugin.roster.nb_unread
		for acct in self.plugin.accounts:
			#in chat / groupchat windows
			for kind in ['chats', 'gc']:
				for jid in self.plugin.windows[acct][kind]:
					if jid != 'tabbed':
						nb += self.plugin.windows[acct][kind][jid].nb_unread[jid]
		if nb > 1:
			label = _('Gajim - %s unread messages') % nb
		elif nb == 1:
			label = _('Gajim - 1 unread message')
		else:
			label = 'Gajim'
		self.tip.set_tip(self.t, label)

	def set_status(self, status):
		self.status = status
		self.set_img()

	def start_chat(self, widget, account, jid):
		if self.plugin.windows[account]['chats'].has_key(jid):
			self.plugin.windows[account]['chats'][jid].window.present()
		elif self.plugin.roster.contacts[account].has_key(jid):
			self.plugin.roster.new_chat(
				self.plugin.roster.contacts[account][jid][0], account)
	
	def on_new_message_menuitem_activate(self, widget, account):
		"""When new message menuitem is activated:
		call the New_message_dialog class"""
		New_message_dialog(self.plugin, account)

	def make_menu(self, event):
		"""create chat with and new message (sub) menus/menuitems"""
		
		chat_with_menuitem = self.xml.get_widget('chat_with_menuitem')
		#menu.append(chat_with_menuitem)
		new_message_menuitem = self.xml.get_widget('new_message_menuitem')
		#menu.append(new_message_menuitem)
		
		if len(self.plugin.accounts.keys()) > 0:
			chat_with_menuitem.set_sensitive(True)
			new_message_menuitem.set_sensitive(True)
		else:
			chat_with_menuitem.set_sensitive(False)
			new_message_menuitem.set_sensitive(False)
		
		if len(self.plugin.accounts.keys()) >= 2: # 2 or more accounts? make submenus
			account_menu_for_chat_with = gtk.Menu()
			chat_with_menuitem.set_submenu(account_menu_for_chat_with)

			account_menu_for_new_message = gtk.Menu()
			new_message_menuitem.set_submenu(account_menu_for_new_message)

			for account in self.plugin.accounts.keys():
				our_jid = self.plugin.accounts[account]['name'] + '@' +\
					self.plugin.accounts[account]['hostname']
				#for chat_with
				item = gtk.MenuItem(_('as ') + our_jid)
				account_menu_for_chat_with.append(item)
				group_menu = self.make_groups_submenus_for_chat_with(account)
				item.set_submenu(group_menu)
				#for new_message
				item = gtk.MenuItem(_('as ') + our_jid)
				item.connect('activate',\
					self.on_new_message_menuitem_activate, account)
				account_menu_for_new_message.append(item)
				
		elif len(self.plugin.accounts.keys()) == 1: # one account
			#one account, no need to show 'as jid
			#for chat_with
			account = self.plugin.accounts.keys()[0]
			
			group_menu = self.make_groups_submenus_for_chat_with(account)
			chat_with_menuitem.set_submenu(group_menu)
					
			#for new message
			self.new_message_handler_id = new_message_menuitem.connect(\
				'activate', self.on_new_message_menuitem_activate, account)

		self.systray_context_menu.popup(None, None, None, event.button, event.time)
		self.systray_context_menu.show_all()
		self.systray_context_menu.reposition()
	
	def on_quit_menuitem_activate(self, widget):	
		self.plugin.roster.on_quit_menuitem_activate(widget)

	def make_groups_submenus_for_chat_with(self, account):
		groups_menu = gtk.Menu()
		
		for group in self.plugin.roster.groups[account].keys():
			if group == 'Agents':
				continue
			# at least one not offline or with errors in this group
			at_least_one = False
			item = gtk.MenuItem(group)
			groups_menu.append(item)
			contacts_menu = gtk.Menu()
			item.set_submenu(contacts_menu)
			for users in self.plugin.roster.contacts[account].values():
				user = users[0]
				if group in user.groups and user.show != 'offline' and \
						user.show != 'error':
					at_least_one = True
					s = user.name.replace('_', '__') + ' (' + user.show + ')'
					item = gtk.MenuItem(s)
					item.connect('activate', self.start_chat, account,\
							user.jid)
					contacts_menu.append(item)
			
			if not at_least_one:
				message = _('All contacts in this group are offline or have errors')
				item = gtk.MenuItem(message)
				item.set_sensitive(False)
				contacts_menu.append(item)

		return groups_menu

	def on_clicked(self, widget, event):
		if event.type == gtk.gdk.BUTTON_PRESS and event.button == 1:
			if len(self.jids) == 0:
				win = self.plugin.roster.window
				if win.is_active():
					win.hide()
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
		if event.button == 3: # right click
			self.make_menu(event)
	
	def on_online_menuitem_activate(self, widget):
		self.plugin.roster.cb.set_active(0) # 0 is online
	
	def on_away_menuitem_activate(self, widget):
		self.plugin.roster.cb.set_active(1) # 1 is away
	
	def on_xa_menuitem_activate(self, widget):
		self.plugin.roster.cb.set_active(2) # 2 is xa

	def on_dnd_menuitem_activate(self, widget):
		self.plugin.roster.cb.set_active(3) # 3 is dnd

	def on_invisible_menuitem_activate(self, widget):
		self.plugin.roster.cb.set_active(4) # 4 is invisible
		
	def on_offline_menuitem_activate(self, widget):
		self.plugin.roster.cb.set_active(5) # 5 is offline

	def show_icon(self):
		if not self.t:
			self.t = trayicon.TrayIcon('Gajim')
			eb = gtk.EventBox()
			eb.connect('button-press-event', self.on_clicked)
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
		self.tip = gtk.Tooltips()
		self.img_tray = gtk.Image()
		self.status = 'offline'
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'systray_context_menu', APP)
		self.systray_context_menu = self.xml.get_widget('systray_context_menu')
		self.xml.signal_autoconnect(self)
		global trayicon
		try:
			import egg.trayicon as trayicon	# gnomepythonextras trayicon
		except:
			import trayicon # yann's trayicon
