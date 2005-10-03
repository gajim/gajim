##	vcard.py (has VcardWindow class)
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
import gobject
import urllib
import base64
import mimetypes
import os
import sys
import dialogs
import gtkgui_helpers

from common import helpers
from common import gajim
from common import i18n
_ = i18n._
Q_ = i18n.Q_
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

GTKGUI_GLADE = 'gtkgui.glade'

class VcardWindow:
	'''Class for contact's information window'''

	def __init__(self, contact, plugin, account, vcard = False):
		#the contact variable is the jid if vcard is true
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'vcard_information_window', APP)
		self.window = self.xml.get_widget('vcard_information_window')
		self.xml.get_widget('photo_vbuttonbox').set_no_show_all(True)
		
		self.publish_button = self.xml.get_widget('publish_button')
		self.retrieve_button = self.xml.get_widget('retrieve_button')
		self.publish_button.set_no_show_all(True)
		self.retrieve_button.set_no_show_all(True)
		
		self.plugin = plugin
		self.contact = contact #don't use it if vcard is true
		self.account = account
		self.vcard = vcard
		self.avatar_mime_type = None
		self.avatar_encoded = None

		if vcard:
			self.jid = contact
			# remove Jabber tab & show publish/retrieve/set_avatar buttons
			self.change_to_vcard()
		else:
			self.jid = contact.jid
			self.publish_button.hide()
			self.retrieve_button.hide()
			self.fill_jabber_page()

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_vcard_information_window_destroy(self, widget = None):
		del self.plugin.windows[self.account]['infos'][self.jid]

	def on_vcard_information_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()

	def on_close_button_clicked(self, widget):
		'''Save contact information and update the roster on the Jabber server'''
		if self.vcard:
			self.window.destroy()
			return
		#update contact.name if it's not ''
		name_entry = self.xml.get_widget('nickname_entry')
		new_name = name_entry.get_text().decode('utf-8')
		if new_name != self.contact.name and new_name != '':
			self.contact.name = new_name
			for i in self.plugin.roster.get_contact_iter(self.contact.jid, self.account):
				self.plugin.roster.tree.get_model().set_value(i, 1, new_name)
			gajim.connections[self.account].update_contact(self.contact.jid,
				self.contact.name, self.contact.groups)
		#log history ?
		oldlog = True
		no_log_for = gajim.config.get_per('accounts', self.account,
			'no_log_for').split()
		if self.contact.jid in no_log_for:
			oldlog = False
		log = self.xml.get_widget('log_checkbutton').get_active()
		if not log and not self.contact.jid in no_log_for:
			no_log_for.append(self.contact.jid)
		if log and self.contact.jid in no_log_for:
			no_log_for.remove(self.contact.jid)
		if oldlog != log:
			gajim.config.set_per('accounts', self.account, 'no_log_for',
				' '.join(no_log_for))
		self.window.destroy()

	def on_clear_button_clicked(self, widget):
		# empty the image
		self.xml.get_widget('PHOTO_image').set_from_pixbuf(None)
		self.avatar_encoded = None

	def image_is_ok(self, image):
		if not os.path.exists(image):
			return False
		return True

	def update_preview(self, widget):
		path_to_file = widget.get_preview_filename()
		if path_to_file is None or os.path.isdir(path_to_file):
			# nothing to preview or directory
			# make sure you clean image do show nothing
			widget.get_preview_widget().set_from_file(None)
			return
		try:
			pixbuf = gtk.gdk.pixbuf_new_from_file_at_size(path_to_file, 100, 100)
		except gobject.GError:
			return
		widget.get_preview_widget().set_from_pixbuf(pixbuf)

	def on_set_avatar_button_clicked(self, widget):
		f = None
		dialog = gtk.FileChooserDialog(_('Choose Avatar'), None,
			gtk.FILE_CHOOSER_ACTION_OPEN,
			(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL,
			gtk.STOCK_OPEN, gtk.RESPONSE_OK))
		dialog.set_default_response(gtk.RESPONSE_OK)
		filtr = gtk.FileFilter()
		filtr.set_name(_('All files'))
		filtr.add_pattern('*')
		dialog.add_filter(filtr)

		filtr = gtk.FileFilter()
		filtr.set_name(_('Images'))
		filtr.add_mime_type('image/png')
		filtr.add_mime_type('image/jpeg')
		filtr.add_mime_type('image/gif')
		filtr.add_pattern('*.png')
		filtr.add_pattern('*.jpg')
		filtr.add_pattern('*.gif')
		filtr.add_pattern('*.tif')
		filtr.add_pattern('*.xpm')
		dialog.add_filter(filtr)
		dialog.set_filter(filtr)
		dialog.set_use_preview_label(False)
		dialog.set_preview_widget(gtk.Image())
		dialog.connect('selection-changed', self.update_preview)

		ok = False
		while not ok:
			response = dialog.run()
			if response == gtk.RESPONSE_OK:
				f = dialog.get_filename()
				f = f.decode(sys.getfilesystemencoding())
				if self.image_is_ok(f):
					ok = True
			else:
				ok = True
		dialog.destroy()

		if f:
			filesize = os.path.getsize(f) # in bytes
			if filesize > 8192: # 8 kb
				dialogs.ErrorDialog(_('The filesize of image "%s" is too large')\
					% os.path.basename(f),
					_('The file must not be more than 8 kilobytes.')).get_response()
				return
			fd = open(f, 'rb')
			data = fd.read()
			pixbuf = gtkgui_helpers.get_pixbuf_from_data(data)
			image = self.xml.get_widget('PHOTO_image')
			image.set_from_pixbuf(pixbuf)
			self.avatar_encoded = base64.encodestring(data)
			# returns None if unknown type
			self.avatar_mime_type = mimetypes.guess_type(f)[0]

	def set_value(self, entry_name, value):
		try:
			self.xml.get_widget(entry_name).set_text(value)
		except AttributeError:
			pass

	def set_values(self, vcard):
		for i in vcard.keys():
			if i == 'PHOTO':
				if not isinstance(vcard[i], dict):
					continue
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
					pixbuf = gtkgui_helpers.get_pixbuf_from_data(img_decoded)
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
			if isinstance(vcard[i], dict):
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
			if not self.os_info[i]['resource'] or \
					self.os_info[i]['resource'] == resource:
				self.os_info[i]['client'] = client_info
				self.os_info[i]['os'] = os_info
			if i > 0:
				client += '\n'
				os += '\n'
			client += self.os_info[i]['client']
			os += self.os_info[i]['os']
			i += 1

		if client == '':
			client = Q_('?Client:Unknown')
		if os == '':
			os = Q_('?OS:Unknown')
		self.xml.get_widget('client_name_version_label').set_text(client)
		self.xml.get_widget('os_label').set_text(os)

	def fill_jabber_page(self):
		self.xml.get_widget('nickname_label').set_text(self.contact.name)
		self.xml.get_widget('jid_label').set_text(self.contact.jid)
		uf_sub = helpers.get_uf_sub(self.contact.sub)
		self.xml.get_widget('subscription_label').set_text(uf_sub)
		label = self.xml.get_widget('ask_label')
		
		uf_ask = helpers.get_uf_ask(self.contact.ask)
		label.set_text(uf_ask)
		self.xml.get_widget('nickname_entry').set_text(self.contact.name)
		log = 1
		if self.contact.jid in gajim.config.get_per('accounts', self.account,
			'no_log_for').split(' '):
			log = 0
		self.xml.get_widget('log_checkbutton').set_active(log)
		resources = '%s (%s)' % (self.contact.resource, unicode(
			self.contact.priority))
		uf_resources = self.contact.resource + _(' resource with priority ')\
			+ unicode(self.contact.priority)
		if not self.contact.status:
			self.contact.status = ''
		
		# stats holds show and status message
		stats = helpers.get_uf_show(self.contact.show)
		if self.contact.status:
			stats += ': ' + self.contact.status
		gajim.connections[self.account].request_os_info(self.contact.jid,
			self.contact.resource)
		self.os_info = {0: {'resource': self.contact.resource, 'client': '',
			'os': ''}}
		i = 1
		if gajim.contacts[self.account].has_key(self.contact.jid):
			for c in gajim.contacts[self.account][self.contact.jid]:
				if c.resource != self.contact.resource:
					resources += '\n%s (%s)' % (c.resource,
						unicode(c.priority))
					uf_resources += '\n' + c.resource + _(' resource with priority ')\
						+ unicode(c.priority)
					if not c.status:
						c.status = ''
					stats += '\n' + c.show + ': ' + c.status
					gajim.connections[self.account].request_os_info(self.contact.jid,
						c.resource)
					self.os_info[i] = {'resource': c.resource, 'client': '',
						'os': ''}
					i += 1
		self.xml.get_widget('resource_prio_label').set_text(resources)
		tip = gtk.Tooltips()
		resource_prio_label_eventbox = self.xml.get_widget(
			'resource_prio_label_eventbox')
		tip.set_tip(resource_prio_label_eventbox, uf_resources)
		
		tip = gtk.Tooltips()
		status_label_eventbox = self.xml.get_widget('status_label_eventbox')
		tip.set_tip(status_label_eventbox, stats)
		status_label = self.xml.get_widget('status_label')
		status_label.set_max_width_chars(15)
		status_label.set_text(stats)
		
		gajim.connections[self.account].request_vcard(self.contact.jid)

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
			'ORG_ORGUNIT', 'TITLE', 'ROLE', 'TEL_WORK_NUMBER', 'EMAIL_WORK_USERID',
			'ADR_WORK_STREET', 'ADR_WORK_EXTADR', 'ADR_WORK_LOCALITY',
			'ADR_WORK_REGION', 'ADR_WORK_PCODE', 'ADR_WORK_CTRY']
		vcard = {}
		for e in entries: 
			txt = self.xml.get_widget(e + '_entry').get_text().decode('utf-8')
			if txt != '':
				vcard = self.add_to_vcard(vcard, e, txt)

		# DESC textview
		buff = self.xml.get_widget('DESC_textview').get_buffer()
		start_iter = buff.get_start_iter()
		end_iter = buff.get_end_iter()
		txt = buff.get_text(start_iter, end_iter, 0)
		if txt != '':
			vcard['DESC'] = txt.decode('utf-8')

		# Avatar
		if self.avatar_encoded:
			vcard['PHOTO'] = {'BINVAL': self.avatar_encoded}
			if self.avatar_mime_type:
				vcard['PHOTO']['TYPE'] = self.avatar_mime_type
		return vcard

	def on_publish_button_clicked(self, widget):
		if gajim.connections[self.account].connected < 2:
			ErrorDialog(_('You are not connected to the server'),
                    _('Without a connection you can not publish your contact information.')).get_response()
			return
		vcard = self.make_vcard()
		nick = ''
		if vcard.has_key('NICKNAME'):
			nick = vcard['NICKNAME']
		if nick == '':
			nick = gajim.config.get_per('accounts', self.account, 'name')
		gajim.nicks[self.account] = nick
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
			ErrorDialog(_('You are not connected to the server'),
						_('Without a connection, you can not get your contact information.')).get_response()

	def change_to_vcard(self):
		self.xml.get_widget('information_notebook').remove_page(0)
		self.xml.get_widget('nickname_label').set_text('Personal details')
		
		self.publish_button.show()
		self.retrieve_button.show()
		
		#photo_vbuttonbox visible
		self.xml.get_widget('photo_vbuttonbox').show()
		
		#make all entries editable
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_HOME_USERID', 'URL',
			'TEL_HOME_NUMBER', 'N_FAMILY', 'N_GIVEN', 'N_MIDDLE', 'N_PREFIX',
			'N_SUFFIX', 'ADR_HOME_STREET', 'ADR_HOME_EXTADR', 'ADR_HOME_LOCALITY',
			'ADR_HOME_REGION', 'ADR_HOME_PCODE', 'ADR_HOME_CTRY', 'ORG_ORGNAME',
			'ORG_ORGUNIT', 'TITLE', 'ROLE', 'TEL_WORK_NUMBER', 'EMAIL_WORK_USERID',
			'ADR_WORK_STREET', 'ADR_WORK_EXTADR', 'ADR_WORK_LOCALITY',
			'ADR_WORK_REGION', 'ADR_WORK_PCODE', 'ADR_WORK_CTRY']
		for e in entries:
			self.xml.get_widget(e + '_entry').set_property('editable', True)

		description_textview = self.xml.get_widget('DESC_textview')
		description_textview.set_editable(True)
		description_textview.set_cursor_visible(True)
