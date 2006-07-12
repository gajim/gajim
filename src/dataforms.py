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
""" This module contains widget that can display data form (JEP-0004). """

import gtk
import pango

import gtkgui_helpers

import common.xmpp as xmpp
import common.dataforms as dataforms

class DataFormWidget(gtk.Alignment, object):
# "public" interface
	""" Data Form widget. Use like any other widget. """
	def __init__(self, dataformnode=None):
		""" Create a widget. """
		gtk.Alignment.__init__(self, xscale=1.0, yscale=1.0)

		self._data_form = None

		self.xml=gtkgui_helpers.get_glade('data_form_window.glade', 'data_form_scrolledwindow')
		self.instructions = self.xml.get_widget('form_instructions_label')
		self.separator = self.xml.get_widget('form_instructions_hseparator')
		self.container = self.xml.get_widget('container_vbox')

		self.add(self.xml.get_widget('data_form_scrolledwindow'))

		if dataformnode is not None:
			self.set_data_form(dataformnode)

	def set_data_form(self, dataform=None):
		""" Set the data form (xmpp.DataForm) displayed in widget.
		Set to None to erase the form. """
		assert isinstance(dataform, dataforms.DataForm)

		self.del_data_form()
		self._data_form = dataform
		if dataform.mode==dataforms.DATAFORM_SINGLE:
			self.form = self.__class__.SingleForm(dataform)
		else:
			self.form = self.__class__.MultipleForm(dataform)
		self.form.show()
		self.container.pack_end(self.form, expand=True, fill=True)

		if dataform.instructions is None:
			self.instructions.set_no_show_all(True)
			self.instructions.hide()
			self.separator.set_no_show_all(True)
			self.separator.hide()
		else:
			self.instructions.set_text(dataform.instructions)
			self.instructions.set_no_show_all(False)
			self.instructions.show()
			self.separator.set_no_show_all(False)
			self.separator.show()

	def get_data_form(self):
		""" Data form displayed in the widget or None if no form. """
		return self._data_form

	def del_data_form(self):
		if self._data_form is not None:
			self.container.remove(self.form)
		self.form = None
		self._data_form = None

	data_form = property(get_data_form, set_data_form, del_data_form,
		"Data form presented in a widget")

	def get_title(self):
		""" Get the title of data form, as a unicode object. If no
		title or no form, returns u''. Useful for setting window title. """
		if self._data_form is not None:
			if self._data_form.has_key('title'):
				return self._data_form['title'].encode('utf-8')
		return u''

	title = property(get_title, None, None, "Data form title")

	def show(self):
		""" Treat 'us' as one widget. """
		self.show_all()

# "private" methods

# we have actually two different kinds of data forms: one is a simple form to fill,
# second is a table with several records; we will treat second as read-only, but still
# we should have a way to show it

# we will place both types in two different private classes, so the code will be clean;
# both will have the same interface

	class SingleForm(gtk.Table, object):
		""" Widget that represent DATAFORM_SINGLE mode form. """
		def __init__(self, dataform):
			assert dataform.mode==dataforms.DATAFORM_SINGLE

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
							if field.value is None:
								field.value = value
						if value == field.value:
							radio.set_active(True)
						widget.pack_start(radio, expand=False)

				elif field.type == 'list-multi':
					# TODO: When more than few choices, make a list
					widget = gtk.VBox()
					for value, label in field.iter_options():
						check = gtk.CheckButton(label, use_underline=False)
						check.set_active(value in field.value)
						check.connect('toggled', self.on_list_multi_checkbutton_toggled,
							field, value)
						widget.pack_start(check, expand=False)

				elif field.type == 'jid-single':
					widget = gtk.Entry()
					widget.connect('changed', self.on_text_single_entry_changed, field)
					if field.value is None:
						field.value = u''
					widget.set_text(field.value)

				elif field.type == 'jid-multi':
					commonwidget = False

					xml = gtkgui_helpers.get_glade('data_form_window.glade', 'item_list_table')
					widget = xml.get_widget('item_list_table')
					treeview = xml.get_widget('item_treeview')

					listmodel = gtk.ListStore(str, bool)
					for value in field.iter_values():
						# nobody will create several megabytes long stanza
						listmodel.insert(999999, (value,False))

					treeview.set_model(listmodel)

					renderer = gtk.CellRendererText()
					renderer.set_property('ellipsize', pango.ELLIPSIZE_START)
					renderer.set_property('editable', True)
					renderer.connect('edited',
						self.on_jid_multi_cellrenderertext_edited, listmodel, field)

					treeview.append_column(gtk.TreeViewColumn(None, renderer,
						text=0, editable=1))

					xml.get_widget('add_button').connect('clicked',
						self.on_jid_multi_add_button_clicked, listmodel, field)
					xml.get_widget('edit_button').connect('clicked',
						self.on_jid_multi_edit_button_clicked, treeview)
					xml.get_widget('remove_button').connect('clicked',
						self.on_jid_multi_remove_button_clicked, treeview)
					xml.get_widget('clear_button').connect('clicked',
						self.on_jid_multi_clean_button_clicked, listmodel, field)

					self.attach(widget, 1, 2, linecounter, linecounter+1)

					del xml

				elif field.type == 'text-private':
					widget = gtk.Entry()
					widget.connect('changed', self.on_text_single_entry_changed, field)
					widget.set_visibility(False)
					if field.value is None:
						field.value = u''
					widget.set_text(field.value)

				elif field.type == 'text-multi':
					# TODO: bigger text view
					commonwidget = False

					textwidget = gtk.TextView()
					textwidget.set_wrap_mode(gtk.WRAP_WORD)
					textwidget.get_buffer().connect('changed', self.on_text_multi_textbuffer_changed,
						field)
					if field.value is None:
						field.value = u''
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

				if commondesc and field.description is not None:
					label = gtk.Label()
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
			if widget.get_active() and value not in field.value:
				field.value += [value]
			elif not widget.get_active() and value in field.value:
				field.value = [v for v in field.value if v!=value]

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

		def on_jid_multi_add_button_clicked(self, widget, model, field):
			iter = model.insert(999999, ("new@jid",))
			field.value += ["new@jid"]

		def on_jid_multi_edit_button_clicked(self, widget, treeview):
			model, iter = treeview.get_selection().get_selected()
			assert iter is not None

			model[iter][1]=True

		def on_jid_multi_remove_button_clicked(self, widget, model, field):
			pass

		def on_jid_multi_clean_button_clicked(self, widget, model, field):
			model.clear()
			del field.value

	class MultipleForm(gtk.Alignment, object):
		def __init__(self, dataform):
			assert dataform.mode==dataforms.DATAFORM_MULTIPLE
