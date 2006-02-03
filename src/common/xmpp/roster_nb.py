##   roster_nb.py
##       based on roster.py
##
##   Copyright (C) 2003-2005 Alexey "Snake" Nezhdanov
##       modified by Dimitur Kirov <dkirov@gmail.com>
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

# $Id: roster.py,v 1.17 2005/05/02 08:38:49 snakeru Exp $

'''
Simple roster implementation. Can be used though for different tasks like
mass-renaming of contacts.
'''

from roster import Roster
from protocol import NS_ROSTER

class NonBlockingRoster(Roster):
	def plugin(self, owner, request=1):
		''' Register presence and subscription trackers in the owner's dispatcher.
			Also request roster from server if the 'request' argument is set.
			Used internally.'''
		self._owner.RegisterHandler('iq', self.RosterIqHandler, 'result', NS_ROSTER, makefirst = 1)
		self._owner.RegisterHandler('iq', self.RosterIqHandler, 'set', NS_ROSTER)
		self._owner.RegisterHandler('presence', self.PresenceHandler)
		if request: 
			self.Request()
	
	def _on_roster_set(self, data):
		if data:
			self._owner.Dispatcher.ProcessNonBlocking(data)
		if not self.set: 
			return 
		self._owner.onreceive(None)
		if self.on_ready:
			self.on_ready(self)
			self.on_ready = None
		return True
		
	def getRoster(self, on_ready=None):
		''' Requests roster from server if neccessary and returns self. '''
		if not self.set: 
			self.on_ready = on_ready
			self._owner.onreceive(self._on_roster_set)
			return
		if on_ready:
			on_ready(self)
			on_ready = None
		else:
			return self
