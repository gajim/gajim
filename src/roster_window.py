# -*- coding: utf-8 -*-
##	roster_window.py
##
## Copyright (C) 2003-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov@gmail.com>
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
import pango
import gobject
import os
import time
import urllib

import common.sleepy
import history_window
import dialogs
import vcard
import config
import disco
import gtkgui_helpers
import cell_renderer_image
import tooltips
import message_control
import adhoc_commands
import notify

from common import gajim
from common import helpers
from common import passwords
from common.exceptions import GajimGeneralException
from common import i18n

from message_window import MessageWindowMgr
from chat_control import ChatControl
from groupchat_control import GroupchatControl
from groupchat_control import PrivateChatControl

from common import dbus_support
if dbus_support.supported:
	from music_track_listener import MusicTrackListener
	import dbus

#(icon, name, type, jid, account, editable, second pixbuf)
(
C_IMG, # image to show state (online, new message etc)
C_NAME, # cellrenderer text that holds contact nickame
C_TYPE, # account, group or contact?
C_JID, # the jid of the row
C_ACCOUNT, # cellrenderer text that holds account name
C_SECPIXBUF, # secondary_pixbuf (holds avatar or padlock)
) = range(6)

class RosterWindow:
	'''Class for main window of the GTK+ interface'''

	def get_account_iter(self, name):
		model = self.tree.get_model()
		if model is None:
			return
		account_iter = model.get_iter_root()
		if self.regroup:
			return account_iter
		while account_iter:
			account_name = model[account_iter][C_ACCOUNT].decode('utf-8')
			if name == account_name:
				break
			account_iter = model.iter_next(account_iter)
		return account_iter

	def get_group_iter(self, name, account):
		model = self.tree.get_model()
		root = self.get_account_iter(account)
		group_iter = model.iter_children(root)
		# C_NAME column contacts the pango escaped group name
		while group_iter:
			group_name = model[group_iter][C_JID].decode('utf-8')
			if name == group_name:
				break
			group_iter = model.iter_next(group_iter)
		return group_iter

	def get_contact_iter(self, jid, account):
		if jid == gajim.get_jid_from_account(account):
			iter = self.get_self_contact_iter(account)
			if iter:
				return [iter]
			else:
				return []
		model = self.tree.get_model()
		acct = self.get_account_iter(account)
		found = []
		if model is None: # when closing Gajim model can be none (async pbs?)
			return found
		group_iter = model.iter_children(acct)
		while group_iter:
			contact_iter = model.iter_children(group_iter)
			while contact_iter:
				if jid == model[contact_iter][C_JID].decode('utf-8') and \
					account == model[contact_iter][C_ACCOUNT].decode('utf-8'):
					found.append(contact_iter)
				# find next contact iter
				if model.iter_has_child(contact_iter):
					# his first child if it has some
					contact_iter = model.iter_children(contact_iter)
				else:
					next_contact_iter = model.iter_next(contact_iter)
					if not next_contact_iter:
						# now we need to go up
						parent_iter = model.iter_parent(contact_iter)
						parent_type = model[parent_iter][C_TYPE]
						while parent_type != 'group':
							contact_iter = model.iter_next(parent_iter)
							if contact_iter:
								break
							else:
								parent_iter = model.iter_parent(parent_iter)
								parent_type = model[parent_iter][C_TYPE]
						else:
							# we tested all contacts in this group
							contact_iter = None
					else:
						# his brother if he has
						contact_iter = next_contact_iter
			group_iter = model.iter_next(group_iter)
		return found

	def get_path(self, jid, account):
		''' Try to get line of contact in roster	'''
		iters = self.get_contact_iter(jid, account)
		if iters:
			path = self.tree.get_model().get_path(iters[0])
		else:
			path = None
		return path

	def show_and_select_path(self, path, jid, account):
		'''Show contact in roster (if he is invisible for example)
		and select line'''
		if not path:
			# contact is in roster but we curently don't see him online
			# show him
			self.add_contact_to_roster(jid, account)
			iters = self.get_contact_iter(jid, account)
			path = self.tree.get_model().get_path(iters[0])
		if self.dragging or not gajim.config.get('scroll_roster_to_last_message'):
			# do not change selection while DND'ing
			return
		# popup == False so we show awaiting event in roster
		# show and select contact line in roster (even if he is not in roster)
		self.tree.expand_row(path[0:1], False)
		self.tree.expand_row(path[0:2], False)
		self.tree.scroll_to_cell(path)
		self.tree.set_cursor(path)

	def add_account_to_roster(self, account):
		model = self.tree.get_model()
		if self.get_account_iter(account):
			return

		if self.regroup:
			show = helpers.get_global_show()
			model.append(None, [self.jabber_state_images['16'][show],
				_('Merged accounts'), 'account', '', 'all', None])
			self.draw_account(account)
			return

		show = gajim.SHOW_LIST[gajim.connections[account].connected]

		tls_pixbuf = None
		if gajim.account_is_securely_connected(account):
			tls_pixbuf = self.window.render_icon(gtk.STOCK_DIALOG_AUTHENTICATION,
				gtk.ICON_SIZE_MENU) # the only way to create a pixbuf from stock

		our_jid = gajim.get_jid_from_account(account)

		model.append(None, [self.jabber_state_images['16'][show],
			gobject.markup_escape_text(account),
			'account', our_jid, account, tls_pixbuf])

	def draw_account(self, account):
		model = self.tree.get_model()
		iter = self.get_account_iter(account)
		if self.regroup:
			accounts = gajim.connections.keys()
		else:
			accounts = [account]
		num_of_accounts = len(accounts)
		num_of_secured = gajim.get_number_of_securely_connected_accounts()
		if num_of_secured and gajim.con_types.has_key(account) and \
		gajim.con_types[account] in ('tls', 'ssl'):
			tls_pixbuf = self.window.render_icon(gtk.STOCK_DIALOG_AUTHENTICATION,
				gtk.ICON_SIZE_MENU) # the only way to create a pixbuf from stock
			if num_of_secured < num_of_accounts:
				# Make it transparent
				colorspace = tls_pixbuf.get_colorspace()
				bps = tls_pixbuf.get_bits_per_sample()
				rowstride = tls_pixbuf.get_rowstride()
				pixels = tls_pixbuf.get_pixels()
				new_pixels = ''
				width = tls_pixbuf.get_width()
				height = tls_pixbuf.get_height()
				for i in range(0, width*height):
					rgb = pixels[4*i:4*i+3]
					new_pixels += rgb
					if rgb == chr(0)*3:
						new_pixels += chr(0)
					else:
						new_pixels += chr(128)
				tls_pixbuf = gtk.gdk.pixbuf_new_from_data(new_pixels, colorspace,
					True, bps, width, height, rowstride)
			model[iter][C_SECPIXBUF] = tls_pixbuf
		else:
			model[iter][C_SECPIXBUF] = None
		path = model.get_path(iter)
		account_name = account
		accounts = [account]
		if self.regroup:
			account_name = _('Merged accounts')
			accounts = []
		if not self.tree.row_expanded(path) and model.iter_has_child(iter):
			# account row not expanded
			account_name = '[%s]' % account_name
		if (gajim.account_is_connected(account) or (self.regroup and \
		gajim.get_number_of_connected_accounts())) and gajim.config.get(
		'show_contacts_number'):
			nbr_on, nbr_total = gajim.contacts.get_nb_online_total_contacts(
				accounts = accounts)
			account_name += ' (%s/%s)' % (repr(nbr_on),repr(nbr_total))
		model[iter][C_NAME] = account_name

	def remove_newly_added(self, jid, account):
		if jid in gajim.newly_added[account]:
			gajim.newly_added[account].remove(jid)
			self.draw_contact(jid, account)

	def add_contact_to_roster(self, jid, account):
		'''Add a contact to the roster and add groups if they aren't in roster
		force is about force to add it, even if it is offline and show offline
		is False, because it has online children, so we need to show it.
		If add_children is True, we also add all children, even if they were not
		already drawn'''
		showOffline = gajim.config.get('showoffline')
		model = self.tree.get_model()
		contact = gajim.contacts.get_first_contact_from_jid(account, jid)
		nb_events = gajim.events.get_nb_roster_events(account, contact.jid)
		# count events from all resources
		for contact_ in gajim.contacts.get_contact(account, jid):
			if contact_.resource:
				nb_events += gajim.events.get_nb_roster_events(account,
					contact_.get_full_jid())
		if not contact:
			return
		# If contact already in roster, do not add it
		if len(self.get_contact_iter(jid, account)):
			return
		if jid == gajim.get_jid_from_account(account):
			self.add_self_contact(account)
			return
		if gajim.jid_is_transport(contact.jid):
			# if jid is transport, check if we wanna show it in roster
			if not gajim.config.get('show_transports_group') and not nb_events:
				return
			contact.groups = [_('Transports')]
		elif not showOffline and not gajim.account_is_connected(account) and \
		nb_events == 0:
			return

		# XEP-0162
		hide = contact.is_hidden_from_roster()
		if hide and contact.sub != 'from':
			return
		observer = contact.is_observer()
		groupchat = contact.is_groupchat()

		if observer:
			# if he has a tag, remove it
			tag = gajim.contacts.get_metacontacts_tag(account, jid)
			if tag:
				gajim.contacts.remove_metacontact(account, jid)

		# family is [{'account': acct, 'jid': jid, 'priority': prio}, ]
		# 'priority' is optional
		family = gajim.contacts.get_metacontacts_family(account, jid)

		# family members that are in roster and belong to the same account.
		shown_family = []
		if family:
			for data in family:
				_account = data['account']
				# Metacontacts over different accounts only in merged mode
				if _account != account and not self.regroup:
					continue
				_jid = data['jid']

				if self.get_contact_iter(_jid, _account):
					shown_family.append(data)
				if _jid == jid and _account == account:
					our_data = data
			shown_family.append(our_data)
			big_brother_data = gajim.contacts.get_metacontacts_big_brother(
				shown_family)
			big_brother_jid = big_brother_data['jid']
			big_brother_account = big_brother_data['account']
			if big_brother_jid != jid or big_brother_account != account:
				# We are adding a child contact
				if contact.show in ('offline', 'error') and \
				not showOffline and len(gajim.events.get_events(account, jid)) == 0:
					return
				parent_iters = self.get_contact_iter(big_brother_jid,
					big_brother_account)
				name = contact.get_shown_name()
				for i in parent_iters:
					# we add some values here. see draw_contact for more
					model.append(i, (None, name, 'contact', jid, account, None))
				self.draw_contact(jid, account)
				self.draw_avatar(jid, account)
				# Redraw parent to change icon
				self.draw_contact(big_brother_jid, big_brother_account)
				return

		if (contact.show in ('offline', 'error') or hide) and \
		not showOffline and (not _('Transports') in contact.groups or \
		gajim.connections[account].connected < 2) and \
		len(gajim.contacts.get_contact(account, jid)) == 1 and nb_events == 0 and\
		not _('Not in Roster') in contact.groups:
			return

		# Remove brother contacts that are already in roster to add them
		# under this iter
		for data in shown_family:
			contacts = gajim.contacts.get_contact(data['account'],
				data['jid'])
			for c in contacts:
				self.remove_contact(c, data['account'])
		groups = contact.groups
		if observer:
			groups = [_('Observers')]
		elif not groups:
			groups = [_('General')]
		for group in groups:
			iterG = self.get_group_iter(group, account)
			if not iterG:
				IterAcct = self.get_account_iter(account)
				iterG = model.append(IterAcct, [
					self.jabber_state_images['16']['closed'],
					gobject.markup_escape_text(group), 'group',
					group, account, None])
				self.draw_group(group, account)
				if model.iter_n_children(IterAcct) == 1: # We added the first one
					self.draw_account(account)
			if group not in gajim.groups[account]: # It can probably never append
				if account + group in self.collapsed_rows:
					ishidden = False
				else:
					ishidden = True
				gajim.groups[account][group] = {'expand': ishidden}
			if not account in self.collapsed_rows:
				self.tree.expand_row((model.get_path(iterG)[0]), False)

			typestr = 'contact'
			if group == _('Transports'):
				typestr = 'agent'
			if gajim.gc_connected[account].has_key(jid):
				typestr = 'groupchat'

			name = contact.get_shown_name()
			# we add some values here. see draw_contact for more
			model.append(iterG, (None, name, typestr, contact.jid, account, None))

			if gajim.groups[account][group]['expand']:
				self.tree.expand_row(model.get_path(iterG), False)
		self.draw_contact(jid, account)
		self.draw_avatar(jid, account)
		# put the children under this iter
		for data in shown_family:
			contacts = gajim.contacts.get_contact(data['account'],
				data['jid'])
			self.add_contact_to_roster(data['jid'], data['account'])

	def draw_group(self, group, account):
		iter = self.get_group_iter(group, account)
		if not iter:
			return
		if self.regroup:
			accounts = []
		else:
			accounts = [account]
		text = gobject.markup_escape_text(group)
		if group in gajim.connections[account].blocked_groups:
			text = '<span strikethrough="true">%s</span>' % text
		if gajim.config.get('show_contacts_number'):
			nbr_on, nbr_total = gajim.contacts.get_nb_online_total_contacts(
				accounts = accounts, groups = [group])
			text += ' (%s/%s)' % (repr(nbr_on), repr(nbr_total))
		model = self.tree.get_model()
		model.set_value(iter, 1 , text)

	def add_to_not_in_the_roster(self, account, jid, nick = '', resource = ''):
		''' add jid to group "not in the roster", he MUST not be in roster yet,
		return contact '''
		keyID = ''
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		if jid in attached_keys:
			keyID = attached_keys[attached_keys.index(jid) + 1]
		contact = gajim.contacts.create_contact(jid = jid, name = nick,
			groups = [_('Not in Roster')], show = 'not in roster', status = '',
			sub = 'none', resource = resource, keyID = keyID)
		gajim.contacts.add_contact(account, contact)
		self.add_contact_to_roster(contact.jid, account)
		return contact

	def add_groupchat_to_roster(self, account, jid, nick = '', resource = '',
		status = ''):
		''' add groupchat to roster '''
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if contact == None:
			contact = gajim.contacts.create_contact(jid = jid, name = jid,
				groups = [_('Groupchats')], show = 'online',
				status = status, sub = 'none',
				resource = resource)
			gajim.contacts.add_contact(account, contact)
			self.add_contact_to_roster(jid, account)
			self.draw_group(_('Groupchats'), account)
		else:
			contact.show = 'online'
			self.draw_contact(jid, account)
			self.add_contact_to_roster(jid, account)
			for group in contact.groups:
				self.draw_group(group, account)
		return contact

	def get_self_contact_iter(self, account):
		model = self.tree.get_model()
		iterAcct = self.get_account_iter(account)
		iter = model.iter_children(iterAcct)
		if not iter:
			return None
		if model[iter][C_TYPE] == 'self_contact':
			return iter
		return None

	def add_self_contact(self, account):
		jid = gajim.get_jid_from_account(account)
		if self.get_self_contact_iter(account):
			self.draw_contact(jid, account)
			self.draw_avatar(jid, account)
			return

		contact = gajim.contacts.get_first_contact_from_jid(account, jid)
		if not contact:
			return
		showOffline = gajim.config.get('showoffline')
		if (contact.show in ('offline', 'error')) and not showOffline and \
			len(gajim.events.get_events(account, jid)) == 0:
			return

		model = self.tree.get_model()
		iterAcct = self.get_account_iter(account)
		model.append(iterAcct, (None, gajim.nicks[account], 'self_contact', jid,
			account, None))
		self.draw_contact(jid, account)
		self.draw_avatar(jid, account)

	def add_transport_to_roster(self, account, transport):
		c = gajim.contacts.create_contact(jid = transport, name = transport,
			groups = [_('Transports')], show = 'offline', status = 'offline',
			sub = 'from')
		gajim.contacts.add_contact(account, c)
		self.add_contact_to_roster(transport, account)

	def really_remove_contact(self, contact, account):
		if not gajim.interface.instances.has_key(account):
			# Account has been deleted during the timeout that called us
			return
		if contact.jid in gajim.newly_added[account]:
			return
		if gajim.jid_is_transport(contact.jid) and gajim.account_is_connected(
		account) and gajim.config.get('show_transports_group'):
			# It's an agent and we show them
			return
		if contact.jid in gajim.to_be_removed[account]:
			gajim.to_be_removed[account].remove(contact.jid)


		hide = contact.is_hidden_from_roster()

		show_offline = gajim.config.get('showoffline')
		show_transports = gajim.config.get('show_transports_group')

		nb_events = 0
		jid_list = [contact.jid]
		if contact.get_full_jid() != contact.jid:
			jid_list.append(contact.get_full_jid())
		for jid in jid_list:
			# dont't count printed_chat messages
			nb_events += gajim.events.get_nb_roster_events(account, jid, ['chat'])

		if (_('Transports') in contact.groups and not show_transports) or \
		((contact.show in ('offline', 'error') or hide) and not show_offline and \
		(not _('Transports') in contact.groups or \
		gajim.account_is_disconnected(account))) and nb_events == 0:
			self.remove_contact(contact, account)
		else:
			self.draw_contact(contact.jid, account)

	def remove_contact(self, contact, account):
		'''Remove a contact from the roster'''
		if contact.jid in gajim.to_be_removed[account]:
			return
		model = self.tree.get_model()
		iters = self.get_contact_iter(contact.jid, account)
		if not iters:
			return
		parent_iter = model.iter_parent(iters[0])
		parent_type = model[parent_iter][C_TYPE]
		# remember children to re-add them
		children = []
		child_iter = model.iter_children(iters[0])
		while child_iter:
			c_jid = model[child_iter][C_JID].decode('utf-8')
			c_account = model[child_iter][C_ACCOUNT].decode('utf-8')
			children.append((c_jid, c_account))
			child_iter = model.iter_next(child_iter)

		# Remove iters and group iter if they are empty
		for i in iters:
			parent_i = model.iter_parent(i)
			model.remove(i)
			if parent_type == 'group':
				group = model[parent_i][C_JID].decode('utf-8')
				if model.iter_n_children(parent_i) == 0:
					model.remove(parent_i)
					# We need to check all contacts, even offline contacts
					for jid in gajim.contacts.get_jid_list(account):
						if group in gajim.contacts.get_contact_with_highest_priority(
							account, jid).groups:
							break
					else:
						if gajim.groups[account].has_key(group):
							del gajim.groups[account][group]

		# re-add children
		for child in children:
			self.add_contact_to_roster(child[0], child[1])
		# redraw parent
		if parent_type == 'contact':
			parent_jid = model[parent_iter][C_JID].decode('utf-8')
			parent_account = model[parent_iter][C_ACCOUNT].decode('utf-8')
			self.draw_contact(parent_jid, parent_account)

	def get_appropriate_state_images(self, jid, size = '16',
		icon_name = 'online'):
		'''check jid and return the appropriate state images dict for
		the demanded size. icon_name is taken into account when jid is from
		transport: transport iconset doesn't contain all icons, so we fall back
		to jabber one'''
		transport = gajim.get_transport_name_from_jid(jid)
		if transport and self.transports_state_images.has_key(size) and \
		self.transports_state_images[size].has_key(transport) and icon_name in \
		self.transports_state_images[size][transport]:
			return self.transports_state_images[size][transport]
		return self.jabber_state_images[size]

	def draw_contact(self, jid, account, selected = False, focus = False):
		'''draw the correct state image, name BUT not avatar'''
		# focus is about if the roster window has toplevel-focus or not
		model = self.tree.get_model()
		iters = self.get_contact_iter(jid, account)
		if len(iters) == 0:
			return
		contact_instances = gajim.contacts.get_contact(account, jid)
		contact = gajim.contacts.get_highest_prio_contact_from_contacts(
			contact_instances)
		if not contact:
			return
		name = gobject.markup_escape_text(contact.get_shown_name())

		# gets number of unread gc marked messages
		if jid in gajim.interface.minimized_controls[account]:
			nb_unread = len(gajim.events.get_events(account, jid,
				['printed_marked_gc_msg']))
			nb_unread += \
				gajim.interface.minimized_controls[account][jid].get_nb_unread_pm()

			if nb_unread == 1:
				name = '%s *' % name
			elif nb_unread > 1:
				name = '%s [%s]' % (name, str(nb_unread))

		strike = False
		if jid in gajim.connections[account].blocked_contacts:
			strike = True
		else:
			groups = contact.groups
			if contact.is_observer():
				groups = [_('Observers')]
			elif not groups:
				groups = [_('General')]
			for group in groups:
				if group in gajim.connections[account].blocked_groups:
					strike = True
					break
		if strike:
			name = '<span strikethrough="true">%s</span>' % name

		nb_connected_contact = 0
		for c in contact_instances:
			if c.show not in ('error', 'offline'):
				nb_connected_contact += 1
		if nb_connected_contact > 1:
			name += ' (' + unicode(nb_connected_contact) + ')'

		# show (account_name) if there are 2 contact with same jid in merged mode
		if self.regroup:
			add_acct = False
			# look through all contacts of all accounts
			for account_iter in gajim.connections:
				if account_iter == account: # useless to add accout name
					continue
				for jid_iter in gajim.contacts.get_jid_list(account_iter):
					# [0] cause it'fster than highest_prio
					contact_iter = gajim.contacts.\
						get_first_contact_from_jid(account_iter, jid_iter)
					if contact_iter.get_shown_name() == \
					contact.get_shown_name() and\
					(jid_iter, account_iter) != (jid, account):
						add_acct = True
						break
				if add_acct:
					# No need to continue in other account if we already found one
					break
			if add_acct:
				name += ' (' + account + ')'

		# add status msg, if not empty, under contact name in the treeview
		if contact.status and gajim.config.get('show_status_msgs_in_roster'):
			status = contact.status.strip()
			if status != '':
				status = helpers.reduce_chars_newlines(status, max_lines = 1)
				# escape markup entities and make them small italic and fg color
				color = gtkgui_helpers._get_fade_color(self.tree, selected, focus)
				colorstring = '#%04x%04x%04x' % (color.red, color.green, color.blue)
				name += \
					'\n<span size="small" style="italic" foreground="%s">%s</span>' \
					% (colorstring, gobject.markup_escape_text(status))

		iter = iters[0] # choose the icon with the first iter

		if gajim.gc_connected[account].has_key(jid):
			contact.show = 'online'
			model[iter][C_TYPE] = 'groupchat'

		icon_name = helpers.get_icon_name_to_show(contact, account)
		# look if another resource has awaiting events
		for c in contact_instances:
			c_icon_name = helpers.get_icon_name_to_show(c, account)
			if c_icon_name in ('message', 'muc_active', 'muc_inactive'):
				icon_name = c_icon_name
				break
		path = model.get_path(iter)
		if model.iter_has_child(iter):
			if not self.tree.row_expanded(path) and \
			icon_name not in ('message', 'muc_active', 'muc_inactive'):
				child_iter = model.iter_children(iter)
				if icon_name in ('error', 'offline'):
					# get the icon from the first child as they are sorted by show
					child_jid = model[child_iter][C_JID].decode('utf-8')
					child_account = model[child_iter][C_ACCOUNT].decode('utf-8')
					child_contact = gajim.contacts.get_contact_with_highest_priority(
						child_account, child_jid)
					child_icon_name = helpers.get_icon_name_to_show(child_contact,
						child_account)
					if child_icon_name not in ('error', 'not in roster'):
						icon_name = child_icon_name
				while child_iter:
					# a child has awaiting messages ?
					child_jid = model[child_iter][C_JID].decode('utf-8')
					child_account = model[child_iter][C_ACCOUNT].decode('utf-8')
					if len(gajim.events.get_events(child_account, child_jid)):
						icon_name = 'message'
						break
					child_iter = model.iter_next(child_iter)
			if self.tree.row_expanded(path):
				state_images = self.get_appropriate_state_images(jid,
					size = 'opened', icon_name = icon_name)
			else:
				state_images = self.get_appropriate_state_images(jid,
					size = 'closed', icon_name = icon_name)
		else:
			# redraw parent
			self.draw_parent_contact(jid, account)
			state_images = self.get_appropriate_state_images(jid,
				icon_name = icon_name)

		img = state_images[icon_name]

		for iter in iters:
			model[iter][C_IMG] = img
			model[iter][C_NAME] = name

	def draw_parent_contact(self, jid, account):
		model = self.tree.get_model()
		iters = self.get_contact_iter(jid, account)
		if not len(iters):
			return
		parent_iter = model.iter_parent(iters[0])
		if model[parent_iter][C_TYPE] != 'contact':
			# parent is not a contact
			return
		parent_jid = model[parent_iter][C_JID].decode('utf-8')
		parent_account = model[parent_iter][C_ACCOUNT].decode('utf-8')
		self.draw_contact(parent_jid, parent_account)

	def draw_avatar(self, jid, account):
		'''draw the avatar'''
		model = self.tree.get_model()
		iters = self.get_contact_iter(jid, account)
		if gajim.config.get('show_avatars_in_roster'):
			pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid)
			if pixbuf in ('ask', None):
				scaled_pixbuf = None
			else:
				scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'roster')
		else:
			scaled_pixbuf = None
		for iter in iters:
			model[iter][C_SECPIXBUF] = scaled_pixbuf

	def join_gc_room(self, account, room_jid, nick, password, minimize = False):
		'''joins the room immediatelly'''
		if gajim.interface.msg_win_mgr.has_window(room_jid, account) and \
				gajim.gc_connected[account][room_jid]:
			win = gajim.interface.msg_win_mgr.get_window(room_jid,  account)
			win.window.present()
			win.set_active_tab(room_jid,  account)
			dialogs.ErrorDialog(_('You are already in group chat %s') % room_jid)
			return
		minimized_control_exists = False
		if room_jid in gajim.interface.minimized_controls[account]:
			minimized_control_exists = True
		invisible_show = gajim.SHOW_LIST.index('invisible')
		if gajim.connections[account].connected == invisible_show:
			dialogs.ErrorDialog(
				_('You cannot join a group chat while you are invisible'))
			return
		if minimize and not minimized_control_exists and \
		not gajim.interface.msg_win_mgr.has_window(room_jid, account):
			contact = gajim.contacts.create_contact(jid = room_jid, name = nick)
			gc_control = GroupchatControl(None, contact, account)
			gajim.interface.minimized_controls[account][room_jid] = gc_control
			gajim.connections[account].join_gc(nick, room_jid, password)
			if password:
				gajim.gc_passwords[room_jid] = password
			self.add_groupchat_to_roster(account, room_jid)
			return
		if not minimized_control_exists and \
			not gajim.interface.msg_win_mgr.has_window(room_jid, account):
			self.new_room(room_jid, nick, account)
		if not minimized_control_exists:
			gc_win = gajim.interface.msg_win_mgr.get_window(room_jid, account)
			gc_win.set_active_tab(room_jid, account)
			gc_win.window.present()
		gajim.connections[account].join_gc(nick, room_jid, password)
		if password:
			gajim.gc_passwords[room_jid] = password
		contact = gajim.contacts.get_contact_with_highest_priority(account, \
			room_jid)
		if contact or minimized_control_exists:
			self.add_groupchat_to_roster(account, room_jid)

	def on_actions_menuitem_activate(self, widget):
		self.make_menu()

	def on_edit_menuitem_activate(self, widget):
		'''need to call make_menu to build profile, avatar item'''
		self.make_menu()

	def on_bookmark_menuitem_activate(self, widget, account, bookmark):
		self.join_gc_room(account, bookmark['jid'], bookmark['nick'],
			bookmark['password'])

	def on_send_server_message_menuitem_activate(self, widget, account):
		server = gajim.config.get_per('accounts', account, 'hostname')
		server += '/announce/online'
		dialogs.SingleMessageWindow(account, server, 'send')

	def on_xml_console_menuitem_activate(self, widget, account):
		if gajim.interface.instances[account].has_key('xml_console'):
			gajim.interface.instances[account]['xml_console'].window.present()
		else:
			gajim.interface.instances[account]['xml_console'] = \
				dialogs.XMLConsoleWindow(account)

	def on_privacy_lists_menuitem_activate(self, widget, account):
		if gajim.interface.instances[account].has_key('privacy_lists'):
			gajim.interface.instances[account]['privacy_lists'].window.present()
		else:
			gajim.interface.instances[account]['privacy_lists'] = \
				dialogs.PrivacyListsWindow(account)

	def on_blocked_contacts_menuitem_activate(self, widget, account):
		if gajim.interface.instances[account].has_key('blocked_contacts'):
			gajim.interface.instances[account]['blocked_contacts'].window.present()
		else:
			gajim.interface.instances[account]['blocked_contacts'] = \
				dialogs.BlockedContactsWindow(account)

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

	def on_history_manager_menuitem_activate(self, widget):
		if os.name == 'nt':
			if os.path.exists('history_manager.exe'): # user is running stable
				helpers.exec_command('history_manager.exe')
			else: # user is running svn
				helpers.exec_command('python history_manager.py')
		else: # Unix user
			helpers.exec_command('python history_manager.py &')

	def get_and_connect_advanced_menuitem_menu(self, account):
		'''adds FOR ACCOUNT options'''
		xml = gtkgui_helpers.get_glade('advanced_menuitem_menu.glade')
		advanced_menuitem_menu = xml.get_widget('advanced_menuitem_menu')

		send_single_message_menuitem = xml.get_widget(
			'send_single_message_menuitem')
		xml_console_menuitem = xml.get_widget('xml_console_menuitem')
		blocked_contacts_menuitem = xml.get_widget('blocked_contacts_menuitem')
		privacy_lists_menuitem = xml.get_widget('privacy_lists_menuitem')
		administrator_menuitem = xml.get_widget('administrator_menuitem')
		send_server_message_menuitem = xml.get_widget(
			'send_server_message_menuitem')
		set_motd_menuitem = xml.get_widget('set_motd_menuitem')
		update_motd_menuitem = xml.get_widget('update_motd_menuitem')
		delete_motd_menuitem = xml.get_widget('delete_motd_menuitem')

		xml_console_menuitem.connect('activate',
			self.on_xml_console_menuitem_activate, account)

		if gajim.connections[account] and gajim.connections[account].\
		privacy_rules_supported:
			blocked_contacts_menuitem.connect('activate',
				self.on_blocked_contacts_menuitem_activate, account)
			privacy_lists_menuitem.connect('activate',
				self.on_privacy_lists_menuitem_activate, account)
		else:
			blocked_contacts_menuitem.set_sensitive(False)
			privacy_lists_menuitem.set_sensitive(False)

		if gajim.connections[account].is_zeroconf:
			send_single_message_menuitem.set_sensitive(False)
			administrator_menuitem.set_sensitive(False)
			send_server_message_menuitem.set_sensitive(False)
			set_motd_menuitem.set_sensitive(False)
			update_motd_menuitem.set_sensitive(False)
			delete_motd_menuitem.set_sensitive(False)
		else:
			send_single_message_menuitem.connect('activate',
				self.on_send_single_message_menuitem_activate, account)

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
		if not self.actions_menu_needs_rebuild:
			return
		new_chat_menuitem = self.xml.get_widget('new_chat_menuitem')
		join_gc_menuitem = self.xml.get_widget('join_gc_menuitem')
		muc_icon = self.load_icon('muc_active')
		if muc_icon:
			join_gc_menuitem.set_image(muc_icon)
		add_new_contact_menuitem = self.xml.get_widget('add_new_contact_menuitem')
		service_disco_menuitem = self.xml.get_widget('service_disco_menuitem')
		advanced_menuitem = self.xml.get_widget('advanced_menuitem')
		profile_avatar_menuitem = self.xml.get_widget('profile_avatar_menuitem')

		# destroy old advanced menus
		for m in self.advanced_menus:
			m.destroy()

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

		if self.new_chat_menuitem_handler_id:
			new_chat_menuitem.handler_disconnect(
				self.new_chat_menuitem_handler_id)
			self.new_chat_menuitem_handler_id = None

		if self.profile_avatar_menuitem_handler_id:
			profile_avatar_menuitem.handler_disconnect(
				self.profile_avatar_menuitem_handler_id)
			self.profile_avatar_menuitem_handler_id = None


		# remove the existing submenus
		add_new_contact_menuitem.remove_submenu()
		service_disco_menuitem.remove_submenu()
		join_gc_menuitem.remove_submenu()
		new_chat_menuitem.remove_submenu()
		advanced_menuitem.remove_submenu()
		profile_avatar_menuitem.remove_submenu()

		# remove the existing accelerator
		if self.have_new_chat_accel:
			ag = gtk.accel_groups_from_object(self.window)[0]
			new_chat_menuitem.remove_accelerator(ag, gtk.keysyms.n,
				gtk.gdk.CONTROL_MASK)
			self.have_new_chat_accel = False

		gc_sub_menu = gtk.Menu() # gc is always a submenu
		join_gc_menuitem.set_submenu(gc_sub_menu)

		connected_accounts = gajim.get_number_of_connected_accounts()
		if connected_accounts > 1: # 2 or more accounts? make submenus
			add_sub_menu = gtk.Menu()
			disco_sub_menu = gtk.Menu()
			new_chat_sub_menu = gtk.Menu()

			accounts_list = gajim.contacts.get_accounts()
			accounts_list.sort()
			for account in accounts_list:
				if gajim.connections[account].connected <= 1:
					# if offline or connecting
					continue

				# new chat
				new_chat_item = gtk.MenuItem(_('using account %s') % account,
					False)
				new_chat_sub_menu.append(new_chat_item)
				new_chat_item.connect('activate',
					self.on_new_chat_menuitem_activate,	account)

				if gajim.config.get_per('accounts', account, 'is_zeroconf'):
					continue

				# join gc
				gc_item = gtk.MenuItem(_('using account %s') % account, False)
				gc_sub_menu.append(gc_item)
				gc_menuitem_menu = gtk.Menu()
				self.add_bookmarks_list(gc_menuitem_menu, account)
				gc_item.set_submenu(gc_menuitem_menu)

				# the 'manage gc bookmarks' item is shown
				# below to avoid duplicate code

				# add
				add_item = gtk.MenuItem(_('to %s account') % account, False)
				add_sub_menu.append(add_item)
				add_item.connect('activate', self.on_add_new_contact, account)

				# disco
				disco_item = gtk.MenuItem(_('using %s account') % account, False)
				disco_sub_menu.append(disco_item)
				disco_item.connect('activate',
					self.on_service_disco_menuitem_activate, account)


			add_new_contact_menuitem.set_submenu(add_sub_menu)
			add_sub_menu.show_all()
			service_disco_menuitem.set_submenu(disco_sub_menu)
			disco_sub_menu.show_all()
			new_chat_menuitem.set_submenu(new_chat_sub_menu)
			new_chat_sub_menu.show_all()
			gc_sub_menu.show_all()

		elif connected_accounts == 1: # user has only one account
			for account in gajim.connections:
				if gajim.account_is_connected(account): # THE connected account
					# gc
					self.add_bookmarks_list(gc_sub_menu, account)
					# add
					if not self.add_new_contact_handler_id:
						self.add_new_contact_handler_id =\
							add_new_contact_menuitem.connect(
							'activate', self.on_add_new_contact, account)
					# disco
					if not self.service_disco_handler_id:
						self.service_disco_handler_id = service_disco_menuitem.\
							connect('activate',
							self.on_service_disco_menuitem_activate, account)
					# new chat
					if not self.new_chat_menuitem_handler_id:
						self.new_chat_menuitem_handler_id = new_chat_menuitem.\
							connect('activate', self.on_new_chat_menuitem_activate,
							account)
					# new chat accel
					if not self.have_new_chat_accel:
						ag = gtk.accel_groups_from_object(self.window)[0]
						new_chat_menuitem.add_accelerator('activate', ag,
							gtk.keysyms.n,	gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
						self.have_new_chat_accel = True

					break # No other account connected

		if connected_accounts == 0:
			# no connected accounts, make the menuitems insensitive
			for item in [new_chat_menuitem, join_gc_menuitem,\
					add_new_contact_menuitem, service_disco_menuitem]:
				item.set_sensitive(False)
		else: # we have one or more connected accounts
			for item in [new_chat_menuitem, join_gc_menuitem,\
						add_new_contact_menuitem, service_disco_menuitem]:
				item.set_sensitive(True)

			# disable some fields if only local account is there
			if connected_accounts == 1:
				for account in gajim.connections:
					if gajim.account_is_connected(account) and \
							gajim.connections[account].is_zeroconf:
						for item in [join_gc_menuitem,\
								add_new_contact_menuitem, service_disco_menuitem]:
							item.set_sensitive(False)

			# show the 'manage gc bookmarks' item
			newitem = gtk.SeparatorMenuItem() # separator
			gc_sub_menu.append(newitem)

		connected_accounts_with_vcard = []
		for account in gajim.connections:
			if gajim.account_is_connected(account) and \
			gajim.connections[account].vcard_supported:
				connected_accounts_with_vcard.append(account)
		if len(connected_accounts_with_vcard) > 1:
			# 2 or more accounts? make submenus
			profile_avatar_sub_menu = gtk.Menu()
			for account in connected_accounts_with_vcard:
				# profile, avatar
				profile_avatar_item = gtk.MenuItem(_('of account %s') % account,
					False)
				profile_avatar_sub_menu.append(profile_avatar_item)
				profile_avatar_item.connect('activate',
					self.on_profile_avatar_menuitem_activate, account)
			profile_avatar_menuitem.set_submenu(profile_avatar_sub_menu)
			profile_avatar_sub_menu.show_all()
		elif len(connected_accounts_with_vcard) == 1: # user has only one account
			account = connected_accounts_with_vcard[0]
			# profile, avatar
			if not self.profile_avatar_menuitem_handler_id:
				self.profile_avatar_menuitem_handler_id = \
				profile_avatar_menuitem.connect('activate', self.\
				on_profile_avatar_menuitem_activate, account)

		if len(connected_accounts_with_vcard) == 0:
			profile_avatar_menuitem.set_sensitive(False)
		else:
			profile_avatar_menuitem.set_sensitive(True)

			newitem = gtk.ImageMenuItem(_('_Manage Bookmarks...'))
			img = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES,
				gtk.ICON_SIZE_MENU)
			newitem.set_image(img)
			newitem.connect('activate',
				self.on_manage_bookmarks_menuitem_activate)
			gc_sub_menu.append(newitem)
			gc_sub_menu.show_all()

		# Advanced Actions
		if len(gajim.connections) == 0: # user has no accounts
			advanced_menuitem.set_sensitive(False)
		elif len(gajim.connections) == 1: # we have one acccount
			account = gajim.connections.keys()[0]
			advanced_menuitem_menu = self.get_and_connect_advanced_menuitem_menu(
				account)
			self.advanced_menus.append(advanced_menuitem_menu)

			self._add_history_manager_menuitem(advanced_menuitem_menu)

			advanced_menuitem.set_submenu(advanced_menuitem_menu)
			advanced_menuitem_menu.show_all()
		else: # user has *more* than one account : build advanced submenus
			advanced_sub_menu = gtk.Menu()
			accounts = [] # Put accounts in a list to sort them
			for account in gajim.connections:
				accounts.append(account)
			accounts.sort()
			for account in accounts:
				advanced_item = gtk.MenuItem(_('for account %s') % account, False)
				advanced_sub_menu.append(advanced_item)
				advanced_menuitem_menu = \
					self.get_and_connect_advanced_menuitem_menu(account)
				self.advanced_menus.append(advanced_menuitem_menu)
				advanced_item.set_submenu(advanced_menuitem_menu)

			self._add_history_manager_menuitem(advanced_sub_menu)

			advanced_menuitem.set_submenu(advanced_sub_menu)
			advanced_sub_menu.show_all()

		self.actions_menu_needs_rebuild = False

	def _add_history_manager_menuitem(self, menu):
		'''adds a seperator and History Manager menuitem BELOW for account
		menuitems'''
		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		# History manager
		item = gtk.ImageMenuItem(_('History Manager'))
		icon = gtk.image_new_from_stock(gtk.STOCK_JUSTIFY_FILL,
			gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		item.connect('activate', self.on_history_manager_menuitem_activate)

	def add_bookmarks_list(self, gc_sub_menu, account):
		'''Show join new group chat item and bookmarks list for an account'''
		item = gtk.ImageMenuItem(_('_Join New Group Chat'))
		icon = gtk.image_new_from_stock(gtk.STOCK_NEW, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		item.connect('activate', self.on_join_gc_activate, account)
		gc_sub_menu.append(item)
		
		if len(gajim.connections[account].bookmarks) > 0: # user has at least one bookmark
			item = gtk.SeparatorMenuItem() # separator
			gc_sub_menu.append(item)

		for bookmark in gajim.connections[account].bookmarks:
			item = gtk.MenuItem(bookmark['name'], False) # Do not use underline
			item.connect('activate', self.on_bookmark_menuitem_activate,
				account, bookmark)
			gc_sub_menu.append(item)

	def _change_style(self, model, path, iter, option):
		if option is None or model[iter][C_TYPE] == option:
			# We changed style for this type of row
			model[iter][C_NAME] = model[iter][C_NAME]

	def change_roster_style(self, option):
		model = self.tree.get_model()
		model.foreach(self._change_style, option)
		for win in gajim.interface.msg_win_mgr.windows():
			win.repaint_themed_widgets()

	def draw_roster(self):
		'''clear and draw roster'''
		# clear the model, only if it is not empty
		model = self.tree.get_model()
		if model:
			model.clear()
		for acct in gajim.connections:
			self.add_account_to_roster(acct)
			self.add_account_contacts(acct)
		# Recalculate column width for ellipsizing
		self.tree.columns_autosize()

	def add_account_contacts(self, account):
		'''adds contacts of group to roster treeview'''
		for jid in gajim.contacts.get_jid_list(account):
			self.add_contact_to_roster(jid, account)
		self.draw_account(account)

	def fire_up_unread_messages_events(self, account):
		'''reads from db the unread messages, and fire them up'''
		for jid in gajim.contacts.get_jid_list(account):
			results = gajim.logger.get_unread_msgs_for_jid(jid)
			for result in results:
				tim = time.localtime(float(result[2]))
				self.on_message(jid, result[1], tim, account, msg_type = 'chat',
					msg_id = result[0])

	def fill_contacts_and_groups_dicts(self, array, account):
		'''fill gajim.contacts and gajim.groups'''
		if account not in gajim.contacts.get_accounts():
			gajim.contacts.add_account(account)
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
				name = ''
			show = 'offline' # show is offline by default
			status = '' #no status message by default

			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			contact1 = gajim.contacts.create_contact(jid = ji, name = name,
				groups = array[jid]['groups'], show = show, status = status,
				sub = array[jid]['subscription'], ask = array[jid]['ask'],
				resource = resource, keyID = keyID)
			gajim.contacts.add_contact(account, contact1)

			# when we draw the roster, we avoid having the same contact
			# more than once (f.e. we avoid showing it twice when 2 resources)
			for g in array[jid]['groups']:
				if g in gajim.groups[account].keys():
					continue

				if account + g in self.collapsed_rows:
					ishidden = False
				else:
					ishidden = True
				gajim.groups[account][g] = { 'expand': ishidden }
			if gajim.config.get('ask_avatars_on_startup'):
				pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(ji)
				if pixbuf == 'ask':
					transport = gajim.get_transport_name_from_jid(contact1.jid)
					if not transport or gajim.jid_is_transport(contact1.jid):
						jid_with_resource = contact1.jid
						if contact1.resource:
							jid_with_resource += '/' + contact1.resource
						gajim.connections[account].request_vcard(jid_with_resource)
					else:
						host = gajim.get_server_from_jid(contact1.jid)
						if not gajim.transport_avatar[account].has_key(host):
							gajim.transport_avatar[account][host] = [contact1.jid]
						else:
							gajim.transport_avatar[account][host].append(contact1.jid)
			# If we already have a chat window opened, update it with new contact
			# instance
			chat_control = gajim.interface.msg_win_mgr.get_control(ji, account)
			if chat_control:
				chat_control.contact = contact1

	def chg_contact_status(self, contact, show, status, account):
		'''When a contact changes his or her status'''
		contact_instances = gajim.contacts.get_contact(account, contact.jid)
		contact.show = show
		contact.status = status
		if show in ('offline', 'error') and \
		len(gajim.events.get_events(account, contact.get_full_jid())) == 0:
			if len(contact_instances) > 1:
				# if multiple resources
				jid_with_resource = contact.jid + '/' + contact.resource
				if gajim.interface.msg_win_mgr.has_window(jid_with_resource,
				account):
					win = gajim.interface.msg_win_mgr.get_window(jid_with_resource,
						account)
					ctrl = win.get_control(jid_with_resource, account)
					ctrl.update_ui()
					win.redraw_tab(ctrl)
				gajim.contacts.remove_contact(account, contact)
		self.remove_contact(contact, account)
		self.add_contact_to_roster(contact.jid, account)
		# print status in chat window and update status/GPG image
		jid_list = [contact.jid]
		for jid in jid_list:
			if gajim.interface.msg_win_mgr.has_window(jid, account):
				win = gajim.interface.msg_win_mgr.get_window(jid, account)
				ctrl = win.get_control(jid, account)
				ctrl.contact = gajim.contacts.get_contact_with_highest_priority(
					account, contact.jid)
				ctrl.update_ui()
				win.redraw_tab(ctrl)

				name = contact.get_shown_name()

				# if multiple resources (or second one disconnecting)
				if (len(contact_instances) > 1 or (len(contact_instances) == 1 and \
				show in ('offline', 'error'))) and contact.resource != '':
					name += '/' + contact.resource

				uf_show = helpers.get_uf_show(show)
				if status:
					ctrl.print_conversation(_('%s is now %s (%s)') % (name, uf_show,
						status), 'status')
				else: # No status message
					ctrl.print_conversation(_('%s is now %s') % (name, uf_show),
						'status')

		if not contact.groups:
			self.draw_group(_('General'), account)
		else:
			for group in contact.groups:
				self.draw_group(group, account)

		self.draw_account(account)

	def on_info(self, widget, contact, account):
		'''Call vcard_information_window class to display contact's information'''
		if gajim.connections[account].is_zeroconf:
			self.on_info_zeroconf(widget, contact, account)
			return

		info = gajim.interface.instances[account]['infos']
		if info.has_key(contact.jid):
			info[contact.jid].window.present()
		else:
			info[contact.jid] = vcard.VcardWindow(contact, account)

	def on_info_zeroconf(self, widget, contact, account):
		info = gajim.interface.instances[account]['infos']
		if info.has_key(contact.jid):
			info[contact.jid].window.present()
		else:
			contact = gajim.contacts.get_first_contact_from_jid(account,
							contact.jid)
			if contact.show in ('offline', 'error'):
				# don't show info on offline contacts
				return
			info[contact.jid] = vcard.ZeroconfVcardWindow(contact, account)


	def show_tooltip(self, contact):
		pointer = self.tree.get_pointer()
		props = self.tree.get_path_at_pos(pointer[0], pointer[1])
		# check if the current pointer is at the same path
		# as it was before setting the timeout
		if props and self.tooltip.id == props[0]:
			# bounding rectangle of coordinates for the cell within the treeview
			rect = self.tree.get_cell_area(props[0], props[1])

			# position of the treeview on the screen
			position = self.tree.window.get_origin()
			self.tooltip.show_tooltip(contact, rect.height, position[1] + rect.y)
		else:
			self.tooltip.hide_tooltip()

	def on_roster_treeview_leave_notify_event(self, widget, event):
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
			if model[iter][C_TYPE] in ('contact', 'self_contact'):
				# we're on a contact entry in the roster
				account = model[iter][C_ACCOUNT].decode('utf-8')
				jid = model[iter][C_JID].decode('utf-8')
				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					contacts = gajim.contacts.get_contact(account, jid)
					connected_contacts = []
					for c in contacts:
						if c.show not in ('offline', 'error'):
							connected_contacts.append(c)
					if not connected_contacts:
						# no connected contacts, show the ofline one
						connected_contacts = contacts
					self.tooltip.account = account
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, connected_contacts)
			elif model[iter][C_TYPE] == 'groupchat':
				account = model[iter][C_ACCOUNT].decode('utf-8')
				jid = model[iter][C_JID].decode('utf-8')
				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					contact = gajim.contacts.get_contact(account, jid)
					self.tooltip.account = account
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, contact)
			elif model[iter][C_TYPE] == 'account':
				# we're on an account entry in the roster
				account = model[iter][C_ACCOUNT].decode('utf-8')
				if account == 'all':
					if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
						self.tooltip.id = row
						self.tooltip.account = None
						self.tooltip.timeout = gobject.timeout_add(500,
							self.show_tooltip, [])
					return
				jid = gajim.get_jid_from_account(account)
				contacts = []
				connection = gajim.connections[account]
				# get our current contact info

				nbr_on, nbr_total = gajim.contacts.get_nb_online_total_contacts(
					accounts = [account])
				account_name = account
				if gajim.account_is_connected(account):
					account_name += ' (%s/%s)' % (repr(nbr_on), repr(nbr_total))
				contact = gajim.contacts.create_contact(jid = jid,
					name = account_name, show = connection.get_status(), sub = '',
					status = connection.status,
					resource = connection.server_resource,
					priority = connection.priority,
					keyID = gajim.config.get_per('accounts', connection.name,
						'keyid'))
				contacts.append(contact)
				# if we're online ...
				if connection.connection:
					roster = connection.connection.getRoster()
					# in threadless connection when no roster stanza is sent,
					# 'roster' is None
					if roster and roster.getItem(jid):
						resources = roster.getResources(jid)
						# ...get the contact info for our other online resources
						for resource in resources:
							show = roster.getShow(jid+'/'+resource)
							if not show:
								show = 'online'
							contact = gajim.contacts.create_contact(jid = jid,
								name = account, show = show,
								status = roster.getStatus(jid+'/'+resource),
								resource = resource,
								priority = roster.getPriority(jid+'/'+resource))
							contacts.append(contact)
				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					self.tooltip.account = None
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, contacts)

	def on_agent_logging(self, widget, jid, state, account):
		'''When an agent is requested to log in or off'''
		gajim.connections[account].send_agent_status(jid, state)

	def on_edit_agent(self, widget, contact, account):
		'''When we want to modify the agent registration'''
		gajim.connections[account].request_register_agent_info(contact.jid)

	def on_remove_agent(self, widget, list_):
		'''When an agent is requested to be removed. list_ is a list of
		(contact, account) tuple'''
		for (contact, account) in list_:
			if gajim.config.get_per('accounts', account, 'hostname') == \
			contact.jid:
				# We remove the server contact
				# remove it from treeview
				gajim.connections[account].unsubscribe(contact.jid)
				self.remove_contact(contact, account)
				gajim.contacts.remove_contact(account, contact)
				return

		def remove(widget, list_):
			self.dialog.destroy()
			for (contact, account) in list_:
				full_jid = contact.get_full_jid()
				gajim.connections[account].unsubscribe_agent(full_jid)
				# remove transport from treeview
				self.remove_contact(contact, account)
				gajim.contacts.remove_jid(account, contact.jid)
				gajim.contacts.remove_contact(account, contact)

		# Check if there are unread events from some contacts
		has_unread_events = False
		for (contact, account) in list_:
			for jid in gajim.events.get_events(account):
				if jid.endswith(contact.jid):
					has_unread_events = True
					break
		if has_unread_events:
			dialogs.ErrorDialog(_('You have unread messages'),
				_('You must read them before removing this transport.'))
			return
		if len(list_) == 1:
			pritext = _('Transport "%s" will be removed') % contact.jid
			sectext = _('You will no longer be able to send and receive messages '
				'from contacts using this transport.')
		else:
			pritext = _('Transports will be removed')
			jids = ''
			for (contact, account) in list_:
				jids += '\n  ' + contact.get_shown_name() + ','
			jids = jids[:-1] + '.'
			sectext = _('You will no longer be able to send and receive messages '
				'to contacts from these transports:%s') % jids
		self.dialog = dialogs.ConfirmationDialog(pritext, sectext,
			on_response_ok = (remove, list_))

	def on_block(self, widget, iter, group_list):
		''' When clicked on the 'block' button in context menu. '''
		model = self.tree.get_model()
		accounts = []
		msg = self.get_status_message('offline')
		if group_list == None:
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			accounts.append(account)
			self.send_status(account, 'offline', msg, to = jid)
			new_rule = {'order': u'1', 'type': u'jid', 'action': u'deny',
				'value' : jid, 'child':  [u'message', u'iq', u'presence-out']}
			gajim.connections[account].blocked_list.append(new_rule)
			# needed for draw_contact:
			gajim.connections[account].blocked_contacts.append(jid)
			self.draw_contact(jid, account)
		else:
			if iter == None:
				for (contact, account) in group_list:
					if account not in accounts:
						if not gajim.connections[account].privacy_rules_supported:
							continue
						accounts.append(account)
					self.send_status(account, 'offline', msg, to=contact.jid)
					new_rule = {'order': u'1', 'type': u'jid',
							'action': u'deny',  'value' : contact.jid,
							'child':  [u'message', u'iq', u'presence-out']}
					gajim.connections[account].blocked_list.append(new_rule)
					# needed for draw_contact:
					gajim.connections[account].blocked_contacts.append(contact.jid)
					self.draw_contact(contact.jid, account)
			else:
				group = model[iter][C_JID].decode('utf-8')
				for (contact, account) in group_list:
					if account not in accounts:
						if not gajim.connections[account].privacy_rules_supported:
							continue
						accounts.append(account)
						# needed for draw_group:
						gajim.connections[account].blocked_groups.append(group)
						self.draw_group(group, account)
					self.send_status(account, 'offline', msg, to=contact.jid)
					self.draw_contact(contact.jid, account)
				new_rule = {'order': u'1', 'type': u'group', 'action': u'deny',
					'value' : group, 'child':  [u'message', u'iq', u'presence-out']}
				gajim.connections[account].blocked_list.append(new_rule)
		for account in accounts:
			gajim.connections[account].set_privacy_list(
			'block', gajim.connections[account].blocked_list)
		if len(gajim.connections[account].blocked_list) == 1:
			gajim.connections[account].set_active_list('block')
			gajim.connections[account].set_default_list('block')
		gajim.connections[account].get_privacy_list('block')

	def on_unblock(self, widget, iter, group_list):
		''' When clicked on the 'unblock' button in context menu. '''
		model = self.tree.get_model()
		accounts = []
		if group_list == None:
			jid = model[iter][C_JID].decode('utf-8')
			jid_account = model[iter][C_ACCOUNT].decode('utf-8')
			accounts.append(jid_account)
			gajim.connections[jid_account].new_blocked_list = []
			for rule in gajim.connections[jid_account].blocked_list:
				if rule['action'] != 'deny' or rule['type'] != 'jid' \
				or rule['value'] != jid:
					gajim.connections[jid_account].new_blocked_list.append(rule)
			# needed for draw_contact:
			if jid in gajim.connections[jid_account].blocked_contacts:
				gajim.connections[jid_account].blocked_contacts.remove(jid)
			self.draw_contact(jid, jid_account)
		else:
			if iter == None:
				for (contact, account) in group_list:
					if account not in accounts:
						if gajim.connections[account].privacy_rules_supported:
							accounts.append(account)
							gajim.connections[account].new_blocked_list = []
							gajim.connections[account].to_unblock = []
							gajim.connections[account].to_unblock.append(contact.jid)
					else:
						gajim.connections[account].to_unblock.append(contact.jid)
					# needed for draw_contact:
					if contact.jid in gajim.connections[account].blocked_contacts:
						gajim.connections[account].blocked_contacts.remove(
							contact.jid)
					self.draw_contact(contact.jid, account)
				for account in accounts:
					for rule in gajim.connections[account].blocked_list:
						if rule['action'] != 'deny' or rule['type'] != 'jid' \
						or rule['value'] not in gajim.connections[account].to_unblock:
							gajim.connections[account].new_blocked_list.append(rule)
			else:
				group = model[iter][C_JID].decode('utf-8')
				for (contact, account) in group_list:
					if account not in accounts:
						if gajim.connections[account].privacy_rules_supported:
							accounts.append(account)
							# needed for draw_group:
							if group in gajim.connections[account].blocked_groups:
								gajim.connections[account].blocked_groups.remove(group)
							self.draw_group(group, account)
							gajim.connections[account].new_blocked_list = []
							for rule in gajim.connections[account].blocked_list:
								if rule['action'] != 'deny' or rule['type'] != 'group' \
								or rule['value'] != group:
									gajim.connections[account].new_blocked_list.append(
										rule)
					self.draw_contact(contact.jid, account)
		for account in accounts:
			gajim.connections[account].set_privacy_list(
				'block', gajim.connections[account].new_blocked_list)
			gajim.connections[account].get_privacy_list('block')
			if len(gajim.connections[account].new_blocked_list) == 0:
				gajim.connections[account].blocked_list = []
				gajim.connections[account].blocked_contacts = []
				gajim.connections[account].blocked_groups = []
				gajim.connections[account].set_default_list('')
				gajim.connections[account].set_active_list('')
				gajim.connections[account].del_privacy_list('block')
				if gajim.interface.instances[account].has_key('blocked_contacts'):
					gajim.interface.instances[account]['blocked_contacts'].\
						privacy_list_received([])
		if group_list == None:
			status = gajim.connections[jid_account].connected
			msg = gajim.connections[jid_account].status
			if not self.regroup:
				show = gajim.SHOW_LIST[status]
			else:	# accounts merged
				show = helpers.get_global_show()
			self.send_status(jid_account, show, msg, to=jid)
		else:
			for (contact, account) in group_list:
				if not self.regroup:
					show = gajim.SHOW_LIST[gajim.connections[account].connected]
				else:	# accounts merged
					show = helpers.get_global_show()
				if account not in accounts:
					if gajim.connections[account].privacy_rules_supported:
						accounts.append(account)
						self.send_status(account, show,
							gajim.connections[account].status, to=contact.jid)
				else:
					self.send_status(account, show,
						gajim.connections[account].status, to=contact.jid)

	def on_rename(self, widget, iter, path):
		# this function is called either by F2 or by Rename menuitem
		if gajim.interface.instances.has_key('rename'):
			gajim.interface.instances['rename'].dialog.present()
			return
		model = self.tree.get_model()

		row_type = model[iter][C_TYPE]
		jid = model[iter][C_JID].decode('utf-8')
		account = model[iter][C_ACCOUNT].decode('utf-8')
		# account is offline, don't allow to rename
		if gajim.connections[account].connected < 2:
			return
		if row_type in ('contact', 'agent'):
			# it's jid
			title = _('Rename Contact')
			message = _('Enter a new nickname for contact %s') % jid
			old_text = gajim.contacts.get_contact_with_highest_priority(account,
				jid).name
		elif row_type == 'group':
			if jid in helpers.special_groups + (_('General'),):
				return
			old_text = model[iter][C_JID].decode('utf-8')
			title = _('Rename Group')
			message = _('Enter a new name for group %s') % old_text

		def on_renamed(new_text, account, row_type, jid, old_text):
			if gajim.interface.instances.has_key('rename'):
				del gajim.interface.instances['rename']
			if row_type in ('contact', 'agent'):
				if old_text == new_text:
					return
				for u in gajim.contacts.get_contact(account, jid):
					u.name = new_text
				gajim.connections[account].update_contact(jid, new_text, u.groups)
				self.draw_contact(jid, account)
				# Update opened chat
				ctrl = gajim.interface.msg_win_mgr.get_control(jid, account)
				if ctrl:
					ctrl.update_ui()
					win = gajim.interface.msg_win_mgr.get_window(jid, account)
					win.redraw_tab(ctrl)
					win.show_title()
			elif row_type == 'group':
				# in C_JID column, we hold the group name (which is not escaped)
				if old_text == new_text:
					return
				# Groups may not change name from or to a special groups
				for g in helpers.special_groups:
					if g in (new_text, old_text):
						return
				# get all contacts in that group
				for jid in gajim.contacts.get_jid_list(account):
					contact = gajim.contacts.get_contact_with_highest_priority(
						account, jid)
					if old_text in contact.groups:
						# set them in the new one and remove it from the old
						contact.groups.remove(old_text)
						self.remove_contact(contact, account)
						if new_text not in contact.groups:
							contact.groups.append(new_text)
						self.add_contact_to_roster(contact.jid, account)
						gajim.connections[account].update_contact(contact.jid,
							contact.name, contact.groups)
				# If last removed iter was not visible, gajim.groups is not cleaned
				if gajim.groups[account].has_key(old_text):
					del gajim.groups[account][old_text]
				self.draw_group(new_text, account)

		def on_canceled():
			if gajim.interface.instances.has_key('rename'):
				del gajim.interface.instances['rename']

		gajim.interface.instances['rename'] = dialogs.InputDialog(title, message,
			old_text, False, (on_renamed, account, row_type, jid, old_text),
			on_canceled)

	def readd_if_needed(self, contact, account):
		need_readd = False
		if len(gajim.events.get_events(account, contact.jid)):
			need_readd = True
		elif gajim.interface.msg_win_mgr.has_window(contact.jid, account):
			if _('Not in Roster') in contact.groups:
				# Close chat window
				msg_win = gajim.interface.msg_win_mgr.get_window(contact.jid,
					account)
				ctrl = gajim.interface.msg_win_mgr.get_control(contact.jid, account)
				msg_win.remove_tab(ctrl, msg_win.CLOSE_CLOSE_BUTTON)
			else:
				need_readd = True
		if need_readd:
			c = gajim.contacts.create_contact(jid = contact.jid,
				name = '', groups = [_('Not in Roster')],
				show = 'not in roster', status = '', ask = 'none',
				keyID = contact.keyID)
			gajim.contacts.add_contact(account, c)
			self.add_contact_to_roster(contact.jid, account)

	def on_remove_group_item_activated(self, widget, group, account):
		dlg = dialogs.ConfirmationDialogCheck(_('Remove Group'),
			_('Do you want to remove group %s from the roster?' % group),
			_('Remove also all contacts in this group from your roster'))
		dlg.set_default_response(gtk.BUTTONS_OK_CANCEL)
		response = dlg.run()
		if response == gtk.RESPONSE_OK:
			for contact in gajim.contacts.get_contacts_from_group(account, group):
				if not dlg.is_checked():
					self.remove_contact_from_group(account, contact, group)
					gajim.connections[account].update_contact(contact.jid,
						contact.name, contact.groups)
					self.add_contact_to_roster(contact.jid, account)
				else:
					gajim.connections[account].unsubscribe(contact.jid)
					for c in gajim.contacts.get_contact(account, contact.jid):
						self.remove_contact(c, account)
					gajim.contacts.remove_jid(account, c.jid)
					self.readd_if_needed(contact, account)
			self.draw_account(account)

	def on_assign_pgp_key(self, widget, contact, account):
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		keys = {}
		#GPG Key
		keyID = _('None')
		for i in xrange(len(attached_keys)/2):
			keys[attached_keys[2*i]] = attached_keys[2*i+1]
			if attached_keys[2*i] == contact.jid:
				keyID = attached_keys[2*i+1]
		public_keys = gajim.connections[account].ask_gpg_keys()
		#GPG Key
		public_keys[_('None')] = _('None')
		instance = dialogs.ChooseGPGKeyDialog(_('Assign OpenPGP Key'),
			_('Select a key to apply to the contact'), public_keys, keyID)
		keyID = instance.run()
		if keyID is None:
			return
		#GPG Key
		if keyID[0] == _('None'):
			if contact.jid in keys:
				del keys[contact.jid]
			for u in gajim.contacts.get_contact(account, contact.jid):
				u.keyID = ''
		else:
			keys[contact.jid] = keyID[0]
			for u in gajim.contacts.get_contact(account, contact.jid):
				u.keyID = keyID[0]
		if gajim.interface.msg_win_mgr.has_window(contact.jid, account):
			ctrl = gajim.interface.msg_win_mgr.get_control(contact.jid, account)
			ctrl.update_ui()
		keys_str = ''
		for jid in keys:
			keys_str += jid + ' ' + keys[jid] + ' '
		gajim.config.set_per('accounts', account, 'attached_gpg_keys', keys_str)

	def on_edit_groups(self, widget, list_):
		dlg = dialogs.EditGroupsDialog(list_)
		dlg.run()

	def on_history(self, widget, contact, account):
		'''When history menuitem is activated: call log window'''
		if gajim.interface.instances['logs'].has_key(contact.jid):
			gajim.interface.instances['logs'][contact.jid].window.present()
		else:
			gajim.interface.instances['logs'][contact.jid] = history_window.\
				HistoryWindow(contact.jid, account)

	def on_disconnect(self, widget, jid, account):
		'''When disconnect menuitem is activated: disconect from room'''
		ctrl = gajim.interface.minimized_controls[account][jid]
		del gajim.interface.minimized_controls[account][jid]
		ctrl.shutdown()

		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if not contact:
			return
		if contact.groups == [_('Groupchats')]:
			self.remove_contact(contact, account)
			gajim.contacts.remove_contact(account, contact)
			self.draw_group(_('Groupchats'), account)

	def on_send_single_message_menuitem_activate(self, widget, account,
	contact = None):
		if contact is None:
			dialogs.SingleMessageWindow(account, action = 'send')
		elif type(contact) == type([]):
			dialogs.SingleMessageWindow(account, contact, 'send')
		else:
			jid = contact.jid
			if contact.jid == gajim.get_jid_from_account(account):
				jid += '/' + contact.resource
			dialogs.SingleMessageWindow(account, jid, 'send')

	def on_send_file_menuitem_activate(self, widget, account, contact):
		gajim.interface.instances['file_transfers'].show_file_send_request(
			account, contact)

	def on_add_special_notification_menuitem_activate(self, widget, jid):
		dialogs.AddSpecialNotificationDialog(jid)

	def make_contact_menu(self, event, iter):
		'''Make contact's popup menu'''
		model = self.tree.get_model()
		jid = model[iter][C_JID].decode('utf-8')
		tree_path = model.get_path(iter)
		account = model[iter][C_ACCOUNT].decode('utf-8')
		our_jid = jid == gajim.get_jid_from_account(account)
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if not contact:
			return

		if gajim.config.get_per('accounts', account, 'is_zeroconf'):
			xml = gtkgui_helpers.get_glade('zeroconf_contact_context_menu.glade')
			zeroconf_contact_context_menu = xml.get_widget(
				'zeroconf_contact_context_menu')

			start_chat_menuitem = xml.get_widget('start_chat_menuitem')
			rename_menuitem = xml.get_widget('rename_menuitem')
			edit_groups_menuitem = xml.get_widget('edit_groups_menuitem')
			# separator has with send file, assign_openpgp_key_menuitem, etc..
			above_send_file_separator = xml.get_widget('above_send_file_separator')
			send_file_menuitem = xml.get_widget('send_file_menuitem')
			assign_openpgp_key_menuitem = xml.get_widget(
				'assign_openpgp_key_menuitem')
			add_special_notification_menuitem = xml.get_widget(
				'add_special_notification_menuitem')

			add_special_notification_menuitem.hide()
			add_special_notification_menuitem.set_no_show_all(True)

			if not our_jid:
				# add a special img for rename menuitem
				path_to_kbd_input_img = os.path.join(gajim.DATA_DIR, 'pixmaps',
					'kbd_input.png')
				img = gtk.Image()
				img.set_from_file(path_to_kbd_input_img)
				rename_menuitem.set_image(img)

			above_information_separator = xml.get_widget(
				'above_information_separator')

			# skip a separator
			information_menuitem = xml.get_widget('information_menuitem')
			history_menuitem = xml.get_widget('history_menuitem')

			contacts = gajim.contacts.get_contact(account, jid)
			if len(contacts) > 1: # several resources
				sub_menu = gtk.Menu()
				start_chat_menuitem.set_submenu(sub_menu)

				iconset = gajim.config.get('iconset')
				path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
				for c in contacts:
					# icon MUST be different instance for every item
					state_images = self.load_iconset(path)
					item = gtk.ImageMenuItem('%s (%s)' % (c.resource,
						str(c.priority)))
					icon_name = helpers.get_icon_name_to_show(c, account)
					icon = state_images[icon_name]
					item.set_image(icon)
					sub_menu.append(item)
					item.connect('activate', self.on_open_chat_window, c, account,
						c.resource)

			else: # one resource
				start_chat_menuitem.connect('activate',
					self.on_roster_treeview_row_activated, tree_path)

			if contact.resource:
				send_file_menuitem.connect('activate',
					self.on_send_file_menuitem_activate, account, contact)
			else: # if we do not have resource we cannot send file
				send_file_menuitem.hide()
				send_file_menuitem.set_no_show_all(True)

			rename_menuitem.connect('activate', self.on_rename, iter, tree_path)
			if contact.show in ('offline', 'error'):
				information_menuitem.set_sensitive(False)
				send_file_menuitem.set_sensitive(False)
			else:
				information_menuitem.connect('activate', self.on_info_zeroconf,
					contact, account)
			history_menuitem.connect('activate', self.on_history, contact,
				account)

			if _('Not in Roster') not in contact.groups:
				#contact is in normal group
				edit_groups_menuitem.set_no_show_all(False)
				assign_openpgp_key_menuitem.set_no_show_all(False)
				edit_groups_menuitem.connect('activate', self.on_edit_groups, [(
					contact,account)])

				if gajim.config.get('usegpg'):
					assign_openpgp_key_menuitem.connect('activate',
						self.on_assign_pgp_key, contact, account)

			else: # contact is in group 'Not in Roster'
				edit_groups_menuitem.hide()
				edit_groups_menuitem.set_no_show_all(True)
				# hide first of the two consecutive separators
				above_send_file_separator.hide()
				above_send_file_separator.set_no_show_all(True)
				assign_openpgp_key_menuitem.hide()
				assign_openpgp_key_menuitem.set_no_show_all(True)

			# Remove many items when it's self contact row
			if our_jid:
				for menuitem in (rename_menuitem, edit_groups_menuitem,
				above_information_separator):
					menuitem.set_no_show_all(True)
					menuitem.hide()

			# Unsensitive many items when account is offline
			if gajim.connections[account].connected < 2:
				for widget in [start_chat_menuitem,	rename_menuitem,
				edit_groups_menuitem, send_file_menuitem]:
					widget.set_sensitive(False)

			event_button = gtkgui_helpers.get_possible_button_event(event)

			zeroconf_contact_context_menu.attach_to_widget(self.tree, None)
			zeroconf_contact_context_menu.connect('selection-done',
				gtkgui_helpers.destroy_widget)
			zeroconf_contact_context_menu.show_all()
			zeroconf_contact_context_menu.popup(None, None, None, event_button,
				event.time)
			return


		# normal account
		xml = gtkgui_helpers.get_glade('roster_contact_context_menu.glade')
		roster_contact_context_menu = xml.get_widget(
			'roster_contact_context_menu')

		start_chat_menuitem = xml.get_widget('start_chat_menuitem')
		send_custom_status_menuitem = xml.get_widget(
			'send_custom_status_menuitem')
		send_single_message_menuitem = xml.get_widget(
			'send_single_message_menuitem')
		invite_menuitem = xml.get_widget('invite_menuitem')
		block_menuitem = xml.get_widget('block_menuitem')
		unblock_menuitem = xml.get_widget('unblock_menuitem')
		rename_menuitem = xml.get_widget('rename_menuitem')
		edit_groups_menuitem = xml.get_widget('edit_groups_menuitem')
		# separator has with send file, assign_openpgp_key_menuitem, etc..
		above_send_file_separator = xml.get_widget('above_send_file_separator')
		send_file_menuitem = xml.get_widget('send_file_menuitem')
		assign_openpgp_key_menuitem = xml.get_widget(
			'assign_openpgp_key_menuitem')
		add_special_notification_menuitem = xml.get_widget(
			'add_special_notification_menuitem')
		execute_command_menuitem = xml.get_widget(
			'execute_command_menuitem')

		add_special_notification_menuitem.hide()
		add_special_notification_menuitem.set_no_show_all(True)

		# send custom status icon
		blocked = False
		if jid in gajim.connections[account].blocked_contacts:
			blocked = True
		else:
			groups = contact.groups
			if contact.is_observer():
				groups = [_('Observers')]
			elif not groups:
				groups = [_('General')]
			for group in groups:
				if group in gajim.connections[account].blocked_groups:
					blocked = True
					break
		if blocked:
			send_custom_status_menuitem.set_image(self.load_icon('offline'))
			send_custom_status_menuitem.set_sensitive(False)
		elif gajim.interface.status_sent_to_users.has_key(account) and \
		jid in gajim.interface.status_sent_to_users[account]:
			send_custom_status_menuitem.set_image(
				self.load_icon(gajim.interface.status_sent_to_users[account][jid]))
		else:
			send_custom_status_menuitem.set_image(None)

		if not our_jid:
			# add a special img for rename menuitem
			path_to_kbd_input_img = os.path.join(gajim.DATA_DIR, 'pixmaps',
				'kbd_input.png')
			img = gtk.Image()
			img.set_from_file(path_to_kbd_input_img)
			rename_menuitem.set_image(img)

		muc_icon = self.load_icon('muc_active')
		if muc_icon:
			invite_menuitem.set_image(muc_icon)

		above_subscription_separator = xml.get_widget(
			'above_subscription_separator')
		subscription_menuitem = xml.get_widget('subscription_menuitem')
		send_auth_menuitem, ask_auth_menuitem, revoke_auth_menuitem =\
			subscription_menuitem.get_submenu().get_children()
		add_to_roster_menuitem = xml.get_widget('add_to_roster_menuitem')
		remove_from_roster_menuitem = xml.get_widget(
			'remove_from_roster_menuitem')

		# skip a separator
		information_menuitem = xml.get_widget('information_menuitem')
		history_menuitem = xml.get_widget('history_menuitem')

		contacts = gajim.contacts.get_contact(account, jid)

		# Invite to
		invite_to_submenu = gtk.Menu()
		invite_menuitem.set_submenu(invite_to_submenu)
		invite_to_new_room_menuitem = gtk.ImageMenuItem(_('_New Group Chat'))
		icon = gtk.image_new_from_stock(gtk.STOCK_NEW, gtk.ICON_SIZE_MENU)
		invite_to_new_room_menuitem.set_image(icon)
		contact_transport = gajim.get_transport_name_from_jid(contact.jid)
		t = contact_transport or 'jabber' # transform None in 'jabber'
		if not gajim.connections[account].muc_jid.has_key(t):
			invite_to_new_room_menuitem.set_sensitive(False)
		invite_to_submenu.append(invite_to_new_room_menuitem)
		rooms = [] # a list of (room_jid, account) tuple
		for gc_control in gajim.interface.msg_win_mgr.get_controls(
		message_control.TYPE_GC) + \
		gajim.interface.minimized_controls[account].values():
			acct = gc_control.account
			room_jid = gc_control.room_jid
			if gajim.gc_connected[acct].has_key(room_jid) and \
			gajim.gc_connected[acct][room_jid] and \
			contact_transport == gajim.get_transport_name_from_jid(room_jid):
				rooms.append((room_jid, acct))
		if len(rooms):
			item = gtk.SeparatorMenuItem() # separator
			invite_to_submenu.append(item)

		# One or several resource, we do the same for send_custom_status
		status_menuitems = gtk.Menu()
		send_custom_status_menuitem.set_submenu(status_menuitems)
		iconset = gajim.config.get('iconset')
		path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
		for s in ['online', 'chat', 'away', 'xa', 'dnd', 'offline']:
			# icon MUST be different instance for every item
			state_images = self.load_iconset(path)
			status_menuitem = gtk.ImageMenuItem(helpers.get_uf_show(s))
			status_menuitem.connect('activate', self.on_send_custom_status,
				[(contact, account)], s)
			icon = state_images[s]
			status_menuitem.set_image(icon)
			status_menuitems.append(status_menuitem)
		if len(contacts) > 1: # several resources
			def resources_submenu(action, room_jid = None, room_account = None):
				''' Build a submenu with contact's resources.
				room_jid and room_account are for action self.on_invite_to_room '''
				sub_menu = gtk.Menu()

				iconset = gajim.config.get('iconset')
				if not iconset:
					iconset = gajim.config.DEFAULT_ICONSET
				path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
				for c in contacts:
					# icon MUST be different instance for every item
					state_images = self.load_iconset(path)
					item = gtk.ImageMenuItem('%s (%s)' % (c.resource,
						str(c.priority)))
					icon_name = helpers.get_icon_name_to_show(c, account)
					icon = state_images[icon_name]
					item.set_image(icon)
					sub_menu.append(item)
					if action == self.on_invite_to_room:
						item.connect('activate', action, [(c, account)],
							room_jid, room_account, c.resource)
					elif action == self.on_invite_to_new_room:
						item.connect('activate', action, [(c, account)], c.resource)
					else: # start_chat, execute_command
						item.connect('activate', action, c, account, c.resource)
				return sub_menu

			start_chat_menuitem.set_submenu(resources_submenu(
				self.on_open_chat_window))
			execute_command_menuitem.set_submenu(resources_submenu(
				self.on_execute_command))
			invite_to_new_room_menuitem.set_submenu(resources_submenu(
				self.on_invite_to_new_room))
			for (room_jid, room_account) in rooms:
				menuitem = gtk.MenuItem(room_jid.split('@')[0])
				menuitem.set_submenu(resources_submenu(self.on_invite_to_room,
					room_jid, room_account))
				invite_to_submenu.append(menuitem)

		else: # one resource
			start_chat_menuitem.connect('activate',
				self.on_open_chat_window, contact, account)
			# we cannot execute commands when the resource is unknown
			# TODO: that's true only if the entity is a contact,
			# TODO: we need to show this also for transports
			if contact.resource:
				execute_command_menuitem.connect('activate',
					self.on_execute_command, contact, account, contact.resource)
			else:
				execute_command_menuitem.hide()
				execute_command_menuitem.set_no_show_all(True)

			our_jid_other_resource = None
			if our_jid:
				# It's another resource of us, be sure to send invite to her
				our_jid_other_resource = contact.resource
			# Else this var is useless but harmless in next connect calls

			invite_to_new_room_menuitem.connect('activate',
				self.on_invite_to_new_room, [(contact, account)],
				our_jid_other_resource)
			for (room_jid, room_account) in rooms:
				menuitem = gtk.MenuItem(room_jid.split('@')[0])
				menuitem.connect('activate', self.on_invite_to_room,
					[(contact, account)], room_jid, room_account,
					our_jid_other_resource)
				invite_to_submenu.append(menuitem)

		if contact.resource:
			send_file_menuitem.connect('activate',
				self.on_send_file_menuitem_activate, account, contact)
		else: # if we do not have resource we cannot send file
			send_file_menuitem.hide()
			send_file_menuitem.set_no_show_all(True)

		send_single_message_menuitem.connect('activate',
			self.on_send_single_message_menuitem_activate, account, contact)

		rename_menuitem.connect('activate', self.on_rename, iter, tree_path)
		remove_from_roster_menuitem.connect('activate', self.on_req_usub,
			[(contact, account)])
		information_menuitem.connect('activate', self.on_info, contact,
			account)
		history_menuitem.connect('activate', self.on_history, contact,
			account)

		if _('Not in Roster') not in contact.groups:
			#contact is in normal group
			edit_groups_menuitem.set_no_show_all(False)
			assign_openpgp_key_menuitem.set_no_show_all(False)
			add_to_roster_menuitem.hide()
			add_to_roster_menuitem.set_no_show_all(True)
			edit_groups_menuitem.connect('activate', self.on_edit_groups, [(
				contact,account)])

			if gajim.config.get('usegpg'):
				assign_openpgp_key_menuitem.connect('activate',
					self.on_assign_pgp_key, contact, account)

			if contact.sub in ('from', 'both'):
				send_auth_menuitem.set_sensitive(False)
			else:
				send_auth_menuitem.connect('activate', self.authorize, jid, account)
			if contact.sub in ('to', 'both'):
				ask_auth_menuitem.set_sensitive(False)
				add_special_notification_menuitem.connect('activate',
					self.on_add_special_notification_menuitem_activate, jid)
			else:
				ask_auth_menuitem.connect('activate', self.req_sub, jid,
					_('I would like to add you to my roster'), account,
					contact.groups, contact.name)
			if contact.sub in ('to', 'none'):
				revoke_auth_menuitem.set_sensitive(False)
			else:
				revoke_auth_menuitem.connect('activate', self.revoke_auth, jid,
					account)

		else: # contact is in group 'Not in Roster'
			add_to_roster_menuitem.set_no_show_all(False)
			edit_groups_menuitem.hide()
			edit_groups_menuitem.set_no_show_all(True)
			# hide first of the two consecutive separators
			above_send_file_separator.hide()
			above_send_file_separator.set_no_show_all(True)
			assign_openpgp_key_menuitem.hide()
			assign_openpgp_key_menuitem.set_no_show_all(True)
			subscription_menuitem.hide()
			subscription_menuitem.set_no_show_all(True)

			add_to_roster_menuitem.connect('activate',
				self.on_add_to_roster, contact, account)

		# Remove many items when it's self contact row
		if our_jid:
			menuitem = xml.get_widget('manage_contact')
			menuitem.set_no_show_all(True)
			menuitem.hide()

		# Unsensitive many items when account is offline
		if gajim.connections[account].connected < 2:
			for widget in [start_chat_menuitem, send_single_message_menuitem,
			rename_menuitem, edit_groups_menuitem, send_file_menuitem,
			subscription_menuitem, add_to_roster_menuitem,
			remove_from_roster_menuitem, execute_command_menuitem]:
				widget.set_sensitive(False)

		if gajim.connections[account] and gajim.connections[account].\
			privacy_rules_supported:
			if jid in gajim.connections[account].blocked_contacts:
					block_menuitem.set_no_show_all(True)
					unblock_menuitem.connect('activate', self.on_unblock, iter, None)
					block_menuitem.hide()
			else:
					unblock_menuitem.set_no_show_all(True)
					block_menuitem.connect('activate', self.on_block, iter, None)
					unblock_menuitem.hide()
		else:
			unblock_menuitem.set_no_show_all(True)
			block_menuitem.set_sensitive(False)
			unblock_menuitem.hide()

		event_button = gtkgui_helpers.get_possible_button_event(event)

		roster_contact_context_menu.attach_to_widget(self.tree, None)
		roster_contact_context_menu.connect('selection-done',
			gtkgui_helpers.destroy_widget)
		roster_contact_context_menu.show_all()
		roster_contact_context_menu.popup(None, None, None, event_button,
			event.time)

	def on_invite_to_new_room(self, widget, list_, resource = None):
		''' resource parameter MUST NOT be used if more than one contact in
		list '''
		account_list = []
		jid_list = []
		for (contact, account) in list_:
			if contact.jid not in jid_list:
				if resource: # we MUST have one contact only in list_
					fjid = contact.jid + '/' + resource
					jid_list.append(fjid)
				else:
					jid_list.append(contact.jid)
			if account not in account_list:
				account_list.append(account)
		# transform None in 'jabber'
		type_ = gajim.get_transport_name_from_jid(jid_list[0]) or 'jabber'
		for account in account_list:
			if gajim.connections[account].muc_jid[type_]:
				# create the room on this muc server
				if gajim.interface.instances[account].has_key('join_gc'):
					gajim.interface.instances[account]['join_gc'].window.destroy()
				try:
					gajim.interface.instances[account]['join_gc'] = \
						dialogs.JoinGroupchatWindow(account,
							gajim.connections[account].muc_jid[type_],
							automatic = {'invities': jid_list})
				except GajimGeneralException:
					continue
				break

	def on_invite_to_room(self, widget, list_, room_jid, room_account,
		resource = None):
		''' resource parameter MUST NOT be used if more than one contact in
		list '''
		for (contact, acct) in list_:
			contact_jid = contact.jid
			if resource: # we MUST have one contact only in list_
				contact_jid += '/' + resource
			gajim.connections[room_account].send_invite(room_jid, contact_jid)


	def make_multiple_contact_menu(self, event, iters):
		'''Make group's popup menu'''
		model = self.tree.get_model()
		list_ = [] # list of (jid, account) tuples
		one_account_offline = False
		connected_accounts = []
		contacts_transport = -1
		# -1 is at start, False when not from the same, None when jabber
		is_blocked = True
		for iter in iters:
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			if gajim.connections[account].connected < 2:
				one_account_offline = True
			elif not account in connected_accounts:
				connected_accounts.append(account)
			contact = gajim.contacts.get_contact_with_highest_priority(account,
				jid)
			transport = gajim.get_transport_name_from_jid(contact.jid)
			if contacts_transport == -1:
				contacts_transport = transport
			if contacts_transport != transport:
				contacts_transport = False
			if jid not in gajim.connections[account].blocked_contacts:
				is_blocked = False
			list_.append((contact, account))

		menu = gtk.Menu()
		account = None
		for (contact, current_account) in list_:
			# check that we use the same account for every sender
			if account is not None and account != current_account:
				account = None
				break
			account = current_account
		if account is not None:
			send_group_message_item = gtk.ImageMenuItem(_('Send Group M_essage'))
			icon = gtk.image_new_from_stock(gtk.STOCK_NEW, gtk.ICON_SIZE_MENU)
			send_group_message_item.set_image(icon)
			menu.append(send_group_message_item)
			send_group_message_item.connect('activate',
				self.on_send_single_message_menuitem_activate, account, list_)
		
		# Invite to Groupchat
		invite_item = gtk.ImageMenuItem(_('In_vite to'))
		muc_icon = self.load_icon('muc_active')
		if muc_icon:
			invite_item.set_image(muc_icon)

		if contacts_transport == False:
			# they are not all from the same transport
			invite_item.set_sensitive(False)
		else:

			sub_menu = gtk.Menu()
			menuitem = gtk.ImageMenuItem(_('_New group chat'))
			icon = gtk.image_new_from_stock(gtk.STOCK_NEW, gtk.ICON_SIZE_MENU)
			menuitem.set_image(icon)
			menuitem.connect('activate', self.on_invite_to_new_room, list_)
			muc_jid = {}
			c_t = contacts_transport or 'jabber' # transform None in 'jabber'
			for account in connected_accounts:
				for t in gajim.connections[account].muc_jid:
					muc_jid[t] = gajim.connections[account].muc_jid[t]
			if not muc_jid.has_key(c_t):
				menuitem.set_sensitive(False)
			sub_menu.append(menuitem)
			rooms = [] # a list of (room_jid, account) tuple
			for gc_control in gajim.interface.msg_win_mgr.get_controls(
			message_control.TYPE_GC) + \
			gajim.interface.minimized_controls[account].values():
				account = gc_control.account
				room_jid = gc_control.room_jid
				if gajim.gc_connected[account].has_key(room_jid) and \
				gajim.gc_connected[account][room_jid] and \
				contacts_transport == gajim.get_transport_name_from_jid(room_jid):
					rooms.append((room_jid, account))
			if len(rooms):
				item = gtk.SeparatorMenuItem() # separator
				sub_menu.append(item)
				for (room_jid, account) in rooms:
					menuitem = gtk.MenuItem(room_jid.split('@')[0])
					menuitem.connect('activate', self.on_invite_to_room, list_,
						room_jid, account)
					sub_menu.append(menuitem)

			invite_item.set_submenu(sub_menu)
		menu.append(invite_item)

		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		# Edit Groups
		edit_groups_item = gtk.ImageMenuItem(_('Edit _Groups'))
		icon = gtk.image_new_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
		edit_groups_item.set_image(icon)
		menu.append(edit_groups_item)
		edit_groups_item.connect('activate', self.on_edit_groups, list_)

		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		# Block
		if is_blocked and gajim.connections[account].privacy_rules_supported:
			unblock_menuitem = gtk.ImageMenuItem(_('_Unblock'))
			icon = gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_MENU)
			unblock_menuitem.set_image(icon)
			unblock_menuitem.connect('activate', self.on_unblock, None, list_)
			menu.append(unblock_menuitem)
		else:
			block_menuitem = gtk.ImageMenuItem(_('_Block'))
			icon = gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_MENU)
			block_menuitem.set_image(icon)
			block_menuitem.connect('activate', self.on_block, None, list_)
			menu.append(block_menuitem)

			if not gajim.connections[account].privacy_rules_supported:
				block_menuitem.set_sensitive(False)

		# Remove 
		remove_item = gtk.ImageMenuItem(_('_Remove from Roster'))
		icon = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
		remove_item.set_image(icon)
		menu.append(remove_item)
		remove_item.connect('activate', self.on_req_usub, list_)
		# unsensitive remove if one account is not connected
		if one_account_offline:
			remove_item.set_sensitive(False)

		event_button = gtkgui_helpers.get_possible_button_event(event)

		menu.attach_to_widget(self.tree, None)
		menu.connect('selection-done', gtkgui_helpers.destroy_widget)
		menu.show_all()
		menu.popup(None, None, None, event_button, event.time)

	def make_groupchat_menu(self, event, iter):
		model = self.tree.get_model()

		path = model.get_path(iter)
		jid = model[iter][C_JID].decode('utf-8')
		account = model[iter][C_ACCOUNT].decode('utf-8')
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		menu = gtk.Menu()

		if jid in gajim.interface.minimized_controls[account]:
			maximize_menuitem = gtk.ImageMenuItem(_('_Maximize'))
			icon = gtk.image_new_from_stock(gtk.STOCK_GOTO_TOP, gtk.ICON_SIZE_MENU)
			maximize_menuitem.set_image(icon)
			maximize_menuitem.connect('activate', self.on_groupchat_maximized, \
				jid, account)
			menu.append(maximize_menuitem)

		history_menuitem = gtk.ImageMenuItem(_('_History'))
		history_icon = gtk.image_new_from_stock(gtk.STOCK_JUSTIFY_FILL, \
			gtk.ICON_SIZE_MENU)
		history_menuitem.set_image(history_icon)
		history_menuitem .connect('activate', self.on_history, \
				contact, account)
		menu.append(history_menuitem)

		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		disconnect_menuitem = gtk.ImageMenuItem(_('_Disconnect'))
		disconnect_icon = gtk.image_new_from_stock(gtk.STOCK_DISCONNECT, \
			gtk.ICON_SIZE_MENU)
		disconnect_menuitem.set_image(disconnect_icon)
		disconnect_menuitem .connect('activate', self.on_disconnect, jid, account)
		menu.append(disconnect_menuitem)

		event_button = gtkgui_helpers.get_possible_button_event(event)

		menu.attach_to_widget(self.tree, None)
		menu.connect('selection-done', gtkgui_helpers.destroy_widget)
		menu.show_all()
		menu.popup(None, None, None, event_button, event.time)

	def on_all_groupchat_maximized(self, widget, group_list):
		for (contact, account) in group_list:
			self.on_groupchat_maximized(widget, contact.jid, account)


	def on_groupchat_maximized(self, widget, jid, account):
		'''When a groupchat is maximised'''
		if not gajim.interface.minimized_controls[account].has_key(jid):
			return


		ctrl = gajim.interface.minimized_controls[account][jid]
		mw = gajim.interface.msg_win_mgr.get_window(ctrl.contact.jid, ctrl.account)
		if not mw:
			mw = gajim.interface.msg_win_mgr.create_window(ctrl.contact, \
				ctrl.account, ctrl.type_id)
		ctrl.parent_win = mw
		mw.new_tab(ctrl)
		mw.set_active_tab(jid, account)
		mw.window.present()
		del gajim.interface.minimized_controls[account][jid]

		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if not contact:
			return
		if contact.groups == [_('Groupchats')]:
			self.remove_contact(contact, account)
			gajim.contacts.remove_contact(account, contact)
			self.draw_group(_('Groupchats'), account)

	def make_group_menu(self, event, iter):
		'''Make group's popup menu'''
		model = self.tree.get_model()
		path = model.get_path(iter)
		group = model[iter][C_JID].decode('utf-8')
		account = model[iter][C_ACCOUNT].decode('utf-8')

		list_ = [] # list of (jid, account) tuples
		list_online = [] # list of (jid, account) tuples

		group = model[iter][C_JID]
		for jid in gajim.contacts.get_jid_list(account):
			contact = gajim.contacts.get_contact_with_highest_priority(account,
					jid)
			if group in contact.groups or (contact.groups == [] and group == \
			_('General')):
				if contact.show not in ('offline', 'error'):
					list_online.append((contact, account))
				list_.append((contact, account))
		menu = gtk.Menu()

		# Make special context menu if group is Groupchats
		if group == _('Groupchats'):
			maximize_menuitem = gtk.ImageMenuItem(_('_Maximize All'))
			icon = gtk.image_new_from_stock(gtk.STOCK_GOTO_TOP, gtk.ICON_SIZE_MENU)
			maximize_menuitem.set_image(icon)
			maximize_menuitem.connect('activate', self.on_all_groupchat_maximized, \
				list_)
			menu.append(maximize_menuitem)
		else:
			# Send Group Message
			send_group_message_item = gtk.ImageMenuItem(_('Send Group M_essage'))
			icon = gtk.image_new_from_stock(gtk.STOCK_NEW, gtk.ICON_SIZE_MENU)
			send_group_message_item.set_image(icon)

			send_group_message_submenu = gtk.Menu()
			send_group_message_item.set_submenu(send_group_message_submenu)
			menu.append(send_group_message_item)

			group_message_to_all_item = gtk.MenuItem(_('To all users'))
			send_group_message_submenu.append(group_message_to_all_item)

			group_message_to_all_online_item = gtk.MenuItem(_('To all online users'))
			send_group_message_submenu.append(group_message_to_all_online_item)

			group_message_to_all_online_item.connect('activate',
				self.on_send_single_message_menuitem_activate, account, list_online)
			group_message_to_all_item.connect('activate',
				self.on_send_single_message_menuitem_activate, account, list_)

			# Send Custom Status
			send_custom_status_menuitem = gtk.ImageMenuItem(_('Send Cus_tom Status'))
			# add a special img for this menuitem
			if group in gajim.connections[account].blocked_groups:
				send_custom_status_menuitem.set_image(self.load_icon('offline'))
				send_custom_status_menuitem.set_sensitive(False)
			elif gajim.interface.status_sent_to_groups.has_key(account) and \
			group in gajim.interface.status_sent_to_groups[account]:
				send_custom_status_menuitem.set_image(self.load_icon(
					gajim.interface.status_sent_to_groups[account][group]))
			else:
				send_custom_status_menuitem.set_image(None)
			status_menuitems = gtk.Menu()
			send_custom_status_menuitem.set_submenu(status_menuitems)
			iconset = gajim.config.get('iconset')
			path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
			for s in ['online', 'chat', 'away', 'xa', 'dnd', 'offline']:
				# icon MUST be different instance for every item
				state_images = self.load_iconset(path)
				status_menuitem = gtk.ImageMenuItem(helpers.get_uf_show(s))
				status_menuitem.connect('activate', self.on_send_custom_status, list_,
					s, group)
				icon = state_images[s]
				status_menuitem.set_image(icon)
				status_menuitems.append(status_menuitem)
			menu.append(send_custom_status_menuitem)

		if not group in helpers.special_groups + (_('General'),):
			item = gtk.SeparatorMenuItem() # separator
			menu.append(item)

			# Rename
			rename_item = gtk.ImageMenuItem(_('Re_name'))
			# add a special img for rename menuitem
			path_to_kbd_input_img = os.path.join(gajim.DATA_DIR, 'pixmaps',
				'kbd_input.png')
			img = gtk.Image()
			img.set_from_file(path_to_kbd_input_img)
			rename_item.set_image(img)
			menu.append(rename_item)
			rename_item.connect('activate', self.on_rename, iter, path)

			# Block group
			is_blocked = False
			if self.regroup:
				for g_account in gajim.connections:
					if group in gajim.connections[g_account].blocked_groups:
						is_blocked = True
			else:
				if group in gajim.connections[account].blocked_groups:
					is_blocked = True

			if is_blocked and gajim.connections[account].privacy_rules_supported:
				unblock_menuitem = gtk.ImageMenuItem(_('_Unblock'))
				icon = gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_MENU)
				unblock_menuitem.set_image(icon)
				unblock_menuitem.connect('activate', self.on_unblock, iter, list_)
				menu.append(unblock_menuitem)
			else:
				block_menuitem = gtk.ImageMenuItem(_('_Block'))
				icon = gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_MENU)
				block_menuitem.set_image(icon)
				block_menuitem.connect('activate', self.on_block, iter, list_)
				menu.append(block_menuitem)
				if not gajim.connections[account].privacy_rules_supported:
					block_menuitem.set_sensitive(False)

			# Remove group
			remove_item = gtk.ImageMenuItem(_('_Remove from Roster'))
			icon = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
			remove_item.set_image(icon)
			menu.append(remove_item)
			remove_item.connect('activate', self.on_remove_group_item_activated,
				group, account)
			# unsensitive if account is not connected
			if gajim.connections[account].connected < 2:
				rename_item.set_sensitive(False)

		event_button = gtkgui_helpers.get_possible_button_event(event)

		menu.attach_to_widget(self.tree, None)
		menu.connect('selection-done', gtkgui_helpers.destroy_widget)
		menu.show_all()
		menu.popup(None, None, None, event_button, event.time)

	def make_transport_menu(self, event, iter):
		'''Make transport's popup menu'''
		model = self.tree.get_model()
		jid = model[iter][C_JID].decode('utf-8')
		path = model.get_path(iter)
		account = model[iter][C_ACCOUNT].decode('utf-8')
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		menu = gtk.Menu()

		# Log on
		item = gtk.ImageMenuItem(_('_Log on'))
		icon = gtk.image_new_from_stock(gtk.STOCK_YES, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		show = contact.show
		if (show != 'offline' and show != 'error') or\
			gajim.account_is_disconnected(account):
			item.set_sensitive(False)
		item.connect('activate', self.on_agent_logging, jid, None, account)

		# Log off
		item = gtk.ImageMenuItem(_('Log _off'))
		icon = gtk.image_new_from_stock(gtk.STOCK_NO, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		if show in ('offline', 'error') or gajim.account_is_disconnected(
			account):
			item.set_sensitive(False)
		item.connect('activate', self.on_agent_logging, jid, 'unavailable',
			account)

		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		# Execute Command
		item = gtk.ImageMenuItem(_('Execute Command...'))
		icon = gtk.image_new_from_stock(gtk.STOCK_EXECUTE, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		item.connect('activate', self.on_execute_command, contact, account,
			contact.resource)
		if gajim.account_is_disconnected(account):
			item.set_sensitive(False)

		# Edit
		item = gtk.ImageMenuItem(_('_Edit'))
		icon = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		item.connect('activate', self.on_edit_agent, contact, account)
		if gajim.account_is_disconnected(account):
			item.set_sensitive(False)

		# Rename
		item = gtk.ImageMenuItem(_('_Rename'))
		# add a special img for rename menuitem
		path_to_kbd_input_img = os.path.join(gajim.DATA_DIR, 'pixmaps',
			'kbd_input.png')
		img = gtk.Image()
		img.set_from_file(path_to_kbd_input_img)
		item.set_image(img)
		menu.append(item)
		item.connect('activate', self.on_rename, iter, path)
		if gajim.account_is_disconnected(account):
			item.set_sensitive(False)
		
		item = gtk.SeparatorMenuItem() # sepator
		menu.append(item)

		# Remove
		item = gtk.ImageMenuItem(_('_Remove from Roster'))
		icon = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		menu.append(item)
		item.connect('activate', self.on_remove_agent, [(contact, account)])
		if gajim.account_is_disconnected(account):
			item.set_sensitive(False)

		information_menuitem = gtk.ImageMenuItem(_('_Information'))
		icon = gtk.image_new_from_stock(gtk.STOCK_INFO, gtk.ICON_SIZE_MENU)
		information_menuitem.set_image(icon)
		menu.append(information_menuitem)
		information_menuitem.connect('activate', self.on_info, contact, account)


		event_button = gtkgui_helpers.get_possible_button_event(event)

		menu.attach_to_widget(self.tree, None)
		menu.connect('selection-done', gtkgui_helpers.destroy_widget)
		menu.show_all()
		menu.popup(None, None, None, event_button, event.time)

	def on_edit_account(self, widget, account):
		if gajim.interface.instances[account].has_key('account_modification'):
			gajim.interface.instances[account]['account_modification'].\
			window.present()
		else:
			gajim.interface.instances[account]['account_modification'] = \
				config.AccountModificationWindow(account)

	def on_zeroconf_properties(self, widget, account):
		if gajim.interface.instances.has_key('zeroconf_properties'):
			gajim.interface.instances['zeroconf_properties'].\
			window.present()
		else:
			gajim.interface.instances['zeroconf_properties'] = \
				config.ZeroconfPropertiesWindow()

	def on_open_gmail_inbox(self, widget, account):
		url = 'http://mail.google.com/mail?account_id=%s' % urllib.quote(
			gajim.config.get_per('accounts', account, 'name'))
		helpers.launch_browser_mailer('url', url)

	def on_change_status_message_activate(self, widget, account):
		show = gajim.SHOW_LIST[gajim.connections[account].connected]
		dlg = dialogs.ChangeStatusMessageDialog(show)
		message = dlg.run()
		if message is not None: # None is if user pressed Cancel
			self.send_status(account, show, message)

	def build_account_menu(self, account):
		# we have to create our own set of icons for the menu
		# using self.jabber_status_images is poopoo
		iconset = gajim.config.get('iconset')
		path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
		state_images = self.load_iconset(path)

		if not gajim.config.get_per('accounts', account, 'is_zeroconf'):
			xml = gtkgui_helpers.get_glade('account_context_menu.glade')
			account_context_menu = xml.get_widget('account_context_menu')

			status_menuitem = xml.get_widget('status_menuitem')
			join_group_chat_menuitem = xml.get_widget('join_group_chat_menuitem')
			muc_icon = self.load_icon('muc_active')
			if muc_icon:
				join_group_chat_menuitem.set_image(muc_icon)
			open_gmail_inbox_menuitem = xml.get_widget('open_gmail_inbox_menuitem')
			add_contact_menuitem = xml.get_widget('add_contact_menuitem')
			service_discovery_menuitem = xml.get_widget(
				'service_discovery_menuitem')
			execute_command_menuitem = xml.get_widget('execute_command_menuitem')
			edit_account_menuitem = xml.get_widget('edit_account_menuitem')
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
			path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'kbd_input.png')
			img = gtk.Image()
			img.set_from_file(path)
			item.set_image(img)
			sub_menu.append(item)
			item.connect('activate', self.on_change_status_message_activate,
				account)
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

			if gajim.config.get_per('accounts', account, 'hostname') not in \
			gajim.gmail_domains:
				open_gmail_inbox_menuitem.set_no_show_all(True)
				open_gmail_inbox_menuitem.hide()
			else:
				open_gmail_inbox_menuitem.connect('activate',
					self.on_open_gmail_inbox, account)

			edit_account_menuitem.connect('activate', self.on_edit_account,
				account)
			add_contact_menuitem.connect('activate', self.on_add_new_contact,
				account)
			service_discovery_menuitem.connect('activate',
				self.on_service_disco_menuitem_activate, account)
			hostname = gajim.config.get_per('accounts', account, 'hostname')
			contact = gajim.contacts.create_contact(jid = hostname) # Fake contact
			execute_command_menuitem.connect('activate',
				self.on_execute_command, contact, account)

			gc_sub_menu = gtk.Menu() # gc is always a submenu
			join_group_chat_menuitem.set_submenu(gc_sub_menu)
			self.add_bookmarks_list(gc_sub_menu, account)

			# make some items insensitive if account is offline
			if gajim.connections[account].connected < 2:
				for widget in [add_contact_menuitem, service_discovery_menuitem,
				join_group_chat_menuitem,
				execute_command_menuitem]:
					widget.set_sensitive(False)
		else:
			xml = gtkgui_helpers.get_glade('zeroconf_context_menu.glade')
			account_context_menu = xml.get_widget('zeroconf_context_menu')

			status_menuitem = xml.get_widget('status_menuitem')
			zeroconf_properties_menuitem = xml.get_widget(
				'zeroconf_properties_menuitem')
			sub_menu = gtk.Menu()
			status_menuitem.set_submenu(sub_menu)

			for show in ('online', 'away', 'dnd', 'invisible'):
				uf_show = helpers.get_uf_show(show, use_mnemonic = True)
				item = gtk.ImageMenuItem(uf_show)
				icon = state_images[show]
				item.set_image(icon)
				sub_menu.append(item)
				item.connect('activate', self.change_status, account, show)

			item = gtk.SeparatorMenuItem()
			sub_menu.append(item)

			item = gtk.ImageMenuItem(_('_Change Status Message'))
			path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'kbd_input.png')
			img = gtk.Image()
			img.set_from_file(path)
			item.set_image(img)
			sub_menu.append(item)
			item.connect('activate', self.on_change_status_message_activate,
				account)
			if gajim.connections[account].connected < 2:
				item.set_sensitive(False)

			uf_show = helpers.get_uf_show('offline', use_mnemonic = True)
			item = gtk.ImageMenuItem(uf_show)
			icon = state_images['offline']
			item.set_image(icon)
			sub_menu.append(item)
			item.connect('activate', self.change_status, account, 'offline')

			zeroconf_properties_menuitem.connect('activate',
				self.on_zeroconf_properties, account)
			#gc_sub_menu = gtk.Menu() # gc is always a submenu
			#join_group_chat_menuitem.set_submenu(gc_sub_menu)
			#self.add_bookmarks_list(gc_sub_menu, account)
			#new_message_menuitem.connect('activate',
			#	self.on_new_message_menuitem_activate, account)

			# make some items insensitive if account is offline
			#if gajim.connections[account].connected < 2:
			#	for widget in [join_group_chat_menuitem, new_message_menuitem]:
			#		widget.set_sensitive(False)
			#	new_message_menuitem.set_sensitive(False)

		return account_context_menu

	def make_account_menu(self, event, iter):
		'''Make account's popup menu'''
		model = self.tree.get_model()
		account = model[iter][C_ACCOUNT].decode('utf-8')

		if account != 'all': # not in merged mode
			menu = self.build_account_menu(account)
		else:
			menu = gtk.Menu()
			iconset = gajim.config.get('iconset')
			path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
			accounts = [] # Put accounts in a list to sort them
			for account in gajim.connections:
				accounts.append(account)
			accounts.sort()
			for account in accounts:
				state_images = self.load_iconset(path)
				item = gtk.ImageMenuItem(account)
				show = gajim.SHOW_LIST[gajim.connections[account].connected]
				icon = state_images[show]
				item.set_image(icon)
				account_menu = self.build_account_menu(account)
				item.set_submenu(account_menu)
				menu.append(item)

		event_button = gtkgui_helpers.get_possible_button_event(event)

		menu.attach_to_widget(self.tree, None)
		menu.connect('selection-done', gtkgui_helpers.destroy_widget)
		menu.show_all()
		menu.popup(None, self.tree, None, event_button, event.time)

	def on_add_to_roster(self, widget, contact, account):
		dialogs.AddNewContactWindow(account, contact.jid, contact.name)

	def authorize(self, widget, jid, account):
		'''Authorize a contact (by re-sending auth menuitem)'''
		gajim.connections[account].send_authorization(jid)
		dialogs.InformationDialog(_('Authorization has been sent'),
			_('Now "%s" will know your status.') %jid)

	def req_sub(self, widget, jid, txt, account, groups = [], nickname = None,
	auto_auth = False):
		'''Request subscription to a contact'''
		gajim.connections[account].request_subscription(jid, txt, nickname,
			groups, auto_auth, gajim.nicks[account])
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if not contact:
			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]
			contact = gajim.contacts.create_contact(jid = jid, name = nickname,
				groups = groups, show = 'requested', status = '', ask = 'none',
				sub = 'subscribe', keyID = keyID)
			gajim.contacts.add_contact(account, contact)
		else:
			if not _('Not in Roster') in contact.groups:
				dialogs.InformationDialog(_('Subscription request has been sent'),
					_('If "%s" accepts this request you will know his or her status.'
					) % jid)
				return
			contact.groups = groups
			if nickname:
				contact.name = nickname
			self.remove_contact(contact, account)
		self.add_contact_to_roster(jid, account)

	def revoke_auth(self, widget, jid, account):
		'''Revoke a contact's authorization'''
		gajim.connections[account].refuse_authorization(jid)
		dialogs.InformationDialog(_('Authorization has been removed'),
			_('Now "%s" will always see you as offline.') %jid)

	def on_roster_treeview_scroll_event(self, widget, event):
		self.tooltip.hide_tooltip()

	def on_roster_treeview_key_press_event(self, widget, event):
		'''when a key is pressed in the treeviews'''
		self.tooltip.hide_tooltip()
		if event.keyval == gtk.keysyms.Escape:
			self.tree.get_selection().unselect_all()
		elif event.keyval == gtk.keysyms.F2:
			treeselection = self.tree.get_selection()
			model, list_of_paths = treeselection.get_selected_rows()
			if len(list_of_paths) != 1:
				return
			path = list_of_paths[0]
			type_ = model[path][C_TYPE]
			if type_ in ('contact', 'group', 'agent'):
				iter = model.get_iter(path)
				self.on_rename(widget, iter, path)

		elif event.keyval == gtk.keysyms.Delete:
			treeselection = self.tree.get_selection()
			model, list_of_paths = treeselection.get_selected_rows()
			if not len(list_of_paths):
				return
			type_ = model[list_of_paths[0]][C_TYPE]
			account = model[list_of_paths[0]][C_ACCOUNT]
			list_ = []
			for path in list_of_paths:
				if model[path][C_TYPE] != type_:
					return
				jid = model[path][C_JID].decode('utf-8')
				account = model[path][C_ACCOUNT].decode('utf-8')
				contact = gajim.contacts.get_contact_with_highest_priority(account,
					jid)
				list_.append((contact, account))
			if type_ in ('account', 'group', 'self_contact') or \
			account == gajim.ZEROCONF_ACC_NAME:
				return
			if type_ == 'contact':
				self.on_req_usub(widget, list_)
			elif type_ == 'agent':
				self.on_remove_agent(widget, list_)

	def show_appropriate_context_menu(self, event, iters):
		# iters must be all of the same type
		model = self.tree.get_model()
		type_ = model[iters[0]][C_TYPE]
		for iter in iters[1:]:
			if model[iter][C_TYPE] != type_:
				return
		if type_ == 'group' and len(iters) == 1:
			self.make_group_menu(event, iters[0])
		if type_ == 'groupchat' and len(iters) == 1:
			self.make_groupchat_menu(event, iters[0])
		elif type_ == 'agent' and len(iters) == 1:
			self.make_transport_menu(event, iters[0])
		elif type_ in ('contact', 'self_contact') and len(iters) == 1:
			self.make_contact_menu(event, iters[0])
		elif type_  == 'contact':
			self.make_multiple_contact_menu(event, iters)
		elif type_ == 'account' and len(iters) == 1:
			self.make_account_menu(event, iters[0])

	def show_treeview_menu(self, event):
		try:
			model, list_of_paths = self.tree.get_selection().get_selected_rows()
		except TypeError:
			self.tree.get_selection().unselect_all()
			return
		if not len(list_of_paths):
			# no row is selected
			return
		if len(list_of_paths) > 1:
			iters = []
			for path in list_of_paths:
				iters.append(model.get_iter(path))
		else:
			path = list_of_paths[0]
			iters = [model.get_iter(path)]
		self.show_appropriate_context_menu(event, iters)

		return True

	def on_roster_treeview_button_press_event(self, widget, event):
		# hide tooltip, no matter the button is pressed
		self.tooltip.hide_tooltip()
		try:
			path, column, x, y = self.tree.get_path_at_pos(int(event.x),
				int(event.y))
		except TypeError:
			self.tree.get_selection().unselect_all()
			return False

		if event.button == 3: # Right click
			try:
				model, list_of_paths = self.tree.get_selection().get_selected_rows()
			except TypeError:
				list_of_paths = []
				pass
			if path not in list_of_paths:
				self.tree.get_selection().unselect_all()
				self.tree.get_selection().select_path(path)
			return self.show_treeview_menu(event)

		elif event.button == 2: # Middle click
			try:
				model, list_of_paths = self.tree.get_selection().get_selected_rows()
			except TypeError:
				list_of_paths = []
				pass
			if list_of_paths != [path]:
				self.tree.get_selection().unselect_all()
				self.tree.get_selection().select_path(path)
			type_ = model[path][C_TYPE]
			if type_ in ('agent', 'contact', 'self_contact', 'groupchat'):
				self.on_row_activated(widget, path)
			elif type_ == 'account':
				account = model[path][C_ACCOUNT].decode('utf-8')
				if account != 'all':
					show = gajim.connections[account].connected
					if show > 1: # We are connected
						self.on_change_status_message_activate(widget, account)
					return True
				show = helpers.get_global_show()
				if show == 'offline':
					return True
				dlg = dialogs.ChangeStatusMessageDialog(show)
				message = dlg.run()
				if not message:
					return True
				for acct in gajim.connections:
					if not gajim.config.get_per('accounts', acct,
					'sync_with_global_status'):
						continue
					current_show = gajim.SHOW_LIST[gajim.connections[acct].connected]
					self.send_status(acct, current_show, message)
			return True

		elif event.button == 1: # Left click
			model = self.tree.get_model()
			type_ = model[path][C_TYPE]
			if gajim.single_click and not event.state & gtk.gdk.SHIFT_MASK and \
			not event.state & gtk.gdk.CONTROL_MASK:
				self.on_row_activated(widget, path)
			else:
				if type_ == 'group' and x < 27:
					# first cell in 1st column (the arrow SINGLE clicked)
					if (self.tree.row_expanded(path)):
						self.tree.collapse_row(path)
					else:
						self.tree.expand_row(path, False)

				elif type_ == 'contact' and x < 27:
					account = model[path][C_ACCOUNT].decode('utf-8')
					jid = model[path][C_JID].decode('utf-8')
					# first cell in 1st column (the arrow SINGLE clicked)
					iters = self.get_contact_iter(jid, account)
					for iter in iters:
						path = model.get_path(iter)
						if (self.tree.row_expanded(path)):
							self.tree.collapse_row(path)
						else:
							self.tree.expand_row(path, False)

	def on_req_usub(self, widget, list_):
		'''Remove a contact. list_ is a list of (contact, account) tuples'''
		def on_ok(widget, list_):
			self.dialog.destroy()
			remove_auth = True
			if len(list_) == 1:
				contact = list_[0][0]
				if contact.sub != 'to' and self.dialog.is_checked():
					remove_auth = False
			for (contact, account) in list_:
				gajim.connections[account].unsubscribe(contact.jid, remove_auth)
				for c in gajim.contacts.get_contact(account, contact.jid):
					self.remove_contact(c, account)
				gajim.contacts.remove_jid(account, contact.jid)
				# redraw group rows for contact numbers
				for group in c.groups:
					self.draw_group(group, account)
				# redraw account rows for contact numbers
				self.draw_account(account)
				if not remove_auth and contact.sub == 'both':
					contact.name = ''
					contact.groups = []
					contact.sub = 'from'
					gajim.contacts.add_contact(account, contact)
					self.add_contact_to_roster(contact.jid, account)
				else:
					if _('Not in Roster') in contact.groups:
						gajim.events.remove_events(account, contact.jid)
					self.readd_if_needed(contact, account)
		if len(list_) == 1:
			contact = list_[0][0]
			account = list_[0][1]
			pritext = _('Contact "%s" will be removed from your roster') % \
				contact.get_shown_name()
			if contact.sub == 'to':
				self.dialog = dialogs.ConfirmationDialog(pritext,
					_('By removing this contact you also remove authorization '
					'resulting in him or her always seeing you as offline.'),
					on_response_ok = (on_ok, list_))
			else:
				self.dialog = dialogs.ConfirmationDialogCheck(pritext,
					_('By removing this contact you also by default remove '
					'authorization resulting in him or her always seeing you as '
					'offline.'),
					_('I want this contact to know my status after removal'),
					on_response_ok = (on_ok, list_))
		else:
			# several contact to remove at the same time
			pritext = _('Contacts will be removed from your roster')
			jids = ''
			for (contact, account) in list_:
				jids += '\n  ' + contact.get_shown_name() + ','
			sectext = _('By removing these contacts:%s\nyou also remove '
				'authorization resulting in them always seeing you as offline.') % \
				jids
			self.dialog = dialogs.ConfirmationDialog(pritext, sectext,
				on_response_ok = (on_ok, list_))


	def forget_gpg_passphrase(self, keyid):
		if self.gpg_passphrase.has_key(keyid):
			del self.gpg_passphrase[keyid]
		return False

	def set_connecting_state(self, account):
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if accountIter:
			model[accountIter][0] =	self.jabber_state_images['16']['connecting']
		if gajim.interface.systray_enabled:
			gajim.interface.systray.change_status('connecting')

	def send_status(self, account, status, txt, auto = False, to = None):
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if status != 'offline':
			if gajim.connections[account].connected < 2:
				self.set_connecting_state(account)

				if not gajim.connections[account].password:
					passphrase = ''
					text = _('Enter your password for account %s') % account
					if passwords.USER_HAS_GNOMEKEYRING and \
					not passwords.USER_USES_GNOMEKEYRING:
						text += '\n' + _('Gnome Keyring is installed but not correctly started (environment variable probably not correctly set)')
					w = dialogs.PassphraseDialog(_('Password Required'), text,
						_('Save password'))
					passphrase, save = w.run()
					if passphrase == -1:
						if accountIter:
							model[accountIter][0] =	self.jabber_state_images['16']\
								['offline']
						if gajim.interface.systray_enabled:
							gajim.interface.systray.change_status('offline')
						self.update_status_combobox()
						return
					gajim.connections[account].password = passphrase
					if save:
						gajim.config.set_per('accounts', account, 'savepass', True)
						passwords.save_password(account, passphrase)

			keyid = None
			use_gpg_agent = gajim.config.get('use_gpg_agent')
			# we don't need to bother with the passphrase if we use the agent
			if use_gpg_agent:
				save_gpg_pass = False
			else:
				save_gpg_pass = gajim.config.get_per('accounts', account,
					'savegpgpass')
			keyid = gajim.config.get_per('accounts', account, 'keyid')
			if keyid and not gajim.config.get('usegpg'):
				#TODO: make this string translatable
				dialog = dialogs.WarningDialog('GPG is not usable', _('You will be connected to %s without OpenPGP.') % account)
			if keyid and gajim.connections[account].connected < 2 and \
				gajim.config.get('usegpg'):

				if use_gpg_agent:
					self.gpg_passphrase[keyid] = None
				else:
					if save_gpg_pass:
						passphrase = gajim.config.get_per('accounts', account,
							'gpgpassword')
					else:
						if self.gpg_passphrase.has_key(keyid):
							passphrase = self.gpg_passphrase[keyid]
							save = False
						else:
							password_ok = False
							count = 0
							title = _('Passphrase Required')
							second = _('Enter GPG key passphrase for account %s.') % \
								account
							while not password_ok and count < 3:
								count += 1
								w = dialogs.PassphraseDialog(title, second,
									_('Save passphrase'))
								passphrase, save = w.run()
								if passphrase == -1:
									passphrase = None
									password_ok = True
								else:
									password_ok = gajim.connections[account].\
										test_gpg_passphrase(passphrase)
									title = _('Wrong Passphrase')
									second = _('Please retype your GPG passphrase or '
										'press Cancel.')
							if passphrase != None:
								self.gpg_passphrase[keyid] = passphrase
								gobject.timeout_add(30000, self.forget_gpg_passphrase,
									keyid)
						if save:
							gajim.config.set_per('accounts', account, 'savegpgpass',
								True)
							gajim.config.set_per('accounts', account, 'gpgpassword',
								passphrase)
					gajim.connections[account].gpg_passphrase(passphrase)

		if gajim.account_is_connected(account):
			if status == 'online' and gajim.interface.sleeper.getState() != \
			common.sleepy.STATE_UNKNOWN:
				gajim.sleeper_state[account] = 'online'
			elif gajim.sleeper_state[account] not in ('autoaway', 'autoxa'):
				gajim.sleeper_state[account] = 'off'
		if to:
			gajim.connections[account].send_custom_status(status, txt, to)
		else:
			was_invisible = gajim.connections[account].connected == \
				gajim.SHOW_LIST.index('invisible')
			gajim.connections[account].change_status(status, txt, auto)

			if gajim.interface.status_sent_to_users.has_key(account):
				gajim.interface.status_sent_to_users[account] = {}
			if gajim.interface.status_sent_to_groups.has_key(account):
				gajim.interface.status_sent_to_groups[account] = {}
			for gc_control in gajim.interface.msg_win_mgr.get_controls(
			message_control.TYPE_GC) + \
			gajim.interface.minimized_controls[account].values():
				if gc_control.account == account:
					if gajim.gc_connected[account][gc_control.room_jid]:
						gajim.connections[account].send_gc_status(gc_control.nick,
							gc_control.room_jid, status, txt)
					else:
						# for some reason, we are not connected to the room even if
						# tab is opened, send initial join_gc()
						gajim.connections[account].join_gc(gc_control.nick,
						gc_control.room_jid, None)
			if was_invisible and status != 'offline':
				# We come back from invisible, join bookmarks
				for bm in gajim.connections[account].bookmarks:
					room_jid = bm['jid']
					if room_jid in gajim.gc_connected[account] and \
					gajim.gc_connected[account][room_jid]:
						continue
					self.join_gc_room(account, room_jid, bm['nick'], bm['password'],
						minimize = bm['minimize'])

	def get_status_message(self, show):
		if show in gajim.config.get_per('defaultstatusmsg'):
			if gajim.config.get_per('defaultstatusmsg', show, 'enabled'):
				return gajim.config.get_per('defaultstatusmsg', show, 'message')
		if (show == 'online' and not gajim.config.get('ask_online_status')) or \
		(show in ('offline', 'invisible')
		and not gajim.config.get('ask_offline_status')):
			return ''
		dlg = dialogs.ChangeStatusMessageDialog(show)
		dlg.window.present() # show it on current workspace
		message = dlg.run()
		return message

	def connected_rooms(self, account):
		if True in gajim.gc_connected[account].values():
			return True
		return False

	def change_status(self, widget, account, status):
		def change(widget, account, status):
			if self.dialog:
				self.dialog.destroy()
			message = self.get_status_message(status)
			if message is None:
				# user pressed Cancel to change status message dialog
				return
			self.send_status(account, status, message)

		self.dialog = None
		if status == 'invisible' and self.connected_rooms(account):
			self.dialog = dialogs.ConfirmationDialog(
				_('You are participating in one or more group chats'),
				_('Changing your status to invisible will result in disconnection '
				'from those group chats. Are you sure you want to go invisible?'),
				on_response_ok = (change, account, status))
		else:
			change(None, account, status)

	def on_send_custom_status(self, widget, contact_list, show, group=None):
		'''send custom status'''
		dlg = dialogs.ChangeStatusMessageDialog(show)
		message = dlg.run()
		if message is not None: # None if user pressed Cancel
			for (contact, account) in contact_list:
				accounts = []
				if group and account not in accounts:
					if not gajim.interface.status_sent_to_groups.has_key(account):
						gajim.interface.status_sent_to_groups[account] = {}
					gajim.interface.status_sent_to_groups[account][group] = show
					accounts.append(group)
				self.send_status(account, show, message, to = contact.jid)
				if not gajim.interface.status_sent_to_users.has_key(account):
					gajim.interface.status_sent_to_users[account] = {}
				gajim.interface.status_sent_to_users[account][contact.jid] = show

	def on_status_combobox_changed(self, widget):
		'''When we change our status via the combobox'''
		model = self.status_combobox.get_model()
		active = self.status_combobox.get_active()
		if active == -1: # no active item
			return
		if not self.combobox_callback_active:
			self.previous_status_combobox_active = active
			return
		accounts = gajim.connections.keys()
		if len(accounts) == 0:
			dialogs.ErrorDialog(_('No account available'),
		_('You must create an account before you can chat with other contacts.'))
			self.update_status_combobox()
			return
		status = model[active][2].decode('utf-8')

		if active == 7: # We choose change status message (7 is that)
			# do not change show, just show change status dialog
			status = model[self.previous_status_combobox_active][2].decode('utf-8')
			dlg = dialogs.ChangeStatusMessageDialog(status)
			message = dlg.run()
			if message is not None: # None if user pressed Cancel
				for account in accounts:
					if not gajim.config.get_per('accounts', account,
						'sync_with_global_status'):
						continue
					current_show = gajim.SHOW_LIST[
						gajim.connections[account].connected]
					self.send_status(account, current_show, message)
			self.combobox_callback_active = False
			self.status_combobox.set_active(
				self.previous_status_combobox_active)
			self.combobox_callback_active = True
			return
		# we are about to change show, so save this new show so in case
		# after user chooses "Change status message" menuitem
		# we can return to this show
		self.previous_status_combobox_active = active
		connected_accounts = gajim.get_number_of_connected_accounts()
		if status == 'invisible':
			bug_user = False
			for account in accounts:
				if connected_accounts < 1 or gajim.account_is_connected(account):
					if not gajim.config.get_per('accounts', account,
							'sync_with_global_status'):
						continue
					# We're going to change our status to invisible
					if self.connected_rooms(account):
						bug_user = True
						break
			if bug_user:
				dialog = dialogs.ConfirmationDialog(
					_('You are participating in one or more group chats'),
					_('Changing your status to invisible will result in '
					'disconnection from those group chats. Are you sure you want to '
					'go invisible?'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					self.update_status_combobox()
					return
		message = self.get_status_message(status)
		if message is None: # user pressed Cancel to change status message dialog
			self.update_status_combobox()
			return
		global_sync_accounts = []
		for acct in accounts:
			if gajim.config.get_per('accounts', acct, 'sync_with_global_status'):
				global_sync_accounts.append(acct)
		global_sync_connected_accounts = gajim.get_number_of_connected_accounts(
			global_sync_accounts)
		for account in accounts:
			if not gajim.config.get_per('accounts', account,
			'sync_with_global_status'):
				continue
			# we are connected (so we wanna change show and status)
			# or no account is connected and we want to connect with new show and
			# status

			if not global_sync_connected_accounts > 0 or \
			gajim.connections[account].connected > 0:
				self.send_status(account, status, message)
		self.update_status_combobox()

	## enable setting status msg from currently playing music track
	def enable_syncing_status_msg_from_current_music_track(self, enabled):
		'''if enabled is True, we listen to events from music players about
		currently played music track, and we update our
		status message accordinly'''
		if not dbus_support.supported:
			# do nothing if user doesn't have D-Bus bindings
			return
		if enabled:
			if self._music_track_changed_signal is None:
				listener = MusicTrackListener.get()
				self._music_track_changed_signal = listener.connect(
					'music-track-changed', self._music_track_changed)
				track = listener.get_playing_track()
				self._music_track_changed(listener, track)
		else:
			if self._music_track_changed_signal is not None:
				listener = MusicTrackListener.get()
				listener.disconnect(self._music_track_changed_signal)
				self._music_track_changed_signal = None
				self._music_track_changed(None, None)

	def _change_awn_icon_status(self, status):
		if not dbus_support.supported:
			# do nothing if user doesn't have D-Bus bindings
			return
		iconset = gajim.config.get('iconset')
		prefix = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '32x32')
		if status in ('chat', 'away', 'xa', 'dnd', 'invisible', 'offline'):
			status = status + '.png'
		elif status == 'online':
			prefix = os.path.join(gajim.DATA_DIR, 'pixmaps')
			status = 'gajim.png'
		path = os.path.join(prefix, status)
		try:
			bus = dbus.SessionBus()
			obj = bus.get_object('com.google.code.Awn', '/com/google/code/Awn')
			awn = dbus.Interface(obj, 'com.google.code.Awn')
			awn.SetTaskIconByName('Gajim', os.path.abspath(path))
		except Exception, e:
			pass

	def _music_track_changed(self, unused_listener, music_track_info):
		accounts = gajim.connections.keys()
		if music_track_info is None:
			status_message = ''
		else:
			if hasattr(music_track_info, 'paused') and \
			music_track_info.paused == 0:
				status_message = ''
			else:
				status_message = '♪ ' + _('"%(title)s" by %(artist)s') % \
				{'title': music_track_info.title,
					'artist': music_track_info.artist } + ' ♪'
		for account in accounts:
			if not gajim.config.get_per('accounts', account,
			'sync_with_global_status'):
				continue
			if not gajim.connections[account].connected:
				continue
			current_show = gajim.SHOW_LIST[gajim.connections[account].connected]
			self.send_status(account, current_show, status_message)


	def update_status_combobox(self):
		# table to change index in connection.connected to index in combobox
		table = {'offline':9, 'connecting':9, 'online':0, 'chat':1, 'away':2,
			'xa':3, 'dnd':4, 'invisible':5}
		show = helpers.get_global_show()
		# temporarily block signal in order not to send status that we show
		# in the combobox
		self.combobox_callback_active = False
		self.status_combobox.set_active(table[show])
		self._change_awn_icon_status(show)
		self.combobox_callback_active = True
		if gajim.interface.systray_enabled:
			gajim.interface.systray.change_status(show)

	def set_account_status_icon(self, account):
		status = gajim.connections[account].connected
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		if not accountIter:
			return
		if not self.regroup:
			show = gajim.SHOW_LIST[status]
		else:	# accounts merged
			show = helpers.get_global_show()
		model[accountIter][C_IMG] = self.jabber_state_images['16'][show]

	def on_status_changed(self, account, status):
		'''the core tells us that our status has changed'''
		if account not in gajim.contacts.get_accounts():
			return
		model = self.tree.get_model()
		accountIter = self.get_account_iter(account)
		self.set_account_status_icon(account)
		if status == 'offline':
			if self.quit_on_next_offline > -1:
				self.quit_on_next_offline -= 1
				if self.quit_on_next_offline < 1:
					self.quit_gtkgui_interface()
			if accountIter:
				model[accountIter][C_SECPIXBUF] = None
			if gajim.con_types.has_key(account):
				gajim.con_types[account] = None
			for jid in gajim.contacts.get_jid_list(account):
				lcontact = gajim.contacts.get_contact(account, jid)
				lcontact_copy = []
				for contact in lcontact:
					lcontact_copy.append(contact)
				for contact in lcontact_copy:
					self.chg_contact_status(contact, 'offline', '', account)
			self.actions_menu_needs_rebuild = True
		self.update_status_combobox()

	def new_private_chat(self, gc_contact, account):
		contact = gajim.contacts.contact_from_gc_contact(gc_contact)
		type_ = message_control.TYPE_PM
		fjid = gc_contact.room_jid + '/' + gc_contact.name
		mw = gajim.interface.msg_win_mgr.get_window(fjid, account)
		if not mw:
			mw = gajim.interface.msg_win_mgr.create_window(contact, account, type_)

		chat_control = PrivateChatControl(mw, gc_contact, contact, account)
		mw.new_tab(chat_control)
		if len(gajim.events.get_events(account, fjid)):
			# We call this here to avoid race conditions with widget validation
			chat_control.read_queue()

	def new_chat(self, contact, account, resource = None):
		# Get target window, create a control, and associate it with the window
		type_ = message_control.TYPE_CHAT

		fjid = contact.jid
		if resource:
			fjid += '/' + resource
		mw = gajim.interface.msg_win_mgr.get_window(fjid, account)
		if not mw:
			mw = gajim.interface.msg_win_mgr.create_window(contact, account, type_)

		chat_control = ChatControl(mw, contact, account, resource)

		mw.new_tab(chat_control)

		if len(gajim.events.get_events(account, fjid)):
			# We call this here to avoid race conditions with widget validation
			chat_control.read_queue()

	def new_chat_from_jid(self, account, fjid):
		jid, resource = gajim.get_room_and_nick_from_fjid(fjid)
		if resource:
			contact = gajim.contacts.get_contact(account, jid, resource)
		else:
			contact = gajim.contacts.get_contact_with_highest_priority(account,
				jid)
		added_to_roster = False
		if not contact:
			added_to_roster = True
			contact = self.add_to_not_in_the_roster(account, jid,
				resource = resource)

		if not gajim.interface.msg_win_mgr.has_window(fjid, account):
			self.new_chat(contact, account, resource = resource)
		mw = gajim.interface.msg_win_mgr.get_window(fjid, account)
		mw.set_active_tab(fjid, account)
		mw.window.present()
		# For JEP-0172
		if added_to_roster:
			mc = mw.get_control(fjid, account)
			mc.user_nick = gajim.nicks[account]

	def new_room(self, room_jid, nick, account):
		# Get target window, create a control, and associate it with the window
		contact = gajim.contacts.create_contact(jid = room_jid, name = nick)
		mw = gajim.interface.msg_win_mgr.get_window(contact.jid, account)
		if not mw:
			mw = gajim.interface.msg_win_mgr.create_window(contact, account,
								GroupchatControl.TYPE_ID)
		gc_control = GroupchatControl(mw, contact, account)
		mw.new_tab(gc_control)

	def on_message(self, jid, msg, tim, account, encrypted = False,
			msg_type = '', subject = None, resource = '', msg_id = None,
			user_nick = '', advanced_notif_num = None, xhtml = None):
		'''when we receive a message'''
		contact = None
		# if chat window will be for specific resource
		resource_for_chat = resource
		fjid = jid
		# Try to catch the contact with correct resource
		if resource:
			fjid = jid + '/' + resource
			contact = gajim.contacts.get_contact(account, jid, resource)
		highest_contact = gajim.contacts.get_contact_with_highest_priority(
			account, jid)
		if not contact:
			# If there is another resource, it may be a message from an invisible
			# resource
			lcontact = gajim.contacts.get_contacts_from_jid(account, jid)
			if (len(lcontact) > 1 or (lcontact and lcontact[0].resource and \
			lcontact[0].show != 'offline')) and jid.find('@') > 0:
				contact = gajim.contacts.copy_contact(highest_contact)
				contact.resource = resource
				if resource:
					fjid = jid + '/' + resource
				contact.priority = 0
				contact.show = 'offline'
				contact.status = ''
				gajim.contacts.add_contact(account, contact)

			else:
				# Default to highest prio
				fjid = jid
				resource_for_chat = None
				contact = highest_contact
		if not contact:
			# contact is not in roster
			contact = self.add_to_not_in_the_roster(account, jid, user_nick)

		path = self.get_path(jid, account) # Try to get line of contact in roster

		# Look for a chat control that has the given resource
		ctrl = gajim.interface.msg_win_mgr.get_control(fjid, account)
		if not ctrl:
			# if not, if message comes from highest prio, get control or open one
			# without resource
			if highest_contact and contact.resource == highest_contact.resource \
			and not jid == gajim.get_jid_from_account(account):
				ctrl = gajim.interface.msg_win_mgr.get_control(jid, account)
				fjid = jid
				resource_for_chat = None

		# Do we have a queue?
		no_queue = len(gajim.events.get_events(account, fjid)) == 0

		popup = helpers.allow_popup_window(account, advanced_notif_num)

		if msg_type == 'normal' and popup: # it's single message to be autopopuped
			dialogs.SingleMessageWindow(account, contact.jid,
				action = 'receive', from_whom = jid, subject = subject,
				message = msg, resource = resource)
			return

		# We print if window is opened and it's not a single message
		if ctrl and msg_type != 'normal':
			typ = ''
			if msg_type == 'error':
				typ = 'status'
			ctrl.print_conversation(msg, typ, tim = tim, encrypted = encrypted,
						subject = subject, xhtml = xhtml)
			if msg_id:
				gajim.logger.set_read_messages([msg_id])
			return

		# We save it in a queue
		type_ = 'chat'
		event_type = 'message_received'
		if msg_type == 'normal':
			type_ = 'normal'
			event_type = 'single_message_received'
		show_in_roster = notify.get_show_in_roster(event_type, account, contact)
		show_in_systray = notify.get_show_in_systray(event_type, account, contact)
		event = gajim.events.create_event(type_, (msg, subject, msg_type, tim,
			encrypted, resource, msg_id, xhtml), show_in_roster = show_in_roster,
			show_in_systray = show_in_systray)
		gajim.events.add_event(account, fjid, event)
		if popup:
			if not ctrl:
				self.new_chat(contact, account, resource = resource_for_chat)
				if path and not self.dragging and gajim.config.get(
				'scroll_roster_to_last_message'):
					# we curently see contact in our roster OR he
					# is not in the roster at all.
					# show and select his line in roster
					# do not change selection while DND'ing
					self.tree.expand_row(path[0:1], False)
					self.tree.expand_row(path[0:2], False)
					self.tree.scroll_to_cell(path)
					self.tree.set_cursor(path)
		else:
			if no_queue: # We didn't have a queue: we change icons
				self.draw_contact(jid, account)
			self.show_title() # we show the * or [n]
			# Show contact in roster (if he is invisible for example) and select
			# line
			self.show_and_select_path(path, jid, account)

	def on_preferences_menuitem_activate(self, widget):
		if gajim.interface.instances.has_key('preferences'):
			gajim.interface.instances['preferences'].window.present()
		else:
			gajim.interface.instances['preferences'] = config.PreferencesWindow()

	def on_add_new_contact(self, widget, account):
		dialogs.AddNewContactWindow(account)

	def on_join_gc_activate(self, widget, account):
		'''when the join gc menuitem is clicked, show the join gc window'''
		invisible_show = gajim.SHOW_LIST.index('invisible')
		if gajim.connections[account].connected == invisible_show:
			dialogs.ErrorDialog(_('You cannot join a group chat while you are '
				'invisible'))
			return
		if gajim.interface.instances[account].has_key('join_gc'):
			gajim.interface.instances[account]['join_gc'].window.present()
		else:
			# c http://nkour.blogspot.com/2005/05/pythons-init-return-none-doesnt-return.html
			try:
				gajim.interface.instances[account]['join_gc'] = \
					dialogs.JoinGroupchatWindow(account)
			except GajimGeneralException:
				pass

	def on_new_chat_menuitem_activate(self, widget, account):
		dialogs.NewChatDialog(account)

	def on_contents_menuitem_activate(self, widget):
		helpers.launch_browser_mailer('url', 'http://trac.gajim.org/wiki')

	def on_faq_menuitem_activate(self, widget):
		helpers.launch_browser_mailer('url',
			'http://trac.gajim.org/wiki/GajimFaq')

	def on_about_menuitem_activate(self, widget):
		dialogs.AboutDialog()

	def on_accounts_menuitem_activate(self, widget):
		if gajim.interface.instances.has_key('accounts'):
			gajim.interface.instances['accounts'].window.present()
		else:
			gajim.interface.instances['accounts'] = config.AccountsWindow()

	def on_file_transfers_menuitem_activate(self, widget):
		if gajim.interface.instances['file_transfers'].window.get_property(
		'visible'):
			gajim.interface.instances['file_transfers'].window.present()
		else:
			gajim.interface.instances['file_transfers'].window.show_all()

	def on_show_transports_menuitem_activate(self, widget):
		gajim.config.set('show_transports_group', widget.get_active())
		self.draw_roster()

	def on_manage_bookmarks_menuitem_activate(self, widget):
		config.ManageBookmarksWindow()

	def on_profile_avatar_menuitem_activate(self, widget, account):
		gajim.interface.edit_own_details(account)

	def close_all_from_dict(self, dic):
		'''close all the windows in the given dictionary'''
		for w in dic.values():
			if type(w) == type({}):
				self.close_all_from_dict(w)
			else:
				w.window.destroy()

	def close_all(self, account, force = False):
		'''close all the windows from an account
		if force is True, do not ask confirmation before closing chat/gc windows
		'''
		self.close_all_from_dict(gajim.interface.instances[account])
		for ctrl in gajim.interface.msg_win_mgr.get_controls(acct = account):
			ctrl.parent_win.remove_tab(ctrl, ctrl.parent_win.CLOSE_CLOSE_BUTTON,
				force = force)

	def on_roster_window_delete_event(self, widget, event):
		'''When we want to close the window'''
		if gajim.interface.systray_enabled and not gajim.config.get(
		'quit_on_roster_x_button'):
			self.tooltip.hide_tooltip()
			self.window.hide()
		else:
			accounts = gajim.connections.keys()
			get_msg = False
			self.quit_on_next_offline = 0
			for acct in accounts:
				if gajim.connections[acct].connected:
					get_msg = True
					break
			if get_msg:
				message = self.get_status_message('offline')
				if message is None:
					# user pressed Cancel to change status message dialog
					message = ''

				for acct in accounts:
					if gajim.connections[acct].connected:
						self.quit_on_next_offline += 1
						self.send_status(acct, 'offline', message)
			if not self.quit_on_next_offline:
				self.quit_gtkgui_interface()
		return True # do NOT destory the window

	def on_roster_window_focus_in_event(self, widget, event):
		# roster received focus, so if we had urgency REMOVE IT
		# NOTE: we do not have to read the message to remove urgency
		# so this functions does that
		gtkgui_helpers.set_unset_urgency_hint(widget, False)

		# if a contact row is selected, update colors (eg. for status msg)
		# because gtk engines may differ in bg when window is selected
		# or not
		if len(self._last_selected_contact):
			for (jid, account) in self._last_selected_contact:
				self.draw_contact(jid, account, selected = True,
					focus = True)

	def on_roster_window_focus_out_event(self, widget, event):
		# if a contact row is selected, update colors (eg. for status msg)
		# because gtk engines may differ in bg when window is selected
		# or not
		if len(self._last_selected_contact):
			for (jid, account) in self._last_selected_contact:
				self.draw_contact(jid, account, selected = True,
					focus = False)

	def on_roster_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			model, list_of_paths = self.tree.get_selection().get_selected_rows()
			if not len(list_of_paths) and gajim.interface.systray_enabled and \
			not gajim.config.get('quit_on_roster_x_button'):
				self.tooltip.hide_tooltip()
				self.window.hide()

	def on_roster_window_popup_menu(self, widget):
		event = gtk.gdk.Event(gtk.gdk.KEY_PRESS)
		self.show_treeview_menu(event)

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

		gajim.config.set('show_roster_on_startup',
			self.window.get_property('visible'))
		gajim.interface.msg_win_mgr.shutdown()

		gajim.config.set('collapsed_rows', '\t'.join(self.collapsed_rows))
		gajim.interface.save_config()
		for account in gajim.connections:
			gajim.connections[account].quit(True)
			self.close_all(account)
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
			if message is None:
				# user pressed Cancel to change status message dialog
				return
			# check if we have unread or recent mesages
			unread = False
			recent = False
			if gajim.events.get_nb_events() > 0:
				unread = True
			for win in gajim.interface.msg_win_mgr.windows():
				unrd = 0
				for ctrl in win.controls():
					if ctrl.type_id == message_control.TYPE_GC:
						if gajim.config.get('notify_on_all_muc_messages'):
							unrd += ctrl.get_nb_unread()
						else:
							if ctrl.attention_flag:
								unrd += 1
				if unrd:
					unread = True
					break

				for ctrl in win.controls():
					fjid = ctrl.get_full_jid()
					if gajim.last_message_time[acct].has_key(fjid):
						if time.time() - gajim.last_message_time[acct][fjid] < 2:
							recent = True
							break
			if unread:
				dialog = dialogs.ConfirmationDialog(_('You have unread messages'),
					_('Messages will only be available for reading them later if you'
					' have history enabled.'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return

			if recent:
				dialog = dialogs.ConfirmationDialog(_('You have unread messages'),
					_('Messages will only be available for reading them later if you'
					' have history enabled.'))
				if dialog.get_response() != gtk.RESPONSE_OK:
					return
			self.quit_on_next_offline = 0
			for acct in accounts:
				if gajim.connections[acct].connected:
					self.quit_on_next_offline += 1
					self.send_status(acct, 'offline', message)
		else:
			self.quit_on_next_offline = 0
		if not self.quit_on_next_offline:
			self.quit_gtkgui_interface()

	def open_event(self, account, jid, event):
		'''If an event was handled, return True, else return False'''
		data = event.parameters
		ft = gajim.interface.instances['file_transfers']
		if event.type_ == 'normal':
			dialogs.SingleMessageWindow(account, jid,
				action = 'receive', from_whom = jid, subject = data[1],
				message = data[0], resource = data[5])
			gajim.interface.remove_first_event(account, jid, event.type_)
			return True
		elif event.type_ == 'file-request':
			contact = gajim.contacts.get_contact_with_highest_priority(account,
				jid)
			gajim.interface.remove_first_event(account, jid, event.type_)
			ft.show_file_request(account, contact, data)
			return True
		elif event.type_ in ('file-request-error', 'file-send-error'):
			gajim.interface.remove_first_event(account, jid, event.type_)
			ft.show_send_error(data)
			return True
		elif event.type_ in ('file-error', 'file-stopped'):
			gajim.interface.remove_first_event(account, jid, event.type_)
			ft.show_stopped(jid, data)
			return True
		elif event.type_ == 'file-completed':
			gajim.interface.remove_first_event(account, jid, event.type_)
			ft.show_completed(jid, data)
			return True
		elif event.type_ == 'gc-invitation':
			dialogs.InvitationReceivedDialog(account, data[0], jid, data[2],
				data[1])
			gajim.interface.remove_first_event(account, jid, event.type_)
			return True
		return False

	def on_execute_command(self, widget, contact, account, resource=None):
		'''Execute command. Full JID needed; if it is other contact,
		resource is necessary. Widget is unnecessary, only to be
		able to make this a callback.'''
		jid = contact.jid
		if resource is not None:
			jid = jid + u'/' + resource
		adhoc_commands.CommandWindow(account, jid)

	def on_open_chat_window(self, widget, contact, account, resource = None):
		# Get the window containing the chat
		fjid = contact.jid
		if resource:
			fjid += '/' + resource
		win = gajim.interface.msg_win_mgr.get_window(fjid, account)
		if not win:
			self.new_chat(contact, account, resource = resource)
			win = gajim.interface.msg_win_mgr.get_window(fjid, account)
			ctrl = win.get_control(fjid, account)
			# last message is long time ago
			gajim.last_message_time[account][ctrl.get_full_jid()] = 0
		win.set_active_tab(fjid, account)
		if gajim.connections[account].is_zeroconf and \
				gajim.connections[account].status in ('offline', 'invisible'):
			win.get_control(fjid, account).got_disconnected()

		win.window.present()

	def on_row_activated(self, widget, path):
		'''When an iter is activated (dubblick or single click if gnome is set
		this way'''
		model = self.tree.get_model()
		account = model[path][C_ACCOUNT].decode('utf-8')
		type_ = model[path][C_TYPE]
		jid = model[path][C_JID].decode('utf-8')
		resource = None
		iter = model.get_iter(path)
		if type_ in ('group', 'account'):
			if self.tree.row_expanded(path):
				self.tree.collapse_row(path)
			else:
				self.tree.expand_row(path, False)
		elif jid in gajim.interface.minimized_controls[account]:
			self.on_groupchat_maximized(None, jid, account)
		else:
			first_ev = gajim.events.get_first_event(account, jid)
			if not first_ev:
				# look in other resources
				for c in gajim.contacts.get_contact(account, jid):
					fjid = c.get_full_jid()
					first_ev = gajim.events.get_first_event(account, fjid)
					if first_ev:
						resource = c.resource
						break
			if not first_ev and model.iter_has_child(iter):
				child_iter = model.iter_children(iter)
				while not first_ev and child_iter:
					child_jid = model[child_iter][C_JID].decode('utf-8')
					first_ev = gajim.events.get_first_event(account, child_jid)
					if first_ev:
						jid = child_jid
					else:
						child_iter = model.iter_next(child_iter)
			if first_ev:
				fjid = jid
				if resource:
					fjid += '/' + resource
				if self.open_event(account, fjid, first_ev):
					return
			c = gajim.contacts.get_contact(account, jid, resource)
			if not c or isinstance(c, list):
				c = gajim.contacts.get_contact_with_highest_priority(account, jid)
			if jid == gajim.get_jid_from_account(account):
				resource = c.resource
			self.on_open_chat_window(widget, c, account, resource = resource)

	def on_roster_treeview_row_activated(self, widget, path, col = 0):
		'''When an iter is double clicked: open the first event window'''
		if not gajim.single_click:
			self.on_row_activated(widget, path)

	def on_roster_treeview_row_expanded(self, widget, iter, path):
		'''When a row is expanded change the icon of the arrow'''
		model = self.tree.get_model()
		if self.regroup: # merged accounts
			accounts = gajim.connections.keys()
		else:
			accounts = [model[iter][C_ACCOUNT].decode('utf-8')]
		type_ = model[iter][C_TYPE]
		if type_ == 'group':
			model.set_value(iter, 0, self.jabber_state_images['16']['opened'])
			jid = model[iter][C_JID].decode('utf-8')
			for account in accounts:
				if gajim.groups[account].has_key(jid): # This account has this group
					gajim.groups[account][jid]['expand'] = True
					if account + jid in self.collapsed_rows:
						self.collapsed_rows.remove(account + jid)
		elif type_ == 'account':
			account = accounts[0] # There is only one cause we don't use merge
			if account in self.collapsed_rows:
				self.collapsed_rows.remove(account)
			for g in gajim.groups[account]:
				groupIter = self.get_group_iter(g, account)
				if groupIter and gajim.groups[account][g]['expand']:
					pathG = model.get_path(groupIter)
					self.tree.expand_row(pathG, False)
			self.draw_account(account)
		elif type_ == 'contact':
			jid =  model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			self.draw_contact(jid, account)

	def on_roster_treeview_row_collapsed(self, widget, iter, path):
		'''When a row is collapsed :
		change the icon of the arrow'''
		model = self.tree.get_model()
		if self.regroup: # merged accounts
			accounts = gajim.connections.keys()
		else:
			accounts = [model[iter][C_ACCOUNT].decode('utf-8')]
		type_ = model[iter][C_TYPE]
		if type_ == 'group':
			model.set_value(iter, 0, self.jabber_state_images['16']['closed'])
			jid = model[iter][C_JID].decode('utf-8')
			for account in accounts:
				if gajim.groups[account].has_key(jid): # This account has this group
					gajim.groups[account][jid]['expand'] = False
					if not account + jid in self.collapsed_rows:
						self.collapsed_rows.append(account + jid)
		elif type_ == 'account':
			account = accounts[0] # There is only one cause we don't use merge
			if not account in self.collapsed_rows:
				self.collapsed_rows.append(account)
			self.draw_account(account)
		elif type_ == 'contact':
			jid =  model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			self.draw_contact(jid, account)

	def on_service_disco_menuitem_activate(self, widget, account):
		server_jid = gajim.config.get_per('accounts', account, 'hostname')
		if gajim.interface.instances[account]['disco'].has_key(server_jid):
			gajim.interface.instances[account]['disco'][server_jid].\
				window.present()
		else:
			try:
				# Object will add itself to the window dict
				disco.ServiceDiscoveryWindow(account, address_entry = True)
			except GajimGeneralException:
				pass

	def load_iconset(self, path, pixbuf2 = None, transport = False):
		'''load full iconset from the given path, and add
		pixbuf2 on top left of each static images'''
		path += '/'
		if transport:
			list = ('online', 'chat', 'away', 'xa', 'dnd', 'offline',
				'not in roster')
		else:
			list = ('connecting', 'online', 'chat', 'away', 'xa', 'dnd',
				'invisible', 'offline', 'error', 'requested', 'message', 'opened',
				'closed', 'not in roster', 'muc_active', 'muc_inactive')
			if pixbuf2:
				list = ('connecting', 'online', 'chat', 'away', 'xa', 'dnd',
					'offline', 'error', 'requested', 'message', 'not in roster')
		return self._load_icon_list(list, path, pixbuf2)

	def load_icon(self, icon_name):
		'''load an icon from the iconset in 16x16'''
		iconset = gajim.config.get('iconset')
		path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16'+ '/')
		icon_list = self._load_icon_list([icon_name], path)
		return icon_list[icon_name]

	def _load_icon_list(self, icons_list, path, pixbuf2 = None):
		'''load icons in icons_list from the given path,
		and add pixbuf2 on top left of each static images'''
		imgs = {}
		for icon in icons_list:
			# try to open a pixfile with the correct method
			icon_file = icon.replace(' ', '_')
			files = []
			files.append(path + icon_file + '.gif')
			files.append(path + icon_file + '.png')
			image = gtk.Image()
			image.show()
			imgs[icon] = image
			for file in files: # loop seeking for either gif or png
				if os.path.exists(file):
					image.set_from_file(file)
					if pixbuf2 and image.get_storage_type() == gtk.IMAGE_PIXBUF:
						# add pixbuf2 on top-left corner of image
						pixbuf1 = image.get_pixbuf()
						pixbuf2.composite(pixbuf1, 0, 0,
							pixbuf2.get_property('width'),
							pixbuf2.get_property('height'), 0, 0, 1.0, 1.0,
							gtk.gdk.INTERP_NEAREST, 255)
						image.set_from_pixbuf(pixbuf1)
					break
		return imgs

	def make_jabber_state_images(self):
		'''initialise jabber_state_images dict'''
		iconset = gajim.config.get('iconset')
		if iconset:
			path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
			if not os.path.exists(path):
				iconset = gajim.config.DEFAULT_ICONSET
		else:
			iconset = gajim.config.DEFAULT_ICONSET

		path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '32x32')
		self.jabber_state_images['32'] = self.load_iconset(path)

		path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
		self.jabber_state_images['16'] = self.load_iconset(path)
		# try to find opened_meta.png file, else opened.png else nopixbuf merge
		path_opened = os.path.join(path, 'opened_meta.png')
		if not os.path.isfile(path_opened):
			path_opened = os.path.join(path, 'opened.png')
		if os.path.isfile(path_opened):
			pixo = gtk.gdk.pixbuf_new_from_file(path_opened)
		else:
			pixo = None
		self.jabber_state_images['opened'] = self.load_iconset(path, pixo)
		# Same thing for closed
		path_closed = os.path.join(path, 'opened_meta.png')
		if not os.path.isfile(path_closed):
			path_closed = os.path.join(path, 'closed.png')
		if os.path.isfile(path_closed):
			pixc = gtk.gdk.pixbuf_new_from_file(path_closed)
		else:
			pixc = None
		self.jabber_state_images['closed'] = self.load_iconset(path, pixc)

		if gajim.config.get('use_transports_iconsets'):
			# update opened and closed transport iconsets
			# standard transport iconsets are loaded one time in init()
			t_path = os.path.join(gajim.DATA_DIR, 'iconsets', 'transports')
			folders = os.listdir(t_path)
			for transport in folders:
				if transport == '.svn':
					continue
				folder = os.path.join(t_path, transport, '16x16')
				self.transports_state_images['opened'][transport] = \
					self.load_iconset(folder, pixo, transport = True)
				self.transports_state_images['closed'][transport] = \
					self.load_iconset(folder, pixc, transport = True)

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
				model[iter][1] = self.jabber_state_images['16'][model[iter][2]]
			iter = model.iter_next(iter)
		# Update the systray
		if gajim.interface.systray_enabled:
			gajim.interface.systray.set_img()

		for win in gajim.interface.msg_win_mgr.windows():
			for ctrl in win.controls():
				ctrl.update_ui()
				win.redraw_tab(ctrl)

		self.update_status_combobox()

	def repaint_themed_widgets(self):
		'''Notify windows that contain themed widgets to repaint them'''
		for win in gajim.interface.msg_win_mgr.windows():
			win.repaint_themed_widgets()
		for account in gajim.connections:
			for addr in gajim.interface.instances[account]['disco']:
				gajim.interface.instances[account]['disco'][addr].paint_banner()

	def on_show_offline_contacts_menuitem_activate(self, widget):
		'''when show offline option is changed:
		redraw the treeview'''
		gajim.config.set('showoffline', not gajim.config.get('showoffline'))
		self.draw_roster()

	def set_renderer_color(self, renderer, style, set_background = True):
		'''set style for treeview cell, using PRELIGHT system color'''
		if set_background:
			bgcolor = self.tree.style.bg[style]
			renderer.set_property('cell-background-gdk', bgcolor)
		else:
			fgcolor = self.tree.style.fg[style]
			renderer.set_property('foreground-gdk', fgcolor)

	def iconCellDataFunc(self, column, renderer, model, iter, data = None):
		'''When a row is added, set properties for icon renderer'''
		theme = gajim.config.get('roster_theme')
		type_ = model[iter][C_TYPE]
		if type_ == 'account':
			color = gajim.config.get_per('themes', theme, 'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				self.set_renderer_color(renderer, gtk.STATE_ACTIVE)
			renderer.set_property('xalign', 0)
		elif type_ == 'group':
			color = gajim.config.get_per('themes', theme, 'groupbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				self.set_renderer_color(renderer, gtk.STATE_PRELIGHT)
			renderer.set_property('xalign', 0.2)
		elif type_: # prevent type_ = None, see http://trac.gajim.org/ticket/2534
			if not model[iter][C_JID] or not model[iter][C_ACCOUNT]:
				# This can append when at the moment we add the row
				return
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background', gajim.config.get(
					'just_connected_bg_color'))
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background', gajim.config.get(
					'just_disconnected_bg_color'))
			else:
				color = gajim.config.get_per('themes', theme, 'contactbgcolor')
				if color:
					renderer.set_property('cell-background', color)
				else:
					renderer.set_property('cell-background', None)
			parent_iter = model.iter_parent(iter)
			if model[parent_iter][C_TYPE] == 'contact':
				renderer.set_property('xalign', 1)
			else:
				renderer.set_property('xalign', 0.4)
		renderer.set_property('width', 26)

	def nameCellDataFunc(self, column, renderer, model, iter, data = None):
		'''When a row is added, set properties for name renderer'''
		theme = gajim.config.get('roster_theme')
		type_ = model[iter][C_TYPE]
		if type_ == 'account':
			color = gajim.config.get_per('themes', theme, 'accounttextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				self.set_renderer_color(renderer, gtk.STATE_ACTIVE, False)
			color = gajim.config.get_per('themes', theme, 'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				self.set_renderer_color(renderer, gtk.STATE_ACTIVE)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'accountfont'))
			renderer.set_property('xpad', 0)
			renderer.set_property('width', 3)
		elif type_ == 'group':
			color = gajim.config.get_per('themes', theme, 'grouptextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				self.set_renderer_color(renderer, gtk.STATE_PRELIGHT, False)
			color = gajim.config.get_per('themes', theme, 'groupbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				self.set_renderer_color(renderer, gtk.STATE_PRELIGHT)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'groupfont'))
			renderer.set_property('xpad', 4)
		elif type_: # prevent type_ = None, see http://trac.gajim.org/ticket/2534
			if not model[iter][C_JID] or not model[iter][C_ACCOUNT]:
				# This can append when at the moment we add the row
				return
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			color = gajim.config.get_per('themes', theme, 'contacttextcolor')
			if color:
				renderer.set_property('foreground', color)
			else:
				renderer.set_property('foreground', None)
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background', gajim.config.get(
					'just_connected_bg_color'))
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background', gajim.config.get(
					'just_disconnected_bg_color'))
			else:
				color = gajim.config.get_per('themes', theme, 'contactbgcolor')
				if color:
					renderer.set_property('cell-background', color)
				else:
					renderer.set_property('cell-background', None)
			renderer.set_property('font',
				gtkgui_helpers.get_theme_font_for_option(theme, 'contactfont'))
			parent_iter = model.iter_parent(iter)
			if model[parent_iter][C_TYPE] == 'contact':
				renderer.set_property('xpad', 16)
			else:
				renderer.set_property('xpad', 8)

	def fill_secondary_pixbuf_rederer(self, column, renderer, model, iter,
	data = None):
		'''When a row is added, set properties for secondary renderer (avatar or
		padlock)'''
		theme = gajim.config.get('roster_theme')
		type_ = model[iter][C_TYPE]
		if type_ == 'account':
			color = gajim.config.get_per('themes', theme, 'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				self.set_renderer_color(renderer, gtk.STATE_ACTIVE)
		elif type_ == 'group':
			color = gajim.config.get_per('themes', theme, 'groupbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				self.set_renderer_color(renderer, gtk.STATE_PRELIGHT)
		elif type_: # prevent type_ = None, see http://trac.gajim.org/ticket/2534
			if not model[iter][C_JID] or not model[iter][C_ACCOUNT]:
				# This can append when at the moment we add the row
				return
			jid = model[iter][C_JID].decode('utf-8')
			account = model[iter][C_ACCOUNT].decode('utf-8')
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background', gajim.config.get(
					'just_connected_bg_color'))
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background', gajim.config.get(
					'just_disconnected_bg_color'))
			else:
				color = gajim.config.get_per('themes', theme, 'contactbgcolor')
				if color:
					renderer.set_property('cell-background', color)
				else:
					renderer.set_property('cell-background', None)
		renderer.set_property('xalign', 1) # align pixbuf to the right

	def get_show(self, lcontact):
		prio = lcontact[0].priority
		show = lcontact[0].show
		for u in lcontact:
			if u.priority > prio:
				prio = u.priority
				show = u.show
		return show

	def compareIters(self, model, iter1, iter2, data = None):
		'''Compare two iters to sort them'''
		name1 = model[iter1][C_NAME]
		name2 = model[iter2][C_NAME]
		if not name1 or not name2:
			return 0
		name1 = name1.decode('utf-8')
		name2 = name2.decode('utf-8')
		type1 = model[iter1][C_TYPE]
		type2 = model[iter2][C_TYPE]
		if type1 == 'self_contact':
			return -1
		if type2 == 'self_contact':
			return 1
		if type1 == 'group':
			name1 = model[iter1][C_JID]
			name2 = model[iter2][C_JID]
			if name1 == _('Transports'):
				return 1
			if name2 == _('Transports'):
				return -1
			if name1 == _('Not in Roster'):
				return 1
			if name2 == _('Not in Roster'):
				return -1
			if name1 == _('Groupchats'):
				return 1
			if name2 == _('Groupchats'):
				return -1
		account1 = model[iter1][C_ACCOUNT]
		account2 = model[iter2][C_ACCOUNT]
		if not account1 or not account2:
			return 0
		account1 = account1.decode('utf-8')
		account2 = account2.decode('utf-8')
		if type1 == 'account':
			if account1 < account2:
				return -1
			return 1
		jid1 = model[iter1][C_JID].decode('utf-8')
		jid2 = model[iter2][C_JID].decode('utf-8')
		if type1 == 'contact':
			lcontact1 = gajim.contacts.get_contact(account1, jid1)
			contact1 = gajim.contacts.get_first_contact_from_jid(account1, jid1)
			if not contact1:
				return 0
			name1 = contact1.get_shown_name()
		if type2 == 'contact':
			lcontact2 = gajim.contacts.get_contact(account2, jid2)
			contact2 = gajim.contacts.get_first_contact_from_jid(account2, jid2)
			if not contact2:
				return 0
			name2 = contact2.get_shown_name()
		# We first compare by show if sort_by_show is True or if it's a child
		# contact
		if type1 == 'contact' and type2 == 'contact' and \
		gajim.config.get('sort_by_show'):
			cshow = {'online':0, 'chat': 1, 'away': 2, 'xa': 3, 'dnd': 4,
				'invisible': 5, 'offline': 6, 'not in roster': 7, 'error': 8}
			s = self.get_show(lcontact1)
			if s in cshow:
				show1 = cshow[s]
			else:
				show1 = 9
			s = self.get_show(lcontact2)
			if s in cshow:
				show2 = cshow[s]
			else:
				show2 = 9
			if show1 < show2:
				return -1
			elif show1 > show2:
				return 1
		# We compare names
		if name1.lower() < name2.lower():
			return -1
		if name2.lower() < name1.lower():
			return 1
		if type1 == 'contact' and type2 == 'contact':
			# We compare account names
			if account1.lower() < account2.lower():
				return -1
			if account2.lower() < account1.lower():
				return 1
			# We compare jids
			if jid1.lower() < jid2.lower():
				return -1
			if jid2.lower() < jid1.lower():
				return 1
		return 0

	def drag_data_get_data(self, treeview, context, selection, target_id, etime):
		model, list_of_paths = self.tree.get_selection().get_selected_rows()
		if len(list_of_paths) != 1:
			return
		path = list_of_paths[0]
		data = ''
		if len(path) >= 3:
			data = model[path][C_JID]
		selection.set(selection.target, 8, data)

	def drag_begin(self, treeview, context):
		self.dragging = True

	def drag_end(self, treeview, context):
		self.dragging = False

	def on_drop_in_contact(self, widget, account_source, c_source, account_dest,
		c_dest, was_big_brother, context, etime):
		if not gajim.connections[account_source].metacontacts_supported or not \
		gajim.connections[account_dest].metacontacts_supported:
			dialogs.WarningDialog(_('Metacontacts storage not supported by your '
				'server'),
				_('Your server does not support storing metacontacts information. '
				'So those information will not be save on next reconnection.'))
		def merge_contacts(widget = None):
			if widget: # dialog has been shown
				dlg.destroy()
				if dlg.is_checked(): # user does not want to be asked again
					gajim.config.set('confirm_metacontacts', 'no')
				else:
					gajim.config.set('confirm_metacontacts', 'yes')
			# children must take the new tag too, so remember old tag
			old_tag = gajim.contacts.get_metacontacts_tag(account_source,
				c_source.jid)
			# remove the source row
			self.remove_contact(c_source, account_source)
			# brother inherite big brother groups
			c_source.groups = []
			for g in c_dest.groups:
				c_source.groups.append(g)
			gajim.connections[account_source].update_contact(c_source.jid,
				c_source.name, c_source.groups)
			gajim.contacts.add_metacontact(account_dest, c_dest.jid,
				account_source, c_source.jid)
			if was_big_brother:
				# add brothers too
				all_jid = gajim.contacts.get_metacontacts_jids(old_tag)
				for _account in all_jid:
					for _jid in all_jid[_account]:
						gajim.contacts.add_metacontact(account_dest, c_dest.jid,
							_account, _jid)
						_c = gajim.contacts.get_first_contact_from_jid(_account, _jid)
						self.remove_contact(_c, _account)
						self.add_contact_to_roster(_jid, _account)
						self.draw_contact(_jid, _account)
			self.add_contact_to_roster(c_source.jid, account_source)
			self.draw_contact(c_dest.jid, account_dest)

			context.finish(True, True, etime)

		confirm_metacontacts = gajim.config.get('confirm_metacontacts')
		if confirm_metacontacts == 'no':
			merge_contacts()
			return
		pritext = _('You are about to create a metacontact. Are you sure you want'
			' to continue?')
		sectext = _('Metacontacts are a way to regroup several contacts in one '
			'line. Generally it is used when the same person has several Jabber '
			'accounts or transport accounts.')
		dlg = dialogs.ConfirmationDialogCheck(pritext, sectext,
			_('Do _not ask me again'), on_response_ok = merge_contacts)
		if not confirm_metacontacts: # First time we see this window
			dlg.checkbutton.set_active(True)

	def on_drop_in_group(self, widget, account, c_source, grp_dest, context,
		etime, grp_source = None):
		if grp_source:
			self.remove_contact_from_group(account, c_source, grp_source)
		# remove tag
		gajim.contacts.remove_metacontact(account, c_source.jid)
		self.add_contact_to_group(account, c_source, grp_dest)
		if context.action in (gtk.gdk.ACTION_MOVE, gtk.gdk.ACTION_COPY):
			context.finish(True, True, etime)

	def add_contact_to_group(self, account, contact, group):
		model = self.tree.get_model()
		if not group in contact.groups:
			contact.groups.append(group)
		# Remove all rows because add_contact_to_roster doesn't add it if one
		# is already in roster
		for i in self.get_contact_iter(contact.jid, account):
			model.remove(i)
		self.add_contact_to_roster(contact.jid, account)
		gajim.connections[account].update_contact(contact.jid, contact.name,
			contact.groups)

	def remove_contact_from_group(self, account, contact, group):
		# Make sure contact was in the group
		if group in contact.groups:
			contact.groups.remove(group)
		self.remove_contact(contact, account)

	def drag_data_received_data(self, treeview, context, x, y, selection, info,
		etime):
		model = treeview.get_model()
		if not selection.data:
			return
		data = selection.data
		drop_info = treeview.get_dest_row_at_pos(x, y)
		if not drop_info:
			return
		path_dest, position = drop_info
		if position == gtk.TREE_VIEW_DROP_BEFORE and len(path_dest) == 2 \
			and path_dest[1] == 0: # dropped before the first group
			return
		iter_dest = model.get_iter(path_dest)
		type_dest = model[iter_dest][C_TYPE].decode('utf-8')
		jid_dest = model[iter_dest][C_JID].decode('utf-8')
		account_dest = model[iter_dest][C_ACCOUNT].decode('utf-8')

		if account_dest == 'all':
			# drop on account row in merged mode: we can't know which account it is
			return

		# if account is not connected, do nothing
		if gajim.connections[account_dest].connected < 2:
			return

		# drop on self contact row
		if type_dest == 'self_contact':
			return

		if info == self.TARGET_TYPE_URI_LIST:
			# User dropped a file on the roster
			if len(path_dest) < 3:
				return
			if type_dest != 'contact':
				return
			c_dest = gajim.contacts.get_contact_with_highest_priority(account_dest,
				jid_dest)
			uri = data.strip()
			uri_splitted = uri.split() # we may have more than one file dropped
			nb_uri = len(uri_splitted)
			prim_text = 'Send file?'
			sec_text =  i18n.ngettext('Do you want to send that file to %s:',
				'Do you want to send those files to %s:', nb_uri) %\
				c_dest.get_shown_name()
			for uri in uri_splitted:
				path = helpers.get_file_path_from_dnd_dropped_uri(uri)
				sec_text += '\n' + os.path.basename(path)
			def _on_send_files(widget, account, jid, uris):
				dialog.destroy()
				c = gajim.contacts.get_contact_with_highest_priority(account, jid)
				for uri in uris:
					path = helpers.get_file_path_from_dnd_dropped_uri(uri)
					if os.path.isfile(path): # is it file?
						gajim.interface.instances['file_transfers'].send_file(
							account, c, path)

			dialog = dialogs.NonModalConfirmationDialog(prim_text, sec_text,
				on_response_ok = (_on_send_files, account_dest, jid_dest,
				uri_splitted))
			dialog.popup()
			return

		if gajim.config.get_per('accounts', account_dest, 'is_zeroconf'):
			# drop on zeroconf account, no contact adds possible
			return

		if position == gtk.TREE_VIEW_DROP_BEFORE and len(path_dest) == 2:
			# dropped before a group : we drop it in the previous group
			path_dest = (path_dest[0], path_dest[1]-1)
		path_source = treeview.get_selection().get_selected_rows()[1][0]
		iter_source = model.get_iter(path_source)
		type_source = model[iter_source][C_TYPE]
		account_source = model[iter_source][C_ACCOUNT].decode('utf-8')
		if type_source != 'contact': # source is not a contact
			return
		if type_dest == 'account' and account_source == account_dest:
			return
		if gajim.config.get_per('accounts', account_source, 'is_zeroconf'):
			return
		it = iter_source
		while model[it][C_TYPE] == 'contact':
			it = model.iter_parent(it)
		grp_source = model[it][C_JID].decode('utf-8')
		if grp_source in helpers.special_groups:
			return
		jid_source = data.decode('utf-8')
		c_source = gajim.contacts.get_contact_with_highest_priority(
			account_source, jid_source)

		grp_dest = None
		if type_dest == 'group':
			grp_dest = model[iter_dest][C_JID].decode('utf-8')
		elif type_dest in ('contact', 'agent'):
			it = iter_dest
			while model[it][C_TYPE] != 'group':
				it = model.iter_parent(it)
			grp_dest = model[it][C_JID].decode('utf-8')

		if type_dest == 'groupchat':
			return

		if (type_dest == 'account' or not self.regroup) and \
		account_source != account_dest:
			# add contact to this account in that group
			dialogs.AddNewContactWindow(account = account_dest, jid = jid_source,
				user_nick = c_source.name, group = grp_dest)
			return

		# Get destination group
		if type_dest == 'group':
			if grp_dest in helpers.special_groups:
				return
			if context.action == gtk.gdk.ACTION_COPY:
				self.on_drop_in_group(None, account_source, c_source, grp_dest,
					context, etime)
				return
			self.on_drop_in_group(None, account_source, c_source, grp_dest,
				context, etime, grp_source)
			return
		if grp_dest in helpers.special_groups:
			return
		if jid_source == jid_dest:
			if grp_source == grp_dest and account_source == account_dest:
				return
		if grp_source == grp_dest:
			# Add meta contact
			#FIXME: doesn't work under windows:
			# http://bugzilla.gnome.org/show_bug.cgi?id=329797
#			if context.action == gtk.gdk.ACTION_COPY:
#				# Keep only MOVE
#				return
			c_dest = gajim.contacts.get_contact_with_highest_priority(account_dest,
				jid_dest)
			is_big_brother = False
			if model.iter_has_child(iter_source):
				is_big_brother = True
			if not c_dest:
				# c_dest is None if jid_dest doesn't belong to account
				return
			self.on_drop_in_contact(treeview, account_source, c_source,
				account_dest, c_dest, is_big_brother, context, etime)
			return
		# We upgrade only the first user because user2.groups is a pointer to
		# user1.groups
		if context.action == gtk.gdk.ACTION_COPY:
			self.on_drop_in_group(None, account_source, c_source, grp_dest,
				context, etime)
		else:
			menu = gtk.Menu()
			item = gtk.MenuItem(_('Drop %s in group %s') % (c_source.name,
				grp_dest))
			item.connect('activate', self.on_drop_in_group, account_source,
				c_source, grp_dest, context, etime, grp_source)
			menu.append(item)
			c_dest = gajim.contacts.get_contact_with_highest_priority(
				account_dest, jid_dest)
			item = gtk.MenuItem(_('Make %s and %s metacontacts') %
				(c_source.get_shown_name(), c_dest.get_shown_name()))
			is_big_brother = False
			if model.iter_has_child(iter_source):
				is_big_brother = True
			item.connect('activate', self.on_drop_in_contact, account_source,
				c_source, account_dest, c_dest, is_big_brother, context, etime)

			menu.append(item)

			menu.attach_to_widget(self.tree, None)
			menu.connect('selection-done', gtkgui_helpers.destroy_widget)
			menu.show_all()
			menu.popup(None, None, None, 1, etime)

	def show_title(self):
		change_title_allowed = gajim.config.get('change_roster_title')
		nb_unread = 0
		if change_title_allowed:
			start = ''
			for account in gajim.connections:
				# Count events in roster title only if we don't auto open them
				if not helpers.allow_popup_window(account):
					nb_unread += gajim.events.get_nb_events(['chat', 'normal',
						'file-request', 'file-error', 'file-completed',
						'file-request-error', 'file-send-error', 'file-stopped',
						'printed_chat'], account)
			if nb_unread > 1:
				start = '[' + str(nb_unread) + ']  '
			elif nb_unread == 1:
				start = '*  '
			self.window.set_title(start + 'Gajim')

		gtkgui_helpers.set_unset_urgency_hint(self.window, nb_unread)

	def iter_is_separator(self, model, iter):
		if model[iter][0] == 'SEPARATOR':
			return True
		return False

	def iter_contact_rows(self):
		'''iterate over all contact rows in the tree model'''
		model = self.tree.get_model()
		account_iter = model.get_iter_root()
		while account_iter:
			group_iter = model.iter_children(account_iter)
			while group_iter:
				contact_iter = model.iter_children(group_iter)
				while contact_iter:
					yield model[contact_iter]
					contact_iter = model.iter_next(contact_iter)
				group_iter = model.iter_next(group_iter)
			account_iter = model.iter_next(account_iter)

	def on_roster_treeview_style_set(self, treeview, style):
		'''When style (theme) changes, redraw all contacts'''
		for contact in self.iter_contact_rows():
			self.draw_contact(contact[C_JID].decode('utf-8'),
				contact[C_ACCOUNT].decode('utf-8'))

	def _on_treeview_selection_changed(self, selection):
		model, list_of_paths = selection.get_selected_rows()
		if len(self._last_selected_contact):
			# update unselected rows
			for (jid, account) in self._last_selected_contact:
				try:
					self.draw_contact(jid, account)
				except:
					# This can fail when last selected row was on an account we just
					# removed. So we don't care if that fail
					pass
		self._last_selected_contact = []
		if len(list_of_paths) == 0:
			return
		for path in list_of_paths:
			row = model[path]
			if row[C_TYPE] != 'contact':
				self._last_selected_contact = []
				return
			jid = row[C_JID].decode('utf-8')
			account = row[C_ACCOUNT].decode('utf-8')
			self._last_selected_contact.append((jid, account))
			self.draw_contact(jid, account, selected = True)

	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('roster_window.glade')
		self.window = self.xml.get_widget('roster_window')
		self._music_track_changed_signal = None
		gajim.interface.msg_win_mgr = MessageWindowMgr()
		self.advanced_menus = [] # We keep them to destroy them
		if gajim.config.get('roster_window_skip_taskbar'):
			self.window.set_property('skip-taskbar-hint', True)
		self.tree = self.xml.get_widget('roster_treeview')
		sel = self.tree.get_selection()
		sel.set_mode(gtk.SELECTION_MULTIPLE)
		sel.connect('changed',
			self._on_treeview_selection_changed)

		self._last_selected_contact = [] # holds a list of (jid, account) tupples
		self.jabber_state_images = {'16': {}, '32': {}, 'opened': {},
			'closed': {}}
		self.transports_state_images = {'16': {}, '32': {}, 'opened': {},
			'closed': {}}

		self.last_save_dir = None
		self.editing_path = None  # path of row with cell in edit mode
		self.add_new_contact_handler_id = False
		self.service_disco_handler_id = False
		self.new_chat_menuitem_handler_id = False
		self.profile_avatar_menuitem_handler_id = False
		self.actions_menu_needs_rebuild = True
		self.regroup = gajim.config.get('mergeaccounts')
		if len(gajim.connections) < 2: # Do not merge accounts if only one exists
			self.regroup = False
		#FIXME: When list_accel_closures will be wrapped in pygtk
		# no need of this variable
		self.have_new_chat_accel = False # Is the "Ctrl+N" shown ?
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
		model = gtk.TreeStore(gtk.Image, str, str, str, str, gtk.gdk.Pixbuf)

		model.set_sort_func(1, self.compareIters)
		model.set_sort_column_id(1, gtk.SORT_ASCENDING)
		self.tree.set_model(model)
		# when this value become 0 we quit main application
		self.quit_on_next_offline = -1
		self.make_jabber_state_images()

		path = os.path.join(gajim.DATA_DIR, 'iconsets', 'transports')
		folders = os.listdir(path)
		for transport in folders:
			if transport == '.svn':
				continue
			folder = os.path.join(path, transport, '32x32')
			self.transports_state_images['32'][transport] = self.load_iconset(
				folder, transport = True)
			folder = os.path.join(path, transport, '16x16')
			self.transports_state_images['16'][transport] = self.load_iconset(
				folder, transport = True)

		# uf_show, img, show, sensitive
		liststore = gtk.ListStore(str, gtk.Image, str, bool)
		self.status_combobox = self.xml.get_widget('status_combobox')

		cell = cell_renderer_image.CellRendererImage(0, 1)
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
			liststore.append([uf_show, self.jabber_state_images['16'][show], show,
				True])
		# Add a Separator (self.iter_is_separator() checks on string SEPARATOR)
		liststore.append(['SEPARATOR', None, '', True])

		path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'kbd_input.png')
		img = gtk.Image()
		img.set_from_file(path)
		# sensitivity to False because by default we're offline
		self.status_message_menuitem_iter = liststore.append(
			[_('Change Status Message...'), img, '', False])
		# Add a Separator (self.iter_is_separator() checks on string SEPARATOR)
		liststore.append(['SEPARATOR', None, '', True])

		uf_show = helpers.get_uf_show('offline')
		liststore.append([uf_show, self.jabber_state_images['16']['offline'],
			'offline', True])

		status_combobox_items = ['online', 'chat', 'away', 'xa', 'dnd',
			'invisible', 'separator1', 'change_status_msg', 'separator2',
			'offline']
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

		show_transports_group = gajim.config.get('show_transports_group')
		self.xml.get_widget('show_transports_menuitem').set_active(
			show_transports_group)

		# columns

		# this col has 3 cells:
		# first one img, second one text, third is sec pixbuf
		col = gtk.TreeViewColumn()

		render_image = cell_renderer_image.CellRendererImage(0, 0)
		# show img or +-
		col.pack_start(render_image, expand = False)
		col.add_attribute(render_image, 'image', C_IMG)
		col.set_cell_data_func(render_image, self.iconCellDataFunc, None)

		render_text = gtk.CellRendererText() # contact or group or account name
		render_text.set_property("ellipsize", pango.ELLIPSIZE_END)
		col.pack_start(render_text, expand = True)
		col.add_attribute(render_text, 'markup', C_NAME) # where we hold the name
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
		self.TARGET_TYPE_URI_LIST = 80
		TARGETS = [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0)]
		TARGETS2 = [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),
					('text/uri-list', 0, self.TARGET_TYPE_URI_LIST)]
		self.tree.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, TARGETS,
			gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
		self.tree.enable_model_drag_dest(TARGETS2, gtk.gdk.ACTION_DEFAULT)
		self.tree.connect('drag_begin', self.drag_begin)
		self.tree.connect('drag_end', self.drag_end)
		self.tree.connect('drag_data_get', self.drag_data_get_data)
		self.tree.connect('drag_data_received', self.drag_data_received_data)
		self.dragging = False
		self.xml.signal_autoconnect(self)
		self.combobox_callback_active = True

		self.collapsed_rows = gajim.config.get('collapsed_rows').split('\t')
		self.tooltip = tooltips.RosterTooltip()
		self.draw_roster()

		## Music Track notifications
		## FIXME: we use a timeout because changing status of
		## accounts has no effect until they are connected.
		gobject.timeout_add(1000,
			self.enable_syncing_status_msg_from_current_music_track,
			gajim.config.get('set_status_msg_from_current_music_track'))

		if gajim.config.get('show_roster_on_startup'):
			self.window.show_all()
		else:
			if not gajim.config.get('trayicon'):
				# cannot happen via GUI, but I put this incase user touches
				# config. without trayicon, he or she should see the roster!
				self.window.show_all()
				gajim.config.set('show_roster_on_startup', True)

		if len(gajim.connections) == 0: # if we have no account
			gajim.interface.instances['account_creation_wizard'] = \
				config.AccountCreationWizardWindow()
