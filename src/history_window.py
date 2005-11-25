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
import calendar
import os

import gtkgui_helpers

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
		xml = gtk.glade.XML(GTKGUI_GLADE, 'history_window', APP)
		self.window = xml.get_widget('history_window')
		if account and gajim.contacts[account].has_key(jid):
			contact = gajim.get_first_contact_instance_from_jid(account, jid)
			title = _('Conversation History with %s') % contact.name
		else:
			title = _('Conversation History with %s') % jid
		self.window.set_title(title)
		self.history_buffer = xml.get_widget('history_textview').get_buffer()
		
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

		date = time.localtime()
		y, m, d = date[0], date[1], date[2]
		self.add_lines_for_date(y, m, d)
		
		self.window.show_all()

	def on_history_window_destroy(self, widget):
		del gajim.interface.instances['logs'][self.jid]

	def on_close_button_clicked(self, widget):
		self.window.destroy()

	def on_calendar_day_selected(self, widget):
		year, month, day = widget.get_date() # integers
		month = gtkgui_helpers.make_gtk_month_python_month(month)
		self.add_lines_for_date(year, month, day)
		
	def on_calendar_month_changed(self, widget):
		return #FIXME: commit this when it works as it should
		year, month, day = widget.get_date() # integers
		month = gtkgui_helpers.make_gtk_month_python_month(month)
		weekday, days_in_this_month = calendar.monthrange(year, month)
		for day in xrange(1, days_in_this_month + 1): # count from 1, so add 1 more
			#FIXME: optimize (ask db once per month and store days that have logs)
			# return those here in tupple
			#print 'ask', year, month, day
			if gajim.logger.date_has_logs(self.jid, year, month, day):
				widget.mark_day(day)
			else:
				widget.unmark_day(day)

	def add_lines_for_date(self, year, month, day):
		'''adds all the lines for given date in textbuffer'''
		self.history_buffer.set_text('') # clear the buffer first
		lines = gajim.logger.get_conversation_for_date(self.jid, year, month, day)
		# lines holds list with tupples that have:
		# contact_name, time, kind, show, message
		for line in lines:
			# line[0] is contact_name, line[1] is time of message
			# line[2] is kind, line[3] is show, line[4] is message
			self.add_new_line(line[0], line[1], line[2], line[3], line[4])
	
	def add_new_line(self, contact_name, tim, kind, show, message):
		'''add a new line in textbuffer'''
		buf = self.history_buffer
		end_iter = buf.get_end_iter()
		tim = time.strftime('[%X] ', time.localtime(float(tim)))
		buf.insert(end_iter, tim) # add time
		tag_name = ''
		tag_msg = ''
		
		if kind == 'gc_msg':
			tag_name = 'incoming'
		elif kind in ('single_msg_recv', 'chat_msg_recv'):
			try:
				contact_name = gajim.contacts[self.account][self.jid][0].name
			except:
				contact_name = self.jid.split('@')[0]
			tag_name = 'incoming'
		elif kind in ('single_msg_sent', 'chat_msg_sent'):
			contact_name = gajim.nicks[self.account]
			tag_name = 'outgoing'
		elif kind == 'gcstatus':
			# message here (if not None) is status message
			if message:
				message = _('%(nick)s is now %(status)s: %(status_msg)s') %\
					{'nick': contact_name, 'status': helpers.get_uf_show(show),
					'status_msg': message }
			else:
				message = _('%(nick)s is now %(status)s') % {'nick': contact_name,
					'status': helpers.get_uf_show(show) }
			tag_msg = 'status'
		else: # 'status'
			# message here (if not None) is status message
			if message:
				message = _('Status is now: %(status)s: %(status_msg)s') % \
					{'status': helpers.get_uf_show(show), 'status_msg': message}
			else:
				message = _('Status is now: %(status)s') % { 'status':
					helpers.get_uf_show(show) }
			tag_msg = 'status'

		# do not do this if gcstats, avoid dupping contact_name
		# eg. nkour: nkour is now Offline
		if contact_name and kind != 'gcstatus':
			# add stuff before and after contact name
			before_str = gajim.config.get('before_nickname')
			after_str = gajim.config.get('after_nickname')
			format = before_str + contact_name + after_str + ' '
			buf.insert_with_tags_by_name(end_iter, format, tag_name)

		message = message + '\n'
		if tag_msg:
			buf.insert_with_tags_by_name(end_iter, message, tag_msg)
		else:
			buf.insert(end_iter, message)
