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
GUI classes related to plug-in management.

:author: Mateusz Biliński <mateusz@bilinski.it>
:since: 06/06/2008
:copyright: Copyright (2008) Mateusz Biliński <mateusz@bilinski.it>
:license: GPL
'''

__all__ = ['PluginsWindow']

import pango
import gtk, gobject

import gtkgui_helpers
from common import gajim

from plugins.helpers import log_calls, log

class PluginsWindow(object):
	'''Class for Plugins window'''

	@log_calls('PluginsWindow')
	def __init__(self):
		'''Initialize Plugins window'''
		self.xml = gtkgui_helpers.get_glade('plugins_window.glade')
		self.window = self.xml.get_widget('plugins_window')
		self.window.set_transient_for(gajim.interface.roster.window)
		
		widgets_to_extract = ('plugins_notebook',
							 'plugin_name_label',
							 'plugin_version_label',
							 'plugin_authors_label',
							 'plugin_homepage_linkbutton',
							 'plugin_description_textview',
							 'uninstall_plugin_button',
							 'configure_plugin_button',
							 'installed_plugins_treeview')
		
		for widget_name in widgets_to_extract:
			setattr(self, widget_name, self.xml.get_widget(widget_name))

		attr_list = pango.AttrList()
		attr_list.insert(pango.AttrWeight(pango.WEIGHT_BOLD, 0, -1))
		self.plugin_name_label.set_attributes(attr_list)
		
		self.installed_plugins_model = gtk.ListStore(gobject.TYPE_PYOBJECT,
													 gobject.TYPE_STRING, 
													 gobject.TYPE_BOOLEAN)
		self.installed_plugins_treeview.set_model(self.installed_plugins_model)
		
		renderer = gtk.CellRendererText()
		col = gtk.TreeViewColumn(_('Plugin'), renderer, text=1)
		self.installed_plugins_treeview.append_column(col)
		
		renderer = gtk.CellRendererToggle()
		renderer.set_property('activatable', True)
		renderer.connect('toggled', self.installed_plugins_toggled_cb)
		col = gtk.TreeViewColumn(_('Active'), renderer, active=2)
		self.installed_plugins_treeview.append_column(col)
		
		# connect signal for selection change
		selection = self.installed_plugins_treeview.get_selection()
		selection.connect('changed',
						  self.installed_plugins_treeview_selection_changed)
		selection.set_mode(gtk.SELECTION_SINGLE)
		
		self._clear_installed_plugin_info()
		
		self.fill_installed_plugins_model()
		
		self.xml.signal_autoconnect(self)

		self.plugins_notebook.set_current_page(0)
		
		self.window.show_all()
		gtkgui_helpers.possibly_move_window_in_current_desktop(self.window)
	
	@log_calls('PluginsWindow')
	def installed_plugins_treeview_selection_changed(self, treeview_selection):
		model, iter = treeview_selection.get_selected()
		if iter:
			plugin = model.get_value(iter, 0)
			plugin_name = model.get_value(iter, 1)
			is_active = model.get_value(iter, 2)
			
			self._display_installed_plugin_info(plugin)
		else:
			self._clear_installed_plugin_info()
		
	def _display_installed_plugin_info(self, plugin):
		self.plugin_name_label.set_text(plugin.name)
		self.plugin_version_label.set_text(plugin.version)
		self.plugin_authors_label.set_text(", ".join(plugin.authors))
		self.plugin_homepage_linkbutton.set_uri(plugin.homepage)
		self.plugin_homepage_linkbutton.set_label(plugin.homepage)
		self.plugin_homepage_linkbutton.set_property('sensitive', True)
		
		desc_textbuffer = self.plugin_description_textview.get_buffer()
		desc_textbuffer.set_text(plugin.description)
		self.plugin_description_textview.set_property('sensitive', True)
		self.uninstall_plugin_button.set_property('sensitive', True)
		self.configure_plugin_button.set_property('sensitive', True)
		
	def _clear_installed_plugin_info(self):
		self.plugin_name_label.set_text('')
		self.plugin_version_label.set_text('')
		self.plugin_authors_label.set_text('')
		self.plugin_homepage_linkbutton.set_uri('')
		self.plugin_homepage_linkbutton.set_label('')
		self.plugin_homepage_linkbutton.set_property('sensitive', False)
		
		desc_textbuffer = self.plugin_description_textview.get_buffer()
		desc_textbuffer.set_text('')
		self.plugin_description_textview.set_property('sensitive', False)
		self.uninstall_plugin_button.set_property('sensitive', False)
		self.configure_plugin_button.set_property('sensitive', False)
	
	@log_calls('PluginsWindow')
	def fill_installed_plugins_model(self):
		pm = gajim.plugin_manager
		self.installed_plugins_model.clear()
		self.installed_plugins_model.set_sort_column_id(0, gtk.SORT_ASCENDING)
		
		for plugin_class in pm.plugins:
			self.installed_plugins_model.append([plugin_class, 
												 plugin_class.name, 
												 plugin_class._active])
		
	@log_calls('PluginsWindow')
	def installed_plugins_toggled_cb(self, cell, path):
		is_active = self.installed_plugins_model[path][2]
		plugin_class = self.installed_plugins_model[path][0]

		if is_active:
			gajim.plugin_manager.deactivate_plugin(plugin_class._instance)
		else:
			gajim.plugin_manager.activate_plugin(plugin_class)
		
		self.installed_plugins_model[path][2] = not is_active
		
	@log_calls('PluginsWindow')
	def on_plugins_window_destroy(self, widget):
		'''Close window'''
		del gajim.interface.instances['plugins']

	@log_calls('PluginsWindow')
	def on_close_button_clicked(self, widget):
		self.window.destroy()