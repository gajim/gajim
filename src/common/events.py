# -*- coding:utf-8 -*-
## src/common/events.py
##
## Copyright (C) 2006 Jean-Marie Traissard <jim AT lapin.org>
##                    Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2007 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Julien Pivotto <roidelapluie AT gmail.com>
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

import time

class Event:
	"""
	Information concerning each event
	"""

	def __init__(self, type_, time_, parameters, show_in_roster=False,
			show_in_systray=True):
		"""
		type_ in chat, normal, file-request, file-error, file-completed,
		file-request-error, file-send-error, file-stopped, gc_msg, pm,
		printed_chat, printed_gc_msg, printed_marked_gc_msg, printed_pm,
		gc-invitation, subscription_request, unsubscribedm jingle-incoming

		parameters is (per type_):
			chat, normal, pm: [message, subject, kind, time, encrypted, resource,
			msg_id]
				where kind in error, incoming
			file-*: file_props
			gc_msg: None
			printed_chat: control
			printed_*: None
				messages that are already printed in chat, but not read
			gc-invitation: [room_jid, reason, password, is_continued]
			subscription_request: [text, nick]
			unsubscribed: contact
			jingle-incoming: (fulljid, sessionid, content_types)
		"""
		self.type_ = type_
		self.time_ = time_
		self.parameters = parameters
		self.show_in_roster = show_in_roster
		self.show_in_systray = show_in_systray
		# Set when adding the event
		self.jid = None
		self.account = None

class Events:
	"""
	Information concerning all events
	"""

	def __init__(self):
		self._events = {} # list of events {acct: {jid1: [E1, E2]}, }
		self._event_added_listeners = []
		self._event_removed_listeners = []

	def event_added_subscribe(self, listener):
		"""
		Add a listener when an event is added to the queue
		"""
		if not listener in self._event_added_listeners:
			self._event_added_listeners.append(listener)

	def event_added_unsubscribe(self, listener):
		"""
		Remove a listener when an event is added to the queue
		"""
		if listener in self._event_added_listeners:
			self._event_added_listeners.remove(listener)

	def event_removed_subscribe(self, listener):
		"""
		Add a listener when an event is removed from the queue
		"""
		if not listener in self._event_removed_listeners:
			self._event_removed_listeners.append(listener)

	def event_removed_unsubscribe(self, listener):
		"""
		Remove a listener when an event is removed from the queue
		"""
		if listener in self._event_removed_listeners:
			self._event_removed_listeners.remove(listener)

	def fire_event_added(self, event):
		for listener in self._event_added_listeners:
			listener(event)

	def fire_event_removed(self, event_list):
		for listener in self._event_removed_listeners:
			listener(event_list)

	def change_account_name(self, old_name, new_name):
		if old_name in self._events:
			self._events[new_name] = self._events[old_name]
			del self._events[old_name]

	def add_account(self, account):
		self._events[account] = {}

	def get_accounts(self):
		return self._events.keys()

	def remove_account(self, account):
		del self._events[account]

	def create_event(self, type_, parameters, time_ = time.time(),
	show_in_roster = False, show_in_systray = True):
		return Event(type_, time_, parameters, show_in_roster,
			show_in_systray)

	def add_event(self, account, jid, event):
		# No such account before ?
		if account not in self._events:
			self._events[account] = {jid: [event]}
		# no such jid before ?
		elif jid not in self._events[account]:
			self._events[account][jid] = [event]
		else:
			self._events[account][jid].append(event)
		event.jid = jid
		event.account = account
		self.fire_event_added(event)

	def remove_events(self, account, jid, event = None, types = []):
		"""
		If event is not specified, remove all events from this jid, optionally
		only from given type return True if no such event found
		"""
		if account not in self._events:
			return True
		if jid not in self._events[account]:
			return True
		if event: # remove only one event
			if event in self._events[account][jid]:
				if len(self._events[account][jid]) == 1:
					del self._events[account][jid]
				else:
					self._events[account][jid].remove(event)
				self.fire_event_removed([event])
				return
			else:
				return True
		if types:
			new_list = [] # list of events to keep
			removed_list = [] # list of removed events
			for ev in self._events[account][jid]:
				if ev.type_ not in types:
					new_list.append(ev)
				else:
					removed_list.append(ev)
			if len(new_list) == len(self._events[account][jid]):
				return True
			if new_list:
				self._events[account][jid] = new_list
			else:
				del self._events[account][jid]
			self.fire_event_removed(removed_list)
			return
		# no event nor type given, remove them all
		self.fire_event_removed(self._events[account][jid])
		del self._events[account][jid]

	def change_jid(self, account, old_jid, new_jid):
		if account not in self._events:
			return
		if old_jid not in self._events[account]:
			return
		if new_jid in self._events[account]:
			self._events[account][new_jid] += self._events[account][old_jid]
		else:
			self._events[account][new_jid] = self._events[account][old_jid]
		del self._events[account][old_jid]

	def get_nb_events(self, types = [], account = None):
		return self._get_nb_events(types = types, account = account)

	def get_events(self, account, jid = None, types = []):
		"""
		Return all events from the given account of the form {jid1: [], jid2:
		[]}. If jid is given, returns all events from the given jid in a list: []
		optionally only from given type
		"""
		if account not in self._events:
			return []
		if not jid:
			events_list = {} # list of events
			for jid_ in self._events[account]:
				events = []
				for ev in self._events[account][jid_]:
					if not types or ev.type_ in types:
						events.append(ev)
				if events:
					events_list[jid_] = events
			return events_list
		if jid not in self._events[account]:
			return []
		events_list = [] # list of events
		for ev in self._events[account][jid]:
			if not types or ev.type_ in types:
				events_list.append(ev)
		return events_list

	def get_first_event(self, account, jid = None, type_ = None):
		"""
		Return the first event of type type_ if given
		"""
		events_list = self.get_events(account, jid, type_)
		# be sure it's bigger than latest event
		first_event_time = time.time() + 1
		first_event = None
		for event in events_list:
			if event.time_ < first_event_time:
				first_event_time = event.time_
				first_event = event
		return first_event

	def _get_nb_events(self, account = None, jid = None, attribute = None, types
			= []):
		"""
		Return the number of pending events
		"""
		nb = 0
		if account:
			accounts = [account]
		else:
			accounts = self._events.keys()
		for acct in accounts:
			if acct not in self._events:
				continue
			if jid:
				jids = [jid]
			else:
				jids = self._events[acct].keys()
			for j in jids:
				if j not in self._events[acct]:
					continue
				for event in self._events[acct][j]:
					if types and event.type_ not in types:
						continue
					if not attribute or \
					attribute == 'systray' and event.show_in_systray or \
					attribute == 'roster' and event.show_in_roster:
						nb += 1
		return nb

	def _get_some_events(self, attribute):
		"""
		Attribute in systray, roster
		"""
		events = {}
		for account in self._events:
			events[account] = {}
			for jid in self._events[account]:
				events[account][jid] = []
				for event in self._events[account][jid]:
					if attribute == 'systray' and event.show_in_systray or \
					attribute == 'roster' and event.show_in_roster:
						events[account][jid].append(event)
				if not events[account][jid]:
					del events[account][jid]
			if not events[account]:
				del events[account]
		return events

	def _get_first_event_with_attribute(self, events):
		"""
		Get the first event

		events is in the form {account1: {jid1: [ev1, ev2], },. }
		"""
		# be sure it's bigger than latest event
		first_event_time = time.time() + 1
		first_account = None
		first_jid = None
		first_event = None
		for account in events:
			for jid in events[account]:
				for event in events[account][jid]:
					if event.time_ < first_event_time:
						first_event_time = event.time_
						first_account = account
						first_jid = jid
						first_event = event
		return first_account, first_jid, first_event

	def get_nb_systray_events(self, types = []):
		"""
		Return the number of events displayed in roster
		"""
		return self._get_nb_events(attribute = 'systray', types = types)

	def get_systray_events(self):
		"""
		Return all events that must be displayed in systray:
			{account1: {jid1: [ev1, ev2], },. }
		"""
		return self._get_some_events('systray')

	def get_first_systray_event(self):
		events = self.get_systray_events()
		return self._get_first_event_with_attribute(events)

	def get_nb_roster_events(self, account = None, jid = None, types = []):
		"""
		Return the number of events displayed in roster
		"""
		return self._get_nb_events(attribute = 'roster', account = account,
			jid = jid, types = types)

	def get_roster_events(self):
		"""
		Return all events that must be displayed in roster:
			{account1: {jid1: [ev1, ev2], },. }
		"""
		return self._get_some_events('roster')

# vim: se ts=3:
