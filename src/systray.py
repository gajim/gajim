##	systray.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
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
import gobject
import dialogs
import os

import tooltips
import gtkgui_helpers

from gajim import Contact
from common import gajim
from common import helpers
from common import i18n

try:
	import egg.trayicon as trayicon	# gnomepythonextras trayicon
except:
	try:
		import trayicon # our trayicon
	except:
		gajim.log.debug('No trayicon module available')
		pass

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class Systray:
	'''Class for icon in the notification area
	This class is both base class (for systraywin32.py) and normal class
	for trayicon in GNU/Linux'''
	
	def __init__(self):
		self.jids = [] # Contain things like [account, jid, type_of_msg]
		self.new_message_handler_id = None
		self.t = None
		self.img_tray = gtk.Image()
		self.status = 'offline'
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'systray_context_menu', APP)
		self.systray_context_menu = self.xml.get_widget('systray_context_menu')
		self.xml.signal_autoconnect(self)

	def set_img(self):
		if len(self.jids) > 0:
			state = 'message'
		else:
			state = self.status
		image = gajim.interface.roster.jabber_state_images[state]
		if image.get_storage_type() == gtk.IMAGE_ANIMATION:
			self.img_tray.set_from_animation(image.get_animation())
		elif image.get_storage_type() == gtk.IMAGE_PIXBUF:
			self.img_tray.set_from_pixbuf(image.get_pixbuf())

	def add_jid(self, jid, account, typ):
		l = [account, jid, typ]
		# We can keep several single message 'cause we open them one by one
		if not l in self.jids or typ == 'normal':
			self.jids.append(l)
			self.set_img()

	def remove_jid(self, jid, account, typ):
		l = [account, jid, typ]
		if l in self.jids:
			self.jids.remove(l)
			self.set_img()

	def change_status(self, global_status):
		''' set tray image to 'global_status' '''
		# change image and status, only if it is different 
		if global_status is not None and self.status != global_status:
			self.status = global_status
		self.set_img()
	
	def start_chat(self, widget, account, jid):
		if gajim.interface.instances[account]['chats'].has_key(jid):
			gajim.interface.instances[account]['chats'][jid].window.present()
			gajim.interface.instances[account]['chats'][jid].set_active_tab(jid)
		elif gajim.contacts[account].has_key(jid):
			gajim.interface.roster.new_chat(
				gajim.contacts[account][jid][0], account)
			gajim.interface.instances[account]['chats'][jid].set_active_tab(jid)
	
	def on_new_message_menuitem_activate(self, widget, account):
		"""When new message menuitem is activated:
		call the NewMessageDialog class"""
		dialogs.NewMessageDialog(account)

	def make_menu(self, event = None):
		'''create chat with and new message (sub) menus/menuitems
		event is None when we're in Windows
		'''
		
		chat_with_menuitem = self.xml.get_widget('chat_with_menuitem')
		new_message_menuitem = self.xml.get_widget('new_message_menuitem')
		status_menuitem = self.xml.get_widget('status_menu')
		
		if self.new_message_handler_id:
			new_message_menuitem.handler_disconnect(
				self.new_message_handler_id)
			self.new_message_handler_id = None

		sub_menu = gtk.Menu()
		status_menuitem.set_submenu(sub_menu)

		# We need our own set of status icons, let's make 'em!
		iconset = gajim.config.get('iconset')
		if not iconset:
			iconset = 'sun'
		path = os.path.join(gajim.DATA_DIR, 'iconsets/' + iconset + '/16x16/')
		state_images = gajim.interface.roster.load_iconset(path)

		for show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible'):
			uf_show = helpers.get_uf_show(show, use_mnemonic = True)
			item = gtk.ImageMenuItem(uf_show)
			item.set_image(state_images[show])
			sub_menu.append(item)
			item.connect('activate', self.on_show_menuitem_activate, show)

		item = gtk.SeparatorMenuItem()
		sub_menu.append(item)

		item = gtk.ImageMenuItem(_('_Change Status Message...'))
		path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'rename.png')
		img = gtk.Image()
		img.set_from_file(path)
		item.set_image(img)
		sub_menu.append(item)
		item.connect('activate', self.on_change_status_message_activate)
		if not helpers.one_account_connected():
			item.set_sensitive(False)

		item = gtk.SeparatorMenuItem()
		sub_menu.append(item)

		uf_show = helpers.get_uf_show('offline', use_mnemonic = True)
		item = gtk.ImageMenuItem(uf_show)
		item.set_image(state_images['offline'])
		sub_menu.append(item)
		item.connect('activate', self.on_show_menuitem_activate, 'offline')

		iskey = len(gajim.connections) > 0
		chat_with_menuitem.set_sensitive(iskey)
		new_message_menuitem.set_sensitive(iskey)
		
		if len(gajim.connections) >= 2: # 2 or more connections? make submenus
			account_menu_for_chat_with = gtk.Menu()
			chat_with_menuitem.set_submenu(account_menu_for_chat_with)

			account_menu_for_new_message = gtk.Menu()
			new_message_menuitem.set_submenu(account_menu_for_new_message)

			for account in gajim.connections:
				#for chat_with
				item = gtk.MenuItem(_('using account ') + account)
				account_menu_for_chat_with.append(item)
				group_menu = self.make_groups_submenus_for_chat_with(account)
				item.set_submenu(group_menu)
				#for new_message
				item = gtk.MenuItem(_('using account ') + account)
				item.connect('activate',
					self.on_new_message_menuitem_activate, account)
				account_menu_for_new_message.append(item)
				
		elif len(gajim.connections) == 1: # one account
			# one account, no need to show 'as jid'
			# for chat_with
			account = gajim.connections.keys()[0]
			
			group_menu = self.make_groups_submenus_for_chat_with(account)
			chat_with_menuitem.set_submenu(group_menu)
					
			# for new message
			self.new_message_handler_id = new_message_menuitem.connect(
				'activate', self.on_new_message_menuitem_activate, account)

		if event is None:
			# None means windows (we explicitly popup in systraywin32.py)
			if self.added_hide_menuitem is False:
				self.systray_context_menu.prepend(gtk.SeparatorMenuItem())
				item = gtk.MenuItem(_('Hide this menu'))
				self.systray_context_menu.prepend(item)
				self.added_hide_menuitem = True
			
		else: # GNU and Unices
			self.systray_context_menu.popup(None, None, None, event.button, event.time)
		self.systray_context_menu.show_all()

	def on_show_all_events_menuitem_activate(self, widget):
		while len(self.jids):
			self.handle_first_event()

	def on_show_roster_menuitem_activate(self, widget):
		win = gajim.interface.roster.window
		win.present()

	def on_preferences_menuitem_activate(self, widget):
		if gajim.interface.instances['preferences'].window.get_property('visible'):
			gajim.interface.instances['preferences'].window.present()
		else:
			gajim.interface.instances['preferences'].window.show_all()

	def on_quit_menuitem_activate(self, widget):	
		gajim.interface.roster.on_quit_menuitem_activate(widget)

	def make_groups_submenus_for_chat_with(self, account):
		iconset = gajim.config.get('iconset')
		if not iconset:
			iconset = 'sun'
		path = os.path.join(gajim.DATA_DIR, 'iconsets/' + iconset + '/16x16/')
		state_images = gajim.interface.roster.load_iconset(path)
		
		groups_menu = gtk.Menu()
		
		for group in gajim.groups[account].keys():
			if group == _('Transports'):
				continue
			# at least one 'not offline' or 'without errors' in this group
			at_least_one = False
			item = gtk.MenuItem(group)
			groups_menu.append(item)
			contacts_menu = gtk.Menu()
			item.set_submenu(contacts_menu)
			for contacts in gajim.contacts[account].values():
				contact = gajim.get_highest_prio_contact_from_contacts(contacts)
				if group in contact.groups and contact.show != 'offline' and \
						contact.show != 'error':
					at_least_one = True
					s = contact.name.replace('_', '__') # two _ show one _ and no underline happens
					item = gtk.ImageMenuItem(s)
					# any given gtk widget can only be used in one place
					# (here we use it in status menu too)
					# gtk.Image is a widget, it's better we refactor to use gdk.gdk.Pixbuf allover
					img = state_images[contact.show]
					img_copy = gobject.new(gtk.Image, pixbuf=img.get_pixbuf())
					item.set_image(img_copy)
					item.connect('activate', self.start_chat, account,
							contact.jid)
					contacts_menu.append(item)
			
			if not at_least_one:
				message = _('All contacts in this group are offline or have errors')
				item = gtk.MenuItem(message)
				item.set_sensitive(False)
				contacts_menu.append(item)

		return groups_menu

	def on_left_click(self):
		win = gajim.interface.roster.window
		if len(self.jids) == 0:
			# no pending events, so toggle visible/hidden for roster window
			if win.get_property('visible'): # visible in ANY virtual desktop?
				win.hide() # we hide it from VD that was visible in
				
				# but we could be in another VD right now. eg vd2
				# and we want not only to hide it in vd1 but also show it in vd2
				gtkgui_helpers.possibly_move_window_in_current_desktop(win)
			else:
				win.present()
		else:
			self.handle_first_event()

	def handle_first_event(self):
		account = self.jids[0][0]
		jid = self.jids[0][1]
		typ = self.jids[0][2]
		self.handle_event(account, jid, typ)

	def handle_event(self, account, jid, typ):
		wins = gajim.interface.instances[account]
		w = None
		if typ == 'gc':
			if wins['gc'].has_key(jid):
				w = wins['gc'][jid]
		elif typ == 'chat':
			if wins['chats'].has_key(jid):
				w = wins['chats'][jid]
			else:
				gajim.interface.roster.new_chat(
					gajim.contacts[account][jid][0], account)
				w = wins['chats'][jid]
		elif typ == 'pm':
			if wins['chats'].has_key(jid):
				w = wins['chats'][jid]
			else:
				room_jid, nick = jid.split('/', 1)
				show = gajim.gc_contacts[account][room_jid][nick].show
				c = Contact(jid = jid, name = nick, groups = ['none'],
					show = show, ask = 'none')
				gajim.interface.roster.new_chat(c, account)
				w = wins['chats'][jid]
		elif typ in ('normal', 'file-request', 'file-request-error',
			'file-send-error', 'file-error', 'file-stopped', 'file-completed'):
			# Get the first single message event
			ev = gajim.get_first_event(account, jid, typ)
			# Open the window
			gajim.interface.roster.open_event(account, jid, ev)
		if w:
			w.set_active_tab(jid)
			w.window.present()
			w.window.window.focus()
			tv = w.conversation_textviews[jid]
			tv.scroll_to_end()

	def on_middle_click(self):
		'''middle click raises window to have complete focus (fe. get kbd events)
		but if already raised, it hides it'''
		win = gajim.interface.roster.window
		if win.is_active(): # is it fully raised? (eg does it receive kbd events?)
			win.hide()
		else:
			win.present()

	def on_clicked(self, widget, event):
		self.on_tray_leave_notify_event(widget, None)
		if event.button == 1: # Left click
			self.on_left_click()
		if event.button == 2: # middle click
			self.on_middle_click()
		if event.button == 3: # right click
			self.make_menu(event)
	
	def on_show_menuitem_activate(self, widget, show):
		# we all add some fake (we cannot select those nor have them as show)
		# but this helps to align with roster's status_combobox index positions
		l = ['online', 'chat', 'away', 'xa', 'dnd', 'invisible', 'SEPARATOR',
			'CHANGE_STATUS_MSG_MENUITEM', 'SEPARATOR', 'offline']
		index = l.index(show)
		gajim.interface.roster.status_combobox.set_active(index)

	def on_change_status_message_activate(self, widget):
		model = gajim.interface.roster.status_combobox.get_model()
		active = gajim.interface.roster.status_combobox.get_active()
		status = model[active][2].decode('utf-8')
		dlg = dialogs.ChangeStatusMessageDialog(status)
		message = dlg.run()
		if message is not None: # None if user press Cancel
			accounts = gajim.connections.keys()
			for acct in accounts:
				if not gajim.config.get_per('accounts', acct,
					'sync_with_global_status'):
					continue
				show = gajim.SHOW_LIST[gajim.connections[acct].connected]
				gajim.interface.roster.send_status(acct, show, message)

	def show_tooltip(self, widget):
		position = widget.window.get_origin()
		if self.tooltip.id == position:
			size = widget.window.get_size()
			self.tooltip.show_tooltip('', 
				(widget.window.get_pointer()[0], size[1]), position)
			
	def on_tray_motion_notify_event(self, widget, event):
		wireq=widget.size_request()
		position = widget.window.get_origin()
		if self.tooltip.timeout > 0:
			if self.tooltip.id != position:
				self.tooltip.hide_tooltip()
		if self.tooltip.timeout == 0 and \
			self.tooltip.id != position:
			self.tooltip.id = position
			self.tooltip.timeout = gobject.timeout_add(500,
				self.show_tooltip, widget)
	
	def on_tray_leave_notify_event(self, widget, event):
		position = widget.window.get_origin()
		if self.tooltip.timeout > 0 and \
			self.tooltip.id == position:
			self.tooltip.hide_tooltip()
		
	def show_icon(self):
		if not self.t:
			self.t = trayicon.TrayIcon('Gajim')
			eb = gtk.EventBox()
			# avoid draw seperate bg color in some gtk themes
			eb.set_visible_window(False)
			eb.set_events(gtk.gdk.POINTER_MOTION_MASK)
			eb.connect('button-press-event', self.on_clicked)
			eb.connect('motion-notify-event', self.on_tray_motion_notify_event)
			eb.connect('leave-notify-event', self.on_tray_leave_notify_event)
			self.tooltip = tooltips.NotificationAreaTooltip()

			self.img_tray = gtk.Image()
			eb.add(self.img_tray)
			self.t.add(eb)
			self.set_img()
		self.t.show_all()
	
	def hide_icon(self):
		if self.t:
			self.t.destroy()
			self.t = None
