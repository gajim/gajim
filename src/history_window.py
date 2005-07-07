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

from common import gajim
from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE = 'gtkgui.glade'

class HistoryWindow:
	"""Class for bowser agent window:
	to know the agents on the selected server"""
	def on_history_window_destroy(self, widget):
		del self.plugin.windows['logs'][self.jid]

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_earliest_button_clicked(self, widget):
		start, end = self.history_buffer.get_bounds()
		self.history_buffer.delete(start, end)
		self.earliest_button.set_sensitive(False)
		self.previous_button.set_sensitive(False)
		self.forward_button.set_sensitive(True)
		self.latest_button.set_sensitive(True)
		end = 50
		if end > self.nb_line:
			end = self.nb_line
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
		if end > self.nb_line:
			end = self.nb_line
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
		if begin > self.nb_line:
			begin = self.nb_line
		end = begin + 50
		if end > self.nb_line:
			end = self.nb_line
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
		begin = self.nb_line - 50
		if begin < 0:
			begin = 0
		nb, lines = gajim.logger.read(self.jid, begin, self.nb_line)
		self.set_buttons_sensitivity(nb)
		for line in lines:
			self.new_line(line[0], line[1], line[2:])
		self.num_begin = begin

	def set_buttons_sensitivity(self, nb):
		if nb == 50:
			self.earliest_button.set_sensitive(False)
			self.previous_button.set_sensitive(False)
		if nb == self.nb_line:
			self.forward_button.set_sensitive(False)
			self.latest_button.set_sensitive(False)

	def new_line(self, date, type, data):
		"""write a new line"""
		buffer = self.history_buffer
		start_iter = buffer.get_start_iter()
		end_iter = buffer.get_end_iter()
		tim = time.strftime('[%x %X] ', time.localtime(float(date)))
		buffer.insert(start_iter, tim)
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
				name = self.plugin.roster.contacts[self.account][self.jid][0].name
			except:
				name = None
			if not name:
				name = self.jid.split('@')[0]
			msg = ':'.join(data[0:])
			tag_name = 'incoming'
		elif type == 'sent':
			name = self.plugin.nicks[self.account]
			msg = ':'.join(data[0:])
			tag_name = 'outgoing'
		else:
			status_msg = ':'.join(data[1:])
			msg = _('Status is now: ') + data[0] + ': ' + status_msg
			tag_msg = 'status'

		if name:
			before_str = gajim.config.get('before_nickname')
			after_str = gajim.config.get('after_nickname')
			format = before_str + name + after_str + ' '
			buffer.insert_with_tags_by_name(start_iter, format, tag_name)
		if tag_msg:
			buffer.insert_with_tags_by_name(start_iter, msg, tag_msg)
		else:
			buffer.insert(start_iter, msg)
	
	def __init__(self, plugin, jid, account):
		self.plugin = plugin
		self.jid = jid
		self.account = account
		self.nb_line = gajim.logger.get_nb_line(jid)
		xml = gtk.glade.XML(GTKGUI_GLADE, 'history_window', APP)
		self.window = xml.get_widget('history_window')
		if account and self.plugin.roster.contacts[account].has_key(jid):
			list_users = self.plugin.roster.contacts[account][self.jid]
			user = list_users[0]
			title = 'Conversation History with ' + user.name
		else:
			title = 'Conversation History with ' + jid
		self.window.set_title(title)
		self.history_buffer = xml.get_widget('history_textview').get_buffer()
		self.earliest_button = xml.get_widget('earliest_button')
		self.previous_button = xml.get_widget('previous_button')
		self.forward_button = xml.get_widget('forward_button')
		self.latest_button = xml.get_widget('latest_button')
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
		if self.nb_line > 50:
			begin = self.nb_line - 50
		nb, lines = gajim.logger.read(self.jid, begin, self.nb_line)
		self.set_buttons_sensitivity(nb)
		for line in lines:
			self.new_line(line[0], line[1], line[2:])
		self.num_begin = begin
		self.window.show_all()
