#!/usr/bin/env python
##	common/hub.py
##
## Gajim Team:
## 	- Yann Le Boulanger <asterix@crans.org>
## 	- Vincent Hanquez <tab@snarc.org>
##
##	Copyright (C) 2003 Gajim Team
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

import Queue
import common.plugin
import common.thread

""" Hub definitions """

class GajimHub:
	def __init__(self):
		self.queues = {}
		# {event1:[queue1, queue2]}
		self.events = {}
		self.queueIn = self.newQueue('in', 100)
	# END __init__

	def newQueue(self, name, size):
		""" Creates a new queue """
		qu = Queue.Queue(size)
		self.queues[name] = qu
		return qu
	# END newQueue

	def newPlugin(self, name):
		"""Creates a new Plugin """
		if name in self.queues.keys():
			return 0
		qu = self.newQueue(name, 100)
		pl = common.plugin.GajimPlugin(name, qu, self.queueIn)
		return pl
	# END newPlugin

	def register(self, name, event):
		""" Records a plugin from an event """
		if not self.queues.has_key(name):
			return
		qu = self.queues[name]
		if self.events.has_key(event) :
			if not qu in self.events[event]:
				self.events[event].append(qu)
		else :
			self.events[event] = [qu]
	# END register

	def unregisterEvents(self, name, event):
		""" Records a plugin from an event """
		if not self.queues.has_key(name):
			return
		qu = self.queues[name]
		if self.events.has_key(event) :
			if qu in self.events[event]:
				self.events[event].remove(qu)
	# END register

	def unregister(self, name):
		if not self.queues.has_key(name):
			return
		qu = self.queues[name]
		for event in self.events:
			if qu in self.events[event]:
				self.events[event].remove(qu)
		del self.queues[name]
	# END unregister

	def sendPlugin(self, event, con, data, qu=None):
		""" Sends an event to registered plugins"""
		if self.events.has_key(event):
			for queue in self.events[event]:
				if qu == None or qu == queue:
					queue.put((event, con, data))
	# END sendPlugin
# END GajimHub
