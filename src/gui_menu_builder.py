# -*- coding:utf-8 -*-
## src/gui_menu_builder.py
##
## Copyright (C) 2009 Yann Leboulanger <asterix AT lagaule.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import gtk
import os
import gtkgui_helpers
import message_control

from common import gajim
from common import helpers
from common.xmpp.protocol import NS_COMMANDS, NS_FILE, NS_MUC, NS_ESESSION

def build_resources_submenu(contacts, account, action, room_jid=None,
room_account=None, cap=None):
	''' Build a submenu with contact's resources.
	room_jid and room_account are for action self.on_invite_to_room '''
	roster = gajim.interface.roster
	sub_menu = gtk.Menu()

	iconset = gajim.config.get('iconset')
	if not iconset:
		iconset = gajim.config.DEFAULT_ICONSET
	path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
	for c in contacts:
		# icon MUST be different instance for every item
		state_images = gtkgui_helpers.load_iconset(path)
		item = gtk.ImageMenuItem('%s (%s)' % (c.resource, str(c.priority)))
		icon_name = helpers.get_icon_name_to_show(c, account)
		icon = state_images[icon_name]
		item.set_image(icon)
		sub_menu.append(item)
		
		if action == roster.on_invite_to_room:
			item.connect('activate', action, [(c, account)], room_jid,
				room_account, c.resource)
		elif action == roster.on_invite_to_new_room:
			item.connect('activate', action, [(c, account)], c.resource)
		else: # start_chat, execute_command, send_file
			item.connect('activate', action, c, account, c.resource)

		if cap and not c.supports(cap):
			item.set_sensitive(False)

	return sub_menu

def build_invite_submenu(invite_menuitem, list_):
	'''list_ in a list of (contact, account)'''
	roster = gajim.interface.roster
	# used if we invite only one contact with several resources
	contact_list = []
	if len(list_) == 1:
		contact, account = list_[0]
		contact_list = gajim.contacts.get_contacts(account, contact.jid)
	contacts_transport = -1
	connected_accounts = []
	# -1 is at start, False when not from the same, None when jabber
	for (contact, account) in list_:
		if not account in connected_accounts:
			connected_accounts.append(account)
		transport = gajim.get_transport_name_from_jid(contact.jid)
		if contacts_transport == -1:
			contacts_transport = transport
		elif contacts_transport != transport:
			contacts_transport = False

	if contacts_transport == False:
		# they are not all from the same transport
		invite_menuitem.set_sensitive(False)
		return
	invite_to_submenu = gtk.Menu()
	invite_menuitem.set_submenu(invite_to_submenu)
	invite_to_new_room_menuitem = gtk.ImageMenuItem(_('_New Group Chat'))
	icon = gtk.image_new_from_stock(gtk.STOCK_NEW, gtk.ICON_SIZE_MENU)
	invite_to_new_room_menuitem.set_image(icon)
	if len(contact_list) > 1: # several resources
		invite_to_new_room_menuitem.set_submenu(build_resources_submenu(
			contact_list, account, roster.on_invite_to_new_room, cap=NS_MUC))
	elif len(list_) == 1 and contact.supports(NS_MUC):
		invite_menuitem.set_sensitive(True)
		# use resource if it's self contact
		if contact.jid == gajim.get_jid_from_account(account):
			resource = contact.resource
		else:
			resource = None
		invite_to_new_room_menuitem.connect('activate',
			roster.on_invite_to_new_room, list_, resource)
	else:
		invite_menuitem.set_sensitive(False)
	# transform None in 'jabber'
	c_t = contacts_transport or 'jabber'
	muc_jid = {}
	for account in connected_accounts:
		for t in gajim.connections[account].muc_jid:
			muc_jid[t] = gajim.connections[account].muc_jid[t]
	if c_t not in muc_jid:
		invite_to_new_room_menuitem.set_sensitive(False)
	rooms = [] # a list of (room_jid, account) tuple
	invite_to_submenu.append(invite_to_new_room_menuitem)
	rooms = [] # a list of (room_jid, account) tuple
	minimized_controls = []
	for account in connected_accounts:
		minimized_controls += gajim.interface.minimized_controls[account].values()
	for gc_control in gajim.interface.msg_win_mgr.get_controls(
	message_control.TYPE_GC) + minimized_controls:
		acct = gc_control.account
		room_jid = gc_control.room_jid
		if room_jid in gajim.gc_connected[acct] and \
		gajim.gc_connected[acct][room_jid] and \
		contacts_transport == gajim.get_transport_name_from_jid(room_jid):
			rooms.append((room_jid, acct))
	if len(rooms):
		item = gtk.SeparatorMenuItem() # separator
		invite_to_submenu.append(item)
		for (room_jid, account) in rooms:
			menuitem = gtk.MenuItem(room_jid.split('@')[0])
			if len(contact_list) > 1: # several resources
				menuitem.set_submenu(build_resources_submenu(
					contact_list, account, roster.on_invite_to_room, room_jid,
					account))
			else:
				# use resource if it's self contact
				if contact.jid == gajim.get_jid_from_account(account):
					resource = contact.resource
				else:
					resource = None
				menuitem.connect('activate', roster.on_invite_to_room, list_,
					room_jid, account, resource)
			invite_to_submenu.append(menuitem)

def get_contact_menu(contact, account, use_multiple_contacts=True,
show_start_chat=True, show_encryption=False, show_buttonbar_items=True,
control=None):
	''' Build contact popup menu for roster and chat window.
	If control is not set, we hide invite_contacts_menuitem'''
	if not contact:
		return

	jid = contact.jid
	our_jid = jid == gajim.get_jid_from_account(account)
	roster = gajim.interface.roster

	xml = gtkgui_helpers.get_glade('contact_context_menu.glade')
	contact_context_menu = xml.get_widget('contact_context_menu')

	start_chat_menuitem = xml.get_widget('start_chat_menuitem')
	execute_command_menuitem = xml.get_widget('execute_command_menuitem')
	rename_menuitem = xml.get_widget('rename_menuitem')
	edit_groups_menuitem = xml.get_widget('edit_groups_menuitem')
	send_file_menuitem = xml.get_widget('send_file_menuitem')
	assign_openpgp_key_menuitem = xml.get_widget('assign_openpgp_key_menuitem')
	add_special_notification_menuitem = xml.get_widget(
		'add_special_notification_menuitem')
	information_menuitem = xml.get_widget('information_menuitem')
	history_menuitem = xml.get_widget('history_menuitem')
	send_custom_status_menuitem = xml.get_widget('send_custom_status_menuitem')
	send_single_message_menuitem = xml.get_widget('send_single_message_menuitem')
	invite_menuitem = xml.get_widget('invite_menuitem')
	block_menuitem = xml.get_widget('block_menuitem')
	unblock_menuitem = xml.get_widget('unblock_menuitem')
	ignore_menuitem = xml.get_widget('ignore_menuitem')
	unignore_menuitem = xml.get_widget('unignore_menuitem')
	set_custom_avatar_menuitem = xml.get_widget('set_custom_avatar_menuitem')
	# Subscription submenu
	subscription_menuitem = xml.get_widget('subscription_menuitem')
	send_auth_menuitem, ask_auth_menuitem, revoke_auth_menuitem = \
		subscription_menuitem.get_submenu().get_children()
	add_to_roster_menuitem = xml.get_widget('add_to_roster_menuitem')
	remove_from_roster_menuitem = xml.get_widget(
		'remove_from_roster_menuitem')
	manage_contact_menuitem = xml.get_widget('manage_contact')
	convert_to_gc_menuitem = xml.get_widget('convert_to_groupchat_menuitem')
	encryption_separator = xml.get_widget('encryption_separator')
	toggle_gpg_menuitem = xml.get_widget('toggle_gpg_menuitem')
	toggle_e2e_menuitem = xml.get_widget('toggle_e2e_menuitem')
	last_separator = xml.get_widget('last_separator')

	items_to_hide = []

	# add a special img for send file menuitem
	path_to_upload_img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'upload.png')
	img = gtk.Image()
	img.set_from_file(path_to_upload_img)
	send_file_menuitem.set_image(img)

	if not our_jid:
		# add a special img for rename menuitem
		path_to_kbd_input_img = os.path.join(gajim.DATA_DIR, 'pixmaps',
			'kbd_input.png')
		img = gtk.Image()
		img.set_from_file(path_to_kbd_input_img)
		rename_menuitem.set_image(img)

	muc_icon = gtkgui_helpers.load_icon('muc_active')
	if muc_icon:
		convert_to_gc_menuitem.set_image(muc_icon)

	contacts = gajim.contacts.get_contacts(account, jid)
	if len(contacts) > 1 and use_multiple_contacts: # several resources
		start_chat_menuitem.set_submenu(build_resources_submenu(contacts,
			account, gajim.interface.on_open_chat_window))
		send_file_menuitem.set_submenu(build_resources_submenu(contacts,
			account, roster.on_send_file_menuitem_activate, cap=NS_FILE))
		execute_command_menuitem.set_submenu(build_resources_submenu(
			contacts, account, roster.on_execute_command, cap=NS_COMMANDS))
	else:
		start_chat_menuitem.connect('activate',
			gajim.interface.on_open_chat_window, contact, account)
		if contact.supports(NS_FILE):
			send_file_menuitem.set_sensitive(True)
			send_file_menuitem.connect('activate',
				roster.on_send_file_menuitem_activate, contact, account)
		else:
			send_file_menuitem.set_sensitive(False)

		if contact.supports(NS_COMMANDS):
			execute_command_menuitem.set_sensitive(True)
			execute_command_menuitem.connect('activate', roster.on_execute_command,
				contact, account, contact.resource)
		else:
			execute_command_menuitem.set_sensitive(False)

	rename_menuitem.connect('activate', roster.on_rename, 'contact', jid,
		account)
	history_menuitem.connect('activate', roster.on_history, contact, account)

	if control:
		convert_to_gc_menuitem.connect('activate',
			control._on_convert_to_gc_menuitem_activate)
	else:
		items_to_hide.append(convert_to_gc_menuitem)

	if _('Not in Roster') not in contact.get_shown_groups():
		# contact is in normal group
		edit_groups_menuitem.connect('activate', roster.on_edit_groups, [(contact,
			account)])

		if gajim.connections[account].gpg:
			assign_openpgp_key_menuitem.connect('activate',
				roster.on_assign_pgp_key, contact, account)
		else:
			assign_openpgp_key_menuitem.set_sensitive(False)
	else:
		# contact is in group 'Not in Roster'
		edit_groups_menuitem.set_sensitive(False)
		assign_openpgp_key_menuitem.set_sensitive(False)

	# Hide items when it's self contact row
	if our_jid:
		items_to_hide += [rename_menuitem, edit_groups_menuitem]

	# Unsensitive many items when account is offline
	if gajim.account_is_disconnected(account):
		for widget in (start_chat_menuitem,	rename_menuitem,
		edit_groups_menuitem, send_file_menuitem, convert_to_gc_menuitem):
			widget.set_sensitive(False)

	if not show_start_chat:
		items_to_hide.append(start_chat_menuitem)

	if not show_encryption or not control:
		items_to_hide += [encryption_separator, toggle_gpg_menuitem,
			toggle_e2e_menuitem]
	else:
		e2e_is_active = control.session is not None and \
			control.session.enable_encryption

		# check if we support and use gpg
		if not gajim.config.get_per('accounts', account, 'keyid') or \
		not gajim.connections[account].USE_GPG or gajim.jid_is_transport(
		contact.jid):
			toggle_gpg_menuitem.set_sensitive(False)
		else:
			toggle_gpg_menuitem.set_sensitive(control.gpg_is_active or \
				not e2e_is_active)
			toggle_gpg_menuitem.set_active(control.gpg_is_active)
			toggle_gpg_menuitem.connect('activate',
				control._on_toggle_gpg_menuitem_activate)

		# disable esessions if we or the other client don't support them
		if not gajim.HAVE_PYCRYPTO or not contact.supports(NS_ESESSION) or \
		not gajim.config.get_per('accounts', account, 'enable_esessions'):
			toggle_e2e_menuitem.set_sensitive(False)
		else:
			toggle_e2e_menuitem.set_active(e2e_is_active)
			toggle_e2e_menuitem.set_sensitive(e2e_is_active or \
				not control.gpg_is_active)
			toggle_e2e_menuitem.connect('activate',
				control._on_toggle_e2e_menuitem_activate)

	if not show_buttonbar_items:
		items_to_hide += [history_menuitem, send_file_menuitem,
			information_menuitem, convert_to_gc_menuitem, last_separator]
	
	if not control:
		items_to_hide.append(convert_to_gc_menuitem)

	for item in items_to_hide:
		item.set_no_show_all(True)
		item.hide()

	# Zeroconf Account
	if gajim.config.get_per('accounts', account, 'is_zeroconf'):
		for item in (send_custom_status_menuitem, send_single_message_menuitem,
		invite_menuitem, block_menuitem, unblock_menuitem, ignore_menuitem,
		unignore_menuitem, set_custom_avatar_menuitem, subscription_menuitem,
		manage_contact_menuitem, convert_to_gc_menuitems):
			item.set_no_show_all(True)
			item.hide()

		if contact.show in ('offline', 'error'):
			information_menuitem.set_sensitive(False)
			send_file_menuitem.set_sensitive(False)
		else:
			information_menuitem.connect('activate', roster.on_info_zeroconf,
				contact, account)

		contact_context_menu.connect('selection-done',
			gtkgui_helpers.destroy_widget)
		contact_context_menu.show_all()
		return contact_context_menu

	# normal account

	# send custom status icon
	blocked = False
	if helpers.jid_is_blocked(account, jid):
		blocked = True
	else:
		for group in contact.get_shown_groups():
			if helpers.group_is_blocked(account, group):
				blocked = True
				break
	if gajim.get_transport_name_from_jid(jid, use_config_setting=False):
		# Transport contact, send custom status unavailable
		send_custom_status_menuitem.set_sensitive(False)
	elif blocked:
		send_custom_status_menuitem.set_image(gtkgui_helpers.load_icon('offline'))
		send_custom_status_menuitem.set_sensitive(False)
	elif account in gajim.interface.status_sent_to_users and \
	jid in gajim.interface.status_sent_to_users[account]:
		send_custom_status_menuitem.set_image(gtkgui_helpers.load_icon(
			gajim.interface.status_sent_to_users[account][jid]))
	else:
		icon = gtk.image_new_from_stock(gtk.STOCK_NETWORK, gtk.ICON_SIZE_MENU)
		send_custom_status_menuitem.set_image(icon)

	muc_icon = gtkgui_helpers.load_icon('muc_active')
	if muc_icon:
		invite_menuitem.set_image(muc_icon)

	build_invite_submenu(invite_menuitem, [(contact, account)])

	# One or several resource, we do the same for send_custom_status
	status_menuitems = gtk.Menu()
	send_custom_status_menuitem.set_submenu(status_menuitems)
	iconset = gajim.config.get('iconset')
	path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
	for s in ('online', 'chat', 'away', 'xa', 'dnd', 'offline'):
		# icon MUST be different instance for every item
		state_images = gtkgui_helpers.load_iconset(path)
		status_menuitem = gtk.ImageMenuItem(helpers.get_uf_show(s))
		status_menuitem.connect('activate', roster.on_send_custom_status,
			[(contact, account)], s)
		icon = state_images[s]
		status_menuitem.set_image(icon)
		status_menuitems.append(status_menuitem)

	send_single_message_menuitem.connect('activate',
		roster.on_send_single_message_menuitem_activate, account, contact)

	remove_from_roster_menuitem.connect('activate', roster.on_req_usub,
		[(contact, account)])
	information_menuitem.connect('activate', roster.on_info, contact, account)

	if _('Not in Roster') not in contact.get_shown_groups():
		# contact is in normal group
		add_to_roster_menuitem.hide()
		add_to_roster_menuitem.set_no_show_all(True)

		if contact.sub in ('from', 'both'):
			send_auth_menuitem.set_sensitive(False)
		else:
			send_auth_menuitem.connect('activate', roster.authorize, jid, account)
		if contact.sub in ('to', 'both'):
			ask_auth_menuitem.set_sensitive(False)
			add_special_notification_menuitem.connect('activate',
				roster.on_add_special_notification_menuitem_activate, jid)
		else:
			ask_auth_menuitem.connect('activate', roster.req_sub, jid,
				_('I would like to add you to my roster'), account,
				contact.groups, contact.name)
		if contact.sub in ('to', 'none') or gajim.get_transport_name_from_jid(
			jid, use_config_setting=False):
			revoke_auth_menuitem.set_sensitive(False)
		else:
			revoke_auth_menuitem.connect('activate', roster.revoke_auth, jid,
				account)

	else:
		# contact is in group 'Not in Roster'
		add_to_roster_menuitem.set_no_show_all(False)
		subscription_menuitem.set_sensitive(False)

		add_to_roster_menuitem.connect('activate', roster.on_add_to_roster,
			contact, account)

	set_custom_avatar_menuitem.connect('activate',
		roster.on_set_custom_avatar_activate, contact, account)

	# Hide items when it's self contact row
	if our_jid:
		manage_contact_menuitem.set_sensitive(False)

	# Unsensitive items when account is offline
	if gajim.account_is_disconnected(account):
		for widget in (send_single_message_menuitem, subscription_menuitem,
		add_to_roster_menuitem, remove_from_roster_menuitem,
		execute_command_menuitem, send_custom_status_menuitem):
			widget.set_sensitive(False)

	if gajim.connections[account] and gajim.connections[account].\
	privacy_rules_supported:
		if helpers.jid_is_blocked(account, jid):
			block_menuitem.set_no_show_all(True)
			block_menuitem.hide()
			if gajim.get_transport_name_from_jid(jid, use_config_setting=False):
				unblock_menuitem.set_no_show_all(True)
				unblock_menuitem.hide()
				unignore_menuitem.set_no_show_all(False)
				unignore_menuitem.connect('activate', roster.on_unblock, [(contact,
					account)])
			else:
				unblock_menuitem.connect('activate', roster.on_unblock, [(contact,
					account)])
		else:
			unblock_menuitem.set_no_show_all(True)
			unblock_menuitem.hide()
			if gajim.get_transport_name_from_jid(jid, use_config_setting=False):
				block_menuitem.set_no_show_all(True)
				block_menuitem.hide()
				ignore_menuitem.set_no_show_all(False)
				ignore_menuitem.connect('activate', roster.on_block, [(contact,
					account)])
			else:
				block_menuitem.connect('activate', roster.on_block, [(contact,
					account)])
	else:
		unblock_menuitem.set_no_show_all(True)
		block_menuitem.set_sensitive(False)
		unblock_menuitem.hide()

	contact_context_menu.connect('selection-done', gtkgui_helpers.destroy_widget)
	contact_context_menu.show_all()
	return contact_context_menu

# vim: se ts=3:
