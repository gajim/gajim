##	plugins/history_window.py
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

from common import i18n

_ = i18n._
APP = i18n.APP
gtk.glade.bindtextdomain(APP, i18n.DIR)
gtk.glade.textdomain(APP)

GTKGUI_GLADE='plugins/gtkgui/gtkgui.glade'

class history_window:
	"""Class for bowser agent window:
	to know the agents on the selected server"""
	def on_history_window_destroy(self, widget):
		"""close window"""
		del self.plugin.windows['logs'][self.jid]

	def on_close_button_clicked(self, widget):
		"""When Close button is clicked"""
		widget.get_toplevel().destroy()

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
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, 0, end))
		self.num_begin = self.nb_line

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
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, begin, end))
		self.num_begin = self.nb_line

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
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, begin, end))
		self.num_begin = self.nb_line

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
		self.plugin.send('LOG_GET_RANGE', None, (self.jid, begin, self.nb_line))
		self.num_begin = self.nb_line

	def new_line(self, infos):
		"""write a new line"""
		#infos = [num_line, date, type, data]
		if infos[0] < self.num_begin:
			self.num_begin = infos[0]
		if infos[0] == 50:
			self.earliest_button.set_sensitive(False)
			self.previous_button.set_sensitive(False)
		if infos[0] == self.nb_line:
			self.forward_button.set_sensitive(False)
			self.latest_button.set_sensitive(False)
		start_iter = self.history_buffer.get_start_iter()
		end_iter = self.history_buffer.get_end_iter()
		tim = time.strftime("[%x %X] ", time.localtime(float(infos[1])))
		self.history_buffer.insert(start_iter, tim)
		if infos[2] == 'recv':
			msg = ':'.join(infos[3][0:])
			msg = msg.replace('\\n', '\n')
			self.history_buffer.insert_with_tags_by_name(start_iter, msg, \
				'incoming')
		elif infos[2] == 'sent':
			msg = ':'.join(infos[3][0:])
			msg = msg.replace('\\n', '\n')
			self.history_buffer.insert_with_tags_by_name(start_iter, msg, \
				'outgoing')
		else:
			msg = ':'.join(infos[3][1:])
			msg = msg.replace('\\n', '\n')
			self.history_buffer.insert_with_tags_by_name(start_iter, \
				_('Status is now: ') + infos[3][0]+': ' + msg, 'status')
	
	def set_nb_line(self, nb_line):
		self.nb_line = nb_line
		self.num_begin = nb_line

	def __init__(self, plugin, jid):
		self.plugin = plugin
		self.jid = jid
		self.nb_line = 0
		self.num_begin = 0
		xml = gtk.glade.XML(GTKGUI_GLADE, 'history_window', APP)
		self.window = xml.get_widget('history_window')
		self.history_buffer = xml.get_widget('history_textview').get_buffer()
		self.earliest_button = xml.get_widget('earliest_button')
		self.previous_button = xml.get_widget('previous_button')
		self.forward_button = xml.get_widget('forward_button')
		self.latest_button = xml.get_widget('latest_button')
		xml.signal_autoconnect(self)
		tagIn = self.history_buffer.create_tag('incoming')
		color = self.plugin.config['inmsgcolor']
		tagIn.set_property('foreground', color)
		tagOut = self.history_buffer.create_tag('outgoing')
		color = self.plugin.config['outmsgcolor']
		tagOut.set_property('foreground', color)
		tagStatus = self.history_buffer.create_tag('status')
		color = self.plugin.config['statusmsgcolor']
		tagStatus.set_property('foreground', color)
		self.plugin.send('LOG_NB_LINE', None, jid)
