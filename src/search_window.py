# -*- coding: utf-8 -*-
##	search_window.py
##
## Copyright (C) 2007 Yann Le Boulanger <asterix@lagaule.org>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 2 only.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.

import gobject
import gtk

from common import xmpp, gajim, dataforms

import gtkgui_helpers
import dialogs
import dataforms_widget

class SearchWindow:
	def __init__(self, account, jid):
		'''Create new window.'''

		# an account object
		self.account = account
		self.jid = jid

		# retrieving widgets from xml
		self.xml = gtkgui_helpers.get_glade('search_window.glade')
		self.window = self.xml.get_widget('search_window')
		for name in ('label', 'progressbar', 'search_vbox', 'search_button'):
			self.__dict__[name] = self.xml.get_widget(name)

		self.data_form_widget = dataforms_widget.DataFormWidget()
		self.table = None

		# displaying the window
		self.xml.signal_autoconnect(self)
		self.window.show_all()
		self.request_form()
		self.pulse_id = gobject.timeout_add(80, self.pulse_callback)

		self.is_form = None
		
		# for non-dataform forms
		self.entries = {}
		self.info = {}

	def request_form(self):
		gajim.connections[self.account].request_search_fields(self.jid)
	
	def pulse_callback(self):
		self.progressbar.pulse()
		return True

	def on_search_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()

	def on_search_window_destroy(self, widget):
		if self.pulse_id:
			gobject.source_remove(self.pulse_id)
		del gajim.interface.instances[self.account]['search'][self.jid]

	def on_close_button_clicked(self, button):
		self.window.destroy()

	def on_search_button_clicked(self, button):
		if self.is_form:
			self.data_form_widget.data_form.type = 'submit'
			gajim.connections[self.account].send_search_form(self.jid,
				self.data_form_widget.data_form, True)
			self.search_vbox.remove(self.data_form_widget)
		else:
			for name in self.entries.keys():
				self.infos[name] = self.entries[name].get_text().decode('utf-8')
			if self.infos.has_key('instructions'):
				del self.infos['instructions']
			gajim.connections[self.account].send_search_form(self.jid, self.infos,
				False)
			self.search_vbox.remove(self.table)

		self.progressbar.show()
		self.label.set_text(_('Waiting for results'))
		self.label.show()
		self.pulse_id = gobject.timeout_add(80, self.pulse_callback)
		self.search_button.hide()

	def on_form_arrived(self, form, is_form):
		if self.pulse_id:
			gobject.source_remove(self.pulse_id)
		self.progressbar.hide()
		self.label.hide()

		if not is_form:
			self.is_form = False
			self.infos = form
			nbrow = 0
			if self.infos.has_key('instructions'):
				self.label.set_text(self.infos['instructions'])
				self.label.show()
			self.table = gtk.Table()
			for name in self.infos.keys():
				if not name:
					continue
				if name == 'instructions':
					continue

				nbrow = nbrow + 1
				self.table.resize(rows = nbrow, columns = 2)
				label = gtk.Label(name.capitalize() + ':')
				self.table.attach(label, 0, 1, nbrow - 1, nbrow, 0, 0, 0, 0)
				entry = gtk.Entry()
				entry.set_activates_default(True)
				if self.infos[name]:
					entry.set_text(self.infos[name])
				if name == 'password':
					entry.set_visibility(False)
				self.table.attach(entry, 1, 2, nbrow - 1, nbrow, 0, 0, 0, 0)
				self.entries[name] = entry
			self.table.show_all()
			self.search_vbox.pack_start(self.table)
			return

		self.dataform = dataforms.ExtendForm(node = form)

		self.data_form_widget.set_sensitive(True)
		try:
			self.data_form_widget.data_form = self.dataform
		except dataforms.Error:
			self.label.set_text(_('Error in received dataform'))
			self.label.show()
			return
		self.is_form = True

		self.search_vbox.pack_start(self.data_form_widget)
		self.data_form_widget.show()
		if self.data_form_widget.title:
			self.window.set_title('%s - Search - Gajim' % \
				self.data_form_widget.title)

	def on_result_arrived(self, form, is_form):
		if self.pulse_id:
			gobject.source_remove(self.pulse_id)
		self.progressbar.hide()
		self.label.hide()

		if not is_form:
			if not form:
				self.label.set_text(_('No result'))
				self.label.show()
				return
			# We suppose all items have the same fields
			sw = gtk.ScrolledWindow()
			sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
			treeview = gtk.TreeView()
			sw.add(treeview)
			# Create model
			fieldtypes = [str]*len(form[0])
			model = gtk.ListStore(*fieldtypes)
			# Copy data to model
			for item in form:
				model.append(item.values())
			# Create columns
			counter = 0
			for field in form[0].keys():
				treeview.append_column(
					gtk.TreeViewColumn(field, gtk.CellRendererText(),
					text = counter))
				counter += 1
			treeview.set_model(model)
			sw.show_all()
			self.search_vbox.pack_start(sw)
			return

		self.dataform = dataforms.ExtendForm(node = form)

		self.data_form_widget.set_sensitive(True)
		try:
			self.data_form_widget.data_form = self.dataform
		except dataforms.Error:
			self.label.set_text(_('Error in received dataform'))
			self.label.show()
			return

		self.search_vbox.pack_start(self.data_form_widget)
		self.data_form_widget.show()
		if self.data_form_widget.title:
			self.window.set_title('%s - Search - Gajim' % \
				self.data_form_widget.title)

