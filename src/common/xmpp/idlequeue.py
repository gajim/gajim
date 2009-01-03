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

''' 
Idlequeues are Gajim's network heartbeat. Transports can be plugged as 
idle objects and be informed about possible IO.
'''

import select
import logging
import gobject
log = logging.getLogger('gajim.c.x.idlequeue')

FLAG_WRITE 			= 20 # write only
FLAG_READ 			= 19 # read only 
FLAG_READ_WRITE 	= 23 # read and write
FLAG_CLOSE 			= 16 # wait for close

PENDING_READ		= 3 # waiting read event
PENDING_WRITE 		= 4 # waiting write event
IS_CLOSED			= 16 # channel closed 


class IdleObject:
	'''
		Idle listener interface. Listed methods are called by IdleQueue.
	'''
	def __init__(self):
		self.fd = -1 #: filedescriptor, must be unique for each IdleObject

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
	'''
	IdleQueue provide three distinct time based features. Uses select.poll()
	
		1. Alarm timeout: Execute a callback after foo seconds
		2. Timeout event: Call read_timeout() of an plugged object if a timeout 
		has been set, but not removed in time.
		3. Check file descriptor of plugged objects for read, write and error
		events 
	'''
	def __init__(self):
		self.queue = {}

		# when there is a timeout it executes obj.read_timeout()
		# timeout is not removed automatically!
		self.read_timeouts = {}

		# cb, which are executed after XX sec., alarms are removed automatically
		self.alarms = {}
		self._init_idle()

	def _init_idle(self):
		''' Hook method for subclassed. Will be called by __init__. '''
		self.selector = select.poll()

	def set_alarm(self, alarm_cb, seconds):
		''' 
		Sets up a new alarm. alarm_cb will be called after specified seconds.
		'''
		alarm_time = self.current_time() + seconds
		# almost impossible, but in case we have another alarm_cb at this time
		if alarm_time in self.alarms:
			self.alarms[alarm_time].append(alarm_cb)
		else:
			self.alarms[alarm_time] = [alarm_cb]
		return alarm_time

	def remove_alarm(self, alarm_cb, alarm_time): 
		'''
		Removes alarm callback alarm_cb scheduled on alarm_time.
		Returns True if it was removed sucessfully, otherwise False
		''' 
		if not alarm_time in self.alarms:
			return False 
		i = -1 
		for i in range(len(self.alarms[alarm_time])):
			# let's not modify the list inside the loop 
			if self.alarms[alarm_time][i] is alarm_cb:
				break 
		if i != -1:
			del self.alarms[alarm_time][i] 
			if self.alarms[alarm_time] == []:
				del self.alarms[alarm_time] 
			return True 
		else: 
			return False

	def remove_timeout(self, fd):
		''' Removes the read timeout '''
		log.info('read timeout removed for fd %s' % fd)
		if fd in self.read_timeouts:
			del(self.read_timeouts[fd])

	def set_read_timeout(self, fd, seconds):
		'''
		Sets a new timeout. If it is not removed after specified seconds,
		obj.read_timeout() will be called.

		A filedescriptor fd can have only one timeout.
		'''
		log.info('read timeout set for fd %s on %s seconds' % (fd, seconds))
		timeout = self.current_time() + seconds
		self.read_timeouts[fd] = timeout

	def _check_time_events(self):
		'''
		Execute and remove alarm callbacks and execute read_timeout() for plugged
		objects if specified time has ellapsed.
		'''
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
				continue
			if alarm_time in self.alarms:
				for callback in self.alarms[alarm_time]:
					callback()
				if alarm_time in self.alarms:
					del(self.alarms[alarm_time])

	def plug_idle(self, obj, writable=True, readable=True):
		'''
		Plug an IdleObject into idlequeue. Filedescriptor fd must be set. 

		:param obj: the IdleObject
		:param writable: True if obj has data to sent
		:param readable: True if obj expects data to be reiceived
		'''
		if obj.fd == -1:
			return
		if obj.fd in self.queue:
			self.unplug_idle(obj.fd)
		self.queue[obj.fd] = obj
		if writable:
			if not readable:
				flags = FLAG_WRITE
			else:
				flags = FLAG_READ_WRITE
		else:
			if readable:
				flags = FLAG_READ
			else:
				# when we paused a FT, we expect only a close event
				flags = FLAG_CLOSE
		self._add_idle(obj.fd, flags)

	def _add_idle(self, fd, flags):
		''' Hook method for subclasses, called by plug_idle '''
		self.selector.register(fd, flags)

	def unplug_idle(self, fd):
		''' Removed plugged IdleObject, specified by filedescriptor fd.  '''
		if fd in self.queue:
			del(self.queue[fd])
			self._remove_idle(fd)

	def current_time(self):
		from time import time
		return time()

	def _remove_idle(self, fd):
		''' Hook method for subclassed, called by unplug_idle '''
		self.selector.unregister(fd)

	def _process_events(self, fd, flags):
		obj = self.queue.get(fd)
		if obj is None:
			self.unplug_idle(fd)
			return False

		if flags & PENDING_READ:
			#print 'waiting read on %d, flags are %d' % (fd, flags)
			obj.pollin()
			return True

		elif flags & PENDING_WRITE:
			obj.pollout()
			return True

		elif flags & IS_CLOSED: 
			# io error, don't expect more events
			self.remove_timeout(obj.fd)
			self.unplug_idle(obj.fd)
			obj.pollend()
		return False

	def process(self):
		'''
		Process idlequeue. Check for any pending timeout or alarm events.
		Call IdleObjects on possible and requested read, write and error events
		on their file descriptors.

		Call this in regular intervals.
		'''
		if not self.queue:
			# check for timeouts/alert also when there are no active fds
			self._check_time_events()
			return True
		try:
			waiting_descriptors = self.selector.poll(0)
		except select.error, e:
			waiting_descriptors = []
			if e[0] != 4: # interrupt
				raise
		for fd, flags in waiting_descriptors:
			self._process_events(fd, flags)
		self._check_time_events()
		return True


class SelectIdleQueue(IdleQueue):
	'''
	Extends IdleQueue to use select.select() for polling

	This class exisists for the sake of gtk2.8 on windows, which
	doesn't seem to support io_add_watch properly (yet)
	'''
	def _init_idle(self):
		'''
		Creates a dict, which maps file/pipe/sock descriptor to glib event id
		'''
		self.read_fds = {}
		self.write_fds = {}
		self.error_fds = {}

	def _add_idle(self, fd, flags):
		''' this method is called when we plug a new idle object.
		Remove descriptor to read/write/error lists, according flags
		'''
		if flags & 3:
			self.read_fds[fd] = fd
		if flags & 4:
			self.write_fds[fd] = fd
		self.error_fds[fd] = fd

	def _remove_idle(self, fd):
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
			self._check_time_events()
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
		self._check_time_events()
		return True


class GlibIdleQueue(IdleQueue):
	'''
	Extends IdleQueue to use glib io_add_wath, instead of select/poll
	In another 'non gui' implementation of Gajim IdleQueue can be used safetly.
	'''

	def _init_idle(self):
		'''
		Creates a dict, which maps file/pipe/sock descriptor to glib event id
		'''
		self.events = {}
		# time() is already called in glib, we just get the last value
		# overrides IdleQueue.current_time()
		self.current_time = gobject.get_current_time

	def _add_idle(self, fd, flags):
		''' this method is called when we plug a new idle object.
		Start listening for events from fd
		'''
		res = gobject.io_add_watch(fd, flags, self._process_events,
			priority=gobject.PRIORITY_LOW)
		# store the id of the watch, so that we can remove it on unplug
		self.events[fd] = res

	def _process_events(self, fd, flags):
		try:
			return IdleQueue._process_events(self, fd, flags)
		except Exception:
			self._remove_idle(fd)
			self._add_idle(fd, flags)
			raise

	def _remove_idle(self, fd):
		''' this method is called when we unplug a new idle object.
		Stop listening for events from fd
		'''
		if not fd in self.events:
			return
		gobject.source_remove(self.events[fd])
		del(self.events[fd])

	def process(self):
		self._check_time_events()


# vim: se ts=3:
