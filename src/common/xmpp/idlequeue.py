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
import logging
log = logging.getLogger('gajim.c.x.idlequeue')

class IdleObject:
	''' base class for all idle listeners, these are the methods, which are called from IdleQueue
	'''
	def __init__(self):
		self.fd = -1

	def pollend(self):
		''' called on stream failure '''
		pass

	def pollin(self):
		''' called on new read event '''
		pass

	def pollout(self):
		''' called on new write event (connect in sockets is a pollout) '''
		pass

	def read_timeout(self):
		''' called when timeout happened '''
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
		log.info('read timeout removed for fd %s' % fd)
		if fd in self.read_timeouts:
			del(self.read_timeouts[fd])

	def set_alarm(self, alarm_cb, seconds):
		''' set up a new alarm, to be called after alarm_cb sec. '''
		alarm_time = self.current_time() + seconds
		# almost impossible, but in case we have another alarm_cb at this time
		if alarm_time in self.alarms:
			self.alarms[alarm_time].append(alarm_cb)
		else:
			self.alarms[alarm_time] = [alarm_cb]
		return alarm_time

	def remove_alarm(self, alarm_cb, alarm_time): 
		''' removes alarm callback alarm_cb scheduled on alarm_time''' 
		if not self.alarms.has_key(alarm_time): return False 
		i = -1 
		for i in range(len(self.alarms[alarm_time])): 
			# let's not modify the list inside the loop 
			if self.alarms[alarm_time][i] is alarm_cb: break 
		if i != -1: 
			del self.alarms[alarm_time][i] 
			if self.alarms[alarm_time] == []: 
				del self.alarms[alarm_time] 
			return True 
		else: 
			return False

	def set_read_timeout(self, fd, seconds):
		''' set a new timeout, if it is not removed after 'seconds',
		then obj.read_timeout() will be called '''
		log.info('read timeout set for fd %s on %s seconds' % (fd, seconds))
		timeout = self.current_time() + seconds
		self.read_timeouts[fd] = timeout

	def check_time_events(self):
		log.info('check time evs')
		current_time = self.current_time()
		for fd, timeout in self.read_timeouts.items():
			if timeout > current_time:
				continue
			if fd in self.queue:
				log.debug('Calling read_timeout for fd %s' % fd) 
				self.queue[fd].read_timeout()
			else:
				self.remove_timeout(fd)
		times = self.alarms.keys()
		for alarm_time in times:
			if alarm_time > current_time:
				break
			if self.alarms.has_key(alarm_time):
				for cb in self.alarms[alarm_time]: cb()
				if self.alarms.has_key(alarm_time): del(self.alarms[alarm_time])

	def plug_idle(self, obj, writable = True, readable = True):
		if obj.fd == -1:
			return
		if obj.fd in self.queue:
			self.unplug_idle(obj.fd)
		self.queue[obj.fd] = obj
		if writable:
			if not readable:
				flags = 20 # write only
			else:
				flags = 23 # both readable and writable
		else:
			if readable:
				flags = 19 # read only
			else:
				# when we paused a FT, we expect only a close event
				flags = 16
		self.add_idle(obj.fd, flags)

	def add_idle(self, fd, flags):
		self.selector.register(fd, flags)

	def unplug_idle(self, fd):
		if fd in self.queue:
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
			#print 'waiting read on %d, flags are %d' % (fd, flags)
			obj.pollin()
			return True

		elif flags & 4: # waiting write event
			obj.pollout()
			return True

		elif flags & 16: # closed channel
			# io error, don't expect more events
			self.remove_timeout(obj.fd)
			self.unplug_idle(obj.fd)
			obj.pollend()
		return False

	def process(self):
		if not self.queue:
			# check for timeouts/alert also when there are no active fds
			self.check_time_events()
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

class SelectIdleQueue(IdleQueue):
	'''
	Extends IdleQueue to use select.select() for polling
	This class exisists for the sake of gtk2.8 on windows, which
	doesn't seem to support io_add_watch properly (yet)
	'''
	# TODO: remove this class and its reference gajim.py, when win-gtk2.8 is stable
	def init_idle(self):
		''' this method is called at the end of class constructor.
		Creates a dict, which maps file/pipe/sock descriptor to glib event id'''
		self.read_fds = {}
		self.write_fds = {}
		self.error_fds = {}

	def add_idle(self, fd, flags):
		''' this method is called when we plug a new idle object.
		Remove descriptor to read/write/error lists, according flags
		'''
		if flags & 3:
			self.read_fds[fd] = fd
		if flags & 4:
			self.write_fds[fd] = fd
		self.error_fds[fd] = fd

	def remove_idle(self, fd):
		''' this method is called when we unplug a new idle object.
		Remove descriptor from read/write/error lists
		'''
		if fd in self.read_fds:
			del(self.read_fds[fd])
		if fd in self.write_fds:
			del(self.write_fds[fd])
		if fd in self.error_fds:
			del(self.error_fds[fd])

	def process(self):
		if not self.write_fds and not self.read_fds:
			self.check_time_events()
			return True
		try:
			waiting_descriptors = select.select(self.read_fds.keys(),
				self.write_fds.keys(), self.error_fds.keys(), 0)
		except select.error, e:
			waiting_descriptors = ((),(),())
			if e[0] != 4: # interrupt
				raise
		for fd in waiting_descriptors[0]:
			q = self.queue.get(fd)
			if q:
				q.pollin()
		for fd in waiting_descriptors[1]:
			q = self.queue.get(fd)
			if q:
				q.pollout()
		for fd in waiting_descriptors[2]:
			q = self.queue.get(fd)
			if q:
				q.pollend()
		self.check_time_events()
		return True

# vim: se ts=3:
