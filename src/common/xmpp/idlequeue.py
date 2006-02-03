##   idlequeue.py
##
##   Copyright (C) 2006 Dimitur Kirov <dkirov@gmail.com>
##
##   This program is free software; you can redistribute it and/or modify
##   it under the terms of the GNU General Public License as published by
##   the Free Software Foundation; either version 2, or (at your option)
##   any later version.
##
##   This program is distributed in the hope that it will be useful,
##   but WITHOUT ANY WARRANTY; without even the implied warranty of
##   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
##   GNU General Public License for more details.

import select

class IdleObject:
	''' base class for all idle listeners, these are the methods, which are called from IdleQueue
	'''
	def __init__(self):
		self.fd = -1
		pass
	
	def pollend(self):
		''' called on stream failure '''
		pass
	
	def pollin(self):
		''' called on new read event '''
		pass
	
	def pollout(self):
		''' called on new write event (connect in sockets is a pollout) '''
		pass
	
	def read_timeout(self, fd):
		''' called when timeout has happend '''
		pass
		
class IdleQueue:
	def __init__(self):
		self.queue = {}
		
		# when there is a timeout it executes obj.read_timeout()
		# timeout is not removed automatically!
		self.read_timeouts = {}
		
		# cb, which are executed after XX sec., alarms are removed automatically
		self.alarms = {}
		self.init_idle()
	
	def init_idle(self):
		self.selector = select.poll()
	
	def remove_timeout(self, fd):
		''' self explanatory, remove the timeout from 'read_timeouts' dict  '''
		if self.read_timeouts.has_key(fd):
			del(self.read_timeouts[fd])
	
	def set_alarm(self, alarm_cb, seconds):
		''' set up a new alarm, to be called after alarm_cb sec. '''
		alarm_time = self.current_time() + seconds
		# almost impossible, but in case we have another alarm_cb at this time
		if self.alarms.has_key(alarm_time):
			self.alarms[alarm_time].append(alarm_cb)
		else:
			self.alarms[alarm_time] = [alarm_cb]
	
	def set_read_timeout(self, fd, seconds):
		''' set a new timeout, if it is not removed after 'seconds', 
		then obj.read_timeout() will be called '''
		timeout = self.current_time() + seconds
		self.read_timeouts[fd] = timeout
	
	def check_time_events(self):
		current_time = self.current_time()
		for fd, timeout in self.read_timeouts.items():
			if timeout > current_time:
				continue
			if self.queue.has_key(fd):
				self.queue[fd].read_timeout()
			else:
				self.remove_timeout(fd)
		times = self.alarms.keys()
		for alarm_time in times:
			if alarm_time > current_time:
				break
			for cb in self.alarms[alarm_time]:
				cb()
			del(self.alarms[alarm_time])
		
	def plug_idle(self, obj, writable = True, readable = True):
		if self.queue.has_key(obj.fd):
			self.unplug_idle(obj.fd)
		self.queue[obj.fd] = obj
		if writable:
			if not readable:
				flags = 4 # read only
			else:
				flags = 7 # both readable and writable
		else:
			flags = 3 # write only
		flags |= 16 # hung up, closed channel
		self.add_idle(obj.fd, flags)
	
	def add_idle(self, fd, flags):
		self.selector.register(fd, flags)
	
	def unplug_idle(self, fd):
		if self.queue.has_key(fd):
			del(self.queue[fd])
			self.remove_idle(fd)
	
	def current_time(self):
		from time import time
		return time()
	
	def remove_idle(self, fd):
		self.selector.unregister(fd)
	
	def process_events(self, fd, flags):
		obj = self.queue.get(fd)
		if obj is None:
			self.unplug_idle(fd)
			return False
		
		if flags & 3: # waiting read event
			obj.pollin()
			return True
		
		elif flags & 4: # waiting write event
			obj.pollout()
			return True
		
		elif flags & 16: # closed channel
			obj.pollend()
		return False
	
	def process(self):
		if not self.queue:
			return True
		try:
			waiting_descriptors = self.selector.poll(0)
		except select.error, e:
			waiting_descriptors = []
			if e[0] != 4: # interrupt
				raise
		for fd, flags in waiting_descriptors:
			self.process_events(fd, flags)
		self.check_time_events()
		return True
