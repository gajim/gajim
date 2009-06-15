# -*- coding:utf-8 -*-
## src/advanced.py
##
## Copyright (C) 2005 Travis Shirk <travis AT pobox.com>
##                    Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005-2007 Yann Leboulanger <asterix AT lagaule.org>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import gtk
import gtkgui_helpers
import gobject

from common import gajim

(
OPT_TYPE,
OPT_VAL
) = range(2)

(
C_PREFNAME,
C_VALUE,
C_TYPE
) = range(3)

GTKGUI_GLADE = 'manage_accounts_window.glade'

def rate_limit(rate):
	''' call func at most *rate* times per second '''
	def decorator(func):
		timeout = [None]
		def f(*args, **kwargs):
			if timeout[0] is not None:
				gobject.source_remove(timeout[0])
				timeout[0] = None
			def timeout_func():
				func(*args, **kwargs)
				timeout[0] = None
			timeout[0] = gobject.timeout_add(int(1000.0 / rate), timeout_func)
		return f
	return decorator

def tree_model_iter_children(model, treeiter):
	it = model.iter_children(treeiter)
	while it:
		yield it
		it = model.iter_next(it)

def tree_model_pre_order(model, treeiter):
	yield treeiter
	for childiter in tree_model_iter_children(model, treeiter):
		for it in tree_model_pre_order(model, childiter):
			yield it

try:
	any(()) # builtin since python 2.5
except Exception:
	def any(iterable):
		for element in iterable:
			if element:
				return True
		return False

class AdvancedConfigurationWindow(object):
	def __init__(self):
		self.xml = gtkgui_helpers.get_glade('advanced_configuration_window.glade')
		self.window = self.xml.get_widget('advanced_configuration_window')
		self.window.set_transient_for(
			gajim.interface.instances['preferences'].window)
		self.entry = self.xml.get_widget('advanced_entry')
		self.desc_label = self.xml.get_widget('advanced_desc_label')
		self.restart_label = self.xml.get_widget('restart_label')

		# Format:
		# key = option name (root/subopt/opt separated by \n then)
		# value = array(oldval, newval)
		self.changed_opts = {}

		# For i18n
		self.right_true_dict = {True: _('Activated'), False: _('Deactivated')}
		self.types = {
			'boolean': _('Boolean'),
			'integer': _('Integer'),
			'string': _('Text'),
			'color': _('Color')}

		treeview = self.xml.get_widget('advanced_treeview')
		self.treeview = treeview
		self.model = gtk.TreeStore(str, str, str)
		self.fill_model()
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

		col.props.resizable = True
		col.set_max_width(250)

		renderer_text = gtk.CellRendererText()
		treeview.insert_column_with_attributes(-1, _('Type'),
			renderer_text, text = 2)

		treeview.set_model(self.modelfilter)

		# connect signal for selection change
		treeview.get_selection().connect('changed',
			self.on_advanced_treeview_selection_changed)

		self.xml.signal_autoconnect(self)
		self.window.show_all()
		self.restart_label.hide()
		gajim.interface.instances['advanced_config'] = self

	def cb_value_column_data(self, col, cell, model, iter_):
		'''check if it's boolen or holds password stuff and if yes
		make the cellrenderertext not editable else it's editable'''
		optname = model[iter_][C_PREFNAME]
		opttype = model[iter_][C_TYPE]
		if opttype == self.types['boolean'] or optname == 'password':
			cell.set_property('editable', False)
		else:
			cell.set_property('editable', True)

	def get_option_path(self, model, iter_):
		# It looks like path made from reversed array
		# path[0] is the true one optname
		# path[1] is the key name
		# path[2] is the root of tree
		# last two is optional
		path = [model[iter_][0].decode('utf-8')]
		parent = model.iter_parent(iter_)
		while parent:
			path.append(model[parent][0].decode('utf-8'))
			parent = model.iter_parent(parent)
		return path

	def on_advanced_treeview_selection_changed(self, treeselection):
		model, iter_ = treeselection.get_selected()
		# Check for GtkTreeIter
		if iter_:
			opt_path = self.get_option_path(model, iter_)
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
		if option in self.changed_opts:
			self.changed_opts[option] = (self.changed_opts[option][0], newval)
		else:
			self.changed_opts[option] = (oldval, newval)

	def on_advanced_treeview_row_activated(self, treeview, path, column):
		modelpath = self.modelfilter.convert_path_to_child_path(path)
		modelrow = self.model[modelpath]
		option = modelrow[0].decode('utf-8')
		if modelrow[2] == self.types['boolean']:
			for key in self.right_true_dict.keys():
				if self.right_true_dict[key] == modelrow[1]:
					modelrow[1] = key
			newval = {'False': True, 'True': False}[modelrow[1]]
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
			modelrow[1] = self.right_true_dict[newval]
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

	def fill_model(self, node=None, parent=None):
		for item, option in gajim.config.get_children(node):
			name = item[-1]
			if option is None: # Node
				newparent = self.model.append(parent, [name, '', ''])
				self.fill_model(item, newparent)
			else: # Leaf
				type_ = self.types[option[OPT_TYPE][0]]
				if name == 'password':
					value = _('Hidden')
				else:
					value = self.right_true_dict.get(option[OPT_VAL],
						option[OPT_VAL])
				self.model.append(parent, [name, value, type_])

	def visible_func(self, model, treeiter):
		search_string  = self.entry.get_text().lower()
		for it in tree_model_pre_order(model,treeiter):
			if model[it][C_TYPE] != '':
				opt_path = self.get_option_path(model, it)
				if len(opt_path) == 3:
					desc = gajim.config.get_desc_per(opt_path[2], opt_path[1],
						opt_path[0])
				elif len(opt_path) == 1:
					desc = gajim.config.get_desc(opt_path[0])
				if search_string in model[it][C_PREFNAME] or (desc and \
				search_string in desc.lower()):
					return True
		return False

	@rate_limit(3)
	def on_advanced_entry_changed(self, widget):
		self.modelfilter.refilter()
		if not widget.get_text():
			# Maybe the expanded rows should be remembered here ...
			self.treeview.collapse_all()
		else:
			# ... and be restored correctly here
			self.treeview.expand_all()

# vim: se ts=3:
