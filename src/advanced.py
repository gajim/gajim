##	Advanced configuration window
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##
##	Copyright (C) 2003-2005 Gajim Team
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##

import gtk
import gtk.glade
import gobject

from common import gajim

OPT_TYPE = 0
OPT_VAL = 1

GTKGUI_GLADE = 'gtkgui.glade'

class Advanced_window:
	def on_config_edited(self, cell, row, text):
		modelrow = self.model[row]
		if gajim.config.set(modelrow[0], text):
			return
		modelrow[1] = text
	
	def on_advanced_window_destroy(self, widget):
		del self.plugin.windows['advanced_config']

	def on_advanced_close_button_clicked(self, widget):
		self.window.destroy()

	def find_iter(self, parent_iter, name):
		if not parent_iter:
			iter = self.model.get_iter_root()
		else:
			iter = self.model.iter_children(parent_iter)
		while iter:
			if self.model.get_value(iter, 0) == name:
				break
			iter = self.model.iter_next(iter)
		return iter
		
	def fill(self, data, name, parents, val):
		iter = None
		if parents:
			for p in parents:
				iter2 = self.find_iter(iter, p)
				if iter2:
					iter = iter2
		
		if not val:
			self.model.append(iter, [name, '', ''])
			return
		self.model.append(iter, [name, val[OPT_VAL], val[OPT_TYPE][0]])

	def visible_func(self, model, iter, str):
		if str is None or str == '':
			return True #show all
		name = model.get_value(iter, 0)
		if name.find(str) != -1: #was found
			#print 'show', name
			return True
		return False
		
	def on_advanced_entry_changed(self, widget):
		#print 'refilter starts'
		#FIXME: maybe some gobject timeout is better
		text = widget.get_text()
		self.filterstr = text
		#print self.filterstr
		self.modelfilter.refilter() #FIXME: does not work!

	def __init__(self, plugin):
		self.plugin = plugin

		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'advanced_window', None)
		self.window = self.xml.get_widget('advanced_window')
		self.xml.signal_autoconnect(self)

		treeview = self.xml.get_widget('advanced_treeview')
		self.model = gtk.TreeStore(gobject.TYPE_STRING,
					gobject.TYPE_STRING,
					gobject.TYPE_STRING)
		self.model.set_sort_column_id(0, gtk.SORT_ASCENDING)

		renderer_text = gtk.CellRendererText()
		treeview.insert_column_with_attributes(-1, 'Preference Name',
						renderer_text, text = 0)
					
		renderer_text = gtk.CellRendererText()
		renderer_text.set_property('editable', 1)
		renderer_text.connect('edited', self.on_config_edited)
		col = treeview.insert_column_with_attributes(-1, 'Value',
						renderer_text, text = 1)
		
		#col.set_sizing(gtk.TREE_VIEW_COLUMN_FIXED)
		col.set_max_width(250)

		renderer_text = gtk.CellRendererText()
		treeview.insert_column_with_attributes(-1, 'Type',
						renderer_text, text = 2)

		# add data to model
		gajim.config.foreach(self.fill, None)
		
		self.modelfilter = self.model.filter_new()
		self.filterstr = 'account'
		self.modelfilter.set_visible_func(self.visible_func, self.filterstr)
		treeview.set_model(self.modelfilter)
		
		self.plugin.windows['advanced_config'] = self
		self.window.show_all()
