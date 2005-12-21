## common/contacts.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
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

class Contact:
	'''Information concerning each contact'''
	def __init__(self, jid='', name='', groups=[], show='', status='', sub='',
			ask='', resource='', priority=5, keyID='', our_chatstate=None,
			chatstate=None):
		self.jid = jid
		self.name = name
		self.groups = groups
		self.show = show
		self.status = status
		self.sub = sub
		self.ask = ask
		self.resource = resource
		self.priority = priority
		self.keyID = keyID

		# please read jep-85 http://www.jabber.org/jeps/jep-0085.html
		# we keep track of jep85 support by the peer by three extra states:
		# None, False and 'ask'
		# None if no info about peer
		# False if peer does not support jep85
		# 'ask' if we sent the first 'active' chatstate and are waiting for reply
		# this holds what WE SEND to contact (our current chatstate)
		self.our_chatstate = our_chatstate
		# this is contact's chatstate
		self.chatstate = chatstate

	def get_full_jid(self):
		if self.resource:
			return self.jid + '/' + self.resource
		return self.jid

class GC_Contact:
	'''Information concerning each groupchat contact'''
	def __init__(self, room_jid='', nick='', show='', status='', role='',
			affiliation='', jid = ''):
		self.room_jid = room_jid
		self.nick = nick
		self.show = show
		self.status = status
		self.role = role
		self.affiliation = affiliation
		self.jid = jid

	def get_full_jid(self):
		return self.room_jid + '/' + self.nick

class Contacts:
	'''Information concerning all contacts and groupchat contacts'''
	def __init__(self):
		self._contacts = {} # list of contacts {acct: {jid1: [C1, C2]}, } one Contact per resource
		self._gc_contacts = {} # list of contacts that are in gc {acct: {room_jid: {nick: C}}}
		self._sub_contacts = {} # {acct: {jid1: jid2}} means jid1 is sub of jid2

	def change_account_name(self, old_name, new_name):
		self._contacts[new_name] = self._contacts[old_name]
		self._gc_contacts[new_name] = self._gc_contacts[old_name]
		self._contacts.remove(old_name)
		self._gc_contacts.remove(old_name)

	def add_account(self, account):
		self._contacts[account] = {}
		self._gc_contacts[account] = {}

	def remove_account(self, account):
		self._contacts.remove(account)
		self._gc_contacts.remove(account)

	def create_contact(self, jid='', name='', groups=[], show='', status='',
		sub='', ask='', resource='', priority=5, keyID='', our_chatstate=None,
		chatstate=None):
		return Contact(jid, name, groups, show, status, sub, ask, resource,
			priority, keyID, our_chatstate, chatstate)
	
	def copy_contact(self, contact):
		return self.create_contact(jid = contact.jid, name = contact.name,
			groups = contact.groups, show = contact.show, status = contact.status,
			sub = contact.sub, ask = contact.ask, resource = contact.resource,
			priority = contact.priority, keyID = contact.keyID,
			our_chatstate = contact.our_chatstate, chatstate = contact.chatstate)

	def add_contact(self, account, contact):
		# No such account before ?
		if not self._contacts.has_key(account):
			self._contacts[account] = {contact.jid : [contact]}
			return
		# No such jid before ?
		if not self._contacts[account].has_key(contact.jid):
			self._contacts[account][contact.jid] = [contact]
			return
		# If same JID with same resource already exists, use the new one
		for c in self._contacts[account][contact.jid]:
			if c.resource == contact.resource:
				self.remove_contact(account, c)
				break
		self._contacts[account][contact.jid].append(contact)

	def remove_contact(self, account, contact):
		if not self._contacts.has_key(account):
			return
		if not self._contacts[account].has_key(contact.jid):
			return
		if contact in self._contacts[account][contact.jid]:
			self._contacts[account][contact.jid].remove(contact)
		# It was the last resource of this contact ?
		if not len(self._contacts[account][contact.jid]):
			self._contacts[account].remove(contact.jid)

	def create_gc_contact(self, room_jid='', nick='', show='', status='',
		role='', affiliation='', jid=''):
		return GC_Contact(room_jid, nick, show, status, role, affiliation, jid)
	
	def add_gc_contact(self, account, gc_contact):
		# No such account before ?
		if not self._gc_contacts.has_key(account):
			self._contacts[account] = {gc_contact.room_jid : {gc_contact.nick: \
				gc_contact}}
			return
		# No such room_jid before ?
		if not self._gc_contacts[account].has_key(gc_contact.room_jid):
			self._gc_contacts[account][gc_contact.room_jid] = {gc_contact.nick: \
				gc_contact}
			return
		self._gc_contacts[account][gc_contact.room_jid][gc_contact.nick] = \
				gc_contact

	def remove_gc_contact(self, account, gc_contact):
		if not self._gc_contacts.has_key(account):
			return
		if not self._gc_contacts[account].has_key(gc_contact.room_jid):
			return
		if not self._gc_contacts[account][gc_contact.room_jid].has_key(
			gc_contact.nick):
			return
		self._gc_contacts[account][gc_contact.room_jid].remove(gc_contact.nick)
		# It was the last nick in room ?
		if not len(self._gc_contacts[account][gc_contact.room_jid]):
			self._gc_contacts[account].remove(gc_contact.room_jid)

	def is_subcontact(self, account, contact):
		if contact.jid in self._sub_contacts[account]:
			return True
	
	def get_contacts_from_jid(self, account, jid):
		''' we may have two or more resources on that jid '''
		if jid in self._contacts[account]:
			contacts_instances = self._contacts[account][jid]
			return contacts_instances
		return []

	def get_highest_prio_contact_from_contacts(self, contacts):
		if not contacts:
			return None
		prim_contact = contacts[0]
		for contact in contacts[1:]:
			if int(contact.priority) > int(prim_contact.priority):
				prim_contact = contact
		return prim_contact

	def get_contact_with_highest_priority(self, account, jid):
		contacts = self.get_contacts_from_jid(account, jid)
		return self.get_highest_prio_contact_from_contacts(contacts)

	def get_first_contact_from_jid(self, account, jid):
		if jid in self._contacts[account]:
			return self._contacts[account][jid][0]
		else: # it's fake jid
			room, nick = gajim.get_room_and_nick_from_fjid(jid)
			if self._gc_contacts[account].has_key(room) and \
				nick in self._gc_contacts[account][room]:
				return self._gc_contacts[account][room][nick]
		return None

	def get_parent_contact(self, account, contact):
		'''Returns the parent contact of contact if it's a sub-contact,
		else contact'''
		if is_subcontact(account, contact):
			parrent_jid = self._sub_contacts[account][contact.jid]
			return self.get_contact_with_highest_priority(account,
				parrent_jid)
		return contact

	def get_master_contact(self, account, contact):
		'''Returns the master contact of contact (parent of parent...) if it's a
		sub-contact, else contact'''
		while is_subcontact(account, contact):
			parrent_jid = self._sub_contacts[account][contact.jid]
			contact = self.get_contact_with_highest_priority(account,
				parrent_jid)
		return contact

	def contact_from_gc_contact(self, gc_contact):
		'''Create a Contact instance from a GC_Contact instance'''
		return Contact(jid = gc_contact.get_full_jid(), name = gc_contact.nick,
			groups = ['none'], show = gc_contact.show, status = gc_contact.status,
			sub = 'none')

	def is_pm_from_jid(self, account, jid):
		'''Returns True if the given jid is a private message jid'''
		if jid in self._contacts[account]:
			return False
		return True
