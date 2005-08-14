##	tooltips.py
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
import gobject
import os

import gtkgui_helpers

from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP

class BaseTooltip:
	''' Base Tooltip . Usage:
		tooltip = BaseTooltip()
		.... 
		tooltip.show_tooltip('', window_postions, widget_postions)
		....
		if tooltip.timeout != 0:
			tooltip.hide_tooltip()
	'''
	def __init__(self):
		self.timeout = 0
		self.prefered_position = [0, 0]
		self.win = None
		self.id = None
		
	def populate(self, data):
		''' this method must be overriden by all extenders '''
		self.create_window()
		self.win.add(gtk.Label(data))
		
	def create_window(self):
		''' create a popup window each time tooltip is requested '''
		self.win = gtk.Window(gtk.WINDOW_POPUP)
		self.win.set_border_width(3)
		self.win.set_resizable(False)
		self.win.set_name('gtk-tooltips')
		
		
		self.win.set_events(gtk.gdk.POINTER_MOTION_MASK)
		self.win.connect_after('expose_event', self.expose)
		self.win.connect('size-request', self.size_request)
		self.win.connect('motion-notify-event', self.motion_notify_event)
	
	def motion_notify_event(self, widget, event):
		self.hide_tooltip()

	def size_request(self, widget, requisition):
		screen = self.win.get_screen()
		half_width = requisition.width / 2 + 1
		if self.prefered_position[0] < half_width:
			self.prefered_position[0] = 0
		elif self.prefered_position[0]  + requisition.width > screen.get_width() \
				+ half_width:
			self.prefered_position[0] = screen.get_width() - requisition.width
		else:
			self.prefered_position[0] -= half_width 
			screen.get_height()
		if self.prefered_position[1] + requisition.height > screen.get_height():
			# flip tooltip up
			self.prefered_position[1] -= requisition.height  + self.widget_height + 8
		if self.prefered_position[1] < 0:
			self.prefered_position[1] = 0
		self.win.move(self.prefered_position[0], self.prefered_position[1])

	def expose(self, widget, event):
		style = self.win.get_style()
		size = self.win.get_size()
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT, None,
			self.win, 'tooltip', 0, 0, -1, 1)
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT, None,
			self.win, 'tooltip', 0, size[1] - 1, -1, 1)
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT, None,
			self.win, 'tooltip', 0, 0, 1, -1)
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT, None,
			self.win, 'tooltip', size[0] - 1, 0, 1, -1)
		return True
	
	def show_tooltip(self, data, widget_pos, win_size):
		self.populate(data)
		new_x = win_size[0] + widget_pos[0] 
		new_y = win_size[1] + widget_pos[1] + 4
		self.prefered_position = [new_x, new_y]
		self.widget_height = widget_pos[1]
		self.win.ensure_style()
		self.win.show_all()

	def hide_tooltip(self):
		if(self.timeout > 0):
			gobject.source_remove(self.timeout)
			self.timeout = 0
		if self.win:
			self.win.destroy()
			self.win = None
		self.id = None

class StatusTable:
	''' Contains methods for creating status table. This 
	is used in Roster and NotificationArea tooltips	'''
	def __init__(self):
		self.current_row = 1
		self.table = None
		self.text_lable = None
		
	def create_table(self):
		self.table = gtk.Table(3, 1)
		self.table.set_property('column-spacing', 6)
		self.text_lable = gtk.Label()
		self.text_lable.set_line_wrap(True)
		self.text_lable.set_alignment(0, 0)
		self.text_lable.set_selectable(False)
		self.table.attach(self.text_lable, 1, 4, 1, 2)
		
	def get_status_info(self, resource, priority, show, status):
		str_status = resource + ' (' + str(priority) + ')'
		if status:
			status = status.strip()
			if status != '':
				if gtk.gtk_version < (2, 6, 0) or gtk.pygtk_version < (2, 6, 0):
					# FIXME: check and do the same if we have more than one \n 
					status = gtkgui_helpers.reduce_chars_newlines(status, 50, 1)
				else:
					status = gtkgui_helpers.reduce_chars_newlines(status, 0, 1)
				str_status += ' - ' + status
		return gtkgui_helpers.escape_for_pango_markup(str_status)
	
	def add_status_row(self, file_path, show, str_status):
		''' appends a new row with status icon to the table '''
		self.current_row += 1
		state_file = show.replace(' ', '_')
		files = []
		files.append(os.path.join(file_path, state_file + '.png'))
		files.append(os.path.join(file_path, state_file + '.gif'))
		image = gtk.Image()
		image.set_from_pixbuf(None)
		spacer = gtk.Label('   ')
		for file in files:
			if os.path.exists(file):
				image.set_from_file(file)
				break
		image.set_alignment(0.01, 1)
		self.table.attach(spacer, 1, 2, self.current_row, 
			self.current_row + 1, 0, 0, 0, 0)
		self.table.attach(image,2,3,self.current_row, 
			self.current_row + 1, 0, 0, 3, 0)
		image.set_alignment(0.01, 1)
		status_label = gtk.Label()
		status_label.set_markup(str_status)
		status_label.set_alignment(00, 0)
		self.table.attach(status_label, 3, 4, self.current_row,
			self.current_row + 1, gtk.EXPAND | gtk.FILL, 0, 0, 0)
	
class NotificationAreaTooltip(BaseTooltip, StatusTable):
	''' Tooltip that is shown in the notification area '''
	def __init__(self, plugin):
		self.plugin = plugin
		BaseTooltip.__init__(self)
		StatusTable.__init__(self)

	def populate(self, data):
		self.create_window()
		self.create_table()
		self.hbox = gtk.HBox()
		self.table.set_property('column-spacing', 1)
		text, single_line, accounts = '', '', []
		if gajim.contacts:
			for account in gajim.contacts.keys():
				status_idx = gajim.connections[account].connected
				# uncomment the following to hide offline accounts
				# if status_idx == 0: continue
				from common.connection import STATUS_LIST
				status = STATUS_LIST[status_idx]
				message = gajim.connections[account].status
				single_line = helpers.get_uf_show(status)
				if message is None:
					message = ''
				else:
					message = message.strip()
				if message != '':
					single_line += ': ' + message
				# the other solution is to hide offline accounts
				elif status == 'offline':
					message = helpers.get_uf_show(status)
				accounts.append({'name': account, 'status_line': single_line, 
						'show': status, 'message': message})
		unread_messages_no = self.plugin.roster.nb_unread
		if unread_messages_no > 1:
			text = _('Gajim - %s unread messages') % unread_messages_no
		elif unread_messages_no == 1:
			text = _('Gajim - 1 unread message')
		elif len(accounts) > 1:
			text = _('Gajim')
			self.current_row = 1
			self.table.resize(2,1)
			iconset = gajim.config.get('iconset')
			if not iconset:
				iconset = 'sun'
			file_path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
			for acct in accounts:
				message = gtkgui_helpers.reduce_chars_newlines(acct['message'], 50, 1)
				message = gtkgui_helpers.escape_for_pango_markup(message)
				self.add_status_row(file_path, acct['show'], '<span weight="bold">' + 
					gtkgui_helpers.escape_for_pango_markup(acct['name']) + '</span>' 
					+ ' - ' + message)
					
		elif len(accounts) == 1:
			message = gtkgui_helpers.reduce_chars_newlines(accounts[0]['status_line'], 
				50, 1)
			message = gtkgui_helpers.escape_for_pango_markup(message)
			text = _('Gajim - %s') % message
		else:
			text = _('Gajim - %s') % helpers.get_uf_show('offline')
		self.text_lable.set_markup(text)
		self.hbox.add(self.table)
		self.win.add(self.hbox)
		
class RosterTooltip(BaseTooltip, StatusTable):
	''' Tooltip that is shown in the roster treeview '''
	def __init__(self, plugin):
		self.account = None
		self.plugin = plugin
		
		self.image = gtk.Image()
		self.image.set_alignment(0.5, 0.025)
		BaseTooltip.__init__(self)
		StatusTable.__init__(self)
		
	def populate(self, contacts):
		if not contacts or len(contacts) == 0:
			return
		self.create_window()
		self.hbox = gtk.HBox()
		self.hbox.set_homogeneous(False)
		self.create_table()
		# primary contact
		prim_contact = gajim.get_highest_prio_contact_from_contacts(contacts)
		
		# try to find the image for the contact status
		state_file = prim_contact.show.replace(' ', '_')
		transport = self.plugin.roster.get_transport_name_by_jid(prim_contact.jid)
		if transport:
			file_path = os.path.join(gajim.DATA_DIR, 'iconsets', 'transports', 
				transport , '16x16')
		else:
			iconset = gajim.config.get('iconset')
			if not iconset:
				iconset = 'sun'
			file_path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')

		files = []
		file_full_path = os.path.join(file_path, state_file)
		files.append(file_full_path + '.png')
		files.append(file_full_path + '.gif')
		self.image.set_from_pixbuf(None)
		for file in files:
			if os.path.exists(file):
				self.image.set_from_file(file)
				break
		
		info = '<span size="large" weight="bold">' + prim_contact.jid + '</span>'
		info += '\n<span weight="bold">' + _('Name: ') + '</span>' + \
			gtkgui_helpers.escape_for_pango_markup(prim_contact.name)
		info += '\n<span weight="bold">' + _('Subscription: ') + '</span>' + \
			gtkgui_helpers.escape_for_pango_markup(prim_contact.sub)

		if prim_contact.keyID:
			keyID = None
			if len(prim_contact.keyID) == 8:
				keyID = prim_contact.keyID
			elif len(prim_contact.keyID) == 16:
				keyID = prim_contact.keyID[8:]
			if keyID:
				info += '\n<span weight="bold">' + _('OpenPGP: ') + \
					'</span>' + gtkgui_helpers.escape_for_pango_markup(keyID)

		single_line, resource_str, multiple_resource= '', '', False
		num_resources = 0
		for contact in contacts:
			if contact.resource:
				num_resources += 1
		if num_resources > 1:
			self.current_row = 1
			self.table.resize(2,1)
			info += '\n<span weight="bold">' + _('Status: ') + '</span>'
			for contact in contacts:
				if contact.resource:
					status_line = self.get_status_info(contact.resource, contact.priority, 
						contact.show, contact.status)
					self.add_status_row(file_path, contact.show, status_line)
					
		else: # only one resource
			if contact.resource:
				info += '\n<span weight="bold">' + _('Resource: ') + \
					'</span>' + gtkgui_helpers.escape_for_pango_markup(
						contact.resource) + ' (' + str(contact.priority) + ')'
			if contact.show:
				info += '\n<span weight="bold">' + _('Status: ') + \
					'</span>' + helpers.get_uf_show(contact.show) 
				if contact.status:
					status = contact.status.strip()
					if status != '':
						# escape markup entities. Is it posible to have markup in status?
						info += ' - ' + gtkgui_helpers.escape_for_pango_markup(status)
		
		self.text_lable.set_markup(info)
		self.hbox.pack_start(self.image, False, False)
		self.hbox.pack_start(self.table, True, True)
		self.win.add(self.hbox)

class FileTransfersTooltip(BaseTooltip):
	''' Tooltip that is shown in the notification area '''
	def __init__(self):
		self.text_lable = gtk.Label()
		self.text_lable.set_line_wrap(True)
		self.text_lable.set_alignment(0, 0)
		self.text_lable.set_selectable(False)
		BaseTooltip.__init__(self)

	def populate(self, file_props):
		self.create_window()
		self.hbox = gtk.HBox()
		text = '<b>' + _('Name: ') + '</b>' 
		name = file_props['name']
		if not name and file_props['file-name']:
			if os.path.exists(file_props['file-name']):
				(path, name) = os.path.split(file_props['file-name'])
		text += gtkgui_helpers.escape_for_pango_markup(name) 
		text += '\n<b>' + _('Type: ') + '</b>'
		if file_props['type'] == 'r':
			text += _('Download')
		else:
			text += _('Upload')
		if file_props['type'] == 'r':
			text += '\n<b>' + _('Sender: ') + '</b>'
			sender = str(file_props['sender']).split('/')[0]
			name = gajim.get_first_contact_instance_from_jid( 
				file_props['tt_account'], sender).name
		else:
			text += '\n<b>' + _('Recipient: ') + '</b>' 
			receiver = file_props['receiver']
			if hasattr(receiver, 'name'):
				receiver = receiver.name
			receiver = receiver.split('/')[0]
			if receiver.find('@') == -1:
				name = receiver
			else:
				name = gajim.get_first_contact_instance_from_jid( 
				file_props['tt_account'], receiver).name
		text +=  gtkgui_helpers.escape_for_pango_markup(name)
		text += '\n<b>' + _('Size: ') + '</b>' 
		text += helpers.convert_bytes(file_props['size'])
		text += '\n<b>' + _('Transferred: ') + '</b>' 
		transfered_len = 0
		if file_props.has_key('received-len'):
			transfered_len = file_props['received-len']
		text += helpers.convert_bytes(transfered_len)
		text += '\n<b>' + _('Status: ') + '</b>' 
		status = '' 
		if not file_props.has_key('started') or not file_props['started']:
			status =  _('not started')
		elif file_props.has_key('connected'):
			if file_props.has_key('stopped') and \
				file_props['stopped'] == True:
				status = _('stopped')
			elif file_props['completed']:
					status = _('completed')
			elif file_props['connected'] == False:
				if file_props['completed']:
					status = _('completed')
			else:
				if file_props.has_key('paused') and  \
					file_props['paused'] == True:
					status = _('paused')
				elif file_props.has_key('stalled') and \
					file_props['stalled'] == True:
					status = _('stalled')
				else:
					status = _('transferring')
		else:
			status =  _('not started')
		
		text += status
		self.text_lable.set_markup(text)
		self.hbox.add(self.text_lable)
		self.win.add(self.hbox)
