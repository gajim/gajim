# -*- coding: utf-8 -*-
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim.  If not, see <http://www.gnu.org/licenses/>.
##
'''
Events Dump plugin.

Dumps info about selected events to console. 

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 10th August 2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

import new
from pprint import pformat

from plugins import GajimPlugin
from plugins.helpers import log_calls, log
from common import ged

class EventsDumpPlugin(GajimPlugin):
	name = u'Events Dump'
	short_name = u'events_dump'
	version = u'0.1'
	description = u'''Dumps info about selected events to console.'''
	authors = [u'Mateusz Biliński <mateusz@bilinski.it>']
	homepage = u'http://blog.bilinski.it'
	
	@log_calls('DBusPlugin')
	def init(self):
		self.config_dialog = None
		#self.gui_extension_points = {}
		#self.config_default_values = {}
		
		self.events_names = ['Roster', 'AccountPresence', 'ContactPresence',
							 'ContactAbsence', 'ContactStatus', 'NewMessage',
							 'Subscribe', 'Subscribed', 'Unsubscribed',
							 'NewAccount', 'VcardInfo', 'LastStatusTime',
							 'OsInfo', 'GCPresence', 'GCMessage', 'RosterInfo',
							 'NewGmail']
		
		self.events_handlers = {}
		self._set_handling_methods()
		
		
	def activate(self):
		pass
		
	def deactivate(self):
		pass

	def _set_handling_methods(self):
		for event_name in self.events_names:
			setattr(self, event_name, 
					new.instancemethod(
						self._generate_handling_method(event_name), 
						self, 
						EventsDumpPlugin))
			self.events_handlers[event_name] = (ged.POSTCORE,
											   getattr(self, event_name))
	
	def _generate_handling_method(self, event_name):
		def handler(self, *args):
			print "Event '%s' occured. Arguments: %s"%(event_name, pformat(*args))
		
		return handler