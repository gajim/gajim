##	dataforms.py
##
## Copyright (C) 2003-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <nkour@jabber.org>
## Copyright (C) 2005 Dimitur Kirov <dkirov@gmail.com>
## Copyright (C) 2003-2005 Vincent Hanquez <tab@snarc.org>
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
""" This module contains widget that can display data form (JEP-0004).
Words single and multiple refers here to types of data forms:
single means these with one record of data (without <recorded/> element),
multiple - these which may contain more data (with <recorded/> element)."""

# TODO: forms of type='result' should be read-only
# TODO: remove tabs from dialog

import gtk

import gtkgui_helpers

import common.dataforms as dataforms

import itertools

class DataFormWidget(gtk.Alignment, object):
# "public" interface
	""" Data Form widget. Use like any other widget. """
	def __init__(self, dataformnode=None):
		""" Create a widget. """
		gtk.Alignment.__init__(self, xscale=1.0, yscale=1.0)

		self._data_form = None

		self.xml=gtkgui_helpers.get_glade('data_form_window.glade', 'data_form_vbox')
		self.xml.signal_autoconnect(self)
		for name in ('instructions_label', 'instructions_hseparator',
				'single_form_viewport', 'data_form_types_notebook',
				'single_form_scrolledwindow', 'multiple_form_hbox',
				'records_treeview', 'add_button', 'remove_button',
				'edit_button', 'up_button', 'down_button', 'clear_button'):
			self.__dict__[name] = self.xml.get_widget(name)

		self.add(self.xml.get_widget('data_form_vbox'))

		if dataformnode is not None:
			self.set_data_form(dataformnode)

		selection = self.records_treeview.get_selection()
		selection.connect('changed', self.on_records_selection_changed)
		selection.set_mode(gtk.SELECTION_MULTIPLE)

	def set_data_form(self, dataform):
		""" Set the data form (xmpp.DataForm) displayed in widget. """
		assert isinstance(dataform, dataforms.DataForm)

		self.del_data_form()
		self._data_form = dataform
		if isinstance(dataform, dataforms.SimpleDataForm):
			self.build_single_data_form()
		else:
			self.build_multiple_data_form()

		# create appropriate description for instructions field if there isn't any
		if dataform.instructions=='':
			if dataform.type=='result':
				# form is single
				instructions = _('This is result of query.')
			else:
				# form is writable (TODO: move that to build_*_data_form()?)
				if isinstance(dataform, dataforms.SimpleDataForm):
					instructions = _('Fill in the form.')
				else:
					instructions = _('Edit items on the list')
		else:
			instructions = dataform.instructions

		self.instructions_label.set_text(instructions)

	def get_data_form(self):
		""" Data form displayed in the widget or None if no form. """
		return self._data_form

	def del_data_form(self):
		self.clean_data_form()
		self._data_form = None

	data_form = property(get_data_form, set_data_form, del_data_form,
		"Data form presented in a widget")

	def get_title(self):
		""" Get the title of data form, as a unicode object. If no
		title or no form, returns u''. Useful for setting window title. """
		if self._data_form is not None:
			if self._data_form.title is not None:
				return self._data_form.title
		return u''

	title = property(get_title, None, None, "Data form title")

	def show(self):
		""" Treat 'us' as one widget. """
		self.show_all()

# "private" methods

# we have actually two different kinds of data forms: one is a simple form to fill,
# second is a table with several records; 

	def clean_data_form(self):
		'''Remove data about existing form. This metod is empty, because
		it is rewritten by build_*_data_form, according to type of form
		which is actually displayed.'''
		pass

	def build_single_data_form(self):
		'''Invoked when new single form is to be created.'''
		assert isinstance(self._data_form, dataforms.SimpleDataForm)

		self.clean_data_form()

		self.singleform = SingleForm(self._data_form)
		self.singleform.show()
		self.single_form_viewport.add(self.singleform)
		self.data_form_types_notebook.set_current_page(
			self.data_form_types_notebook.page_num(
				self.single_form_scrolledwindow))

		self.clean_data_form = self.clean_single_data_form

	def clean_single_data_form(self):
		'''(Called as clean_data_form, read the docs of clean_data_form()).
		Remove form from widget.'''
		self.singleform.destroy()
		del self.singleform

	def build_multiple_data_form(self):
		'''Invoked when new multiple form is to be created.'''
		assert isinstance(self._data_form, dataforms.MultipleDataForm)

		self.clean_data_form()

		# creating model for form...
		fieldtypes = []
		for field in self._data_form.recorded.iter_fields():
			# note: we store also text-private and hidden fields,
			# we just do not display them.
			# TODO: boolean fields
			#elif field.type=='boolean': fieldtypes.append(bool)
			fieldtypes.append(str)

		self.multiplemodel = gtk.ListStore(*fieldtypes)

		# moving all data to model
		for item in self._data_form.iter_records():
			# TODO: probably wrong... (.value[s]?, fields not in the same order?)
			# not checking multiple-item forms...
			self.multiplemodel.append([field.value for field in item.iter_fields()])

		# constructing columns...
		for field, counter in zip(self._data_form.iter_fields(), itertools.count()):
			print repr(field), repr(counter)
			self.records_treeview.append_column(
				gtk.TreeViewColumn(field.label,	gtk.CellRendererText(),
					text=counter))

		self.records_treeview.set_model(self.multiplemodel)
		self.records_treeview.show_all()

		self.data_form_types_notebook.set_current_page(
			self.data_form_types_notebook.page_num(
				self.multiple_form_hbox))

		self.clean_data_form = self.clean_multiple_data_form

		# refresh list look
		self.refresh_multiple_buttons()

	def clean_multiple_data_form(self):
		'''(Called as clean_data_form, read the docs of clean_data_form()).
		Remove form from widget.'''
		del self.multiplemodel

	def refresh_multiple_buttons(self):
		''' Checks for treeview state and makes control buttons sensitive.'''
		selection = self.records_treeview.get_selection()
		model = self.records_treeview.get_model()
		count = selection.count_selected_rows()
		if count==0:
			self.remove_button.set_sensitive(False)
			self.edit_button.set_sensitive(False)
			self.up_button.set_sensitive(False)
			self.down_button.set_sensitive(False)
		elif count==1:
			self.remove_button.set_sensitive(True)
			self.edit_button.set_sensitive(True)
			_, (path,) = selection.get_selected_rows()
			iter = model.get_iter(path)
			if model.iter_next(iter) is None:
				self.up_button.set_sensitive(True)
				self.down_button.set_sensitive(False)
			elif path==(0,):
				self.up_button.set_sensitive(False)
				self.down_button.set_sensitive(True)
			else:
				self.up_button.set_sensitive(True)
				self.down_button.set_sensitive(True)
		else:
			self.remove_button.set_sensitive(True)
			self.edit_button.set_sensitive(True)
			self.up_button.set_sensitive(False)
			self.down_button.set_sensitive(False)

		if len(model)==0:
			self.clear_button.set_sensitive(False)
		else:
			self.clear_button.set_sensitive(True)

	def on_clear_button_clicked(self, widget):
		self.records_treeview.get_model().clear()

	def on_remove_button_clicked(self, widget):
		selection = self.records_treeview.get_selection()
		model, rowrefs = selection.get_selected_rows()	# rowref is a list of paths
		for i in xrange(len(rowrefs)):
			rowrefs[i] = gtk.TreeRowReference(model, rowrefs[i])
		# rowref is a list of row references; need to convert because we will modify the model,
		# paths would change
		for rowref in rowrefs:
			del model[rowref.get_path()]
	
	def on_up_button_clicked(self, widget):
		selection = self.records_treeview.get_selection()
		model, (path,) = selection.get_selected_rows()
		iter = model.get_iter(path)
		previter = model.get_iter((path[0]-1,))	# constructing path for previous iter
		model.swap(iter, previter)

		self.refresh_multiple_buttons()

	def on_down_button_clicked(self, widget):
		selection = self.records_treeview.get_selection()
		model, (path,) = selection.get_selected_rows()
		iter = model.get_iter(path)
		nextiter = model.iter_next(iter)
		model.swap(iter, nextiter)

		self.refresh_multiple_buttons()

	def on_records_selection_changed(self, widget):
		self.refresh_multiple_buttons()

class SingleForm(gtk.Table, object):
	""" Widget that represent DATAFORM_SINGLE mode form. Because this is used
	not only to display single forms, but to form input windows of multiple-type
	forms, it is in another class."""
	def __init__(self, dataform):
		assert isinstance(dataform, dataforms.SimpleDataForm)

		gtk.Table.__init__(self)
		self.set_col_spacings(6)
		self.set_row_spacings(6)

		self._data_form = dataform

		# building widget
		linecounter = 0

		# for each field...
		for field in self._data_form.iter_fields():
			if field.type=='hidden': continue

			commonlabel = True
			commondesc = True
			commonwidget = True
			widget = None

			if field.type=='boolean':
				widget = gtk.CheckButton()
				widget.connect('toggled', self.on_boolean_checkbutton_toggled, field)
				widget.set_active(field.value)

			elif field.type=='fixed':
				leftattach = 1
				rightattach = 2
				if field.label is None:
					commonlabel = False
					leftattach = 0
				if field.description is None:
					commondesc = False
					rightattach = 3
				
				commonwidget=False
				widget = gtk.Label(field.value)
				widget.set_line_wrap(True)
				self.attach(widget, leftattach, rightattach, linecounter, linecounter+1,
					xoptions=gtk.FILL, yoptions=gtk.FILL)

			elif field.type == 'list-single':
				# TODO: When more than few choices, make a list
				# TODO: Think of moving that to another function (it could be used
				# TODO: in stage2 of adhoc commands too).
				# TODO: What if we have radio buttons and non-required field?
				# TODO: We cannot deactivate them all...
				widget = gtk.VBox()
				first_radio = None
				for value, label in field.iter_options():
					radio = gtk.RadioButton(first_radio, label=label)
					radio.connect('toggled', self.on_list_single_radiobutton_toggled,
						field, value)
					if first_radio is None:
						first_radio = radio
						if field.value=='':	# TODO: is None when done
							field.value = value
					if value == field.value:
						radio.set_active(True)
					widget.pack_start(radio, expand=False)

			elif field.type == 'list-multi':
				# TODO: When more than few choices, make a list
				widget = gtk.VBox()
				for value, label in field.iter_options():
					check = gtk.CheckButton(label, use_underline=False)
					check.set_active(value in field.values)
					check.connect('toggled', self.on_list_multi_checkbutton_toggled,
						field, value)
					widget.pack_start(check, expand=False)

			elif field.type == 'jid-single':
				widget = gtk.Entry()
				widget.connect('changed', self.on_text_single_entry_changed, field)
				widget.set_text(field.value)

			elif field.type == 'jid-multi':
				commonwidget = False

				xml = gtkgui_helpers.get_glade('data_form_window.glade', 'item_list_table')
				widget = xml.get_widget('item_list_table')
				treeview = xml.get_widget('item_treeview')

				listmodel = gtk.ListStore(str)
				for value in field.iter_values():
					# nobody will create several megabytes long stanza
					listmodel.insert(999999, (value,))

				treeview.set_model(listmodel)

				renderer = gtk.CellRendererText()
				renderer.set_property('editable', True)
				renderer.connect('edited',
					self.on_jid_multi_cellrenderertext_edited, listmodel, field)

				treeview.append_column(gtk.TreeViewColumn(None, renderer,
					text=0))

				xml.get_widget('add_button').connect('clicked',
					self.on_jid_multi_add_button_clicked, treeview, listmodel, field)
				xml.get_widget('edit_button').connect('clicked',
					self.on_jid_multi_edit_button_clicked, treeview)
				xml.get_widget('remove_button').connect('clicked',
					self.on_jid_multi_remove_button_clicked, treeview, field)
				xml.get_widget('clear_button').connect('clicked',
					self.on_jid_multi_clean_button_clicked, listmodel, field)

				self.attach(widget, 1, 2, linecounter, linecounter+1)

				del xml

			elif field.type == 'text-private':
				widget = gtk.Entry()
				widget.connect('changed', self.on_text_single_entry_changed, field)
				widget.set_visibility(False)
				widget.set_text(field.value)

			elif field.type == 'text-multi':
				# TODO: bigger text view
				commonwidget = False

				textwidget = gtk.TextView()
				textwidget.set_wrap_mode(gtk.WRAP_WORD)
				textwidget.get_buffer().connect('changed', self.on_text_multi_textbuffer_changed,
					field)
				textwidget.get_buffer().set_text(field.value)
				
				widget = gtk.ScrolledWindow()
				widget.add(textwidget)

				self.attach(widget, 1, 2, linecounter, linecounter+1)

			else:# field.type == 'text-single' or field.type is nonstandard:
				# JEP says that if we don't understand some type, we
				# should handle it as text-single
				widget = gtk.Entry()
				widget.connect('changed', self.on_text_single_entry_changed, field)
				if field.value is None:
					field.value = u''
				widget.set_text(field.value)

			if commonlabel and field.label is not None:
				label = gtk.Label(field.label)
				label.set_alignment(1.0, 0.5)
				self.attach(label, 0, 1, linecounter, linecounter+1,
					xoptions=gtk.FILL, yoptions=gtk.FILL)

			if commonwidget:
				assert widget is not None
				self.attach(widget, 1, 2, linecounter, linecounter+1,
					yoptions=gtk.FILL)
			widget.show_all()

			if commondesc and field.description!='':
				label = gtk.Label()
				label.set_alignment(0.0, 0.5)	# align to left
				label.set_markup('<small>'+\
					gtkgui_helpers.escape_for_pango_markup(field.description)+\
					'</small>')
				label.set_line_wrap(True)
				self.attach(label, 2, 3, linecounter, linecounter+1,
					xoptions=gtk.FILL|gtk.SHRINK, yoptions=gtk.FILL|gtk.SHRINK)

			linecounter+=1
		if self.get_property('visible'):
			self.show_all()

	def show(self):
		# simulate that we are one widget
		self.show_all()

	def on_boolean_checkbutton_toggled(self, widget, field):
		field.value = widget.get_active()

	def on_list_single_radiobutton_toggled(self, widget, field, value):
		field.value = value

	def on_list_multi_checkbutton_toggled(self, widget, field, value):
		# TODO: make some methods like add_value and remove_value
		if widget.get_active() and value not in field.values:
			field.values += [value]
		elif not widget.get_active() and value in field.values:
			field.values = [v for v in field.values if v!=value]

	def on_text_single_entry_changed(self, widget, field):
		field.value = widget.get_text()

	def on_text_multi_textbuffer_changed(self, widget, field):
		field.value = widget.get_text(
			widget.get_start_iter(),
			widget.get_end_iter())

	def on_jid_multi_cellrenderertext_edited(self, cell, path, newtext, model, field):
		old=model[path][0]
		model[path][0]=newtext

		values = field.values
		values[values.index(old)]=newtext
		field.values = values

	def on_jid_multi_add_button_clicked(self, widget, treeview, model, field):
		iter = model.insert(999999, ("new@jabber.id",))
		treeview.set_cursor(model.get_path(iter), treeview.get_column(0), True)
		field.values = field.values + ["new@jabber.id"]

	def on_jid_multi_edit_button_clicked(self, widget, treeview):
		model, iter = treeview.get_selection().get_selected()
		assert iter is not None

		treeview.set_cursor(model.get_path(iter), treeview.get_column(0), True)

	def on_jid_multi_remove_button_clicked(self, widget, treeview, field):
		selection = treeview.get_selection()
		model = treeview.get_model()
		deleted = []

		def remove(model, path, iter, deleted):
			deleted+=model[iter]
			model.remove(iter)

		selection.selected_foreach(remove, deleted)
		field.values = (v for v in field.values if v not in deleted)

	def on_jid_multi_clean_button_clicked(self, widget, model, field):
		model.clear()
		del field.values
