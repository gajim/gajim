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
import urllib
import base64
import mimetypes
import os
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

	def on_clear_button_clicked(self, widget):
		# empty the image
		self.xml.get_widget('PHOTO_image').set_from_pixbuf(None)

	def image_is_ok(self, image):
		if not os.path.exists(image):
			return False
		return True

	def on_set_avatar_button_clicked(self, widget):
		file = None
		dialog = gtk.FileChooserDialog('Choose avatar', None,
			gtk.FILE_CHOOSER_ACTION_OPEN,
			(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
			gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		dialog.set_default_response(gtk.RESPONSE_OK)
		filter = gtk.FileFilter()
		filter.set_name('All files')
		filter.add_pattern('*')
		dialog.add_filter(filter)

		filter = gtk.FileFilter()
		filter.set_name('Images')
		filter.add_mime_type('image/png')
		filter.add_mime_type('image/jpeg')
		filter.add_mime_type('image/gif')
		filter.add_pattern('*.png')
		filter.add_pattern('*.jpg')
		filter.add_pattern('*.gif')
		filter.add_pattern('*.tif')
		filter.add_pattern('*.xpm')
		dialog.add_filter(filter)
		dialog.set_filter(filter)

		ok = False
		while not ok:
			response = dialog.run()
			if response == gtk.RESPONSE_OK:
				file = dialog.get_filename()
				if self.image_is_ok(file):
					ok = True
			else:
				ok = True
		dialog.destroy()

		if file:
			fd = open(file)
			data = fd.read()
			pixbufloader = gtk.gdk.PixbufLoader()
			pixbufloader.write(data)
			pixbufloader.close()
			pixbuf = pixbufloader.get_pixbuf()
			image = self.xml.get_widget('PHOTO_image')
			image.set_from_pixbuf(pixbuf)
			self.avatar_encoded = base64.encodestring(data)
			self.avatar_mime_type = mimetypes.guess_type(file)[0]

	def set_value(self, entry_name, value):
		try:
			self.xml.get_widget(entry_name).set_text(value)
		except AttributeError, e:
			pass

	def set_values(self, vcard):
		for i in vcard.keys():
			if i == 'PHOTO':
				img_decoded = None
				if vcard[i].has_key('BINVAL') and vcard[i].has_key('TYPE'):
					img_encoded = vcard[i]['BINVAL']
					self.avatar_encoded = img_encoded
					self.avatar_mime_type = vcard[i]['TYPE']
					try:
						img_decoded = base64.decodestring(img_encoded)
					except:
						pass
				elif vcard[i].has_key('EXTVAL'):
					url = vcard[i]['EXTVAL']
					try:
						fd = urllib.urlopen(url)
						img_decoded = fd.read()
					except:
						pass
				if img_decoded:
					pixbufloader = gtk.gdk.PixbufLoader()
					pixbufloader.write(img_decoded)
					pixbufloader.close()
					pixbuf = pixbufloader.get_pixbuf()
					image = self.xml.get_widget('PHOTO_image')
					image.set_from_pixbuf(pixbuf)
				continue
			if i == 'ADR' or i == 'TEL' or i == 'EMAIL':
				for entry in vcard[i]:
					add_on = '_HOME'
					if 'WORK' in entry:
						add_on = '_WORK'
					for j in entry.keys():
						self.set_value(i + add_on + '_' + j + '_entry', entry[j])
			if type(vcard[i]) == type({}):
				for j in vcard[i].keys():
					self.set_value(i + '_' + j + '_entry', vcard[i][j])
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
		stats = self.user.show
		if self.user.status:
			stats += ': ' + self.user.status
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
		if len(entries) == 3: # We need to use lists
			if not loc.has_key(entries[0]):
				loc[entries[0]] = []
			found = False
			for e in loc[entries[0]]:
				if entries[1] in e:
					found = True
					break
			if found:
				e[entries[2]] = txt
			else:
				loc[entries[0]].append({entries[1]: '', entries[2]: txt})
			return vcard
		while len(entries) > 1:
			if not loc.has_key(entries[0]):
				loc[entries[0]] = {}
			loc = loc[entries[0]]
			del entries[0]
		loc[entries[0]] = txt
		return vcard

	def make_vcard(self):
		'''make the vCard dictionary'''
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_HOME_USERID', 'URL',
			'TEL_HOME_NUMBER', 'N_FAMILY', 'N_GIVEN', 'N_MIDDLE', 'N_PREFIX',
			'N_SUFFIX', 'ADR_HOME_STREET', 'ADR_HOME_EXTADR', 'ADR_HOME_LOCALITY',
			'ADR_HOME_REGION', 'ADR_HOME_PCODE', 'ADR_HOME_CTRY', 'ORG_ORGNAME',
			'ORG_ORGUNIT', 'TITLE', 'ROLE', 'ADR_WORK_STREET', 'ADR_WORK_EXTADR',
			'ADR_WORK_LOCALITY', 'ADR_WORK_REGION', 'ADR_WORK_PCODE',
			'ADR_WORK_CTRY']
		vcard = {}
		for e in entries: 
			txt = self.xml.get_widget(e + '_entry').get_text()
			if txt != '':
				vcard = self.add_to_vcard(vcard, e, txt)

		# DESC textview
		buffer = self.xml.get_widget('DESC_textview').get_buffer()
		start_iter = buffer.get_start_iter()
		end_iter = buffer.get_end_iter()
		txt = buffer.get_text(start_iter, end_iter, 0)
		if txt != '':
			vcard['DESC'] = txt

		# Avatar
		if self.avatar_encoded:
			vcard['PHOTO'] = {'TYPE': self.avatar_mime_type,
				'BINVAL': self.avatar_encoded}
		return vcard

	def on_publish_button_clicked(self, widget):
		if gajim.connections[self.account].connected < 2:
			Error_dialog(_('You are not connected to the server'),
                    _('Without a connection you can not publish your contact information.')).get_response()
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
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_HOME_USERID', 'URL',
			'TEL_HOME_NUMBER', 'N_FAMILY', 'N_GIVEN', 'N_MIDDLE', 'N_PREFIX',
			'N_SUFFIX', 'ADR_HOME_STREET', 'ADR_HOME_EXTADR', 'ADR_HOME_LOCALITY',
			'ADR_HOME_REGION', 'ADR_HOME_PCODE', 'ADR_HOME_CTRY', 'ORG_ORGNAME',
			'ORG_ORGUNIT', 'TITLE', 'ROLE', 'ADR_WORK_STREET', 'ADR_WORK_EXTADR',
			'ADR_WORK_LOCALITY', 'ADR_WORK_REGION', 'ADR_WORK_PCODE',
			'ADR_WORK_CTRY']
		if gajim.connections[self.account].connected > 1:
			# clear all entries
			for e in entries:
				self.xml.get_widget(e + '_entry').set_text('')
			self.xml.get_widget('DESC_textview').get_buffer().set_text('')
			self.xml.get_widget('PHOTO_image').set_from_pixbuf(None)
			gajim.connections[self.account].request_vcard(self.jid)
		else:
			Error_dialog(_('You are not connected to the server'),
						_('Without a connection, you can not get your contact information.')).get_response()

	def change_to_vcard(self):
		self.xml.get_widget('information_notebook').remove_page(0)
		self.xml.get_widget('nickname_label').set_text('Personal details')
		information_hbuttonbox = self.xml.get_widget('information_hbuttonbox')
		#publish button
		button = gtk.Button(stock = gtk.STOCK_GOTO_TOP)
		button.get_children()[0].get_children()[0].get_children()[1].set_text(
			_('Publish'))
		button.connect('clicked', self.on_publish_button_clicked)
		button.show_all()
		information_hbuttonbox.pack_start(button)
		#retrieve button
		button = gtk.Button(stock = gtk.STOCK_GOTO_BOTTOM)
		button.get_children()[0].get_children()[0].get_children()[1].set_text(
			_('Retrieve'))
		button.connect('clicked', self.on_retrieve_button_clicked)
		button.show_all()
		information_hbuttonbox.pack_start(button)
		#close button at the end
		button = self.xml.get_widget('close_button')
		information_hbuttonbox.reorder_child(button, 2)
		#photo_vbuttonbox visible
		self.xml.get_widget('photo_vbuttonbox').show()
		
		#make all entries editable
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_HOME_USERID', 'URL',
			'TEL_HOME_NUMBER', 'N_FAMILY', 'N_GIVEN', 'N_MIDDLE', 'N_PREFIX',
			'N_SUFFIX', 'ADR_HOME_STREET', 'ADR_HOME_EXTADR', 'ADR_HOME_LOCALITY',
			'ADR_HOME_REGION', 'ADR_HOME_PCODE', 'ADR_HOME_CTRY', 'ORG_ORGNAME',
			'ORG_ORGUNIT', 'TITLE', 'ROLE', 'ADR_WORK_STREET', 'ADR_WORK_EXTADR',
			'ADR_WORK_LOCALITY', 'ADR_WORK_REGION', 'ADR_WORK_PCODE',
			'ADR_WORK_CTRY']
		for e in entries:
			self.xml.get_widget(e + '_entry').set_property('editable', True)

		description_textview = self.xml.get_widget('DESC_textview')
		description_textview.set_editable(True)
		description_textview.set_cursor_visible(True)

	#the user variable is the jid if vcard is true
	def __init__(self, user, plugin, account, vcard = False):
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'vcard_information_window', APP)
		self.window = self.xml.get_widget('vcard_information_window')
		self.xml.get_widget('photo_vbuttonbox').set_no_show_all(True)
		self.plugin = plugin
		self.user = user #don't use it if vcard is true
		self.account = account
		self.vcard = vcard
		self.avatar_mime_type = None
		self.avatar_encoded = None

		if vcard:
			self.jid = user
			self.change_to_vcard()
		else:
			self.jid = user.jid
			self.fill_jabber_page()

		self.xml.signal_autoconnect(self)
		self.window.show_all()
