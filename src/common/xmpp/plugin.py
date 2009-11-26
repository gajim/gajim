##   plugin.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
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

# $Id: client.py,v 1.52 2006/01/02 19:40:55 normanr Exp $

"""
Provides PlugIn class functionality to develop extentions for xmpppy
"""

import logging
log = logging.getLogger('gajim.c.x.plugin')

class PlugIn:
	"""
	Abstract xmpppy plugin infrastructure code, providing plugging in/out and
	debugging functionality

	Inherit to develop pluggable objects. No code change on the owner class
	required (the object where we plug into)

	For every instance of PlugIn class the 'owner' is the class in what the plug
	was plugged.
	"""

	def __init__(self):
		self._exported_methods=[]

	def PlugIn(self, owner):
		"""
		Attach to owner and register ourself and our _exported_methods in it.
		If defined by a subclass, call self.plugin(owner) to execute hook
		code after plugging
		"""
		self._owner=owner
		log.info('Plugging %s __INTO__ %s' % (self, self._owner))
		if self.__class__.__name__ in owner.__dict__:
			log.debug('Plugging ignored: another instance already plugged.')
			return
		self._old_owners_methods=[]
		for method in self._exported_methods:
			if method.__name__ in owner.__dict__:
				self._old_owners_methods.append(owner.__dict__[method.__name__])
			owner.__dict__[method.__name__]=method
		if self.__class__.__name__.endswith('Dispatcher'):
			# FIXME: I need BOSHDispatcher or XMPPDispatcher on .Dispatcher
			# there must be a better way..
			owner.__dict__['Dispatcher']=self
		else:
			owner.__dict__[self.__class__.__name__]=self

		# Execute hook
		if hasattr(self,'plugin'):
			return self.plugin(owner)

	def PlugOut(self):
		"""
		Unregister our _exported_methods from owner and detach from it.
		If defined by a subclass, call self.plugout() after unplugging to execute
		hook code
		"""
		log.info('Plugging %s __OUT__ of %s.' % (self, self._owner))
		for method in self._exported_methods:
			del self._owner.__dict__[method.__name__]
		for method in self._old_owners_methods:
			self._owner.__dict__[method.__name__]=method
		# FIXME: Dispatcher workaround
		if self.__class__.__name__.endswith('Dispatcher'):
			del self._owner.__dict__['Dispatcher']
		else:
			del self._owner.__dict__[self.__class__.__name__]
		# Execute hook
		if hasattr(self,'plugout'):
			return self.plugout()
		del self._owner

	@classmethod
	def get_instance(cls, *args, **kwargs):
		"""
		Factory Method for object creation

		Use this instead of directly initializing the class in order to make
		unit testing easier. For testing, this method can be patched to inject
		mock objects.
		"""
		return cls(*args, **kwargs)

# vim: se ts=3:
