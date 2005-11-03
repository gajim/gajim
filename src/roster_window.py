##	roster_window.py
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
import pango
import gobject
import os
import time

import common.sleepy
import tabbed_chat_window
import groupchat_window
import history_window
import dialogs
import config
import disco
import gtkgui_helpers
import cell_renderer_image
import tooltips

from gajim import Contact
from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

#(icon, name, type, jid, account, editable, s)
(
C_IMG, # image to show state (online, new message etc)
C_NAME, # cellrenderer text that holds contact nickame
C_TYPE, # account, group or contact?
C_JID, # the jid of the row
C_ACCOUNT, # cellrenderer text that holds account name
C_EDITABLE, # cellrenderer text that holds name editable or not?
C_SECPIXBUF, # econdary_pixbuf
) = range(7)


GTKGUI_GLADE = 'gtkgui.glade'

class RosterWindow:
	'''Class for main window of gtkgui interface'''

	def get_account_iter(self, name):
		if self.regroup:
			return
		model = self.tree.get_model()
		if model is None:
			return
		account_iter = model.get_iter_root()
		while account_iter:
			account_name = model[account_iter][C_NAME].decode('utf-8')
			if name == account_name:
				break
			account_iter = model.iter_next(account_iter)
		return account_iter

	def get_group_iter(self, name, account):
		model = self.tree.get_model()
		root = self.get_account_iter(account)
		group_iter = model.iter_children(root)
		while group_iter:
			group_name = model[group_iter][C_NAME].decode('utf-8')
			if name == group_name:
				break
			group_iter = model.iter_next(group_iter)
		return group_iter

	def get_contact_iter(self, jid, account):
		model = self.tree.get_model()
		acct = self.get_account_iter(account)
		found = []
		fin = False
		if model is None: # when closing Gajim model can be none (async pbs?)
			return found
		group_iter = model.iter_children(acct)
		while group_iter:
			user_iter = model.iter_children(group_iter)
			while user_iter:
				if jid == model[user_iter][C_JID].decode('utf-8'):
					found.append(user_iter)
				user_iter = model.iter_next(user_iter)
			group_iter = model.iter_next(group_iter)
		return found

	def add_account_to_roster(self, account):
		if self.regroup:
			return
		model = self.tree.get_model()
		if self.get_account_iter(account):
			return
		statuss = ['offline', 'connecting', 'online', 'chat',
			'away', 'xa', 'dnd', 'invisible']
		status = statuss[gajim.connections[account].connected]

		tls_pixbuf = None
		if gajim.con_types.has_key(account) and \
			gajim.con_types[account] in ('tls', 'ssl'):
			tls_pixbuf = self.window.render_icon(gtk.STOCK_DIALOG_AUTHENTICATION,
				gtk.ICON_SIZE_MENU) # the only way to create a pixbuf from stock

		our_jid = gajim.get_jid_from_account(account)

		model.append(None, [self.jabber_state_images[status], account,
			'account', our_jid, account, False, tls_pixbuf])

	def remove_newly_added(self, jid, account):
		if jid in gajim.newly_added[account]:
			gajim.newly_added[account].remove(jid)
			self.draw_contact(jid, account)

	def add_contact_to_roster(self, jid, account):
		'''Add a contact to the roster and add groups if they aren't in roster'''
		showOffline = gajim.config.get('showoffline')
		if not gajim.contacts[account].has_key(jid):
			return
		users = gajim.contacts[account][jid]
		user = users[0]
		if user.jid.find('@') <= 0: # if not '@' or '@' starts the jid ==> agent
			user.groups = [_('Transports')]
		elif user.groups == []:
			user.groups.append(_('General'))

		if user.show in ('offline', 'error') and \
		   not showOffline and (not _('Transports') in user.groups or \
			gajim.connections[account].connected < 2) and \
		   not gajim.awaiting_events[account].has_key(user.jid):
			return

		model = self.tree.get_model()
		for g in user.groups:
			iterG = self.get_group_iter(g, account)
			if not iterG:
				IterAcct = self.get_account_iter(account)
				iterG = model.append(IterAcct, [self.jabber_state_images['closed'],
					g, 'group', g, account, False, None])
			if not gajim.groups[account].has_key(g): #It can probably never append
				if account + g in self.collapsed_rows:
					ishidden = False
				else:
					ishidden = True
				gajim.groups[account][g] = { 'expand': ishidden }
			if not account in self.collapsed_rows and \
			   not gajim.config.get('mergeaccounts'):
				self.tree.expand_row((model.get_path(iterG)[0]), False)

			typestr = 'contact'
			if g == _('Transports'):
				typestr = 'agent'

			model.append(iterG, [self.jabber_state_images[user.show], user.name,
					typestr, user.jid, account, False, None]) # FIXME None --> avatar
			
			if gajim.groups[account][g]['expand']:
				self.tree.expand_row(model.get_path(iterG), False)
		self.draw_contact(jid, account)
	
	def really_remove_contact(self, user, account):
		if user.jid in gajim.newly_added[account]:
			return
		if user.jid.find('@') < 1 and gajim.connections[account].connected > 1: # It's an agent
			return
		if user.jid in gajim.to_be_removed[account]:
			gajim.to_be_removed[account].remove(user.jid)
		if gajim.config.get('showoffline'):
			self.draw_contact(user.jid, account)
			return
		self.remove_contact(user, account)
	
	def remove_contact(self, user, account):
		'''Remove a user from the roster'''
		if user.jid in gajim.to_be_removed[account]:
			return
		model = self.tree.get_model()
		for i in self.get_contact_iter(user.jid, account):
			parent_i = model.iter_parent(i)
			group = model.get_value(parent_i, 3).decode('utf-8')
			model.remove(i)
			if model.iter_n_children(parent_i) == 0:
				model.remove(parent_i)
				# We need to check all contacts, even offline contacts
				for jid in gajim.contacts[account]:
					if group in gajim.contacts[account][jid][0].groups:
						break
				else:
					if gajim.groups[account].has_key(group):
						del gajim.groups[account][group]

	def get_appropriate_state_images(self, jid):
		'''check jid and return the appropriate state images dict'''
		transport = gajim.get_transport_name_from_jid(jid)
		if transport:
			return self.transports_state_images[transport]
		return self.jabber_state_images

	def draw_contact(self, jid, account):
		'''draw the correct state image and name'''
		model = self.tree.get_model()
		iters = self.get_contact_iter(jid, account)
		if len(iters) == 0:
			return
		contact_instances = gajim.get_contact_instances_from_jid(account, jid)
		contact = gajim.get_highest_prio_contact_from_contacts(contact_instances)
		name = contact.name
		if len(contact_instances) > 1:
			name += ' (' + unicode(len(contact_instances)) + ')'

		state_images = self.get_appropriate_state_images(jid)
		if gajim.awaiting_events[account].has_key(jid):
			#TODO: change icon for FT
			img = state_images['message']
		elif jid.find('@') <= 0: # if not '@' or '@' starts the jid ==> agent
			img = state_images[contact.show]					
		else:
			if contact.sub in ('both', 'to'):
				img = state_images[contact.show]
			else:
				if contact.ask == 'subscribe':
					img = state_images['requested']
				else:
					transport = gajim.get_transport_name_from_jid(jid)
					if transport and state_images.has_key(contact.show):
						img = state_images[contact.show]
					else:
						img = state_images['not in the roster']
		for iter in iters:
			model[iter][C_IMG] = img
			model[iter][C_NAME] = name
			#FIXME: add avatar

	def join_gc_room(self, account, room_jid, nick, password):
		if room_jid in gajim.interface.windows[account]['gc'] and \
		gajim.gc_connected[account][room_jid]:
			dialogs.ErrorDialog(_('You are already in room %s') %room_jid
				).get_response()
			return
		invisible_show = gajim.SHOW_LIST.index('invisible')
		if gajim.connections[account].connected == invisible_show:
			dialogs.ErrorDialog(_('You cannot join a room while you are invisible')
				).get_response()
			return
		room, server = room_jid.split('@')
		if not room_jid in gajim.interface.windows[account]['gc']:
			self.new_room(room_jid, nick, account)
		gajim.interface.windows[account]['gc'][room_jid].set_active_tab(room_jid)
		gajim.interface.windows[account]['gc'][room_jid].window.present()
		gajim.connections[account].join_gc(nick, room, server, password)

	def on_bookmark_menuitem_activate(self, widget, account, bookmark):
		self.join_gc_room(account, bookmark['jid'], bookmark['nick'],
			bookmark['password'])

	def on_bm_header_changed_state(self, widget, event):
		widget.set_state(gtk.STATE_NORMAL) #do not allow selected_state

	def on_send_server_message_menuitem_activate(self, widget, account):
		server = gajim.config.get_per('accounts', account, 'hostname')
		server += '/announce/online'
		dialogs.SingleMessageWindow(account, server, 'send')

	def on_xml_console_menuitem_activate(self, widget, account):
		if gajim.interface.windows[account].has_key('xml_console'):
			gajim.interface.windows[account]['xml_console'].window.present()
		else:
			gajim.interface.windows[account]['xml_console'].window.show_all()

	def on_set_motd_menuitem_activate(self, widget, account):
		server = gajim.config.get_per('accounts', account, 'hostname')
		server += '/announce/motd'
		dialogs.SingleMessageWindow(account, server, 'send')

	def on_update_motd_menuitem_activate(self, widget, account):
		server = gajim.config.get_per('accounts', account, 'hostname')
		server += '/announce/motd/update'
		dialogs.SingleMessageWindow(account, server, 'send')

	def on_delete_motd_menuitem_activate(self, widget, account):
		server = gajim.config.get_per('accounts', account, 'hostname')
		server += '/announce/motd/delete'
		gajim.connections[account].send_motd(server)	
	
	def on_online_users_menuitem_activate(self, widget, account):
		pass #FIXME: impement disco in users for 0.9

	def get_and_connect_advanced_menuitem_menu(self, account):
		xml = gtk.glade.XML(GTKGUI_GLADE, 'advanced_menuitem_menu', APP)
		advanced_menuitem_menu = xml.get_widget('advanced_menuitem_menu')
		
		send_single_message_menuitem = xml.get_widget(
			'send_single_message_menuitem')
		xml_console_menuitem = xml.get_widget('xml_console_menuitem')
		administrator_menuitem = xml.get_widget('administrator_menuitem')
		online_users_menuitem = xml.get_widget('online_users_menuitem')
		send_server_message_menuitem = xml.get_widget(
			'send_server_message_menuitem')
		set_motd_menuitem = xml.get_widget('set_motd_menuitem')
		update_motd_menuitem = xml.get_widget('update_motd_menuitem')
		delete_motd_menuitem = xml.get_widget('delete_motd_menuitem')
		
		send_single_message_menuitem.connect('activate',
			self.on_send_single_message_menuitem_activate, account)

		xml_console_menuitem.connect('activate',
			self.on_xml_console_menuitem_activate, account)

		#FIXME: 0.9 should have this: it does disco in the place where users are
		online_users_menuitem.set_no_show_all(True)
		online_users_menuitem.hide()
		online_users_menuitem.connect('activate',
			self.on_online_users_menuitem_activate, account)

		send_server_message_menuitem.connect('activate',
			self.on_send_server_message_menuitem_activate, account)

		set_motd_menuitem.connect('activate',
			self.on_set_motd_menuitem_activate, account)

		update_motd_menuitem.connect('activate',
			self.on_update_motd_menuitem_activate, account)
		
		delete_motd_menuitem.connect('activate',
			self.on_delete_motd_menuitem_activate, account)
		
		advanced_menuitem_menu.show_all()
			
		return advanced_menuitem_menu

	def make_menu(self):
		'''create the main window's menus'''
		new_message_menuitem = self.xml.get_widget('new_message_menuitem')
		join_gc_menuitem = self.xml.get_widget('join_gc_menuitem')
		add_new_contact_menuitem  = self.xml.get_widget('add_new_contact_menuitem')
		service_disco_menuitem  = self.xml.get_widget('service_disco_menuitem')
		advanced_menuitem = self.xml.get_widget('advanced_menuitem')
		show_offline_contacts_menuitem = self.xml.get_widget(
			'show_offline_contacts_menuitem')
		profile_avatar_menuitem = self.xml.get_widget('profile_avatar_menuitem')
		
		# make it sensitive. it is insensitive only if no accounts are *available*
		advanced_menuitem.set_sensitive(True)


		if self.add_new_contact_handler_id:
			add_new_contact_menuitem.handler_disconnect(
				self.add_new_contact_handler_id)
			self.add_new_contact_handler_id = None

		if self.service_disco_handler_id:
			service_disco_menuitem.handler_disconnect(
				self.service_disco_handler_id)
			self.service_disco_handler_id = None
			
		if self.new_message_menuitem_handler_id:
			new_message_menuitem.handler_disconnect(
				self.new_message_menuitem_handler_id)
			self.new_message_menuitem_handler_id = None
			
		#remove the existing submenus
		add_new_contact_menuitem.remove_submenu()
		service_disco_menuitem.remove_submenu()
		join_gc_menuitem.remove_submenu()
		new_message_menuitem.remove_submenu()
		advanced_menuitem.remove_submenu()

		#remove the existing accelerator
		if self.have_new_message_accel:
			ag = gtk.accel_groups_from_object(self.window)[0]
			new_message_menuitem.remove_accelerator(ag, gtk.keysyms.n,
				gtk.gdk.CONTROL_MASK)
			self.have_new_message_accel = False

		#join gc
		sub_menu = gtk.Menu()
		join_gc_menuitem.set_submenu(sub_menu)
		at_least_one_account_connected = False
		multiple_accounts = len(gajim.connections) >= 2 #FIXME: stop using bool var here
		for account in gajim.connections:
			if gajim.connections[account].connected <= 1: #if offline or connecting
				continue
			if not at_least_one_account_connected:
				at_least_one_account_connected = True
			if multiple_accounts:
				label = gtk.Label()
				label.set_markup('<u>' + account.upper() +'</u>')
				item = gtk.MenuItem()
				item.add(label)
				item.connect('state-changed', self.on_bm_header_changed_state)
				sub_menu.append(item)
			
			item = gtk.MenuItem(_('_Join New Room'))
			item.connect('activate', self.on_join_gc_activate, account)
			sub_menu.append(item)

			for bookmark in gajim.connections[account].bookmarks:
				item = gtk.MenuItem(bookmark['name'])
				item.connect('activate', self.on_bookmark_menuitem_activate,
					account, bookmark)
				sub_menu.append(item)

		if at_least_one_account_connected: #FIXME: move this below where we do this check
			#and make sure it works
			newitem = gtk.SeparatorMenuItem() # seperator
			sub_menu.append(newitem)
		
			newitem = gtk.ImageMenuItem(_('Manage Bookmarks...'))
			img = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES,
				gtk.ICON_SIZE_MENU)
			newitem.set_image(img)
			newitem.connect('activate', self.on_manage_bookmarks_menuitem_activate)
			sub_menu.append(newitem)
			sub_menu.show_all()

		if multiple_accounts: # 2 or more accounts? make submenus
			#add
			sub_menu = gtk.Menu()
			for account in gajim.connections:
				if gajim.connections[account].connected <= 1:
					#if offline or connecting
					continue
				item = gtk.MenuItem(_('to %s account') % account)
				sub_menu.append(item)
				item.connect('activate', self.on_add_new_contact, account)
			add_new_contact_menuitem.set_submenu(sub_menu)
			sub_menu.show_all()
			
			#disco
			sub_menu = gtk.Menu()
			for account in gajim.connections:
				if gajim.connections[account].connected <= 1:
					#if offline or connecting
					continue
				item = gtk.MenuItem(_('using %s account') % account)
				sub_menu.append(item)
				item.connect('activate', self.on_service_disco_menuitem_activate,
					account)

			service_disco_menuitem.set_submenu(sub_menu)
			sub_menu.show_all()
			
			#new message
			sub_menu = gtk.Menu()
			for account in gajim.connections:
				if gajim.connections[account].connected <= 1:
					#if offline or connecting
					continue
				our_jid = gajim.config.get_per('accounts', account, 'name') + '@' +\
					gajim.config.get_per('accounts', account, 'hostname')
				item = gtk.MenuItem(_('as %s') % our_jid)
				sub_menu.append(item)
				item.connect('activate', self.on_new_message_menuitem_activate, 
									account)
	
			new_message_menuitem.set_submenu(sub_menu)
			sub_menu.show_all()
			
			#Advanced Actions
			sub_menu = gtk.Menu()
			for account in gajim.connections:
				item = gtk.MenuItem(_('for account %s') % account)
				sub_menu.append(item)
				advanced_menuitem_menu = self.get_and_connect_advanced_menuitem_menu(
					account)
				item.set_submenu(advanced_menuitem_menu)
			
			advanced_menuitem.set_submenu(sub_menu)
			sub_menu.show_all()
			
		else:
			if len(gajim.connections) == 1: # user has only one account
				#add
				if not self.add_new_contact_handler_id:
					self.add_new_contact_handler_id = add_new_contact_menuitem.connect(
						'activate', self.on_add_new_contact, gajim.connections.keys()[0])
				#disco
				if not self.service_disco_handler_id:
					self.service_disco_handler_id = service_disco_menuitem.connect( 
						'activate', self.on_service_disco_menuitem_activate, 
						gajim.connections.keys()[0])
				#new msg
				if not self.new_message_menuitem_handler_id:
					self.new_message_menuitem_handler_id = new_message_menuitem.\
						connect('activate', self.on_new_message_menuitem_activate, 
						gajim.connections.keys()[0])
				#new msg accel
				if not self.have_new_message_accel:
					ag = gtk.accel_groups_from_object(self.window)[0]
					new_message_menuitem.add_accelerator('activate', ag,
						gtk.keysyms.n,	gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
					self.have_new_message_accel = True
				
				account = gajim.connections.keys()[0]
				advanced_menuitem_menu = self.get_and_connect_advanced_menuitem_menu(
					account)
				advanced_menuitem.set_submenu(advanced_menuitem_menu)
			elif len(gajim.connections) == 0: # user has no accounts
				advanced_menuitem.set_sensitive(False)

		
		#FIXME: Gajim 0.9 should have this visible
		profile_avatar_menuitem.set_no_show_all(True)
		profile_avatar_menuitem.hide()
		
		if at_least_one_account_connected:
			new_message_menuitem.set_sensitive(True)
			join_gc_menuitem.set_sensitive(True)
			add_new_contact_menuitem.set_sensitive(True)
			service_disco_menuitem.set_sensitive(True)
			show_offline_contacts_menuitem.set_sensitive(True)
		else:
			# make the menuitems insensitive
			new_message_menuitem.set_sensitive(False)
			join_gc_menuitem.set_sensitive(False)
			add_new_contact_menuitem.set_sensitive(False)
			service_disco_menuitem.set_sensitive(False)
			show_offline_contacts_menuitem.set_sensitive(False)
			profile_avatar_menuitem.set_sensitive(False)

	def _change_style(self, model, path, iter, option):
		if option is None:
			model[iter][C_NAME] = model[iter][C_NAME]
		elif model[iter][C_TYPE] == 'account':
			if option == 'account':
				model[iter][C_NAME] = model[iter][C_NAME]
		elif model[iter][C_TYPE] == 'group':
			if option == 'group':
				model[iter][C_NAME] = model[iter][C_NAME]
		elif model[iter][C_TYPE] == 'contact':
			if option == 'contact':
				model[iter][C_NAME] = model[iter][C_NAME]

	def change_roster_style(self, option):
		model = self.tree.get_model()
		model.foreach(self._change_style, option)
	
	def draw_roster(self):
		'''Clear and draw roster'''
		self.tree.get_model().clear()
		for acct in gajim.connections:
			self.add_account_to_roster(acct)
			for jid in gajim.contacts[acct].keys():
				self.add_contact_to_roster(jid, acct)
		self.make_menu() # re-make menu in case an account was removed
		#FIXME: maybe move thie make_menu() in where we remove the account?
	
	def fill_contacts_and_groups_dicts(self, array, account):
		'''fill gajim.contacts and gajim.groups'''
		if not gajim.contacts.has_key(account):
			gajim.contacts[account] = {}
		if not gajim.groups.has_key(account):
			gajim.groups[account] = {}
		for jid in array.keys():
			jids = jid.split('/')
			#get jid
			ji = jids[0]
			#get resource
			resource = ''
			if len(jids) > 1:
				resource = '/'.join(jids[1:])
			#get name
			name = array[jid]['name']
			if not name:
				if ji.find('@') <= 0:
					name = ji
				else:
					name = jid.split('@')[0]
			show = 'offline' # show is offline by default
			status = '' #no status message by default

			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			contact1 = Contact(jid = ji, name = name, groups = array[jid]['groups'],
				show = show, status = status, sub = array[jid]['subscription'],
				ask = array[jid]['ask'], resource = resource, keyID = keyID)

			# when we draw the roster, we avoid having the same contact
			# more than once (f.e. we avoid showing it twice when 2 resources)
			gajim.contacts[account][ji] = [contact1]
			for g in array[jid]['groups'] :
				if g in gajim.groups[account].keys():
					continue

				if account + g in self.collapsed_rows:
					ishidden = False
				else:
					ishidden = True
				gajim.groups[account][g] = { 'expand': ishidden }

	def chg_contact_status(self, contact, show, status, account):
		'''When a contact changes his status'''
		showOffline = gajim.config.get('showoffline')
		model = self.tree.get_model()
		contact_instances = gajim.contacts[account][contact.jid]
		contact.show = show
		contact.status = status
		if show in ('offline', 'error') and \
		   not gajim.awaiting_events[account].has_key(contact.jid):
			if len(contact_instances) > 1: # if multiple resources
				contact_instances.remove(contact)
				self.draw_contact(contact.jid, account)
			elif not showOffline:
				self.remove_contact(contact, account)
			else:
				self.draw_contact(contact.jid, account)
		else:
			if not self.get_contact_iter(contact.jid, account):
				self.add_contact_to_roster(contact.jid, account)
			self.draw_contact(contact.jid, account)
		# print status in chat window and update status/GPG image
		if gajim.interface.windows[account]['chats'].has_key(contact.jid):
			jid = contact.jid
			gajim.interface.windows[account]['chats'][jid].set_state_image(jid)
			name = contact.name
			if contact.resource != '':
				name += '/' + contact.resource
			uf_show = helpers.get_uf_show(show)
			gajim.interface.windows[account]['chats'][jid].print_conversation(
				_('%s is now %s (%s)') % (name, uf_show, status), jid, 'status')
			
			if contact == gajim.get_contact_instance_with_highest_priority(\
				account, contact.jid):
				gajim.interface.windows[account]['chats'][jid].draw_name_banner(contact)

	def on_info(self, widget, user, account):
		'''Call vcard_information_window class to display user's information'''
		info = gajim.interface.windows[account]['infos']
		if info.has_key(user.jid):
			info[user.jid].window.present()
		else:
			info[user.jid] = dialogs.VcardWindow(user, account)

	def show_tooltip(self, contact):
		pointer = self.tree.get_pointer()
		props = self.tree.get_path_at_pos(pointer[0], pointer[1])
		if props and self.tooltip.id == props[0]:
			# check if the current pointer is at the same path
			# as it was before setting the timeout
			rect =  self.tree.get_cell_area(props[0], props[1])
			position = self.tree.window.get_origin()
			pointer = self.window.get_pointer()
			self.tooltip.show_tooltip(contact, (pointer[0], rect.height),
				 (position[0], position[1] + rect.y))
		else:
			self.tooltip.hide_tooltip()

	def on_roster_treeview_leave_notify_event(self, widget, event):
		model = widget.get_model()
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id == props[0]:
				self.tooltip.hide_tooltip()

	def on_roster_treeview_motion_notify_event(self, widget, event):
		model = widget.get_model()
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id != props[0]:
				self.tooltip.hide_tooltip()
		if props:
			[row, col, x, y] = props
			iter = None
			try:
				iter = model.get_iter(row)
			except:
				self.tooltip.hide_tooltip()
				return
			if model[iter][C_TYPE] == 'contact':
				# we're on a contact entry in the roster
				account = model[iter][C_ACCOUNT].decode('utf-8')
				jid = model[iter][C_JID].decode('utf-8')
				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, gajim.contacts[account][jid])
			elif model[iter][C_TYPE] == 'account':
				# we're on an account entry in the roster
				account = model[iter][C_NAME].decode('utf-8')
				jid = gajim.get_jid_from_account(account)
				contacts = []
				connection = gajim.connections[account]
				# get our current contact info
				contact = Contact(jid=jid, name=account, 
					show=connection.get_status(), 
					status=connection.status, 
					resource=gajim.config.get_per('accounts', connection.name, 'resource'), 
					priority=gajim.config.get_per('accounts', connection.name, 'priority'),
					keyID=gajim.config.get_per('accounts', connection.name, 'keyid'))
				contacts.append(contact)
				# if we're online ...
				if connection.connection:
					roster = connection.connection.getRoster()
					if roster.getItem(jid):
						resources = roster.getResources(jid)
						# ...get the contact info for our other online resources
						for resource in resources:
							show = roster.getShow(jid+'/'+resource)
							if not show:
								show = 'online'
							contact = Contact(jid=jid, name=account, 
								show=show,
								status=roster.getStatus(jid+'/'+resource), resource=resource, 
								priority=roster.getPriority(jid+'/'+resource))
							contacts.append(contact)
				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, contacts)

	def on_agent_logging(self, widget, jid, state, account):
		'''When an agent is requested to log in or off'''
		gajim.connections[account].send_agent_status(jid, state)

	def on_edit_agent(self, widget, contact, account):
		'''When we want to modify the agent registration'''
		gajim.connections[account].request_register_agent_info(contact.jid)

	def on_remove_agent(self, widget, contact, account):
		'''When an agent is requested to log in or off'''
		if gajim.config.get_per('accounts', account, 'hostname') == contact.jid:
			# We remove the server contact
			# remove it from treeview
			self.remove_contact(contact, account)
			del gajim.contacts[account][contact.jid]
			return

		window = dialogs.ConfirmationDialog(_('Transport "%s" will be removed') % contact.jid, _('You will no longer be able to send and receive messages to contacts from this transport.'))
		if window.get_response() == gtk.RESPONSE_OK:
			gajim.connections[account].unsubscribe_agent(contact.jid + '/' \
																		+ contact.resource)
			# remove transport from treeview
			self.remove_contact(contact, account)
			# remove transport's contacts from treeview
			for jid, contacts in gajim.contacts[account].items():
				contact = contacts[0]
				if jid.endswith('@' + contact.jid):
					gajim.log.debug(
					'Removing contact %s due to unregistered transport %s'\
						% (contact.jid, contact.name))
					self.remove_contact(contact, account)
			del gajim.contacts[account][contact.jid]

	def on_rename(self, widget, iter, path):
		model = self.tree.get_model()
		
		row_type = model[iter][C_TYPE]
		jid = model[iter][C_JID].decode('utf-8')
		account = model[iter][C_ACCOUNT].decode('utf-8')
		if row_type == 'contact':
			# it's jid
			#Remove resource indicator (Name (2))
			contacts = gajim.contacts[account][jid]
			name = contacts[0].name
			model[iter][C_NAME] = name

		model[iter][C_EDITABLE] = True # set 'editable' to True
		self.tree.set_cursor(path, self.tree.get_column(0), True)
		
	def on_assign_pgp_key(self, widget, user, account):
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		keys = {}
		keyID = 'None'
		for i in xrange(0, len(attached_keys)/2):
			keys[attached_keys[2*i]] = attached_keys[2*i+1]
			if attached_keys[2*i] == user.jid:
				keyID = attached_keys[2*i+1]
		public_keys = gajim.connections[account].ask_gpg_keys()
		public_keys['None'] = 'None'
		instance = dialogs.ChooseGPGKeyDialog(_('Assign OpenPGP Key'),
			_('Select a key to apply to the contact'), public_keys, keyID)
		keyID = instance.run()
		if keyID is None:
			return
		if keyID[0] == 'None':
			if user.jid in keys:
				del keys[user.jid]
		else:
			keys[user.jid] = keyID[0]
			for u in gajim.contacts[account][user.jid]:
				u.keyID = keyID[0]
			if gajim.interface.windows[account]['chats'].has_key(user.jid):
				gajim.interface.windows[account]['chats'][user.jid].draw_widgets(user)
		keys_str = ''
		for jid in keys:
			keys_str += jid + ' ' + keys[jid] + ' '
		gajim.config.set_per('accounts', account, 'attached_gpg_keys', keys_str)

	def on_edit_groups(self, widget, user, account):
		dlg = dialogs.EditGroupsDialog(user, account)
		dlg.run()
		
	def on_history(self, widget, contact, account):
		'''When history menuitem is activated: call log window'''
		if gajim.interface.windows['logs'].has_key(contact.jid):
			gajim.interface.windows['logs'][contact.jid].window.present()
		else:
			gajim.interface.windows['logs'][contact.jid] = history_window.\
				HistoryWindow(contact.jid, account)

	def on_send_single_message_menuitem_activate(self, wiget, account,
	contact = None):
		if contact is None:
			dialogs.SingleMessageWindow(account, action = 'send')
		else:
			dialogs.SingleMessageWindow(account, contact.jid, 'send')
		
	def on_send_file_menuitem_activate(self, widget, account, contact):
		gajim.interface.windows['file_transfers'].show_file_send_request( 
			account, contact)
		
	def mk_menu_user(self, event, iter):
		'''Make contact's popup menu'''
		model = self.tree.get_model()
		jid = model[iter][C_JID].decode('utf-8')
		path = model.get_path(iter)
		account = model[iter][C_ACCOUNT].decode('utf-8')
		contact = gajim.get_highest_prio_contact_from_contacts(
			gajim.contacts[account][jid])
		
		xml = gtk.glade.XML(GTKGUI_GLADE, 'roster_contact_context_menu',
			APP)
		roster_contact_context_menu = xml.get_widget(
			'roster_contact_context_menu')
		childs = roster_contact_context_menu.get_children()
		
		start_chat_menuitem = childs[0]
		send_single_message_menuitem = childs[1]
		rename_menuitem = childs[2]
		edit_groups_menuitem = childs[3]
		# separator4 goes with assign_openpgp_key_menuitem
		assign_openpgp_separator = childs[4]
		send_file_menuitem = childs[5]
		assign_openpgp_key_menuitem = childs[6]
		
		#skip a seperator
		subscription_to_menuitem, subscription_from_menuitem =\
			childs[8].get_submenu().get_children()
		add_to_roster_menuitem = childs[9]
		remove_from_roster_menuitem = childs[10]
		#skip a seperator
		information_menuitem = childs[12]
		history_menuitem = childs[13]
		
		
		if contact.resource:
			send_file_menuitem.connect('activate',
				self.on_send_file_menuitem_activate, account, contact)
		else: # if we do not have resource we cannot send file
			send_file_menuitem.hide()
			send_file_menuitem.set_no_show_all(True)
			
		start_chat_menuitem.connect('activate',
			self.on_roster_treeview_row_activated, path)
		send_single_message_menuitem.connect('activate',
			self.on_send_single_message_menuitem_activate, account, contact)
		rename_menuitem.connect('activate', self.on_rename, iter, path)
		remove_from_roster_menuitem.connect('activate', self.on_req_usub,
			contact, account)
		information_menuitem.connect('activate', self.on_info, contact,
			account)
		history_menuitem.connect('activate', self.on_history, contact,
			account)

		if _('not in the roster') not in contact.groups:
			#contact is in normal group
			edit_groups_menuitem.set_no_show_all(False)
			assign_openpgp_key_menuitem.set_no_show_all(False)
			add_to_roster_menuitem.hide()
			add_to_roster_menuitem.set_no_show_all(True)
			edit_groups_menuitem.connect('activate', self.on_edit_groups, contact,
				account)

			if gajim.config.get('usegpg'):
				assign_openpgp_key_menuitem.connect('activate',
					self.on_assign_pgp_key, contact, account)

			subscription_to_menuitem.connect('activate', self.authorize, jid,
				account)
			subscription_from_menuitem.connect('activate', self.req_sub,
				jid, _('I would like to add you to my roster'), account)
			
		else: # contact is in group 'not in the roster'
			add_to_roster_menuitem.set_no_show_all(False)
			edit_groups_menuitem.hide()
			edit_groups_menuitem.set_no_show_all(True)
			# hide first of the two consecutive separators
			assign_openpgp_separator.hide()
			assign_openpgp_separator.set_no_show_all(True)
			assign_openpgp_key_menuitem.hide()
			assign_openpgp_key_menuitem.set_no_show_all(True)
			
			add_to_roster_menuitem.connect('activate',
				self.on_add_to_roster, contact, account)

		event_button = self.get_possible_button_event(event)

		roster_contact_context_menu.popup(None, None, None, event_button,
			event.time)
		roster_contact_context_menu.show_all()

	def mk_menu_g(self, event, iter):
		'''Make group's popup menu'''
		model = self.tree.get_model()
		path = model.get_path(iter)
		
		menu = gtk.Menu()

		rename_item = gtk.ImageMenuItem(_('Rename'))
		rename_icon = gtk.image_new_from_stock(gtk.STOCK_REFRESH,
			gtk.ICON_SIZE_MENU)
		rename_item.set_image(rename_icon)
		menu.append(rename_item)
		rename_item.connect('activate', self.on_rename, iter, path)

		event_button = self.get_possible_button_event(event)
			
		menu.popup(None, None, None, event_button, event.time)
		menu.show_all()
	
	def mk_menu_agent(self, event, iter):
		'''Make agent's popup menu'''
		model = self.tree.get_model()
		jid = model[iter][C_JID].decode('utf-8')
		path = model.get_path(iter)
		account = model[iter][C_ACCOUNT].decode('utf-8')
		user = gajim.contacts[account][jid][0]
		menu = gtk.Menu()
		
		item = gtk.ImageMenuItem(_('_Log on'))
		icon = gtk.image_new_from_stock(gtk.STOCK_YES, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		show = gajim.contacts[account][jid][0].show
		if show != 'offline' and show != 'error':
			item.set_sensitive(False)
		item.connect('activate', self.on_agent_logging, jid, None, account)

		item = gtk.ImageMenuItem(_('Log _off'))
		icon = gtk.image_new_from_stock(gtk.STOCK_NO, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		if show in ('offline', 'error'):
			item.set_sensitive(False)
		item.connect('activate', self.on_agent_logging, jid, 'unavailable',
							account)

		item = gtk.SeparatorMenuItem() # seperator
		menu.append(item)

		item = gtk.ImageMenuItem(_('Edit'))
		icon = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		item.connect('activate', self.on_edit_agent, user, account)

		item = gtk.ImageMenuItem(_('_Remove from Roster'))
		icon = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		item.connect('activate', self.on_remove_agent, user, account)

		event_button = self.get_possible_button_event(event)

		menu.popup(None, None, None, event_button, event.time)
		menu.show_all()

	def on_edit_account(self, widget, account):
		if gajim.interface.windows[account].has_key('account_modification'):
			gajim.interface.windows[account]['account_modification'].window.present()
		else:
			gajim.interface.windows[account]['account_modification'] = \
				config.AccountModificationWindow(account)
	
	def get_possible_button_event(self, event):
		'''mouse or keyboard caused the event?'''
		if event.type == gtk.gdk.KEY_PRESS:
			event_button = 0 # no event.button so pass 0
		else: # BUTTON_PRESS event, so pass event.button
			event_button = event.button
		
		return event_button

	def on_change_status_message_activate(self, widget, account):
		show = gajim.SHOW_LIST[gajim.connections[account].connected]
		dlg = dialogs.ChangeStatusMessageDialog(show)
		message = dlg.run()
		if message is not None: # None is if user pressed Cancel
			self.send_status(account, show, message)

	def mk_menu_account(self, event, iter):
		'''Make account's popup menu'''
		model = self.tree.get_model()
		account = model[iter][C_ACCOUNT].decode('utf-8')
		
		#FIXME: make most menuitems of this menu insensitive if account is offline

		# we have to create our own set of icons for the menu
		# using self.jabber_status_images is poopoo
		iconset = gajim.config.get('iconset')
		if not iconset:
			iconset = 'sun'
		path = os.path.join(gajim.DATA_DIR, 'iconsets/' + iconset + '/16x16/')
		state_images = self.load_iconset(path)

		xml = gtk.glade.XML(GTKGUI_GLADE, 'account_context_menu', APP)
		account_context_menu = xml.get_widget('account_context_menu')
		childs = account_context_menu.get_children()
		
		status_menuitem = childs[0]
		# we skip the seperator
		advanced_actions_menuitem = childs[2]
		xml_console_menuitem = xml.get_widget('xml_console_menuitem')
		set_motd_menuitem = xml.get_widget('set_motd_menuitem')
		update_motd_menuitem = xml.get_widget('update_motd_menuitem')
		delete_motd_menuitem = xml.get_widget('delete_motd_menuitem')
		edit_account_menuitem = childs[3]
		service_discovery_menuitem = childs[4]
		add_contact_menuitem = childs[5]
		join_group_chat_menuitem = childs[6]
		new_message_menuitem = childs[7]
		
		sub_menu = gtk.Menu()
		status_menuitem.set_submenu(sub_menu)

		for show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible'):
			uf_show = helpers.get_uf_show(show, use_mnemonic = True)
			item = gtk.ImageMenuItem(uf_show)
			icon = state_images[show]
			item.set_image(icon)
			sub_menu.append(item)
			item.connect('activate', self.change_status, account, show)

		item = gtk.SeparatorMenuItem()
		sub_menu.append(item)

		item = gtk.ImageMenuItem(_('_Change Status Message'))
		path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'rename.png')
		img = gtk.Image()
		img.set_from_file(path)
		item.set_image(img)
		sub_menu.append(item)
		item.connect('activate', self.on_change_status_message_activate, account)
		if gajim.connections[account].connected < 2:
			item.set_sensitive(False)

		item = gtk.SeparatorMenuItem()
		sub_menu.append(item)

		uf_show = helpers.get_uf_show('offline', use_mnemonic = True)
		item = gtk.ImageMenuItem(uf_show)
		icon = state_images['offline']
		item.set_image(icon)
		sub_menu.append(item)
		item.connect('activate', self.change_status, account, 'offline')

		xml_console_menuitem.connect('activate', self.on_xml_console_menuitem_activate,
			account)
		set_motd_menuitem.connect('activate', self.on_set_motd_menuitem_activate, account)
		update_motd_menuitem.connect('activate', self.on_update_motd_menuitem_activate, account)
		delete_motd_menuitem.connect('activate', self.on_delete_motd_menuitem_activate, account)
		edit_account_menuitem.connect('activate', self.on_edit_account, account)
		service_discovery_menuitem.connect('activate',
			self.on_service_disco_menuitem_activate, account)
		add_contact_menuitem.connect('activate', self.on_add_new_contact, account)
		join_group_chat_menuitem.connect('activate',
			self.on_join_gc_activate, account)
		new_message_menuitem.connect('activate',
			self.on_new_message_menuitem_activate, account)
		
		event_button = self.get_possible_button_event(event)
		
		account_context_menu.popup(None, self.tree, None, event_button,
			event.time)
		account_context_menu.show_all()

	def on_add_to_roster(self, widget, user, account):
		dialogs.AddNewContactWindow(account, user.jid)
	
	def authorize(self, widget, jid, account):
		'''Authorize a user (by re-sending auth menuitem)'''
		gajim.connections[account].send_authorization(jid)
		dialogs.InformationDialog(_('Authorization has been sent'),
			_('Now "%s" will know your status.') %jid)

	def req_sub(self, widget, jid, txt, account, group=None, pseudo=None):
		'''Request subscription to a user'''
		if not pseudo:
			pseudo = jid
		gajim.connections[account].request_subscription(jid, txt)
		if not group:
			group = _('General')
		if not gajim.contacts[account].has_key(jid):
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			user1 = Contact(jid = jid, name = pseudo, groups = [group],
				show = 'requested', status = '', ask = 'none',
				sub = 'subscribe', keyID = keyID)
			gajim.contacts[account][jid] = [user1]
		else:
			user1 = gajim.contacts[account][jid][0]
			if not _('not in the roster') in user1.groups:
				dialogs.InformationDialog(_('Subscription request has been sent'),
_('If "%s" accepts this request you will know his status.') %jid)
				return
			user1.groups = [group]
			user1.name = pseudo
			self.remove_contact(user1, account)
		self.add_contact_to_roster(jid, account)

	def on_roster_treeview_scroll_event(self, widget, event):
		self.tooltip.hide_tooltip()

	def on_roster_treeview_key_press_event(self, widget, event):
		'''when a key is pressed in the treeviews'''
		self.tooltip.hide_tooltip()
		if event.keyval == gtk.keysyms.Menu:
			self.show_treeview_menu(event)
			return True
		if event.keyval == gtk.keysyms.Escape:
			self.tree.get_selection().unselect_all()
		if event.keyval == gtk.keysyms.F2:
			treeselection = self.tree.get_selection()
			model, iter = treeselection.get_selected()
			if not iter:
				return
			type = model[iter][C_TYPE]
			if type in ('contact', 'group'):
				path = model.get_path(iter)
				self.on_rename(widget, iter, path)

		if event.keyval == gtk.keysyms.Delete:
			treeselection = self.tree.get_selection()
			model, iter = treeselection.get_selected()
			if not iter:
				return
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			type = model[iter][C_TYPE]
			if type in ('account', 'group'):
				return
			user = gajim.contacts[account][jid][0]
			if type == 'contact':
				self.on_req_usub(widget, user, account)
			elif type == 'agent':
				self.on_remove_agent(widget, user, account)

	def show_appropriate_context_menu(self, event, iter):
		model = self.tree.get_model()
		type = model[iter][C_TYPE]
		if type == 'group':
			self.mk_menu_g(event, iter)
		elif type == 'agent':
			self.mk_menu_agent(event, iter)
		elif type == 'contact':
			self.mk_menu_user(event, iter)
		elif type == 'account':
			self.mk_menu_account(event, iter)

	def show_treeview_menu(self, event):
		try:
			store, iter = self.tree.get_selection().get_selected()
		except TypeError:
			self.tree.get_selection().unselect_all()
			return
		model = self.tree.get_model()
		path = model.get_path(iter)
		self.tree.get_selection().select_path(path)

		self.show_appropriate_context_menu(event, iter)
		
		return True

	def on_roster_treeview_button_press_event(self, widget, event):
		# hide tooltip, no matter the button is pressed
		self.tooltip.hide_tooltip()
		if event.button == 3: # Right click
			try:
				path, column, x, y = self.tree.get_path_at_pos(int(event.x), 
					int(event.y))
			except TypeError:
				self.tree.get_selection().unselect_all()
				return
			self.tree.get_selection().select_path(path)
			model = self.tree.get_model()
			iter = model.get_iter(path)
			self.show_appropriate_context_menu(event, iter)
			return True
		
		if event.button == 2: # Middle click
			try:
				path, column, x, y = self.tree.get_path_at_pos(int(event.x), 
					int(event.y))
			except TypeError:
				self.tree.get_selection().unselect_all()
				return
			self.tree.get_selection().select_path(path)
			model = self.tree.get_model()
			iter = model.get_iter(path)
			type = model[iter][C_TYPE]
			if type in ('agent', 'contact'):
				account = model[iter][C_ACCOUNT].decode('utf-8')
				jid = model[iter][C_JID].decode('utf-8')
				if gajim.interface.windows[account]['chats'].has_key(jid):
					gajim.interface.windows[account]['chats'][jid].set_active_tab(jid)
				elif gajim.contacts[account].has_key(jid):
					c = gajim.get_contact_instance_with_highest_priority(account, jid)
					self.new_chat(c, account)
					gajim.interface.windows[account]['chats'][jid].set_active_tab(jid)
				gajim.interface.windows[account]['chats'][jid].window.present()
			elif type == 'account':
				account = model[iter][C_ACCOUNT]
				show = gajim.connections[account].connected
				if show > 1: # We are connected
					self.on_change_status_message_activate(widget, account)
			return True
		
		if event.button == 1: # Left click
			try:
				path, column, x, y = self.tree.get_path_at_pos(int(event.x), 
					int(event.y))
			except TypeError:
				self.tree.get_selection().unselect_all()
				return False
			model = self.tree.get_model()
			iter = model.get_iter(path)
			type = model[iter][C_TYPE]
			if type == 'group':
				if x < 20: # first cell in 1st column (the arrow SINGLE clicked)
					if (self.tree.row_expanded(path)):
						self.tree.collapse_row(path)
					else:
						self.tree.expand_row(path, False)

	def on_req_usub(self, widget, user, account):
		'''Remove a contact'''
		window = dialogs.ConfirmationDialogCheck(
			_('Contact "%s" will be removed from your roster') % (user.name),
			_('By removing this contact you also by default remove authorization resulting in him/her always seeing you as offline.'),
			_('I want this contact to know my status after removal'))
		# FIXME:
		# maybe use 2 optionboxes from which the user can select? (better)
		if window.get_response() == gtk.RESPONSE_OK:
			remove_auth = True
			if window.is_checked():
				remove_auth = False
			gajim.connections[account].unsubscribe(user.jid, remove_auth)
			for u in gajim.contacts[account][user.jid]:
				self.remove_contact(u, account)
			del gajim.contacts[account][u.jid]
			if user.jid in gajim.interface.windows[account]['chats']:
				user1 = Contact(jid = user.jid, name = user.name,
					groups = [_('not in the roster')], show = 'not in the roster',
					status = '', ask = 'none', keyID = user.keyID)
				gajim.contacts[account][user.jid] = [user1] 
				self.add_contact_to_roster(user.jid, account)	
			
	def forget_gpg_passphrase(self, keyid):
		if self.gpg_passphrase.has_key(keyid):
			del self.gpg_passphrase[keyid]
		return False

	def set_connecting_state(self, account):
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if accountIter:
			model[accountIter][0] =	self.jabber_state_images['connecting']
		if gajim.interface.systray_enabled:
			gajim.interface.systray.change_status('connecting')

	def send_status(self, account, status, txt, sync = False, auto = False):
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if status != 'offline':
			if gajim.connections[account].connected < 2:
				self.set_connecting_state(account)

			save_pass = gajim.config.get_per('accounts', account, 'savepass')
			if not save_pass and gajim.connections[account].connected < 2:
				passphrase = ''
				w = dialogs.PassphraseDialog(
					_('Password Required'),
					_('Enter your password for account %s') % account, 
					_('Save password'))
				passphrase, save = w.run()
				if passphrase == -1:
					if accountIter:
						model[accountIter][0] =	self.jabber_state_images['offline']
					if gajim.interface.systray_enabled:
						gajim.interface.systray.change_status('offline')
					self.update_status_comboxbox()
					return
				gajim.connections[account].password = passphrase
				if save:
					gajim.config.set_per('accounts', account, 'savepass', True)
					gajim.config.set_per('accounts', account, 'password', passphrase)

			keyid = None
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			# we don't need to bother with the passphrase if we use the agent
			if use_gpg_agent:
				save_gpg_pass = False
			else:
			        save_gpg_pass = gajim.config.get_per('accounts', account, 
				        'savegpgpass')
			keyid = gajim.config.get_per('accounts', account, 'keyid')
			if keyid and gajim.connections[account].connected < 2 and \
				gajim.config.get('usegpg'):
				
				if use_gpg_agent:
					self.gpg_passphrase[keyid] = None
				else:
					if save_gpg_pass:
						passphrase = gajim.config.get_per('accounts', account, 'gpgpassword')
					else:
						if self.gpg_passphrase.has_key(keyid):
							passphrase = self.gpg_passphrase[keyid]
							save = False
						else:
							w = dialogs.PassphraseDialog(
								_('Passphrase Required'),
								_('Enter GPG key passphrase for account %s') % account, 
								_('Save passphrase'))
							passphrase, save = w.run()
						if passphrase == -1:
							passphrase = None
						else:
							self.gpg_passphrase[keyid] = passphrase
							gobject.timeout_add(30000, self.forget_gpg_passphrase, keyid)
						if save:
							gajim.config.set_per('accounts', account, 'savegpgpass', True)
							gajim.config.set_per('accounts', account, 'gpgpassword', 
														passphrase)
					gajim.connections[account].gpg_passphrase(passphrase)
					
		gajim.connections[account].change_status(status, txt, sync, auto)
		for room_jid in gajim.interface.windows[account]['gc']:
			if room_jid != 'tabbed':
				nick = gajim.interface.windows[account]['gc'][room_jid].nicks[room_jid]
				gajim.connections[account].send_gc_status(nick, room_jid, status, 
					txt)
		if status == 'online' and gajim.interface.sleeper.getState() != \
			common.sleepy.STATE_UNKNOWN:
			gajim.sleeper_state[account] = 'online'
		else:
			gajim.sleeper_state[account] = 'off'

	def get_status_message(self, show):
		if (show == 'online' and not gajim.config.get('ask_online_status')) or \
			(show == 'offline' and not gajim.config.get('ask_offline_status')):
			return ''
		dlg = dialogs.ChangeStatusMessageDialog(show)
		message = dlg.run()
		return message

	def connected_rooms(self, account):
		accounts = gajim.connections.keys()
		if True in gajim.gc_connected[account].values():
			return True
		return False

	def change_status(self, widget, account, status):
		if status == 'invisible':
			if self.connected_rooms(account):
				dialog = dialogs.ConfirmationDialog(
		_('You are participating in one or more group chats'),
		_('Changing your status to invisible will result in disconnection from those group chats. Are you sure you want to go invisible?'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return
		message = self.get_status_message(status)
		if message is None: # user pressed Cancel to change status message dialog
			return
		self.send_status(account, status, message)

	def on_status_combobox_changed(self, widget):
		'''When we change our status via the combobox'''
		model = self.status_combobox.get_model()
		active = self.status_combobox.get_active()
		if active == -1: # no active item
			return
		accounts = gajim.connections.keys()
		if len(accounts) == 0:
			dialogs.ErrorDialog(_('No account available'),
		_('You must create an account before you can chat with other contacts.')
		).get_response()
			self.update_status_comboxbox()
			return
		status = model[active][2].decode('utf-8')
		one_connected = helpers.one_account_connected()
		if active == 7: # We choose change status message (7 is that)
			# do not change show, just show change status dialog
			dlg = dialogs.ChangeStatusMessageDialog()
			message = dlg.run()
			if message is not None: # None if user pressed Cancel
				for acct in accounts:
					if not gajim.config.get_per('accounts', acct,
						'sync_with_global_status'):
						continue
					current_show = gajim.SHOW_LIST[gajim.connections[acct].connected]
					self.send_status(acct, current_show, message)
			self.status_combobox.handler_block(self.id_signal_cb)
			self.status_combobox.set_active(self.previous_status_combobox_active)
			self.status_combobox.handler_unblock(self.id_signal_cb)
			return
		# we are about to change show, so save this new show so in case
		# after user chooses "Change status message" menuitem
		# we can return to this show
		self.previous_status_combobox_active = active
		if status == 'invisible':
			bug_user = False
			for acct in accounts:
				if not one_connected or gajim.connections[acct].connected > 1:
					if not gajim.config.get_per('accounts', acct, 
							'sync_with_global_status'):
						continue
					# We're going to change our status to invisible
					if self.connected_rooms(acct):
						bug_user = True
						break
			if bug_user:
				dialog = dialogs.ConfirmationDialog(
		_('You are participating in one or more group chats'),
		_('Changing your status to invisible will result in disconnection from those group chats. Are you sure you want to go invisible?'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return
		message = self.get_status_message(status)
		if message is None: # user pressed Cancel to change status message dialog
			self.update_status_comboxbox()
			return
		for acct in accounts:
			if not gajim.config.get_per('accounts', acct, 'sync_with_global_status'):
				continue
			# we are connected (so we wanna change show and status)
			# or no account is connected and we want to connect with new show and status
			if not one_connected or gajim.connections[acct].connected > 1:
				self.send_status(acct, status, message)
	
	def update_status_comboxbox(self):
		# table to change index in connection.connected to index in combobox
		table = {0:9, 1:9, 2:0, 3:1, 4:2, 5:3, 6:4, 7:5}
		maxi = 0
		for account in gajim.connections:
			if gajim.connections[account].connected > maxi:
				maxi = gajim.connections[account].connected
		# temporarily block signal in order not to send status that we show
		# in the combobox
		self.status_combobox.handler_block(self.id_signal_cb)
		self.status_combobox.set_active(table[maxi])
		self.status_combobox.handler_unblock(self.id_signal_cb)
		statuss = ['offline', 'connecting', 'online', 'chat', 'away', 
						'xa', 'dnd', 'invisible']
		if gajim.interface.systray_enabled:
			gajim.interface.systray.change_status(statuss[maxi])

	def on_status_changed(self, account, status):
		'''the core tells us that our status has changed'''
		if not gajim.contacts.has_key(account):
			return
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if accountIter:
			model[accountIter][0] = self.jabber_state_images[status]
		if status == 'offline':
			if accountIter:
				model[accountIter][6] = None
			for jid in gajim.contacts[account]:
				luser = gajim.contacts[account][jid]
				luser_copy = []
				for user in luser:
					luser_copy.append(user)
				for user in luser_copy:
					self.chg_contact_status(user, 'offline', 'Disconnected', account)
		self.update_status_comboxbox()
		self.make_menu()
	
	def new_chat(self, contact, account):
		chats = gajim.interface.windows[account]['chats']
		if gajim.config.get('usetabbedchat'):
			if not chats.has_key('tabbed'):
				chats['tabbed'] = tabbed_chat_window.TabbedChatWindow(contact,
					account)
			else:
				chats['tabbed'].new_tab(contact)

			chats[contact.jid] = chats['tabbed']
		else:
			chats[contact.jid] = tabbed_chat_window.TabbedChatWindow(contact,
				account)

	def new_chat_from_jid(self, account, jid):
		if gajim.contacts[account].has_key(jid):
			contact = gajim.get_contact_instance_with_highest_priority(account, jid)
		else:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			contact = Contact(jid = jid, name = jid.split('@')[0],
				groups = [_('not in the roster')], show = 'not in the roster',
				status = '', sub = 'none', keyID = keyID)
			gajim.contacts[account][jid] = [contact]
			self.add_contact_to_roster(contact.jid, account)			

		if not gajim.interface.windows[account]['chats'].has_key(jid):
			self.new_chat(contact, account)
		gajim.interface.windows[account]['chats'][jid].set_active_tab(jid)
		gajim.interface.windows[account]['chats'][jid].window.present()

	def new_room(self, jid, nick, account):
		if gajim.config.get('usetabbedchat'):
			if not gajim.interface.windows[account]['gc'].has_key('tabbed'):
				gajim.interface.windows[account]['gc']['tabbed'] = \
					groupchat_window.GroupchatWindow(jid, nick, account)
			else:
				gajim.interface.windows[account]['gc']['tabbed'].new_room(jid, nick)
			gajim.interface.windows[account]['gc'][jid] = \
				gajim.interface.windows[account]['gc']['tabbed']
		else:
			gajim.interface.windows[account]['gc'][jid] = \
				groupchat_window.GroupchatWindow(jid, nick, account)

	def on_message(self, jid, msg, tim, account, encrypted = False,
		msg_type = '', subject = None, resource = ''):
		'''when we receive a message'''
		if not gajim.contacts[account].has_key(jid):
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			user1 = Contact(jid = jid, name = jid.split('@')[0],
				groups = [_('not in the roster')], show = 'not in the roster',
				status = '', ask = 'none', keyID = keyID, resource = resource)
			gajim.contacts[account][jid] = [user1] 
			self.add_contact_to_roster(jid, account)

		iters = self.get_contact_iter(jid, account)
		if iters:
			path = self.tree.get_model().get_path(iters[0])
		else:
			path = None
		autopopup = gajim.config.get('autopopup')
		autopopupaway = gajim.config.get('autopopupaway')
		save_in_queue = False

		# Do we have a queue?
		qs = gajim.awaiting_events[account]
		no_queue = True
		if qs.has_key(jid):
			no_queue = False
		popup = False
		if autopopup and (autopopupaway or gajim.connections[account].connected \
			> 3):
			popup = True

		if msg_type == 'normal': # it's single message
			if popup:
				contact = gajim.contacts[account][jid][0]
				dialogs.SingleMessageWindow(account, contact.jid,
					action = 'receive', from_whom = jid, subject = subject,
					message = msg)
				return
		
		# We print if window is opened and it's not a single message
		if gajim.interface.windows[account]['chats'].has_key(jid) and \
			msg_type != 'normal':
			typ = ''
			if msg_type == 'error':
				typ = 'status'
			gajim.interface.windows[account]['chats'][jid].print_conversation(msg, 
				jid, typ, tim = tim, encrypted = encrypted, subject = subject)
			return

		# We save it in a queue
		if no_queue:
			qs[jid] = []
		kind = 'chat'
		if msg_type == 'normal':
			kind = 'normal'
		qs[jid].append((kind, (msg, subject, msg_type, tim, encrypted)))
		self.nb_unread += 1
		if popup:
			if not gajim.interface.windows[account]['chats'].has_key(jid):
				c = gajim.get_contact_instance_with_highest_priority(account, jid)
				self.new_chat(c, account)
				if path:
					self.tree.expand_row(path[0:1], False)
					self.tree.expand_row(path[0:2], False)
					self.tree.scroll_to_cell(path)
					self.tree.set_cursor(path)
		else:
			if no_queue: # We didn't have a queue: we change icons
				self.draw_contact(jid, account)
			if gajim.interface.systray_enabled:
				gajim.interface.systray.add_jid(jid, account, kind)
			self.show_title() # we show the * or [n]
			if not path:
				self.add_contact_to_roster(jid, account)
				iters = self.get_contact_iter(jid, account)
				path = self.tree.get_model().get_path(iters[0])
			self.tree.expand_row(path[0:1], False)
			self.tree.expand_row(path[0:2], False)
			self.tree.scroll_to_cell(path)
			self.tree.set_cursor(path)

	def on_preferences_menuitem_activate(self, widget):
		if gajim.interface.windows['preferences'].window.get_property('visible'):
			gajim.interface.windows['preferences'].window.present()
		else:
			gajim.interface.windows['preferences'].window.show_all()

	def on_add_new_contact(self, widget, account):
		dialogs.AddNewContactWindow(account)

	def on_join_gc_activate(self, widget, account):
		invisible_show = gajim.SHOW_LIST.index('invisible')
		if gajim.connections[account].connected == invisible_show:
			dialogs.ErrorDialog(_('You cannot join a room while you are invisible')
				).get_response()
			return
		if gajim.interface.windows[account].has_key('join_gc'):
			gajim.interface.windows[account]['join_gc'].window.present()
		else:
			# c http://nkour.blogspot.com/2005/05/pythons-init-return-none-doesnt-return.html
			try:
				gajim.interface.windows[account]['join_gc'] = \
					dialogs.JoinGroupchatWindow(account)
			except RuntimeError:
				pass

	def on_new_message_menuitem_activate(self, widget, account):
		dialogs.NewMessageDialog(account)
			
	def on_contents_menuitem_activate(self, widget):
		helpers.launch_browser_mailer('url', 'http://trac.gajim.org/wiki')
		
	def on_faq_menuitem_activate(self, widget):
		helpers.launch_browser_mailer('url', 'http://trac.gajim.org/wiki/GajimFaq')

	def on_about_menuitem_activate(self, widget):
		dialogs.AboutDialog()

	def on_accounts_menuitem_activate(self, widget):
		if gajim.interface.windows.has_key('accounts'):
			gajim.interface.windows['accounts'].window.present()
		else:
			gajim.interface.windows['accounts'] = config.AccountsWindow() 

	def on_file_transfers_menuitem_activate(self, widget):
		if gajim.interface.windows['file_transfers'].window.get_property('visible'):
			gajim.interface.windows['file_transfers'].window.present()
		else:
			gajim.interface.windows['file_transfers'].window.show_all()

	def on_manage_bookmarks_menuitem_activate(self, widget):
		config.ManageBookmarksWindow()

	def close_all(self, dic):
		'''close all the windows in the given dictionary'''
		for w in dic.values():
			if type(w) == type({}):
				self.close_all(w)
			else:
				w.window.destroy()
	
	def on_roster_window_delete_event(self, widget, event):
		'''When we want to close the window'''
		if gajim.interface.systray_enabled and not gajim.config.get('quit_on_roster_x_button'):
			self.tooltip.hide_tooltip()
			self.window.hide()
		else:
			accounts = gajim.connections.keys()
			get_msg = False
			for acct in accounts:
				if gajim.connections[acct].connected:
					get_msg = True
					break
			if get_msg:
				message = self.get_status_message('offline')
				if message is None: # user pressed Cancel to change status message dialog
					message = ''
				for acct in accounts:
					if gajim.connections[acct].connected:
						self.send_status(acct, 'offline', message, True)
			self.quit_gtkgui_interface()
		return True # do NOT destory the window

	def on_roster_window_focus_in_event(self, widget, event):
		'''roster received focus, so if we had urgency REMOVE IT
		NOTE: we do not have to read the message to remove urgency
		so this functions does that'''
		if gtk.gtk_version >= (2, 8, 0) and gtk.pygtk_version >= (2, 8, 0):
			if widget.props.urgency_hint:
				widget.props.urgency_hint = False

	def on_roster_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			treeselection = self.tree.get_selection()
			model, iter = treeselection.get_selected()
			if not iter and gajim.interface.systray_enabled and not gajim.config.get('quit_on_roster_x_button'):
				self.tooltip.hide_tooltip()
				self.window.hide()

	def quit_gtkgui_interface(self):
		'''When we quit the gtk interface :
		tell that to the core and exit gtk'''
		if gajim.config.get('saveposition'):
			# in case show_roster_on_start is False and roster is never shown
			# window.window is None
			if self.window.window is not None:
				x, y = self.window.window.get_root_origin()
				gajim.config.set('roster_x-position', x)
				gajim.config.set('roster_y-position', y)
				width, height = self.window.get_size()
				gajim.config.set('roster_width', width)
				gajim.config.set('roster_height', height)

		gajim.config.set('collapsed_rows', '\t'.join(self.collapsed_rows))
		gajim.interface.save_config()
		for account in gajim.connections:
			gajim.connections[account].quit(True)
		self.close_all(gajim.interface.windows)
		if gajim.interface.systray_enabled:
			gajim.interface.hide_systray()
		gtk.main_quit()

	def on_quit_menuitem_activate(self, widget):
		accounts = gajim.connections.keys()
		get_msg = False
		for acct in accounts:
			if gajim.connections[acct].connected:
				get_msg = True
				break
		if get_msg:
			message = self.get_status_message('offline')
			if message is None: # user pressed Cancel to change status message dialog
				return
			# check if we have unread or recent mesages
			unread = False
			recent = False
			if self.nb_unread > 0:
				unread = True
			for account in accounts:
				if gajim.interface.windows[account]['chats'].has_key('tabbed'):
					wins = [gajim.interface.windows[account]['chats']['tabbed']]
				else:
					wins = gajim.interface.windows[account]['chats'].values()
				for win in wins:
					unrd = 0
					for jid in win.nb_unread:
						unrd += win.nb_unread[jid]
					if unrd:
						unread = True
						break
					for jid in win.contacts:
						if time.time() - gajim.last_message_time[account][jid] < 2:
							recent = True
							break
			if unread:
				dialog = dialogs.ConfirmationDialog(_('You have unread messages'),
					_('Messages will only be available for reading them later if you have history enabled.'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return

			if recent:
				dialog = dialogs.ConfirmationDialog(_('You have unread messages'), 
					_('Messages will only be available for reading them later if you have history enabled.'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return
			for acct in accounts:
				if gajim.connections[acct].connected:
					# send status asynchronously
					self.send_status(acct, 'offline', message, True)
		self.quit_gtkgui_interface()

	def open_event(self, account, jid, event):
		'''If an event was handled, return True, else return False'''
		typ = event[0]
		data = event[1]
		ft = gajim.interface.windows['file_transfers']
		if typ == 'normal':
			dialogs.SingleMessageWindow(account, jid,
				action = 'receive', from_whom = jid, subject = data[1],
				message = data[0])
			gajim.interface.remove_first_event(account, jid, typ)
			return True
		elif typ == 'file-request':
			contact = gajim.get_contact_instance_with_highest_priority(account, jid)
			ft.show_file_request(account, contact, data)
			gajim.interface.remove_first_event(account, jid, typ)
			return True
		elif typ in ('file-request-error', 'file-send-error'):
			ft.show_send_error(data)
			gajim.interface.remove_first_event(account, jid, typ)
			return True
		elif typ in ('file-error', 'file-stopped'):
			ft.show_stopped(jid, data)
			gajim.interface.remove_first_event(account, jid, typ)
			return True
		elif typ == 'file-completed':
			ft.show_completed(jid, data)
			gajim.interface.remove_first_event(account, jid, typ)
			return True
		return False

	def on_roster_treeview_row_activated(self, widget, path, col = 0):
		'''When an iter is double clicked: open the first event window'''
		model = self.tree.get_model()
		iter = model.get_iter(path)
		account = model[iter][C_ACCOUNT].decode('utf-8')
		type = model[iter][C_TYPE]
		jid = model[iter][C_JID].decode('utf-8')
		if type in ('group', 'account'):
			if self.tree.row_expanded(path):
				self.tree.collapse_row(path)
			else:
				self.tree.expand_row(path, False)
		else:
			first_ev = gajim.get_first_event(account, jid)
			if first_ev:
				if self.open_event(account, jid, first_ev):
					return
			chats = gajim.interface.windows[account]['chats']
			if chats.has_key(jid):
				chats[jid].set_active_tab(jid)
			elif gajim.contacts[account].has_key(jid):
				c = gajim.get_contact_instance_with_highest_priority(account, jid)
				self.new_chat(c, account)
				chats[jid].set_active_tab(jid)
			chats[jid].window.present()

	def on_roster_treeview_row_expanded(self, widget, iter, path):
		'''When a row is expanded change the icon of the arrow'''
		model = self.tree.get_model()
		if gajim.config.get('mergeaccounts'):
			accounts = gajim.connections.keys()
		else:
			accounts = [model[iter][C_ACCOUNT].decode('utf-8')]
		type = model[iter][C_TYPE]
		if type == 'group':
			model.set_value(iter, 0, self.jabber_state_images['opened'])
			jid = model[iter][C_JID].decode('utf-8')
			for account in accounts:
				if gajim.groups[account].has_key(jid): # This account has this group
					gajim.groups[account][jid]['expand'] = True
					if account + jid in self.collapsed_rows:
						self.collapsed_rows.remove(account + jid)
		elif type == 'account':
			account = accounts[0] # There is only one cause we don't use merge
			if account in self.collapsed_rows:
				self.collapsed_rows.remove(account)
			for g in gajim.groups[account]:
				groupIter = self.get_group_iter(g, account)
				if groupIter and gajim.groups[account][g]['expand']:
					pathG = model.get_path(groupIter)
					self.tree.expand_row(pathG, False)

	def on_roster_treeview_row_collapsed(self, widget, iter, path):
		'''When a row is collapsed :
		change the icon of the arrow'''
		model = self.tree.get_model()
		if gajim.config.get('mergeaccounts'):
			accounts = gajim.connections.keys()
		else:
			accounts = [model[iter][C_ACCOUNT].decode('utf-8')]
		type = model[iter][C_TYPE]
		if type == 'group':
			model.set_value(iter, 0, self.jabber_state_images['closed'])
			jid = model[iter][C_JID].decode('utf-8')
			for account in accounts:
				if gajim.groups[account].has_key(jid): # This account has this group
					gajim.groups[account][jid]['expand'] = False
					if not account + jid in self.collapsed_rows:
						self.collapsed_rows.append(account + jid)
		elif type == 'account':
			account = accounts[0] # There is only one cause we don't use merge
			if not account in self.collapsed_rows:
				self.collapsed_rows.append(account)

	def on_editing_started(self, cell, event, row):
		''' start editing a cell in the tree  '''
		path = self.tree.get_cursor()[0]
		self.editing_path = path
		
	def on_editing_canceled(self, cell):
		'''editing has been canceled'''
		path = self.tree.get_cursor()[0]
		# do not set new name if row order has changed
		if path != self.editing_path:
			self.editing_path = None
			return
		self.editing_path = None
		model = self.tree.get_model()
		iter = model.get_iter(path)
		account = model[iter][C_ACCOUNT].decode('utf-8')
		jid = model[iter][C_JID].decode('utf-8')
		type = model[iter][C_TYPE]
		# restore the number of resources string at the end of contact name
		if type == 'contact' and len(gajim.contacts[account][jid]) > 1:
			self.draw_contact(jid, account)
		# reset editable to False
		model[iter][C_EDITABLE] = False

	def on_cell_edited(self, cell, row, new_text):
		'''When an iter is edited:
		if text has changed, rename the contact'''
		model = self.tree.get_model()
		# if this is a last item in the group, row is invalid
		try:
			iter = model.get_iter_from_string(row)
		except:
			self.editing_path = None
			return
		path = model.get_path(iter)
		# do not set new name if row order has changed
		if path != self.editing_path:
			self.editing_path = None
			return
		self.editing_path = None
		new_text = new_text.decode('utf-8')
		account = model[iter][C_ACCOUNT].decode('utf-8')
		jid = model[iter][C_JID].decode('utf-8')
		type = model[iter][C_TYPE]
		if type == 'contact':
			old_text = gajim.contacts[account][jid][0].name
			if old_text != new_text:
				for u in gajim.contacts[account][jid]:
					u.name = new_text
				gajim.connections[account].update_contact(jid, new_text, u.groups)
			self.draw_contact(jid, account)
		elif type == 'group':
			old_name = model[iter][C_NAME].decode('utf-8')
			#  Groups maynot change name from or to 'not in the roster'
			if _('not in the roster') in (new_text, old_name):
				return
			#get all users in that group
			for jid in gajim.contacts[account]:
				user = gajim.contacts[account][jid][0]
				if old_name in user.groups:
					#set them in the new one and remove it from the old
					self.remove_contact(user, account)
					user.groups.remove(old_name)
					user.groups.append(new_text)
					self.add_contact_to_roster(user.jid, account)
					gajim.connections[account].update_contact(user.jid, user.name, 
																		user.groups)
		model.set_value(iter, 5, False)
		
	def on_service_disco_menuitem_activate(self, widget, account):
		server_jid = gajim.config.get_per('accounts', account, 'hostname')
		if gajim.interface.windows[account]['disco'].has_key(server_jid):
			gajim.interface.windows[account]['disco'][server_jid].window.present()
		else:
			try:
				# Object will add itself to the window dict
				disco.ServiceDiscoveryWindow(account, address_entry=True)
			except RuntimeError:
				pass

	def load_iconset(self, path):
		imgs = {}
		for state in ('connecting', 'online', 'chat', 'away', 'xa',
							'dnd', 'invisible', 'offline', 'error', 'requested',
							'message', 'opened', 'closed', 'not in the roster'):
			
			# try to open a pixfile with the correct method
			state_file = state.replace(' ', '_')
			files = []
			files.append(path + state_file + '.gif')
			files.append(path + state_file + '.png')
			image = gtk.Image()
			image.show()
			imgs[state] = image
			for file in files: # loop seeking for either gif or png
				if os.path.exists(file):
					image.set_from_file(file)
					break
		return imgs

	def make_jabber_state_images(self):
		'''initialise jabber_state_images dict'''
		iconset = gajim.config.get('iconset')
		if not iconset:
			iconset = 'sun'
		path = os.path.join(gajim.DATA_DIR, 'iconsets/' + iconset + '/16x16/')
		self.jabber_state_images = self.load_iconset(path)

	def reload_jabber_state_images(self):
		self.make_jabber_state_images()
		# Update the roster
		self.draw_roster()
		# Update the status combobox
		model = self.status_combobox.get_model()
		iter = model.get_iter_root()
		while iter:
			if model[iter][2] != '':
				# If it's not change status message iter
				# eg. if it has show parameter not ''
				model[iter][1] = self.jabber_state_images[model[iter][2]]
			iter = model.iter_next(iter)
		# Update the systray
		if gajim.interface.systray_enabled:
			gajim.interface.systray.set_img()
		for account in gajim.connections:
			# Update opened chat windows
			for jid in gajim.interface.windows[account]['chats']:
				if jid != 'tabbed':
					gajim.interface.windows[account]['chats'][jid].set_state_image(jid)
			# Update opened groupchat windows
			for jid in gajim.interface.windows[account]['gc']:
				if jid != 'tabbed':
					gajim.interface.windows[account]['gc'][jid].update_state_images()
		self.update_status_comboxbox()

	def repaint_themed_widgets(self):
		"""Notify windows that contain themed widgets to repaint them"""
		for account in gajim.connections:
			# Update opened chat windows/tabs
			for jid in gajim.interface.windows[account]['chats']:
				gajim.interface.windows[account]['chats'][jid].repaint_colored_widgets()
			for jid in gajim.interface.windows[account]['gc']:
				gajim.interface.windows[account]['gc'][jid].repaint_colored_widgets()
			for addr in gajim.interface.windows[account]['disco']:
				gajim.interface.windows[account]['disco'][addr].paint_banner()

	def on_show_offline_contacts_menuitem_activate(self, widget):
		'''when show offline option is changed:
		redraw the treeview'''
		gajim.config.set('showoffline', not gajim.config.get('showoffline'))
		self.draw_roster()

	def iconCellDataFunc(self, column, renderer, model, iter, data = None):
		'''When a row is added, set properties for icon renderer'''
		theme = gajim.config.get('roster_theme')
		if model[iter][C_TYPE] == 'account':
			color = gajim.config.get_per('themes', theme, 'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
			renderer.set_property('xalign', 0)
		elif model[iter][C_TYPE] == 'group':
			color = gajim.config.get_per('themes', theme, 'groupbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
			renderer.set_property('xalign', 0.5)
		else:
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background', '#adc3c6')
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background', '#ab6161')
			else:
				color = gajim.config.get_per('themes', theme, 'contactbgcolor')
				if color:
					renderer.set_property('cell-background', color)
				else:
					renderer.set_property('cell-background', None)
			renderer.set_property('xalign', 1)
		renderer.set_property('width', 20)
	
	def nameCellDataFunc(self, column, renderer, model, iter, data = None):
		'''When a row is added, set properties for name renderer'''
		theme = gajim.config.get('roster_theme')
		if model[iter][C_TYPE] == 'account':
			color = gajim.config.get_per('themes', theme, 'accounttextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				renderer.set_property('foreground', None)
			color = gajim.config.get_per('themes', theme, 'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
			renderer.set_property('font', 
				gtkgui_helpers.get_theme_font_for_option(theme, 'accountfont'))
			renderer.set_property('xpad', 0)
			renderer.set_property('width', 3)
		elif model[iter][C_TYPE] == 'group':
			color = gajim.config.get_per('themes', theme, 'grouptextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				renderer.set_property('foreground', None)
			color = gajim.config.get_per('themes', theme, 'groupbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'groupfont'))
			renderer.set_property('xpad', 4)
		else:
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			color = gajim.config.get_per('themes', theme, 'contacttextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				renderer.set_property('foreground', None)
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background', '#adc3c6')
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background', '#ab6161')
			else:
				color = gajim.config.get_per('themes', theme, 'contactbgcolor')
				if color:
					renderer.set_property('cell-background', color)
				else:
					renderer.set_property('cell-background', None)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'contactfont'))
			renderer.set_property('xpad', 8)

	def fill_secondary_pixbuf_rederer(self, column, renderer, model, iter, data=None):
		'''When a row is added, set properties for secondary renderer (avatar or tls)'''
		theme = gajim.config.get('roster_theme')
		if model[iter][C_TYPE] == 'account':
			color = gajim.config.get_per('themes', theme, 'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
		elif model[iter][C_TYPE] == 'group':
			color = gajim.config.get_per('themes', theme, 'groupbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				renderer.set_property('cell-background', None)
		else:
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background', '#adc3c6')
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background', '#ab6161')
			else:
				color = gajim.config.get_per('themes', theme, 'contactbgcolor')
				if color:
					renderer.set_property('cell-background', color)
				else:
					renderer.set_property('cell-background', None)
		#renderer.set_property('width', 20)
		#renderer.set_property('xalign', 0)

	def get_show(self, luser):
		prio = luser[0].priority
		show = luser[0].show
		for u in luser:
			if u.priority > prio:
				prio = u.priority
				show = u.show
		return show

	def compareIters(self, model, iter1, iter2, data = None):
		'''Compare two iters to sort them'''
		name1 = model.get_value(iter1, 1)
		name2 = model.get_value(iter2, 1)
		if not name1 or not name2:
			return 0
		else:
			name1 = name1.decode('utf-8')
			name2 = name2.decode('utf-8')
		type1 = model.get_value(iter1, 2)
		type2 = model.get_value(iter2, 2)
		if type1 == 'group':
			if name1 == _('Transports'):
				return 1
			if name2 == _('Transports'):
				return -1
			if name1 == _('not in the roster'):
				return 1
			if name2 == _('not in the roster'):
				return -1
		if type1 == 'contact' and type2 == 'contact' and \
				gajim.config.get('sort_by_show'):
			account1 = model.get_value(iter1, 4)
			account2 = model.get_value(iter2, 4)
			if account1 and account2:
				account1 = account1.decode('utf-8')
				account2 = account2.decode('utf-8')
				jid1 = model[iter1][C_JID].decode('utf-8')
				jid2 = model[iter2][C_JID].decode('utf-8')
				luser1 = gajim.contacts[account1][jid1]
				luser2 = gajim.contacts[account2][jid2]
				cshow = {'online':0, 'chat': 1, 'away': 2, 'xa': 3, 'dnd': 4,
					'invisible': 5, 'offline': 6, 'not in the roster': 7, 'error': 8}
				s = self.get_show(luser1)
				if s in cshow:
					show1 = cshow[s]
				else:
					show1 = 9
				s = self.get_show(luser2)
				if s in cshow:
					show2 = cshow[s]
				else:
					show2 = 9
				if show1 < show2:
					return -1
				elif show1 > show2:
					return 1
		if name1.lower() < name2.lower():
			return -1
		if name2.lower < name1.lower():
			return 1
		return 0

	def drag_data_get_data(self, treeview, context, selection, target_id, etime):
		treeselection = treeview.get_selection()
		model, iter = treeselection.get_selected()
		path = model.get_path(iter)
		data = ''
		merge = 0
		if gajim.config.get('mergeaccounts'):
			merge = 1
		if len(path) == 3 - merge:
			data = model[iter][C_JID]
		selection.set(selection.target, 8, data)

	def drag_data_received_data(self, treeview, context, x, y, selection, info,
		etime):
		merge = 0
		if gajim.config.get('mergeaccounts'):
			merge = 1
		model = treeview.get_model()
		if not selection.data:
			return
		data = selection.data.decode('utf-8')
		drop_info = treeview.get_dest_row_at_pos(x, y)
		if not drop_info:
			return
		path_dest, position = drop_info
		if position == gtk.TREE_VIEW_DROP_BEFORE and len(path_dest) == 2 - merge\
			and path_dest[1 - merge] == 0: #droped before the first group
			return
		if position == gtk.TREE_VIEW_DROP_BEFORE and len(path_dest) == 2 - merge:
			#droped before a group : we drop it in the previous group
			path_dest = (path_dest[1 - merge], path_dest[1 - merge]-1)
		iter_dest = model.get_iter(path_dest)
		iter_source = treeview.get_selection().get_selected()[1]
		path_source = model.get_path(iter_source)
		if len(path_dest) == 1 and not merge: #droped on an account
			return
		if path_dest[0] != path_source[0] and not merge:
			#droped in another account
			return
		iter_group_source = model.iter_parent(iter_source)
		grp_source = model[iter_group_source][C_JID].decode('utf-8')
		if grp_source == _('Transports') or grp_source == _('not in the roster'):
			return
		account = model[iter_dest][C_ACCOUNT].decode('utf-8')
		type_dest = model.get_value(iter_dest, C_TYPE)
		if type_dest == 'group':
			grp_dest = model[iter_dest][C_JID].decode('utf-8')
		else:
			grp_dest = model[model.iter_parent(iter_dest)][C_JID].decode('utf-8')
		if grp_source == grp_dest:
			return
		# We upgrade only the first user because user2.groups is a pointer to
		# user1.groups
		u = gajim.contacts[account][data][0]
		if context.action != gtk.gdk.ACTION_COPY:
			u.groups.remove(grp_source)
			if model.iter_n_children(iter_group_source) == 1:
				# this was the only child
				model.remove(iter_group_source)
			# delete the group if it is empty (need to look for offline users too)
			for jid in gajim.contacts[account]:
				if grp_source in gajim.contacts[account][jid][0].groups:
					break
			else:
				del gajim.groups[account][grp_source]
		if not grp_dest in u.groups:
			u.groups.append(grp_dest)
			self.add_contact_to_roster(data, account)
		gajim.connections[account].update_contact(u.jid, u.name, u.groups)
		if context.action in (gtk.gdk.ACTION_MOVE, gtk.gdk.ACTION_COPY):
			context.finish(True, True, etime)
		return

	def show_title(self):
		change_title_allowed = gajim.config.get('change_roster_title')
		if change_title_allowed:
			start = ''
			if self.nb_unread > 1:
				start = '[' + str(self.nb_unread) + ']  '
			elif self.nb_unread == 1:
				start = '*  '
			self.window.set_title(start + 'Gajim')
		
		gtkgui_helpers.set_unset_urgency_hint(self.window, self.nb_unread)

	def iter_is_separator(self, model, iter):
		if model[iter][0] == 'SEPARATOR':
			return True
		return False

	def __init__(self):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'roster_window', APP)
		self.window = self.xml.get_widget('roster_window')
		self.tree = self.xml.get_widget('roster_treeview')
		self.nb_unread = 0
		self.last_save_dir = None
		self.editing_path = None  # path of row with cell in edit mode
		self.add_new_contact_handler_id = False
		self.service_disco_handler_id = False
		self.new_message_menuitem_handler_id = False
		self.regroup = gajim.config.get('mergeaccounts')
		#FIXME: When list_accel_closures will be wrapped in pygtk
		# no need of this variable
		self.have_new_message_accel = False # Is the "Ctrl+N" shown ?
		if gajim.config.get('saveposition'):
			gtkgui_helpers.move_window(self.window,
				gajim.config.get('roster_x-position'),
				gajim.config.get('roster_y-position'))
			gtkgui_helpers.resize_window(self.window,
				gajim.config.get('roster_width'),
				gajim.config.get('roster_height'))

		self.popups_notification_height = 0
		self.popup_notification_windows = []
		self.gpg_passphrase = {}
		#(icon, name, type, jid, account, editable, secondary_pixbuf)
		model = gtk.TreeStore(gtk.Image, str, str, str, str, bool, gtk.gdk.Pixbuf)
		model.set_sort_func(1, self.compareIters)
		model.set_sort_column_id(1, gtk.SORT_ASCENDING)
		self.tree.set_model(model)
		self.make_jabber_state_images()
		self.transports_state_images = { 'aim': {}, 'gadugadu': {}, 'irc': {},
			'icq': {}, 'msn': {}, 'sms': {}, 'weather': {}, 'yahoo': {} }
		
		path = os.path.join(gajim.DATA_DIR, 'iconsets/transports')
		folders = os.listdir(path)
		for transport in folders:
			if transport == '.svn':
				continue
			folder = os.path.join(path, transport)
			self.transports_state_images[transport] = self.load_iconset(
				folder + '/16x16/')

		# uf_show, img, show, sensitive
		liststore = gtk.ListStore(str, gtk.Image, str, bool)
		self.status_combobox = self.xml.get_widget('status_combobox')

		cell = cell_renderer_image.CellRendererImage()
		self.status_combobox.pack_start(cell, False)
		
		# img to show is in in 2nd column of liststore
		self.status_combobox.add_attribute(cell, 'image', 1)
		# if it will be sensitive or not it is in the fourth column
		# all items in the 'row' must have sensitive to False
		# if we want False (so we add it for img_cell too)
		self.status_combobox.add_attribute(cell, 'sensitive', 3)

		cell = gtk.CellRendererText()
		cell.set_property('xpad', 5) # padding for status text
		self.status_combobox.pack_start(cell, True)
		# text to show is in in first column of liststore
		self.status_combobox.add_attribute(cell, 'text', 0)
		# if it will be sensitive or not it is in the fourth column
		self.status_combobox.add_attribute(cell, 'sensitive', 3)

		self.status_combobox.set_row_separator_func(self.iter_is_separator)

		for show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible'):
			uf_show = helpers.get_uf_show(show)
			liststore.append([uf_show, self.jabber_state_images[show], show, True])
		# Add a Separator (self.iter_is_separator() checks on string SEPARATOR)
		liststore.append(['SEPARATOR', None, '', True])

		path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'rename.png')
		img = gtk.Image()
		img.set_from_file(path)
		# sensitivity to False because by default we're offline
		self.status_message_menuitem_iter = liststore.append(
			[_('Change Status Message...'), img, '', False])
		# Add a Separator (self.iter_is_separator() checks on string SEPARATOR)
		liststore.append(['SEPARATOR', None, '', True])

		uf_show = helpers.get_uf_show('offline')
		liststore.append([uf_show, self.jabber_state_images['offline'],
			'offline', True])
			
		status_combobox_items = ['online', 'chat', 'away', 'xa', 'dnd', 'invisible',
			'separator1', 'change_status_msg', 'separator2', 'offline']
		self.status_combobox.set_model(liststore)
		
		# default to offline
		number_of_menuitem = status_combobox_items.index('offline')
		self.status_combobox.set_active(number_of_menuitem)
		
		# holds index to previously selected item so if "change status message..."
		# is selected we can fallback to previously selected item and not stay
		# with that item selected
		self.previous_status_combobox_active = number_of_menuitem

		showOffline = gajim.config.get('showoffline')
		self.xml.get_widget('show_offline_contacts_menuitem').set_active(
			showOffline)

		# columns
		
		# this col has two cells: first one img, second one text
		col = gtk.TreeViewColumn()
		
		render_image = cell_renderer_image.CellRendererImage() # show img or +-
		col.pack_start(render_image, expand = False)
		col.add_attribute(render_image, 'image', C_IMG)
		col.set_cell_data_func(render_image, self.iconCellDataFunc, None)

		render_text = gtk.CellRendererText() # contact or group or account name
		render_text.connect('edited', self.on_cell_edited)
		render_text.connect('editing-canceled', self.on_editing_canceled)
		render_text.connect('editing-started', self.on_editing_started)
		col.pack_start(render_text, expand = True)
		col.add_attribute(render_text, 'text', C_NAME) # where we hold the name
		col.add_attribute(render_text, 'editable', C_EDITABLE) # where we hold if the row is editable
		col.set_cell_data_func(render_text, self.nameCellDataFunc, None)

		
		render_pixbuf = gtk.CellRendererPixbuf() # tls or avatar img
		col.pack_start(render_pixbuf, expand = False)
		col.add_attribute(render_pixbuf, 'pixbuf', C_SECPIXBUF)
		col.set_cell_data_func(render_pixbuf, self.fill_secondary_pixbuf_rederer,
			None)

		self.tree.append_column(col)
		
		#do not show gtk arrows workaround
		col = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand = False)
		self.tree.append_column(col)
		col.set_visible(False)
		self.tree.set_expander_column(col)

		#signals
		TARGETS = [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)]
		self.tree.enable_model_drag_source( gtk.gdk.BUTTON1_MASK, TARGETS,
			gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
		self.tree.enable_model_drag_dest(TARGETS, gtk.gdk.ACTION_DEFAULT)
		self.tree.connect('drag_data_get', self.drag_data_get_data)
		self.tree.connect('drag_data_received', self.drag_data_received_data)
		self.xml.signal_autoconnect(self)
		self.id_signal_cb = self.status_combobox.connect('changed',
			self.on_status_combobox_changed)

		self.collapsed_rows = gajim.config.get('collapsed_rows').split('\t')
		self.tooltip = tooltips.RosterTooltip()
		self.make_menu()
		self.draw_roster()

		if gajim.config.get('show_roster_on_startup'):
			self.window.show_all()
		else:
			if not gajim.config.get('trayicon'):
				# cannot happen via GUI, but I put this incase user touches config
				self.window.show_all() # without trayicon, he should see the roster!
				gajim.config.set('show_roster_on_startup', True)

		if len(gajim.connections) == 0: # if we have no account
			gajim.interface.windows['wizard_window'] = \
				config.AccountCreationWizardWindow()
