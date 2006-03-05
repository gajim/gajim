##	advanced.py
##
## Contributors for this file:
## - Yann Le Boulanger <asterix@lagaule.org>
## - Nikos Kouremenos <kourem@gmail.com>
## - Vincent Hanquez <tab@snarc.org>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
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

from common import gajim
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

(
OPT_TYPE,
OPT_VAL
) = range(2)

(
C_PREFNAME,
C_VALUE,
C_TYPE
) = range(3)

GTKGUI_GLADE = 'gtkgui.glade'

class AdvancedConfigurationWindow:
	def __init__(self):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'advanced_configuration_window', APP)
		self.window = self.xml.get_widget('advanced_configuration_window')
		self.entry = self.xml.get_widget('advanced_entry')
		self.desc_label = self.xml.get_widget('advanced_desc_label')
		self.restart_label = self.xml.get_widget('restart_label')

		# Format:
		# key = option name (root/subopt/opt separated by \n then)
		# value = array(oldval, newval)
		self.changed_opts = {}

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
		renderer_text.connect('edited', self.on_config_edited)
		col = treeview.insert_column_with_attributes(-1, _('Value'),
			renderer_text, text = 1)
		col.set_cell_data_func(renderer_text, self.cb_value_column_data)

		if gtk.gtk_version >= (2, 8, 0) and gtk.pygtk_version >= (2, 8, 0):
			col.set_resizable(True) # there is a bug in 2.6.x series
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
		self.restart_label.hide()
		gajim.interface.instances['advanced_config'] = self

	def cb_value_column_data(self, col, cell, model, iter):
		'''check if it's boolen or holds password stuff and if yes
		make the cellrenderertext not editable else it's editable'''
		optname = model[iter][C_PREFNAME]
		opttype = model[iter][C_TYPE]
		if opttype == 'boolean' or optname in ('password', 'gpgpassword'):
			cell.set_property('editable', False)
		else:
			cell.set_property('editable', True)

	def get_option_path(self, model, iter):
		# It looks like path made from reversed array
		# path[0] is the true one optname
		# path[1] is the key name
		# path[2] is the root of tree
		# last two is optional
		path = [model[iter][0].decode('utf-8')]
		parent = model.iter_parent(iter)
		while parent:
			path.append(model[parent][0].decode('utf-8'))
			parent = model.iter_parent(parent)
		return path

	def on_advanced_treeview_selection_changed(self, treeselection):
		model, iter = treeselection.get_selected()
		# Check for GtkTreeIter
		if iter:
			opt_path = self.get_option_path(model, iter)
			# Get text from first column in this row
			desc = None
			if len(opt_path) == 3:
				desc = gajim.config.get_desc_per(opt_path[2], opt_path[1],
					opt_path[0])
			elif len(opt_path) == 1:
				desc = gajim.config.get_desc(opt_path[0])
			if desc:
				self.desc_label.set_text(desc)
			else:
				#we talk about option description in advanced configuration editor
				self.desc_label.set_text(_('(None)'))

	def remember_option(self, option, oldval, newval):
		if self.changed_opts.has_key(option):
			self.changed_opts[option] = (self.changed_opts[option][0], newval)
		else:
			self.changed_opts[option] = (oldval, newval)

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
				gajim.config.get_desc_per(optname, key, option)
				self.remember_option(option + '\n' + key + '\n' + optname,
					modelrow[1], newval)
				gajim.config.set_per(optname, key, option, newval)
			else:
				self.remember_option(option, modelrow[1], newval)
				gajim.config.set(option, newval)
			gajim.interface.save_config()
			modelrow[1] = newval
			self.check_for_restart()

	def check_for_restart(self):
		self.restart_label.hide()
		for opt in self.changed_opts:
			opt_path = opt.split('\n')
			if len(opt_path)==3:
				restart = gajim.config.get_restart_per(opt_path[2], opt_path[1],
					opt_path[0])
			else:
				restart = gajim.config.get_restart(opt_path[0])
			if restart:
				if self.changed_opts[opt][0] != self.changed_opts[opt][1]:
					self.restart_label.show()
					break

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
			self.remember_option(option + '\n' + key + '\n' + optname, modelrow[1],
				text)
			gajim.config.set_per(optname, key, option, text)
		else:
			self.remember_option(option, modelrow[1], text)
			gajim.config.set(option, text)
		gajim.interface.save_config()
		modelrow[1] = text
		self.check_for_restart()

	def on_advanced_configuration_window_destroy(self, widget):
		del gajim.interface.instances['advanced_config']

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
		value = val[OPT_VAL]
		if name in ('password', 'gpgpassword'):
			#we talk about password
			value = _('Hidden') # override passwords with this string
		model.append(iter, [name, value, type])

	def visible_func(self, model, iter):
		str = self.entry.get_text().decode('utf-8')
		if str in (None, ''):
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
		self.modelfilter.refilter()
