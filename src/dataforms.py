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

class DataFormWidget(gtk.Alignment):
# "public" interface
	""" Data Form widget. Use like any other widget. """
	def __init__(self, dataformnode=None):
		""" Create a widget. """
		gtk.Alignment.__init__(self)

		self.xml=gtkgui_helpers.get_glade('data_form_window.glade', 'data_form_scrolledwindow')
		self.instructions = self.xml.get_widget('form_instructions_label')
		self.form = self.xml.get_widget('form_vbox')

		self.add(self.xml.get_widget('data_form_scrolledwindow')

		self.set_data_form(dataform)

	def set_data_form(self, dataform=None):
		""" Set the data form (xmpp.DataForm) displayed in widget.
		Set to None to erase the form. """
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

	data_form = property(get_data_form, set_data_form, None, "Data form presented in a widget")
	title = property(get_title, None, None, "Data form title")

# "private" methods
	def _buildWidgets(self):
		""" Create all sub-widgets according to self._data_form and
		JEP-0004. """
		assert self._data_form is not None
		assert length(self.form.get_children())==0

		# it is *very* often used here
		df = self._data_form

		if df.has_key('instructions'):
			self.instructions.set_text(df['instructions'])

		i = -1
		while df.has_key(i+1):
			i += 1
			if not df[i].has_key['type']:
				continue
			
			ctype = df[i]['type']
			if ctype = 'hidden':
				continue

			hbox = gtk.HBox(spacing = 5)
			label = gtk.Label('')
			label.set_line_wrap(True)
			label.set_alignment(0.0, 0.5)
			label.set_property('width_request', 150)
			hbox.pack_start(label, False)
			if df[i].has_key('label'):
				label.set_text(df[i]['label'])
			if ctype == 'boolean':
				desc = None
				if df[i].has_key('desc'):
					desc = df[i]['desc']
				widget = gtk.CheckButton(desc, False)
				activ = False
				if df[i].has_key('values'):
					activ = df[i]['values'][0]
				widget.set_active(activ)
				widget.connect('toggled', self.on_checkbutton_toggled, i)
			elif ctype == 'fixed':
				widget = gtk.Label('\n'.join(df[i]['values']))
				widget.set_line_wrap(True)
				widget.set_alignment(0.0, 0.5)
			elif ctype == 'jid-multi':
				#FIXME
				widget = gtk.Label('')
			elif ctype == 'jid-single':
				#FIXME
				widget = gtk.Label('')
			elif ctype == 'list-multi':
				j = 0
				widget = gtk.Table(1, 1)
				while df[i]['options'].has_key(j):
					widget.resize(j + 1, 1)
					child = gtk.CheckButton(df[i]['options'][j]['label'],
						False)
					if df[i]['options'][j]['values'][0] in \
					df[i]['values']:
						child.set_active(True)
					child.connect('toggled', self.on_checkbutton_toggled2, i, j)
					widget.attach(child, 0, 1, j, j+1)
					j += 1
			elif ctype == 'list-single':
				widget = gtk.combo_box_new_text()
				widget.connect('changed', self.on_combobox_changed, i)
				index = 0
				j = 0
				while df[i]['options'].has_key(j):
					if df[i]['options'][j]['values'][0] == \
						df[i]['values'][0]:
						index = j
					widget.append_text(df[i]['options'][j]['label'])
					j += 1
				widget.set_active(index)
			elif ctype == 'text-multi':
				widget = gtk.TextView()
				widget.set_size_request(100, -1)
				widget.get_buffer().connect('changed', self.on_textbuffer_changed, \
					i)
				widget.get_buffer().set_text('\n'.join(df[i]['values']))
			elif ctype == 'text-private':
				widget = gtk.Entry()
				widget.connect('changed', self.on_entry_changed, i)
				if not df[i].has_key('values'):
					df[i]['values'] = ['']
				widget.set_text(df[i]['values'][0])
				widget.set_visibility(False)
			elif ctype == 'text-single':
				widget = gtk.Entry()
				widget.connect('changed', self.on_entry_changed, i)
				if not df[i].has_key('values'):
					df[i]['values'] = ['']
				widget.set_text(df[i]['values'][0])
			hbox.pack_start(widget, False)
			hbox.pack_start(gtk.Label('')) # So that widhet doesn't take all space
			self.form.pack_start(hbox, False)
		self.form.show_all()

	def _cleanWidgets(self):
		""" Destroy all sub-widgets used to build current data form. """
		def remove(widget):
			self.form.remove(widget)

		self.form.foreach(remove)

	def on_checkbutton_toggled(self, widget, index):
		self.config[index]['values'][0] = widget.get_active()

	def on_checkbutton_toggled2(self, widget, index1, index2):
		val = self._data_form[index1]['options'][index2]['values'][0]
		if widget.get_active() and val not in self._data_form[index1]['values']:
			self._data_form[index1]['values'].append(val)
		elif not widget.get_active() and val in self._data_form[index1]['values']:
			self._data_form[index1]['values'].remove(val)

	def on_combobox_changed(self, widget, index):
		self._data_form[index]['values'][0] = self.config[index]['options'][ \
			widget.get_active()]['values'][0]

	def on_entry_changed(self, widget, index):
		self._data_form[index]['values'][0] = widget.get_text().decode('utf-8')

	def on_textbuffer_changed(self, widget, index):
		begin, end = widget.get_bounds()
		self._data_form[index]['values'][0] = widget.get_text(begin, end)
