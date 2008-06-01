# -*- coding: utf-8 -*-

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
Helper code related to plug-ins management system.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 05/30/2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

__all__ = ['PluginManager']

import os
import sys
import fnmatch

import common.gajim as gajim

from helpers import log, log_calls, Singleton
from plugin import GajimPlugin

class PluginManager(object):
	__metaclass__ = Singleton

	@log_calls('PluginManager')
	def __init__(self):
		self.plugins = []
		self.active = []
		self.gui_extension_points = {}

		for path in gajim.PLUGINS_DIRS:
			self.plugins.extend(self._scan_dir_for_plugins(path))

		log.debug('plugins: %s'%(self.plugins))
		
		self._activate_all_plugins()
		
		log.debug('active: %s'%(self.active))
	
	@log_calls('PluginManager')
	def gui_extension_point(self, gui_extpoint_name, *args):
		if gui_extpoint_name in self.gui_extension_points:
			for handlers in self.gui_extension_points[gui_extpoint_name]:
				handlers[0](*args)

	@log_calls('PluginManager')
	def _activate_plugin(self, plugin):
		'''
		:param plugin: Plugin to be activated.
		:type plugin: class object of GajimPlugin subclass
		'''
		p = plugin()
		
		success = True
		
		# :fix: what if only some handlers are successfully connected? we should
		# revert all those connections that where successfully made. Maybe
		# call 'self._deactivate_plugin()' or sth similar.
		# Looking closer - we only rewrite tuples here. Real check should be
		# made in method that invokes gui_extpoints handlers.
		for gui_extpoint_name, gui_extpoint_handlers in \
				p.gui_extension_points.iteritems():
			self.gui_extension_points.setdefault(gui_extpoint_name,[]).append(
					gui_extpoint_handlers)
			
		if success:
			self.active.append(p)
			
		return success
		
	@log_calls('PluginManager')
	def _activate_all_plugins(self):
		self.active = []
		for plugin in self.plugins:
			self._activate_plugin(plugin)

	@log_calls('PluginManager')
	def _scan_dir_for_plugins(self, path):
		plugins_found = []
		if os.path.isdir(path):
			dir_list = os.listdir(path)
			log.debug(dir_list)

			sys.path.insert(0, path)
			log.debug(sys.path)

			for file in fnmatch.filter(dir_list, '*.py'):
				log.debug('- "%s"'%(file))
				file_path = os.path.join(path, file)
				log.debug('  "%s"'%(file_path))
				if os.path.isfile(file_path):
					module_name = os.path.splitext(file)[0]
					module = __import__(module_name)
					filter_out_bad_names = \
										 lambda x: not (x.startswith('__') or 
														x.endswith('__'))
					for module_attr_name in filter(filter_out_bad_names,
												   dir(module)):
						module_attr = getattr(module, module_attr_name)
						log.debug('%s : %s'%(module_attr_name, module_attr))
						
						try:
							if issubclass(module_attr, GajimPlugin) and \
									not module_attr is GajimPlugin:
								log.debug('is subclass of GajimPlugin')
								plugins_found.append(module_attr)
						except TypeError, e:
							log.debug('module_attr: %s, error : %s'%(
									module_name+'.'+module_attr_name,
									e))

					log.debug(module)

		return plugins_found