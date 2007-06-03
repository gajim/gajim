##	vcard.py (has VcardWindow class and a func get_avatar_pixbuf_encoded_mime)
##
## Copyright (C) 2003-2006 Yann Le Boulanger <asterix@lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem@gmail.com>
## Copyright (C) 2006 Stefan Bethge <stefan@lanpartei.de>
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

# THIS FILE IS FOR **OTHERS'** PROFILE (when we VIEW their INFO)

import gtk
import gobject
import base64
import time
import locale
import os

import gtkgui_helpers
import dialogs
import message_control

from common import helpers
from common import gajim
from common.i18n import Q_

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

	def __init__(self, contact, account, gc_contact = None):
		# the contact variable is the jid if vcard is true
		self.xml = gtkgui_helpers.get_glade('vcard_information_window.glade')
		self.window = self.xml.get_widget('vcard_information_window')
		self.progressbar = self.xml.get_widget('progressbar')

		self.contact = contact
		self.account = account
		self.gc_contact = gc_contact

		self.xml.get_widget('no_user_avatar_label').set_no_show_all(True)
		self.xml.get_widget('no_user_avatar_label').hide()
		self.xml.get_widget('PHOTO_image').set_no_show_all(True)
		self.xml.get_widget('PHOTO_image').hide()
		image = gtk.Image()
		self.photo_button = self.xml.get_widget('PHOTO_button')
		self.photo_button.set_image(image)
		self.nophoto_button = self.xml.get_widget('NOPHOTO_button')
		puny_jid = helpers.sanitize_filename(contact.jid)
		local_avatar_basepath = os.path.join(gajim.AVATAR_PATH, puny_jid) + \
			'_local'
		for extension in ('.png', '.jpeg'):
			local_avatar_path = local_avatar_basepath + extension
			if os.path.isfile(local_avatar_path):
				image.set_from_file(local_avatar_path)
				self.nophoto_button.set_no_show_all(True)
				self.nophoto_button.hide()
				break
		else:
			self.photo_button.set_no_show_all(True)
			self.photo_button.hide()
		self.avatar_mime_type = None
		self.avatar_encoded = None
		self.vcard_arrived = False
		self.os_info_arrived = False
		self.update_progressbar_timeout_id = gobject.timeout_add(100,
			self.update_progressbar)

		self.fill_jabber_page()
		annotations = gajim.connections[self.account].annotations
		if self.contact.jid in annotations:
			buffer = self.xml.get_widget('textview_annotation').get_buffer()
			buffer.set_text(annotations[self.contact.jid])

		self.xml.signal_autoconnect(self)
		self.window.show_all()
		self.xml.get_widget('close_button').grab_focus()

	def update_progressbar(self):
		self.progressbar.pulse()
		return True # loop forever

	def update_avatar_in_gui(self):
		jid = self.contact.jid
		# Update roster
		gajim.interface.roster.draw_avatar(jid, self.account)
		# Update chat window
		if gajim.interface.msg_win_mgr.has_window(jid, self.account):
			win = gajim.interface.msg_win_mgr.get_window(jid, self.account)
			ctrl = win.get_control(jid, self.account)
			if win and ctrl.type_id != message_control.TYPE_GC:
				ctrl.show_avatar()

	def on_NOPHOTO_button_clicked(self, button):
		def on_ok(widget, path_to_file):
			filesize = os.path.getsize(path_to_file) # in bytes
			invalid_file = False
			msg = ''
			if os.path.isfile(path_to_file):
				stat = os.stat(path_to_file)
				if stat[6] == 0:
					invalid_file = True
					msg = _('File is empty')
			else:
				invalid_file = True
				msg = _('File does not exist')
			if invalid_file:
				dialogs.ErrorDialog(_('Could not load image'), msg)
				return
			try:
				pixbuf = gtk.gdk.pixbuf_new_from_file(path_to_file)
				if filesize > 16384: # 16 kb
					# get the image at 'notification size'
					# and hope that user did not specify in ACE crazy size
					pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'tooltip')
			except gobject.GError, msg: # unknown format
				# msg should be string, not object instance
				msg = str(msg)
				dialogs.ErrorDialog(_('Could not load image'), msg)
				return
			puny_jid = helpers.sanitize_filename(self.contact.jid)
			path_to_file = os.path.join(gajim.AVATAR_PATH, puny_jid) + '_local.png'
			pixbuf.save(path_to_file, 'png')
			self.dialog.destroy()
			self.update_avatar_in_gui()

			# rescale it
			pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'vcard')
			image = self.photo_button.get_image()
			image.set_from_pixbuf(pixbuf)
			self.photo_button.show()
			self.nophoto_button.hide()

		def on_clear(widget):
			self.dialog.destroy()
			self.on_clear_button_clicked(widget)

		self.dialog = dialogs.AvatarChooserDialog(on_response_ok = on_ok,
			on_response_clear = on_clear)

	def on_clear_button_clicked(self, widget):
		# empty the image
		image = self.photo_button.get_image()
		image.set_from_pixbuf(None)
		self.photo_button.hide()
		self.nophoto_button.show()
		# Delete file:
		puny_jid = helpers.sanitize_filename(self.contact.jid)
		path_to_file = os.path.join(gajim.AVATAR_PATH, puny_jid) + '_local.png'
		try:
			os.remove(path_to_file)
		except OSError:
			gajim.log.debug('Cannot remove %s' % path_to_file)
		self.update_avatar_in_gui()

	def on_PHOTO_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3 and self.avatar_encoded: # right click
			menu = gtk.Menu()

			# Try to get pixbuf
#			pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(self.jid)

#			if pixbuf:
#				nick = self.contact.get_shown_name()
#				menuitem = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS)
#				menuitem.connect('activate',
#					gtkgui_helpers.on_avatar_save_as_menuitem_activate, self.jid,
#					None, nick + '.jpeg')
#				menu.append(menuitem)
			# show clear
			menuitem = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
			menuitem.connect('activate', self.on_clear_button_clicked)
			menu.append(menuitem)
			menu.connect('selection-done', lambda w:w.destroy())
			# show the menu
			menu.show_all()
			menu.popup(None, None, None, event.button, event.time)
		elif event.button == 1: # left click
			self.on_NOPHOTO_button_clicked(widget)

	def on_vcard_information_window_destroy(self, widget):
		if self.update_progressbar_timeout_id is not None:
			gobject.source_remove(self.update_progressbar_timeout_id)
		del gajim.interface.instances[self.account]['infos'][self.contact.jid]
		buffer = self.xml.get_widget('textview_annotation').get_buffer()
		annotation = buffer.get_text(buffer.get_start_iter(),
			buffer.get_end_iter())
		connection = gajim.connections[self.account]
		if annotation != connection.annotations.get(self.contact.jid, ''):
			connection.annotations[self.contact.jid] = annotation
			connection.store_annotations()

	def on_vcard_information_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()

	def on_PHOTO_eventbox_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3: # right click
			menu = gtk.Menu()
			menuitem = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS)
			menuitem.connect('activate',
				gtkgui_helpers.on_avatar_save_as_menuitem_activate,
				self.contact.jid, self.account, self.contact.get_shown_name() +
				'.jpeg')
			menu.append(menuitem)
			menu.connect('selection-done', lambda w:w.destroy())	
			# show the menu
			menu.show_all()
			menu.popup(None, None, None, event.button, event.time)

	def set_value(self, entry_name, value):
		try:
			if value and entry_name == 'URL_label':
				if gtk.pygtk_version >= (2, 10, 0) and gtk.gtk_version >= (2, 10, 0):
					widget = gtk.LinkButton(value, value)
				else:
					widget = gtk.Label(value)
					widget.set_selectable(True)
				widget.show()
				table = self.xml.get_widget('personal_info_table')
				table.attach(widget, 1, 4, 3, 4, yoptions = 0)
			else:
				self.xml.get_widget(entry_name).set_text(value)
		except AttributeError:
			pass

	def set_values(self, vcard):
		if not 'PHOTO' in vcard:
			self.xml.get_widget('no_user_avatar_label').show()
		for i in vcard.keys():
			if i == 'PHOTO' and self.xml.get_widget('information_notebook').\
			get_n_pages() > 4:
				pixbuf, self.avatar_encoded, self.avatar_mime_type = \
					get_avatar_pixbuf_encoded_mime(vcard[i])
				image = self.xml.get_widget('PHOTO_image')
				image.show()
				if not pixbuf:
					image.set_from_icon_name('stock_person',
						gtk.ICON_SIZE_DIALOG)
					continue
				pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'vcard')
				image.set_from_pixbuf(pixbuf)
				continue
			if i in ('ADR', 'TEL', 'EMAIL'):
				for entry in vcard[i]:
					add_on = '_HOME'
					if 'WORK' in entry:
						add_on = '_WORK'
					for j in entry.keys():
						self.set_value(i + add_on + '_' + j + '_label', entry[j])
			if isinstance(vcard[i], dict):
				for j in vcard[i].keys():
					self.set_value(i + '_' + j + '_label', vcard[i][j])
			else:
				if i == 'DESC':
					self.xml.get_widget('DESC_textview').get_buffer().set_text(
						vcard[i], 0)
				elif i != 'jid': # Do not override jid_label
					self.set_value(i + '_label', vcard[i])
		self.vcard_arrived = True
		self.test_remove_progressbar()

	def test_remove_progressbar(self):
		if self.update_progressbar_timeout_id is not None and \
		self.vcard_arrived and self.os_info_arrived:
			gobject.source_remove(self.update_progressbar_timeout_id)
			self.progressbar.hide()
			self.update_progressbar_timeout_id = None

	def set_last_status_time(self):
		self.fill_status_label()

	def set_os_info(self, resource, client_info, os_info):
		if self.xml.get_widget('information_notebook').get_n_pages() < 5:
			return
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
		self.os_info_arrived = True
		self.test_remove_progressbar()

	def fill_status_label(self):
		if self.xml.get_widget('information_notebook').get_n_pages() < 5:
			return
		contact_list = gajim.contacts.get_contact(self.account, self.contact.jid)
		connected_contact_list = []
		for c in contact_list:
			if c.show not in ('offline', 'error'):
				connected_contact_list.append(c)
		if not connected_contact_list:
			# no connected contact, get the offline one
			connected_contact_list = contact_list
		# stats holds show and status message
		stats = ''
		one = True # Are we adding the first line ?
		if connected_contact_list:
			for c in connected_contact_list:
				if not one:
					stats += '\n'
				stats += helpers.get_uf_show(c.show)
				if c.status:
					stats += ': ' + c.status
				if c.last_status_time:
					stats += '\n' + _('since %s') % time.strftime('%c',
						c.last_status_time).decode(locale.getpreferredencoding())
				one = False
		else: # Maybe gc_vcard ?
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
		self.xml.get_widget('nickname_label').set_markup(
			'<b><span size="x-large">' +
			self.contact.get_shown_name() +
			'</span></b>')
		self.xml.get_widget('jid_label').set_text(self.contact.jid)
		
		subscription_label = self.xml.get_widget('subscription_label')
		ask_label = self.xml.get_widget('ask_label')
		if self.gc_contact:
			self.xml.get_widget('subscription_title_label').set_text(_("Role:"))
			uf_role = helpers.get_uf_role(self.gc_contact.role)
			subscription_label.set_text(uf_role)

			self.xml.get_widget('ask_title_label').set_text(_("Affiliation:"))
			uf_affiliation = helpers.get_uf_affiliation(self.gc_contact.affiliation)
			ask_label.set_text(uf_affiliation)
		else:
			uf_sub = helpers.get_uf_sub(self.contact.sub)
			subscription_label.set_text(uf_sub)
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

			uf_ask = helpers.get_uf_ask(self.contact.ask)
			ask_label.set_text(uf_ask)
			eb = self.xml.get_widget('ask_label_eventbox')
			if self.contact.ask == 'subscribe':
				tooltips.set_tip(eb,
				_("You are waiting contact's answer about your subscription request"))

		resources = '%s (%s)' % (self.contact.resource, unicode(
			self.contact.priority))
		uf_resources = self.contact.resource + _(' resource with priority ')\
			+ unicode(self.contact.priority)
		if not self.contact.status:
			self.contact.status = ''

		# Request list time status
		gajim.connections[self.account].request_last_status_time(self.contact.jid,
			self.contact.resource)

		# do not wait for os_info if contact is not connected or has error
		# additional check for observer is needed, as show is offline for him
		if self.contact.show in ('offline', 'error')\
		and not self.contact.is_observer():
			self.os_info_arrived = True
		else: # Request os info if contact is connected
			gobject.idle_add(gajim.connections[self.account].request_os_info,
				self.contact.jid, self.contact.resource)
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
						gobject.idle_add(
							gajim.connections[self.account].request_os_info, c.jid,
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

		if self.gc_contact:
			gajim.connections[self.account].request_vcard(self.contact.jid,
				self.gc_contact.get_full_jid())
		else:
			gajim.connections[self.account].request_vcard(self.contact.jid)

	def on_close_button_clicked(self, widget):
		self.window.destroy()


class ZeroconfVcardWindow:
	def __init__(self, contact, account, is_fake = False):
		# the contact variable is the jid if vcard is true
		self.xml = gtkgui_helpers.get_glade('zeroconf_information_window.glade')
		self.window = self.xml.get_widget('zeroconf_information_window')

		self.contact = contact
		self.account = account
		self.is_fake = is_fake

	#	self.avatar_mime_type = None
	#	self.avatar_encoded = None

		self.fill_contact_page()
		self.fill_personal_page()

		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def on_zeroconf_information_window_destroy(self, widget):
		del gajim.interface.instances[self.account]['infos'][self.contact.jid]

	def on_zeroconf_information_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()

	def on_PHOTO_eventbox_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3: # right click
			menu = gtk.Menu()
			menuitem = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS)
			menuitem.connect('activate',
				gtkgui_helpers.on_avatar_save_as_menuitem_activate,
				self.contact.jid, self.account, self.contact.get_shown_name() +
				'.jpeg')
			menu.append(menuitem)
			menu.connect('selection-done', lambda w:w.destroy())	
			# show the menu
			menu.show_all()
			menu.popup(None, None, None, event.button, event.time)

	def set_value(self, entry_name, value):
		try:
			if value and entry_name == 'URL_label':
				if gtk.pygtk_version >= (2, 10, 0) and gtk.gtk_version >= (2, 10, 0):
					widget = gtk.LinkButton(value, value)
				else:
					widget = gtk.Label(value)
					widget.set_selectable(True)
				table = self.xml.get_widget('personal_info_table')
				table.attach(widget, 1, 4, 3, 4, yoptions = 0)
			else:
				self.xml.get_widget(entry_name).set_text(value)
		except AttributeError:
			pass

	def fill_status_label(self):
		if self.xml.get_widget('information_notebook').get_n_pages() < 2:
			return
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
		else: # Maybe gc_vcard ?
			stats = helpers.get_uf_show(self.contact.show)
			if self.contact.status:
				stats += ': ' + self.contact.status
		status_label = self.xml.get_widget('status_label')
		status_label.set_max_width_chars(15)
		status_label.set_text(stats)

		tip = gtk.Tooltips()
		status_label_eventbox = self.xml.get_widget('status_label_eventbox')
		tip.set_tip(status_label_eventbox, stats)
	
	def fill_contact_page(self):
		tooltips = gtk.Tooltips()
		self.xml.get_widget('nickname_label').set_markup(
			'<b><span size="x-large">' +
			self.contact.get_shown_name() +
			'</span></b>')
		self.xml.get_widget('local_jid_label').set_text(self.contact.jid)

		resources = '%s (%s)' % (self.contact.resource, unicode(
			self.contact.priority))
		uf_resources = self.contact.resource + _(' resource with priority ')\
			+ unicode(self.contact.priority)
		if not self.contact.status:
			self.contact.status = ''

		# Request list time status
	#	gajim.connections[self.account].request_last_status_time(self.contact.jid,
	#		self.contact.resource)

		self.xml.get_widget('resource_prio_label').set_text(resources)
		resource_prio_label_eventbox = self.xml.get_widget(
			'resource_prio_label_eventbox')
		tooltips.set_tip(resource_prio_label_eventbox, uf_resources)

		self.fill_status_label()

	#	gajim.connections[self.account].request_vcard(self.contact.jid, self.is_fake)
	
	def fill_personal_page(self):
		contact = gajim.connections[gajim.ZEROCONF_ACC_NAME].roster.getItem(self.contact.jid)
		for key in ('1st', 'last', 'jid', 'email'):
			if not contact['txt_dict'].has_key(key):
				contact['txt_dict'][key] = ''
		self.xml.get_widget('first_name_label').set_text(contact['txt_dict']['1st'])
		self.xml.get_widget('last_name_label').set_text(contact['txt_dict']['last'])
		self.xml.get_widget('jabber_id_label').set_text(contact['txt_dict']['jid'])
		self.xml.get_widget('email_label').set_text(contact['txt_dict']['email'])

	def on_close_button_clicked(self, widget):
		self.window.destroy()
