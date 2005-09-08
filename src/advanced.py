##	advanced.py
##
## Gajim Team:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Vincent Hanquez <tab@snarc.org>
## - Nikos Kouremenos <kourem@gmail.com>
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
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

OPT_TYPE = 0
OPT_VAL = 1

(
C_PREFNAME,
C_VALUE,
C_TYPE
) = range(3)

GTKGUI_GLADE = 'gtkgui.glade'

class AdvancedConfigurationWindow:
	def __init__(self, plugin):
		self.plugin = plugin

		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'advanced_configuration_window', APP)
		self.window = self.xml.get_widget('advanced_configuration_window')
		self.entry = self.xml.get_widget('advanced_entry')
		self.desc_label = self.xml.get_widget('advanced_desc_label')

		treeview = self.xml.get_widget('advanced_treeview')
		self.model = gtk.TreeStore(str, str, str)
		self.model.set_sort_column_id(0, gtk.SORT_ASCENDING)
		self.modelfilter = self.model.filter_new()
		self.modelfilter.set_visible_func(self.visible_func)

		renderer_text = gtk.CellRendererText()
		col = treeview.insert_column_with_attributes(-1, _('Preference Name'),
			renderer_text, text = 0)
		col.set_resizable(True)
		
		renderer_text = gtk.CellRendererText()
		renderer_text.set_property('editable', 1)
		renderer_text.connect('edited', self.on_config_edited)
		col = treeview.insert_column_with_attributes(-1, _('Value'),
			renderer_text, text = 1)
		col.set_cell_data_func(renderer_text, self.cb_value_column_data)

		#col.set_resizable(True) DO NOT REMOVE
		# GTK+ bug http://bugzilla.gnome.org/show_bug.cgi?id=304139
		col.set_max_width(250)

		renderer_text = gtk.CellRendererText()
		treeview.insert_column_with_attributes(-1, _('Type'),
			renderer_text, text = 2)

		# add data to model
		gajim.config.foreach(self.fill, self.model)
		
		treeview.set_model(self.modelfilter)
		
		# connect signal for selection change
		treeview.get_selection().connect('changed',
			self.on_advanced_treeview_selection_changed)
		
		self.xml.signal_autoconnect(self)
		self.window.show_all()
		self.plugin.windows['advanced_config'] = self

	def cb_value_column_data(self, col, cell, model, iter):
		optname = model[iter][C_PREFNAME]
		opttype = model[iter][C_TYPE]
		if opttype == 'boolean' or optname.find('password') != -1 or\
			optname.find('passphrase') != -1:
			cell.set_property('editable', 0)
		else:
			cell.set_property('editable', 1)
	
	def on_advanced_treeview_selection_changed(self, treeselection):
		iter = treeselection.get_selected()
		# Get text from first column in this row
		opt = iter[0][iter[1]][0]
		desc = gajim.config.get_desc(opt)
		if desc:
			self.desc_label.set_text(_(desc))
		else:
			self.desc_label.set_text(_('(None)'))
	
	def on_advanced_treeview_row_activated(self, treeview, path, column):
		modelpath = self.modelfilter.convert_path_to_child_path(path)
		modelrow = self.model[modelpath]
		option = modelrow[0].decode('utf-8')
		if modelrow[2] == 'boolean':
			newval = {'False': 'True', 'True': 'False'}[modelrow[1]]
			if len(modelpath) > 1:
				optnamerow = self.model[modelpath[0]]
				optname = optnamerow[0].decode('utf-8')
				keyrow = self.model[modelpath[:2]]
				key = keyrow[0].decode('utf-8')
				gajim.config.set_per(optname, key, option, newval)
			else:
				gajim.config.set(option, newval)
			self.plugin.save_config()
			modelrow[1] = newval

	def on_config_edited(self, cell, path, text):
		# convert modelfilter path to model path
		modelpath = self.modelfilter.convert_path_to_child_path(path)
		modelrow = self.model[modelpath]
		option = modelrow[0].decode('utf-8')
		text = text.decode('utf-8')
		if len(modelpath) > 1:
			optnamerow = self.model[modelpath[0]]
			optname = optnamerow[0].decode('utf-8')
			keyrow = self.model[modelpath[:2]]
			key = keyrow[0].decode('utf-8')
			gajim.config.set_per(optname, key, option, text)
		else:
			gajim.config.set(option, text)
		self.plugin.save_config()
		modelrow[1] = text

	def on_advanced_configuration_window_destroy(self, widget):
		# update ui of preferences window to get possible changes we did
		self.plugin.windows['preferences'].update_preferences_window()
		del self.plugin.windows['advanced_config']

	def on_advanced_close_button_clicked(self, widget):
		self.window.destroy()

	def find_iter(self, model, parent_iter, name):
		if not parent_iter:
			iter = model.get_iter_root()
		else:
			iter = model.iter_children(parent_iter)
		while iter:
			if model[iter][C_PREFNAME].decode('utf-8') == name:
				break
			iter = model.iter_next(iter)
		return iter
		
	def fill(self, model, name, parents, val):
		iter = None
		if parents:
			for p in parents:
				iter2 = self.find_iter(model, iter, p)
				if iter2:
					iter = iter2
		
		if not val:
			model.append(iter, [name, '', ''])
			return
		type = ''
		if val[OPT_TYPE]:
			type = val[OPT_TYPE][0]
		if name.find('password') != -1 or name.find('passphrase') != -1:
			pass # FIXME: do not save Hidden as our pass!
			# just opening once the advanced editor and then closing
			# f$$cks it all up
			#val[OPT_VAL] = _('Hidden') # override passwords with this string
		model.append(iter, [name, val[OPT_VAL], type])

	def visible_func(self, model, iter):
		str = self.entry.get_text().decode('utf-8')
		if str is None or str == '':
			return True # show all
		name = model[iter][C_PREFNAME].decode('utf-8')
		# If a child of the iter matches, we return True
		if model.iter_has_child(iter):
			iterC = model.iter_children(iter)
			while iterC:
				nameC = model[iterC][C_PREFNAME].decode('utf-8')
				if model.iter_has_child(iterC):
					iterCC = model.iter_children(iterC)
					while iterCC:
						nameCC = model[iterCC][C_PREFNAME].decode('utf-8')
						if nameCC.find(str) != -1:
							return True
						iterCC = model.iter_next(iterCC)
				elif nameC.find(str) != -1:
					return True
				iterC = model.iter_next(iterC)
		elif name.find(str) != -1:
			return True
		return False
		
	def on_advanced_entry_changed(self, widget):
		text = widget.get_text().decode('utf-8')
		self.modelfilter.refilter()
