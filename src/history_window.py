# -*- coding:utf-8 -*-
## src/history_window.py
##
## Copyright (C) 2003-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005 Vincent Hanquez <tab AT snarc.org>
## Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
##                    Travis Shirk <travis AT pobox.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
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

import gtk
import gobject
import time
import calendar

import gtkgui_helpers
import conversation_textview

from common import gajim
from common import helpers
from common import exceptions

from common.logger import Constants

constants = Constants()

# Completion dict
(
C_INFO_JID,
C_INFO_ACCOUNT,
C_INFO_NAME,
C_INFO_COMPLETION
) = range(4)

# contact_name, date, message, time
(
C_LOG_JID,
C_CONTACT_NAME,
C_UNIXTIME,
C_MESSAGE,
C_TIME
) = range(5)

class HistoryWindow:
	'''Class for browsing logs of conversations with contacts'''

	def __init__(self, jid = None, account = None):
		xml = gtkgui_helpers.get_glade('history_window.glade')
		self.window = xml.get_widget('history_window')
		self.jid_entry = xml.get_widget('jid_entry')
		self.calendar = xml.get_widget('calendar')
		scrolledwindow = xml.get_widget('scrolledwindow')
		self.history_textview = conversation_textview.ConversationTextview(
			account, used_in_history_window = True)
		scrolledwindow.add(self.history_textview.tv)
		self.history_buffer = self.history_textview.tv.get_buffer()
		self.history_buffer.create_tag('highlight', background = 'yellow')
		self.checkbutton = xml.get_widget('log_history_checkbutton')
		self.checkbutton.connect('toggled',
			self.on_log_history_checkbutton_toggled)
		self.query_entry = xml.get_widget('query_entry')
		self.query_combobox = xml.get_widget('query_combobox')
		self.query_combobox.set_active(0)
		self.results_treeview = xml.get_widget('results_treeview')
		self.results_window = xml.get_widget('results_scrolledwindow')

		# contact_name, date, message, time
		model = gtk.ListStore(str, str, str, str, str)
		self.results_treeview.set_model(model)
		col = gtk.TreeViewColumn(_('Name'))
		self.results_treeview.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = C_CONTACT_NAME)
		col.set_sort_column_id(C_CONTACT_NAME) # user can click this header and sort
		col.set_resizable(True)

		col = gtk.TreeViewColumn(_('Date'))
		self.results_treeview.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = C_UNIXTIME)
		col.set_sort_column_id(C_UNIXTIME) # user can click this header and sort
		col.set_resizable(True)

		col = gtk.TreeViewColumn(_('Message'))
		self.results_treeview.append_column(col)
		renderer = gtk.CellRendererText()
		col.pack_start(renderer)
		col.set_attributes(renderer, text = C_MESSAGE)
		col.set_resizable(True)

		self.jid = None # The history we are currently viewing
		self.account = None
		self.completion_dict = {}
		self.accounts_seen_online = [] # Update dict when new accounts connect
		self.jids_to_search = []

		# This will load history too
		gobject.idle_add(self._fill_completion_dict().next)

		if jid:
			self.jid_entry.set_text(jid)
		else:
			self._load_history(None)

		gtkgui_helpers.resize_window(self.window,
			gajim.config.get('history_window_width'),
			gajim.config.get('history_window_height'))
		gtkgui_helpers.move_window(self.window,
			gajim.config.get('history_window_x-position'),
			gajim.config.get('history_window_y-position'))

		xml.signal_autoconnect(self)
		self.window.show_all()

	def _fill_completion_dict(self):
		'''Fill completion_dict for key auto completion. Then load history for
		current jid (by calling another function).

		Key will be either jid or full_completion_name
		(contact name or long description like "pm-contact from groupchat....")

		{key : (jid, account, nick_name, full_completion_name}
		this is a generator and does pseudo-threading via idle_add()
		'''
		liststore = gtkgui_helpers.get_completion_liststore(self.jid_entry)

		# Add all jids in logs.db:
		db_jids = gajim.logger.get_jids_in_db()
		self.completion_dict = dict.fromkeys(db_jids)

		self.accounts_seen_online = gajim.contacts.get_accounts()[:]

		# Enhance contacts of online accounts with contact. Needed for mapping below
		for account in self.accounts_seen_online:
			self.completion_dict.update(
				helpers.get_contact_dict_for_account(account))

		muc_active_img = gtkgui_helpers.load_icon('muc_active')
		contact_img = gajim.interface.jabber_state_images['16']['online']
		muc_active_pix = muc_active_img.get_pixbuf()
		contact_pix = contact_img.get_pixbuf()

		keys = self.completion_dict.keys()
		# Move the actual jid at first so we load history faster
		actual_jid = self.jid_entry.get_text().decode('utf-8')
		if actual_jid in keys:
			keys.remove(actual_jid)
			keys.insert(0, actual_jid)
		if None in keys:
			keys.remove(None)
		# Map jid to info tuple
		# Warning : This for is time critical with big DB
		for key in keys:
			completed = key
			contact = self.completion_dict[completed]
			if contact:
				info_name = contact.get_shown_name()
				info_completion = info_name
				info_jid = contact.jid
			else:
				# Corrensponding account is offline, we know nothing
				info_name = completed.split('@')[0]
				info_completion = completed
				info_jid = completed

			info_acc = self._get_account_for_jid(info_jid)

			if gajim.logger.jid_is_room_jid(completed) or\
			gajim.logger.jid_is_from_pm(completed):
				pix = muc_active_pix
				if gajim.logger.jid_is_from_pm(completed):
					# It's PM. Make it easier to find
					room, nick = gajim.get_room_and_nick_from_fjid(completed)
					info_completion = '%s from %s' % (nick, room)
					completed = info_completion
					info_name = nick
			else:
				pix = contact_pix

			liststore.append((pix, completed))
			self.completion_dict[key] = (info_jid, info_acc, info_name,
				info_completion)
			self.completion_dict[completed] = (info_jid, info_acc,
				info_name, info_completion)
			if key == actual_jid:
				self._load_history(info_jid, info_acc)
			yield True
		keys.sort()
		yield False

	def _get_account_for_jid(self, jid):
		'''Return the corresponding account of the jid.
		May be None if an account could not be found'''
		accounts = gajim.contacts.get_accounts()
		account = None
		for acc in accounts:
			jid_list = gajim.contacts.get_jid_list(acc)
			gc_list = gajim.contacts.get_gc_list(acc)
			if jid in jid_list or jid in gc_list:
				account = acc
				break
		return account

	def on_history_window_destroy(self, widget):
		self.history_textview.del_handlers()
		del gajim.interface.instances['logs']

	def on_history_window_key_press_event(self, widget, event):
		if event.keyval == gtk.keysyms.Escape:
			self.save_state()
			self.window.destroy()

	def on_close_button_clicked(self, widget):
		self.save_state()
		self.window.destroy()

	def on_jid_entry_activate(self, widget):
		if not self.query_combobox.get_active() < 0:
			# Don't disable querybox when we have changed the combobox
			# to GC or All and hit enter
			return
		jid = self.jid_entry.get_text().decode('utf-8')
		account = None # we don't know the account, could be any. Search for it!
		self._load_history(jid, account)
		self.results_window.set_property('visible', False)

	def on_jid_entry_focus(self, widget, event):
			widget.select_region(0, -1) # select text

	def _load_history(self, jid_or_name, account = None):
		'''Load history for the given jid/name and show it'''
		if jid_or_name and jid_or_name in self.completion_dict:
			# a full qualified jid or a contact name was entered
			info_jid, info_account, info_name, info_completion = self.completion_dict[jid_or_name]
			self.jids_to_search = [info_jid]
			self.jid = info_jid

			if account:
				self.account = account
			else:
				self.account = info_account
			if self.account is None:
				# We don't know account. Probably a gc not opened or an
				# account not connected.
				# Disable possibility to say if we want to log or not
				self.checkbutton.set_sensitive(False)
			else:
				# Are log disabled for account ?
				if self.account in gajim.config.get_per('accounts', self.account,
					'no_log_for').split(' '):
					self.checkbutton.set_active(False)
					self.checkbutton.set_sensitive(False)
				else:
					# Are log disabled for jid ?
					log = True
					if self.jid in gajim.config.get_per('accounts', self.account,
						'no_log_for').split(' '):
						log = False
					self.checkbutton.set_active(log)
					self.checkbutton.set_sensitive(True)

			self.jids_to_search = [info_jid]

			# select logs for last date we have logs with contact
			self.calendar.set_sensitive(True)
			last_log = \
				gajim.logger.get_last_date_that_has_logs(self.jid, self.account)

			date = time.localtime(last_log)

			y, m, d = date[0], date[1], date[2]
			gtk_month = gtkgui_helpers.make_python_month_gtk_month(m)
			self.calendar.select_month(gtk_month, y)
			self.calendar.select_day(d)

			self.query_entry.set_sensitive(True)
			self.query_entry.grab_focus()

			title = _('Conversation History with %s') % info_name
			self.window.set_title(title)
			self.jid_entry.set_text(info_completion)

		else:	# neither a valid jid, nor an existing contact name was entered
			# we have got nothing to show or to search in
			self.jid = None
			self.account = None

			self.history_buffer.set_text('') # clear the buffer
			self.query_entry.set_sensitive(False)

			self.checkbutton.set_sensitive(False)
			self.calendar.set_sensitive(False)
			self.calendar.clear_marks()

			self.results_window.set_property('visible', False)

			title = _('Conversation History')
			self.window.set_title(title)

	def on_calendar_day_selected(self, widget):
		if not self.jid:
			return
		year, month, day = widget.get_date() # integers
		month = gtkgui_helpers.make_gtk_month_python_month(month)
		self._add_lines_for_date(year, month, day)

	def on_calendar_month_changed(self, widget):
		'''asks for days in this month if they have logs it bolds them (marks
		them)
		'''
		if not self.jid:
			return
		year, month, day = widget.get_date() # integers
		# in gtk January is 1, in python January is 0,
		# I want the second
		# first day of month is 1 not 0
		widget.clear_marks()
		month = gtkgui_helpers.make_gtk_month_python_month(month)
		days_in_this_month = calendar.monthrange(year, month)[1]
		try:
			log_days = gajim.logger.get_days_with_logs(self.jid, year, month,
				days_in_this_month, self.account)
		except exceptions.PysqliteOperationalError, e:
			dialogs.ErrorDialog(_('Disk Error'), str(e))
			return
		for day in log_days:
			widget.mark_day(day)

	def _get_string_show_from_constant_int(self, show):
		if show == constants.SHOW_ONLINE:
			show = 'online'
		elif show == constants.SHOW_CHAT:
			show = 'chat'
		elif show == constants.SHOW_AWAY:
			show = 'away'
		elif show == constants.SHOW_XA:
			show = 'xa'
		elif show == constants.SHOW_DND:
			show = 'dnd'
		elif show == constants.SHOW_OFFLINE:
			show = 'offline'

		return show

	def _add_lines_for_date(self, year, month, day):
		'''adds all the lines for given date in textbuffer'''
		self.history_buffer.set_text('') # clear the buffer first
		self.last_time_printout = 0

		lines = gajim.logger.get_conversation_for_date(self.jid, year, month, day, self.account)
		# lines holds list with tupples that have:
		# contact_name, time, kind, show, message
		for line in lines:
			# line[0] is contact_name, line[1] is time of message
			# line[2] is kind, line[3] is show, line[4] is message
			self._add_new_line(line[0], line[1], line[2], line[3], line[4])

	def _add_new_line(self, contact_name, tim, kind, show, message):
		'''add a new line in textbuffer'''
		if not message and kind not in (constants.KIND_STATUS,
			constants.KIND_GCSTATUS):
			return
		buf = self.history_buffer
		end_iter = buf.get_end_iter()

		if gajim.config.get('print_time') == 'always':
			timestamp_str = gajim.config.get('time_stamp')
			timestamp_str = helpers.from_one_line(timestamp_str)
			tim = time.strftime(timestamp_str, time.localtime(float(tim)))
			buf.insert(end_iter, tim) # add time
		elif gajim.config.get('print_time') == 'sometimes':
			every_foo_seconds = 60 * gajim.config.get(
				'print_ichat_every_foo_minutes')
			seconds_passed = tim - self.last_time_printout
			if seconds_passed > every_foo_seconds:
				self.last_time_printout = tim
				tim = time.strftime('%X ', time.localtime(float(tim)))
				buf.insert_with_tags_by_name(end_iter, tim + '\n',
					'time_sometimes')

		tag_name = ''
		tag_msg = ''

		show = self._get_string_show_from_constant_int(show)

		if kind == constants.KIND_GC_MSG:
			tag_name = 'incoming'
		elif kind in (constants.KIND_SINGLE_MSG_RECV,
		constants.KIND_CHAT_MSG_RECV):
			contact_name = self.completion_dict[self.jid][C_INFO_NAME]
			tag_name = 'incoming'
		elif kind in (constants.KIND_SINGLE_MSG_SENT,
		constants.KIND_CHAT_MSG_SENT):
			if self.account:
				contact_name = gajim.nicks[self.account]
			else:
				# we don't have roster, we don't know our own nick, use first
				# account one (urk!)
				account = gajim.contacts.get_accounts()[0]
				contact_name = gajim.nicks[account]
			tag_name = 'outgoing'
		elif kind == constants.KIND_GCSTATUS:
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

		if message.startswith('/me ') or message.startswith('/me\n'):
			tag_msg = tag_name
		else:
			# do not do this if gcstats, avoid dupping contact_name
			# eg. nkour: nkour is now Offline
			if contact_name and kind != constants.KIND_GCSTATUS:
				# add stuff before and after contact name
				before_str = gajim.config.get('before_nickname')
				before_str = helpers.from_one_line(before_str)
				after_str = gajim.config.get('after_nickname')
				after_str = helpers.from_one_line(after_str)
				format = before_str + contact_name + after_str + ' '
				buf.insert_with_tags_by_name(end_iter, format, tag_name)

		message = message + '\n'
		if tag_msg:
			self.history_textview.print_real_text(message, [tag_msg],
				name=contact_name)
		else:
			self.history_textview.print_real_text(message, name=contact_name)

	def on_query_entry_activate(self, widget):
		text = self.query_entry.get_text()
		model = self.results_treeview.get_model()
		model.clear()
		if text == '':
			self.results_window.set_property('visible', False)
			return
		else:
			self.results_window.set_property('visible', True)

		# perform search in preselected jids
		# jids are preselected with the query_combobox (all, single jid...)
		for jid in self.jids_to_search:
			account = self.completion_dict[jid][C_INFO_ACCOUNT]
			if account is None:
				# We do not know an account. This can only happen if the contact is offine,
				# or if we browse a groupchat history. The account is not needed, a dummy can
				# be set.
				# This may leed to wrong self nick in the displayed history (Uggh!)
				account = gajim.contacts.get_accounts()[0]

			# contact_name, time, kind, show, message, subject
			results = gajim.logger.get_search_results_for_query(
						jid, text, account)
			#FIXME:
			# add "subject:  | message: " in message column if kind is single
			# also do we need show at all? (we do not search on subject)
			for row in results:
				contact_name = row[0]
				if not contact_name:
					kind = row[2]
					if kind == constants.KIND_CHAT_MSG_SENT: # it's us! :)
						contact_name = gajim.nicks[account]
					else:
						contact_name = self.completion_dict[jid][C_INFO_NAME]
				tim = row[1]
				message = row[4]
				local_time = time.localtime(tim)
				date = time.strftime('%Y-%m-%d', local_time)

				#  jid (to which log is assigned to), name, date, message,
				# time (full unix time)
				model.append((jid, contact_name, date, message, tim))

	def on_query_combobox_changed(self, widget):
		if self.query_combobox.get_active() < 0:
			return # custom entry
		self.account = None
		self.jid = None
		self.jids_to_search = []
		self._load_history(None) # clear textview

		if self.query_combobox.get_active() == 0:
			# JID or Contact name
			self.query_entry.set_sensitive(False)
			self.jid_entry.grab_focus()
		if self.query_combobox.get_active() == 1:
			# Groupchat Histories
			self.query_entry.set_sensitive(True)
			self.query_entry.grab_focus()
			self.jids_to_search = (jid for jid in gajim.logger.get_jids_in_db()
					if gajim.logger.jid_is_room_jid(jid))
		if self.query_combobox.get_active() == 2:
			# All Chat Histories
			self.query_entry.set_sensitive(True)
			self.query_entry.grab_focus()
			self.jids_to_search = gajim.logger.get_jids_in_db()

	def on_results_treeview_row_activated(self, widget, path, column):
		'''a row was double clicked, get date from row, and select it in calendar
		which results to showing conversation logs for that date'''
		# get currently selected date
		cur_year, cur_month = self.calendar.get_date()[0:2]
		cur_month = gtkgui_helpers.make_gtk_month_python_month(cur_month)
		model = widget.get_model()
		# make it a tupple (Y, M, D, 0, 0, 0...)
		tim = time.strptime(model[path][C_UNIXTIME], '%Y-%m-%d')
		year = tim[0]
		gtk_month = tim[1]
		month = gtkgui_helpers.make_python_month_gtk_month(gtk_month)
		day = tim[2]

		# switch to belonging logfile if necessary
		log_jid = model[path][C_LOG_JID]
		if log_jid != self.jid:
			self._load_history(log_jid, None)

		# avoid reruning mark days algo if same month and year!
		if year != cur_year or gtk_month != cur_month:
			self.calendar.select_month(month, year)

		self.calendar.select_day(day)
		unix_time = model[path][C_TIME]
		self._scroll_to_result(unix_time)
		#FIXME: one day do not search just for unix_time but the whole and user
		# specific format of the textbuffer line [time] nick: message
		# and highlight all that

	def _scroll_to_result(self, unix_time):
		'''scrolls to the result using unix_time and highlight line'''
		start_iter = self.history_buffer.get_start_iter()
		local_time = time.localtime(float(unix_time))
		tim = time.strftime('%X', local_time)
		result = start_iter.forward_search(tim, gtk.TEXT_SEARCH_VISIBLE_ONLY,
			None)
		if result is not None:
			match_start_iter, match_end_iter = result
			match_start_iter.backward_char() # include '[' or other character before time
			match_end_iter.forward_line() # highlight all message not just time
			self.history_buffer.apply_tag_by_name('highlight', match_start_iter,
				match_end_iter)

			match_start_mark = self.history_buffer.create_mark('match_start',
				match_start_iter, True)
			self.history_textview.tv.scroll_to_mark(match_start_mark, 0, True)

	def on_log_history_checkbutton_toggled(self, widget):
		# log conversation history?
		oldlog = True
		no_log_for = gajim.config.get_per('accounts', self.account,
			'no_log_for').split()
		if self.jid in no_log_for:
			oldlog = False
		log = widget.get_active()
		if not log and not self.jid in no_log_for:
			no_log_for.append(self.jid)
		if log and self.jid in no_log_for:
			no_log_for.remove(self.jid)
		if oldlog != log:
			gajim.config.set_per('accounts', self.account, 'no_log_for',
				' '.join(no_log_for))

	def open_history(self, jid, account):
		'''Load chat history of the specified jid'''
		self.jid_entry.set_text(jid)
		if account and account not in self.accounts_seen_online:
			# Update dict to not only show bare jid
			gobject.idle_add(self._fill_completion_dict().next)
		else:
			# Only in that case because it's called by self._fill_completion_dict()
			# otherwise
			self._load_history(jid, account)
		self.results_window.set_property('visible', False)

	def save_state(self):
		x,y = self.window.window.get_root_origin()
		width, height = self.window.get_size()

		gajim.config.set('history_window_x-position', x)
		gajim.config.set('history_window_y-position', y)
		gajim.config.set('history_window_width', width);
		gajim.config.set('history_window_height', height);

		gajim.interface.save_config()

# vim: se ts=3:
