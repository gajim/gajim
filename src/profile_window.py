# -*- coding:utf-8 -*-
## src/profile_window.py
##
## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

# THIS FILE IS FOR **OUR** PROFILE (when we edit our INFO)

import gtk
import gobject
import base64
import mimetypes
import os

import gtkgui_helpers
import dialogs
import vcard

from common import gajim


class ProfileWindow:
	'''Class for our information window'''

	def __init__(self, account):
		self.xml = gtkgui_helpers.get_glade('profile_window.glade')
		self.window = self.xml.get_widget('profile_window')
		self.progressbar = self.xml.get_widget('progressbar')
		self.statusbar = self.xml.get_widget('statusbar')
		self.context_id = self.statusbar.get_context_id('profile')

		self.account = account
		self.jid = gajim.get_jid_from_account(account)

		self.dialog = None
		self.avatar_mime_type = None
		self.avatar_encoded = None
		self.message_id = self.statusbar.push(self.context_id,
			_('Retrieving profile...'))
		self.update_progressbar_timeout_id = gobject.timeout_add(100,
			self.update_progressbar)
		self.remove_statusbar_timeout_id = None

		# Create Image for avatar button
		image = gtk.Image()
		self.xml.get_widget('PHOTO_button').set_image(image)
		self.xml.signal_autoconnect(self)
		self.window.show_all()

	def update_progressbar(self):
		self.progressbar.pulse()
		return True # loop forever

	def remove_statusbar(self, message_id):
		self.statusbar.remove(self.context_id, message_id)
		self.remove_statusbar_timeout_id = None

	def on_profile_window_destroy(self, widget):
		if self.update_progressbar_timeout_id is not None:
			gobject.source_remove(self.update_progressbar_timeout_id)
		if self.remove_statusbar_timeout_id is not None:
			gobject.source_remove(self.remove_statusbar_timeout_id)
		del gajim.interface.instances[self.account]['profile']
		if self.dialog: # Image chooser dialog
			self.dialog.destroy()

	def on_profile_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.window.destroy()

	def on_clear_button_clicked(self, widget):
		# empty the image
		button = self.xml.get_widget('PHOTO_button')
		image = button.get_image()
		image.set_from_pixbuf(None)
		button.hide()
		text_button = self.xml.get_widget('NOPHOTO_button')
		text_button.show()
		self.avatar_encoded = None
		self.avatar_mime_type = None

	def on_set_avatar_button_clicked(self, widget):
		def on_ok(widget, path_to_file):
			must_delete = False
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
			if not invalid_file and filesize > 16384: # 16 kb
				try:
					pixbuf = gtk.gdk.pixbuf_new_from_file(path_to_file)
					# get the image at 'notification size'
					# and hope that user did not specify in ACE crazy size
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
						must_delete = True

			fd = open(path_to_file, 'rb')
			data = fd.read()
			pixbuf = gtkgui_helpers.get_pixbuf_from_data(data)
			try:
				# rescale it
				pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'vcard')
			except AttributeError: # unknown format
				dialogs.ErrorDialog(_('Could not load image'))
				return
			self.dialog.destroy()
			self.dialog = None
			button = self.xml.get_widget('PHOTO_button')
			image = button.get_image()
			image.set_from_pixbuf(pixbuf)
			button.show()
			text_button = self.xml.get_widget('NOPHOTO_button')
			text_button.hide()
			self.avatar_encoded = base64.encodestring(data)
			# returns None if unknown type
			self.avatar_mime_type = mimetypes.guess_type(path_to_file)[0]
			if must_delete:
				try:
					os.remove(path_to_file)
				except OSError:
					gajim.log.debug('Cannot remove %s' % path_to_file)

		def on_clear(widget):
			self.dialog.destroy()
			self.dialog = None
			self.on_clear_button_clicked(widget)

		def on_cancel(widget):
			self.dialog.destroy()
			self.dialog = None

		if self.dialog:
			self.dialog.present()
		else:
			self.dialog = dialogs.AvatarChooserDialog(on_response_ok = on_ok,
				on_response_cancel = on_cancel, on_response_clear = on_clear)

	def on_PHOTO_button_press_event(self, widget, event):
		'''If right-clicked, show popup'''
		if event.button == 3 and self.avatar_encoded: # right click
			menu = gtk.Menu()

			# Try to get pixbuf
			pixbuf = gtkgui_helpers.get_avatar_pixbuf_from_cache(self.jid,
				use_local = False)

			if pixbuf:
				nick = gajim.config.get_per('accounts', self.account, 'name')
				menuitem = gtk.ImageMenuItem(gtk.STOCK_SAVE_AS)
				menuitem.connect('activate',
					gtkgui_helpers.on_avatar_save_as_menuitem_activate,
					self.jid, None, nick + '.jpeg')
				menu.append(menuitem)
			# show clear
			menuitem = gtk.ImageMenuItem(gtk.STOCK_CLEAR)
			menuitem.connect('activate', self.on_clear_button_clicked)
			menu.append(menuitem)
			menu.connect('selection-done', lambda w:w.destroy())
			# show the menu
			menu.show_all()
			menu.popup(None, None, None, event.button, event.time)
		elif event.button == 1: # left click
			self.on_set_avatar_button_clicked(widget)

	def set_value(self, entry_name, value):
		try:
			self.xml.get_widget(entry_name).set_text(value)
		except AttributeError:
			pass

	def set_values(self, vcard_):
		button = self.xml.get_widget('PHOTO_button')
		image = button.get_image()
		text_button = self.xml.get_widget('NOPHOTO_button')
		if not 'PHOTO' in vcard_:
			# set default image
			image.set_from_pixbuf(None)
			button.hide()
			text_button.show()
		for i in vcard_.keys():
			if i == 'PHOTO':
				pixbuf, self.avatar_encoded, self.avatar_mime_type = \
					vcard.get_avatar_pixbuf_encoded_mime(vcard_[i])
				if not pixbuf:
					image.set_from_pixbuf(None)
					button.hide()
					text_button.show()
					continue
				pixbuf = gtkgui_helpers.get_scaled_pixbuf(pixbuf, 'vcard')
				image.set_from_pixbuf(pixbuf)
				button.show()
				text_button.hide()
				continue
			if i == 'ADR' or i == 'TEL' or i == 'EMAIL':
				for entry in vcard_[i]:
					add_on = '_HOME'
					if 'WORK' in entry:
						add_on = '_WORK'
					for j in entry.keys():
						self.set_value(i + add_on + '_' + j + '_entry', entry[j])
			if isinstance(vcard_[i], dict):
				for j in vcard_[i].keys():
					self.set_value(i + '_' + j + '_entry', vcard_[i][j])
			else:
				if i == 'DESC':
					self.xml.get_widget('DESC_textview').get_buffer().set_text(
						vcard_[i], 0)
				else:
					self.set_value(i + '_entry', vcard_[i])
		if self.update_progressbar_timeout_id is not None:
			if self.message_id:
				self.statusbar.remove(self.context_id, self.message_id)
			self.message_id = self.statusbar.push(self.context_id,
				_('Information received'))
			self.remove_statusbar_timeout_id = gobject.timeout_add_seconds(3,
				self.remove_statusbar, self.message_id)
			gobject.source_remove(self.update_progressbar_timeout_id)
			self.progressbar.hide()
			self.progressbar.set_fraction(0)
			self.update_progressbar_timeout_id = None

	def add_to_vcard(self, vcard_, entry, txt):
		'''Add an information to the vCard dictionary'''
		entries = entry.split('_')
		loc = vcard_
		if len(entries) == 3: # We need to use lists
			if entries[0] not in loc:
				loc[entries[0]] = []
			found = False
			for e in loc[entries[0]]:
				if entries[1] in e:
					e[entries[2]] = txt
					break
			else:
				loc[entries[0]].append({entries[1]: '', entries[2]: txt})
			return vcard_
		while len(entries) > 1:
			if entries[0] not in loc:
				loc[entries[0]] = {}
			loc = loc[entries[0]]
			del entries[0]
		loc[entries[0]] = txt
		return vcard_

	def make_vcard(self):
		'''make the vCard dictionary'''
		entries = ['FN', 'NICKNAME', 'BDAY', 'EMAIL_HOME_USERID', 'URL',
			'TEL_HOME_NUMBER', 'N_FAMILY', 'N_GIVEN', 'N_MIDDLE', 'N_PREFIX',
			'N_SUFFIX', 'ADR_HOME_STREET', 'ADR_HOME_EXTADR', 'ADR_HOME_LOCALITY',
			'ADR_HOME_REGION', 'ADR_HOME_PCODE', 'ADR_HOME_CTRY', 'ORG_ORGNAME',
			'ORG_ORGUNIT', 'TITLE', 'ROLE', 'TEL_WORK_NUMBER', 'EMAIL_WORK_USERID',
			'ADR_WORK_STREET', 'ADR_WORK_EXTADR', 'ADR_WORK_LOCALITY',
			'ADR_WORK_REGION', 'ADR_WORK_PCODE', 'ADR_WORK_CTRY']
		vcard_ = {}
		for e in entries:
			txt = self.xml.get_widget(e + '_entry').get_text().decode('utf-8')
			if txt != '':
				vcard_ = self.add_to_vcard(vcard_, e, txt)

		# DESC textview
		buff = self.xml.get_widget('DESC_textview').get_buffer()
		start_iter = buff.get_start_iter()
		end_iter = buff.get_end_iter()
		txt = buff.get_text(start_iter, end_iter, 0)
		if txt != '':
			vcard_['DESC'] = txt.decode('utf-8')

		# Avatar
		if self.avatar_encoded:
			vcard_['PHOTO'] = {'BINVAL': self.avatar_encoded}
			if self.avatar_mime_type:
				vcard_['PHOTO']['TYPE'] = self.avatar_mime_type
		return vcard_

	def on_ok_button_clicked(self, widget):
		if self.update_progressbar_timeout_id:
			# Operation in progress
			return
		if gajim.connections[self.account].connected < 2:
			dialogs.ErrorDialog(_('You are not connected to the server'),
				_('Without a connection you can not publish your contact '
				'information.'))
			return
		vcard_ = self.make_vcard()
		nick = ''
		if 'NICKNAME' in vcard_:
			nick = vcard_['NICKNAME']
			from common import pep
			pep.user_send_nickname(self.account, nick)
		if nick == '':
			nick = gajim.config.get_per('accounts', self.account, 'name')
		gajim.nicks[self.account] = nick
		gajim.connections[self.account].send_vcard(vcard_)
		self.message_id = self.statusbar.push(self.context_id,
			_('Sending profile...'))
		self.progressbar.show()
		self.update_progressbar_timeout_id = gobject.timeout_add(100,
			self.update_progressbar)

	def vcard_published(self):
		if self.update_progressbar_timeout_id is not None:
			gobject.source_remove(self.update_progressbar_timeout_id)
			self.update_progressbar_timeout_id = None
		self.window.destroy()

	def vcard_not_published(self):
		if self.message_id:
			self.statusbar.remove(self.context_id, self.message_id)
		self.message_id = self.statusbar.push(self.context_id,
			_('Information NOT published'))
		self.remove_statusbar_timeout_id = gobject.timeout_add_seconds(3,
			self.remove_statusbar, self.message_id)
		if self.update_progressbar_timeout_id is not None:
			gobject.source_remove(self.update_progressbar_timeout_id)
			self.progressbar.set_fraction(0)
			self.update_progressbar_timeout_id = None
		dialogs.InformationDialog(_('vCard publication failed'),
			_('There was an error while publishing your personal information, '
			'try again later.'))

	def on_cancel_button_clicked(self, widget):
		self.window.destroy()

# vim: se ts=3:
