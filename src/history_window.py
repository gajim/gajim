##	history_window.py
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
import time
import os

import dialogs

from common import gajim
from common import helpers
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class HistoryWindow:
	'''Class for browsing logs of conversations with contacts'''

	def __init__(self, jid, account):
		self.jid = jid
		self.account = account
		self.no_of_lines = gajim.logger.get_no_of_lines(jid)
		xml = gtk.glade.XML(GTKGUI_GLADE, 'history_window', APP)
		self.window = xml.get_widget('history_window')
		if account and gajim.contacts[account].has_key(jid):
			contact = gajim.get_first_contact_instance_from_jid(account, jid)
			title = _('Conversation History with %s') % contact.name
		else:
			title = _('Conversation History with %s') % jid
		self.window.set_title(title)
		self.history_buffer = xml.get_widget('history_textview').get_buffer()
		self.earliest_button = xml.get_widget('earliest_button')
		self.previous_button = xml.get_widget('previous_button')
		self.forward_button = xml.get_widget('forward_button')
		self.latest_button = xml.get_widget('latest_button')
		self.filter_entry = xml.get_widget('filter_entry')
		
		# FIXME: someday..
		filter_hbox = xml.get_widget('filter_hbox')
		filter_hbox.hide()
		filter_hbox.set_no_show_all(True)
		
		xml.signal_autoconnect(self)

		tag = self.history_buffer.create_tag('incoming')
		color = gajim.config.get('inmsgcolor')
		tag.set_property('foreground', color)

		tag = self.history_buffer.create_tag('outgoing')
		color = gajim.config.get('outmsgcolor')
		tag.set_property('foreground', color)

		tag = self.history_buffer.create_tag('status')
		color = gajim.config.get('statusmsgcolor')
		tag.set_property('foreground', color)

		begin = 0
		#FIXME: 50 is very bad. find a way to always fill size of window
		#or come up with something better in general.
		#investigate how other clients do this window
		if self.no_of_lines > 50:
			begin = self.no_of_lines - 50
		nb, lines = gajim.logger.read(self.jid, begin, self.no_of_lines)
		self.set_buttons_sensitivity(nb)
		for line in lines:
			self.new_line(line[0], line[1], line[2:])
		self.num_begin = begin
		self.window.show_all()

	def on_history_window_destroy(self, widget):
		del gajim.interface.windows['logs'][self.jid]

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_apply_filter_button_clicked(self, widget):
		filter = self.filter_entry.get_text()
		if len(filter) < 3:
			dialogs.ErrorDialog(_('Filter query too short'),
				_('Query must be at least 3 characters long.')).get_response()
			return

		# FIXME: what if jid is fake (pm)?
		path_to_file = os.path.join(gajim.LOGPATH, self.jid)
		# FIXME: ship grep.exe for windoz?
		command = 'grep %s %s' % (filter, path_to_file)
		stdout = helpers.get_output_of_command(command)
		if stdout is not None:
			text = ' '.join(stdout)
			self.history_buffer.set_text(text)

	def on_clear_filter_button_clicked(self, widget):
		pass
		# FIXME: reread from scratch (if it's possible to save current page it's even better)

	def on_earliest_button_clicked(self, widget):
		start, end = self.history_buffer.get_bounds()
		self.history_buffer.delete(start, end)
		self.earliest_button.set_sensitive(False)
		self.previous_button.set_sensitive(False)
		self.forward_button.set_sensitive(True)
		self.latest_button.set_sensitive(True)
		end = 50
		if end > self.no_of_lines:
			end = self.no_of_lines
		nb, lines = gajim.logger.read(self.jid, 0, end)
		self.set_buttons_sensitivity(nb)
		for line in lines:
			self.new_line(line[0], line[1], line[2:])
		self.num_begin = 0

	def on_previous_button_clicked(self, widget):
		start, end = self.history_buffer.get_bounds()
		self.history_buffer.delete(start, end)
		self.earliest_button.set_sensitive(True)
		self.previous_button.set_sensitive(True)
		self.forward_button.set_sensitive(True)
		self.latest_button.set_sensitive(True)
		begin = self.num_begin - 50
		if begin < 0:
			begin = 0
		end = begin + 50
		if end > self.no_of_lines:
			end = self.no_of_lines
		nb, lines = gajim.logger.read(self.jid, begin, end)
		self.set_buttons_sensitivity(nb)
		for line in lines:
			self.new_line(line[0], line[1], line[2:])
		self.num_begin = begin

	def on_forward_button_clicked(self, widget):
		start, end = self.history_buffer.get_bounds()
		self.history_buffer.delete(start, end)
		self.earliest_button.set_sensitive(True)
		self.previous_button.set_sensitive(True)
		self.forward_button.set_sensitive(True)
		self.latest_button.set_sensitive(True)
		begin = self.num_begin + 50
		if begin > self.no_of_lines:
			begin = self.no_of_lines
		end = begin + 50
		if end > self.no_of_lines:
			end = self.no_of_lines
		nb, lines = gajim.logger.read(self.jid, begin, end)
		self.set_buttons_sensitivity(nb)
		for line in lines:
			self.new_line(line[0], line[1], line[2:])
		self.num_begin = begin

	def on_latest_button_clicked(self, widget):
		start, end = self.history_buffer.get_bounds()
		self.history_buffer.delete(start, end)
		self.earliest_button.set_sensitive(True)
		self.previous_button.set_sensitive(True)
		self.forward_button.set_sensitive(False)
		self.latest_button.set_sensitive(False)
		begin = self.no_of_lines - 50
		if begin < 0:
			begin = 0
		nb, lines = gajim.logger.read(self.jid, begin, self.no_of_lines)
		self.set_buttons_sensitivity(nb)
		for line in lines:
			self.new_line(line[0], line[1], line[2:])
		self.num_begin = begin

	def set_buttons_sensitivity(self, nb):
		if nb == 50:
			self.earliest_button.set_sensitive(False)
			self.previous_button.set_sensitive(False)
		if nb == self.no_of_lines:
			self.forward_button.set_sensitive(False)
			self.latest_button.set_sensitive(False)

	def new_line(self, date, type, data):
		'''add a new line in textbuffer'''
		buff = self.history_buffer
		start_iter = buff.get_start_iter()
		tim = time.strftime('[%x %X] ', time.localtime(float(date)))
		buff.insert(start_iter, tim)
		name = None
		tag_name = ''
		tag_msg = ''
		if type == 'gc':
			name = data[0]
			msg = ':'.join(data[1:])
			tag_name = 'incoming'
		elif type == 'gcstatus':
			nick = data[0]
			show = data[1]
			status_msg = ':'.join(data[2:])
			msg = _('%s is now %s: %s') % (nick, show, status_msg)
			tag_msg = 'status'
		elif type == 'recv':
			try:
				name = gajim.contacts[self.account][self.jid][0].name
			except:
				name = None
			if not name:
				name = self.jid.split('@')[0]
			msg = ':'.join(data[0:])
			tag_name = 'incoming'
		elif type == 'sent':
			name = gajim.nicks[self.account]
			msg = ':'.join(data[0:])
			tag_name = 'outgoing'
		else:
			status_msg = ':'.join(data[1:])
			msg = _('Status is now: %s: %s') % (data[0], status_msg)
			tag_msg = 'status'

		if name:
			before_str = gajim.config.get('before_nickname')
			after_str = gajim.config.get('after_nickname')
			format = before_str + name + after_str + ' '
			buff.insert_with_tags_by_name(start_iter, format, tag_name)
		if tag_msg:
			buff.insert_with_tags_by_name(start_iter, msg, tag_msg)
		else:
			buff.insert(start_iter, msg)
