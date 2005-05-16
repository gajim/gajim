##	vcard.py (has Vcard_window class)
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
from common import gajim
from common import i18n
_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

GTKGUI_GLADE = 'gtkgui.glade'

class Vcard_window:
	'''Class for contact's information window'''
	def on_user_information_window_destroy(self, widget = None):
		del self.plugin.windows[self.account]['infos'][self.jid]

	def on_vcard_information_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.window.destroy()

	def on_close_button_clicked(self, widget):
		'''Save user's informations and update the roster on the Jabber server'''
		if self.vcard:
			self.window.destroy()
			return
		#update user.name if it's not ''
		name_entry = self.xml.get_widget('nickname_entry')
		new_name = name_entry.get_text()
		if new_name != self.user.name and new_name != '':
			self.user.name = new_name
			for i in self.plugin.roster.get_user_iter(self.user.jid, self.account):
				self.plugin.roster.tree.get_model().set_value(i, 1, new_name)
			gajim.connections[self.account].update_user(self.user.jid,
				self.user.name, self.user.groups)
		#log history ?
		oldlog = 1
		no_log_for = gajim.config.get_per('accounts', self.account,
			'no_log_for').split()
		if self.user.jid in no_log_for:
			oldlog = 0
		log = self.xml.get_widget('log_checkbutton').get_active()
		if not log and not self.user.jid in no_log_for:
			no_log_for.append(self.user.jid)
		if log and self.user.jid in no_log_for:
			no_log_for.remove(self.user.jid)
		if oldlog != log:
			gajim.config.set_per('accounts', self.account, 'no_log_for',
				' '.join(no_log_for))
		self.window.destroy()

	def set_value(self, entry_name, value):
		try:
			self.xml.get_widget(entry_name).set_text(value)
		except AttributeError, e:
			pass

	def set_values(self, vcard):
		for i in vcard.keys():
			if type(vcard[i]) == type({}):
				for j in vcard[i].keys():
					self.set_value(i + '_' + j +
							'_entry', vcard[i][j])
			else:
				if i == 'DESC':
					self.xml.get_widget('DESC_textview').get_buffer().set_text(
						vcard[i], 0)
				else:
					self.set_value(i + '_entry', vcard[i])
	
	def set_os_info(self, resource, client_info, os_info):
		i = 0
		client = ''
		os = ''
		while self.os_info.has_key(i):
			if self.os_info[i]['resource'] == resource:
				self.os_info[i]['client'] = client_info
				self.os_info[i]['os'] = os_info
			if i > 0:
				client += '\n'
				os += '\n'
			client += self.os_info[i]['client']
			os += self.os_info[i]['os']
			i += 1

		if client == '':
			client = 'N/A'
		if os == '':
			os = 'N/A'
		self.xml.get_widget('client_name_version_label').set_text(client)
		self.xml.get_widget('os_label').set_text(os)

	def fill_jabber_page(self):
		self.xml.get_widget('nickname_label').set_text(self.user.name)
		self.xml.get_widget('jid_label').set_text(self.user.jid)
		self.xml.get_widget('subscription_label').set_text(self.user.sub)
		label = self.xml.get_widget('ask_label')
		if self.user.ask:
			label.set_text(self.user.ask)
		else:
			label.set_text('None')
		self.xml.get_widget('nickname_entry').set_text(self.user.name)
		log = 1
		if self.user.jid in gajim.config.get_per('accounts', self.account,
			'no_log_for').split(' '):
			log = 0
		self.xml.get_widget('log_checkbutton').set_active(log)
		resources = self.user.resource + ' (' + str(self.user.priority) + ')'
		if not self.user.status:
			self.user.status = ''
		stats = self.user.show + ': ' + self.user.status
		gajim.connections[self.account].request_os_info(self.user.jid,
			self.user.resource)
		self.os_info = {0: {'resource': self.user.resource, 'client': '',
			'os': ''}}
		i = 1
		for u in self.plugin.roster.contacts[self.account][self.user.jid]:
			if u.resource != self.user.resource:
				resources += '\n' + u.resource + ' (' + str(u.priority) + ')'
				if not u.status:
					u.status = ''
				stats += '\n' + u.show + ': ' + u.status
				gajim.connections[self.account].request_os_info(self.user.jid,
					u.resource)
				self.os_info[i] = {'resource': u.resource, 'client': '',
					'os': ''}
				i += 1
		self.xml.get_widget('resource_label').set_text(resources)
		self.xml.get_widget('status_label').set_text(stats)
		gajim.connections[self.account].request_vcard(self.user.jid)

	def add_to_vcard(self, vcard, entry, txt):
		'''Add an information to the vCard dictionary'''
		entries = entry.split('_')
		loc = vcard
		while len(entries) > 1:
			if not loc.has_key(entries[0]):
				loc[entries[0]] = {}
			loc = loc[entries[0]]
			del entries[0]
		loc[entries[0]] = txt
		return vcard

	def make_vcard(self):
		'''make the vCard dictionary'''
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_USERID', 'URL', 'TEL_NUMBER',
			'ADR_STREET', 'ADR_EXTADR', 'ADR_LOCALITY', 'ADR_REGION', 'ADR_PCODE',
			'ADR_CTRY', 'ORG_ORGNAME', 'ORG_ORGUNIT', 'TITLE', 'ROLE'] 
		vcard = {}
		for e in entries: 
			txt = self.xml.get_widget(e + '_entry').get_text()
			if txt != '':
				vcard = self.add_to_vcard(vcard, e, txt)
		buffer = self.xml.get_widget('DESC_textview').get_buffer()
		start_iter = buffer.get_start_iter()
		end_iter = buffer.get_end_iter()
		txt = buffer.get_text(start_iter, end_iter, 0)
		if txt != '':
			vcard['DESC'] = txt
		return vcard

	def on_publish_button_clicked(self, widget):
		if gajim.connections[self.account].connected < 2:
			Error_dialog(_('You must be connected to publish your contact information'))
			return
		vcard = self.make_vcard()
		nick = ''
		if vcard.has_key('NICKNAME'):
			nick = vcard['NICKNAME']
		if nick == '':
			nick = gajim.config.get_per('accounts', self.account, 'name')
		self.plugin.nicks[self.account] = nick
		gajim.connections[self.account].send_vcard(vcard)

	def on_retrieve_button_clicked(self, widget):
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_USERID', 'URL', 'TEL_NUMBER',
			'ADR_STREET', 'ADR_EXTADR', 'ADR_LOCALITY', 'ADR_REGION', 'ADR_PCODE',
			'ADR_CTRY', 'ORG_ORGNAME', 'ORG_ORGUNIT', 'TITLE', 'ROLE']
		if gajim.connections[self.account].connected > 1:
			# clear all entries
			for e in entries:
				self.xml.get_widget(e + '_entry').set_text('')
			self.xml.get_widget('DESC_textview').get_buffer().set_text('')
			gajim.connections[self.account].request_vcard(self.jid)
		else:
			Error_dialog(_('You must be connected to get your contact information'))

	def change_to_vcard(self):
		self.xml.get_widget('information_notebook').remove_page(0)
		self.xml.get_widget('nickname_label').set_text('Personal details')
		information_hbuttonbox = self.xml.get_widget('information_hbuttonbox')
		#publish button
		button = gtk.Button(stock = gtk.STOCK_GOTO_TOP)
		button.get_children()[0].get_children()[0].get_children()[1].set_text(
			'Publish')
		button.connect('clicked', self.on_publish_button_clicked)
		button.show_all()
		information_hbuttonbox.pack_start(button)
		#retrieve button
		button = gtk.Button(stock = gtk.STOCK_GOTO_BOTTOM)
		button.get_children()[0].get_children()[0].get_children()[1].set_text(
			'Retrieve')
		button.connect('clicked', self.on_retrieve_button_clicked)
		button.show_all()
		information_hbuttonbox.pack_start(button)
		#close button at the end
		button = self.xml.get_widget('close_button')
		information_hbuttonbox.reorder_child(button, 2)
		
		#make all entries editable
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_USERID', 'URL', 'TEL_NUMBER',
			'ADR_STREET', 'ADR_EXTADR', 'ADR_LOCALITY', 'ADR_REGION', 'ADR_PCODE',
			'ADR_CTRY', 'ORG_ORGNAME', 'ORG_ORGUNIT', 'TITLE', 'ROLE'] 
		for e in entries:
			self.xml.get_widget(e + '_entry').set_property('editable', True)

		description_textview = self.xml.get_widget('DESC_textview')
		description_textview.set_editable(True)
		description_textview.set_cursor_visible(True)

	#the user variable is the jid if vcard is true
	def __init__(self, user, plugin, account, vcard = False):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'vcard_information_window', APP)
		self.window = self.xml.get_widget('vcard_information_window')
		self.plugin = plugin
		self.user = user #don't use it if vcard is true
		self.account = account
		self.vcard = vcard

		if vcard:
			self.jid = user
			self.change_to_vcard()
		else:
			self.jid = user.jid
			self.fill_jabber_page()

		self.xml.signal_autoconnect(self)
		self.window.show_all()
