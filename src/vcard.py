##	vcard.py (has VcardWindow class and a func get_avatar_pixbuf_encoded_mime)
##
## Copyright (C) 2003-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
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
import base64
import mimetypes
import os
import time
import locale

import gtkgui_helpers
import dialogs

from common import helpers
from common import gajim
from common import i18n
_ = i18n._
Q_ = i18n.Q_
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

def get_avatar_pixbuf_encoded_mime(photo):
	'''return the pixbuf of the image
	photo is a dictionary containing PHOTO information'''
	if not isinstance(photo, dict):
		return None, None, None
	img_decoded = None
	avatar_encoded = None
	avatar_mime_type = None
	if photo.has_key('BINVAL'):
		img_encoded = photo['BINVAL']
		avatar_encoded = img_encoded
		try:
			img_decoded = base64.decodestring(img_encoded)
		except:
			pass
	if img_decoded:
		if photo.has_key('TYPE'):
			avatar_mime_type = photo['TYPE']
			pixbuf = gtkgui_helpers.get_pixbuf_from_data(img_decoded)
		else:
			pixbuf, avatar_mime_type = gtkgui_helpers.get_pixbuf_from_data(
							img_decoded, want_type=True)
	else:
		pixbuf = None
	return pixbuf, avatar_encoded, avatar_mime_type

class VcardWindow:
	'''Class for contact's information window'''

	def __init__(self, contact, account, vcard = False, is_fake = False):
		# the contact variable is the jid if vcard is true
		self.xml = gtkgui_helpers.get_glade('vcard_information_window.glade')
		self.window = self.xml.get_widget('vcard_information_window')

		self.publish_button = self.xml.get_widget('publish_button')
		self.retrieve_button = self.xml.get_widget('retrieve_button')
		self.nickname_entry = self.xml.get_widget('nickname_entry')
		if not vcard: # Maybe gc_vcard ?
			self.nickname_entry.set_property('editable', False)

		self.publish_button.set_no_show_all(True)
		self.retrieve_button.set_no_show_all(True)
		self.xml.get_widget('photo_vbuttonbox').set_no_show_all(True)

		self.contact = contact # don't use it if vcard is true
		self.account = account
		self.vcard = vcard
		self.is_fake = is_fake
		self.avatar_mime_type = None
		self.avatar_encoded = None
		self.avatar_save_as_id = None

		if vcard: # we view/edit our own vcard
			self.jid = contact
			# remove Jabber tab & show publish/retrieve/close/set_avatar buttons
			# and make entries and textview editable
			self.change_to_vcard()
		else: # we see someone else's vcard
			self.publish_button.hide()
			self.retrieve_button.hide()
			self.jid = contact.jid
			self.fill_jabber_page()
			
			# if we are editing our own vcard publish button should publish
			# vcard data we have typed including nickname, it's why we connect only
			# here (when we see someone else's vcard)
			self.nickname_entry.connect('focus-out-event',
				self.on_nickname_entry_focus_out_event)

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_vcard_information_window_destroy(self, widget):
		del gajim.interface.instances[self.account]['infos'][self.jid]

	def on_vcard_information_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()

	def on_log_history_checkbutton_toggled(self, widget):
		#log conversation history?
		oldlog = True
		no_log_for = gajim.config.get_per('accounts', self.account,
			'no_log_for').split()
		if self.contact.jid in no_log_for:
			oldlog = False
		log = widget.get_active()
		if not log and not self.contact.jid in no_log_for:
			no_log_for.append(self.contact.jid)
		if log and self.contact.jid in no_log_for:
			no_log_for.remove(self.contact.jid)
		if oldlog != log:
			gajim.config.set_per('accounts', self.account, 'no_log_for',
				' '.join(no_log_for))
	
	def on_nickname_entry_focus_out_event(self, widget, event):
		'''Save contact information and update 
		the roster item on the Jabber server'''
		new_name = self.nickname_entry.get_text().decode('utf-8')
		# update contact.name with new nickname if that is not ''
		if new_name != self.contact.name and new_name != '':
			self.contact.name = new_name
			# update roster model
			model = gajim.interface.roster.tree.get_model()
			for iter_ in gajim.interface.roster.get_contact_iter(self.contact.jid,
				self.account):
				model[iter_][1] = new_name
			gajim.connections[self.account].update_contact(self.contact.jid,
				self.contact.name, self.contact.groups)
			# update opened chat window
			ctrl = gajim.interface.msg_win_mgr.get_control(self.contact.jid,
				self.account)
			if ctrl:
				ctrl.update_ui()
				win = gajim.interface.msg_win_mgr.get_window(self.contact.jid,
					self.account)
				win.redraw_tab(ctrl)
				win.show_title()

	def on_close_button_clicked(self, widget):		
		self.window.destroy()

	def on_clear_button_clicked(self, widget):
		# empty the image
		self.xml.get_widget('PHOTO_image').set_from_pixbuf(None)
		self.avatar_encoded = None
		if self.avatar_save_as_id:
			self.xml.get_widget('PHOTO_eventbox').disconnect(
						self.avatar_save_as_id)
			self.avatar_save_as_id = None

	def on_set_avatar_button_clicked(self, widget):
		f = None
		def on_ok(widget, path_to_file):
			filesize = os.path.getsize(path_to_file) # in bytes
			#FIXME: use messages for invalid file for 0.11
			invalid_file = False
			msg = ''
			if os.path.isfile(path_to_file):
				stat = os.stat(path_to_file)
				if stat[6] == 0:
					invalid_file = True
			else:
				invalid_file = True
			if not invalid_file and filesize > 16384: # 16 kb
				try:
					pixbuf = gtk.gdk.pixbuf_new_from_file(path_to_file)
					# get the image at 'notification size'
					# and use that user did not specify in ACE crazy size
					scaled_pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf,
						'tooltip')
				except gobject.GError, msg: # unknown format
					# msg should be string, not object instance
					msg = str(msg)
					invalid_file = True
			if invalid_file:
				if True: # keep identation
					dialogs.ErrorDialog(_('Could not load image'), msg)
					return
			if filesize > 16384:
					if scaled_pixbuf:
						path_to_file = os.path.join(gajim.TMP,
							'avatar_scaled.png')
						scaled_pixbuf.save(path_to_file, 'png')
			self.dialog.destroy()

			fd = open(path_to_file, 'rb')
			data = fd.read()
			pixbuf = gtkgui_helpers.get_pixbuf_from_data(data)
			# rescale it
			pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'vcard')
			image = self.xml.get_widget('PHOTO_image')
			image.set_from_pixbuf(pixbuf)
			self.avatar_encoded = base64.encodestring(data)
			# returns None if unknown type
			self.avatar_mime_type = mimetypes.guess_type(path_to_file)[0]

		self.dialog = dialogs.ImageChooserDialog(on_response_ok = on_ok)

	def on_PHOTO_eventbox_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3: # right click
			if self.vcard:
				# our own avatar
				account = None
				nick = gajim.config.get_per('accounts', self.account, 'name')
			else:
				account = self.account
				nick = self.contact.name
			menu = gtk.Menu()
			menuitem = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS)
			menuitem.connect('activate',
				gtkgui_helpers.on_avatar_save_as_menuitem_activate,
				self.jid, account, nick + '.jpeg')
			menu.append(menuitem)
			menu.show_all()
			menu.connect('selection-done', lambda w:w.destroy())	
			# show the menu
			menu.show_all()
			menu.popup(None, None, None, event.button, event.time)

	def set_value(self, entry_name, value):
		try:
			self.xml.get_widget(entry_name).set_text(value)
		except AttributeError:
			pass

	def set_values(self, vcard):
		for i in vcard.keys():
			if i == 'PHOTO':
				pixbuf, self.avatar_encoded, self.avatar_mime_type = \
					get_avatar_pixbuf_encoded_mime(vcard[i])
				if not pixbuf:
					continue
				image = self.xml.get_widget('PHOTO_image')
				pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'vcard')
				image.set_from_pixbuf(pixbuf)
				eventbox = self.xml.get_widget('PHOTO_eventbox')
				self.avatar_save_as_id = eventbox.connect('button-press-event',
					self.on_PHOTO_eventbox_button_press_event)
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

	def set_last_status_time(self):
		self.fill_status_label()

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

	def fill_status_label(self):
		contact_list = gajim.contacts.get_contact(self.account, self.contact.jid)
		# stats holds show and status message
		stats = ''
		one = True # Are we adding the first line ?
		if contact_list:
			for c in contact_list:
				if not one:
					stats += '\n'
				stats += helpers.get_uf_show(c.show)
				if c.status:
					stats += ': ' + c.status
				if c.last_status_time:
					stats += '\n' + _('since %s') % time.strftime('%c',
						c.last_status_time).decode(locale.getpreferredencoding())
				one = False
		elif not self.vcard: # Maybe gc_vcard ?
			stats = helpers.get_uf_show(self.contact.show)
			if self.contact.status:
				stats += ': ' + self.contact.status
		status_label = self.xml.get_widget('status_label')
		status_label.set_max_width_chars(15)
		status_label.set_text(stats)

		tip = gtk.Tooltips()
		status_label_eventbox = self.xml.get_widget('status_label_eventbox')
		tip.set_tip(status_label_eventbox, stats)

	def fill_jabber_page(self):
		tooltips = gtk.Tooltips()
		self.xml.get_widget('nickname_label').set_text(
			self.contact.get_shown_name())
		self.xml.get_widget('jid_label').set_text(self.contact.jid)
		uf_sub = helpers.get_uf_sub(self.contact.sub)
		self.xml.get_widget('subscription_label').set_text(uf_sub)
		eb = self.xml.get_widget('subscription_label_eventbox')
		if self.contact.sub == 'from':
			tt_text = _("This contact is interested in your presence information, but you are not interested in his/her presence")
		elif self.contact.sub == 'to':
			tt_text = _("You are interested in the contact's presence information, but he/she is not interested in yours")
		elif self.contact.sub == 'both':
			tt_text = _("You and the contact are interested in each other's presence information")
		else: # None
			tt_text = _("You are not interested in the contact's presence, and neither he/she is interested in yours")
		tooltips.set_tip(eb, tt_text)

		label = self.xml.get_widget('ask_label')
		uf_ask = helpers.get_uf_ask(self.contact.ask)
		label.set_text(uf_ask)
		eb = self.xml.get_widget('ask_label_eventbox')
		if self.contact.ask == 'subscribe':
			tooltips.set_tip(eb,
			_("You are waiting contact's answer about your subscription request"))
		self.nickname_entry.set_text(self.contact.name)
		log = True
		if self.contact.jid in gajim.config.get_per('accounts', self.account,
			'no_log_for').split(' '):
			log = False
		checkbutton = self.xml.get_widget('log_history_checkbutton')
		checkbutton.set_active(log)
		checkbutton.connect('toggled', self.on_log_history_checkbutton_toggled)
		
		resources = '%s (%s)' % (self.contact.resource, unicode(
			self.contact.priority))
		uf_resources = self.contact.resource + _(' resource with priority ')\
			+ unicode(self.contact.priority)
		if not self.contact.status:
			self.contact.status = ''

		# Request list time status
		gajim.connections[self.account].request_last_status_time(self.contact.jid,
			self.contact.resource)

		# Request os info in contact is connected
		if self.contact.show not in ('offline', 'error'):
			gajim.connections[self.account].request_os_info(self.contact.jid,
				self.contact.resource)
		self.os_info = {0: {'resource': self.contact.resource, 'client': '',
			'os': ''}}
		i = 1
		contact_list = gajim.contacts.get_contact(self.account, self.contact.jid)
		if contact_list:
			for c in contact_list:
				if c.resource != self.contact.resource:
					resources += '\n%s (%s)' % (c.resource,
						unicode(c.priority))
					uf_resources += '\n' + c.resource + \
						_(' resource with priority ') + unicode(c.priority)
					if c.show not in ('offline', 'error'):
						gajim.connections[self.account].request_os_info(c.jid,
							c.resource)
					gajim.connections[self.account].request_last_status_time(c.jid,
						c.resource)
					self.os_info[i] = {'resource': c.resource, 'client': '',
						'os': ''}
					i += 1
		self.xml.get_widget('resource_prio_label').set_text(resources)
		resource_prio_label_eventbox = self.xml.get_widget(
			'resource_prio_label_eventbox')
		tooltips.set_tip(resource_prio_label_eventbox, uf_resources)

		self.fill_status_label()

		gajim.connections[self.account].request_vcard(self.contact.jid, self.is_fake)

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
			dialogs.ErrorDialog(_('You are not connected to the server'),
        		_('Without a connection you can not publish your contact '
        		'information.'))
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
			if self.avatar_save_as_id:
				self.xml.get_widget('PHOTO_eventbox').disconnect(
					self.avatar_save_as_id)
				self.avatar_save_as_id = None
			gajim.connections[self.account].request_vcard(self.jid)
		else:
			dialogs.ErrorDialog(_('You are not connected to the server'),
  		    	_('Without a connection, you can not get your contact information.'))

	def change_to_vcard(self):
		self.xml.get_widget('information_notebook').remove_page(0)
		self.xml.get_widget('nickname_label').set_text(_('Personal details'))
		
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
