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
Plug-in management related classes.

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

from plugins.helpers import log, log_calls, Singleton
from plugins.plugin import GajimPlugin

class PluginManager(object):
	'''
	Main plug-in management class.
	
	Currently: 
		- scans for plugins
		- activates them
		- handles GUI extension points, when called by GUI objects after plugin 
		  is activated (by dispatching info about call to handlers in plugins)
	
	:todo: add more info about how GUI extension points work
	:todo: add list of available GUI extension points
	:todo: implement mechanism to dynamically load plugins where GUI extension
		   points have been already called (i.e. when plugin is activated
		   after GUI object creation). [DONE?]
	:todo: implement mechanism to dynamically deactive plugins (call plugin's
		   deactivation handler) [DONE?]
	:todo: when plug-in is deactivated all GUI extension points are removed
		   from `PluginManager.gui_extension_points_handlers`. But when
		   object that invoked GUI extension point is abandoned by Gajim, eg.
		   closed ChatControl object, the reference to called GUI extension
		   points is still in `PluginManager.gui_extension_points`. These
		   should be removed, so that object can be destroyed by Python.
		   Possible solution: add call to clean up method in classes
		   'destructors' (classes that register GUI extension points)
	'''
	
	__metaclass__ = Singleton

	#@log_calls('PluginManager')
	def __init__(self):
		self.plugins = []
		'''
		Detected plugin classes.
		
		Each class object in list is `GajimPlugin` subclass.
		
		:type: [] of class objects
		'''
		self.active_plugins = []
		'''
		Instance objects of active plugins.
		
		These are object instances of classes held `plugins`, but only those
		that were activated.
		
		:type: [] of `GajimPlugin` based objects
		'''
		self.gui_extension_points = {}
		'''
		Registered GUI extension points.
		'''
		
		self.gui_extension_points_handlers = {}
		'''
		Registered handlers of GUI extension points.
		'''

		for path in gajim.PLUGINS_DIRS:
			self._add_plugins(PluginManager.scan_dir_for_plugins(path))

		log.debug('plugins: %s'%(self.plugins))

		self.activate_all_plugins()

		log.debug('active: %s'%(self.active_plugins))

		
	@log_calls('PluginManager')
	def _add_plugin(self, plugin_class):
		'''
		:todo: what about adding plug-ins that are already added? Module reload
		and adding class from reloaded module or ignoring adding plug-in?
		'''
		plugin_class._active = False
		plugin_class._instance = None
		self.plugins.append(plugin_class)
	
	@log_calls('PluginManager')
	def _add_plugins(self, plugin_classes):
		for plugin_class in plugin_classes:
			self._add_plugin(plugin_class)
		
	@log_calls('PluginManager')
	def gui_extension_point(self, gui_extpoint_name, *args):
		'''
		Invokes all handlers (from plugins) for particular GUI extension point.
		
		:param gui_extpoint_name: name of GUI extension point.
		:type gui_extpoint_name: unicode
		:param args: parameters to be passed to extension point handlers 
			(typically and object that invokes `gui_extension_point`; however, 
			this can be practically anything)
		:type args: tuple

		:todo: GUI extension points must be documented well - names with
			parameters that will be passed to handlers (in plugins). Such
			documentation must be obeyed both in core and in plugins. This
			is a loosely coupled approach and is pretty natural in Python.
			   
		:bug: what if only some handlers are successfully connected? we should
			revert all those connections that where successfully made. Maybe
			call 'self._deactivate_plugin()' or sth similar.
			Looking closer - we only rewrite tuples here. Real check should be
			made in method that invokes gui_extpoints handlers.
		'''

		self._add_gui_extension_point_call_to_list(gui_extpoint_name, *args)
		self._execute_all_handlers_of_gui_extension_point(gui_extpoint_name, *args)
				
	@log_calls('PluginManager')
	def _add_gui_extension_point_call_to_list(self, gui_extpoint_name, *args):
		self.gui_extension_points.setdefault(gui_extpoint_name, []).append(args)
	
	@log_calls('PluginManager')
	def _execute_all_handlers_of_gui_extension_point(self, gui_extpoint_name, *args):
		if gui_extpoint_name in self.gui_extension_points_handlers:
			for handlers in self.gui_extension_points_handlers[gui_extpoint_name]:
				handlers[0](*args)

	@log_calls('PluginManager')
	def activate_plugin(self, plugin_class):
		'''
		:param plugin: plugin to be activated
		:type plugin: class object of `GajimPlugin` subclass
		'''
		
		plugin_object = plugin_class()

		success = True

		self._add_gui_extension_points_handlers_from_plugin(plugin_object)
		self._handle_all_gui_extension_points_with_plugin(plugin_object)

		if success:
			self.active_plugins.append(plugin_object)
			plugin_class._instance = plugin_object
			plugin_class._active = True

		return success
	
	def deactivate_plugin(self, plugin_object):
		# detaching plug-in from handler GUI extension points (calling
		# cleaning up method that must be provided by plug-in developer
		# for each handled GUI extension point)
		for gui_extpoint_name, gui_extpoint_handlers in \
				plugin_object.gui_extension_points.iteritems():
			if gui_extpoint_name in self.gui_extension_points:
				for gui_extension_point_args in self.gui_extension_points[gui_extpoint_name]:
					gui_extpoint_handlers[1](*gui_extension_point_args)
				
		# remove GUI extension points handlers (provided by plug-in) from
		# handlers list
		for gui_extpoint_name, gui_extpoint_handlers in \
				plugin_object.gui_extension_points.iteritems():
			self.gui_extension_points_handlers[gui_extpoint_name].remove(gui_extpoint_handlers)
			
		# removing plug-in from active plug-ins list
		self.active_plugins.remove(plugin_object)
		plugin_object.__class__._active = False
		del plugin_object
		
	def deactivate_all_plugins(self):
		for plugin_object in self.active_plugins:
			self.deactivate_plugin(plugin_object)
	
	@log_calls('PluginManager')
	def _add_gui_extension_points_handlers_from_plugin(self, plugin_object):
		for gui_extpoint_name, gui_extpoint_handlers in \
				plugin_object.gui_extension_points.iteritems():
			self.gui_extension_points_handlers.setdefault(gui_extpoint_name, []).append(
					gui_extpoint_handlers)
	
	@log_calls('PluginManager')
	def _handle_all_gui_extension_points_with_plugin(self, plugin_object):
		for gui_extpoint_name, gui_extpoint_handlers in \
				plugin_object.gui_extension_points.iteritems():
			if gui_extpoint_name in self.gui_extension_points:
				for gui_extension_point_args in self.gui_extension_points[gui_extpoint_name]:
					gui_extpoint_handlers[0](*gui_extension_point_args)

	@log_calls('PluginManager')
	def activate_all_plugins(self):
		'''
		Activates all plugins in `plugins`.
		
		Activated plugins are appended to `active_plugins` list.
		'''
		self.active_plugins = []
		for plugin in self.plugins:
			self.activate_plugin(plugin)

	@staticmethod
	@log_calls('PluginManager')
	def scan_dir_for_plugins(path):
		'''
		Scans given directory for plugin classes.
		
		:param path: directory to scan for plugins
		:type path: unicode
		
		:return: list of found plugin classes (subclasses of `GajimPlugin`
		:rtype: [] of class objects
		
		:note: currently it only searches for plugin classes in '\*.py' files
			present in given direcotory `path` (no recursion here)
		
		:todo: add scanning packages
		:todo: add scanning zipped modules
		'''
		plugins_found = []
		if os.path.isdir(path):
			dir_list = os.listdir(path)
			log.debug(dir_list)

			sys.path.insert(0, path)
			log.debug(sys.path)

			for file_name in fnmatch.filter(dir_list, '*.py'):
				log.debug('- "%s"'%(file_name))
				file_path = os.path.join(path, file_name)
				log.debug('  "%s"'%(file_path))
				if os.path.isfile(file_path):
					module_name = os.path.splitext(file_name)[0]
					module = __import__(module_name)
					for module_attr_name in [f_name for f_name in dir(module) 
								if not (f_name.startswith('__') or 
										f_name.endswith('__'))]:
						module_attr = getattr(module, module_attr_name)
						log.debug('%s : %s'%(module_attr_name, module_attr))

						try:
							if issubclass(module_attr, GajimPlugin) and \
							   not module_attr is GajimPlugin:
								log.debug('is subclass of GajimPlugin')
								plugins_found.append(module_attr)
						except TypeError, type_error:
							log.debug('module_attr: %s, error : %s'%(
								module_name+'.'+module_attr_name,
								type_error))

					log.debug(module)

		return plugins_found