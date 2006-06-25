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
import gtkgui_helpers

import common.xmpp as xmpp

class DataFormWidget(gtk.Alignment):
# "public" interface
	""" Data Form widget. Use like any other widget. """
	def __init__(self, dataformnode=None):
		""" Create a widget. """
		gtk.Alignment.__init__(self)

		self._data_form = None

		self.xml=gtkgui_helpers.get_glade('data_form_window.glade', 'data_form_scrolledwindow')
		self.instructions = self.xml.get_widget('form_instructions_label')
		self.form = self.xml.get_widget('form_table')

		self.add(self.xml.get_widget('data_form_scrolledwindow'))

		self.set_data_form(dataformnode)

	def set_data_form(self, dataform=None):
		""" Set the data form (xmpp.DataForm) displayed in widget.
		Set to None to erase the form. """
		assert (isinstance(dataform, xmpp.Node) or (dataform is None))

		if self._data_form is not None: self._cleanWidgets()
		self._data_form = dataform
		if self._data_form is not None: self._buildWidgets()

	def get_data_form(self):
		""" Data form displayed in the widget or None if no form. """
		return self._data_form

	def get_title(self):
		""" Get the title of data form, as a unicode object. If no
		title or no form, returns u''. Useful for setting window title. """
		if self._data_form is not None:
			if self._data_form.has_key('title'):
				return self._data_form['title'].encode('utf-8')
		return u''

	def show(self):
		""" Treat 'us' as one widget. """
		self.show_all()

	def filled_data_form(self):
		""" Generates form that contains values filled by user. This
		won't be DataForm object, as the DataFields seem to be uncapable
		of some things. """
		assert isinstance(self._data_form, xmpp.DataForm)

		form = xmpp.Node('x', {'xmlns':xmpp.NS_DATA, 'type':'submit'})
		for field in self._data_form.kids:
			if not isinstance(field, xmpp.DataField): continue
			
			ftype = field.getType()
			if ftype not in ('boolean', 'fixed', 'hidden', 'jid-multi',
				'jid-single', 'list-multi', 'list-single',
				'text-multi', 'text-private', 'text-single'):
				ftype = 'text-single'

			if ftype in ('fixed',):
				continue

			newfield = xmpp.Node('field', {'var': field.getVar()})

			if ftype in ('jid-multi', 'list-multi', 'text-multi'):
				for value in field.getValues():
					newvalue = xmpp.Node('value', {}, [value])
					newfield.addChild(node=newvalue)
			else:
				newvalue = xmpp.Node('value', {}, [field.getValue()])
				newfield.addChild(node=newvalue)

			form.addChild(node=newfield)

		return form

	data_form = property(get_data_form, set_data_form, None, "Data form presented in a widget")
	title = property(get_title, None, None, "Data form title")

# "private" methods
	def _buildWidgets(self):
		""" Create all sub-widgets according to self._data_form and
		JEP-0004. """
		assert self._data_form is not None
		assert len(self.form.get_children())==0

		# it is *very* often used here
		df = self._data_form

		instructions = df.getInstructions()
		if instructions is not None:
			self.instructions.set_text(instructions)

		linecounter = 0

		for field in df.kids:
			if not isinstance(field, xmpp.DataField): continue

			# TODO: rewrite that when xmpp.DataField will be rewritten
			ftype = field.getType()
			if ftype not in ('boolean', 'fixed', 'hidden', 'jid-multi',
				'jid-single', 'list-multi', 'list-single',
				'text-multi', 'text-private', 'text-single'):
				ftype = 'text-single'

			if ftype == 'hidden': continue

			# field label
			flabel = field.getAttr('label')
			if flabel is None:
				flabel = field.getVar()

			# field description
			fdesc = field.getDesc()

			# field value (if one)
			fvalue = field.getValue()

			# field values (if one or more)
			fvalues = field.getValues()

			# field options
			foptions = field.getOptions()

			commonlabel = True
			commondesc = True
			commonwidget = True

			if ftype == 'boolean':
				widget = gtk.CheckButton()
				widget.connect('toggled', self.on_boolean_checkbutton_toggled, field)
				if fvalue in ('1', 'true'):
					widget.set_active(True)
				else:
					field.setValue('0')

			elif ftype == 'fixed':
				leftattach = 1
				rightattach = 2
				if flabel is None:
					commonlabel = False
					leftattach = 0
				if fdesc is None:
					commondesc = False
					rightattach = 3
				commonwidget = False
				widget = gtk.Label(fvalue)
				widget.set_line_wrap(True)
				self.form.attach(widget, leftattach, rightattach, linecounter, linecounter+1)

			elif ftype == 'jid-multi':
				widget = gtk.Label('jid-multi field')

			elif ftype == 'jid-single':
				widget = gtk.Label('jid-single field')

			elif ftype == 'list-multi':
				widget = gtk.Label('list-multi field')

			elif ftype == 'list-single':
				# TODO: When more than few choices, make a list
				widget = gtk.VBox()
				first_radio = None
				right_value = False
				for label, value in foptions:
					radio = gtk.RadioButton(first_radio, label=label)
					radio.connect('toggled', self.on_list_single_radiobutton_toggled,
						field, value)
					if first_radio is None:
						first_radio = radio
						first_value = value
					if value == fvalue:
						right_value = True
					widget.pack_end(radio, expand=False)
				if not right_value:
					field.setValue(first_value)

			elif ftype == 'text-multi':
				widget = gtk.Label('text-multi field')

			elif ftype == 'text-private':
				widget = gtk.Label('text-private field')

			elif ftype == 'text-single':
				widget = gtk.Entry()
				widget.connect('changed', self.on_text_single_entry_changed, field)
				if fvalue is None:
					field.setValue('')
					fvalue = ''
				widget.set_text(fvalue)
			
			else:
				widget = gtk.Label('Unhandled widget type!')

			if commonlabel and flabel is not None:
				label = gtk.Label(flabel)
				label.set_justify(gtk.JUSTIFY_RIGHT)
				self.form.attach(label, 0, 1, linecounter, linecounter+1)

			if commonwidget:
				self.form.attach(widget, 1, 2, linecounter, linecounter+1)

			if commondesc and fdesc is not None:
				label = gtk.Label(fdesc)
				label.set_line_wrap(True)
				self.form.attach(label, 2, 3, linecounter, linecounter+1)

			linecounter += 1

		self.form.show_all()

	def _cleanWidgets(self):
		""" Destroy all sub-widgets used to build current data form. """
		def remove(widget):
			self.form.remove(widget)

		self.form.foreach(remove)
		self.instructions.set_text(u"")

	def on_boolean_checkbutton_toggled(self, widget, field):
		if widget.get_active():
			field.setValue('true')
		else:
			field.setValue('false')

	def on_list_single_radiobutton_toggled(self, widget, field, value):
		field.setValue(value)

	def on_text_single_entry_changed(self, widget, field):
		# TODO: check for encoding?
		field.setValue(widget.get_text())
