##	tooltips.py
##
## Contributors for this file:
##	- Yann Le Boulanger <asterix@lagaule.org>
##	- Nikos Kouremenos <kourem@gmail.com>
##	- Dimitur Kirov <dkirov@gmail.com>
##
## Copyright (C) 2003-2004 Yann Le Boulanger <asterix@lagaule.org>
##                         Vincent Hanquez <tab@snarc.org>
## Copyright (C) 2005 Yann Le Boulanger <asterix@lagaule.org>
##                    Vincent Hanquez <tab@snarc.org>
##                    Nikos Kouremenos <nkour@jabber.org>
##                    Dimitur Kirov <dkirov@gmail.com>
##                    Travis Shirk <travis@pobox.com>
##                    Norman Rasmussen <norman@rasmussen.co.za>
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
import time
import locale

import gtkgui_helpers
import message_control

from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP

class BaseTooltip:
	''' Base Tooltip class;
		Usage:
			tooltip = BaseTooltip()
			.... 
			tooltip.show_tooltip(data, widget_height, widget_y_position)
			....
			if tooltip.timeout != 0:
				tooltip.hide_tooltip()
		
		* data - the text to be displayed  (extenders override this argument and 
			dislpay more complex contents)
		* widget_height  - the height of the widget on which we want to show tooltip
		* widget_y_position - the vertical position of the widget on the screen
		
		Tooltip is displayed aligned centered to the mouse poiner and 4px below the widget.
		In case tooltip goes below the visible area it is shown above the widget.
	'''
	def __init__(self):
		self.timeout = 0
		self.preferred_position = [0, 0]
		self.win = None
		self.id = None
		
	def populate(self, data):
		''' this method must be overriden by all extenders
		This is the most simple implementation: show data as value of a label
		'''
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
		self.win.connect('size-request', self.on_size_request)
		self.win.connect('motion-notify-event', self.motion_notify_event)
		self.screen = self.win.get_screen()
	
	def _get_icon_name_for_tooltip(self, contact):
		''' helper function used for tooltip contacts/acounts 
		Tooltip on account has fake contact with sub == '', in this case we show
		real status of the account
		'''
		if contact.ask == 'subscribe':
			return 'requested'
		elif contact.sub in ('both', 'to', ''):
			return contact.show
		return 'not in roster'


	def motion_notify_event(self, widget, event):
		self.hide_tooltip()

	def on_size_request(self, widget, requisition):
		half_width = requisition.width / 2 + 1
		if self.preferred_position[0] < half_width: 
			self.preferred_position[0] = 0
		elif self.preferred_position[0]  + requisition.width > \
			self.screen.get_width() + half_width:
			self.preferred_position[0] = self.screen.get_width() - \
				requisition.width
		else:
			self.preferred_position[0] -= half_width 
			self.screen.get_height()
		if self.preferred_position[1] + requisition.height > \
			self.screen.get_height():
			# flip tooltip up
			self.preferred_position[1] -= requisition.height  + \
				self.widget_height + 8
		if self.preferred_position[1] < 0:
			self.preferred_position[1] = 0
		self.win.move(self.preferred_position[0], self.preferred_position[1])

	def expose(self, widget, event):
		style = self.win.get_style()
		size = self.win.get_size()
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT,
			None, self.win, 'tooltip', 0, 0, -1, 1)
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT,
			None, self.win, 'tooltip', 0, size[1] - 1, -1, 1)
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT,
			None, self.win, 'tooltip', 0, 0, 1, -1)
		style.paint_flat_box(self.win.window, gtk.STATE_NORMAL, gtk.SHADOW_OUT,
			None, self.win, 'tooltip', size[0] - 1, 0, 1, -1)
		return True
	
	def show_tooltip(self, data, widget_height, widget_y_position):
		''' show tooltip on widget.
		data contains needed data for tooltip contents
		widget_height is the height of the widget on which we show the tooltip
		widget_y_position is vertical position of the widget on the screen
		'''
		# set tooltip contents 
		self.populate(data)
		
		# get the X position of mouse pointer on the screen
		pointer_x = self.screen.get_display().get_pointer()[1]
		
		# get the prefered X position of the tooltip on the screen in case this position is > 
		# than the height of the screen, tooltip will be shown above the widget
		preferred_y = widget_y_position + widget_height + 4
		
		self.preferred_position = [pointer_x, preferred_y]
		self.widget_height =widget_height
		self.win.ensure_style()
		self.win.show_all()

	def hide_tooltip(self):
		if self.timeout > 0:
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
		self.text_label = None
		self.spacer_label = '   '
		
	def create_table(self):
		self.table = gtk.Table(3, 1)
		self.table.set_property('column-spacing', 2)
		self.text_label = gtk.Label()
		self.text_label.set_line_wrap(True)
		self.text_label.set_alignment(0, 0)
		self.text_label.set_selectable(False)
		self.table.attach(self.text_label, 1, 4, 1, 2)
		
	def get_status_info(self, resource, priority, show, status):
		str_status = resource + ' (' + unicode(priority) + ')'
		if status:
			status = status.strip()
			if status != '':
				# make sure 'status' is unicode before we send to to reduce_chars
				if isinstance(status, str):
					status = unicode(status, encoding='utf-8')
				status = gtkgui_helpers.reduce_chars_newlines(status, 0, 1)
				str_status += ' - ' + status
		return gtkgui_helpers.escape_for_pango_markup(str_status)
	
	def add_status_row(self, file_path, show, str_status, status_time = None):
		''' appends a new row with status icon to the table '''
		self.current_row += 1
		state_file = show.replace(' ', '_')
		files = []
		files.append(os.path.join(file_path, state_file + '.png'))
		files.append(os.path.join(file_path, state_file + '.gif'))
		image = gtk.Image()
		image.set_from_pixbuf(None)
		for file in files:
			if os.path.exists(file):
				image.set_from_file(file)
				break
		spacer = gtk.Label(self.spacer_label)
		image.set_alignment(0, 1.)
		self.table.attach(spacer, 1, 2, self.current_row, 
			self.current_row + 1, 0, 0, 0, 0)
		self.table.attach(image, 2, 3, self.current_row, 
			self.current_row + 1, 0, 0, 3, 0)
		status_label = gtk.Label()
		status_label.set_markup(str_status)
		status_label.set_alignment(0, 0)
		self.table.attach(status_label, 3, 4, self.current_row,
			self.current_row + 1, gtk.EXPAND | gtk.FILL, 0, 0, 0)
		if status_time:
			self.current_row += 1
			# decode locale encoded string, the same way as below (10x nk)
			local_time = time.strftime("%c", status_time)
			local_time = local_time.decode(locale.getpreferredencoding()) 
			status_time_label = gtk.Label(local_time)
			self.table.attach(status_time_label, 2, 4, self.current_row,
			self.current_row + 1, gtk.EXPAND | gtk.FILL, 0, 0, 0)
	
class NotificationAreaTooltip(BaseTooltip, StatusTable):
	''' Tooltip that is shown in the notification area '''
	def __init__(self):
		BaseTooltip.__init__(self)
		StatusTable.__init__(self)

	def get_accounts_info(self):
		accounts = []
		for account in gajim.contacts.get_accounts():
			status_idx = gajim.connections[account].connected
			# uncomment the following to hide offline accounts
			# if status_idx == 0: continue
			status = gajim.SHOW_LIST[status_idx]
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
		return accounts

	def fill_table_with_accounts(self, accounts):
		iconset = gajim.config.get('iconset')
		if not iconset:
			iconset = 'dcraven'
		file_path = os.path.join(gajim.DATA_DIR, 'iconsets', iconset, '16x16')
		for acct in accounts:
			message = acct['message']
			# before reducing the chars we should assure we send unicode, else 
			# there are possible pango TBs on 'set_markup'
			if isinstance(message, str):
				message = unicode(message, encoding = 'utf-8')
			message = gtkgui_helpers.reduce_chars_newlines(message, 50, 1)
			message = gtkgui_helpers.escape_for_pango_markup(message)
			if message:
				self.add_status_row(file_path, acct['show'], '<span weight="bold">'\
					+ gtkgui_helpers.escape_for_pango_markup(acct['name']) + \
					'</span>' + ' - ' + message)
			else:
				self.add_status_row(file_path, acct['show'], '<span weight="bold">'\
					+ gtkgui_helpers.escape_for_pango_markup(acct['name']) + \
					'</span>')

	def populate(self, data):
		self.create_window()
		self.create_table()
		self.hbox = gtk.HBox()
		self.table.set_property('column-spacing', 1)
		text, single_line = '', ''

		unread_chat = gajim.interface.roster.nb_unread
		unread_single_chat = 0
		unread_gc = 0
		unread_pm = 0

		accounts = self.get_accounts_info()

		for acct in gajim.connections:
			# Count unread chat messages
			chat_t = message_control.TYPE_CHAT
			for ctrl in gajim.interface.msg_win_mgr.get_controls(chat_t, acct):
				unread_chat += ctrl.nb_unread

			# Count unread PM messages for which we have a control
			chat_t = message_control.TYPE_PM
			for ctrl in gajim.interface.msg_win_mgr.get_controls(chat_t, acct):
				unread_pm += ctrl.nb_unread

			# we count unread gc/pm messages
			chat_t = message_control.TYPE_GC
			for ctrl in gajim.interface.msg_win_mgr.get_controls(chat_t, acct):
				# These are PMs for which the PrivateChatControl has not yet been
				# created
				pm_msgs = ctrl.get_specific_unread()
				unread_gc += ctrl.nb_unread
				unread_gc -= pm_msgs
				unread_pm += pm_msgs

		if unread_chat or unread_single_chat or unread_gc or unread_pm:
			text = ''
			if unread_chat:
				text += i18n.ngettext(
					'Gajim - %d unread message',
					'Gajim - %d unread messages',
					unread_chat, unread_chat, unread_chat)
				text += '\n'
			if unread_single_chat:
				text += i18n.ngettext(
					'Gajim - %d unread single message',
					'Gajim - %d unread single messages',
					unread_single_chat, unread_single_chat, unread_single_chat)
				text += '\n'
			if unread_gc:
				text += i18n.ngettext(
					'Gajim - %d unread group chat message',
					'Gajim - %d unread group chat messages',
					unread_gc, unread_gc, unread_gc)
				text += '\n'
			if unread_pm:
				text += i18n.ngettext(
					'Gajim - %d unread private message',
					'Gajim - %d unread private messages',
					unread_pm, unread_pm, unread_pm)
				text += '\n'
			text = text[:-1] # remove latest \n
		elif len(accounts) > 1:
			text = _('Gajim')
			self.current_row = 1
			self.table.resize(2, 1)
			self.fill_table_with_accounts(accounts)

		elif len(accounts) == 1:
			message = accounts[0]['status_line']
			message = gtkgui_helpers.reduce_chars_newlines(message, 50, 1)
			message = gtkgui_helpers.escape_for_pango_markup(message)
			text = _('Gajim - %s') % message
		else:
			text = _('Gajim - %s') % helpers.get_uf_show('offline')
		self.text_label.set_markup(text)
		self.hbox.add(self.table)
		self.win.add(self.hbox)

class GCTooltip(BaseTooltip):
	''' Tooltip that is shown in the GC treeview '''
	def __init__(self):
		self.account = None

		self.text_label = gtk.Label()
		self.text_label.set_line_wrap(True)
		self.text_label.set_alignment(0, 0)
		self.text_label.set_selectable(False)

		BaseTooltip.__init__(self)
		
	def populate(self, contact):
		if not contact:
			return
		self.create_window()
		hbox = gtk.HBox()
		
		if contact.jid.strip() != '':
			info = '<span size="large" weight="bold">' + contact.jid + '</span>'
		else:
			info = '<span size="large" weight="bold">' + contact.get_shown_name() \
				+ '</span>'
			
		info += '\n<span weight="bold">' + _('Role: ') + '</span>' + \
			 helpers.get_uf_role(contact.role)

		info += '\n<span weight="bold">' + _('Affiliation: ') + '</span>' + \
			contact.affiliation.capitalize()

		info += '\n<span weight="bold">' + _('Status: ') + \
					'</span>' + helpers.get_uf_show(contact.show)
		
		if contact.status:
			status = contact.status.strip()
			if status != '':
				# escape markup entities
				info += ' - ' + gtkgui_helpers.escape_for_pango_markup(status)
		
		if hasattr(contact, 'resource') and contact.resource.strip() != '':
			info += '\n<span weight="bold">' + _('Resource: ') + \
					'</span>' + gtkgui_helpers.escape_for_pango_markup(
						contact.resource) 

		self.text_label.set_markup(info)
		hbox.add(self.text_label)
		self.win.add(hbox)

class RosterTooltip(NotificationAreaTooltip):
	''' Tooltip that is shown in the roster treeview '''
	def __init__(self):
		self.account = None
		self.image = gtk.Image()
		self.image.set_alignment(0, 0)
		# padding is independent of the total length and better than alignment
		self.image.set_padding(1, 2) 
		self.avatar_image = gtk.Image()
		NotificationAreaTooltip.__init__(self)

	def populate(self, contacts):
		self.create_window()
		self.hbox = gtk.HBox()
		self.hbox.set_homogeneous(False)
		self.hbox.set_spacing(2)
		self.create_table()
		if not contacts or len(contacts) == 0:
			# Tooltip for merged accounts row
			accounts = self.get_accounts_info()
			self.current_row = 0
			self.table.resize(2, 1)
			self.spacer_label = ''
			self.fill_table_with_accounts(accounts)
			self.hbox.add(self.table)
			self.win.add(self.hbox)
			return
		# primary contact
		prim_contact = gajim.contacts.get_highest_prio_contact_from_contacts(
			contacts)
		# try to find the image for the contact status
		icon_name = self._get_icon_name_for_tooltip(prim_contact)
		state_file = icon_name.replace(' ', '_')
		transport = gajim.get_transport_name_from_jid(prim_contact.jid)
		if transport:
			file_path = os.path.join(gajim.DATA_DIR, 'iconsets', 'transports', 
				transport , '16x16')
		else:
			iconset = gajim.config.get('iconset')
			if not iconset:
				iconset = 'dcraven'
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
			gtkgui_helpers.escape_for_pango_markup(prim_contact.get_shown_name())
		if prim_contact.sub:
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
					status_line = self.get_status_info(contact.resource,
						contact.priority, contact.show, contact.status)
					
					icon_name = self._get_icon_name_for_tooltip(contact)
					self.add_status_row(file_path, icon_name, status_line,
						contact.last_status_time)
					
		else: # only one resource
			if contact.resource:
				info += '\n<span weight="bold">' + _('Resource: ') + \
					'</span>' + gtkgui_helpers.escape_for_pango_markup(
						contact.resource) + ' (' + unicode(contact.priority) + ')'
			if contact.show:
				info += '\n<span weight="bold">' + _('Status: ') + \
					'</span>' + helpers.get_uf_show(contact.show) 
				if contact.status:
					status = contact.status.strip()
					if status != '':
						# reduce long status
						# (no more than 130 chars on line and no more than 5 lines)
						status = gtkgui_helpers.reduce_chars_newlines(status, 130, 5)
						# escape markup entities. 
						info += ' - ' + gtkgui_helpers.escape_for_pango_markup(status)
			if contact.last_status_time:
				if contact.show == 'offline':
					text = _('Last status on %s')
				else:
					text = _('Since %s')

				# time.strftime returns locale encoded string
				local_time = time.strftime('%c', contact.last_status_time)
				local_time = local_time.decode(locale.getpreferredencoding()) 
				text = text % local_time 
				info += '\n<span style="italic">%s</span>' % text
		
		# uncomment this
		#~ for type_ in ('jpeg', 'png'):
			#~ file = os.path.join(gajim.AVATAR_PATH, prim_contact.jid + '.' + type_)
			#~ if os.path.exists(file):
				#~ self.avatar_image.set_from_file(file)
				#~ pix = self.avatar_image.get_pixbuf()
				#~ pix = gtkgui_helpers.get_scaled_pixbuf(pix, 'tooltip')
				#~ self.avatar_image.set_from_pixbuf(pix)
				#~ break
		#~ else:
			#~ self.avatar_image.set_from_pixbuf(None)
		self.text_label.set_markup(info)
		self.hbox.pack_start(self.image, False, False)
		self.hbox.pack_start(self.table, True, True)
		#~ self.hbox.pack_start(self.avatar_image, False, False)
		self.win.add(self.hbox)

class FileTransfersTooltip(BaseTooltip):
	''' Tooltip that is shown in the notification area '''
	def __init__(self):
		self.text_label = gtk.Label()
		self.text_label.set_line_wrap(True)
		self.text_label.set_alignment(0, 0)
		self.text_label.set_selectable(False)
		BaseTooltip.__init__(self)

	def populate(self, file_props):
		self.create_window()
		self.hbox = gtk.HBox()
		text = '<b>' + _('Name: ') + '</b>' 
		name = file_props['name']
		if file_props['type'] == 'r':
			(file_path, file_name) = os.path.split(file_props['file-name'])
		else:
			file_name = file_props['name']
		text += gtkgui_helpers.escape_for_pango_markup(file_name) 
		text += '\n<b>' + _('Type: ') + '</b>'
		if file_props['type'] == 'r':
			text += _('Download')
			text += '\n<b>' + _('Sender: ') + '</b>'
			sender = unicode(file_props['sender']).split('/')[0]
			name = gajim.contacts.get_first_contact_from_jid( 
				file_props['tt_account'], sender).get_shown_name()
		else:
			text += _('Upload')
			text += '\n<b>' + _('Recipient: ') + '</b>' 
			receiver = file_props['receiver']
			if hasattr(receiver, 'name'):
				name = receiver.get_shown_name()
			else:
				name = receiver.split('/')[0]
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
			status =  _('Not started')
		elif file_props.has_key('connected'):
			if file_props.has_key('stopped') and \
				file_props['stopped'] == True:
				status = _('Stopped')
			elif file_props['completed']:
					status = _('Completed')
			elif file_props['connected'] == False:
				if file_props['completed']:
					status = _('Completed')
			else:
				if file_props.has_key('paused') and  \
					file_props['paused'] == True:
					status = _('Paused')
				elif file_props.has_key('stalled') and \
					file_props['stalled'] == True:
					#stalled is not paused. it is like 'frozen' it stopped alone
					status = _('Stalled')
				else:
					status = _('Transferring')
		else:
			status =  _('Not started')
		
		text += status
		self.text_label.set_markup(text)
		self.hbox.add(self.text_label)
		self.win.add(self.hbox)


class ServiceDiscoveryTooltip(BaseTooltip):
	''' Tooltip that is shown when hovering over a service discovery row '''
	def populate(self, status):
		self.create_window()
		label = gtk.Label()
		label.set_line_wrap(True)
		label.set_alignment(0, 0)
		label.set_selectable(False)
		if status == 1:
			label.set_text(
				_('This service has not yet responded with detailed information'))
		elif status == 2:
			label.set_text(
				_('This service could not respond with detailed information.\n'
				'It is most likely legacy or broken'))
		self.win.add(label)
