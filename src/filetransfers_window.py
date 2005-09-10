##	filetransfers_window.py
##
## Gajim Team:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Vincent Hanquez <tab@snarc.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
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
import pango
import os
import sys
import time

import gtkgui_helpers
import tooltips
import dialogs

from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain (APP, i18n.DIR)
gtk.glade.textdomain (APP)

GTKGUI_GLADE = 'gtkgui.glade'

C_IMAGE = 0
C_LABELS = 1
C_FILE = 2
C_TIME = 3
C_PROGRESS = 4
C_PERCENT = 5
C_SID = 6


class FileTransfersWindow:
	def __init__(self, plugin):
		self.files_props = {'r' : {}, 's': {}}
		self.plugin = plugin
		self.height_diff = 0
		self.xml = gtk.glade.XML(GTKGUI_GLADE, 'file_transfers_window', APP)
		self.window = self.xml.get_widget('file_transfers_window')
		self.tree = self.xml.get_widget('transfers_list')
		self.cancel_button = self.xml.get_widget('cancel_button')
		self.pause_button = self.xml.get_widget('pause_restore_button')
		self.cleanup_button = self.xml.get_widget('cleanup_button')
		self.notify_ft_checkbox = self.xml.get_widget(
			'notify_ft_complete_checkbox')
		notify = gajim.config.get('notify_on_file_complete')
		if notify:
			self.notify_ft_checkbox.set_active(True)
		else:
			self.notify_ft_checkbox.set_active(False)
		self.model = gtk.ListStore(gtk.gdk.Pixbuf, str, str, str, str, int, str)
		self.tree.set_model(self.model)
		col = gtk.TreeViewColumn()
		
		render_pixbuf = gtk.CellRendererPixbuf()
		
		col.pack_start(render_pixbuf, expand = True)
		render_pixbuf.set_property('xpad', 3)
		render_pixbuf.set_property('ypad', 3)
		render_pixbuf.set_property('yalign', .0)
		col.add_attribute(render_pixbuf, 'pixbuf', 0)
		self.tree.append_column(col)
		
		col = gtk.TreeViewColumn(_('File'))
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, expand=False)
		col.add_attribute(renderer, 'markup' , C_LABELS)
		renderer.set_property('yalign', 0.)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, expand=True)
		col.add_attribute(renderer, 'markup' , C_FILE)
		renderer.set_property('xalign', 0.)
		renderer.set_property('yalign', 0.)
		renderer.set_property('ellipsize', pango.ELLIPSIZE_END)
		col.set_resizable(True)
		col.set_expand(True)
		self.tree.append_column(col)
		
		col = gtk.TreeViewColumn(_('Time'))
		renderer = gtk.CellRendererText()
		col.pack_start(renderer, expand=False)
		col.add_attribute(renderer, 'markup' , C_TIME)
		renderer.set_property('yalign', 0.5)
		renderer.set_property('xalign', 0.5)
		renderer = gtk.CellRendererText()
		renderer.set_property('ellipsize', pango.ELLIPSIZE_END)
		col.set_resizable(True)
		col.set_expand(False)
		self.tree.append_column(col)
		
		col = gtk.TreeViewColumn(_('Progress'))
		renderer = gtk.CellRendererProgress()
		renderer.set_property('yalign', 0.5)
		renderer.set_property('xalign', 0.5)
		col.pack_start(renderer, expand = False)
		col.set_expand(False)
		col.add_attribute(renderer, 'text' , C_PROGRESS)
		col.add_attribute(renderer, 'value' , C_PERCENT)
		col.set_resizable(True)
		self.tree.append_column(col)
		
		self.set_images()
		self.tree.get_selection().set_mode(gtk.SELECTION_SINGLE)
		self.tree.get_selection().connect('changed', self.selection_changed)
		self.tooltip = tooltips.FileTransfersTooltip()
		self.xml.signal_autoconnect(self)
		popup_xml = gtk.glade.XML(GTKGUI_GLADE, 'file_transfers_menu',
			APP)
		self.file_transfers_menu = popup_xml.get_widget('file_transfers_menu')
		self.open_folder_menuitem = popup_xml.get_widget('open_folder_menuitem')
		self.cancel_menuitem = popup_xml.get_widget('cancel_menuitem')
		self.pause_menuitem = popup_xml.get_widget('pause_menuitem')
		self.continue_menuitem = popup_xml.get_widget('continue_menuitem')
		self.continue_menuitem.hide()
		self.continue_menuitem.set_no_show_all(True)
		self.remove_menuitem = popup_xml.get_widget('remove_menuitem')
		popup_xml.signal_autoconnect(self)
		
	def find_transfer_by_jid(self, account, jid):
		''' find all transfers with peer 'jid' that belong to 'account' '''
		active_transfers = [[],[]] # ['senders', 'receivers']
		
		# 'account' is the sender
		for file_props in self.files_props['s'].values():
			if file_props['tt_account'] == account:
				receiver_jid = unicode(file_props['receiver']).split('/')[0]
				if jid == receiver_jid:
					if not self.is_transfer_stoped(file_props):
						active_transfers[0].append(file_props)
		
		# 'account' is the recipient
		for file_props in self.files_props['r'].values():
			if file_props['tt_account'] == account:
				sender_jid = unicode(file_props['sender']).split('/')[0]
				if jid == sender_jid:
					if not self.is_transfer_stoped(file_props):
						active_transfers[1].append(file_props)
		return active_transfers
	
	def show_completed(self, jid, file_props):
		''' show a dialog saying that file (file_props) has been transferred'''
		self.window.present()
		self.window.window.focus()
		if file_props['type'] == 'r':
			# file path is used below in 'Save in'
			(file_path, file_name) = os.path.split(file_props['file-name'])
		else:
			file_name = file_props['name']
		sectext = '\t' + _('Filename: %s') % \
			gtkgui_helpers.escape_for_pango_markup(file_name)
		sectext += '\n\t' + _('Size: %s') % \
		helpers.convert_bytes(file_props['size'])
		if file_props['type'] == 'r':
			jid = unicode(file_props['sender']).split('/')[0]
			sender_name = gajim.get_first_contact_instance_from_jid( 
				file_props['tt_account'], jid).name
			sender = gtkgui_helpers.escape_for_pango_markup(sender_name)
		else:
			#You is a reply of who send a file
			sender = _('You')
		sectext += '\n\t' +_('Sender: %s') % sender
		sectext += '\n\t' +_('Recipient: ')
		if file_props['type'] == 's':
			jid = unicode(file_props['receiver']).split('/')[0]
			receiver_name = gajim.get_first_contact_instance_from_jid( 
				file_props['tt_account'], jid).name
			recipient = gtkgui_helpers.escape_for_pango_markup(receiver_name)
		else:
			#You is a reply of who received a file
			recipient = ('You')
		sectext += recipient
		if file_props['type'] == 'r':
			sectext += '\n\t' +_('Saved in: %s') % \
				gtkgui_helpers.escape_for_pango_markup(file_path)
		dialog = dialogs.HigDialog(None, gtk.MESSAGE_INFO, gtk.BUTTONS_NONE, 
				_('File transfer completed'), sectext)
		dialog.add_buttons(_('_Open Containing Folder'), gtk.RESPONSE_ACCEPT, 
				 gtk.STOCK_OK, gtk.RESPONSE_OK )
		dialog.show_all()
		if file_props['type'] == 's':
			button.hide()
		response = dialog.run()
		dialog.destroy()
		if response == gtk.RESPONSE_ACCEPT:
			if not file_props.has_key('file-name'):
				return
			(path, file) = os.path.split(file_props['file-name'])
			if os.path.exists(path) and os.path.isdir(path):
				helpers.launch_file_manager(path)
			self.tree.get_selection().unselect_all()
		
	def show_request_error(self, file_props):
		''' show error dialog to the recipient saying that transfer 
		has been canceled'''
		self.window.present()
		self.window.window.focus()
		dialogs.InformationDialog(_('File transfer canceled'), _('Connection with peer cannot be established.'))
		self.tree.get_selection().unselect_all()
		
	def show_send_error(self, file_props):
		''' show error dialog to the sender saying that transfer 
		has been canceled'''
		self.window.present()
		self.window.window.focus()
		dialogs.InformationDialog(_('File transfer canceled'),
_('Connection with peer cannot be established.'))
		self.tree.get_selection().unselect_all()
	
	def show_stopped(self, jid, file_props):
		self.window.present()
		self.window.window.focus()
		if file_props['type'] == 'r':
			file_name = os.path.basename(file_props['file-name'])
		else:
			file_name = file_props['name']
		sectext = '\t' + _('Filename: %s') % \
			gtkgui_helpers.escape_for_pango_markup(file_name)
		sectext += '\n\t' + _('Sender: %s') % \
			gtkgui_helpers.escape_for_pango_markup(jid)
		dialogs.ErrorDialog(_('File transfer stopped by the contact of the other side'), \
			sectext).get_response()
		self.tree.get_selection().unselect_all()
		
	def show_file_send_request(self, account, contact):
		#FIXME: user better name for this function
		#atm it's like it shows popup for incoming file transfer request
		last_send_dir = gajim.config.get('last_send_dir')
		dialog = gtk.FileChooserDialog(title=_('Choose File to Send...'), 
			action=gtk.FILE_CHOOSER_ACTION_OPEN, 
			buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL))
		butt = dialog.add_button(_('Send'), gtk.RESPONSE_OK)
		butt.set_use_stock(True)
		dialog.set_default_response(gtk.RESPONSE_OK)
		dialog.set_select_multiple(True) # we can select many files to send
		if last_send_dir and os.path.isdir(last_send_dir):
			dialog.set_current_folder(last_send_dir)
		else:
			home_dir = os.path.expanduser('~')
			dialog.set_current_folder(home_dir)
		file_props = {}
		response = dialog.run()
		if response == gtk.RESPONSE_OK:
			files_path_list = dialog.get_filenames()
			dialog.destroy()
			file_dir = None
			for file_path in files_path_list:
				file_path = file_path.decode(sys.getfilesystemencoding())
				if os.path.isfile(file_path):
					file_dir = os.path.dirname(file_path)
					self.send_file(account, contact, file_path)
			if file_dir:
				gajim.config.set('last_send_dir', file_dir)
		else:
			dialog.destroy()

	def send_file(self, account, contact, file_path):
		''' start the real transfer(upload) of the file '''
		if type(contact) == str:
			if contact.find('/') == -1:
				return
			(jid, resource) = contact.split("/", 1)
			contact = gajim.Contact(jid = jid, resource = resource)
		(file_dir, file_name) = os.path.split(file_path)
		file_props = self.get_send_file_props(account, contact, 
				file_path, file_name)
		self.add_transfer(account, contact, file_props)
		gajim.connections[account].send_file_request(file_props)
	
	def show_file_request(self, account, contact, file_props):
		''' show dialog asking for comfirmation and store location of new
		file requested by a contact'''
		if file_props is None or not file_props.has_key('name'):
			return
		last_save_dir = gajim.config.get('last_save_dir')
		sec_text = '\t' + _('File: %s') % \
			gtkgui_helpers.escape_for_pango_markup(file_props['name'])
		if file_props.has_key('size'):
			sec_text += '\n\t' + _('Size: %s') % \
				helpers.convert_bytes(file_props['size'])
		if file_props.has_key('mime-type'):
			sec_text += '\n\t' + _('Type: %s') % \
				gtkgui_helpers.escape_for_pango_markup(file_props['mime-type'])
		if file_props.has_key('desc'):
			sec_text += '\n\t' + _('Description: %s') % \
				gtkgui_helpers.escape_for_pango_markup(file_props['desc'])
		prim_text = _('%s wants to send you a file:') % contact.jid
		dialog = dialogs.ConfirmationDialog(prim_text, sec_text)
		if dialog.get_response() == gtk.RESPONSE_OK:
			dialog = gtk.FileChooserDialog(title=_('Save File as...'), 
				action=gtk.FILE_CHOOSER_ACTION_SAVE, 
				buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, 
				gtk.STOCK_SAVE, gtk.RESPONSE_OK))
			dialog.set_current_name(file_props['name'])
			dialog.set_default_response(gtk.RESPONSE_OK)
			gtk28 = False
			if gtk.gtk_version >= (2, 8, 0) and gtk.pygtk_version >= (2, 8, 0):
				dialog.props.do_overwrite_confirmation = True
				gtk28 = True
			if last_save_dir and os.path.isdir(last_save_dir):
				dialog.set_current_folder(last_save_dir)
			else:
				home_dir = os.path.expanduser('~')
				dialog.set_current_folder(home_dir)
			while True:
				response = dialog.run()
				if response == gtk.RESPONSE_OK:
					file_path = dialog.get_filename()
					file_path = file_path.decode('utf-8')
					if not gtk28 and os.path.exists(file_path):
						#FIXME: pango does not work here.
						primtext = _('This file already exists')
						sectext = _('Would you like to overwrite it?')
						dialog2 = dialogs.ConfirmationDialog(primtext, sectext)
						if dialog2.get_response() != gtk.RESPONSE_OK:
							continue
					file_dir = os.path.dirname(file_path)
					if file_dir:
						gajim.config.set('last_save_dir', file_dir)
					file_props['file-name'] = file_path
					self.add_transfer(account, contact, file_props)
					gajim.connections[account].send_file_approval(file_props)
				else:
					gajim.connections[account].send_file_rejection(file_props)
				dialog.destroy()
				break
		else:
			gajim.connections[account].send_file_rejection(file_props)
	
	def set_images(self):
		''' create pixbufs for status images in transfer rows'''
		self.images = {}
		self.images['upload'] = self.window.render_icon(gtk.STOCK_GO_UP, 
			gtk.ICON_SIZE_MENU)
		self.images['download'] = self.window.render_icon(gtk.STOCK_GO_DOWN, 
			gtk.ICON_SIZE_MENU)
		self.images['stop'] = self.window.render_icon(gtk.STOCK_STOP, 
			gtk.ICON_SIZE_MENU)
		self.images['waiting'] = self.window.render_icon(gtk.STOCK_REFRESH, 
			gtk.ICON_SIZE_MENU)
		self.images['pause'] = self.window.render_icon(gtk.STOCK_MEDIA_PAUSE, 
			gtk.ICON_SIZE_MENU)
		self.images['continue'] = self.window.render_icon(gtk.STOCK_MEDIA_PLAY, 
			gtk.ICON_SIZE_MENU)
		self.images['ok'] = self.window.render_icon(gtk.STOCK_APPLY, 
			gtk.ICON_SIZE_MENU)
			
	def set_status(self, typ, sid, status):
		''' change the status of a transfer to state 'status' '''
		iter = self.get_iter_by_sid(typ, sid)
		if iter is None:
			return
		sid = self.model[iter][C_SID].decode('utf-8')
		file_props = self.files_props[sid[0]][sid[1:]]
		if status == 'stop':
			file_props['stopped'] = True
		elif status == 'ok':
			file_props['completed'] = True
		self.model.set(iter, C_IMAGE, self.images[status])
		
	def _format_percent(self, percent):
		''' add extra spaces from both sides of the percent, so that
		progress string has always a fixed size'''
		_str = '          '
		if percent != 100.:
			_str += ' '
		if percent < 10:
			_str += ' '
		_str += unicode(percent) + '%          \n'
		return _str
		
	def _format_time(self, _time):
		
		times = { 'hours': 0, 'minutes': 0, 'seconds': 0 }
		_time = int(_time)
		times['seconds'] = _time % 60
		if _time >= 60:
			_time /= 60
			times['minutes'] = _time % 60
			if _time >= 60:
				times['hours'] = _time / 60
		
		#Print remaining time in format 00:00:00
		#You can change the places of hours, minutes, seconds -
		#they are not translatable.
		return _('%(hours)02.d:%(minutes)02.d:%(seconds)02.d')  % times
		
	def _get_eta_and_speed(self, full_size, transfered_size, elapsed_time):
		if elapsed_time == 0:
			return 0., 0.
		speed = round(float(transfered_size) / elapsed_time)
		if speed == 0.:
			return 0., 0.
		remaining_size = full_size - transfered_size
		eta = remaining_size / speed
		return eta, speed
		
	def set_progress(self, typ, sid, transfered_size, iter = None):
		''' change the progress of a transfer with new transfered size'''
		if not self.files_props[typ].has_key(sid):
			return
		file_props = self.files_props[typ][sid]
		full_size = int(file_props['size'])
		if full_size == 0:
			percent = 0
		else:
			percent = round(float(transfered_size) / full_size * 100)
		if iter is None:
			iter = self.get_iter_by_sid(typ, sid)
		if iter is not None:
			text = self._format_percent(percent)
			if transfered_size == 0:
				text += '0'
			else:
				text += helpers.convert_bytes(transfered_size)
			text += '/' + helpers.convert_bytes(full_size)
			# Kb/s
			
			# remaining time
			eta, speed = self._get_eta_and_speed(full_size, transfered_size, 
				file_props['elapsed-time'])
			
			self.model.set(iter, C_PROGRESS, text)
			self.model.set(iter, C_PERCENT, int(percent))
			text = self._format_time(eta)
			#This should make the string Kb/s, 
			#where 'Kb' part is taken from %s.
			#Only the last 's' should be translated.
			text += '\n'
			text += _('(%s/s)') % helpers.convert_bytes(speed)
			self.model.set(iter, C_TIME, text)
			
			# try to guess what should be the status image
			if file_props['type'] == 'r':
				status = 'download'
			else:
				status = 'upload'
			if file_props.has_key('paused') and file_props['paused'] == True:
				status = 'pause'
			elif file_props.has_key('stalled') and file_props['stalled'] == True:
				status = 'waiting'
			if file_props.has_key('connected') and file_props['connected'] == False:
				status = 'stop'
			self.model.set(iter, 0, self.images[status])
			if percent == 100:
				self.set_status(typ, sid, 'ok')
	
	def get_iter_by_sid(self, typ, sid):
		'''returns iter to the row, which holds file transfer, identified by the
		session id'''
		iter = self.model.get_iter_root()
		while iter:
			if typ + sid == self.model[iter][C_SID].decode('utf-8'):
				return iter
			iter = self.model.iter_next(iter)
	
	def get_sid(self):
		''' create random string of length 16'''
		rng = range(65, 90)
		rng.extend(range(48, 57))
		char_sequence = map(lambda e:chr(e), rng)
		from random import sample
		return reduce(lambda e1, e2: e1 + e2, 
				sample(char_sequence, 16))
	
	def get_send_file_props(self, account, contact, file_path, file_name):
		''' create new file_props dict and set initial file transfer 
		properties in it'''
		file_props = {'file-name' : file_path, 'name' : file_name, 
			'type' : 's'}
		if os.path.exists(file_path) and os.path.isfile(file_path):
			stat = os.stat(file_path)
		os.stat(file_path)
		file_props['elapsed-time'] = 0
		file_props['size'] = unicode(stat[6])
		file_props['sid'] = self.get_sid()
		file_props['completed'] = False
		file_props['started'] = False
		file_props['sender'] = account
		file_props['receiver'] = contact
		file_props['tt_account'] = account
		return file_props
		
	def add_transfer(self, account, contact, file_props):
		''' add new transfer to FT window and show the FT window '''
		self.on_transfers_list_leave_notify_event(None)
		if file_props is None:
			return
		file_props['elapsed-time'] = 0
		self.files_props[file_props['type']][file_props['sid']] = file_props
		iter = self.model.append()
		text_labels = '<b>' + _('Name: ') + '</b>\n' 
		if file_props['type'] == 'r':
			text_labels += '<b>' + _('Sender: ') + '</b>' 
		else:
			text_labels += '<b>' + _('Recipient: ') + '</b>' 
			
		if file_props['type'] == 'r':
			(file_path, file_name) = os.path.split(file_props['file-name'])
		else:
			file_name = file_props['name']
		text_props = gtkgui_helpers.escape_for_pango_markup(file_name) + '\n'
		text_props += gtkgui_helpers.escape_for_pango_markup(contact.name)
		self.model.set(iter, 1, text_labels, 2, text_props, C_SID, \
			file_props['type'] + file_props['sid'])
		self.set_progress(file_props['type'], file_props['sid'], 0, iter)
		if file_props.has_key('started') and file_props['started'] is False:
			status = 'waiting'
		elif file_props['type'] == 'r':
			status = 'download'
		else:
			status = 'upload'
		file_props['tt_account'] = account
		self.set_status(file_props['type'], file_props['sid'], status)
		self.set_cleanup_sensitivity()
		self.window.show_all()
	
	def on_transfers_list_motion_notify_event(self, widget, event):
		pointer = self.tree.get_pointer()
		orig = widget.window.get_origin()
		props = widget.get_path_at_pos(int(event.x), int(event.y))
		self.height_diff = pointer[1] - int(event.y)
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id != props[0]:
				self.tooltip.hide_tooltip()
		if props:
			[row, col, x, y] = props
			iter = None
			try:
				iter = self.model.get_iter(row)
			except:
				self.tooltip.hide_tooltip()
				return
			sid = self.model[iter][C_SID].decode('utf-8')
			file_props = self.files_props[sid[0]][sid[1:]]
			if file_props is not None:
				if self.tooltip.timeout == 0 or self.tooltip.id != props[0]:
					self.tooltip.id = row
					self.tooltip.timeout = gobject.timeout_add(500,
						self.show_tooltip, widget)
	
	def on_transfers_list_leave_notify_event(self, widget = None, event = None):
		if event is not None:
			self.height_diff = int(event.y)
		elif self.height_diff is 0:
			return
		pointer = self.tree.get_pointer()
		props = self.tree.get_path_at_pos(pointer[0], 
			pointer[1] - self.height_diff)
		if self.tooltip.timeout > 0:
			if not props or self.tooltip.id == props[0]:
				self.tooltip.hide_tooltip()
	
	def on_transfers_list_row_activated(self, widget, path, col):
		# try to open the containing folder
		self.on_open_folder_menuitem_activate(widget)
		
	def is_transfer_paused(self, file_props):
		if file_props.has_key('stopped') and file_props['stopped']:
			return False
		if file_props.has_key('completed') and file_props['completed']:
			return False
		if not file_props.has_key('disconnect_cb'):
			return False
		return file_props['paused']
		
	def is_transfer_active(self, file_props):
		if file_props.has_key('stopped') and file_props['stopped']:
			return False
		if file_props.has_key('completed') and file_props['completed']:
			return False
		if not file_props.has_key('started') or not file_props['started']:
			return False
		if not file_props.has_key('paused'):
			return True
		return not file_props['paused']
		
	def is_transfer_stoped(self, file_props):
		if file_props.has_key('error') and file_props['error'] != 0:
			return True
		if file_props.has_key('completed') and file_props['completed']:
			return True
		if not file_props.has_key('stopped') or not \
			file_props['stopped']:
			return False
		return True

	def set_cleanup_sensitivity(self):
		''' check if there are transfer rows and set cleanup_button 
		sensitive, or insensitive if model is empty
		'''
		if len(self.model) == 0:
			self.cleanup_button.set_sensitive(False)
		else:
			self.cleanup_button.set_sensitive(True)
	
	def set_all_insensitive(self):
		''' make all buttons/menuitems insensitive '''
		self.pause_button.set_sensitive(False)
		self.pause_menuitem.set_sensitive(False)
		self.continue_menuitem.set_sensitive(False)
		self.remove_menuitem.set_sensitive(False)
		self.cancel_button.set_sensitive(False)
		self.cancel_menuitem.set_sensitive(False)
		self.open_folder_menuitem.set_sensitive(False)
		self.set_cleanup_sensitivity()
	
	def set_buttons_sensitive(self, path, is_row_selected):
		''' make buttons/menuitems sensitive as appropriate to 
		the state of file transfer located at path 'path' '''
		if path is None:
			self.set_all_insensitive()
			return
		current_iter = self.model.get_iter(path)
		sid = self.model[current_iter][C_SID].decode('utf-8')
		file_props = self.files_props[sid[0]][sid[1:]]
		self.remove_menuitem.set_sensitive(is_row_selected)
		self.open_folder_menuitem.set_sensitive(is_row_selected)
		is_stopped = False
		if self.is_transfer_stoped(file_props):
			is_stopped = True
		self.cancel_button.set_sensitive(not is_stopped)
		self.cancel_menuitem.set_sensitive(not is_stopped)
		if not is_row_selected:
			# no selection, disable the buttons
			self.set_all_insensitive()
		elif not is_stopped:
			if self.is_transfer_active(file_props):
				# file transfer is active
				self.toggle_pause_continue(True)
				self.pause_button.set_sensitive(True)
			elif self.is_transfer_paused(file_props):
				# file transfer is paused
				self.toggle_pause_continue(False)
				self.pause_button.set_sensitive(True)
			else:
				self.pause_button.set_sensitive(False)
				self.pause_menuitem.set_sensitive(False)
				self.continue_menuitem.set_sensitive(False)
		else:
			self.pause_button.set_sensitive(False)
			self.pause_menuitem.set_sensitive(False)
			self.continue_menuitem.set_sensitive(False)
		return True
	
	def selection_changed(self, args):
		''' selection has changed - change the sensitivity of the 
		buttons/menuitems'''
		selection = args
		selected = selection.get_selected_rows()
		if selected[1] != []:
			selected_path = selected[1][0]
			self.select_func(selected_path)
		else:
			self.set_all_insensitive()
	
	def select_func(self, path):
		is_selected = False
		selected = self.tree.get_selection().get_selected_rows()
		if selected[1] != []:
			selected_path = selected[1][0]
			if selected_path == path:
				is_selected = True
		self.set_buttons_sensitive(path, is_selected)
		self.set_cleanup_sensitivity()
		return True
	
	def on_cleanup_button_clicked(self, widget):
		i = len(self.model) - 1
		while i >= 0:
			iter = self.model.get_iter((i))
			sid = self.model[iter][C_SID].decode('utf-8')
			file_props = self.files_props[sid[0]][sid[1:]]
			if file_props.has_key('completed') and file_props['completed']:
				self.model.remove(iter)
			elif file_props.has_key('stopped') and file_props['stopped']:
				self.model.remove(iter)
			i -= 1
		self.tree.get_selection().unselect_all()
		self.set_all_insensitive()
	
	def toggle_pause_continue(self, status):
		if status:
			label = _('Pause')
			self.pause_button.set_label(label)
			self.pause_button.set_image(gtk.image_new_from_stock(
				gtk.STOCK_MEDIA_PAUSE, gtk.ICON_SIZE_MENU))
			
			self.pause_menuitem.set_sensitive(True)
			self.pause_menuitem.set_no_show_all(False)
			self.continue_menuitem.hide()
			self.continue_menuitem.set_no_show_all(True)
			
		else:
			label = _('_Continue')
			self.pause_button.set_label(label)
			self.pause_button.set_image(gtk.image_new_from_stock(
				gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU))
			self.pause_menuitem.hide()
			self.pause_menuitem.set_no_show_all(True)
			self.continue_menuitem.set_sensitive(True)
			self.continue_menuitem.set_no_show_all(False)
	
	def on_pause_restore_button_clicked(self, widget):
		selected = self.tree.get_selection().get_selected()
		if selected is None or selected[1] is None:
			return 
		s_iter = selected[1]
		sid = self.model[s_iter][C_SID].decode('utf-8')
		file_props = self.files_props[sid[0]][sid[1:]]
		if self.is_transfer_paused(file_props):
			file_props['last-time'] = time.time()
			file_props['paused'] = False
			types = {'r' : 'download', 's' : 'upload'}
			self.set_status(file_props['type'], file_props['sid'], types[sid[0]])
			self.toggle_pause_continue(True)
		elif self.is_transfer_active(file_props):
			file_props['paused'] = True
			self.set_status(file_props['type'], file_props['sid'], 'pause')
			self.toggle_pause_continue(False)
		
	def on_cancel_button_clicked(self, widget):
		selected = self.tree.get_selection().get_selected()
		if selected is None or selected[1] is None:
			return 
		s_iter = selected[1]
		sid = self.model[s_iter][C_SID].decode('utf-8')
		file_props = self.files_props[sid[0]][sid[1:]]
		if not file_props.has_key('tt_account'):
			return 
		account = file_props['tt_account']
		if not gajim.connections.has_key(account):
			return
		gajim.connections[account].disconnect_transfer(file_props)
		self.set_status(file_props['type'], file_props['sid'], 'stop')
	
	def show_tooltip(self, widget):
		if self.height_diff == 0:
			self.tooltip.hide_tooltip()
			return
		pointer = self.tree.get_pointer()
		props = self.tree.get_path_at_pos(pointer[0], 
			pointer[1] - self.height_diff)
		if props and self.tooltip.id == props[0]:
			# check if the current pointer is at the same path
			# as it was before setting the timeout
			iter = self.model.get_iter(props[0])
			sid = self.model[iter][C_SID].decode('utf-8')
			file_props = self.files_props[sid[0]][sid[1:]]
			rect =  self.tree.get_cell_area(props[0],props[1])
			position = widget.window.get_origin()
			self.tooltip.show_tooltip(file_props , (pointer[0], rect.height ), 
				 (position[0], position[1] + rect.y + self.height_diff))
		else:
			self.tooltip.hide_tooltip()
	
	def on_notify_ft_complete_checkbox_toggled(self, widget):
		gajim.config.set('notify_on_file_complete', 
			widget.get_active())
		
	def on_file_transfers_dialog_delete_event(self, widget, event):
		self.on_transfers_list_leave_notify_event(widget, None)
		self.window.hide()
		return True # do NOT destory window
	
	def on_close_button_clicked(self, widget):
		self.window.hide()

	def show_context_menu(self, event, iter):
		# change the sensitive propery of the buttons and menuitems
		path = None
		if iter is not None:
			path = self.model.get_path(iter)
		self.set_buttons_sensitive(path, True)
		
		event_button = self.get_possible_button_event(event)
		self.file_transfers_menu.popup(None, self.tree, None, 
			event_button, event.time)
		self.file_transfers_menu.show_all()
	
	def get_possible_button_event(self, event):
		'''mouse or keyboard caused the event?'''
		if event.type == gtk.gdk.KEY_PRESS:
			event_button = 0 # no event.button so pass 0
		else: # BUTTON_PRESS event, so pass event.button
			event_button = event.button
		
		return event_button
	
	def on_transfers_list_key_press_event(self, widget, event):
		'''when a key is pressed in the treeviews'''
		self.tooltip.hide_tooltip()
		iter = None
		try:
			store, iter = self.tree.get_selection().get_selected()
		except TypeError:
			self.tree.get_selection().unselect_all()
		
		if iter is not None:
			path = self.model.get_path(iter)
			self.tree.get_selection().select_path(path)
		
		if event.keyval == gtk.keysyms.Menu:
			self.show_context_menu(event, iter)
			return True
			
	
	def on_transfers_list_button_release_event(self, widget, event):
		# hide tooltip, no matter the button is pressed
		self.tooltip.hide_tooltip()
		path = None
		try:
			path, column, x, y = self.tree.get_path_at_pos(int(event.x), 
				int(event.y))
		except TypeError:
			self.tree.get_selection().unselect_all()
		if path is None:
			self.set_all_insensitive()
		else:
			self.select_func(path)
			
	def on_transfers_list_button_press_event(self, widget, event):
		# hide tooltip, no matter the button is pressed
		self.tooltip.hide_tooltip()
		path, iter = None, None
		try:
			path, column, x, y = self.tree.get_path_at_pos(int(event.x), 
				int(event.y))
		except TypeError:
			self.tree.get_selection().unselect_all()
		if event.button == 3: # Right click
			if path is not None:
				self.tree.get_selection().select_path(path)
				iter = self.model.get_iter(path)
			self.show_context_menu(event, iter)
			if path is not None:
				return True
		
	def on_open_folder_menuitem_activate(self, widget):
		selected = self.tree.get_selection().get_selected()
		if selected is None or selected[1] is None:
			return 
		s_iter = selected[1]
		sid = self.model[s_iter][C_SID].decode('utf-8')
		file_props = self.files_props[sid[0]][sid[1:]]
		if not file_props.has_key('file-name'):
			return
		(path, file) = os.path.split(file_props['file-name'])
		if os.path.exists(path) and os.path.isdir(path):
			helpers.launch_file_manager(path)
		
	def on_cancel_menuitem_activate(self, widget):
		self.on_cancel_button_clicked(widget)
		
	def on_continue_menuitem_activate(self, widget):
		self.on_pause_restore_button_clicked(widget)
	
	def on_pause_menuitem_activate(self, widget):
		self.on_pause_restore_button_clicked(widget)
		#FIXME: change the stock
		
	def on_remove_menuitem_activate(self, widget):
		selected = self.tree.get_selection().get_selected()
		if selected is None or selected[1] is None:
			return 
		s_iter = selected[1]
		sid = self.model[s_iter][C_SID].decode('utf-8')
		file_props = self.files_props[sid[0]][sid[1:]]
		if not file_props.has_key('tt_account'):
			# file transfer is not set yet
			return 
		account = file_props['tt_account']
		if not gajim.connections.has_key(account):
			# no connection to the account
			return
		gajim.connections[account].remove_transfer(file_props)
		self.model.remove(s_iter)
		self.set_all_insensitive()

	def on_file_transfers_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape: # ESCAPE
			self.window.hide()
		
