# -*- coding: utf-8 -*-
## src/roster_window.py
##
## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Alex Mauer <hawke AT hawkesnest.net>
##                    Stéphan Kochen <stephan AT kochen.nl>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2005-2007 Travis Shirk <travis AT pobox.com>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Stefan Bethge <stefan AT lanpartei.de>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 Lukas Petrovicky <lukas AT petrovicky.net>
##                    James Newton <redshodan AT gmail.com>
##                    Tomasz Melcer <liori AT exroot.org>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
##                    Jonathan Schleifer <js-gajim AT webkeks.org>
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
import pango
import gobject
import os
import sys
import time

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
import features_window

from common import gajim
from common import helpers
from common.exceptions import GajimGeneralException
from common import i18n
from common import pep

from message_window import MessageWindowMgr

from common import dbus_support
if dbus_support.supported:
	import dbus

from common.xmpp.protocol import NS_COMMANDS, NS_FILE, NS_MUC
from common.pep import MOODS, ACTIVITIES

#(icon, name, type, jid, account, editable, second pixbuf)
(
C_IMG, # image to show state (online, new message etc)
C_NAME, # cellrenderer text that holds contact nickame
C_TYPE, # account, group or contact?
C_JID, # the jid of the row
C_ACCOUNT, # cellrenderer text that holds account name
C_MOOD_PIXBUF,
C_ACTIVITY_PIXBUF,
C_TUNE_PIXBUF,
C_AVATAR_PIXBUF, # avatar_pixbuf
C_PADLOCK_PIXBUF, # use for account row only
) = range(10)

class RosterWindow:
	'''Class for main window of the GTK+ interface'''

	def _get_account_iter(self, name, model=None):
		'''
		Return the gtk.TreeIter of the given account or None
		if not found.

		Keyword arguments:
		name -- the account name
		model -- the data model (default TreeFilterModel)
		'''
		if not model:
			model = self.modelfilter
		if model is None:
			return
		account_iter = model.get_iter_root()
		if self.regroup:
			return account_iter
		while account_iter:
			account_name = model[account_iter][C_ACCOUNT]
			if account_name and name == account_name.decode('utf-8'):
				break
			account_iter = model.iter_next(account_iter)
		return account_iter


	def _get_group_iter(self, name, account, account_iter=None, model=None):
		'''
		Return the gtk.TreeIter of the given group or None if not found.

		Keyword arguments:
		name -- the group name
		account -- the account name
		account_iter -- the iter of the account the model (default None)
		model -- the data model (default TreeFilterModel)

		'''
		if not model:
			model = self.modelfilter
		if not account_iter:
			account_iter = self._get_account_iter(account, model)
		group_iter = model.iter_children(account_iter)
		# C_NAME column contacts the pango escaped group name
		while group_iter:
			group_name = model[group_iter][C_JID].decode('utf-8')
			if name == group_name:
				break
			group_iter = model.iter_next(group_iter)
		return group_iter


	def _get_self_contact_iter(self, jid, account, model=None):
		''' Return the gtk.TreeIter of SelfContact or None if not found.

		Keyword arguments:
		jid -- the jid of SelfContact
		account -- the account of SelfContact
		model -- the data model (default TreeFilterModel)

		'''

		if not model:
			model = self.modelfilter
		iterAcct = self._get_account_iter(account, model)
		iterC = model.iter_children(iterAcct)

		# There might be several SelfContacts in merged account view
		while iterC:
			if model[iterC][C_TYPE] != 'self_contact':
				break
			iter_jid = model[iterC][C_JID]
			if iter_jid and jid == iter_jid.decode('utf-8'):
				return iterC
			iterC = model.iter_next(iterC)
		return None


	def _get_contact_iter(self, jid, account, contact=None, model=None):
		''' Return a list of gtk.TreeIter of the given contact.

		Keyword arguments:
		jid -- the jid without resource
		account -- the account
		contact -- the contact (default None)
		model -- the data model (default TreeFilterModel)

		'''
		if not model:
			model = self.modelfilter
			# when closing Gajim model can be none (async pbs?)
			if model is None:
				return []

		if jid == gajim.get_jid_from_account(account):
			contact_iter = self._get_self_contact_iter(jid,	account, model)
			if contact_iter:
				return [contact_iter]
			else:
				return []

		if not contact:
			contact = gajim.contacts.get_first_contact_from_jid(account, jid)
			if not contact:
				# We don't know this contact
				return []

		acct = self._get_account_iter(account, model)
		found = [] # the contact iters. One per group
		for group in contact.get_shown_groups():
			group_iter = self._get_group_iter(group, account, acct,  model)
			contact_iter = model.iter_children(group_iter)

			while contact_iter:
				# Loop over all contacts in this group
				iter_jid = model[contact_iter][C_JID]
				if iter_jid and jid == iter_jid.decode('utf-8') and \
				account == model[contact_iter][C_ACCOUNT].decode('utf-8'):
					# only one iter per group
					found.append(contact_iter)
					contact_iter = None
				elif model.iter_has_child(contact_iter):
					# it's a big brother and has children
					contact_iter = model.iter_children(contact_iter)
				else:
					# try to find next contact:
					# other contact in this group or
					# brother contact
					next_contact_iter = model.iter_next(contact_iter)
					if next_contact_iter:
						contact_iter = next_contact_iter
					else:
						# It's the last one.
						# Go up if we are big brother
						parent_iter = model.iter_parent(contact_iter)
						if parent_iter and model[parent_iter][C_TYPE] == 'contact':
							contact_iter = model.iter_next(parent_iter)
						else:
							# we tested all
							# contacts in this group
							contact_iter = None
		return found


	def _iter_is_separator(self, model, titer):
		''' Return True if the given iter is a separator.

		Keyword arguments:
		model -- the data model
		iter -- the gtk.TreeIter to test
		'''
		if model[titer][0] == 'SEPARATOR':
			return True
		return False


	def _iter_contact_rows(self, model=None):
		'''Iterate over all contact rows in given model.

		Keyword argument
		model -- the data model (default TreeFilterModel)
		'''
		if not model:
			model = self.modelfilter
		account_iter = model.get_iter_root()
		while account_iter:
			group_iter = model.iter_children(account_iter)
			while group_iter:
				contact_iter = model.iter_children(group_iter)
				while contact_iter:
					yield model[contact_iter]
					contact_iter = model.iter_next(
						contact_iter)
				group_iter = model.iter_next(group_iter)
			account_iter = model.iter_next(account_iter)


#############################################################################
### Methods for adding and removing roster window items
#############################################################################

	def add_account(self, account):
		'''
		Add account to roster and draw it. Do nothing if it is
		already in.
		'''
		if self._get_account_iter(account):
			# Will happen on reconnect or for merged accounts
			return

		if self.regroup:
			# Merged accounts view
			show = helpers.get_global_show()
			self.model.append(None, [
				gajim.interface.jabber_state_images['16'][show],
				_('Merged accounts'), 'account', '', 'all',
				None, None, None, None, None])
		else:
			show = gajim.SHOW_LIST[gajim.connections[account].connected]
			our_jid = gajim.get_jid_from_account(account)

			tls_pixbuf = None
			if gajim.account_is_securely_connected(account):
				# the only way to create a pixbuf from stock
				tls_pixbuf = self.window.render_icon(
					gtk.STOCK_DIALOG_AUTHENTICATION,
					gtk.ICON_SIZE_MENU)

			self.model.append(None, [
				gajim.interface.jabber_state_images['16'][show],
				gobject.markup_escape_text(account), 'account',
				our_jid, account, None, None, None, None,
				tls_pixbuf])

		self.draw_account(account)


	def add_account_contacts(self, account):
		'''Add all contacts and groups of the given account to roster,
		draw them and account.
		'''
		self.starting = True
		jids = gajim.contacts.get_jid_list(account)

		self.tree.freeze_child_notify()
		for jid in jids:
			self.add_contact(jid, account)
		self.tree.thaw_child_notify()

		# Do not freeze the GUI when drawing the contacts
		if jids:
			# Overhead is big, only invoke when needed
			self._idle_draw_jids_of_account(jids, account)

		# Draw all known groups
		for group in gajim.groups[account]:
			self.draw_group(group, account)
		self.draw_account(account)
		self.starting = False


	def _add_entity(self, contact, account, groups=None,
	big_brother_contact=None, big_brother_account=None):
		'''Add the given contact to roster data model.

		Contact is added regardless if he is already in roster or not.
		Return list of newly added iters.

		Keyword arguments:
		contact -- the contact to add
		account -- the contacts account
		groups -- list of groups to add the contact to.
			  (default groups in contact.get_shown_groups()).
			Parameter ignored when big_brother_contact is specified.
		big_brother_contact -- if specified contact is added as child
			  big_brother_contact. (default None)
		'''
		added_iters = []
		if big_brother_contact:
			# Add contact under big brother

			parent_iters = self._get_contact_iter(
				big_brother_contact.jid, big_brother_account,
				big_brother_contact, self.model)
			assert len(parent_iters) > 0, 'Big brother is not yet in roster!'

			# Do not confuse get_contact_iter: Sync groups of family members
			contact.groups = big_brother_contact.get_shown_groups()[:]

			for child_iter in parent_iters:
				it = self.model.append(child_iter, (None,	contact.get_shown_name(),
				'contact', contact.jid, account, None, None, None, None, None))
				added_iters.append(it)
		else:
			# We are a normal contact. Add us to our groups.
			if not groups:
				groups = contact.get_shown_groups()
			for group in groups:
				child_iterG = self._get_group_iter(group, account,
						model = self.model)
				if not child_iterG:
					# Group is not yet in roster, add it!
					child_iterA = self._get_account_iter(account, self.model)
					child_iterG = self.model.append(child_iterA,
						[gajim.interface.jabber_state_images['16']['closed'],
						gobject.markup_escape_text(group),
						'group', group, account, None, None, None, None, None])
					self.draw_group(group, account)

				if contact.is_transport():
					typestr = 'agent'
				elif contact.is_groupchat():
					typestr = 'groupchat'
				else:
					typestr = 'contact'

				# we add some values here. see draw_contact
				# for more
				i_ = self.model.append(child_iterG, (None,
					contact.get_shown_name(), typestr,
					contact.jid, account, None, None, None,
					None, None))
				added_iters.append(i_)

				# Restore the group expand state
				if account + group in self.collapsed_rows:
					is_expanded = False
				else:
					is_expanded = True
				if group not in gajim.groups[account]:
					gajim.groups[account][group] = {'expand': is_expanded}

		assert len(added_iters), '%s has not been added to roster!' % contact.jid
		return added_iters

	def _remove_entity(self, contact, account, groups=None):
		'''Remove the given contact from roster data model.

		Empty groups after contact removal are removed too.
		Return False if contact still has children and deletion was
		not performed.
		Return True on success.

		Keyword arguments:
		contact -- the contact to add
		account -- the contacts account
		groups -- list of groups to remove the contact from.
		'''
		iters = self._get_contact_iter(contact.jid, account, contact, self.model)
		assert iters, '%s shall be removed but is not in roster' % contact.jid

		parent_iter = self.model.iter_parent(iters[0])
		parent_type = self.model[parent_iter][C_TYPE]

		if groups:
			# Only remove from specified groups
			all_iters = iters[:]
			group_iters = [self._get_group_iter(group, account)
				for group in groups]
			iters = [titer for titer in all_iters
				if self.model.iter_parent(titer) in group_iters]

		iter_children = self.model.iter_children(iters[0])

		if iter_children:
			# We have children. We cannot be removed!
			return False
		else:
			# Remove us and empty groups from the model
			for i in iters:
				assert self.model[i][C_JID] == contact.jid and \
					self.model[i][C_ACCOUNT] == account, \
					"Invalidated iters of %s" % contact.jid

				parent_i = self.model.iter_parent(i)

				if parent_type == 'group' and \
				self.model.iter_n_children(parent_i) == 1:
					group = self.model[parent_i][C_JID].decode('utf-8')
					if group in gajim.groups[account]:
						del gajim.groups[account][group]
					self.model.remove(parent_i)
				else:
					self.model.remove(i)
			return True

	def _add_metacontact_family(self, family, account):
		'''
		Add the give Metacontact family to roster data model.

		Add Big Brother to his groups and all others under him.
		Return list of all added (contact, account) tuples with
		Big Brother as first element.

		Keyword arguments:
		family -- the family, see Contacts.get_metacontacts_family()
		'''

		nearby_family, big_brother_jid, big_brother_account = \
			self._get_nearby_family_and_big_brother(family, account)
		big_brother_contact = gajim.contacts.get_first_contact_from_jid(
			big_brother_account, big_brother_jid)

		assert len(self._get_contact_iter(big_brother_jid,
			big_brother_account, big_brother_contact, self.model)) == 0, \
			'Big brother %s already in roster\n Family: %s' \
			% (big_brother_jid, family)
		self._add_entity(big_brother_contact, big_brother_account)

		brothers = []
		# Filter family members
		for data in nearby_family:
			_account = data['account']
			_jid = data['jid']
			_contact = gajim.contacts.get_first_contact_from_jid(
				_account, _jid)

			if not _contact or _contact == big_brother_contact:
				# Corresponding account is not connected
				# or brother already added
				continue

			assert len(self._get_contact_iter(_jid, _account,
				_contact, self.model)) == 0, \
				"%s already in roster.\n Family: %s" % (_jid, nearby_family)
			self._add_entity(_contact, _account,
				big_brother_contact = big_brother_contact,
				big_brother_account = big_brother_account)
			brothers.append((_contact, _account))

		brothers.insert(0, (big_brother_contact, big_brother_account))
		return brothers

	def _remove_metacontact_family(self, family, account):
		'''
		Remove the given Metacontact family from roster data model.

		See Contacts.get_metacontacts_family() and
		RosterWindow._remove_entity()
		'''
		nearby_family = self._get_nearby_family_and_big_brother(
			family, account)[0]

		# Family might has changed (actual big brother not on top).
		# Remove childs first then big brother
		family_in_roster = False
		for data in nearby_family:
			_account = data['account']
			_jid = data['jid']
			_contact = gajim.contacts.get_first_contact_from_jid(_account, _jid)

			iters = self._get_contact_iter(_jid, _account, _contact, self.model)
			if not iters or not _contact:
				# Family might not be up to date.
				# Only try to remove what is actually in the roster
				continue
			assert iters, '%s shall be removed but is not in roster \
				\n Family: %s' % (_jid, family)

			family_in_roster = True

			parent_iter = self.model.iter_parent(iters[0])
			parent_type = self.model[parent_iter][C_TYPE]

			if parent_type != 'contact':
				# The contact on top
				old_big_account = _account
				old_big_contact = _contact
				old_big_jid = _jid
				continue

			ok = self._remove_entity(_contact, _account)
			assert ok, '%s was not removed' % _jid
			assert len(self._get_contact_iter(_jid, _account, _contact,
				self.model)) == 0, '%s is removed but still in roster' % _jid

		if not family_in_roster:
			return False

		assert old_big_jid, 'No Big Brother in nearby family % (Family: %)' % \
			(nearby_family, family)
		iters = self._get_contact_iter(old_big_jid, old_big_account,
			old_big_contact, self.model)
		assert len(iters) > 0, 'Old Big Brother %s is not in roster anymore' % \
			old_big_jid
		assert not self.model.iter_children(iters[0]),\
			'Old Big Brother %s still has children' % old_big_jid

		ok = self._remove_entity(old_big_contact, old_big_account)
		assert ok, "Old Big Brother %s not removed" % old_big_jid
		assert len(self._get_contact_iter(old_big_jid, old_big_account,
			old_big_contact, self.model)) == 0,\
			'Old Big Brother %s is removed but still in roster' % old_big_jid

		return True


	def _recalibrate_metacontact_family(self, family, account):
		'''Regroup metacontact family if necessary.'''

		brothers = []
		nearby_family, big_brother_jid, big_brother_account = \
			self._get_nearby_family_and_big_brother(family, account)
		big_brother_contact = gajim.contacts.get_contact(big_brother_account,
			big_brother_jid)
		child_iters = self._get_contact_iter(big_brother_jid, big_brother_account,
			model=self.model)
		if child_iters:
			parent_iter = self.model.iter_parent(child_iters[0])
			parent_type = self.model[parent_iter][C_TYPE]

			# Check if the current BigBrother has even been before.
			if parent_type == 'contact':
				for data in nearby_family:
					# recalibrate after remove to keep highlight
					if data['jid'] in gajim.to_be_removed[data['account']]:
						return

				self._remove_metacontact_family(family, account)
				brothers = self._add_metacontact_family(family, account)

				for c, acc in brothers:
					self.draw_completely(c.jid, acc)

		# Check is small brothers are under the big brother
		for child in nearby_family:
			_jid = child['jid']
			_account = child['account']
			if _account == big_brother_account and _jid == big_brother_jid:
				continue
			child_iters = self._get_contact_iter(_jid, _account, model=self.model)
			if not child_iters:
				continue
			parent_iter = self.model.iter_parent(child_iters[0])
			parent_type = self.model[parent_iter][C_TYPE]
			if parent_type != 'contact':
				_contact = gajim.contacts.get_contact(_account, _jid)
				self._remove_entity(_contact, _account)
				self._add_entity(_contact, _account, groups=None,
					big_brother_contact=big_brother_contact,
					big_brother_account=big_brother_account)

	def _get_nearby_family_and_big_brother(self, family, account):
		'''Return the nearby family and its Big Brother

		Nearby family is the part of the family that is grouped with the metacontact.
		A metacontact may be over different accounts. If regroup is s False the
		given family is split account wise.

		(nearby_family, big_brother_jid, big_brother_account)
		'''
		if self.regroup:
			# group all together
			nearby_family = family
		else:
			# we want one nearby_family per account
			nearby_family = [data for data in family
				if account == data['account']]

		big_brother_data = gajim.contacts.get_metacontacts_big_brother(
			nearby_family)
		big_brother_jid = big_brother_data['jid']
		big_brother_account = big_brother_data['account']

		return (nearby_family, big_brother_jid, big_brother_account)


	def _add_self_contact(self, account):
		'''Add account's SelfContact to roster and draw it and the account.

		Return the SelfContact contact instance
		'''
		jid = gajim.get_jid_from_account(account)
		contact = gajim.contacts.get_first_contact_from_jid(account, jid)

		assert len(self._get_contact_iter(jid, account, contact, self.model)) == \
			0, 'Self contact %s already in roster' % jid

		child_iterA = self._get_account_iter(account, self.model)
		self.model.append(child_iterA, (None, gajim.nicks[account],
			'self_contact', jid, account, None, None, None, None,
			None))

		self.draw_completely(jid, account)
		self.draw_account(account)

		return contact


	def redraw_metacontacts(self, account):
		for tag in gajim.contacts.get_metacontacts_tags(account):
			family = gajim.contacts.get_metacontacts_family_from_tag(account, tag)
			self._recalibrate_metacontact_family(family, account)

	def add_contact(self, jid, account):
		'''Add contact to roster and draw him.

		Add contact to all its group and redraw the groups, the contact and the
		account. If it's a Metacontact, add and draw the whole family.
		Do nothing if the contact is already in roster.

		Return the added contact instance. If it is a Metacontact return
		Big Brother.

		Keyword arguments:
		jid -- the contact's jid or SelfJid to add SelfContact
		account -- the corresponding account.

		'''
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if len(self._get_contact_iter(jid, account, contact, self.model)):
			# If contact already in roster, do nothing
			return

		if jid == gajim.get_jid_from_account(account):
			show_self_contact = gajim.config.get('show_self_contact')
			if show_self_contact == 'never':
				return
			if (contact.resource != gajim.connections[account].server_resource and\
			show_self_contact == 'when_other_resource') or show_self_contact == \
			'always':
				return self._add_self_contact(account)
			return

		is_observer = contact.is_observer()
		if is_observer:
			# if he has a tag, remove it
			tag = gajim.contacts.get_metacontacts_tag(account, jid)
			if tag:
				gajim.contacts.remove_metacontact(account, jid)

		# Add contact to roster
		family = gajim.contacts.get_metacontacts_family(account, jid)
		contacts = []
		if family:
			# We have a family. So we are a metacontact.
			# Add all family members that we shall be grouped with
			if self.regroup:
				# remove existing family members to regroup them
				self._remove_metacontact_family(family, account)
			contacts = self._add_metacontact_family(family, account)
		else:
			# We are a normal contact
			contacts = [(contact, account),]
			self._add_entity(contact, account)

		# Draw the contact and its groups contact
		if not self.starting:
			for c, acc in contacts:
				self.draw_completely(c.jid, acc)
			for group in contact.get_shown_groups():
				self.draw_group(group, account)
				self._adjust_group_expand_collapse_state(group, account)
			self.draw_account(account)

		return contacts[0][0] # it's contact/big brother with highest priority

	def remove_contact(self, jid, account, force=False, backend=False):
		'''Remove contact from roster.

		Remove contact from all its group. Remove empty groups or redraw
		otherwise.
		Draw the account.
		If it's a Metacontact, remove the whole family.
		Do nothing if the contact is not in roster.

		Keyword arguments:
		jid -- the contact's jid or SelfJid to remove SelfContact
		account -- the corresponding account.
		force -- remove contact even it has pending evens (Default False)
		backend -- also remove contact instance (Default False)

		'''
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if not contact:
			return

		if not force and (self.contact_has_pending_roster_events(contact,
		account) or gajim.interface.msg_win_mgr.get_control(jid, account)):
			# Contact has pending events or window
			#TODO: or single message windows? Bur they are not listed for the
			# moment
			key = (jid, account)
			if not key in self.contacts_to_be_removed:
				self.contacts_to_be_removed[key] = {'backend': backend}
			# if more pending event, don't remove from roster
			if self.contact_has_pending_roster_events(contact, account):
				return False

		iters = self._get_contact_iter(jid, account, contact, self.model)
		if iters:
			# no more pending events
			# Remove contact from roster directly
			family = gajim.contacts.get_metacontacts_family(account, jid)
			if family:
				# We have a family. So we are a metacontact.
				self._remove_metacontact_family(family, account)
			else:
				self._remove_entity(contact, account)

		if backend and (not gajim.interface.msg_win_mgr.get_control(jid, account)\
		or force):
			# If a window is still opened: don't remove contact instance
			# Remove contact before redrawing, otherwise the old
			# numbers will still be show
			gajim.contacts.remove_jid(account, jid, remove_meta=True)
			if iters:
				rest_of_family = [data for data in family
					if account != data['account'] or jid != data['jid']]
				if rest_of_family:
					# reshow the rest of the family
					brothers = self._add_metacontact_family(rest_of_family, account)
					for c, acc in brothers:
						self.draw_completely(c.jid, acc)

		if iters:
			# Draw all groups of the contact
			for group in contact.get_shown_groups():
				self.draw_group(group, account)
			self.draw_account(account)

		return True

	def add_groupchat(self, jid, account, status=''):
		'''Add groupchat to roster and draw it.
		Return the added contact instance.
		'''
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		# Do not show gc if we are disconnected and minimize it
		if gajim.account_is_connected(account):
			show = 'online'
		else:
			show = 'offline'
			status = ''

		if contact is None:
			gc_control = gajim.interface.msg_win_mgr.get_gc_control(jid, account)
			if gc_control:
				# there is a window that we can minimize
				gajim.interface.minimized_controls[account][jid] = gc_control
				name = gc_control.name
			elif jid in gajim.interface.minimized_controls[account]:
				name = gajim.interface.minimized_controls[account][jid].name
			else:
				name = jid.split('@')[0]
			# New groupchat
			contact = gajim.contacts.create_contact(jid=jid, name=name,
				groups=[_('Groupchats')], show=show, status=status, sub='none')
			gajim.contacts.add_contact(account, contact)
			self.add_contact(jid, account)
		else:
			if jid not in gajim.interface.minimized_controls[account]:
				# there is a window that we can minimize
				gc_control = gajim.interface.msg_win_mgr.get_gc_control(jid,
					account)
				gajim.interface.minimized_controls[account][jid] = gc_control
			contact.show = show
			contact.status = status
			self.adjust_and_draw_contact_context(jid, account)

		return contact


	def remove_groupchat(self, jid, account):
		'''Remove groupchat from roster and redraw account and group.'''
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if contact.is_groupchat():
			if jid in gajim.interface.minimized_controls[account]:
				del gajim.interface.minimized_controls[account][jid]
			self.remove_contact(jid, account, force=True, backend=True)
			return True
		else:
			return False


	# FIXME: This function is yet unused! Port to new API
	def add_transport(self, jid, account):
		'''Add transport to roster and draw it.
		Return the added contact instance.'''
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		if contact is None:
			contact = gajim.contacts.create_contact(jid=jid, name=jid,
				groups=[_('Transports')], show='offline', status='offline',
				sub='from')
			gajim.contacts.add_contact(account, contact)
		self.add_contact(jid, account)
		return contact

	def remove_transport(self, jid, account):
		'''Remove transport from roster and redraw account and group.'''
		self.remove_contact(jid, account, force=True, backend=True)
		return True
		
	def rename_group(self, old_name, new_name, account):
		"""
		rename a roster group
		"""
		if old_name == new_name:
			return
		
		# Groups may not change name from or to a special groups
		for g in helpers.special_groups:
			if g in (new_name, old_name):
				return
		
		# update all contacts in the given group
		if self.regroup:
			accounts = gajim.connections.keys()
		else:
			accounts = [account,]
		
		for acc in accounts:
			changed_contacts = []
			for jid in gajim.contacts.get_jid_list(acc):
				contact = gajim.contacts.get_first_contact_from_jid(acc, jid)
				if old_name not in contact.groups:
					continue
				
				self.remove_contact(jid, acc, force=True)
				
				contact.groups.remove(old_name)
				if new_name not in contact.groups:
					contact.groups.append(new_name)
			
				changed_contacts.append({'jid':jid, 'name':contact.name, 
					'groups':contact.groups})
			
			gajim.connections[acc].update_contacts(changed_contacts)				
			
			for c in changed_contacts:
				self.add_contact(c['jid'], acc)
				
			self._adjust_group_expand_collapse_state(new_name, acc)
			
			self.draw_group(old_name, acc)
			self.draw_group(new_name, acc)
					

	def add_contact_to_groups(self, jid, account, groups, update=True):
		'''Add contact to given groups and redraw them.

		Contact on server is updated too. When the contact has a family,
		the action will be performed for all members.

		Keyword Arguments:
		jid -- the jid
		account -- the corresponding account
		groups -- list of Groups to add the contact to.
		update -- update contact on the server

		'''
		self.remove_contact(jid, account, force=True)
		for contact in gajim.contacts.get_contacts(account, jid):
			for group in groups:
				if group not in contact.groups:
					# we might be dropped from meta to group
					contact.groups.append(group)
			if update:
				gajim.connections[account].update_contact(jid, contact.name,
					contact.groups)

		self.add_contact(jid, account)

		for group in groups:
			self._adjust_group_expand_collapse_state(group, account)

	def remove_contact_from_groups(self, jid, account, groups, update=True):
		'''Remove contact from given groups and redraw them.

		Contact on server is updated too. When the contact has a family,
		the action will be performed for all members.

		Keyword Arguments:
		jid -- the jid
		account -- the corresponding account
		groups -- list of Groups to remove the contact from
		update -- update contact on the server

		'''
		self.remove_contact(jid, account, force=True)
		for contact in gajim.contacts.get_contacts(account, jid):
			for group in groups:
				if group in contact.groups:
					# Needed when we remove from "General" or "Observers"
					contact.groups.remove(group)
			if update:
				gajim.connections[account].update_contact(jid, contact.name,
					contact.groups)
		self.add_contact(jid, account)

		# Also redraw old groups
		for group in groups:
			self.draw_group(group, account)

	# FIXME: maybe move to gajim.py
	def remove_newly_added(self, jid, account):
		if jid in gajim.newly_added[account]:
			gajim.newly_added[account].remove(jid)
			self.draw_contact(jid, account)

	# FIXME: maybe move to gajim.py
	def remove_to_be_removed(self, jid, account):
		if account not in gajim.interface.instances:
			# Account has been deleted during the timeout that called us
			return
		if jid in gajim.newly_added[account]:
			return
		if jid in gajim.to_be_removed[account]:
			gajim.to_be_removed[account].remove(jid)
			family = gajim.contacts.get_metacontacts_family(account, jid)
			if family:
				# Peform delayed recalibration
				self._recalibrate_metacontact_family(family, account)
			self.draw_contact(jid, account)

	#FIXME: integrate into add_contact()
	def add_to_not_in_the_roster(self, account, jid, nick='', resource=''):
		keyID = ''
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		if jid in attached_keys:
			keyID = attached_keys[attached_keys.index(jid) + 1]
		contact = gajim.contacts.create_contact(jid=jid, name=nick,
			groups=[_('Not in Roster')], show='not in roster', status='',
			sub='none', resource=resource, keyID=keyID)
		gajim.contacts.add_contact(account, contact)
		self.add_contact(contact.jid, account)
		return contact


################################################################################
### Methods for adding and removing roster window items
################################################################################

	def draw_account(self, account):
		child_iter = self._get_account_iter(account, self.model)
		if not child_iter:
			assert False, 'Account iter of %s could not be found.' % account
			return

		num_of_accounts = gajim.get_number_of_connected_accounts()
		num_of_secured = gajim.get_number_of_securely_connected_accounts()

		if gajim.account_is_securely_connected(account) and not self.regroup or \
		self.regroup and num_of_secured and num_of_secured == num_of_accounts:
			tls_pixbuf = self.window.render_icon(gtk.STOCK_DIALOG_AUTHENTICATION,
				gtk.ICON_SIZE_MENU) # the only way to create a pixbuf from stock
			self.model[child_iter][C_PADLOCK_PIXBUF] = tls_pixbuf
		else:
			self.model[child_iter][C_PADLOCK_PIXBUF] = None

		if self.regroup:
			account_name = _('Merged accounts')
			accounts = []
		else:
			account_name = account
			accounts = [account]

		if account in self.collapsed_rows and \
		self.model.iter_has_child(child_iter):
			account_name = '[%s]' % account_name

		if (gajim.account_is_connected(account) or (self.regroup and \
		gajim.get_number_of_connected_accounts())) and gajim.config.get(
		'show_contacts_number'):
			nbr_on, nbr_total = gajim.contacts.get_nb_online_total_contacts(
				accounts = accounts)
			account_name += ' (%s/%s)' % (repr(nbr_on), repr(nbr_total))

		self.model[child_iter][C_NAME] = account_name

		if gajim.config.get('show_mood_in_roster') \
		and 'mood' in gajim.connections[account].mood \
		and gajim.connections[account].mood['mood'].strip() in MOODS:

			self.model[child_iter][C_MOOD_PIXBUF] = gtkgui_helpers.load_mood_icon(
				gajim.connections[account].mood['mood'].strip()).get_pixbuf()

		elif gajim.config.get('show_mood_in_roster') \
		and 'mood' in gajim.connections[account].mood:
			self.model[child_iter][C_MOOD_PIXBUF] = \
				gtkgui_helpers.load_mood_icon('unknown'). \
				get_pixbuf()
		else:
			self.model[child_iter][C_MOOD_PIXBUF] = None

		if gajim.config.get('show_activity_in_roster') \
		and 'activity' in gajim.connections[account].activity \
		and gajim.connections[account].activity['activity'].strip() \
		in ACTIVITIES:
			if 'subactivity' in gajim.connections[account].activity \
			and gajim.connections[account].activity['subactivity'].strip() \
			in ACTIVITIES[gajim.connections[account].activity['activity'].strip()]:
				self.model[child_iter][C_ACTIVITY_PIXBUF] = \
					gtkgui_helpers.load_activity_icon(
					gajim.connections[account].activity['activity'].strip(),
					gajim.connections[account].activity['subactivity'].strip()). \
					get_pixbuf()
			else:
				self.model[child_iter][C_ACTIVITY_PIXBUF] = \
					gtkgui_helpers.load_activity_icon(
					gajim.connections[account].activity['activity'].strip()). \
					get_pixbuf()
		elif gajim.config.get('show_activity_in_roster') \
		and 'activity' in gajim.connections[account].activity:
			self.model[child_iter][C_ACTIVITY_PIXBUF] = \
				gtkgui_helpers.load_activity_icon('unknown'). \
				get_pixbuf()
		else:
			self.model[child_iter][C_ACTIVITY_PIXBUF] = None

		if gajim.config.get('show_tunes_in_roster') \
		and ('artist' in gajim.connections[account].tune \
		or 'title' in gajim.connections[account].tune):
			path = os.path.join(gajim.DATA_DIR, 'emoticons', 'static', 'music.png')
			self.model[child_iter][C_TUNE_PIXBUF] = \
				gtk.gdk.pixbuf_new_from_file(path)
		else:
			self.model[child_iter][C_TUNE_PIXBUF] = None

		return False

	def draw_group(self, group, account):
		child_iter = self._get_group_iter(group, account, model=self.model)
		if not child_iter:
			# Eg. We redraw groups after we removed a entitiy
			# and its empty groups
			return
		if self.regroup:
			accounts = []
		else:
			accounts = [account]
		text = gobject.markup_escape_text(group)
		if helpers.group_is_blocked(account, group):
			text = '<span strikethrough="true">%s</span>' % text
		if gajim.config.get('show_contacts_number'):
			nbr_on, nbr_total = gajim.contacts.get_nb_online_total_contacts(
				accounts = accounts, groups = [group])
			text += ' (%s/%s)' % (repr(nbr_on), repr(nbr_total))

		self.model[child_iter][C_NAME] = text
		return False

	def draw_parent_contact(self, jid, account):
		child_iters = self._get_contact_iter(jid, account, model=self.model)
		if not child_iters:
			return False
		parent_iter = self.model.iter_parent(child_iters[0])
		if self.model[parent_iter][C_TYPE] != 'contact':
			# parent is not a contact
			return
		parent_jid = self.model[parent_iter][C_JID].decode('utf-8')
		parent_account = self.model[parent_iter][C_ACCOUNT].decode('utf-8')
		self.draw_contact(parent_jid, parent_account)
		return False

	def draw_contact(self, jid, account, selected=False, focus=False):
		'''draw the correct state image, name BUT not avatar'''
		# focus is about if the roster window has toplevel-focus or not
		# FIXME: We really need a custom cell_renderer

		contact_instances = gajim.contacts.get_contacts(account, jid)
		contact = gajim.contacts.get_highest_prio_contact_from_contacts(
			contact_instances)

		child_iters = self._get_contact_iter(jid, account, contact, self.model)
		if not child_iters:
			return False

		name = gobject.markup_escape_text(contact.get_shown_name())

		# gets number of unread gc marked messages
		if jid in gajim.interface.minimized_controls[account] and \
		gajim.interface.minimized_controls[account][jid]:
			nb_unread = len(gajim.events.get_events(account, jid,
				['printed_marked_gc_msg']))
			nb_unread += gajim.interface.minimized_controls \
				[account][jid].get_nb_unread_pm()

			if nb_unread == 1:
				name = '%s *' % name
			elif nb_unread > 1:
				name = '%s [%s]' % (name, str(nb_unread))

		# Strike name if blocked
		strike = False
		if helpers.jid_is_blocked(account, jid):
			strike = True
		else:
			for group in contact.get_shown_groups():
				if helpers.group_is_blocked(account, group):
					strike = True
					break
		if strike:
			name = '<span strikethrough="true">%s</span>' % name

		# Show resource counter
		nb_connected_contact = 0
		for c in contact_instances:
			if c.show not in ('error', 'offline'):
				nb_connected_contact += 1
		if nb_connected_contact > 1:
			# switch back to default writing direction
			name += i18n.paragraph_direction_mark(unicode(name))
			name += u' (%d)' % nb_connected_contact

		# show (account_name) if there are 2 contact with same jid
		# in merged mode
		if self.regroup:
			add_acct = False
			# look through all contacts of all accounts
			for account_ in gajim.connections:
				# useless to add account name
				if account_ == account:
					continue
				for jid_ in gajim.contacts.get_jid_list(account_):
					contact_ = gajim.contacts.get_first_contact_from_jid(
						account_, jid_)
					if contact_.get_shown_name() == contact.get_shown_name() and \
					(jid_, account_) != (jid, account):
						add_acct = True
						break
				if add_acct:
					# No need to continue in other account
					# if we already found one
					break
			if add_acct:
				name += ' (' + account + ')'

		# add status msg, if not empty, under contact name in
		# the treeview
		if contact.status and gajim.config.get('show_status_msgs_in_roster'):
			status = contact.status.strip()
			if status != '':
				status = helpers.reduce_chars_newlines(status,
					max_lines = 1)
				# escape markup entities and make them small
				# italic and fg color color is calcuted to be
				# always readable
				color = gtkgui_helpers._get_fade_color(self.tree, selected, focus)
				colorstring = '#%04x%04x%04x' % (color.red, color.green, color.blue)
				name += '\n<span size="small" style="italic" ' \
					'foreground="%s">%s</span>' % (
					colorstring,
					gobject.markup_escape_text(status))

		icon_name = helpers.get_icon_name_to_show(contact, account)
		# look if another resource has awaiting events
		for c in contact_instances:
			c_icon_name = helpers.get_icon_name_to_show(c, account)
			if c_icon_name in ('event', 'muc_active', 'muc_inactive'):
				icon_name = c_icon_name
				break

		# Check for events of collapsed (hidden) brothers
		family = gajim.contacts.get_metacontacts_family(account, jid)
		is_big_brother = False
		have_visible_children = False
		if family:
			bb_jid, bb_account = \
				self._get_nearby_family_and_big_brother(family, account)[1:]
			is_big_brother = (jid, account) == (bb_jid, bb_account)
			iters = self._get_contact_iter(jid, account)
			have_visible_children = iters \
				and self.modelfilter.iter_has_child(iters[0])

		if have_visible_children:
			# We are the big brother and have a visible family
			for child_iter in child_iters:
				child_path = self.model.get_path(child_iter)
				path = self.modelfilter.convert_child_path_to_path(child_path)

				if not self.tree.row_expanded(path) and icon_name != 'event':
					iterC = self.model.iter_children(child_iter)
					while iterC:
						# a child has awaiting messages?
						jidC = self.model[iterC][C_JID].decode('utf-8')
						accountC = self.model[iterC][C_ACCOUNT].decode('utf-8')
						if len(gajim.events.get_events(accountC, jidC)):
							icon_name = 'event'
							break
						iterC = self.model.iter_next(iterC)

				if self.tree.row_expanded(path):
					state_images = self.get_appropriate_state_images(
						jid, size = 'opened',
						icon_name = icon_name)
				else:
					state_images = self.get_appropriate_state_images(
						jid, size = 'closed',
						icon_name = icon_name)

				# Expand/collapse icon might differ per iter
				# (group)
				img = state_images[icon_name]
				self.model[child_iter][C_IMG] = img
				self.model[child_iter][C_NAME] = name
		else:
			# A normal contact or little brother
			state_images = self.get_appropriate_state_images(jid,
				icon_name = icon_name)

			# All iters have the same icon (no expand/collapse)
			img = state_images[icon_name]
			for child_iter in child_iters:
				self.model[child_iter][C_IMG] = img
				self.model[child_iter][C_NAME] = name

			# We are a little brother
			if family and not is_big_brother and not self.starting:
				self.draw_parent_contact(jid, account)

		for group in contact.get_shown_groups():
			# We need to make sure that _visible_func is called for
			# our groups otherwise we might not be shown
			iterG = self._get_group_iter(group, account, model=self.model)
			if iterG:
				# it's not self contact
				self.model[iterG][C_JID] = self.model[iterG][C_JID]

		return False


	def draw_mood(self, jid, account):
		iters = self._get_contact_iter(jid, account, model=self.model)
		if not iters or not gajim.config.get('show_mood_in_roster'):
			return
		jid = self.model[iters[0]][C_JID]
		jid = jid.decode('utf-8')
		contact = gajim.contacts.get_contact(account, jid)
		if 'mood' in contact.mood and contact.mood['mood'].strip() in MOODS:
			pixbuf = gtkgui_helpers.load_mood_icon(
				contact.mood['mood'].strip()).get_pixbuf()
		elif 'mood' in contact.mood:
			pixbuf = gtkgui_helpers.load_mood_icon(
				'unknown').get_pixbuf()
		else:
			pixbuf = None
		for child_iter in iters:
			self.model[child_iter][C_MOOD_PIXBUF] = pixbuf
		return False


	def draw_activity(self, jid, account):
		iters = self._get_contact_iter(jid, account, model=self.model)
		if not iters or not gajim.config.get('show_activity_in_roster'):
			return
		jid = self.model[iters[0]][C_JID]
		jid = jid.decode('utf-8')
		contact = gajim.contacts.get_contact(account, jid)
		if 'activity' in contact.activity \
		and contact.activity['activity'].strip() in ACTIVITIES:
			if 'subactivity' in contact.activity \
			and contact.activity['subactivity'].strip() in \
			ACTIVITIES[contact.activity['activity'].strip()]:
				pixbuf = gtkgui_helpers.load_activity_icon(
					contact.activity['activity'].strip(),
					contact.activity['subactivity'].strip()).get_pixbuf()
			else:
				pixbuf = gtkgui_helpers.load_activity_icon(
					contact.activity['activity'].strip()).get_pixbuf()
		elif 'activity' in contact.activity:
			pixbuf = gtkgui_helpers.load_activity_icon(
				'unknown').get_pixbuf()
		else:
			pixbuf = None
		for child_iter in iters:
			self.model[child_iter][C_ACTIVITY_PIXBUF] = pixbuf
		return False


	def draw_tune(self, jid, account):
		iters = self._get_contact_iter(jid, account, model=self.model)
		if not iters or not gajim.config.get('show_tunes_in_roster'):
			return
		jid = self.model[iters[0]][C_JID]
		jid = jid.decode('utf-8')
		contact = gajim.contacts.get_contact(account, jid)
		if 'artist' in contact.tune or 'title' in contact.tune:
			path = os.path.join(gajim.DATA_DIR, 'emoticons', 'static', 'music.png')
			pixbuf = gtk.gdk.pixbuf_new_from_file(path)
		else:
			pixbuf = None
		for child_iter in iters:
			self.model[child_iter][C_TUNE_PIXBUF] = pixbuf
		return False


	def draw_avatar(self, jid, account):
		iters = self._get_contact_iter(jid, account, model=self.model)
		if not iters or not gajim.config.get('show_avatars_in_roster'):
			return
		jid = self.model[iters[0]][C_JID]
		jid = jid.decode('utf-8')
		pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(jid)
		if pixbuf is None or pixbuf == 'ask':
			scaled_pixbuf = None
		else:
			scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'roster')
		for child_iter in iters:
			self.model[child_iter][C_AVATAR_PIXBUF] = scaled_pixbuf
		return False

	def draw_completely(self, jid, account):
		self.draw_contact(jid, account)
		self.draw_mood(jid, account)
		self.draw_activity(jid, account)
		self.draw_tune(jid, account)
		self.draw_avatar(jid, account)

	def adjust_and_draw_contact_context(self, jid, account):
		'''Draw contact, account and groups of given jid
		Show contact if it has pending events
		'''
		contact = gajim.contacts.get_first_contact_from_jid(account, jid)
		if not contact:
			# idle draw or just removed SelfContact
			return

		family = gajim.contacts.get_metacontacts_family(account, jid)
		if family:
			# There might be a new big brother
			self._recalibrate_metacontact_family(family, account)
		self.draw_contact(jid, account)
		self.draw_account(account)

		for group in contact.get_shown_groups():
			self.draw_group(group, account)
			self._adjust_group_expand_collapse_state(group, account)

	def _idle_draw_jids_of_account(self, jids, account):
		'''Draw given contacts and their avatars in a lazy fashion.

		Keyword arguments:
		jids -- a list of jids to draw
		account -- the corresponding account
		'''
		def _draw_all_contacts(jids, account):
			for jid in jids:
				family = gajim.contacts.get_metacontacts_family(account, jid)
				if family:
					# For metacontacts over several accounts:
					# When we connect a new account existing brothers
					# must be redrawn (got removed and readded)
					for data in family:
						self.draw_completely(data['jid'], data['account'])
				else:
					self.draw_completely(jid, account)
				yield True
			yield False

		task = _draw_all_contacts(jids, account)
		gobject.idle_add(task.next)

	def setup_and_draw_roster(self):
		'''create new empty model and draw roster'''
		self.modelfilter = None
		# (icon, name, type, jid, account, editable, mood_pixbuf,
		# activity_pixbuf, tune_pixbuf avatar_pixbuf, padlock_pixbuf)
		self.model = gtk.TreeStore(gtk.Image, str, str, str, str,
			gtk.gdk.Pixbuf, gtk.gdk.Pixbuf, gtk.gdk.Pixbuf,
			gtk.gdk.Pixbuf, gtk.gdk.Pixbuf)

		self.model.set_sort_func(1, self._compareIters)
		self.model.set_sort_column_id(1, gtk.SORT_ASCENDING)
		self.modelfilter = self.model.filter_new()
		self.modelfilter.set_visible_func(self._visible_func)
		self.modelfilter.connect('row-has-child-toggled',
			self.on_modelfilter_row_has_child_toggled)
		self.tree.set_model(self.modelfilter)

		for acct in gajim.connections:
			self.add_account(acct)
			self.add_account_contacts(acct)
		# Recalculate column width for ellipsizing
		self.tree.columns_autosize()


	def select_contact(self, jid, account):
		'''Select contact in roster. If contact is hidden but has events,
		show him.'''
		# Refiltering SHOULD NOT be needed:
		# When a contact gets a new event he will be redrawn and his
		# icon changes, so _visible_func WILL be called on him anyway
		iters = self._get_contact_iter(jid, account)
		if not iters:
			# Not visible in roster
			return
		path = self.modelfilter.get_path(iters[0])
		if self.dragging or not gajim.config.get('scroll_roster_to_last_message'):
			# do not change selection while DND'ing
			return
		# Expand his parent, so this path is visible, don't expand it.
		self.tree.expand_to_path(path[:-1])
		self.tree.scroll_to_cell(path)
		self.tree.set_cursor(path)


	def _adjust_account_expand_collapse_state(self, account):
		'''Expand/collapse account row based on self.collapsed_rows'''
		iterA = self._get_account_iter(account)
		if not iterA:
			# thank you modelfilter
			return
		path = self.modelfilter.get_path(iterA)
		if account in self.collapsed_rows:
			self.tree.collapse_row(path)
		else:
			self.tree.expand_row(path, False)
		return False


	def _adjust_group_expand_collapse_state(self, group, account):
		'''Expand/collapse group row based on self.collapsed_rows'''
		iterG = self._get_group_iter(group, account)
		if not iterG:
			# Group not visible
			return
		path = self.modelfilter.get_path(iterG)
		if account + group in self.collapsed_rows:
			self.tree.collapse_row(path)
		else:
			self.tree.expand_row(path, False)
		return False

##############################################################################
### Roster and Modelfilter handling
##############################################################################

	def _search_roster_func(self, model, column, key, titer):
		key = key.decode('utf-8').lower()
		name = model[titer][C_NAME].decode('utf-8').lower()
		return not (key in name)

	def refilter_shown_roster_items(self):
		self.filtering = True
		self.modelfilter.refilter()
		self.filtering = False

	def contact_has_pending_roster_events(self, contact, account):
		'''Return True if the contact or one if it resources has pending events'''
		# jid has pending events
		if gajim.events.get_nb_roster_events(account, contact.jid) > 0:
			return True
		# check events of all resources
		for contact_ in gajim.contacts.get_contacts(account, contact.jid):
			if contact_.resource and gajim.events.get_nb_roster_events(account,
			contact_.get_full_jid()) > 0:
				return True
		return False

	def contact_is_visible(self, contact, account):
		if self.contact_has_pending_roster_events(contact, account):
			return True

		if contact.show in ('offline', 'error'):
			if contact.jid in gajim.to_be_removed[account]:
				return True
			return False
		if gajim.config.get('show_only_chat_and_online') and contact.show in (
		'away', 'xa', 'busy'):
			return False
		return True

	def _visible_func(self, model, titer):
		'''Determine whether iter should be visible in the treeview'''
		type_ = model[titer][C_TYPE]
		if not type_:
			return False
		if type_ == 'account':
			# Always show account
			return True

		account = model[titer][C_ACCOUNT]
		if not account:
			return False

		account = account.decode('utf-8')
		jid = model[titer][C_JID]
		if not jid:
			return False
		jid = jid.decode('utf-8')
		if type_ == 'group':
			group = jid
			if group == _('Transports'):
				return gajim.config.get('show_transports_group') and \
					(gajim.account_is_connected(account) or \
					gajim.config.get('showoffline'))
			if gajim.config.get('showoffline'):
				return True


			if self.regroup:
				# C_ACCOUNT for groups depends on the order
				# accounts were connected
				# Check all accounts for online group contacts
				accounts = gajim.contacts.get_accounts()
			else:
				accounts = [account]
			for _acc in accounts:
				for contact in gajim.contacts.iter_contacts(_acc):
					# Is this contact in this group ? (last part of if check if it's
					# self contact)
					if group in contact.get_shown_groups():
						if self.contact_is_visible(contact, _acc):
							return True
			return False
		if type_ == 'contact':
			if gajim.config.get('showoffline'):
				return True
			bb_jid = None
			bb_account = None
			family = gajim.contacts.get_metacontacts_family(account, jid)
			if family:
				nearby_family, bb_jid, bb_account = \
					self._get_nearby_family_and_big_brother(family, account)
			if (bb_jid, bb_account) == (jid, account):
				# Show the big brother if a child has pending events
				for data in nearby_family:
					jid = data['jid']
					account = data['account']
					contact = gajim.contacts.get_contact_with_highest_priority(
						account, jid)
					if contact and self.contact_is_visible(contact, account):
						return True
				return False
			else:
				contact = gajim.contacts.get_contact_with_highest_priority(account,
					jid)
				return self.contact_is_visible(contact, account)
		if type_ == 'agent':
			return gajim.config.get('show_transports_group') and \
				(gajim.account_is_connected(account) or \
				gajim.config.get('showoffline'))
		return True

	def _compareIters(self, model, iter1, iter2, data=None):
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
			lcontact1 = gajim.contacts.get_contacts(account1, jid1)
			contact1 = gajim.contacts.get_first_contact_from_jid(account1, jid1)
			if not contact1:
				return 0
			name1 = contact1.get_shown_name()
		if type2 == 'contact':
			lcontact2 = gajim.contacts.get_contacts(account2, jid2)
			contact2 = gajim.contacts.get_first_contact_from_jid(account2, jid2)
			if not contact2:
				return 0
			name2 = contact2.get_shown_name()
		# We first compare by show if sort_by_show_in_roster is True or if it's a
		# child contact
		if type1 == 'contact' and type2 == 'contact' and \
		gajim.config.get('sort_by_show_in_roster'):
			cshow = {'chat':0, 'online': 1, 'away': 2, 'xa': 3, 'dnd': 4,
				'invisible': 5, 'offline': 6, 'not in roster': 7, 'error': 8}
			s = self.get_show(lcontact1)
			show1 = cshow.get(s, 9)
			s = self.get_show(lcontact2)
			show2 = cshow.get(s, 9)
			removing1 = False
			removing2 = False
			if show1 == 6 and jid1 in gajim.to_be_removed[account1]:
				removing1 = True
			if show2 == 6 and jid2 in gajim.to_be_removed[account2]:
				removing2 = True
			if removing1 and not removing2:
				return 1
			if removing2 and not removing1:
				return -1
			sub1 = contact1.sub
			sub2 = contact2.sub
			# none and from goes after
			if sub1 not in ['none', 'from'] and sub2 in ['none', 'from']:
				return -1
			if sub1 in ['none', 'from'] and sub2 not in ['none', 'from']:
				return 1
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

################################################################################
### FIXME: Methods that don't belong to roster window...
###		... atleast not in there current form
################################################################################

	def fire_up_unread_messages_events(self, account):
		'''reads from db the unread messages, and fire them up, and
		if we find very old unread messages, delete them from unread table'''
		results = gajim.logger.get_unread_msgs()
		for result in results:
			jid = result[4]
			shown = result[5]
			if gajim.contacts.get_first_contact_from_jid(account, jid) and not \
			shown:
				# We have this jid in our contacts list
				# XXX unread messages should probably have their session saved with
				# them
				session = gajim.connections[account].make_new_session(jid)

				tim = time.localtime(float(result[2]))
				session.roster_message(jid, result[1], tim, msg_type='chat',
					msg_id=result[0])
				gajim.logger.set_shown_unread_msgs(result[0])

			elif (time.time() - result[2]) > 2592000:
				# ok, here we see that we have a message in unread messages table
				# that is older than a month. It is probably from someone not in our
				# roster for accounts we usually launch, so we will delete this id
				# from unread message tables.
				gajim.logger.set_read_messages([result[0]])

	def fill_contacts_and_groups_dicts(self, array, account):
		'''fill gajim.contacts and gajim.groups'''
		# FIXME: This function needs to be splitted
		# Most of the logic SHOULD NOT be done at GUI level
		if account not in gajim.contacts.get_accounts():
			gajim.contacts.add_account(account)
		if account not in gajim.groups:
			gajim.groups[account] = {}
		if gajim.config.get('show_self_contact') == 'always':
			self_jid = gajim.get_jid_from_account(account)
			if gajim.connections[account].server_resource:
				self_jid += '/' + gajim.connections[account].server_resource
			array[self_jid] = {'name': gajim.nicks[account],
				'groups': ['self_contact'], 'subscription': 'both', 'ask': 'none'}
		# .keys() is needed
		for jid in array.keys():
			# Remove the contact in roster. It might has changed
			self.remove_contact(jid, account, force=True)
			# Remove old Contact instances
			gajim.contacts.remove_jid(account, jid, remove_meta=False)
			jids = jid.split('/')
			# get jid
			ji = jids[0]
			# get resource
			resource = ''
			if len(jids) > 1:
				resource = '/'.join(jids[1:])
			# get name
			name = array[jid]['name'] or ''
			show = 'offline' # show is offline by default
			status = '' # no status message by default

			keyID = ''
			attached_keys = gajim.config.get_per('accounts', account,
				'attached_gpg_keys').split()
			if jid in attached_keys:
				keyID = attached_keys[attached_keys.index(jid) + 1]

			if gajim.jid_is_transport(jid):
				array[jid]['groups'] = [_('Transports')]
			contact1 = gajim.contacts.create_contact(jid=ji, name=name,
				groups=array[jid]['groups'], show=show, status=status,
				sub=array[jid]['subscription'], ask=array[jid]['ask'],
				resource=resource, keyID=keyID)
			gajim.contacts.add_contact(account, contact1)

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
						if host not in gajim.transport_avatar[account]:
							gajim.transport_avatar[account][host] = [contact1.jid]
						else:
							gajim.transport_avatar[account][host].append(contact1.jid)

			# If we already have chat windows opened, update them with new contact
			# instance
			chat_control = gajim.interface.msg_win_mgr.get_control(ji, account)
			if chat_control:
				chat_control.contact = contact1

	def connected_rooms(self, account):
		if account in gajim.gc_connected[account].values():
			return True
		return False

	def on_event_removed(self, event_list):
		'''Remove contacts on last events removed.

		Only performed if removal was requested before 	but the contact
		still had pending events
		'''
		contact_list = ((event.jid.split('/')[0], event.account) for event in \
			event_list)

		for jid, account in contact_list:
			self.draw_contact(jid, account)
			# Remove contacts in roster if removal was requested
			key = (jid, account)
			if key in self.contacts_to_be_removed.keys():
				backend = self.contacts_to_be_removed[key]['backend']
				del self.contacts_to_be_removed[key]
				# Remove contact will delay removal if there are more events pending
				self.remove_contact(jid, account, backend=backend)
		self.show_title()

	def open_event(self, account, jid, event):
		'''If an event was handled, return True, else return False'''
		data = event.parameters
		ft = gajim.interface.instances['file_transfers']
		event = gajim.events.get_first_event(account, jid, event.type_)
		if event.type_ == 'normal':
			dialogs.SingleMessageWindow(account, jid,
				action='receive', from_whom=jid, subject=data[1], message=data[0],
				resource=data[5], session=data[8], form_node=data[9])
			gajim.events.remove_events(account, jid, event)
			return True
		elif event.type_ == 'file-request':
			contact = gajim.contacts.get_contact_with_highest_priority(account,
				jid)
			ft.show_file_request(account, contact, data)
			gajim.events.remove_events(account, jid, event)
			return True
		elif event.type_ in ('file-request-error', 'file-send-error'):
			ft.show_send_error(data)
			gajim.events.remove_events(account, jid, event)
			return True
		elif event.type_ in ('file-error', 'file-stopped'):
			msg_err = ''
			if data['error'] == -1:
				msg_err = _('Remote contact stopped transfer')
			elif data['error'] == -6:
				msg_err = _('Error opening file')
			ft.show_stopped(jid, data, error_msg=msg_err)
			gajim.events.remove_events(account, jid, event)
			return True
		elif event.type_ == 'file-completed':
			ft.show_completed(jid, data)
			gajim.events.remove_events(account, jid, event)
			return True
		elif event.type_ == 'gc-invitation':
			dialogs.InvitationReceivedDialog(account, data[0], jid, data[2],
				data[1])
			gajim.events.remove_events(account, jid, event)
			return True
		elif event.type_ == 'subscription_request':
			dialogs.SubscriptionRequestWindow(jid, data[0], account, data[1])
			gajim.events.remove_events(account, jid, event)
			return True
		elif event.type_ == 'unsubscribed':
			gajim.interface.show_unsubscribed_dialog(account, data)
			gajim.events.remove_events(account, jid, event)
			return True
		return False

################################################################################
### This and that... random.
################################################################################

	def show_roster_vbox(self, active):
		if active:
			self.xml.get_widget('roster_vbox2').show()
		else:
			self.xml.get_widget('roster_vbox2').hide()


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


	def authorize(self, widget, jid, account):
		'''Authorize a contact (by re-sending auth menuitem)'''
		gajim.connections[account].send_authorization(jid)
		dialogs.InformationDialog(_('Authorization has been sent'),
			_('Now "%s" will know your status.') %jid)

	def req_sub(self, widget, jid, txt, account, groups=[], nickname=None,
	auto_auth=False):
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
			contact = gajim.contacts.create_contact(jid=jid, name=nickname,
				groups=groups, show='requested', status='', ask='none',
				sub='subscribe', keyID=keyID)
			gajim.contacts.add_contact(account, contact)
		else:
			if not _('Not in Roster') in contact.get_shown_groups():
				dialogs.InformationDialog(_('Subscription request has been sent'),
					_('If "%s" accepts this request you will know his or her status.'
					) % jid)
				return
			self.remove_contact(contact.jid, account, force=True)
			contact.groups = groups
			if nickname:
				contact.name = nickname
		self.add_contact(jid, account)

	def revoke_auth(self, widget, jid, account):
		'''Revoke a contact's authorization'''
		gajim.connections[account].refuse_authorization(jid)
		dialogs.InformationDialog(_('Authorization has been removed'),
			_('Now "%s" will always see you as offline.') %jid)

	def set_state(self, account, state):
		child_iterA = self._get_account_iter(account, self.model)
		if child_iterA:
			self.model[child_iterA][0] = \
				gajim.interface.jabber_state_images['16'][state]
		if gajim.interface.systray_enabled:
			gajim.interface.systray.change_status(state)

	def set_connecting_state(self, account):
		self.set_state(account, 'connecting')

	def send_status(self, account, status, txt, auto=False, to=None):
		child_iterA = self._get_account_iter(account, self.model)
		if status != 'offline':
			if to is None:
				if status == gajim.connections[account].get_status() and \
				txt == gajim.connections[account].status:
					return
				gajim.config.set_per('accounts', account, 'last_status', status)
				gajim.config.set_per('accounts', account, 'last_status_msg',
					helpers.to_one_line(txt))
			if gajim.connections[account].connected < 2:
				self.set_connecting_state(account)

				keyid = gajim.config.get_per('accounts', account, 'keyid')
				if keyid and not gajim.connections[account].gpg:
					dialogs.WarningDialog(_('GPG is not usable'),
						_('You will be connected to %s without OpenPGP.') % account)

		self.send_status_continue(account, status, txt, auto, to)

	def send_pep(self, account, pep_dict=None):
		'''Sends pep information (activity, mood)'''
		if not pep_dict:
			return
		# activity
		if 'activity' in pep_dict and pep_dict['activity'] in pep.ACTIVITIES:
			activity = pep_dict['activity']
			if 'subactivity' in pep_dict and \
			pep_dict['subactivity'] in pep.ACTIVITIES[activity]:
				subactivity = pep_dict['subactivity']
			else:
				subactivity = 'other'
			if 'activity_text' in pep_dict:
				activity_text = pep_dict['activity_text']
			else:
				activity_text = ''
			pep.user_send_activity(account, activity, subactivity, activity_text)
		else:
			pep.user_send_activity(account, '')

		# mood
		if 'mood' in pep_dict and pep_dict['mood'] in pep.MOODS:
			mood = pep_dict['mood']
			if 'mood_text' in pep_dict:
				mood_text = pep_dict['mood_text']
			else:
				mood_text = ''
			pep.user_send_mood(account, mood, mood_text)
		else:
			pep.user_send_mood(account, '')

	def send_status_continue(self, account, status, txt, auto, to):
		if gajim.account_is_connected(account) and not to:
			if status == 'online' and gajim.interface.sleeper.getState() != \
			common.sleepy.STATE_UNKNOWN:
				gajim.sleeper_state[account] = 'online'
			elif gajim.sleeper_state[account] not in ('autoaway', 'autoxa') or \
			status == 'offline':
				gajim.sleeper_state[account] = 'off'

		if to:
			gajim.connections[account].send_custom_status(status, txt, to)
		else:
			if status in ('invisible', 'offline'):
				pep.delete_pep(gajim.get_jid_from_account(account), \
					account)
			was_invisible = gajim.connections[account].connected == \
				gajim.SHOW_LIST.index('invisible')
			gajim.connections[account].change_status(status, txt, auto)

			if account in gajim.interface.status_sent_to_users:
				gajim.interface.status_sent_to_users[account] = {}
			if account in gajim.interface.status_sent_to_groups:
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
				gajim.interface.auto_join_bookmarks(account)


	def chg_contact_status(self, contact, show, status, account):
		'''When a contact changes his or her status'''
		contact_instances = gajim.contacts.get_contacts(account, contact.jid)
		contact.show = show
		contact.status = status
		# name is to show in conversation window
		name = contact.get_shown_name()
		fjid = contact.get_full_jid()

		# The contact has several resources
		if len(contact_instances) > 1:
			if contact.resource != '':
				name += '/' + contact.resource

			# Remove resource when going offline
			if show in ('offline', 'error') and \
			not self.contact_has_pending_roster_events(contact, account):
				ctrl = gajim.interface.msg_win_mgr.get_control(fjid, account)
				if ctrl:
					ctrl.update_ui()
					ctrl.parent_win.redraw_tab(ctrl)
					# keep the contact around, since it's
					# already attached to the control
				else:
					gajim.contacts.remove_contact(account, contact)

		elif contact.jid == gajim.get_jid_from_account(account) and \
		show in ('offline', 'error'):
			if gajim.config.get('show_self_contact') != 'never':
				# SelfContact went offline. Remove him when last pending
				# message was read
				self.remove_contact(contact.jid, account, backend=True)

		uf_show = helpers.get_uf_show(show)

		# print status in chat window and update status/GPG image
		ctrl = gajim.interface.msg_win_mgr.get_control(contact.jid, account)
		if ctrl and ctrl.type_id != message_control.TYPE_GC:
			ctrl.contact = gajim.contacts.get_contact_with_highest_priority(
				account, contact.jid)
			ctrl.update_status_display(name, uf_show, status)

		if contact.resource:
			ctrl = gajim.interface.msg_win_mgr.get_control(fjid, account)
			if ctrl:
				ctrl.update_status_display(name, uf_show, status)

		# Delete pep if needed
		keep_pep = any(c.show not in ('error', 'offline') for c in
			contact_instances)
		if not keep_pep and contact.jid != gajim.get_jid_from_account(account) \
		and not contact.is_groupchat():
			pep.delete_pep(contact.jid, account)

		# Redraw everything and select the sender
		self.adjust_and_draw_contact_context(contact.jid, account)


	def on_status_changed(self, account, show):
		'''the core tells us that our status has changed'''
		if account not in gajim.contacts.get_accounts():
			return
		child_iterA = self._get_account_iter(account, self.model)
		if gajim.config.get('show_self_contact') == 'always':
			self_resource = gajim.connections[account].server_resource
			self_contact = gajim.contacts.get_contact(account,
				gajim.get_jid_from_account(account), resource=self_resource)
			if self_contact:
				status = gajim.connections[account].status
				self.chg_contact_status(self_contact, show, status, account)
		self.set_account_status_icon(account)
		if show == 'offline':
			if self.quit_on_next_offline > -1:
				# we want to quit, we are waiting for all accounts to be offline
				self.quit_on_next_offline -= 1
				if self.quit_on_next_offline < 1:
					# all accounts offline, quit
					self.quit_gtkgui_interface()
			else:
				# No need to redraw contacts if we're quitting
				if child_iterA:
					self.model[child_iterA][C_AVATAR_PIXBUF] = None
				if account in gajim.con_types:
					gajim.con_types[account] = None
				for jid in gajim.contacts.get_jid_list(account):
					lcontact = gajim.contacts.get_contacts(account, jid)
					ctrl = gajim.interface.msg_win_mgr.get_gc_control(jid, account)
					for contact in [c for c in lcontact if ((c.show != 'offline' or \
					c.is_transport()) and not ctrl)]:
						self.chg_contact_status(contact, 'offline', '', account)
			self.actions_menu_needs_rebuild = True
		self.update_status_combobox()

	def get_status_message(self, show, on_response, show_pep=True,
	always_ask=False):
		''' get the status message by:
		1/ looking in default status message
		2/ asking to user if needed depending on ask_on(ff)line_status and
			always_ask
		show_pep can be False to hide pep things from status message or True
		'''
		empty_pep = {'activity': '', 'subactivity': '', 'activity_text': '',
			'mood': '', 'mood_text': ''}
		if show in gajim.config.get_per('defaultstatusmsg'):
			if gajim.config.get_per('defaultstatusmsg', show, 'enabled'):
				on_response(gajim.config.get_per('defaultstatusmsg', show,
					'message'), empty_pep)
				return
		if not always_ask and ((show == 'online' and not gajim.config.get(
		'ask_online_status')) or (show in ('offline', 'invisible') and not \
		gajim.config.get('ask_offline_status'))):
			on_response('', empty_pep)
			return

		dlg = dialogs.ChangeStatusMessageDialog(on_response, show, show_pep)
		dlg.dialog.present() # show it on current workspace

	def change_status(self, widget, account, status):
		def change(account, status):
			def on_response(message, pep_dict):
				if message is None:
					# user pressed Cancel to change status message dialog
					return
				self.send_status(account, status, message)
				self.send_pep(account, pep_dict)
			self.get_status_message(status, on_response)

		if status == 'invisible' and self.connected_rooms(account):
			dialogs.ConfirmationDialog(
				_('You are participating in one or more group chats'),
				_('Changing your status to invisible will result in disconnection '
				'from those group chats. Are you sure you want to go invisible?'),
				on_response_ok = (change, account, status))
		else:
			change(account, status)

	def update_status_combobox(self):
		# table to change index in connection.connected to index in combobox
		table = {'offline':9, 'connecting':9, 'online':0, 'chat':1, 'away':2,
			'xa':3, 'dnd':4, 'invisible':5}

		# we check if there are more options in the combobox that it should
		# if yes, we remove the first ones
		while len(self.status_combobox.get_model()) > len(table)+2:
			self.status_combobox.remove_text(0)

		show = helpers.get_global_show()
		# temporarily block signal in order not to send status that we show
		# in the combobox
		self.combobox_callback_active = False
		if helpers.statuses_unified():
			self.status_combobox.set_active(table[show])
		else:
			uf_show = helpers.get_uf_show(show)
			liststore = self.status_combobox.get_model()
			liststore.prepend(['SEPARATOR', None, '', True])
			status_combobox_text = uf_show + ' (' + _("desync'ed") +')'
			liststore.prepend([status_combobox_text,
				gajim.interface.jabber_state_images['16'][show], show, False])
			self.status_combobox.set_active(0)
		gajim.interface._change_awn_icon_status(show)
		self.combobox_callback_active = True
		if gajim.interface.systray_enabled:
			gajim.interface.systray.change_status(show)

	def get_show(self, lcontact):
		prio = lcontact[0].priority
		show = lcontact[0].show
		for u in lcontact:
			if u.priority > prio:
				prio = u.priority
				show = u.show
		return show

	def on_message_window_delete(self, win_mgr, msg_win):
		if gajim.config.get('one_message_window') == 'always_with_roster':
			self.show_roster_vbox(True)
			gtkgui_helpers.resize_window(self.window,
				gajim.config.get('roster_width'),
				gajim.config.get('roster_height'))

	def close_all_from_dict(self, dic):
		'''close all the windows in the given dictionary'''
		for w in dic.values():
			if isinstance(w, dict):
				self.close_all_from_dict(w)
			else:
				w.window.destroy()

	def close_all(self, account, force=False):
		'''close all the windows from an account
		if force is True, do not ask confirmation before closing chat/gc windows
		'''
		if account in gajim.interface.instances:
			self.close_all_from_dict(gajim.interface.instances[account])
		for ctrl in gajim.interface.msg_win_mgr.get_controls(acct=account):
			ctrl.parent_win.remove_tab(ctrl, ctrl.parent_win.CLOSE_CLOSE_BUTTON,
				force = force)

	def on_roster_window_delete_event(self, widget, event):
		'''Main window X button was clicked'''
		if gajim.interface.systray_enabled and not gajim.config.get(
		'quit_on_roster_x_button') and gajim.config.get('trayicon') != 'on_event':
			self.tooltip.hide_tooltip()
			self.window.hide()
		elif gajim.config.get('quit_on_roster_x_button'):
			self.on_quit_request()
		else:
			def on_ok(checked):
				if checked:
					gajim.config.set('quit_on_roster_x_button', True)
				self.on_quit_request()
			dialogs.ConfirmationDialogCheck(_('Really quit Gajim?'),
				_('Are you sure you want to quit Gajim?'),
				_('Always close Gajim'), on_response_ok=on_ok)
		return True # do NOT destroy the window

	def prepare_quit(self):
		msgwin_width_adjust = 0

		# in case show_roster_on_start is False and roster is never shown
		# window.window is None
		if self.window.window is not None:
			x, y = self.window.window.get_root_origin()
			gajim.config.set('roster_x-position', x)
			gajim.config.set('roster_y-position', y)
			width, height = self.window.get_size()
			# For the width use the size of the vbox containing the tree and
			# status combo, this will cancel out any hpaned width
			width = self.xml.get_widget('roster_vbox2').allocation.width
			gajim.config.set('roster_width', width)
			gajim.config.set('roster_height', height)
			if not self.xml.get_widget('roster_vbox2').get_property('visible'):
				# The roster vbox is hidden, so the message window is larger
				# then we want to save (i.e. the window will grow every startup)
				# so adjust.
				msgwin_width_adjust = -1 * width
		gajim.config.set('show_roster_on_startup',
			self.window.get_property('visible'))
		gajim.interface.msg_win_mgr.shutdown(msgwin_width_adjust)

		gajim.config.set('collapsed_rows', '\t'.join(self.collapsed_rows))
		gajim.interface.save_config()
		for account in gajim.connections:
			gajim.connections[account].quit(True)
			self.close_all(account)
		if gajim.interface.systray_enabled:
			gajim.interface.hide_systray()

	def quit_gtkgui_interface(self):
		'''When we quit the gtk interface : exit gtk'''
		self.prepare_quit()
		gtk.main_quit()

	def on_quit_request(self, widget=None):
		''' user want to quit. Check if he should be warned about messages
		pending. Terminate all sessions and send offline to all connected
		account. We do NOT really quit gajim here '''
		accounts = gajim.connections.keys()
		get_msg = False
		for acct in accounts:
			if gajim.connections[acct].connected:
				get_msg = True
				break

		def on_continue2(message, pep_dict):
			self.quit_on_next_offline = 0
			accounts_to_disconnect = []
			for acct in accounts:
				if gajim.connections[acct].connected:
					self.quit_on_next_offline += 1
					accounts_to_disconnect.append(acct)

			for acct in accounts_to_disconnect:
				self.send_status(acct, 'offline', message)
				self.send_pep(acct, pep_dict)

			if not self.quit_on_next_offline:
				self.quit_gtkgui_interface()

		def on_continue(message, pep_dict):
			if message is None:
				# user pressed Cancel to change status message dialog
				return
			# check if we have unread messages
			unread = gajim.events.get_nb_events()
			if not gajim.config.get('notify_on_all_muc_messages'):
				unread_not_to_notify = gajim.events.get_nb_events(
					['printed_gc_msg'])
				unread -= unread_not_to_notify

			# check if we have recent messages
			recent = False
			for win in gajim.interface.msg_win_mgr.windows():
				for ctrl in win.controls():
					fjid = ctrl.get_full_jid()
					if fjid in gajim.last_message_time[ctrl.account]:
						if time.time() - gajim.last_message_time[ctrl.account][fjid] \
						< 2:
							recent = True
							break
				if recent:
					break

			if unread or recent:
				dialogs.ConfirmationDialog(_('You have unread messages'),
					_('Messages will only be available for reading them later if you'
					' have history enabled and contact is in your roster.'),
					on_response_ok=(on_continue2, message, pep_dict))
				return
			on_continue2(message, pep_dict)

		if get_msg:
			self.get_status_message('offline', on_continue, show_pep=False)
		else:
			on_continue('', None)

################################################################################
### Menu and GUI callbacks
### FIXME: order callbacks in itself...
################################################################################

	def on_actions_menuitem_activate(self, widget):
		self.make_menu()

	def on_edit_menuitem_activate(self, widget):
		'''need to call make_menu to build profile, avatar item'''
		self.make_menu()

	def on_bookmark_menuitem_activate(self, widget, account, bookmark):
		gajim.interface.join_gc_room(account, bookmark['jid'], bookmark['nick'],
			bookmark['password'])

	def on_send_server_message_menuitem_activate(self, widget, account):
		server = gajim.config.get_per('accounts', account, 'hostname')
		server += '/announce/online'
		dialogs.SingleMessageWindow(account, server, 'send')

	def on_xml_console_menuitem_activate(self, widget, account):
		if 'xml_console' in gajim.interface.instances[account]:
			gajim.interface.instances[account]['xml_console'].window.present()
		else:
			gajim.interface.instances[account]['xml_console'] = \
				dialogs.XMLConsoleWindow(account)

	def on_privacy_lists_menuitem_activate(self, widget, account):
		if 'privacy_lists' in gajim.interface.instances[account]:
			gajim.interface.instances[account]['privacy_lists'].window.present()
		else:
			gajim.interface.instances[account]['privacy_lists'] = \
				dialogs.PrivacyListsWindow(account)

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
				helpers.exec_command('%s history_manager.py' % sys.executable)
		else: # Unix user
			helpers.exec_command('%s history_manager.py' % sys.executable)

	def on_info(self, widget, contact, account):
		'''Call vcard_information_window class to display contact's information'''
		if gajim.connections[account].is_zeroconf:
			self.on_info_zeroconf(widget, contact, account)
			return

		info = gajim.interface.instances[account]['infos']
		if contact.jid in info:
			info[contact.jid].window.present()
		else:
			info[contact.jid] = vcard.VcardWindow(contact, account)

	def on_info_zeroconf(self, widget, contact, account):
		info = gajim.interface.instances[account]['infos']
		if contact.jid in info:
			info[contact.jid].window.present()
		else:
			contact = gajim.contacts.get_first_contact_from_jid(account,
							contact.jid)
			if contact.show in ('offline', 'error'):
				# don't show info on offline contacts
				return
			info[contact.jid] = vcard.ZeroconfVcardWindow(contact, account)

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
			row = props[0]
			titer = None
			try:
				titer = model.get_iter(row)
			except Exception:
				self.tooltip.hide_tooltip()
				return
			if model[titer][C_TYPE] in ('contact', 'self_contact'):
				# we're on a contact entry in the roster
				account = model[titer][C_ACCOUNT].decode('utf-8')
				jid = model[titer][C_JID].decode('utf-8')
				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					contacts = gajim.contacts.get_contacts(account, jid)
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
			elif model[titer][C_TYPE] == 'groupchat':
				account = model[titer][C_ACCOUNT].decode('utf-8')
				jid = model[titer][C_JID].decode('utf-8')
				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					contact = gajim.contacts.get_contacts(account, jid)
					self.tooltip.account = account
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, contact)
			elif model[titer][C_TYPE] == 'account':
				# we're on an account entry in the roster
				account = model[titer][C_ACCOUNT].decode('utf-8')
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
				contact = gajim.contacts.create_contact(jid=jid, name=account_name,
					show=connection.get_status(), sub='', status=connection.status,
					resource=connection.server_resource,
					priority=connection.priority, mood=connection.mood,
					tune=connection.tune, activity=connection.activity)
				if gajim.connections[account].gpg:
					contact.keyID = gajim.config.get_per('accounts', connection.name,
						'keyid')
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
							# Check if we already have this resource
							found = False
							for contact_ in contacts:
								if contact_.resource == resource:
									found = True
									break
							if found:
								continue
							show = roster.getShow(jid+'/'+resource)
							if not show:
								show = 'online'
							contact = gajim.contacts.create_contact(jid=jid,
								name=account, groups=['self_contact'], show=show,
								status=roster.getStatus(jid + '/' + resource),
								resource=resource,
								priority=roster.getPriority(jid + '/' + resource))
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
				self.remove_contact(contact.jid, account, backend=True)
				return

		def remove(list_):
			for (contact, account) in list_:
				full_jid = contact.get_full_jid()
				gajim.connections[account].unsubscribe_agent(full_jid)
				# remove transport from treeview
				self.remove_contact(contact.jid, account, backend=True)

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
			pritext = _('Transport "%s" will be removed') % list_[0][0].jid
			sectext = _('You will no longer be able to send and receive messages '
				'from contacts using this transport.')
		else:
			pritext = _('Transports will be removed')
			jids = ''
			for (contact, account) in list_:
				jids += '\n  ' + contact.get_shown_name() + ','
			jids = jids[:-1] + '.'
			sectext = _('You will no longer be able to send and receive messages '
				'to contacts from these transports: %s') % jids
		dialogs.ConfirmationDialog(pritext, sectext,
			on_response_ok = (remove, list_))

	def on_block(self, widget, list_, group=None):
		''' When clicked on the 'block' button in context menu.
		list_ is a list of (contact, account)'''
		def on_continue(msg, pep_dict):
			if msg is None:
				# user pressed Cancel to change status message dialog
				return
			accounts = []
			if group is None:
				for (contact, account) in list_:
					if account not in accounts:
						if not gajim.connections[account].privacy_rules_supported:
							continue
						accounts.append(account)
					self.send_status(account, 'offline', msg, to=contact.jid)
					new_rule = {'order': u'1', 'type': u'jid', 'action': u'deny',
						'value' : contact.jid, 'child': [u'message', u'iq',
						u'presence-out']}
					gajim.connections[account].blocked_list.append(new_rule)
					# needed for draw_contact:
					gajim.connections[account].blocked_contacts.append(
						contact.jid)
					self.draw_contact(contact.jid, account)
			else:
				for (contact, account) in list_:
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
					'value' : group, 'child': [u'message', u'iq', u'presence-out']}
				gajim.connections[account].blocked_list.append(new_rule)
			for account in accounts:
				connection = gajim.connections[account]
				connection.set_privacy_list('block', connection.blocked_list)
				if len(connection.blocked_list) == 1:
					connection.set_active_list('block')
					connection.set_default_list('block')
				connection.get_privacy_list('block')

		def _block_it(is_checked=None):
			if is_checked is not None: # dialog has been shown
				if is_checked: # user does not want to be asked again
					gajim.config.set('confirm_block', 'no')
				else:
					gajim.config.set('confirm_block', 'yes')
			self.get_status_message('offline', on_continue, show_pep=False)

		confirm_block = gajim.config.get('confirm_block')
		if confirm_block == 'no':
			_block_it()
			return
		pritext = _('You are about to block a contact. Are you sure you want'
			' to continue?')
		sectext = _('This contact will see you offline and you will not receive '
			'messages he will send you.')
		dlg = dialogs.ConfirmationDialogCheck(pritext, sectext,
			_('Do _not ask me again'), on_response_ok=_block_it)

	def on_unblock(self, widget, list_, group=None):
		''' When clicked on the 'unblock' button in context menu. '''
		accounts = []
		if group is None:
			for (contact, account) in list_:
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
					gajim.connections[account].blocked_contacts.remove(contact.jid)
				self.draw_contact(contact.jid, account)
			for account in accounts:
				for rule in gajim.connections[account].blocked_list:
					if rule['action'] != 'deny' or rule['type'] != 'jid' \
					or rule['value'] not in gajim.connections[account].to_unblock:
						gajim.connections[account].new_blocked_list.append(rule)
		else:
			for (contact, account) in list_:
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
								gajim.connections[account].new_blocked_list.append(rule)
				self.draw_contact(contact.jid, account)
		for account in accounts:
			gajim.connections[account].set_privacy_list('block',
				gajim.connections[account].new_blocked_list)
			gajim.connections[account].get_privacy_list('block')
			if len(gajim.connections[account].new_blocked_list) == 0:
				gajim.connections[account].blocked_list = []
				gajim.connections[account].blocked_contacts = []
				gajim.connections[account].blocked_groups = []
				gajim.connections[account].set_default_list('')
				gajim.connections[account].set_active_list('')
				gajim.connections[account].del_privacy_list('block')
				if 'blocked_contacts' in gajim.interface.instances[account]:
					gajim.interface.instances[account]['blocked_contacts'].\
						privacy_list_received([])
		for (contact, account) in list_:
			if not self.regroup:
				show = gajim.SHOW_LIST[gajim.connections[account].connected]
			else:	# accounts merged
				show = helpers.get_global_show()
			if show == 'invisible':
				# Don't send our presence if we're invisible
				continue
			if account not in accounts:
				accounts.append(account)
				if gajim.connections[account].privacy_rules_supported:
					self.send_status(account, show,
						gajim.connections[account].status, to=contact.jid)
			else:
				self.send_status(account, show,
					gajim.connections[account].status, to=contact.jid)

	def on_rename(self, widget, row_type, jid, account):
		# this function is called either by F2 or by Rename menuitem
		if 'rename' in gajim.interface.instances:
			gajim.interface.instances['rename'].dialog.present()
			return

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
			old_text = jid
			title = _('Rename Group')
			message = _('Enter a new name for group %s') % \
				gobject.markup_escape_text(jid)

		def on_renamed(new_text, account, row_type, jid, old_text):
			if 'rename' in gajim.interface.instances:
				del gajim.interface.instances['rename']
			if row_type in ('contact', 'agent'):
				if old_text == new_text:
					return
				for contact in gajim.contacts.get_contacts(account, jid):
					contact.name = new_text
				gajim.connections[account].update_contact(jid, new_text, \
					contact.groups)
				self.draw_contact(jid, account)
				# Update opened chats
				for ctrl in gajim.interface.msg_win_mgr.get_controls(jid, account):
					ctrl.update_ui()
					win = gajim.interface.msg_win_mgr.get_window(jid, account)
					win.redraw_tab(ctrl)
					win.show_title()
			elif row_type == 'group':
				# in C_JID column, we hold the group name (which is not escaped)
				self.rename_group(old_text, new_text, account)

		def on_canceled():
			if 'rename' in gajim.interface.instances:
				del gajim.interface.instances['rename']

		gajim.interface.instances['rename'] = dialogs.InputDialog(title, message,
			old_text, False, (on_renamed, account, row_type, jid, old_text),
			on_canceled)

	def on_remove_group_item_activated(self, widget, group, account):
		def on_ok(checked):
			for contact in gajim.contacts.get_contacts_from_group(account, group):
				if not checked:
					self.remove_contact_from_groups(contact.jid,account, [group])
				else:
					gajim.connections[account].unsubscribe(contact.jid)
					self.remove_contact(contact.jid, account, backend=True)

		dialogs.ConfirmationDialogCheck(_('Remove Group'),
			_('Do you want to remove group %s from the roster?') % group,
			_('Also remove all contacts in this group from your roster'),
			on_response_ok=on_ok)

	def on_assign_pgp_key(self, widget, contact, account):
		attached_keys = gajim.config.get_per('accounts', account,
			'attached_gpg_keys').split()
		keys = {}
		keyID = _('None')
		for i in xrange(len(attached_keys)/2):
			keys[attached_keys[2*i]] = attached_keys[2*i+1]
			if attached_keys[2*i] == contact.jid:
				keyID = attached_keys[2*i+1]
		public_keys = gajim.connections[account].ask_gpg_keys()
		public_keys[_('None')] = _('None')

		def on_key_selected(keyID):
			if keyID is None:
				return
			if keyID[0] == _('None'):
				if contact.jid in keys:
					del keys[contact.jid]
				keyID = ''
			else:
				keyID = keyID[0]
				keys[contact.jid] = keyID

			ctrl = gajim.interface.msg_win_mgr.get_control(contact.jid, account)
			if ctrl:
				ctrl.update_ui()

			keys_str = ''
			for jid in keys:
				keys_str += jid + ' ' + keys[jid] + ' '
			gajim.config.set_per('accounts', account, 'attached_gpg_keys',
				keys_str)
			for u in gajim.contacts.get_contacts(account, contact.jid):
				u.keyID = helpers.prepare_and_validate_gpg_keyID(account,
					contact.jid, keyID)

		dialogs.ChooseGPGKeyDialog(_('Assign OpenPGP Key'),
			_('Select a key to apply to the contact'), public_keys,
			on_key_selected, selected=keyID)

	def on_set_custom_avatar_activate(self, widget, contact, account):
		def on_ok(widget, path_to_file):
			filesize = os.path.getsize(path_to_file) # in bytes
			invalid_file = False
			msg = ''
			if os.path.isfile(path_to_file):
				stat = os.stat(path_to_file)
				if stat[6] == 0:
					invalid_file = True
					msg = _('File is empty')
			else:
				invalid_file = True
				msg = _('File does not exist')
			if invalid_file:
				dialogs.ErrorDialog(_('Could not load image'), msg)
				return
			try:
				pixbuf = gtk.gdk.pixbuf_new_from_file(path_to_file)
				if filesize > 16384: # 16 kb
					# get the image at 'tooltip size'
					# and hope that user did not specify in ACE crazy size
					pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'tooltip')
			except gobject.GError, msg: # unknown format
				# msg should be string, not object instance
				msg = str(msg)
				dialogs.ErrorDialog(_('Could not load image'), msg)
				return
			gajim.interface.save_avatar_files(contact.jid, pixbuf, local=True)
			dlg.destroy()
			self.update_avatar_in_gui(contact.jid, account)

		def on_clear(widget):
			dlg.destroy()
			# Delete file:
			gajim.interface.remove_avatar_files(contact.jid, local=True)
			self.update_avatar_in_gui(contact.jid, account)

		dlg = dialogs.AvatarChooserDialog(on_response_ok=on_ok,
			on_response_clear=on_clear)

	def on_edit_groups(self, widget, list_):
		dialogs.EditGroupsDialog(list_)

	def on_history(self, widget, contact, account):
		'''When history menuitem is activated: call log window'''
		if 'logs' in gajim.interface.instances:
			gajim.interface.instances['logs'].window.present()
			gajim.interface.instances['logs'].open_history(contact.jid, account)
		else:
			gajim.interface.instances['logs'] = history_window.\
				HistoryWindow(contact.jid, account)

	def on_disconnect(self, widget, jid, account):
		'''When disconnect menuitem is activated: disconect from room'''
		if jid in gajim.interface.minimized_controls[account]:
			ctrl = gajim.interface.minimized_controls[account][jid]
			ctrl.shutdown()
			ctrl.got_disconnected()
		self.remove_groupchat(jid, account)

	def on_reconnect(self, widget, jid, account):
		'''When disconnect menuitem is activated: disconect from room'''
		if jid in gajim.interface.minimized_controls[account]:
			ctrl = gajim.interface.minimized_controls[account][jid]
		gajim.interface.join_gc_room(account, jid, ctrl.nick,
			gajim.gc_passwords.get(jid, ''))

	def on_send_single_message_menuitem_activate(self, widget, account,
	contact=None):
		if contact is None:
			dialogs.SingleMessageWindow(account, action='send')
		elif isinstance(contact, list):
			dialogs.SingleMessageWindow(account, contact, 'send')
		else:
			jid = contact.jid
			if contact.jid == gajim.get_jid_from_account(account):
				jid += '/' + contact.resource
			dialogs.SingleMessageWindow(account, jid, 'send')

	def on_send_file_menuitem_activate(self, widget, contact, account,
	resource=None):
		gajim.interface.instances['file_transfers'].show_file_send_request(
			account, contact)

	def on_add_special_notification_menuitem_activate(self, widget, jid):
		dialogs.AddSpecialNotificationDialog(jid)

	def on_invite_to_new_room(self, widget, list_, resource=None):
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
				if 'join_gc' in gajim.interface.instances[account]:
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
		resource=None):
		''' resource parameter MUST NOT be used if more than one contact in
		list '''
		for e in list_:
			contact = e[0]
			contact_jid = contact.jid
			if resource: # we MUST have one contact only in list_
				contact_jid += '/' + resource
			gajim.connections[room_account].send_invite(room_jid, contact_jid)

	def on_all_groupchat_maximized(self, widget, group_list):
		for (contact, account) in group_list:
			self.on_groupchat_maximized(widget, contact.jid, account)

	def on_groupchat_maximized(self, widget, jid, account):
		'''When a groupchat is maximised'''
		if not jid in gajim.interface.minimized_controls[account]:
			# Already opened?
			gc_control = gajim.interface.msg_win_mgr.get_gc_control(jid, account)
			if gc_control:
				mw = gajim.interface.msg_win_mgr.get_window(jid, account)
				mw.set_active_tab(gc_control)
				mw.window.window.focus(gtk.get_current_event_time())
			return
		ctrl = gajim.interface.minimized_controls[account][jid]
		mw = gajim.interface.msg_win_mgr.get_window(jid, account)
		if not mw:
			mw = gajim.interface.msg_win_mgr.create_window(ctrl.contact,
				ctrl.account, ctrl.type_id)
		ctrl.parent_win = mw
		mw.new_tab(ctrl)
		mw.set_active_tab(ctrl)
		mw.window.window.focus(gtk.get_current_event_time())
		self.remove_groupchat(jid, account)

	def on_edit_account(self, widget, account):
		if 'accounts' in gajim.interface.instances:
			gajim.interface.instances['accounts'].window.present()
		else:
			gajim.interface.instances['accounts'] = config.AccountsWindow()
		gajim.interface.instances['accounts'].select_account(account)

	def on_zeroconf_properties(self, widget, account):
		if 'accounts' in gajim.interface.instances:
			gajim.interface.instances['accounts'].window.present()
		else:
			gajim.interface.instances['accounts'] = config.AccountsWindow()
		gajim.interface.instances['accounts'].select_account(account)

	def on_open_gmail_inbox(self, widget, account):
		url = gajim.connections[account].gmail_url
		if url:
			helpers.launch_browser_mailer('url', url)

	def on_change_status_message_activate(self, widget, account):
		show = gajim.SHOW_LIST[gajim.connections[account].connected]
		def on_response(message, pep_dict):
			if message is None: # None is if user pressed Cancel
				return
			self.send_status(account, show, message)
			self.send_pep(account, pep_dict)
		dialogs.ChangeStatusMessageDialog(on_response, show)

	def on_add_to_roster(self, widget, contact, account):
		dialogs.AddNewContactWindow(account, contact.jid, contact.name)


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
				jid = model[path][C_JID].decode('utf-8')
				account = model[path][C_ACCOUNT].decode('utf-8')
				self.on_rename(widget, type_, jid, account)

		elif event.keyval == gtk.keysyms.Delete:
			treeselection = self.tree.get_selection()
			model, list_of_paths = treeselection.get_selected_rows()
			if not len(list_of_paths):
				return
			type_ = model[list_of_paths[0]][C_TYPE]
			account = model[list_of_paths[0]][C_ACCOUNT].decode('utf-8')
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

	def on_roster_treeview_button_release_event(self, widget, event):
		try:
			path = self.tree.get_path_at_pos(int(event.x), int(event.y))[0]
		except TypeError:
			return False

		if event.button == 1: # Left click
			if gajim.single_click and not event.state & gtk.gdk.SHIFT_MASK and \
			not event.state & gtk.gdk.CONTROL_MASK:
				# Check if button has been pressed on the same row
				if self.clicked_path == path:
					self.on_row_activated(widget, path)
				self.clicked_path = None

	def on_roster_treeview_button_press_event(self, widget, event):
		# hide tooltip, no matter the button is pressed
		self.tooltip.hide_tooltip()
		try:
			pos = self.tree.get_path_at_pos(int(event.x), int(event.y))
			path, x = pos[0], pos[2]
		except TypeError:
			self.tree.get_selection().unselect_all()
			return False

		if event.button == 3: # Right click
			try:
				model, list_of_paths = self.tree.get_selection().get_selected_rows()
			except TypeError:
				list_of_paths = []
			if path not in list_of_paths:
				self.tree.get_selection().unselect_all()
				self.tree.get_selection().select_path(path)
			return self.show_treeview_menu(event)

		elif event.button == 2: # Middle click
			try:
				model, list_of_paths = self.tree.get_selection().get_selected_rows()
			except TypeError:
				list_of_paths = []
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
				def on_response(message, pep_dict):
					if message is None:
						return True
					for acct in gajim.connections:
						if not gajim.config.get_per('accounts', acct,
						'sync_with_global_status'):
							continue
						current_show = gajim.SHOW_LIST[gajim.connections[acct].\
							connected]
						self.send_status(acct, current_show, message)
						self.send_pep(acct, pep_dict)
				dialogs.ChangeStatusMessageDialog(on_response, show)
			return True

		elif event.button == 1: # Left click
			model = self.modelfilter
			type_ = model[path][C_TYPE]
			# x_min is the x start position of status icon column
			if gajim.config.get('avatar_position_in_roster') == 'left':
				x_min = gajim.config.get('roster_avatar_width')
			else:
				x_min = 0
			if gajim.single_click and not event.state & gtk.gdk.SHIFT_MASK and \
			not event.state & gtk.gdk.CONTROL_MASK:
				# Don't handle double click if we press icon of a metacontact
				titer = model.get_iter(path)
				if x > x_min and x < x_min + 27 and type_ == 'contact' and \
				model.iter_has_child(titer):
					if (self.tree.row_expanded(path)):
						self.tree.collapse_row(path)
					else:
						self.tree.expand_row(path, False)
					return
				# We just save on which row we press button, and open chat window on
				# button release to be able to do DND without opening chat window
				self.clicked_path = path
				return
			else:
				if type_ == 'group' and x < 27:
					# first cell in 1st column (the arrow SINGLE clicked)
					if (self.tree.row_expanded(path)):
						self.tree.collapse_row(path)
					else:
						self.tree.expand_row(path, False)

				elif type_ == 'contact' and x > x_min and x < x_min + 27:
					if (self.tree.row_expanded(path)):
						self.tree.collapse_row(path)
					else:
						self.tree.expand_row(path, False)

	def on_req_usub(self, widget, list_):
		'''Remove a contact. list_ is a list of (contact, account) tuples'''
		def on_ok(is_checked, list_):
			remove_auth = True
			if len(list_) == 1:
				contact = list_[0][0]
				if contact.sub != 'to' and is_checked:
					remove_auth = False
			for (contact, account) in list_:
				if _('Not in Roster') not in contact.get_shown_groups():
					gajim.connections[account].unsubscribe(contact.jid, remove_auth)
				self.remove_contact(contact.jid, account, backend=True)
				if not remove_auth and contact.sub == 'both':
					contact.name = ''
					contact.groups = []
					contact.sub = 'from'
					# we can't see him, but have to set it manually in contact
					contact.show = 'offline'
					gajim.contacts.add_contact(account, contact)
					self.add_contact(contact.jid, account)
		def on_ok2(list_):
			on_ok(False, list_)

		if len(list_) == 1:
			contact = list_[0][0]
			pritext = _('Contact "%s" will be removed from your roster') % \
				contact.get_shown_name()
			sectext = _('You are about to remove "%(name)s" (%(jid)s) from your '
				'roster.\n') % {'name': contact.get_shown_name(),
				'jid': contact.jid}
			if contact.sub == 'to':
				dialogs.ConfirmationDialog(pritext, sectext + \
					_('By removing this contact you also remove authorization '
					'resulting in him or her always seeing you as offline.'),
					on_response_ok = (on_ok2, list_))
			elif _('Not in Roster') in contact.get_shown_groups():
				# Contact is not in roster
				dialogs.ConfirmationDialog(pritext, sectext + \
					_('Do you want to continue?'), on_response_ok = (on_ok2, list_))
			else:
				dialogs.ConfirmationDialogCheck(pritext, sectext + \
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
				jids += '\n  ' + contact.get_shown_name() + ' (%s)' % contact.jid +\
					','
			sectext = _('By removing these contacts:%s\nyou also remove '
				'authorization resulting in them always seeing you as offline.') % \
				jids
			dialogs.ConfirmationDialog(pritext, sectext,
				on_response_ok = (on_ok2, list_))

	def on_send_custom_status(self, widget, contact_list, show, group=None):
		'''send custom status'''
		# contact_list has only one element except if group != None
		def on_response(message, pep_dict):
			if message is None: # None if user pressed Cancel
				return
			account_list = []
			for (contact, account) in contact_list:
				if account not in account_list:
					account_list.append(account)
			# 1. update status_sent_to_[groups|users] list
			if group:
				for account in account_list:
					if account not in gajim.interface.status_sent_to_groups:
						gajim.interface.status_sent_to_groups[account] = {}
					gajim.interface.status_sent_to_groups[account][group] = show
			else:
				for (contact, account) in contact_list:
					if account not in gajim.interface.status_sent_to_users:
						gajim.interface.status_sent_to_users[account] = {}
					gajim.interface.status_sent_to_users[account][contact.jid] = show

			# 2. update privacy lists if main status is invisible
			for account in account_list:
				if gajim.SHOW_LIST[gajim.connections[account].connected] == \
				'invisible':
					gajim.connections[account].set_invisible_rule()

			# 3. send directed presence
			for (contact, account) in contact_list:
				our_jid = gajim.get_jid_from_account(account)
				jid = contact.jid
				if jid == our_jid:
					jid += '/' + contact.resource
				self.send_status(account, show, message, to=jid)

		def send_it(is_checked=None):
			if is_checked is not None: # dialog has been shown
				if is_checked: # user does not want to be asked again
					gajim.config.set('confirm_custom_status', 'no')
				else:
					gajim.config.set('confirm_custom_status', 'yes')
			self.get_status_message(show, on_response, show_pep=False,
				always_ask=True)

		confirm_custom_status = gajim.config.get('confirm_custom_status')
		if confirm_custom_status == 'no':
			send_it()
			return
		pritext = _('You are about to send a custom status. Are you sure you want'
			' to continue?')
		sectext = _('This contact will temporarily see you as %(status)s, '
			'but only until you change your status. Then he will see your global '
			'status.') % {'status': show}
		dlg = dialogs.ConfirmationDialogCheck(pritext, sectext,
			_('Do _not ask me again'), on_response_ok=send_it)

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
		statuses_unified = helpers.statuses_unified() # status "desync'ed" or not
		if (active == 7 and statuses_unified) or (active == 9 and \
		not statuses_unified):
			# 'Change status message' selected:
			# do not change show, just show change status dialog
			status = model[self.previous_status_combobox_active][2].decode('utf-8')
			def on_response(message, pep_dict):
				if message is not None: # None if user pressed Cancel
					for account in accounts:
						if not gajim.config.get_per('accounts', account,
							'sync_with_global_status'):
							continue
						current_show = gajim.SHOW_LIST[
							gajim.connections[account].connected]
						self.send_status(account, current_show, message)
						self.send_pep(account, pep_dict)
				self.combobox_callback_active = False
				self.status_combobox.set_active(
					self.previous_status_combobox_active)
				self.combobox_callback_active = True
			dialogs.ChangeStatusMessageDialog(on_response, status)
			return
		# we are about to change show, so save this new show so in case
		# after user chooses "Change status message" menuitem
		# we can return to this show
		self.previous_status_combobox_active = active
		connected_accounts = gajim.get_number_of_connected_accounts()

		def on_continue(message, pep_dict):
			if message is None:
				# user pressed Cancel to change status message dialog
				self.update_status_combobox()
				return
			global_sync_accounts = []
			for acct in accounts:
				if gajim.config.get_per('accounts', acct,
				'sync_with_global_status'):
					global_sync_accounts.append(acct)
			global_sync_connected_accounts = \
				gajim.get_number_of_connected_accounts(global_sync_accounts)
			for account in accounts:
				if not gajim.config.get_per('accounts', account,
				'sync_with_global_status'):
					continue
				# we are connected (so we wanna change show and status)
				# or no account is connected and we want to connect with new show
				# and status

				if not global_sync_connected_accounts > 0 or \
				gajim.connections[account].connected > 0:
					self.send_status(account, status, message)
					self.send_pep(account, pep_dict)
			self.update_status_combobox()

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
				def on_ok():
					self.get_status_message(status, on_continue, show_pep=False)

				def on_cancel():
					self.update_status_combobox()

				dialogs.ConfirmationDialog(
					_('You are participating in one or more group chats'),
					_('Changing your status to invisible will result in '
					'disconnection from those group chats. Are you sure you want to '
					'go invisible?'), on_reponse_ok=on_ok,
					on_response_cancel=on_cancel)
				return

		self.get_status_message(status, on_continue)

	def on_preferences_menuitem_activate(self, widget):
		if 'preferences' in gajim.interface.instances:
			gajim.interface.instances['preferences'].window.present()
		else:
			gajim.interface.instances['preferences'] = config.PreferencesWindow()

	def on_publish_tune_toggled(self, widget, account):
		act = widget.get_active()
		gajim.config.set_per('accounts', account, 'publish_tune', act)
		if act:
			gajim.interface.enable_music_listener()
		else:
			# disable it only if no other account use it
			for acct in gajim.connections:
				if gajim.config.get_per('accounts', acct, 'publish_tune'):
					break
			else:
				gajim.interface.disable_music_listener()

			if gajim.connections[account].pep_supported:
				# As many implementations don't support retracting items, we send a
				# "Stopped" event first
				pep.user_send_tune(account, '')
				pep.user_retract_tune(account)
		helpers.update_optional_features(account)

	def on_pep_services_menuitem_activate(self, widget, account):
		if 'pep_services' in gajim.interface.instances[account]:
			gajim.interface.instances[account]['pep_services'].window.present()
		else:
			gajim.interface.instances[account]['pep_services'] = \
				config.ManagePEPServicesWindow(account)

	def on_add_new_contact(self, widget, account):
		dialogs.AddNewContactWindow(account)

	def on_join_gc_activate(self, widget, account):
		'''when the join gc menuitem is clicked, show the join gc window'''
		invisible_show = gajim.SHOW_LIST.index('invisible')
		if gajim.connections[account].connected == invisible_show:
			dialogs.ErrorDialog(_('You cannot join a group chat while you are '
				'invisible'))
			return
		if 'join_gc' in gajim.interface.instances[account]:
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

	def on_features_menuitem_activate(self, widget):
		features_window.FeaturesWindow()

	def on_about_menuitem_activate(self, widget):
		dialogs.AboutDialog()

	def on_accounts_menuitem_activate(self, widget):
		if 'accounts' in gajim.interface.instances:
			gajim.interface.instances['accounts'].window.present()
		else:
			gajim.interface.instances['accounts'] = config.AccountsWindow()

	def on_file_transfers_menuitem_activate(self, widget):
		if gajim.interface.instances['file_transfers'].window.get_property(
		'visible'):
			gajim.interface.instances['file_transfers'].window.present()
		else:
			gajim.interface.instances['file_transfers'].window.show_all()

	def on_history_menuitem_activate(self, widget):
		if 'logs' in gajim.interface.instances:
			gajim.interface.instances['logs'].window.present()
		else:
			gajim.interface.instances['logs'] = history_window.\
				HistoryWindow()

	def on_show_transports_menuitem_activate(self, widget):
		gajim.config.set('show_transports_group', widget.get_active())
		self.refilter_shown_roster_items()

	def on_manage_bookmarks_menuitem_activate(self, widget):
		config.ManageBookmarksWindow()

	def on_profile_avatar_menuitem_activate(self, widget, account):
		gajim.interface.edit_own_details(account)

	def on_execute_command(self, widget, contact, account, resource=None):
		'''Execute command. Full JID needed; if it is other contact,
		resource is necessary. Widget is unnecessary, only to be
		able to make this a callback.'''
		jid = contact.jid
		if resource is not None:
			jid = jid + u'/' + resource
		adhoc_commands.CommandWindow(account, jid)

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
				self.draw_contact(jid, account, selected=True, focus=True)

	def on_roster_window_focus_out_event(self, widget, event):
		# if a contact row is selected, update colors (eg. for status msg)
		# because gtk engines may differ in bg when window is selected
		# or not
		if len(self._last_selected_contact):
			for (jid, account) in self._last_selected_contact:
				self.draw_contact(jid, account, selected=True, focus=False)

	def on_roster_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			if gajim.interface.msg_win_mgr.mode == \
			MessageWindowMgr.ONE_MSG_WINDOW_ALWAYS_WITH_ROSTER and \
			gajim.interface.msg_win_mgr.one_window_opened():
				# let message window close the tab
				return
			list_of_paths = self.tree.get_selection().get_selected_rows()[1]
			if not len(list_of_paths) and gajim.interface.systray_enabled and \
			not gajim.config.get('quit_on_roster_x_button'):
				self.tooltip.hide_tooltip()
				self.window.hide()
		elif event.state & gtk.gdk.CONTROL_MASK and event.keyval == gtk.keysyms.i:
			treeselection = self.tree.get_selection()
			model, list_of_paths = treeselection.get_selected_rows()
			for path in list_of_paths:
				type_ = model[path][C_TYPE]
				if type_ in ('contact', 'agent'):
					jid = model[path][C_JID].decode('utf-8')
					account = model[path][C_ACCOUNT].decode('utf-8')
					contact = gajim.contacts.get_first_contact_from_jid(account, jid)
					self.on_info(widget, contact, account)
		elif event.state & gtk.gdk.CONTROL_MASK and event.keyval == gtk.keysyms.h:
			treeselection = self.tree.get_selection()
			model, list_of_paths = treeselection.get_selected_rows()
			if len(list_of_paths) != 1:
				return
			path = list_of_paths[0]
			type_ = model[path][C_TYPE]
			if type_ in ('contact', 'agent'):
				jid = model[path][C_JID].decode('utf-8')
				account = model[path][C_ACCOUNT].decode('utf-8')
				contact = gajim.contacts.get_first_contact_from_jid(account, jid)
				self.on_history(widget, contact, account)

	def on_roster_window_popup_menu(self, widget):
		event = gtk.gdk.Event(gtk.gdk.KEY_PRESS)
		self.show_treeview_menu(event)

	def on_row_activated(self, widget, path):
		'''When an iter is activated (double-click or single click if gnome is
		set this way)'''
		model = self.modelfilter
		account = model[path][C_ACCOUNT].decode('utf-8')
		type_ = model[path][C_TYPE]
		if type_ in ('group', 'account'):
			if self.tree.row_expanded(path):
				self.tree.collapse_row(path)
			else:
				self.tree.expand_row(path, False)
			return
		jid = model[path][C_JID].decode('utf-8')
		resource = None
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		titer = model.get_iter(path)
		if contact.is_groupchat():
			first_ev = gajim.events.get_first_event(account, jid)
			if first_ev and self.open_event(account, jid, first_ev):
				# We are invited to a GC
				# open event cares about connecting to it
				self.remove_groupchat(jid, account)
			else:
				self.on_groupchat_maximized(None, jid, account)
			return

		# else
		first_ev = gajim.events.get_first_event(account, jid)
		if not first_ev:
			# look in other resources
			for c in gajim.contacts.get_contacts(account, jid):
				fjid = c.get_full_jid()
				first_ev = gajim.events.get_first_event(account, fjid)
				if first_ev:
					resource = c.resource
					break
		if not first_ev and model.iter_has_child(titer):
			child_iter = model.iter_children(titer)
			while not first_ev and child_iter:
				child_jid = model[child_iter][C_JID].decode('utf-8')
				first_ev = gajim.events.get_first_event(account, child_jid)
				if first_ev:
					jid = child_jid
				else:
					child_iter = model.iter_next(child_iter)
		session = None
		if first_ev:
			if first_ev.type_ in ('chat', 'normal'):
				session = first_ev.parameters[8]
			fjid = jid
			if resource:
				fjid += '/' + resource
			if self.open_event(account, fjid, first_ev):
				return
			# else
			contact = gajim.contacts.get_contact(account, jid, resource)
		if not contact or isinstance(contact, list):
			contact = gajim.contacts.get_contact_with_highest_priority(account,
				jid)
		if jid == gajim.get_jid_from_account(account):
			resource = contact.resource

		gajim.interface.on_open_chat_window(None, contact, account, \
			resource=resource, session=session)

	def on_roster_treeview_row_activated(self, widget, path, col=0):
		'''When an iter is double clicked: open the first event window'''
		if not gajim.single_click:
			self.on_row_activated(widget, path)

	def on_roster_treeview_row_expanded(self, widget, titer, path):
		'''When a row is expanded change the icon of the arrow'''
		self._toggeling_row = True
		model = widget.get_model()
		child_model = model.get_model()
		child_iter =  model.convert_iter_to_child_iter(titer)

		if self.regroup: # merged accounts
			accounts = gajim.connections.keys()
		else:
			accounts = [model[titer][C_ACCOUNT].decode('utf-8')]

		type_ = model[titer][C_TYPE]
		if type_ == 'group':
			group = model[titer][C_JID].decode('utf-8')
			child_model[child_iter][C_IMG] = gajim.interface.jabber_state_images[
				'16']['opened']
			for account in accounts:
				if group in gajim.groups[account]: # This account has this group
					gajim.groups[account][group]['expand'] = True
					if account + group in self.collapsed_rows:
						self.collapsed_rows.remove(account + group)
				for contact in gajim.contacts.iter_contacts(account):
					jid = contact.jid
					if group in contact.groups and gajim.contacts.is_big_brother(
					account, jid, accounts) and account + group + jid \
					not in self.collapsed_rows:
						titers = self._get_contact_iter(jid, account)
						for titer in titers:
							path = model.get_path(titer)
							self.tree.expand_row(path, False)
		elif type_ == 'account':
			account = accounts[0] # There is only one cause we don't use merge
			if account in self.collapsed_rows:
				self.collapsed_rows.remove(account)
			self.draw_account(account)
			# When we expand, groups are collapsed. Restore expand state
			for group in gajim.groups[account]:
				if gajim.groups[account][group]['expand']:
					titer = self._get_group_iter(group, account)
					if titer:
						path = model.get_path(titer)
						self.tree.expand_row(path, False)
		elif type_ == 'contact':
			# Metacontact got toggled, update icon
			jid = model[titer][C_JID].decode('utf-8')
			account = model[titer][C_ACCOUNT].decode('utf-8')
			contact = gajim.contacts.get_contact(account, jid)
			for group in contact.groups:
				if account + group + jid in self.collapsed_rows:
					self.collapsed_rows.remove(account + group + jid)
			family = gajim.contacts.get_metacontacts_family(account, jid)
			nearby_family = \
				self._get_nearby_family_and_big_brother(family, account)[0]
			# Redraw all brothers to show pending events
			for data in nearby_family:
				self.draw_contact(data['jid'], data['account'])

		self._toggeling_row = False

	def on_roster_treeview_row_collapsed(self, widget, titer, path):
		'''When a row is collapsed change the icon of the arrow'''
		self._toggeling_row = True
		model = widget.get_model()
		child_model = model.get_model()
		child_iter =  model.convert_iter_to_child_iter(titer)

		if self.regroup: # merged accounts
			accounts = gajim.connections.keys()
		else:
			accounts = [model[titer][C_ACCOUNT].decode('utf-8')]

		type_ = model[titer][C_TYPE]
		if type_ == 'group':
			child_model[child_iter][C_IMG] = gajim.interface.jabber_state_images[
				'16']['closed']
			group = model[titer][C_JID].decode('utf-8')
			for account in accounts:
				if group in gajim.groups[account]: # This account has this group
					gajim.groups[account][group]['expand'] = False
					if account + group not in self.collapsed_rows:
						self.collapsed_rows.append(account + group)
		elif type_ == 'account':
			account = accounts[0] # There is only one cause we don't use merge
			if account not in self.collapsed_rows:
				self.collapsed_rows.append(account)
			self.draw_account(account)
		elif type_ == 'contact':
			# Metacontact got toggled, update icon
			jid = model[titer][C_JID].decode('utf-8')
			account = model[titer][C_ACCOUNT].decode('utf-8')
			contact = gajim.contacts.get_contact(account, jid)
			for group in contact.groups:
				if account + group + jid not in self.collapsed_rows:
					self.collapsed_rows.append(account + group + jid)
			family = gajim.contacts.get_metacontacts_family(account, jid)
			nearby_family  = \
				self._get_nearby_family_and_big_brother(family, account)[0]
			# Redraw all brothers to show pending events
			for data in nearby_family:
				self.draw_contact(data['jid'], data['account'])

		self._toggeling_row = False

	def on_modelfilter_row_has_child_toggled(self, model, path, titer):
		'''Called when a row has gotten the first or lost its last child row.

		Expand Parent if necessary.
		'''
		if self._toggeling_row:
			# Signal is emitted when we write to our model
			return

		type_ = model[titer][C_TYPE]
		account = model[titer][C_ACCOUNT]
		if not account:
			return

		account = account.decode('utf-8')

		if type_ == 'contact':
			child_iter = model.convert_iter_to_child_iter(titer)
			if self.model.iter_has_child(child_iter):
				# we are a bigbrother metacontact
				# redraw us to show/hide expand icon
				if self.filtering:
					# Prevent endless loops
					jid = model[titer][C_JID].decode('utf-8')
					gobject.idle_add(self.draw_contact, jid, account)
		elif type_ == 'group':
			group = model[titer][C_JID].decode('utf-8')
			self._adjust_group_expand_collapse_state(group, account)
		elif type_ == 'account':
			self._adjust_account_expand_collapse_state(account)

# Selection can change when the model is filtered
# Only write to the model when filtering is finished!
#
# FIXME: When we are filtering our custom colors are somehow lost
#
#	def on_treeview_selection_changed(self, selection):
#		'''Called when selection in TreeView has changed.
#
#		Redraw unselected rows to make status message readable
#		on all possible backgrounds.
#		'''
#		model, list_of_paths = selection.get_selected_rows()
#		if len(self._last_selected_contact):
#			# update unselected rows
#			for (jid, account) in self._last_selected_contact:
#				gobject.idle_add(self.draw_contact, jid, account)
#		self._last_selected_contact = []
#		if len(list_of_paths) == 0:
#			return
#		for path in list_of_paths:
#			row = model[path]
#			if row[C_TYPE] != 'contact':
#				self._last_selected_contact = []
#				return
#			jid = row[C_JID].decode('utf-8')
#			account = row[C_ACCOUNT].decode('utf-8')
#			self._last_selected_contact.append((jid, account))
#			gobject.idle_add(self.draw_contact, jid, account, True)

	def on_service_disco_menuitem_activate(self, widget, account):
		server_jid = gajim.config.get_per('accounts', account, 'hostname')
		if server_jid in gajim.interface.instances[account]['disco']:
			gajim.interface.instances[account]['disco'][server_jid].\
				window.present()
		else:
			try:
				# Object will add itself to the window dict
				disco.ServiceDiscoveryWindow(account, address_entry=True)
			except GajimGeneralException:
				pass

	def on_show_offline_contacts_menuitem_activate(self, widget):
		'''when show offline option is changed:
		redraw the treeview'''
		gajim.config.set('showoffline', not gajim.config.get('showoffline'))
		self.refilter_shown_roster_items()
		w = self.xml.get_widget('show_only_active_contacts_menuitem')
		if gajim.config.get('showoffline'):
			# We need to filter twice to show groups with no contacts inside
			# in the correct expand state
			self.refilter_shown_roster_items()
			w.set_sensitive(False)
		else:
			w.set_sensitive(True)

	def on_show_only_active_contacts_menuitem_activate(self, widget):
		'''when show only active contact option is changed:
		redraw the treeview'''
		gajim.config.set('show_only_chat_and_online', not gajim.config.get(
			'show_only_chat_and_online'))
		self.refilter_shown_roster_items()
		w = self.xml.get_widget('show_offline_contacts_menuitem')
		if gajim.config.get('show_only_chat_and_online'):
			# We need to filter twice to show groups with no contacts inside
			# in the correct expand state
			self.refilter_shown_roster_items()
			w.set_sensitive(False)
		else:
			w.set_sensitive(True)

	def on_view_menu_activate(self, widget):
		# Hide the show roster menu if we are not in the right windowing mode.
		if self.hpaned.get_child2() is not None:
			self.xml.get_widget('show_roster_menuitem').show()
		else:
			self.xml.get_widget('show_roster_menuitem').hide()

	def on_show_roster_menuitem_toggled(self, widget):
		# when num controls is 0 this menuitem is hidden, but still need to
		# disable keybinding
		if self.hpaned.get_child2() is not None:
			self.show_roster_vbox(widget.get_active())

################################################################################
### Drag and Drop handling
################################################################################

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

	def on_drop_rosterx(self, widget, account_source, c_source, account_dest,
	c_dest, was_big_brother, context, etime):
		gajim.connections[account_dest].send_contacts([c_source], c_dest.jid)

	def on_drop_in_contact(self, widget, account_source, c_source, account_dest,
	c_dest, was_big_brother, context, etime):

		if not gajim.connections[account_source].private_storage_supported or not\
		gajim.connections[account_dest].private_storage_supported:
			dialogs.WarningDialog(_('Metacontacts storage not supported by your '
				'server'),
				_('Your server does not support storing metacontacts information. '
				'So those information will not be saved on next reconnection.'))

		def merge_contacts(is_checked=None):
			contacts = 0
			if is_checked is not None: # dialog has been shown
				if is_checked: # user does not want to be asked again
					gajim.config.set('confirm_metacontacts', 'no')
				else:
					gajim.config.set('confirm_metacontacts', 'yes')

			# We might have dropped on a metacontact.
			# Remove it and readd later with updated family info
			dest_family = gajim.contacts.get_metacontacts_family(account_dest,
				c_dest.jid)
			if dest_family:
				self._remove_metacontact_family(dest_family, account_dest)
				source_family = gajim.contacts.get_metacontacts_family(account_source, c_source.jid)
				if dest_family == source_family:
					n = contacts = len(dest_family)
					for tag in source_family:
						if tag['jid'] == c_source.jid:
							tag['order'] = contacts
							continue
						if 'order' in tag:
							n -= 1
							tag['order'] = n
			else:
				self._remove_entity(c_dest, account_dest)

			old_family = gajim.contacts.get_metacontacts_family(account_source,
				c_source.jid)
			old_groups = c_source.groups

			# Remove old source contact(s)
			if was_big_brother:
				# We have got little brothers. Readd them all
				self._remove_metacontact_family(old_family, account_source)
			else:
				# We are only a litle brother. Simply remove us from our big brother
				if self._get_contact_iter(c_source.jid, account_source):
					# When we have been in the group before.
					# Do not try to remove us again
					self._remove_entity(c_source, account_source)

				own_data = {}
				own_data['jid'] = c_source.jid
				own_data['account'] = account_source
				# Don't touch the rest of the family
				old_family = [own_data]

			# Apply new tag and update contact
			for data in old_family:
				if account_source != data['account'] and not self.regroup:
					continue

				_account = data['account']
				_jid = data['jid']
				_contact = gajim.contacts.get_first_contact_from_jid(_account, _jid)

				_contact.groups = c_dest.groups[:]
				gajim.contacts.add_metacontact(account_dest, c_dest.jid,
					_account, _contact.jid, contacts)
				gajim.connections[account_source].update_contact(_contact.jid,
					_contact.name, _contact.groups)

			# Re-add all and update GUI
			new_family = gajim.contacts.get_metacontacts_family(account_source,
				c_source.jid)
			brothers = self._add_metacontact_family(new_family, account_source)

			for c, acc in brothers:
				self.draw_completely(c.jid, acc)

			old_groups.extend(c_dest.groups)
			for g in old_groups:
				self.draw_group(g, account_source)

			self.draw_account(account_source)
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
			_('Do _not ask me again'), on_response_ok=merge_contacts)
		if not confirm_metacontacts: # First time we see this window
			dlg.checkbutton.set_active(True)


	def on_drop_in_group(self, widget, account, c_source, grp_dest,
	is_big_brother, context, etime, grp_source = None):
		if is_big_brother:
			# add whole metacontact to new group
			self.add_contact_to_groups(c_source.jid, account, [grp_dest,])
			# remove afterwards so the contact is not moved to General in the
			# meantime
			if grp_dest != grp_source:
				self.remove_contact_from_groups(c_source.jid, account, [grp_source])
		else:
			# Normal contact or little brother
			family = gajim.contacts.get_metacontacts_family(account,
				c_source.jid)
			if family:
				# Little brother
				# Remove whole family. Remove us from the family.
				# Then re-add other family members.
				self._remove_metacontact_family(family, account)
				gajim.contacts.remove_metacontact(account, c_source.jid)
				for data in family:
					if account != data['account'] and not self.regroup:
						continue
					if data['jid'] == c_source.jid and\
					data['account'] == account:
						continue
					self.add_contact(data['jid'], data['account'])
					break

				self.add_contact_to_groups(c_source.jid, account, [grp_dest,])

			else:
				# Normal contact
				self.add_contact_to_groups(c_source.jid, account, [grp_dest,])
				# remove afterwards so the contact is not moved to General in the
				# meantime
				if grp_dest != grp_source:
					self.remove_contact_from_groups(c_source.jid, account,
						[grp_source])

		if context.action in (gtk.gdk.ACTION_MOVE, gtk.gdk.ACTION_COPY):
			context.finish(True, True, etime)


	def drag_drop(self, treeview, context, x, y, timestamp):
		target_list = treeview.drag_dest_get_target_list()
		target = treeview.drag_dest_find_target(context, target_list)
		treeview.drag_get_data(context, target)
		context.finish(False, True)
		return True

	def drag_data_received_data(self, treeview, context, x, y, selection, info,
	etime):
		treeview.stop_emission('drag_data_received')
		drop_info = treeview.get_dest_row_at_pos(x, y)
		if not drop_info:
			return
		if not selection.data:
			return # prevents tb when several entrys are dragged
		model = treeview.get_model()
		data = selection.data
		path_dest, position = drop_info

		if position == gtk.TREE_VIEW_DROP_BEFORE and len(path_dest) == 2 \
			and path_dest[1] == 0: # dropped before the first group
			return
		if position == gtk.TREE_VIEW_DROP_BEFORE and len(path_dest) == 2:
			# dropped before a group: we drop it in the previous group every time
			path_dest = (path_dest[0], path_dest[1]-1)
		# destination: the row something got dropped on
		iter_dest = model.get_iter(path_dest)
		type_dest = model[iter_dest][C_TYPE].decode('utf-8')
		jid_dest = model[iter_dest][C_JID].decode('utf-8')
		account_dest = model[iter_dest][C_ACCOUNT].decode('utf-8')

		# drop on account row in merged mode, we cannot know the desired account
		if account_dest == 'all':
			return
		# nothing can be done, if destination account is offline
		if gajim.connections[account_dest].connected < 2:
			return

		# A file got dropped on the roster
		if info == self.TARGET_TYPE_URI_LIST:
			if len(path_dest) < 3:
				return
			if type_dest != 'contact':
				return
			c_dest = gajim.contacts.get_contact_with_highest_priority(account_dest,
				jid_dest)
			if not gajim.capscache.is_supported(c_dest, NS_FILE):
				return
			uri = data.strip()
			uri_splitted = uri.split() # we may have more than one file dropped
			try:
				# This is always the last element in windows
				uri_splitted.remove('\0')
			except ValueError:
				pass
			nb_uri = len(uri_splitted)
			# Check the URIs
			bad_uris = []
			for a_uri in uri_splitted:
				path = helpers.get_file_path_from_dnd_dropped_uri(a_uri)
				if not os.path.isfile(path):
					bad_uris.append(a_uri)
			if len(bad_uris):
				dialogs.ErrorDialog(_('Invalid file URI:'), '\n'.join(bad_uris))
				return
			def _on_send_files(account, jid, uris):
				c = gajim.contacts.get_contact_with_highest_priority(account, jid)
				for uri in uris:
					path = helpers.get_file_path_from_dnd_dropped_uri(uri)
					if os.path.isfile(path): # is it file?
						gajim.interface.instances['file_transfers'].send_file(
							account, c, path)
			# Popup dialog to confirm sending
			prim_text = 'Send file?'
			sec_text = i18n.ngettext('Do you want to send this file to %s:',
				'Do you want to send these files to %s:', nb_uri) %\
				c_dest.get_shown_name()
			for uri in uri_splitted:
				path = helpers.get_file_path_from_dnd_dropped_uri(uri)
				sec_text += '\n' + os.path.basename(path)
			dialog = dialogs.NonModalConfirmationDialog(prim_text, sec_text,
				on_response_ok = (_on_send_files, account_dest, jid_dest,
				uri_splitted))
			dialog.popup()
			return

		# a roster entry was dragged and dropped somewhere in the roster

		# source: the row that was dragged
		path_source = treeview.get_selection().get_selected_rows()[1][0]
		iter_source = model.get_iter(path_source)
		type_source = model[iter_source][C_TYPE]
		account_source = model[iter_source][C_ACCOUNT].decode('utf-8')

		# Only normal contacts can be dragged
		if type_source != 'contact':
			return
		if gajim.config.get_per('accounts', account_source, 'is_zeroconf'):
			return

		# A contact was dropped
		if gajim.config.get_per('accounts', account_dest, 'is_zeroconf'):
			# drop on zeroconf account, adding not possible
			return
		if type_dest == 'self_contact':
			# drop on self contact row
			return
		if type_dest == 'account' and account_source == account_dest:
			# drop on the account it was dragged from
			return
		if type_dest == 'groupchat':
			# drop on a minimized groupchat
			# TODO: Invite to groupchat
			return

		# Get valid source group, jid and contact
		it = iter_source
		while model[it][C_TYPE] == 'contact':
			it = model.iter_parent(it)
		grp_source = model[it][C_JID].decode('utf-8')
		if grp_source in helpers.special_groups and \
			grp_source not in ('Not in Roster', 'Observers'):
			# a transport or a minimized groupchat was dragged
			# we can add it to other accounts but not move it to another group,
			# see below
			return
		jid_source = data.decode('utf-8')
		c_source = gajim.contacts.get_contact_with_highest_priority(
			account_source, jid_source)

		# Get destination group
		grp_dest = None
		if type_dest == 'group':
			grp_dest = model[iter_dest][C_JID].decode('utf-8')
		elif type_dest in ('contact', 'agent'):
			it = iter_dest
			while model[it][C_TYPE] != 'group':
				it = model.iter_parent(it)
			grp_dest = model[it][C_JID].decode('utf-8')
		if grp_dest in helpers.special_groups:
			return

		if jid_source == jid_dest:
			if grp_source == grp_dest and account_source == account_dest:
				# Drop on self
				return

		# contact drop somewhere in or on a foreign account
		if (type_dest == 'account' or not self.regroup) and \
				account_source != account_dest:
			# add to account in specified group
			dialogs.AddNewContactWindow(account=account_dest, jid=jid_source,
				user_nick=c_source.name, group=grp_dest)
			return

		# we may not add contacts from special_groups
		if grp_source in helpers.special_groups :
			return

		# Is the contact we drag a meta contact?
		accounts = (self.regroup and gajim.contacts.get_accounts()) or account_source
		is_big_brother = gajim.contacts.is_big_brother(account_source, jid_source, accounts)

		# Contact drop on group row or between two contacts
		if type_dest == 'group' or position == gtk.TREE_VIEW_DROP_BEFORE or \
				position == gtk.TREE_VIEW_DROP_AFTER:
			self.on_drop_in_group(None, account_source, c_source, grp_dest,
				is_big_brother, context, etime, grp_source)
			return

		# Contact drop on another contact, make meta contacts
		if position == gtk.TREE_VIEW_DROP_INTO_OR_AFTER or \
				position == gtk.TREE_VIEW_DROP_INTO_OR_BEFORE:
			c_dest = gajim.contacts.get_contact_with_highest_priority(account_dest,
				jid_dest)
			if not c_dest:
				# c_dest is None if jid_dest doesn't belong to account
				return
			menu = gtk.Menu()
			item = gtk.MenuItem(_('Send %s to %s') % (c_source.get_shown_name(),
				c_dest.get_shown_name()))
			item.connect('activate', self.on_drop_rosterx, account_source,
				c_source, account_dest, c_dest, is_big_brother, context, etime)
			menu.append(item)

			item = gtk.MenuItem(_('Make %s and %s metacontacts') % (
				c_source.get_shown_name(), c_dest.get_shown_name()))
			item.connect('activate', self.on_drop_in_contact, account_source,
				c_source, account_dest, c_dest, is_big_brother, context, etime)

			menu.append(item)

			menu.attach_to_widget(self.tree, None)
			menu.connect('selection-done', gtkgui_helpers.destroy_widget)
			menu.show_all()
			menu.popup(None, None, None, 1, etime)
#			self.on_drop_in_contact(treeview, account_source, c_source,
#				account_dest, c_dest, is_big_brother, context, etime)

################################################################################
### Everything about images and icons....
### Cleanup assigned to Jim++ :-)
################################################################################

	def get_appropriate_state_images(self, jid, size='16', icon_name='online'):
		'''check jid and return the appropriate state images dict for
		the demanded size. icon_name is taken into account when jid is from
		transport: transport iconset doesn't contain all icons, so we fall back
		to jabber one'''
		transport = gajim.get_transport_name_from_jid(jid)
		if transport and size in self.transports_state_images:
			if transport not in self.transports_state_images[size]:
				# we don't have iconset for this transport loaded yet. Let's do it
				self.make_transport_state_images(transport)
			if transport in self.transports_state_images[size] and \
			icon_name in self.transports_state_images[size][transport]:
				return self.transports_state_images[size][transport]
		return gajim.interface.jabber_state_images[size]

	def make_transport_state_images(self, transport):
		'''initialise opened and closed 'transport' iconset dict'''
		if gajim.config.get('use_transports_iconsets'):
			folder = os.path.join(helpers.get_transport_path(transport),
				'16x16')
			pixo, pixc = gtkgui_helpers.load_icons_meta()
			self.transports_state_images['opened'][transport] = \
				gtkgui_helpers.load_iconset(folder, pixo, transport=True)
			self.transports_state_images['closed'][transport] = \
				gtkgui_helpers.load_iconset(folder, pixc, transport=True)
			folder = os.path.join(helpers.get_transport_path(transport), '32x32')
			self.transports_state_images['32'][transport] = \
				gtkgui_helpers.load_iconset(folder, transport=True)
			folder = os.path.join(helpers.get_transport_path(transport), '16x16')
			self.transports_state_images['16'][transport] = \
				gtkgui_helpers.load_iconset(folder, transport=True)

	def update_jabber_state_images(self):
		# Update the roster
		self.setup_and_draw_roster()
		# Update the status combobox
		model = self.status_combobox.get_model()
		titer = model.get_iter_root()
		while titer:
			if model[titer][2] != '':
				# If it's not change status message iter
				# eg. if it has show parameter not ''
				model[titer][1] = gajim.interface.jabber_state_images['16'][model[
					titer][2]]
			titer = model.iter_next(titer)
		# Update the systray
		if gajim.interface.systray_enabled:
			gajim.interface.systray.set_img()

		for win in gajim.interface.msg_win_mgr.windows():
			for ctrl in win.controls():
				ctrl.update_ui()
				win.redraw_tab(ctrl)

		self.update_status_combobox()

	def set_account_status_icon(self, account):
		status = gajim.connections[account].connected
		child_iterA = self._get_account_iter(account, self.model)
		if not child_iterA:
			return
		if not self.regroup:
			show = gajim.SHOW_LIST[status]
		else:	# accounts merged
			show = helpers.get_global_show()
		self.model[child_iterA][C_IMG] = gajim.interface.jabber_state_images[
			'16'][show]

################################################################################
### Style and theme related methods
################################################################################

	def show_title(self):
		change_title_allowed = gajim.config.get('change_roster_title')
		if not change_title_allowed:
			return

		if gajim.config.get('one_message_window') == 'always_with_roster':
			# always_with_roster mode defers to the MessageWindow
			if not gajim.interface.msg_win_mgr.one_window_opened():
				# No MessageWindow to defer to
				self.window.set_title('Gajim')
			return

		nb_unread = 0
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

	def _change_style(self, model, path, titer, option):
		if option is None or model[titer][C_TYPE] == option:
			# We changed style for this type of row
			model[titer][C_NAME] = model[titer][C_NAME]

	def change_roster_style(self, option):
		self.model.foreach(self._change_style, option)
		for win in gajim.interface.msg_win_mgr.windows():
			win.repaint_themed_widgets()

	def repaint_themed_widgets(self):
		'''Notify windows that contain themed widgets to repaint them'''
		for win in gajim.interface.msg_win_mgr.windows():
			win.repaint_themed_widgets()
		for account in gajim.connections:
			for addr in gajim.interface.instances[account]['disco']:
				gajim.interface.instances[account]['disco'][addr].paint_banner()
			for ctrl in gajim.interface.minimized_controls[account].values():
				ctrl.repaint_themed_widgets()

	def update_avatar_in_gui(self, jid, account):
		# Update roster
		self.draw_avatar(jid, account)
		# Update chat window

		ctrl = gajim.interface.msg_win_mgr.get_control(jid, account)
		if ctrl:
			ctrl.show_avatar()

	def on_roster_treeview_style_set(self, treeview, style):
		'''When style (theme) changes, redraw all contacts'''
		for contact in self._iter_contact_rows():
			self.draw_contact(contact[C_JID].decode('utf-8'),
				contact[C_ACCOUNT].decode('utf-8'))

	def set_renderer_color(self, renderer, style, set_background=True):
		'''set style for treeview cell, using PRELIGHT system color'''
		if set_background:
			bgcolor = self.tree.style.bg[style]
			renderer.set_property('cell-background-gdk', bgcolor)
		else:
			fgcolor = self.tree.style.fg[style]
			renderer.set_property('foreground-gdk', fgcolor)

	def _iconCellDataFunc(self, column, renderer, model, titer, data=None):
		'''When a row is added, set properties for icon renderer'''
		theme = gajim.config.get('roster_theme')
		type_ = model[titer][C_TYPE]
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
			if not model[titer][C_JID] or not model[titer][C_ACCOUNT]:
				# This can append when at the moment we add the row
				return
			jid = model[titer][C_JID].decode('utf-8')
			account = model[titer][C_ACCOUNT].decode('utf-8')
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
			parent_iter = model.iter_parent(titer)
			if model[parent_iter][C_TYPE] == 'contact':
				renderer.set_property('xalign', 1)
			else:
				renderer.set_property('xalign', 0.4)
		renderer.set_property('width', 26)

	def _nameCellDataFunc(self, column, renderer, model, titer, data=None):
		'''When a row is added, set properties for name renderer'''
		theme = gajim.config.get('roster_theme')
		type_ = model[titer][C_TYPE]
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
			if not model[titer][C_JID] or not model[titer][C_ACCOUNT]:
				# This can append when at the moment we add the row
				return
			jid = model[titer][C_JID].decode('utf-8')
			account = model[titer][C_ACCOUNT].decode('utf-8')
			color = None
			if type_ == 'groupchat':
				ctrl = gajim.interface.minimized_controls[account].get(jid, None)
				if ctrl and ctrl.attention_flag:
					color = gajim.config.get_per('themes', theme,
						 'state_muc_directed_msg_color')
				renderer.set_property('foreground', 'red')
			if not color:
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
			parent_iter = model.iter_parent(titer)
			if model[parent_iter][C_TYPE] == 'contact':
				renderer.set_property('xpad', 16)
			else:
				renderer.set_property('xpad', 8)


	def _fill_mood_pixbuf_renderer(self, column, renderer, model, titer,
	data = None):
		'''When a row is added, set properties for avatar renderer'''
		theme = gajim.config.get('roster_theme')
		type_ = model[titer][C_TYPE]
		if type_ == 'group':
			renderer.set_property('visible', False)
			return

		# allocate space for the icon only if needed
		if model[titer][C_MOOD_PIXBUF]:
			renderer.set_property('visible', True)
		else:
			renderer.set_property('visible', False)
		if type_ == 'account':
			color = gajim.config.get_per('themes', theme,
				'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				self.set_renderer_color(renderer,
					gtk.STATE_ACTIVE)
			# align pixbuf to the right)
			renderer.set_property('xalign', 1)
		# prevent type_ = None, see http://trac.gajim.org/ticket/2534
		elif type_:
			if not model[titer][C_JID] \
			or not model[titer][C_ACCOUNT]:
				# This can append at the moment we add the row
				return
			jid = model[titer][C_JID].decode('utf-8')
			account = model[titer][C_ACCOUNT].decode('utf-8')
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background',
					gajim.config.get(
					'just_connected_bg_color'))
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background',
					gajim.config.get(
					'just_disconnected_bg_color'))
			else:
				color = gajim.config.get_per('themes',
					theme, 'contactbgcolor')
				if color:
					renderer.set_property(
						'cell-background', color)
				else:
					renderer.set_property(
						'cell-background', None)
			# align pixbuf to the right
			renderer.set_property('xalign', 1)


	def _fill_activity_pixbuf_renderer(self, column, renderer, model, titer,
	data = None):
		'''When a row is added, set properties for avatar renderer'''
		theme = gajim.config.get('roster_theme')
		type_ = model[titer][C_TYPE]
		if type_ == 'group':
			renderer.set_property('visible', False)
			return

		# allocate space for the icon only if needed
		if model[titer][C_ACTIVITY_PIXBUF]:
			renderer.set_property('visible', True)
		else:
			renderer.set_property('visible', False)
		if type_ == 'account':
			color = gajim.config.get_per('themes', theme,
				'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				self.set_renderer_color(renderer,
					gtk.STATE_ACTIVE)
			# align pixbuf to the right)
			renderer.set_property('xalign', 1)
		# prevent type_ = None, see http://trac.gajim.org/ticket/2534
		elif type_:
			if not model[titer][C_JID] \
			or not model[titer][C_ACCOUNT]:
				# This can append at the moment we add the row
				return
			jid = model[titer][C_JID].decode('utf-8')
			account = model[titer][C_ACCOUNT].decode('utf-8')
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background',
					gajim.config.get(
					'just_connected_bg_color'))
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background',
					gajim.config.get(
					'just_disconnected_bg_color'))
			else:
				color = gajim.config.get_per('themes',
					theme, 'contactbgcolor')
				if color:
					renderer.set_property(
						'cell-background', color)
				else:
					renderer.set_property(
						'cell-background', None)
			# align pixbuf to the right
			renderer.set_property('xalign', 1)


	def _fill_tune_pixbuf_renderer(self, column, renderer, model, titer,
	data = None):
		'''When a row is added, set properties for avatar renderer'''
		theme = gajim.config.get('roster_theme')
		type_ = model[titer][C_TYPE]
		if type_ == 'group':
			renderer.set_property('visible', False)
			return

		# allocate space for the icon only if needed
		if model[titer][C_TUNE_PIXBUF]:
			renderer.set_property('visible', True)
		else:
			renderer.set_property('visible', False)
		if type_ == 'account':
			color = gajim.config.get_per('themes', theme,
				'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				self.set_renderer_color(renderer,
					gtk.STATE_ACTIVE)
			# align pixbuf to the right)
			renderer.set_property('xalign', 1)
		# prevent type_ = None, see http://trac.gajim.org/ticket/2534
		elif type_:
			if not model[titer][C_JID] \
			or not model[titer][C_ACCOUNT]:
				# This can append at the moment we add the row
				return
			jid = model[titer][C_JID].decode('utf-8')
			account = model[titer][C_ACCOUNT].decode('utf-8')
			if jid in gajim.newly_added[account]:
				renderer.set_property('cell-background',
					gajim.config.get(
					'just_connected_bg_color'))
			elif jid in gajim.to_be_removed[account]:
				renderer.set_property('cell-background',
					gajim.config.get(
					'just_disconnected_bg_color'))
			else:
				color = gajim.config.get_per('themes',
					theme, 'contactbgcolor')
				if color:
					renderer.set_property(
						'cell-background', color)
				else:
					renderer.set_property(
						'cell-background', None)
			# align pixbuf to the right
			renderer.set_property('xalign', 1)


	def _fill_avatar_pixbuf_renderer(self, column, renderer, model, titer,
	data = None):
		'''When a row is added, set properties for avatar renderer'''
		theme = gajim.config.get('roster_theme')
		type_ = model[titer][C_TYPE]
		if type_ in ('group', 'account'):
			renderer.set_property('visible', False)
			return

		# allocate space for the icon only if needed
		if model[titer][C_AVATAR_PIXBUF] or \
		gajim.config.get('avatar_position_in_roster') == 'left':
			renderer.set_property('visible', True)
		else:
			renderer.set_property('visible', False)
		if type_: # prevent type_ = None, see http://trac.gajim.org/ticket/2534
			if not model[titer][C_JID] or not model[titer][C_ACCOUNT]:
				# This can append at the moment we add the row
				return
			jid = model[titer][C_JID].decode('utf-8')
			account = model[titer][C_ACCOUNT].decode('utf-8')
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
		if gajim.config.get('avatar_position_in_roster') == 'left':
			renderer.set_property('width', gajim.config.get('roster_avatar_width'))
			renderer.set_property('xalign', 0.5)
		else:
			renderer.set_property('xalign', 1) # align pixbuf to the right

	def _fill_padlock_pixbuf_renderer(self, column, renderer, model, titer,
	data = None):
		'''When a row is added, set properties for padlock renderer'''
		theme = gajim.config.get('roster_theme')
		type_ = model[titer][C_TYPE]
		# allocate space for the icon only if needed
		if type_ == 'account' and model[titer][C_PADLOCK_PIXBUF]:
			renderer.set_property('visible', True)
			color = gajim.config.get_per('themes', theme, 'accountbgcolor')
			if color:
				renderer.set_property('cell-background', color)
			else:
				self.set_renderer_color(renderer, gtk.STATE_ACTIVE)
			renderer.set_property('xalign', 1) # align pixbuf to the right
		else:
			renderer.set_property('visible', False)

################################################################################
### Everything about building menus
### FIXME: We really need to make it simpler! 1465 lines are a few to much....
################################################################################

	def make_menu(self, force=False):
		'''create the main window\'s menus'''
		if not force and not self.actions_menu_needs_rebuild:
			return
		new_chat_menuitem = self.xml.get_widget('new_chat_menuitem')
		single_message_menuitem = self.xml.get_widget(
			'send_single_message_menuitem')
		join_gc_menuitem = self.xml.get_widget('join_gc_menuitem')
		muc_icon = gtkgui_helpers.load_icon('muc_active')
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

		if self.single_message_menuitem_handler_id:
			single_message_menuitem.handler_disconnect(
				self.single_message_menuitem_handler_id)
			self.single_message_menuitem_handler_id = None

		if self.profile_avatar_menuitem_handler_id:
			profile_avatar_menuitem.handler_disconnect(
				self.profile_avatar_menuitem_handler_id)
			self.profile_avatar_menuitem_handler_id = None

		# remove the existing submenus
		add_new_contact_menuitem.remove_submenu()
		service_disco_menuitem.remove_submenu()
		join_gc_menuitem.remove_submenu()
		single_message_menuitem.remove_submenu()
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

		connected_accounts_with_private_storage = 0

		# items that get shown whether an account is zeroconf or not
		accounts_list = sorted(gajim.contacts.get_accounts())
		if connected_accounts > 1: # 2 or more accounts? make submenus
			new_chat_sub_menu = gtk.Menu()

			for account in accounts_list:
				if gajim.connections[account].connected <= 1:
					# if offline or connecting
					continue

				# new chat
				new_chat_item = gtk.MenuItem(_('using account %s') % account,
					False)
				new_chat_sub_menu.append(new_chat_item)
				new_chat_item.connect('activate',
					self.on_new_chat_menuitem_activate, account)

			new_chat_menuitem.set_submenu(new_chat_sub_menu)
			new_chat_sub_menu.show_all()

		elif connected_accounts == 1: # user has only one account
			for account in gajim.connections:
				if gajim.account_is_connected(account): # THE connected account
					# new chat
					if not self.new_chat_menuitem_handler_id:
						self.new_chat_menuitem_handler_id = new_chat_menuitem.\
							connect('activate', self.on_new_chat_menuitem_activate,
							account)

					break

		# menu items that don't apply to zeroconf connections
		if connected_accounts == 1 or (connected_accounts == 2 and \
		gajim.zeroconf_is_connected()):
			# only one 'real' (non-zeroconf) account is connected, don't need submenus

			for account in accounts_list:
				if gajim.account_is_connected(account) and \
				not gajim.config.get_per('accounts', account, 'is_zeroconf'):
					# gc
					if gajim.connections[account].private_storage_supported:
						connected_accounts_with_private_storage += 1
					self.add_bookmarks_list(gc_sub_menu, account)
					gc_sub_menu.show_all()
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

					# single message
					if not self.single_message_menuitem_handler_id:
						self.single_message_menuitem_handler_id = \
						single_message_menuitem.connect('activate', \
						self.on_send_single_message_menuitem_activate, account)

					# new chat accel
					if not self.have_new_chat_accel:
						ag = gtk.accel_groups_from_object(self.window)[0]
						new_chat_menuitem.add_accelerator('activate', ag,
							gtk.keysyms.n,	gtk.gdk.CONTROL_MASK, gtk.ACCEL_VISIBLE)
						self.have_new_chat_accel = True

					break # No other account connected
		else:
			# 2 or more 'real' accounts are connected, make submenus
			single_message_sub_menu = gtk.Menu()
			add_sub_menu = gtk.Menu()
			disco_sub_menu = gtk.Menu()

			for account in accounts_list:
				if gajim.connections[account].connected <= 1 or \
				gajim.config.get_per('accounts', account, 'is_zeroconf'):
					# skip account if it's offline or connecting or is zeroconf
					continue

				# single message
				single_message_item = gtk.MenuItem(_('using account %s') % account,
					False)
				single_message_sub_menu.append(single_message_item)
				single_message_item.connect('activate',
					self.on_send_single_message_menuitem_activate, account)

				# join gc
				if gajim.connections[account].private_storage_supported:
					connected_accounts_with_private_storage += 1
				gc_item = gtk.MenuItem(_('using account %s') % account, False)
				gc_sub_menu.append(gc_item)
				gc_menuitem_menu = gtk.Menu()
				self.add_bookmarks_list(gc_menuitem_menu, account)
				gc_item.set_submenu(gc_menuitem_menu)

				# add
				add_item = gtk.MenuItem(_('to %s account') % account, False)
				add_sub_menu.append(add_item)
				add_item.connect('activate', self.on_add_new_contact, account)

				# disco
				disco_item = gtk.MenuItem(_('using %s account') % account, False)
				disco_sub_menu.append(disco_item)
				disco_item.connect('activate',
					self.on_service_disco_menuitem_activate, account)

			single_message_menuitem.set_submenu(single_message_sub_menu)
			single_message_sub_menu.show_all()
			gc_sub_menu.show_all()
			add_new_contact_menuitem.set_submenu(add_sub_menu)
			add_sub_menu.show_all()
			service_disco_menuitem.set_submenu(disco_sub_menu)
			disco_sub_menu.show_all()

		if connected_accounts == 0:
			# no connected accounts, make the menuitems insensitive
			for item in (new_chat_menuitem, join_gc_menuitem,\
					add_new_contact_menuitem, service_disco_menuitem,\
					single_message_menuitem):
				item.set_sensitive(False)
		else: # we have one or more connected accounts
			for item in (new_chat_menuitem, join_gc_menuitem,
					add_new_contact_menuitem, service_disco_menuitem,
					single_message_menuitem):
				item.set_sensitive(True)
			# disable some fields if only local account is there
			if connected_accounts == 1:
				for account in gajim.connections:
					if gajim.account_is_connected(account) and \
							gajim.connections[account].is_zeroconf:
						for item in (join_gc_menuitem, add_new_contact_menuitem,
							service_disco_menuitem, single_message_menuitem):
							item.set_sensitive(False)

		# Manage GC bookmarks
		newitem = gtk.SeparatorMenuItem() # separator
		gc_sub_menu.append(newitem)

		newitem = gtk.ImageMenuItem(_('_Manage Bookmarks...'))
		img = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES,
			gtk.ICON_SIZE_MENU)
		newitem.set_image(img)
		newitem.connect('activate', self.on_manage_bookmarks_menuitem_activate)
		gc_sub_menu.append(newitem)
		gc_sub_menu.show_all()
		if connected_accounts_with_private_storage == 0:
			newitem.set_sensitive(False)

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
					profile_avatar_menuitem.connect('activate',
					self.on_profile_avatar_menuitem_activate, account)

		if len(connected_accounts_with_vcard) == 0:
			profile_avatar_menuitem.set_sensitive(False)
		else:
			profile_avatar_menuitem.set_sensitive(True)

		# Advanced Actions
		if len(gajim.connections) == 0: # user has no accounts
			advanced_menuitem.set_sensitive(False)
		elif len(gajim.connections) == 1: # we have one acccount
			account = gajim.connections.keys()[0]
			advanced_menuitem_menu = self.get_and_connect_advanced_menuitem_menu(
				account)
			self.advanced_menus.append(advanced_menuitem_menu)

			self.add_history_manager_menuitem(advanced_menuitem_menu)

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

			self.add_history_manager_menuitem(advanced_sub_menu)

			advanced_menuitem.set_submenu(advanced_sub_menu)
			advanced_sub_menu.show_all()

		self.actions_menu_needs_rebuild = False

	def build_account_menu(self, account):
		# we have to create our own set of icons for the menu
		# using self.jabber_status_images is poopoo
		iconset = gajim.config.get('iconset')
		path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
		state_images = gtkgui_helpers.load_iconset(path)

		if not gajim.config.get_per('accounts', account, 'is_zeroconf'):
			xml = gtkgui_helpers.get_glade('account_context_menu.glade')
			account_context_menu = xml.get_widget('account_context_menu')

			status_menuitem = xml.get_widget('status_menuitem')
			start_chat_menuitem = xml.get_widget('start_chat_menuitem')
			join_group_chat_menuitem = xml.get_widget('join_group_chat_menuitem')
			muc_icon = gtkgui_helpers.load_icon('muc_active')
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
				uf_show = helpers.get_uf_show(show, use_mnemonic=True)
				item = gtk.ImageMenuItem(uf_show)
				icon = state_images[show]
				item.set_image(icon)
				sub_menu.append(item)
				con = gajim.connections[account]
				if show == 'invisible' and con.connected > 1 and \
				not con.privacy_rules_supported:
					item.set_sensitive(False)
				else:
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

			uf_show = helpers.get_uf_show('offline', use_mnemonic=True)
			item = gtk.ImageMenuItem(uf_show)
			icon = state_images['offline']
			item.set_image(icon)
			sub_menu.append(item)
			item.connect('activate', self.change_status, account, 'offline')

			pep_menuitem = xml.get_widget('pep_menuitem')
			if gajim.connections[account].pep_supported:
				have_tune = gajim.config.get_per('accounts', account,
					'publish_tune')
				pep_submenu = gtk.Menu()
				pep_menuitem.set_submenu(pep_submenu)
				item = gtk.CheckMenuItem(_('Publish Tune'))
				pep_submenu.append(item)
				if not dbus_support.supported:
					item.set_sensitive(False)
				else:
					item.set_active(have_tune)
					item.connect('toggled', self.on_publish_tune_toggled, account)

				pep_config = gtk.ImageMenuItem(_('Configure Services...'))
				item = gtk.SeparatorMenuItem()
				pep_submenu.append(item)
				pep_config.set_sensitive(True)
				pep_submenu.append(pep_config)
				pep_config.connect('activate',
					self.on_pep_services_menuitem_activate, account)
				img = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES,
					gtk.ICON_SIZE_MENU)
				pep_config.set_image(img)

			else:
				pep_menuitem.set_sensitive(False)

			if not gajim.connections[account].gmail_url:
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
			contact = gajim.contacts.create_contact(jid=hostname) # Fake contact
			execute_command_menuitem.connect('activate',
				self.on_execute_command, contact, account)

			start_chat_menuitem.connect('activate',
				self.on_new_chat_menuitem_activate, account)

			gc_sub_menu = gtk.Menu() # gc is always a submenu
			join_group_chat_menuitem.set_submenu(gc_sub_menu)
			self.add_bookmarks_list(gc_sub_menu, account)

			# make some items insensitive if account is offline
			if gajim.connections[account].connected < 2:
				for widget in (add_contact_menuitem, service_discovery_menuitem,
				join_group_chat_menuitem, execute_command_menuitem, pep_menuitem,
				start_chat_menuitem):
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
				uf_show = helpers.get_uf_show(show, use_mnemonic=True)
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

			uf_show = helpers.get_uf_show('offline', use_mnemonic=True)
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

	def make_account_menu(self, event, titer):
		'''Make account's popup menu'''
		model = self.modelfilter
		account = model[titer][C_ACCOUNT].decode('utf-8')

		if account != 'all': # not in merged mode
			menu = self.build_account_menu(account)
		else:
			menu = gtk.Menu()
			iconset = gajim.config.get('iconset')
			path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
			accounts = [] # Put accounts in a list to sort them
			for account in gajim.connections:
				accounts.append(account)
			accounts.sort()
			for account in accounts:
				state_images = gtkgui_helpers.load_iconset(path)
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
		menu.popup(None, None, None, event_button, event.time)

	def make_group_menu(self, event, titer):
		'''Make group's popup menu'''
		model = self.modelfilter
		path = model.get_path(titer)
		group = model[titer][C_JID].decode('utf-8')
		account = model[titer][C_ACCOUNT].decode('utf-8')

		list_ = [] # list of (jid, account) tuples
		list_online = [] # list of (jid, account) tuples

		group = model[titer][C_JID]
		for jid in gajim.contacts.get_jid_list(account):
			contact = gajim.contacts.get_contact_with_highest_priority(account,
					jid)
			if group in contact.get_shown_groups():
				if contact.show not in ('offline', 'error'):
					list_online.append((contact, account))
				list_.append((contact, account))
		menu = gtk.Menu()

		# Make special context menu if group is Groupchats
		if group == _('Groupchats'):
			maximize_menuitem = gtk.ImageMenuItem(_('_Maximize All'))
			icon = gtk.image_new_from_stock(gtk.STOCK_GOTO_TOP, gtk.ICON_SIZE_MENU)
			maximize_menuitem.set_image(icon)
			maximize_menuitem.connect('activate', self.on_all_groupchat_maximized,\
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

			group_message_to_all_online_item = gtk.MenuItem(
				_('To all online users'))
			send_group_message_submenu.append(group_message_to_all_online_item)

			group_message_to_all_online_item.connect('activate',
				self.on_send_single_message_menuitem_activate, account, list_online)
			group_message_to_all_item.connect('activate',
				self.on_send_single_message_menuitem_activate, account, list_)

			# Invite to
			invite_menuitem = gtk.ImageMenuItem(_('In_vite to'))
			muc_icon = gtkgui_helpers.load_icon('muc_active')
			if muc_icon:
				invite_menuitem.set_image(muc_icon)

			self.build_invite_submenu(invite_menuitem, list_online)
			menu.append(invite_menuitem)

			# Send Custom Status
			send_custom_status_menuitem = gtk.ImageMenuItem(
				_('Send Cus_tom Status'))
			# add a special img for this menuitem
			if helpers.group_is_blocked(account, group):
				send_custom_status_menuitem.set_image(gtkgui_helpers.load_icon(
					'offline'))
				send_custom_status_menuitem.set_sensitive(False)
			else:
				icon = gtk.image_new_from_stock(gtk.STOCK_NETWORK,
					gtk.ICON_SIZE_MENU)
				send_custom_status_menuitem.set_image(icon)
			status_menuitems = gtk.Menu()
			send_custom_status_menuitem.set_submenu(status_menuitems)
			iconset = gajim.config.get('iconset')
			path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
			for s in ('online', 'chat', 'away', 'xa', 'dnd', 'offline'):
				# icon MUST be different instance for every item
				state_images = gtkgui_helpers.load_iconset(path)
				status_menuitem = gtk.ImageMenuItem(helpers.get_uf_show(s))
				status_menuitem.connect('activate', self.on_send_custom_status,
					list_, s, group)
				icon = state_images[s]
				status_menuitem.set_image(icon)
				status_menuitems.append(status_menuitem)
			menu.append(send_custom_status_menuitem)

			# there is no singlemessage and custom status for zeroconf
			if gajim.config.get_per('accounts', account, 'is_zeroconf'):
				send_custom_status_menuitem.set_sensitive(False)
				send_group_message_item.set_sensitive(False)

		if not group in helpers.special_groups:
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
			rename_item.connect('activate', self.on_rename, 'group', group,
				account)

			# Block group
			is_blocked = False
			if self.regroup:
				for g_account in gajim.connections:
					if helpers.group_is_blocked(g_account, group):
						is_blocked = True
			else:
				if helpers.group_is_blocked(account, group):
					is_blocked = True

			if is_blocked and gajim.connections[account].privacy_rules_supported:
				unblock_menuitem = gtk.ImageMenuItem(_('_Unblock'))
				icon = gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_MENU)
				unblock_menuitem.set_image(icon)
				unblock_menuitem.connect('activate', self.on_unblock, list_, group)
				menu.append(unblock_menuitem)
			else:
				block_menuitem = gtk.ImageMenuItem(_('_Block'))
				icon = gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_MENU)
				block_menuitem.set_image(icon)
				block_menuitem.connect('activate', self.on_block, list_, group)
				menu.append(block_menuitem)
				if not gajim.connections[account].privacy_rules_supported:
					block_menuitem.set_sensitive(False)

			# Remove group
			remove_item = gtk.ImageMenuItem(_('_Remove'))
			icon = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
			remove_item.set_image(icon)
			menu.append(remove_item)
			remove_item.connect('activate', self.on_remove_group_item_activated,
				group, account)

			# unsensitive if account is not connected
			if gajim.connections[account].connected < 2:
				rename_item.set_sensitive(False)

			# General group cannot be changed
			if group == _('General'):
				rename_item.set_sensitive(False)
				block_menuitem.set_sensitive(False)
				remove_item.set_sensitive(False)

		event_button = gtkgui_helpers.get_possible_button_event(event)

		menu.attach_to_widget(self.tree, None)
		menu.connect('selection-done', gtkgui_helpers.destroy_widget)
		menu.show_all()
		menu.popup(None, None, None, event_button, event.time)

	def make_contact_menu(self, event, titer):
		'''Make contact\'s popup menu'''
		model = self.modelfilter
		jid = model[titer][C_JID].decode('utf-8')
		tree_path = model.get_path(titer)
		account = model[titer][C_ACCOUNT].decode('utf-8')
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		menu = gtkgui_helpers.get_contact_menu(contact, account)
		menu.attach_to_widget(self.tree, None)

		if not contact:
			return

		# Zeroconf Account
		if gajim.config.get_per('accounts', account, 'is_zeroconf'):
			xml = gtkgui_helpers.get_glade('zeroconf_contact_context_menu.glade')
			zeroconf_contact_context_menu = xml.get_widget(
				'zeroconf_contact_context_menu')

			start_chat_menuitem = xml.get_widget('start_chat_menuitem')
			execute_command_menuitem = xml.get_widget('execute_command_menuitem')
			rename_menuitem = xml.get_widget('rename_menuitem')
			edit_groups_menuitem = xml.get_widget('edit_groups_menuitem')
			send_file_menuitem = xml.get_widget('send_file_menuitem')
			assign_openpgp_key_menuitem = xml.get_widget(
				'assign_openpgp_key_menuitem')
			add_special_notification_menuitem = xml.get_widget(
				'add_special_notification_menuitem')

			# add a special img for send file menuitem
			path_to_upload_img = os.path.join(gajim.DATA_DIR, 'pixmaps',
				'upload.png')
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

			above_information_separator = xml.get_widget(
				'above_information_separator')

			information_menuitem = xml.get_widget('information_menuitem')
			history_menuitem = xml.get_widget('history_menuitem')

			contacts = gajim.contacts.get_contacts(account, jid)
			if len(contacts) > 1: # several resources
				sub_menu = gtk.Menu()
				start_chat_menuitem.set_submenu(sub_menu)

				iconset = gajim.config.get('iconset')
				path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
				for c in contacts:
					# icon MUST be different instance for every item
					state_images = gtkgui_helpers.load_iconset(path)
					item = gtk.ImageMenuItem('%s (%s)' % (c.resource,
						str(c.priority)))
					icon_name = helpers.get_icon_name_to_show(c, account)
					icon = state_images[icon_name]
					item.set_image(icon)
					sub_menu.append(item)
					item.connect('activate', gajim.interface.on_open_chat_window, \
						c, account,	c.resource)

			else: # one resource
				start_chat_menuitem.connect('activate',
					self.on_roster_treeview_row_activated, tree_path)

			if gajim.capscache.is_supported(contact, NS_FILE):
				send_file_menuitem.set_sensitive(True)
				send_file_menuitem.connect('activate',
					self.on_send_file_menuitem_activate, contact, account)
			else:
				send_file_menuitem.set_sensitive(False)

			execute_command_menuitem.connect('activate',
				self.on_execute_command, contact, account)

			rename_menuitem.connect('activate', self.on_rename, 'contact', jid,
				account)
			if contact.show in ('offline', 'error'):
				information_menuitem.set_sensitive(False)
				send_file_menuitem.set_sensitive(False)
			else:
				information_menuitem.connect('activate', self.on_info_zeroconf,
					contact, account)
			history_menuitem.connect('activate', self.on_history, contact,
				account)

			if _('Not in Roster') not in contact.get_shown_groups():
				# contact is in normal group
				edit_groups_menuitem.set_no_show_all(False)
				assign_openpgp_key_menuitem.set_no_show_all(False)
				edit_groups_menuitem.connect('activate', self.on_edit_groups, [(
					contact,account)])

				if gajim.connections[account].gpg:
					assign_openpgp_key_menuitem.connect('activate',
						self.on_assign_pgp_key, contact, account)
				else:
					assign_openpgp_key_menuitem.set_sensitive(False)

			else: # contact is in group 'Not in Roster'
				edit_groups_menuitem.set_sensitive(False)
				edit_groups_menuitem.set_no_show_all(True)
				assign_openpgp_key_menuitem.set_sensitive(False)

			# Remove many items when it's self contact row
			if our_jid:
				for menuitem in (rename_menuitem, edit_groups_menuitem,
				above_information_separator):
					menuitem.set_no_show_all(True)
					menuitem.hide()

			# Unsensitive many items when account is offline
			if gajim.connections[account].connected < 2:
				for widget in (start_chat_menuitem,	rename_menuitem,
				edit_groups_menuitem, send_file_menuitem):
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
		ignore_menuitem = xml.get_widget('ignore_menuitem')
		unignore_menuitem = xml.get_widget('unignore_menuitem')
		rename_menuitem = xml.get_widget('rename_menuitem')
		edit_groups_menuitem = xml.get_widget('edit_groups_menuitem')
		send_file_menuitem = xml.get_widget('send_file_menuitem')
		assign_openpgp_key_menuitem = xml.get_widget(
			'assign_openpgp_key_menuitem')
		set_custom_avatar_menuitem = xml.get_widget('set_custom_avatar_menuitem')
		add_special_notification_menuitem = xml.get_widget(
			'add_special_notification_menuitem')
		execute_command_menuitem = xml.get_widget(
			'execute_command_menuitem')

		# add a special img for send file menuitem
		path_to_upload_img = os.path.join(gajim.DATA_DIR, 'pixmaps', 'upload.png')
		img = gtk.Image()
		img.set_from_file(path_to_upload_img)
		send_file_menuitem.set_image(img)

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
			send_custom_status_menuitem.set_image( \
				gtkgui_helpers.load_icon('offline'))
			send_custom_status_menuitem.set_sensitive(False)
		elif account in gajim.interface.status_sent_to_users and \
		jid in gajim.interface.status_sent_to_users[account]:
			send_custom_status_menuitem.set_image(
				gtkgui_helpers.load_icon( \
					gajim.interface.status_sent_to_users[account][jid]))
		else:
			icon = gtk.image_new_from_stock(gtk.STOCK_NETWORK, gtk.ICON_SIZE_MENU)
			send_custom_status_menuitem.set_image(icon)

		if not our_jid:
			# add a special img for rename menuitem
			path_to_kbd_input_img = os.path.join(gajim.DATA_DIR, 'pixmaps',
				'kbd_input.png')
			img = gtk.Image()
			img.set_from_file(path_to_kbd_input_img)
			rename_menuitem.set_image(img)

		muc_icon = gtkgui_helpers.load_icon('muc_active')
		if muc_icon:
			invite_menuitem.set_image(muc_icon)

		self.build_invite_submenu(invite_menuitem, [(contact, account)])

		# Subscription submenu
		subscription_menuitem = xml.get_widget('subscription_menuitem')
		send_auth_menuitem, ask_auth_menuitem, revoke_auth_menuitem =\
			subscription_menuitem.get_submenu().get_children()
		add_to_roster_menuitem = xml.get_widget('add_to_roster_menuitem')
		remove_from_roster_menuitem = xml.get_widget(
			'remove_from_roster_menuitem')

		information_menuitem = xml.get_widget('information_menuitem')
		history_menuitem = xml.get_widget('history_menuitem')

		contacts = gajim.contacts.get_contacts(account, jid)

		# One or several resource, we do the same for send_custom_status
		status_menuitems = gtk.Menu()
		send_custom_status_menuitem.set_submenu(status_menuitems)
		iconset = gajim.config.get('iconset')
		path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
		for s in ('online', 'chat', 'away', 'xa', 'dnd', 'offline'):
			# icon MUST be different instance for every item
			state_images = gtkgui_helpers.load_iconset(path)
			status_menuitem = gtk.ImageMenuItem(helpers.get_uf_show(s))
			status_menuitem.connect('activate', self.on_send_custom_status,
				[(contact, account)], s)
			icon = state_images[s]
			status_menuitem.set_image(icon)
			status_menuitems.append(status_menuitem)
		if len(contacts) > 1: # several resources
			start_chat_menuitem.set_submenu(self.build_resources_submenu(contacts,
				account, gajim.interface.on_open_chat_window))
			send_file_menuitem.set_submenu(self.build_resources_submenu(contacts,
				account, self.on_send_file_menuitem_activate,
				cap=NS_FILE))
			execute_command_menuitem.set_submenu(self.build_resources_submenu(
				contacts, account, self.on_execute_command,
				cap=NS_COMMANDS))

		else: # one resource
			start_chat_menuitem.connect('activate',
				gajim.interface.on_open_chat_window, contact, account)
			if gajim.capscache.is_supported(contact, NS_COMMANDS):
				execute_command_menuitem.set_sensitive(True)
				execute_command_menuitem.connect('activate', self.on_execute_command,
					contact, account, contact.resource)
			else:
				execute_command_menuitem.set_sensitive(False)

			# This does nothing:
			# our_jid_other_resource = None
			# if our_jid:
			# 	# It's another resource of us, be sure to send invite to her
			# 	our_jid_other_resource = contact.resource
			# Else this var is useless but harmless in next connect calls

			if gajim.capscache.is_supported(contact, NS_FILE):
				send_file_menuitem.set_sensitive(True)
				send_file_menuitem.connect('activate',
					self.on_send_file_menuitem_activate, contact, account)
			else:
				send_file_menuitem.set_sensitive(False)

		send_single_message_menuitem.connect('activate',
			self.on_send_single_message_menuitem_activate, account, contact)

		rename_menuitem.connect('activate', self.on_rename, 'contact', jid,
			account)
		remove_from_roster_menuitem.connect('activate', self.on_req_usub,
			[(contact, account)])
		information_menuitem.connect('activate', self.on_info, contact,
			account)
		history_menuitem.connect('activate', self.on_history, contact,
			account)

		if _('Not in Roster') not in contact.get_shown_groups():
			# contact is in normal group
			add_to_roster_menuitem.hide()
			add_to_roster_menuitem.set_no_show_all(True)
			edit_groups_menuitem.connect('activate', self.on_edit_groups, [(
				contact,account)])

			if gajim.connections[account].gpg:
				assign_openpgp_key_menuitem.connect('activate',
					self.on_assign_pgp_key, contact, account)
			else:
				assign_openpgp_key_menuitem.set_sensitive(False)

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
			if contact.sub in ('to', 'none') or gajim.get_transport_name_from_jid(
			jid, use_config_setting=False):
				revoke_auth_menuitem.set_sensitive(False)
			else:
				revoke_auth_menuitem.connect('activate', self.revoke_auth, jid,
					account)

		else: # contact is in group 'Not in Roster'
			add_to_roster_menuitem.set_no_show_all(False)
			edit_groups_menuitem.set_sensitive(False)
			assign_openpgp_key_menuitem.set_sensitive(False)
			subscription_menuitem.set_sensitive(False)

			add_to_roster_menuitem.connect('activate',
				self.on_add_to_roster, contact, account)

		set_custom_avatar_menuitem.connect('activate',
			self.on_set_custom_avatar_activate, contact, account)
		# Hide items when it's self contact row
		if our_jid:
			menuitem = xml.get_widget('manage_contact')
			menuitem.set_sensitive(False)

		# Unsensitive many items when account is offline
		if gajim.connections[account].connected < 2:
			for widget in (start_chat_menuitem, send_single_message_menuitem,
			rename_menuitem, edit_groups_menuitem, send_file_menuitem,
			subscription_menuitem, add_to_roster_menuitem,
			remove_from_roster_menuitem, execute_command_menuitem,
			send_custom_status_menuitem):
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
					unignore_menuitem.connect('activate', self.on_unblock, [(contact,
						account)])
				else:
					unblock_menuitem.connect('activate', self.on_unblock, [(contact,
						account)])
			else:
				unblock_menuitem.set_no_show_all(True)
				unblock_menuitem.hide()
				if gajim.get_transport_name_from_jid(jid, use_config_setting=False):
					block_menuitem.set_no_show_all(True)
					block_menuitem.hide()
					ignore_menuitem.set_no_show_all(False)
					ignore_menuitem.connect('activate', self.on_block, [(contact,
						account)])
				else:
					block_menuitem.connect('activate', self.on_block, [(contact,
						account)])
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

	def make_multiple_contact_menu(self, event, iters):
		'''Make group's popup menu'''
		model = self.modelfilter
		list_ = [] # list of (jid, account) tuples
		one_account_offline = False
		is_blocked = True
		privacy_rules_supported = True
		for titer in iters:
			jid = model[titer][C_JID].decode('utf-8')
			account = model[titer][C_ACCOUNT].decode('utf-8')
			if gajim.connections[account].connected < 2:
				one_account_offline = True
			if not gajim.connections[account].privacy_rules_supported:
				privacy_rules_supported = False
			contact = gajim.contacts.get_contact_with_highest_priority(account,
				jid)
			if helpers.jid_is_blocked(account, jid):
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
		muc_icon = gtkgui_helpers.load_icon('muc_active')
		if muc_icon:
			invite_item.set_image(muc_icon)

		self.build_invite_submenu(invite_item, list_)
		menu.append(invite_item)

		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		# Manage Transport submenu
		item = gtk.ImageMenuItem(_('_Manage Contacts'))
		icon = gtk.image_new_from_stock(gtk.STOCK_PROPERTIES, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		manage_contacts_submenu = gtk.Menu()
		item.set_submenu(manage_contacts_submenu)
		menu.append(item)

		# Edit Groups
		edit_groups_item = gtk.ImageMenuItem(_('Edit _Groups'))
		icon = gtk.image_new_from_stock(gtk.STOCK_EDIT, gtk.ICON_SIZE_MENU)
		edit_groups_item.set_image(icon)
		manage_contacts_submenu.append(edit_groups_item)
		edit_groups_item.connect('activate', self.on_edit_groups, list_)

		item = gtk.SeparatorMenuItem() # separator
		manage_contacts_submenu.append(item)

		# Block
		if is_blocked and privacy_rules_supported:
			unblock_menuitem = gtk.ImageMenuItem(_('_Unblock'))
			icon = gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_MENU)
			unblock_menuitem.set_image(icon)
			unblock_menuitem.connect('activate', self.on_unblock, list_)
			manage_contacts_submenu.append(unblock_menuitem)
		else:
			block_menuitem = gtk.ImageMenuItem(_('_Block'))
			icon = gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_MENU)
			block_menuitem.set_image(icon)
			block_menuitem.connect('activate', self.on_block, list_)
			manage_contacts_submenu.append(block_menuitem)

			if not privacy_rules_supported:
				block_menuitem.set_sensitive(False)

		# Remove
		remove_item = gtk.ImageMenuItem(_('_Remove'))
		icon = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
		remove_item.set_image(icon)
		manage_contacts_submenu.append(remove_item)
		remove_item.connect('activate', self.on_req_usub, list_)
		# unsensitive remove if one account is not connected
		if one_account_offline:
			remove_item.set_sensitive(False)

		event_button = gtkgui_helpers.get_possible_button_event(event)

		menu.attach_to_widget(self.tree, None)
		menu.connect('selection-done', gtkgui_helpers.destroy_widget)
		menu.show_all()
		menu.popup(None, None, None, event_button, event.time)

	def make_transport_menu(self, event, titer):
		'''Make transport\'s popup menu'''
		model = self.modelfilter
		jid = model[titer][C_JID].decode('utf-8')
		path = model.get_path(titer)
		account = model[titer][C_ACCOUNT].decode('utf-8')
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		menu = gtk.Menu()

		# Send single message
		item = gtk.ImageMenuItem(_('Send Single Message'))
		icon = gtk.image_new_from_stock(gtk.STOCK_NEW, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		item.connect('activate',
			self.on_send_single_message_menuitem_activate, account, contact)
		menu.append(item)

		blocked = False
		if helpers.jid_is_blocked(account, jid):
			blocked = True

		# Send Custom Status
		send_custom_status_menuitem = gtk.ImageMenuItem(_('Send Cus_tom Status'))
		# add a special img for this menuitem
		if blocked:
			send_custom_status_menuitem.set_image(gtkgui_helpers.load_icon(
				'offline'))
			send_custom_status_menuitem.set_sensitive(False)
		else:
			if account in gajim.interface.status_sent_to_users and \
			jid in gajim.interface.status_sent_to_users[account]:
				send_custom_status_menuitem.set_image(gtkgui_helpers.load_icon(
					gajim.interface.status_sent_to_users[account][jid]))
			else:
				icon = gtk.image_new_from_stock(gtk.STOCK_NETWORK,
					gtk.ICON_SIZE_MENU)
				send_custom_status_menuitem.set_image(icon)
			status_menuitems = gtk.Menu()
			send_custom_status_menuitem.set_submenu(status_menuitems)
			iconset = gajim.config.get('iconset')
			path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
			for s in ('online', 'chat', 'away', 'xa', 'dnd', 'offline'):
				# icon MUST be different instance for every item
				state_images = gtkgui_helpers.load_iconset(path)
				status_menuitem = gtk.ImageMenuItem(helpers.get_uf_show(s))
				status_menuitem.connect('activate', self.on_send_custom_status,
					[(contact, account)], s)
				icon = state_images[s]
				status_menuitem.set_image(icon)
				status_menuitems.append(status_menuitem)
		menu.append(send_custom_status_menuitem)

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

		# Manage Transport submenu
		item = gtk.ImageMenuItem(_('_Manage Transport'))
		icon = gtk.image_new_from_stock(gtk.STOCK_PROPERTIES, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		manage_transport_submenu = gtk.Menu()
		item.set_submenu(manage_transport_submenu)
		menu.append(item)

		# Modify Transport
		item = gtk.ImageMenuItem(_('_Modify Transport'))
		icon = gtk.image_new_from_stock(gtk.STOCK_PREFERENCES, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		manage_transport_submenu.append(item)
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
		manage_transport_submenu.append(item)
		item.connect('activate', self.on_rename, 'agent', jid, account)
		if gajim.account_is_disconnected(account):
			item.set_sensitive(False)

		item = gtk.SeparatorMenuItem() # separator
		manage_transport_submenu.append(item)

		# Block
		if blocked:
			item = gtk.ImageMenuItem(_('_Unblock'))
			item.connect('activate', self.on_unblock, [(contact, account)])
		else:
			item = gtk.ImageMenuItem(_('_Block'))
			item.connect('activate', self.on_block, [(contact, account)])

		icon = gtk.image_new_from_stock(gtk.STOCK_STOP, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		manage_transport_submenu.append(item)
		if gajim.account_is_disconnected(account):
			item.set_sensitive(False)

		# Remove
		item = gtk.ImageMenuItem(_('_Remove'))
		icon = gtk.image_new_from_stock(gtk.STOCK_REMOVE, gtk.ICON_SIZE_MENU)
		item.set_image(icon)
		manage_transport_submenu.append(item)
		item.connect('activate', self.on_remove_agent, [(contact, account)])
		if gajim.account_is_disconnected(account):
			item.set_sensitive(False)

		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		# Information
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

	def make_groupchat_menu(self, event, titer):
		model = self.modelfilter

		jid = model[titer][C_JID].decode('utf-8')
		account = model[titer][C_ACCOUNT].decode('utf-8')
		contact = gajim.contacts.get_contact_with_highest_priority(account, jid)
		menu = gtk.Menu()

		if jid in gajim.interface.minimized_controls[account]:
			maximize_menuitem = gtk.ImageMenuItem(_('_Maximize'))
			icon = gtk.image_new_from_stock(gtk.STOCK_GOTO_TOP, gtk.ICON_SIZE_MENU)
			maximize_menuitem.set_image(icon)
			maximize_menuitem.connect('activate', self.on_groupchat_maximized, \
				jid, account)
			menu.append(maximize_menuitem)

		if not gajim.gc_connected[account].get(jid, False):
			connect_menuitem = gtk.ImageMenuItem(_('_Reconnect'))
			connect_icon = gtk.image_new_from_stock(gtk.STOCK_CONNECT, \
				gtk.ICON_SIZE_MENU)
			connect_menuitem.set_image(connect_icon)
			connect_menuitem.connect('activate', self.on_reconnect, jid, account)
			menu.append(connect_menuitem)
		disconnect_menuitem = gtk.ImageMenuItem(_('_Disconnect'))
		disconnect_icon = gtk.image_new_from_stock(gtk.STOCK_DISCONNECT, \
			gtk.ICON_SIZE_MENU)
		disconnect_menuitem.set_image(disconnect_icon)
		disconnect_menuitem.connect('activate', self.on_disconnect, jid, account)
		menu.append(disconnect_menuitem)

		item = gtk.SeparatorMenuItem() # separator
		menu.append(item)

		history_menuitem = gtk.ImageMenuItem(_('_History'))
		history_icon = gtk.image_new_from_stock(gtk.STOCK_JUSTIFY_FILL, \
			gtk.ICON_SIZE_MENU)
		history_menuitem.set_image(history_icon)
		history_menuitem .connect('activate', self.on_history, \
				contact, account)
		menu.append(history_menuitem)

		event_button = gtkgui_helpers.get_possible_button_event(event)

		menu.attach_to_widget(self.tree, None)
		menu.connect('selection-done', gtkgui_helpers.destroy_widget)
		menu.show_all()
		menu.popup(None, None, None, event_button, event.time)

	def build_resources_submenu(self, contacts, account, action, room_jid=None,
	room_account=None, cap=None):
		''' Build a submenu with contact's resources.
		room_jid and room_account are for action self.on_invite_to_room '''
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
			if action == self.on_invite_to_room:
				item.connect('activate', action, [(c, account)],
					room_jid, room_account, c.resource)
			elif action == self.on_invite_to_new_room:
				item.connect('activate', action, [(c, account)], c.resource)
			else: # start_chat, execute_command, send_file
				item.connect('activate', action, c, account, c.resource)
			if cap and \
			not gajim.capscache.is_supported(c, cap):
				item.set_sensitive(False)
		return sub_menu

	def build_invite_submenu(self, invite_menuitem, list_):
		'''list_ in a list of (contact, account)'''
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
			invite_to_new_room_menuitem.set_submenu(self.build_resources_submenu(
				contact_list, account, self.on_invite_to_new_room, cap=NS_MUC))
		elif len(list_) == 1 and gajim.capscache.is_supported(contact, NS_MUC):
			invite_menuitem.set_sensitive(True)
			# use resource if it's self contact
			if contact.jid == gajim.get_jid_from_account(account):
				resource = contact.resource
			else:
				resource = None
			invite_to_new_room_menuitem.connect('activate',
				self.on_invite_to_new_room, list_, resource)
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
			minimized_controls += \
				gajim.interface.minimized_controls[account].values()
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
					menuitem.set_submenu(self.build_resources_submenu(
						contact_list, account, self.on_invite_to_room, room_jid,
						account))
				else:
					# use resource if it's self contact
					if contact.jid == gajim.get_jid_from_account(account):
						resource = contact.resource
					else:
						resource = None
					menuitem.connect('activate', self.on_invite_to_room, list_,
						room_jid, account, resource)
				invite_to_submenu.append(menuitem)

	def get_and_connect_advanced_menuitem_menu(self, account):
		'''adds FOR ACCOUNT options'''
		xml = gtkgui_helpers.get_glade('advanced_menuitem_menu.glade')
		advanced_menuitem_menu = xml.get_widget('advanced_menuitem_menu')

		xml_console_menuitem = xml.get_widget('xml_console_menuitem')
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
			privacy_lists_menuitem.connect('activate',
				self.on_privacy_lists_menuitem_activate, account)
		else:
			privacy_lists_menuitem.set_sensitive(False)

		if gajim.connections[account].is_zeroconf:
			administrator_menuitem.set_sensitive(False)
			send_server_message_menuitem.set_sensitive(False)
			set_motd_menuitem.set_sensitive(False)
			update_motd_menuitem.set_sensitive(False)
			delete_motd_menuitem.set_sensitive(False)
		else:
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

	def add_history_manager_menuitem(self, menu):
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

		# user has at least one bookmark
		if len(gajim.connections[account].bookmarks) > 0:
			item = gtk.SeparatorMenuItem() # separator
			gc_sub_menu.append(item)

		for bookmark in gajim.connections[account].bookmarks:
			item = gtk.MenuItem(bookmark['name'], False) # Do not use underline
			item.connect('activate', self.on_bookmark_menuitem_activate,
				account, bookmark)
			gc_sub_menu.append(item)

	def set_actions_menu_needs_rebuild(self):
		self.actions_menu_needs_rebuild = True

	def show_appropriate_context_menu(self, event, iters):
		# iters must be all of the same type
		model = self.modelfilter
		type_ = model[iters[0]][C_TYPE]
		for titer in iters[1:]:
			if model[titer][C_TYPE] != type_:
				return
		if type_ == 'group' and len(iters) == 1:
			self.make_group_menu(event, iters[0])
		if type_ == 'groupchat' and len(iters) == 1:
			self.make_groupchat_menu(event, iters[0])
		elif type_ == 'agent' and len(iters) == 1:
			self.make_transport_menu(event, iters[0])
		elif type_ in ('contact', 'self_contact') and len(iters) == 1:
			self.make_contact_menu(event, iters[0])
		elif type_ == 'contact':
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

################################################################################
###
################################################################################

	def __init__(self):
		self.filtering = False
		self.xml = gtkgui_helpers.get_glade('roster_window.glade')
		self.window = self.xml.get_widget('roster_window')
		self.hpaned = self.xml.get_widget('roster_hpaned')
		gajim.interface.msg_win_mgr = MessageWindowMgr(self.window, self.hpaned)
		gajim.interface.msg_win_mgr.connect('window-delete',
			self.on_message_window_delete)
		self.advanced_menus = [] # We keep them to destroy them
		if gajim.config.get('roster_window_skip_taskbar'):
			self.window.set_property('skip-taskbar-hint', True)
		self.tree = self.xml.get_widget('roster_treeview')
		sel = self.tree.get_selection()
		sel.set_mode(gtk.SELECTION_MULTIPLE)
		#sel.connect('changed',
		#	self.on_treeview_selection_changed)

		self._last_selected_contact = [] # holds a list of (jid, account) tupples
		self.transports_state_images = {'16': {}, '32': {}, 'opened': {},
			'closed': {}}

		self.last_save_dir = None
		self.editing_path = None # path of row with cell in edit mode
		self.add_new_contact_handler_id = False
		self.service_disco_handler_id = False
		self.new_chat_menuitem_handler_id = False
		self.single_message_menuitem_handler_id = False
		self.profile_avatar_menuitem_handler_id = False
		self.actions_menu_needs_rebuild = True
		self.regroup = gajim.config.get('mergeaccounts')
		self.clicked_path = None # Used remember on wich row we clicked
		if len(gajim.connections) < 2: # Do not merge accounts if only one exists
			self.regroup = False
		#FIXME: When list_accel_closures will be wrapped in pygtk
		# no need of this variable
		self.have_new_chat_accel = False # Is the "Ctrl+N" shown ?
		gtkgui_helpers.resize_window(self.window,
			gajim.config.get('roster_width'),
			gajim.config.get('roster_height'))
		gtkgui_helpers.move_window(self.window,
			gajim.config.get('roster_x-position'),
			gajim.config.get('roster_y-position'))

		self.popups_notification_height = 0
		self.popup_notification_windows = []

 		# Remove contact from roster when last event opened
		# { (contact, account): { backend: boolean }
		self.contacts_to_be_removed = {}
		gajim.events.event_removed_subscribe(self.on_event_removed)

		# when this value become 0 we quit main application. If it's more than 0
		# it means we are waiting for this number of accounts to disconnect before
		# quitting
		self.quit_on_next_offline = -1

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

		self.status_combobox.set_row_separator_func(self._iter_is_separator)

		for show in ('online', 'chat', 'away', 'xa', 'dnd', 'invisible'):
			uf_show = helpers.get_uf_show(show)
			liststore.append([uf_show, gajim.interface.jabber_state_images['16'][
				show], show, True])
		# Add a Separator (self._iter_is_separator() checks on string SEPARATOR)
		liststore.append(['SEPARATOR', None, '', True])

		path = os.path.join(gajim.DATA_DIR, 'pixmaps', 'kbd_input.png')
		img = gtk.Image()
		img.set_from_file(path)
		# sensitivity to False because by default we're offline
		self.status_message_menuitem_iter = liststore.append(
			[_('Change Status Message...'), img, '', False])
		# Add a Separator (self._iter_is_separator() checks on string SEPARATOR)
		liststore.append(['SEPARATOR', None, '', True])

		uf_show = helpers.get_uf_show('offline')
		liststore.append([uf_show, gajim.interface.jabber_state_images['16'][
			'offline'], 'offline', True])

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
		showOnlyChatAndOnline = gajim.config.get('show_only_chat_and_online')

		w = self.xml.get_widget('show_offline_contacts_menuitem')
		w.set_active(showOffline)
		if showOnlyChatAndOnline:
			w.set_sensitive(False)

		w = self.xml.get_widget('show_only_active_contacts_menuitem')
		w.set_active(showOnlyChatAndOnline)
		if showOffline:
			w.set_sensitive(False)

		show_transports_group = gajim.config.get('show_transports_group')
		self.xml.get_widget('show_transports_menuitem').set_active(
			show_transports_group)

		self.xml.get_widget('show_roster_menuitem').set_active(True)

		# columns

		# this col has 3 cells:
		# first one img, second one text, third is sec pixbuf
		col = gtk.TreeViewColumn()

		def add_avatar_renderer():
			render_pixbuf = gtk.CellRendererPixbuf() # avatar img
			col.pack_start(render_pixbuf, expand=False)
			col.add_attribute(render_pixbuf, 'pixbuf',
				C_AVATAR_PIXBUF)
			col.set_cell_data_func(render_pixbuf,
				self._fill_avatar_pixbuf_renderer, None)

		if gajim.config.get('avatar_position_in_roster') == 'left':
			add_avatar_renderer()

		render_image = cell_renderer_image.CellRendererImage(0, 0)
		# show img or +-
		col.pack_start(render_image, expand=False)
		col.add_attribute(render_image, 'image', C_IMG)
		col.set_cell_data_func(render_image, self._iconCellDataFunc, None)

		render_text = gtk.CellRendererText() # contact or group or account name
		render_text.set_property('ellipsize', pango.ELLIPSIZE_END)
		col.pack_start(render_text, expand=True)
		col.add_attribute(render_text, 'markup', C_NAME) # where we hold the name
		col.set_cell_data_func(render_text, self._nameCellDataFunc, None)

		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand=False)
		col.add_attribute(render_pixbuf, 'pixbuf', C_MOOD_PIXBUF)
		col.set_cell_data_func(render_pixbuf,
			self._fill_mood_pixbuf_renderer, None)

		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand=False)
		col.add_attribute(render_pixbuf, 'pixbuf', C_ACTIVITY_PIXBUF)
		col.set_cell_data_func(render_pixbuf,
			self._fill_activity_pixbuf_renderer, None)

		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand=False)
		col.add_attribute(render_pixbuf, 'pixbuf', C_TUNE_PIXBUF)
		col.set_cell_data_func(render_pixbuf,
			self._fill_tune_pixbuf_renderer, None)

		if gajim.config.get('avatar_position_in_roster') == 'right':
			add_avatar_renderer()

		render_pixbuf = gtk.CellRendererPixbuf() # tls/ssl img
		col.pack_start(render_pixbuf, expand=False)
		col.add_attribute(render_pixbuf, 'pixbuf', C_PADLOCK_PIXBUF)
		col.set_cell_data_func(render_pixbuf,
			self._fill_padlock_pixbuf_renderer, None)
		self.tree.append_column(col)

		# do not show gtk arrows workaround
		col = gtk.TreeViewColumn()
		render_pixbuf = gtk.CellRendererPixbuf()
		col.pack_start(render_pixbuf, expand=False)
		self.tree.append_column(col)
		col.set_visible(False)
		self.tree.set_expander_column(col)

		# set search function
		self.tree.set_search_equal_func(self._search_roster_func)

		# signals
		self.TARGET_TYPE_URI_LIST = 80
		TARGETS = [('MY_TREE_MODEL_ROW',
			gtk.TARGET_SAME_APP | gtk.TARGET_SAME_WIDGET, 0)]
		TARGETS2 = [('MY_TREE_MODEL_ROW', gtk.TARGET_SAME_WIDGET, 0),
					('text/uri-list', 0, self.TARGET_TYPE_URI_LIST)]
		self.tree.enable_model_drag_source(gtk.gdk.BUTTON1_MASK, TARGETS,
			gtk.gdk.ACTION_DEFAULT | gtk.gdk.ACTION_MOVE | gtk.gdk.ACTION_COPY)
		self.tree.enable_model_drag_dest(TARGETS2, gtk.gdk.ACTION_DEFAULT)
		self.tree.connect('drag_begin', self.drag_begin)
		self.tree.connect('drag_end', self.drag_end)
		self.tree.connect('drag_drop', self.drag_drop)
		self.tree.connect('drag_data_get', self.drag_data_get_data)
		self.tree.connect('drag_data_received', self.drag_data_received_data)
		self.dragging = False
		self.xml.signal_autoconnect(self)
		self.combobox_callback_active = True

		self.collapsed_rows = gajim.config.get('collapsed_rows').split('\t')
		self.tooltip = tooltips.RosterTooltip()
		# Workaroung: For strange reasons signal is behaving like row-changed
		self._toggeling_row = False
		self.setup_and_draw_roster()

		if gajim.config.get('show_roster_on_startup'):
			self.window.show_all()
		else:
			if not gajim.config.get('trayicon') or not \
			gajim.interface.systray_capabilities:
				# cannot happen via GUI, but I put this incase user touches
				# config. without trayicon, he or she should see the roster!
				self.window.show_all()
				gajim.config.set('show_roster_on_startup', True)

		if len(gajim.connections) == 0: # if we have no account
			gajim.interface.instances['account_creation_wizard'] = \
				config.AccountCreationWizardWindow()
		if not gajim.ZEROCONF_ACC_NAME in gajim.config.get_per('accounts'):
			# Create zeroconf in config file
			from common.zeroconf import connection_zeroconf
			connection_zeroconf.ConnectionZeroconf(gajim.ZEROCONF_ACC_NAME)

# vim: se ts=3:
