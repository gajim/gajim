##	roster_window.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
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
import cell_renderer_image

from gajim import User
from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class RosterWindow:
	'''Class for main window of gtkgui plugin'''

	def get_account_iter(self, name):
		if self.regroup:
			return None
		model = self.tree.get_model()
		account = model.get_iter_root()
		while account:
			account_name = model.get_value(account, 3)
			if name == account_name:
				break
			account = model.iter_next(account)
		return account

	def get_group_iter(self, name, account):
		model = self.tree.get_model()
		root = self.get_account_iter(account)
		group = model.iter_children(root)
		while group:
			group_name = model.get_value(group, 3)
			if name == group_name:
				break
			group = model.iter_next(group)
		return group

	def get_user_iter(self, jid, account):
		model = self.tree.get_model()
		acct = self.get_account_iter(account)
		found = []
		fin = False
		group = model.iter_children(acct)
		while group:
			user = model.iter_children(group)
			while user:
				if jid == model.get_value(user, 3):
					found.append(user)
				user = model.iter_next(user)
			group = model.iter_next(group)
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
		model.append(None, (self.jabber_state_images[status], account,
				'account', account, account, False))

	def remove_newly_added(self, jid, account):
		if jid in self.newly_added[account]:
			self.newly_added[account].remove(jid)
			self.draw_contact(jid, account)

	def add_user_to_roster(self, jid, account):
		'''Add a user to the roster and add groups if they aren't in roster'''
		showOffline = gajim.config.get('showoffline')
		if not self.contacts[account].has_key(jid):
			return
		users = self.contacts[account][jid]
		user = users[0]
		if user.jid.find('@') <= 0: # if not '@' or '@' starts the jid ==> agent
			user.groups = ['Transports']
		elif user.groups == []:
			user.groups.append('General')

		if (user.show == 'offline' or user.show == 'error') and \
		   not showOffline and (not 'Transports' in user.groups or \
			gajim.connections[account].connected < 2) and \
		   not self.plugin.queues[account].has_key(user.jid):
			return

		model = self.tree.get_model()
		for g in user.groups:
			iterG = self.get_group_iter(g, account)
			if not iterG:
				IterAcct = self.get_account_iter(account)
				iterG = model.append(IterAcct, 
					(self.jabber_state_images['closed'], g, 'group', g, account, False))
			if not self.groups[account].has_key(g): #It can probably never append
				if account + g in self.collapsed_rows:
					ishidden = False
				else:
					ishidden = True
				self.groups[account][g] = { 'expand': ishidden }
			if not account in self.collapsed_rows and \
			   not gajim.config.get('mergeaccounts'):
				self.tree.expand_row((model.get_path(iterG)[0]), False)

			typestr = 'user'
			if g == 'Transports':
				typestr = 'agent'

			model.append(iterG, (self.jabber_state_images[user.show], user.name,
					typestr, user.jid, account, False))
			
			if self.groups[account][g]['expand']:
				self.tree.expand_row(model.get_path(iterG),
							False)
		self.draw_contact(jid, account)
	
	def really_remove_user(self, user, account):
		if user.jid in self.newly_added[account]:
			return
		if user.jid.find('@') < 1 and gajim.connections[account].connected > 1: # It's an agent
			return
		if user.jid in self.to_be_removed[account]:
			self.to_be_removed[account].remove(user.jid)
		if gajim.config.get('showoffline'):
			self.draw_contact(user.jid, account)
			return
		self.remove_user(user, account)
	
	def remove_user(self, user, account):
		'''Remove a user from the roster'''
		if user.jid in self.to_be_removed[account]:
			return
		model = self.tree.get_model()
		for i in self.get_user_iter(user.jid, account):
			parent_i = model.iter_parent(i)
			group = model.get_value(parent_i, 3)
			model.remove(i)
			if model.iter_n_children(parent_i) == 0:
				model.remove(parent_i)
				# We need to check all contacts, even offline contacts
				group_empty = True
				for jid in self.contacts[account]:
					if group in self.contacts[account][jid][0].groups:
						group_empty = False
						break
				if group_empty:
					del self.groups[account][group]

	def get_appropriate_state_images(self, jid):
		'''check jid and return the appropriate state images dict'''
		if not jid or not gajim.config.get('use_transports_iconsets'):
			return self.jabber_state_images

		host = jid.split('@')[-1]

		if host.startswith('aim'):
			state_images = self.transports_state_images['aim']
		elif host.startswith('gadugadu'):
			state_images = self.transports_state_images['gadugadu']
		elif host.startswith('irc'):
			state_images = self.transports_state_images['irc']
		elif host.startswith('icq'): # abc@icqsucks.org will match as ICQ, but what to do..
			state_images = self.transports_state_images['icq']
		elif host.startswith('msn'):
			state_images = self.transports_state_images['msn']
		elif host.startswith('sms'):
			state_images = self.transports_state_images['sms']
		elif host.startswith('yahoo'):
			state_images = self.transports_state_images['yahoo']
		else:
			state_images = self.jabber_state_images

		return state_images

	def draw_contact(self, jid, account):
		'''draw the correct state image and name'''
		model = self.tree.get_model()
		iters = self.get_user_iter(jid, account)
		if len(iters) == 0:
			return
		users = self.contacts[account][jid]
		name = users[0].name
		if len(users) > 1:
			name += ' (' + str(len(users)) + ')'
		prio = 0
		user = users[0]
		for u in users:
			if u.priority > prio:
				prio = u.priority
				user = u

		state_images = self.get_appropriate_state_images(jid)
		if self.plugin.queues[account].has_key(jid):
			img = state_images['message']
		elif jid.find('@') <= 0: # if not '@' or '@' starts the jid ==> agent
			img = state_images[user.show]					
		else:
			if user.sub == 'both':
				img = state_images[user.show]
			else:
				if user.ask == 'subscribe':
					img = state_images['requested']
				else:
					img = state_images['not in the roster']
		for iter in iters:
			model.set_value(iter, 0, img)
			model.set_value(iter, 1, name)

	def join_gc_room(self, account, bookmark):
		jid = bookmark['jid']
		self.new_room(jid, bookmark['nick'], account)
		self.plugin.windows[account]['gc'][jid].set_active_tab(jid)
		self.plugin.windows[account]['gc'][jid].window.present()

	def on_bookmark_menuitem_activate(self, widget, account, bookmark):
		self.join_gc_room(account, bookmark)

	def on_bm_header_changed_state(self, widget, event):
		widget.set_state(gtk.STATE_NORMAL) #do not allow selected_state

	def make_menu(self):
		'''create the main_window's menus'''
		new_message_menuitem = self.xml.get_widget('new_message_menuitem')
		join_gc_menuitem = self.xml.get_widget('join_gc_menuitem')
		add_new_contact_menuitem  = self.xml.get_widget('add_new_contact_menuitem')
		service_disco_menuitem  = self.xml.get_widget('service_disco_menuitem')
		if self.add_new_contact_handler_id:
			add_new_contact_menuitem.handler_disconnect(self.add_new_contact_handler_id)
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
		if add_new_contact_menuitem.get_submenu():
			add_new_contact_menuitem.remove_submenu()
		if service_disco_menuitem.get_submenu():
			service_disco_menuitem.remove_submenu()
		join_gc_menuitem.remove_submenu()
		if new_message_menuitem.get_submenu():
			new_message_menuitem.remove_submenu()
		if len(gajim.connections) > 0:
			new_message_menuitem.set_sensitive(True)
			join_gc_menuitem.set_sensitive(True)
			add_new_contact_menuitem.set_sensitive(True)
			service_disco_menuitem.set_sensitive(True)
		else:
			new_message_menuitem.set_sensitive(False)
			join_gc_menuitem.set_sensitive(False)
			add_new_contact_menuitem.set_sensitive(False)
			service_disco_menuitem.set_sensitive(False)

		#join gc
		sub_menu = gtk.Menu()
		join_gc_menuitem.set_submenu(sub_menu)
		at_least_one_account_connected = False
		for account in gajim.connections:
			if gajim.connections[account].connected <= 1:
				continue
			if not at_least_one_account_connected:
				at_least_one_account_connected = True
			label = gtk.Label()
			label.set_markup('<u>' + account.upper() +'</u>')
			item = gtk.MenuItem()
			item.add(label)
			item.connect('state-changed', self.on_bm_header_changed_state)
			sub_menu.append(item)
			
			item = gtk.MenuItem(_('New _Room'))
			sub_menu.append(item)
			item.connect('activate', self.on_join_gc_activate, account)

			for bookmark in gajim.connections[account].bookmarks:
				item = gtk.MenuItem(bookmark['name'])
				sub_menu.append(item)
				item.connect('activate', self.on_bookmark_menuitem_activate,
					account, bookmark)

		if at_least_one_account_connected:
			newitem = gtk.MenuItem() # seperator
			sub_menu.append(newitem)
		
			newitem = gtk.MenuItem('Bookmarks')
			sub_menu.append(newitem)
			newitem.connect('activate', self.on_bookmarks_menuitem_activate)
			sub_menu.show_all()

		if len(gajim.connections) >= 2: # 2 or more accounts? make submenus
			#add
			sub_menu = gtk.Menu()
			add_new_contact_menuitem.set_submenu(sub_menu)
			for account in gajim.connections:
				item = gtk.MenuItem(_('to ') + account + _(' account'))
				sub_menu.append(item)
				item.connect('activate', self.on_add_new_contact, account)
			sub_menu.show_all()
			#disco
			sub_menu = gtk.Menu()
			service_disco_menuitem.set_submenu(sub_menu)
			for account in gajim.connections:
				item = gtk.MenuItem(_('using ') + account + _(' account'))
				sub_menu.append(item)
				item.connect('activate', self.on_service_disco_menuitem_activate, account)
			sub_menu.show_all()
			
			#new message
			sub_menu = gtk.Menu()
			new_message_menuitem.set_submenu(sub_menu)
			for account in gajim.connections:
				our_jid = gajim.config.get_per('accounts', account, 'name') + '@' +\
					gajim.config.get_per('accounts', account, 'hostname')
				item = gtk.MenuItem(_('as ') + our_jid)
				sub_menu.append(item)
				item.connect('activate', self.on_new_message_menuitem_activate, 
									account)
			sub_menu.show_all()
		elif len(gajim.connections) == 1: # one account
			#add
			if not self.add_new_contact_handler_id:
				self.add_new_contact_handler_id = add_new_contact_menuitem.connect(
					'activate', self.on_add_new_contact, gajim.connections.keys()[0])
			#disco
			if not self.service_disco_handler_id:
				self.service_disco_handler_id = service_disco_menuitem.connect( 
					'activate', self.on_service_disco_menuitem_activate, 
					gajim.connections.keys()[0])
			if not self.new_message_menuitem_handler_id:
				self.new_message_menuitem_handler_id = new_message_menuitem.\
					connect('activate', self.on_new_message_menuitem_activate, 
					gajim.connections.keys()[0])

	def draw_roster(self):
		'''Clear and draw roster'''
		self.make_menu()
		self.tree.get_model().clear()
		for acct in gajim.connections:
			self.add_account_to_roster(acct)
			for jid in self.contacts[acct].keys():
				self.add_user_to_roster(jid, acct)
	
	def mklists(self, array, account):
		'''fill self.contacts and self.groups'''
		if not self.contacts.has_key(account):
			self.contacts[account] = {}
		if not self.groups.has_key(account):
			self.groups[account] = {}
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
			user1 = User(ji, name, array[jid]['groups'], show, status,\
					array[jid]['subscription'], array[jid]['ask'], resource, 0,
					keyID)

			# when we draw the roster, we avoid having the same contact
			# more than once (eg. we avoid showing it twice with 2 resources)
			self.contacts[account][ji] = [user1]
			for g in array[jid]['groups'] :
				if g in self.groups[account].keys():
					continue

				if account + g in self.collapsed_rows:
					ishidden = False
				else:
					ishidden = True
				self.groups[account][g] = { 'expand': ishidden }

	def chg_user_status(self, user, show, status, account):
		'''When a user change his status'''
		showOffline = gajim.config.get('showoffline')
		model = self.tree.get_model()
		luser = self.contacts[account][user.jid]
		user.show = show
		user.status = status
		if (show == 'offline' or show == 'error') and \
		   not self.plugin.queues[account].has_key(user.jid):
			if len(luser) > 1:
				luser.remove(user)
				self.draw_contact(user.jid, account)
			elif not showOffline:
				self.remove_user(user, account)
			else:
				self.draw_contact(user.jid, account)
		else:
			if not self.get_user_iter(user.jid, account):
				self.add_user_to_roster(user.jid, account)
			self.draw_contact(user.jid, account)
		#print status in chat window and update status/GPG image
		if self.plugin.windows[account]['chats'].has_key(user.jid):
			jid = user.jid
			self.plugin.windows[account]['chats'][jid].set_state_image(jid)
			name = user.name
			if user.resource != '':
				name += '/' + user.resource
			uf_show = helpers.get_uf_show(show)
			self.plugin.windows[account]['chats'][jid].print_conversation(
				_('%s is now %s (%s)') % (name, uf_show, status), jid, 'status')

	def on_info(self, widget, user, account):
		'''Call vcard_information_window class to display user's information'''
		info = self.plugin.windows[account]['infos']
		if info.has_key(user.jid):
			info[user.jid].window.present()
		else:
			info[user.jid] = dialogs.VcardWindow(user, self.plugin,
								account)

	def on_agent_logging(self, widget, jid, state, account):
		'''When an agent is requested to log in or off'''
		gajim.connections[account].send_agent_status(jid, state)

	def on_edit_agent(self, widget, user, account):
		'''When we want to modify the agent registration'''
		gajim.connections[account].request_register_agent_info(user.jid)

	def on_remove_agent(self, widget, user, account):
		'''When an agent is requested to log in or off'''
		window = dialogs.ConfirmationDialog(_('Transport "%s" will be removed') % user.jid, _('You will no longer be able to send and receive messages to contacts from %s.' % user.jid))
		if window.get_response() == gtk.RESPONSE_OK:
			gajim.connections[account].unsubscribe_agent(user.jid + '/' \
																		+ user.resource)
			# remove transport from treeview
			self.remove_user(user, account)
			# remove transport's contacts from treeview
			for jid, contacts in self.contacts[account].items():
				contact = contacts[0]
				if jid.endswith('@' + user.jid):
					gajim.log.debug('REMOVE user %s due to unregistered transport %s' % (contact.jid, user.name))
					self.remove_user(contact, account)
			del self.contacts[account][user.jid]

	def on_rename(self, widget, iter, path):
		model = self.tree.get_model()
		model.set_value(iter, 5, True)
		self.tree.set_cursor(path, self.tree.get_column(0), True)
		
	def on_assign_pgp_key(self, widget, user, account):
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		keys = {}
		keyID = 'None'
		for i in range(0, len(attached_keys)/2):
			keys[attached_keys[2*i]] = attached_keys[2*i+1]
			if attached_keys[2*i] == user.jid:
				keyID = attached_keys[2*i+1]
		public_keys = gajim.connections[account].ask_gpg_keys()
		public_keys['None'] = 'None'
		w = dialogs.ChooseGPGKeyDialog(_('Assign PGP Key'), _('Select a key to apply to the contact'), 
			public_keys, keyID)
		keyID = w.run()
		if keyID == -1:
			return
		if keyID[0] == 'None' and user.jid in keys:
			del keys[user.jid]
		else:
			keys[user.jid] = keyID[0]
			for u in self.contacts[account][user.jid]:
				u.keyID = keyID[0]
			if self.plugin.windows[account]['chats'].has_key(user.jid):
				self.plugin.windows[account]['chats'][user.jid].draw_widgets(user)
		keys_str = ''
		for jid in keys:
			keys_str += jid + ' ' + keys[jid]
		gajim.config.set_per('accounts', account, 'attached_gpg_keys', keys_str)

	def on_edit_groups(self, widget, user, account):
		dlg = dialogs.EditGroupsDialog(user, account, self.plugin)
		dlg.run()
		
	def on_history(self, widget, user):
		'''When history menuitem is activated: call log window'''
		if self.plugin.windows['logs'].has_key(user.jid):
			self.plugin.windows['logs'][user.jid].window.present()
		else:
			self.plugin.windows['logs'][user.jid] = history_window.\
				HistoryWindow(self.plugin, user.jid)
	
	def mk_menu_user(self, event, iter):
		'''Make user's popup menu'''
		model = self.tree.get_model()
		jid = model.get_value(iter, 3)
		path = model.get_path(iter)
		account = model.get_value(iter, 4)
		user = self.contacts[account][jid][0]
		
		menu = gtk.Menu()
		item = gtk.MenuItem(_('Start chat'))
		menu.append(item)
		item.connect('activate', self.on_roster_treeview_row_activated, path)
		item = gtk.MenuItem(_('Rename'))
		menu.append(item)
		item.connect('activate', self.on_rename, iter, path)
		if not 'not in the roster' in user.groups:
			item = gtk.MenuItem(_('Edit Groups'))
			menu.append(item)
			item.connect('activate', self.on_edit_groups, user, account)
			item = gtk.MenuItem()
			menu.append(item)
			if gajim.config.get('usegpg'):
				item = gtk.MenuItem(_('Assign OpenPGP key'))
				menu.append(item)
				item.connect('activate', self.on_assign_pgp_key, user, account)
				item = gtk.MenuItem()
				menu.append(item)
			item = gtk.MenuItem(_('Subscription'))
			menu.append(item)

			sub_menu = gtk.Menu()
			item.set_submenu(sub_menu)
			item = gtk.MenuItem(_('Resend Authorization to'))
			sub_menu.append(item)
			item.connect('activate', self.authorize, jid, account)
			item = gtk.MenuItem(_('Rerequest Authorization from'))
			sub_menu.append(item)
			item.connect('activate', self.req_sub, jid, 
				_('I would like to add you to my roster'), account)
		else:
			item = gtk.MenuItem()
			menu.append(item)
			item = gtk.MenuItem(_('Add to Roster'))
			menu.append(item)
			item.connect('activate', self.on_add_to_roster, user, account)

		item = gtk.MenuItem(_('Remove'))
		menu.append(item)
		item.connect('activate', self.on_req_usub, user, account)

		item = gtk.MenuItem()
		menu.append(item)
		item = gtk.MenuItem(_('Information'))
		menu.append(item)
		item.connect('activate', self.on_info, user, account)
		item = gtk.MenuItem(_('History'))
		menu.append(item)
		item.connect('activate', self.on_history, user)

		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def mk_menu_g(self, event, iter):
		'''Make group's popup menu'''
		model = self.tree.get_model()
		path = model.get_path(iter)

		menu = gtk.Menu()
		item = gtk.MenuItem(_('Rename'))
		menu.append(item)
		item.connect('activate', self.on_rename, iter, path)
		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()
	
	def mk_menu_agent(self, event, iter):
		'''Make agent's popup menu'''
		model = self.tree.get_model()
		jid = model.get_value(iter, 3)
		path = model.get_path(iter)
		account = model.get_value(iter, 4)
		user = self.contacts[account][jid][0]
		menu = gtk.Menu()
		item = gtk.MenuItem(_('_Log on'))
		show = self.contacts[account][jid][0].show
		if show != 'offline' and show != 'error':
			item.set_sensitive(False)
		menu.append(item)
		item.connect('activate', self.on_agent_logging, jid, None, account)

		item = gtk.MenuItem(_('Log _off'))
		if show == 'offline' or show == 'error':
			item.set_sensitive(False)
		menu.append(item)
		item.connect('activate', self.on_agent_logging, jid, 'unavailable',
							account)

		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem(_('_Edit'))
		menu.append(item)
		item.connect('activate', self.on_edit_agent, user, account)

		item = gtk.MenuItem(_('_Remove'))
		menu.append(item)
		item.connect('activate', self.on_remove_agent, user, account)

		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def on_edit_account(self, widget, account):
		if self.plugin.windows[account].has_key('account_modification'):
			self.plugin.windows[account]['account_modification'].window.present()
		else:
			self.plugin.windows[account]['account_modification'] = \
				config.AccountModificationWindow(self.plugin, account)

	def mk_menu_account(self, event, iter):
		'''Make account's popup menu'''
		model = self.tree.get_model()
		account = model.get_value(iter, 3)
		
		menu = gtk.Menu()
		item = gtk.MenuItem(_('Status'))
		menu.append(item)
		
		sub_menu = gtk.Menu()
		item.set_submenu(sub_menu)
		item = gtk.MenuItem(_('Online'))
		sub_menu.append(item)
		item.connect('activate', self.change_status, account, 'online')
		item = gtk.MenuItem(_('Free for chat'))
		sub_menu.append(item)
		item.connect('activate', self.change_status, account, 'chat')
		item = gtk.MenuItem(_('Away'))
		sub_menu.append(item)
		item.connect('activate', self.change_status, account, 'away')
		item = gtk.MenuItem(_('Not Available'))
		sub_menu.append(item)
		item.connect('activate', self.change_status, account, 'xa')
		item = gtk.MenuItem(_('Busy'))
		sub_menu.append(item)
		item.connect('activate', self.change_status, account, 'dnd')
		item = gtk.MenuItem(_('Invisible'))
		sub_menu.append(item)
		item.connect('activate', self.change_status, account, 'invisible')
		item = gtk.MenuItem()
		sub_menu.append(item)
		item = gtk.MenuItem(_('Offline'))
		sub_menu.append(item)
		item.connect('activate', self.change_status, account, 'offline')
		
		item = gtk.MenuItem()
		menu.append(item)

		item = gtk.MenuItem(_('_Edit Account'))
		menu.append(item)
		item.connect('activate', self.on_edit_account, account)
		item = gtk.MenuItem(_('_Service Discovery'))
		menu.append(item)
		item.connect('activate', self.on_service_disco_menuitem_activate, account)
		item = gtk.MenuItem(_('_Add Contact'))
		menu.append(item)
		item.connect('activate', self.on_add_new_contact, account)
		item = gtk.MenuItem(_('Join _Groupchat'))
		menu.append(item)
		item.connect('activate', self.on_join_gc_activate, account)
		item = gtk.MenuItem(_('_New Message'))
		menu.append(item)
		item.connect('activate', self.on_new_message_menuitem_activate, account)

		menu.popup(None, None, None, event.button, event.time)
		menu.show_all()
		menu.reposition()

	def on_add_to_roster(self, widget, user, account):
		dialogs.AddNewContactWindow(self.plugin, account, user.jid)
	
	def authorize(self, widget, jid, account):
		'''Authorize a user'''
		gajim.connections[account].send_authorization(jid)

	def req_sub(self, widget, jid, txt, account, group = None, pseudo = None):
		'''Request subscription to a user'''
		if not pseudo:
			pseudo = jid
		gajim.connections[account].request_subscription(jid, txt)
		if not group:
			group = 'General'
		if not self.contacts[account].has_key(jid):
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			user1 = User(jid, pseudo, [group], 'requested', 'requested', 
								'none', 'subscribe', '', 0, keyID)
			self.contacts[account][jid] = [user1]
		else:
			user1 = self.contacts[account][jid][0]
			if not 'not in the roster' in user1.groups:
				return
			user1.groups = [group]
			user1.name = pseudo
			self.remove_user(user1, account)
		self.add_user_to_roster(jid, account)

	def on_roster_treeview_key_press_event(self, widget, event):
		'''when a key is pressed in the treeviews'''
		if event.keyval == gtk.keysyms.Escape:
			self.tree.get_selection().unselect_all()
		if event.keyval == gtk.keysyms.F2:
			treeselection = self.tree.get_selection()
			model, iter = treeselection.get_selected()
			if not iter:
				return
			type = model.get_value(iter, 2)
			if type == 'user' or type == 'group':
				path = model.get_path(iter)
				model.set_value(iter, 5, True)
				self.tree.set_cursor(path, self.tree.get_column(0), True)
		if event.keyval == gtk.keysyms.Delete:
			treeselection = self.tree.get_selection()
			model, iter = treeselection.get_selected()
			if not iter:
				return
			jid = model.get_value(iter, 3)
			account = model.get_value(iter, 4)
			type = model.get_value(iter, 2)
			user = self.contacts[account][jid][0]
			if type == 'user':
				self.on_req_usub(widget, user, account)
			elif type == 'agent':
				self.on_remove_agent(widget, user, account)
		return False
	
	def on_roster_treeview_button_press_event(self, widget, event):
		'''popup contact's, group's or agent's menu'''
		if event.type == gtk.gdk.BUTTON_PRESS:
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
				type = model.get_value(iter, 2)
				if type == 'group':
					self.mk_menu_g(event, iter)
				elif type == 'agent':
					self.mk_menu_agent(event, iter)
				elif type == 'user':
					self.mk_menu_user(event, iter)
				elif type == 'account':
					self.mk_menu_account(event, iter)
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
				type = model.get_value(iter, 2)
				if type == 'group':
					if x < 20: # first cell in 1st column (the arrow SINGLE clicked)
						if (self.tree.row_expanded(path)):
							self.tree.collapse_row(path)
						else:
							self.tree.expand_row(path, False)

	def on_req_usub(self, widget, user, account):
		'''Remove a user'''
		window = dialogs.ConfirmationDialog(\
			_('Contact "%s" will be removed from your roster') % (user.name),
			_('By removing this contact you also remove authorization. Contact "%s" will always see you as offline.') % user.name)
		if window.get_response() == gtk.RESPONSE_OK:
			gajim.connections[account].unsubscribe(user.jid)
			for u in self.contacts[account][user.jid]:
				self.remove_user(u, account)
			del self.contacts[account][u.jid]
			if user.jid in self.plugin.windows[account]['chats']:
				user1 = User(user.jid, user.name, ['not in the roster'],
					'not in the roster', 'not in the roster', 'none', None, '', 0,
					user.keyID)
				self.contacts[account][user.jid] = [user1] 
				self.add_user_to_roster(user.jid, account)	
			
	def forget_gpg_passphrase(self, keyid):
		if self.gpg_passphrase.has_key(keyid):
			del self.gpg_passphrase[keyid]
		return False

	def send_status(self, account, status, txt):
		if status != 'offline':
			if gajim.connections[account].connected < 2:
				model = self.tree.get_model()
				accountIter = self.get_account_iter(account)
				if accountIter:
					model.set_value(accountIter, 0, self.jabber_state_images['connecting'])
				if self.plugin.systray_enabled:
					self.plugin.systray.set_status('connecting')

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
						model.set_value(accountIter, 0, self.jabber_state_images['offline'])
#					gajim.connections[account].connected = 0
					if self.plugin.systray_enabled:
						self.plugin.systray.set_status('offline')
					self.update_status_comboxbox()
					return
				gajim.connections[account].password = passphrase
				if save:
					gajim.config.set_per('accounts', account, 'savepass', True)
					gajim.config.set_per('accounts', account, 'password', passphrase)

			keyid = None
			save_gpg_pass = 0
			save_gpg_pass = gajim.config.get_per('accounts', account, 
				'savegpgpass')
			keyid = gajim.config.get_per('accounts', account, 'keyid')
			if keyid and gajim.connections[account].connected < 2 and \
				gajim.config.get('usegpg'):
				if save_gpg_pass:
					passphrase = gajim.config.get_per('accounts', account, 
																	'gpgpassword')
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
						passphrase = ''
					else:
						self.gpg_passphrase[keyid] = passphrase
						gobject.timeout_add(30000, self.forget_gpg_passphrase, keyid)
					if save:
						gajim.config.set_per('accounts', account, 'savegpgpass', True)
						gajim.config.set_per('accounts', account, 'gpgpassword', 
													passphrase)
				gajim.connections[account].gpg_passphrase(passphrase)
		gajim.connections[account].change_status(status, txt)
		for room_jid in self.plugin.windows[account]['gc']:
			if room_jid != 'tabbed':
				nick = self.plugin.windows[account]['gc'][room_jid].nicks[room_jid]
				gajim.connections[account].send_gc_status(nick, room_jid, status, 
																		txt)
		if status == 'online' and self.plugin.sleeper.getState() != \
			common.sleepy.STATE_UNKNOWN:
			self.plugin.sleeper_state[account] = 1
		else:
			self.plugin.sleeper_state[account] = 0

	def get_status_message(self, show):
		if (show == 'online' and not gajim.config.get('ask_online_status')) or \
			(show == 'offline' and not gajim.config.get('ask_offline_status')):
			lowered_uf_status_msg = helpers.get_uf_show(show).lower()
			return _("I'm %s") % lowered_uf_status_msg
		dlg = dialogs.ChangeStatusMessageDialog(self.plugin, show)
		message = dlg.run()
		return message

	def change_status(self, widget, account, status):
		message = self.get_status_message(status)
		if message == -1:
			return
		self.send_status(account, status, message)

	def on_status_combobox_changed(self, widget):
		'''When we change our status'''
		model = self.status_combobox.get_model()
		active = self.status_combobox.get_active()
		if active < 0:
			return
		accounts = gajim.connections.keys()
		if len(accounts) == 0:
			dialogs.ErrorDialog(_('No accounts created'),
				_('You must create Jabber account before connecting the server.')).get_response()
			self.update_status_comboxbox()
			return
		status = model[active][2]
		message = self.get_status_message(status)
		if message == -1:
			self.update_status_comboxbox()
			return
		for acct in accounts:
			if not gajim.config.get_per('accounts', acct, 
													'sync_with_global_status'):
				continue
			self.send_status(acct, status, message)
	
	def update_status_comboxbox(self):
		#table to change index in plugin.connected to index in combobox
		table = {0:6, 1:6, 2:0, 3:1, 4:2, 5:3, 6:4, 7:5}
		maxi = 0
		for account in gajim.connections:
			if gajim.connections[account].connected > maxi:
				maxi = gajim.connections[account].connected
		#temporarily block signal in order not to send status that we show
		#in the combobox
		self.status_combobox.handler_block(self.id_signal_cb)
		self.status_combobox.set_active(table[maxi])
		self.status_combobox.handler_unblock(self.id_signal_cb)
		statuss = ['offline', 'connecting', 'online', 'chat', 'away', 
						'xa', 'dnd', 'invisible']
		if self.plugin.systray_enabled:
			self.plugin.systray.set_status(statuss[maxi])

	def on_status_changed(self, account, status):
		'''the core tells us that our status has changed'''
		if not self.contacts.has_key(account):
			return
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if accountIter:
			model.set_value(accountIter, 0, self.jabber_state_images[status])
		if status == 'offline':
			for jid in self.contacts[account]:
				luser = self.contacts[account][jid]
				luser_copy = []
				for user in luser:
					luser_copy.append(user)
				for user in luser_copy:
					self.chg_user_status(user, 'offline', 'Disconnected', account)
		self.update_status_comboxbox()

	def new_chat(self, user, account):
		if gajim.config.get('usetabbedchat'):
			if not self.plugin.windows[account]['chats'].has_key('tabbed'):
				self.plugin.windows[account]['chats']['tabbed'] = \
					tabbed_chat_window.TabbedChatWindow(user, self.plugin, account)
			else:
				self.plugin.windows[account]['chats']['tabbed'].new_user(user)
				
			self.plugin.windows[account]['chats'][user.jid] = \
				self.plugin.windows[account]['chats']['tabbed']
		else:
			self.plugin.windows[account]['chats'][user.jid] = \
				tabbed_chat_window.TabbedChatWindow(user, self.plugin, account)

	def new_room(self, jid, nick, account):
		if gajim.config.get('usetabbedchat'):
			if not self.plugin.windows[account]['gc'].has_key('tabbed'):
				self.plugin.windows[account]['gc']['tabbed'] = \
					groupchat_window.GroupchatWindow(jid, nick, self.plugin, 
																	account)
			else:
				self.plugin.windows[account]['gc']['tabbed'].new_room(jid, nick)
			self.plugin.windows[account]['gc'][jid] = \
				self.plugin.windows[account]['gc']['tabbed']
		else:
			self.plugin.windows[account]['gc'][jid] = \
				groupchat_window.GroupchatWindow(jid, nick, self.plugin, account)

	def on_message(self, jid, msg, tim, account, encrypted = False):
		'''when we receive a message'''
		if not self.contacts[account].has_key(jid):
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			user1 = User(jid, jid, ['not in the roster'], 'not in the roster', 
								'not in the roster', 'none', None, '', 0, keyID)
			self.contacts[account][jid] = [user1] 
			self.add_user_to_roster(jid, account)
		iters = self.get_user_iter(jid, account)
		if iters:
			path = self.tree.get_model().get_path(iters[0])
		else:
			path = None
		autopopup = gajim.config.get('autopopup')
		autopopupaway = gajim.config.get('autopopupaway')
		# Do we have a queue ?
		no_queue = True
		if self.plugin.queues[account].has_key(jid):
			no_queue = False
		if self.plugin.windows[account]['chats'].has_key(jid):
			self.plugin.windows[account]['chats'][jid].print_conversation(msg, 
				jid, tim = tim, encrypted = encrypted)
			return
		#We save it in a queue
		if not self.plugin.queues[account].has_key(jid):
			self.plugin.queues[account][jid] = []
		self.plugin.queues[account][jid].append((msg, tim, encrypted))
		self.nb_unread += 1
		if (not autopopup or ( not autopopupaway and \
			gajim.connections[account].connected > 2)) and not \
			self.plugin.windows[account]['chats'].has_key(jid):
			if no_queue: #We didn't have a queue: we change icons
				model = self.tree.get_model()
				self.draw_contact(jid, account)
				if self.plugin.systray_enabled:
					self.plugin.systray.add_jid(jid, account)
			self.show_title() # we show the * or [n]
			if not path:
				self.add_user_to_roster(jid, account)
				iters = self.get_user_iter(jid, account)
				path = self.tree.get_model().get_path(iters[0])
			self.tree.expand_row(path[0:1], False)
			self.tree.expand_row(path[0:2], False)
			self.tree.scroll_to_cell(path)
			self.tree.set_cursor(path)
		else:
			if not self.plugin.windows[account]['chats'].has_key(jid):
				self.new_chat(self.contacts[account][jid][0], account)
				if path:
					self.tree.expand_row(path[0:1], False)
					self.tree.expand_row(path[0:2], False)
					self.tree.scroll_to_cell(path)
					self.tree.set_cursor(path)

	def on_preferences_menuitem_activate(self, widget):
		if self.plugin.windows['preferences'].window.get_property('visible'):
			self.plugin.windows['preferences'].window.present()
		else:
			self.plugin.windows['preferences'].window.show_all()

	def on_add_new_contact(self, widget, account):
		dialogs.AddNewContactWindow(self.plugin, account)

	def on_join_gc_activate(self, widget, account):
		if self.plugin.windows[account].has_key('join_gc'):
			self.plugin.windows[account]['join_gc'].window.present()		
		else:
			try:
				self.plugin.windows[account]['join_gc'] = dialogs.JoinGroupchatWindow(self.plugin, account)
			except RuntimeError:
				pass


	def on_new_message_menuitem_activate(self, widget, account):
		dialogs.NewMessageDialog(self.plugin, account)
			
	def on_about_menuitem_activate(self, widget):
		dialogs.AboutDialog()

	def on_accounts_menuitem_activate(self, widget):
		if self.plugin.windows.has_key('accounts'):
			self.plugin.windows['accounts'].window.present()
		else:
			self.plugin.windows['accounts'] = config.AccountsWindow(self.plugin) 

	def on_bookmarks_menuitem_activate(self, widget):
		config.ManageBookmarksWindow(self.plugin)

	def close_all(self, dic):
		'''close all the windows in the given dictionary'''
		for w in dic.values():
			if type(w) == type({}):
				self.close_all(w)
			else:
				w.window.destroy()
	
	def on_roster_window_delete_event(self, widget, event):
		'''When we want to close the window'''
		if self.plugin.systray_enabled:
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
				if message == -1:
					message = ''
				for acct in accounts:
					if gajim.connections[acct].connected:
						self.send_status(acct, 'offline', message)
			self.quit_gtkgui_plugin()
		return True # do NOT destory the window

	def quit_gtkgui_plugin(self):
		'''When we quit the gtk plugin :
		tell that to the core and exit gtk'''
		if gajim.config.get('saveposition'):
			x, y = self.window.get_position()
			gajim.config.set('x-position', x)
			gajim.config.set('y-position', y)
			width, height = self.window.get_size()
			gajim.config.set('width', width)
			gajim.config.set('height', height)

		gajim.config.set('collapsed_rows', '\t'.join(self.collapsed_rows))
		self.plugin.save_config()
		for account in gajim.connections:
			gajim.connections[account].quit(True)
		self.close_all(self.plugin.windows)
		if self.plugin.systray_enabled:
			self.plugin.hide_systray()
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
			if message == -1:
				return
			# check if we have unread or recent mesages
			unread = False
			recent = False
			if self.nb_unread > 0:
				unread = True
			for account in accounts:
				if self.plugin.windows[account]['chats'].has_key('tabbed'):
					wins = [self.plugin.windows[account]['chats']['tabbed']]
				else:
					wins = self.plugin.windows[account]['chats'].values()
				for win in wins:
					unrd = 0
					for jid in win.nb_unread:
						unrd += win.nb_unread[jid]
					if unrd:
						unread = True
						break
					for jid in win.users:
						if time.time() - win.last_message_time[jid] < 2:
							recent = True
							break
			if unread:
				dialog = dialogs.ConfirmationDialog(_('You have unread messages'), _('If you exit Gajim these messages will be lost.'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return

			if recent:
				dialog = dialogs.ConfirmationDialog(_('You have unread messages'), _('If you exit Gajim these messages will be lost.'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return
			for acct in accounts:
				if gajim.connections[acct].connected:
					self.send_status(acct, 'offline', message)
		self.quit_gtkgui_plugin()

	def on_roster_treeview_row_activated(self, widget, path, col = 0):
		'''When an iter is double clicked: open the chat window'''
		model = self.tree.get_model()
		iter = model.get_iter(path)
		account = model.get_value(iter, 4)
		type = model.get_value(iter, 2)
		jid = model.get_value(iter, 3)
		if type == 'group' or type == 'account':
			if self.tree.row_expanded(path):
				self.tree.collapse_row(path)
			else:
				self.tree.expand_row(path, False)
		else:
			if self.plugin.windows[account]['chats'].has_key(jid):
				self.plugin.windows[account]['chats'][jid].set_active_tab(jid)
			elif self.contacts[account].has_key(jid):
				self.new_chat(self.contacts[account][jid][0], account)
				self.plugin.windows[account]['chats'][jid].set_active_tab(jid)
			self.plugin.windows[account]['chats'][jid].window.present()

	def on_roster_treeview_row_expanded(self, widget, iter, path):
		'''When a row is expanded change the icon of the arrow'''
		model = self.tree.get_model()
		account = model.get_value(iter, 4)
		type = model.get_value(iter, 2)
		if type == 'group':
			model.set_value(iter, 0, self.jabber_state_images['opened'])
			jid = model.get_value(iter, 3)
			self.groups[account][jid]['expand'] = True
			if account + jid in self.collapsed_rows:
				self.collapsed_rows.remove(account + jid)
		elif type == 'account':
			if account in self.collapsed_rows:
				self.collapsed_rows.remove(account)
			for g in self.groups[account]:
				groupIter = self.get_group_iter(g, account)
				if groupIter and self.groups[account][g]['expand']:
					pathG = model.get_path(groupIter)
					self.tree.expand_row(pathG, False)
			
	
	def on_roster_treeview_row_collapsed(self, widget, iter, path):
		'''When a row is collapsed :
		change the icon of the arrow'''
		model = self.tree.get_model()
		account = model.get_value(iter, 4)
		type = model.get_value(iter, 2)
		if type == 'group':
			model.set_value(iter, 0, self.jabber_state_images['closed'])
			jid = model.get_value(iter, 3)
			self.groups[account][jid]['expand'] = False
			if not account + jid in self.collapsed_rows:
				self.collapsed_rows.append(account + jid)
		elif type == 'account':
			if not account in self.collapsed_rows:
				self.collapsed_rows.append(account)

	def on_editing_canceled (self, cell):
		'''editing has been canceled'''
		#TODO: get iter
		#model.set_value(iter, 5, False)
		pass

	def on_cell_edited(self, cell, row, new_text):
		'''When an iter is editer :
		if text has changed, rename the user'''
		model = self.tree.get_model()
		iter = model.get_iter_from_string(row)
		path = model.get_path(iter)
		account = model.get_value(iter, 4)
		jid = model.get_value(iter, 3)
		type = model.get_value(iter, 2)
		if type == 'user':
			old_text = self.contacts[account][jid][0].name
			if old_text != new_text:
				for u in self.contacts[account][jid]:
					u.name = new_text
				gajim.connections[account].update_user(jid, new_text, u.groups)
			self.draw_contact(jid, account)
		elif type == 'group':
			old_name = model.get_value(iter, 1)
			#get all users in that group
			for jid in self.contacts[account]:
				user = self.contacts[account][jid][0]
				if old_name in user.groups:
					#set them in the new one and remove it from the old
					self.remove_user(user, account)
					user.groups.remove(old_name)
					user.groups.append(new_text)
					self.add_user_to_roster(user.jid, account)
					gajim.connections[account].update_user(user.jid, user.name, 
																		user.groups)
		model.set_value(iter, 5, False)
		
	def on_service_disco_menuitem_activate(self, widget, account):
		if self.plugin.windows[account].has_key('disco'):
			self.plugin.windows[account]['disco'].window.present()
		else:
			try:
				self.plugin.windows[account]['disco'] = \
					config.ServiceDiscoveryWindow(self.plugin, account)
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
			for file in files:
				if os.path.exists(file):
					image.set_from_file(file)
					break
		return imgs

	def make_jabber_state_images(self):
		'''initialise jabber_state_images dict'''
		iconset = gajim.config.get('iconset')
		if not iconset:
			iconset = 'sun'
		self.path = os.path.join(gajim.DATA_DIR, 'iconsets/' + iconset + '/16x16/')
		self.jabber_state_images = self.load_iconset(self.path)

	def reload_jabber_state_images(self):
		self.make_jabber_state_images()
		# Update the roster
		self.draw_roster()
		# Update the status combobox
		model = self.status_combobox.get_model()
		iter = model.get_iter_root()
		while iter:
			model.set_value(iter, 1, self.jabber_state_images[model.get_value(iter, 2)])
			iter = model.iter_next(iter)
		# Update the systray
		if self.plugin.systray_enabled:
			self.plugin.systray.set_img()
		for account in gajim.connections:
			# Update opened chat windows
			for jid in self.plugin.windows[account]['chats']:
				if jid != 'tabbed':
					self.plugin.windows[account]['chats'][jid].set_state_image(jid)
			# Update opened groupchat windows
			for jid in self.plugin.windows[account]['gc']:
				if jid != 'tabbed':
					self.plugin.windows[account]['gc'][jid].update_state_images()
		self.update_status_comboxbox()

	def repaint_themed_widgets(self):
		"""Notify windows that contain themed widgets to repaint them"""
		for account in gajim.connections:
			# Update opened chat windows/tabs
			for jid in self.plugin.windows[account]['chats']:
				self.plugin.windows[account]['chats'][jid].repaint_colored_widgets()
			for jid in self.plugin.windows[account]['gc']:
				self.plugin.windows[account]['gc'][jid].repaint_colored_widgets()

	def on_show_offline_contacts_menuitem_activate(self, widget):
		'''when show offline option is changed:
		redraw the treeview'''
		gajim.config.set('showoffline', 1 - gajim.config.get('showoffline'))
		self.draw_roster()

	def iconCellDataFunc(self, column, renderer, model, iter, data = None):
		'''When a row is added, set properties for icon renderer'''
		if model.get_value(iter, 2) == 'account':
			renderer.set_property('cell-background', 
				gajim.config.get('accountbgcolor'))
			renderer.set_property('xalign', 0)
		elif model.get_value(iter, 2) == 'group':
			renderer.set_property('cell-background', 
				gajim.config.get('groupbgcolor'))
			renderer.set_property('xalign', 0.5)
		else:
			jid = model.get_value(iter, 3)
			account = model.get_value(iter, 4)
			if jid in self.newly_added[account]:
				renderer.set_property('cell-background', '#adc3c6')
			elif jid in self.to_be_removed[account]:
				renderer.set_property('cell-background', '#ab6161')
			else:
				renderer.set_property('cell-background', 
					gajim.config.get('userbgcolor'))
			renderer.set_property('xalign', 1)
		renderer.set_property('width', 20)
	
	def nameCellDataFunc(self, column, renderer, model, iter, data = None):
		'''When a row is added, set properties for name renderer'''
		if model.get_value(iter, 2) == 'account':
			renderer.set_property('foreground', 
				gajim.config.get('accounttextcolor'))
			renderer.set_property('cell-background', 
				gajim.config.get('accountbgcolor'))
			renderer.set_property('font', gajim.config.get('accountfont'))
			renderer.set_property('xpad', 0)
		elif model.get_value(iter, 2) == 'group':
			renderer.set_property('foreground', 
				gajim.config.get('grouptextcolor'))
			renderer.set_property('cell-background', 
				gajim.config.get('groupbgcolor'))
			renderer.set_property('font', gajim.config.get('groupfont'))
			renderer.set_property('xpad', 4)
		else:
			jid = model.get_value(iter, 3)
			account = model.get_value(iter, 4)
			renderer.set_property('foreground', 
				gajim.config.get('usertextcolor'))
			if jid in self.newly_added[account]:
				renderer.set_property('cell-background', '#adc3c6')
			elif jid in self.to_be_removed[account]:
				renderer.set_property('cell-background', '#ab6161')
			else:
				renderer.set_property('cell-background', 
					gajim.config.get('userbgcolor'))
			renderer.set_property('font', gajim.config.get('userfont'))
			renderer.set_property('xpad', 8)

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
		type1 = model.get_value(iter1, 2)
		type2 = model.get_value(iter2, 2)
		if type1 == 'group':
			if name1 == 'Transports':
				return 1
			if name2 == 'Transports':
				return -1
			if name1 == 'not in the roster':
				return 1
			if name2 == 'not in the roster':
				return -1
		if type1 == 'user' and type2 == 'user' and \
				gajim.config.get('sort_by_show'):
			account = model.get_value(iter1, 4)
			if account and model.get_value(iter2, 4) == account:
				jid1 = model.get_value(iter1, 3)
				jid2 = model.get_value(iter2, 3)
				luser1 = self.contacts[account][jid1]
				luser2 = self.contacts[account][jid2]
				cshow = {'online':0, 'chat': 1, 'away':2, 'xa':3, 'dnd':4,
					'invisible':5, 'offline':6, 'not in the roster':7, 'error':8}
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
		if len(path) == 3:
			data = model.get_value(iter, 3)
		selection.set(selection.target, 8, data)

	def drag_data_received_data(self, treeview, context, x, y, selection, info,
		etime):
		merge = 0
		if gajim.config.get('mergeaccounts'):
			merge = 1
		model = treeview.get_model()
		data = selection.data
		if not data:
			return
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
		grp_source = model.get_value(iter_group_source, 3)
		if grp_source == 'Transports' or grp_source == 'not in the roster':
			return
		account = model.get_value(iter_dest, 4)
		type_dest = model.get_value(iter_dest, 2)
		if type_dest == 'group':
			grp_dest = model.get_value(iter_dest, 3)
		else:
			grp_dest = model.get_value(model.iter_parent(iter_dest), 3)
		if grp_source == grp_dest:
			return
		# We upgrade only the first user because user2.groups is a pointer to
		# user1.groups
		u = self.contacts[account][data][0]
		u.groups.remove(grp_source)
		if model.iter_n_children(iter_group_source) == 1: #this was the only child
			model.remove(iter_group_source)
		#delete the group if it is empty (need to look for offline users too)
		group_empty = True
		for jid in self.contacts[account]:
			if grp_source in self.contacts[account][jid][0].groups:
				group_empty = False
				break
		if group_empty:
			del self.groups[account][grp_source]
		if not grp_dest in u.groups:
			u.groups.append(grp_dest)
			self.add_user_to_roster(data, account)
		gajim.connections[account].update_user(u.jid, u.name, u.groups)
		if context.action == gtk.gdk.ACTION_MOVE:
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

	def __init__(self, plugin):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'roster_window', APP)
		self.window = self.xml.get_widget('roster_window')
		self.tree = self.xml.get_widget('roster_treeview')
		self.plugin = plugin
		self.nb_unread = 0
		self.add_new_contact_handler_id = False
		self.service_disco_handler_id = False
		self.new_message_menuitem_handler_id = False
		self.regroup = 0
		self.regroup = gajim.config.get('mergeaccounts')
		if gajim.config.get('saveposition'):
			self.window.move(gajim.config.get('x-position'), \
				gajim.config.get('y-position'))
			self.window.resize(gajim.config.get('width'), \
				gajim.config.get('height'))
		
		if gajim.config.get('show_roster_on_startup'):
			self.window.show_all()
		else:
			if not gajim.config.get('trayicon'):
				# cannot happen via GUI, but I put this incase user touches config
				self.window.show_all() # without trayicon, he should see the roster!
				gajim.config.set('show_roster_on_startup', True)
			
		self.groups = {}
		self.contacts = {}
		self.newly_added = {}
		self.to_be_removed = {}
		self.popups_notification_height = 0
		self.popup_notification_windows = []
		self.gpg_passphrase = {}
		for a in gajim.connections:
			self.contacts[a] = {}
			self.groups[a] = {}
			self.newly_added[a] = []
			self.to_be_removed[a] = []
		#(icon, name, type, jid, account, editable)
		model = gtk.TreeStore(gtk.Image, str, str, str, str, gobject.TYPE_BOOLEAN)
		model.set_sort_func(1, self.compareIters)
		model.set_sort_column_id(1, gtk.SORT_ASCENDING)
		self.tree.set_model(model)
		self.make_jabber_state_images()
		self.transports_state_images = { 'aim': {}, 'gadugadu': {}, 'irc': {}, 'icq': {}, 'msn': {}, 'sms': {}, 'yahoo': {} }
		
		path = os.path.join(gajim.DATA_DIR, 'iconsets/transports')
		folders = os.listdir(path)
		for transport in folders:
			if transport == '.svn':
				continue
			folder = os.path.join(path, transport)
			self.transports_state_images[transport] = self.load_iconset(folder + \
				'/16x16/')

		liststore = gtk.ListStore(gobject.TYPE_STRING, gtk.Image, 
			gobject.TYPE_STRING)
		self.status_combobox = gtk.ComboBox()
		roster_vbox = self.xml.get_widget('roster_vbox')
		roster_vbox.pack_end(self.status_combobox, False)
		cell = cell_renderer_image.CellRendererImage()
		self.status_combobox.pack_start(cell, False)
		self.status_combobox.add_attribute(cell, 'image', 1)
		cell = gtk.CellRendererText()
		cell.set_property('xpad', 5) # padding for status text
		self.status_combobox.pack_start(cell, True)
		self.status_combobox.add_attribute(cell, 'text', 0)

		for show in ['online', 'chat', 'away', 'xa', 'dnd', 'invisible',
			'offline']:
			uf_show = helpers.get_uf_show(show)
			iter = liststore.append([uf_show, self.jabber_state_images[show],
				show])
		self.status_combobox.show_all()
		self.status_combobox.set_model(liststore)
		self.status_combobox.set_active(6) # default to offline

		showOffline = gajim.config.get('showoffline')
		self.xml.get_widget('show_offline_contacts_menuitem').set_active(showOffline)

		#columns
		
		#this col has two cells: first one img, second one text
		col = gtk.TreeViewColumn()
		render_pixbuf = cell_renderer_image.CellRendererImage()
		col.pack_start(render_pixbuf, expand = False)
		col.add_attribute(render_pixbuf, 'image', 0)
		col.set_cell_data_func(render_pixbuf, self.iconCellDataFunc, None)

		render_text = gtk.CellRendererText()
		render_text.connect('edited', self.on_cell_edited)
		render_text.connect('editing-canceled', self.on_editing_canceled)
		col.pack_start(render_text, expand = True)
		col.add_attribute(render_text, 'text', 1)
		col.add_attribute(render_text, 'editable', 5)
		col.set_cell_data_func(render_text, self.nameCellDataFunc, None)
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
			gtk.gdk.ACTION_DEFAULT| gtk.gdk.ACTION_MOVE)
		self.tree.enable_model_drag_dest(TARGETS, gtk.gdk.ACTION_DEFAULT)
		self.tree.connect('drag_data_get', self.drag_data_get_data)
		self.tree.connect('drag_data_received', self.drag_data_received_data)
		self.xml.signal_autoconnect(self)
		self.id_signal_cb = self.status_combobox.connect('changed',
			self.on_status_combobox_changed)

		self.collapsed_rows = gajim.config.get('collapsed_rows').split('\t')
		self.draw_roster()
		if len(gajim.connections) == 0: # if no account
			self.plugin.windows['account_modification'] = \
				config.AccountModificationWindow(self.plugin)
