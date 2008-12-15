##   client.py
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

'''
Provides PlugIn class functionality to develop extentions for xmpppy.
Also provides Client and Component classes implementations as the
examples of xmpppy structures usage.
These classes can be used for simple applications "AS IS" though.
'''

import logging
log = logging.getLogger('gajim.c.x.plugin')

class PlugIn:
	''' Common xmpppy plugins infrastructure: plugging in/out, debugging. '''
	def __init__(self):
		self._exported_methods=[]

	def PlugIn(self,owner):
		''' Attach to main instance and register ourself and all our staff in it. '''
		self._owner=owner
		log.info('Plugging %s __INTO__ %s' % (self,self._owner))
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

		# following commented line will not work for classes inheriting plugin()
		#if self.__class__.__dict__.has_key('plugin'): return self.plugin(owner)
		if hasattr(self,'plugin'): return self.plugin(owner)

	def PlugOut(self):
		''' Unregister all our staff from main instance and detach from it. '''
		log.info('Plugging %s __OUT__ of %s.' % (self, self._owner))
		for method in self._exported_methods: del self._owner.__dict__[method.__name__]
		for method in self._old_owners_methods: self._owner.__dict__[method.__name__]=method
		if self.__class__.__name__.endswith('Dispatcher'):
			del self._owner.__dict__['Dispatcher']
		else:
			del self._owner.__dict__[self.__class__.__name__]
		#if self.__class__.__dict__.has_key('plugout'): return self.plugout()
		if hasattr(self,'plugout'): return self.plugout()
		del self._owner

# vim: se ts=3:
