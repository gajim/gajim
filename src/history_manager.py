#! /usr/bin/env python
## history_manager.py
##
## Copyright (C) 2006 Nikos Kouremenos <kourem@gmail.com>
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

## NOTE: some method names may match those of logger.py but that's it
## someday (TM) should have common class that abstracts db connections and helpers on it
## the same can be said for history_window.py

import sys
import os
import signal
import gtk
import gtk.glade
import time

import exceptions
import dialogs
from common.logger import LOG_DB_PATH, constants

from common import i18n
_ = i18n._
gtk.glade.bindtextdomain(i18n.APP, i18n.DIR)
gtk.glade.textdomain(i18n.APP)

# time, message, subject
(
C_UNIXTIME,
C_MESSAGE,
C_SUBJECT
) = range(2, 5)

try:
	from pysqlite2 import dbapi2 as sqlite
except ImportError:
	raise exceptions.PysqliteNotAvailable


class HistoryManager:

	def __init__(self):
		if not os.path.exists(LOG_DB_PATH):
			dialogs.ErrorDialog(_('Cannot find history logs database'),
				'%s does not exist.' % LOG_DB_PATH).get_response()
			sys.exit()
		
		xml = gtk.glade.XML('history_manager.glade',
			'history_manager_window', i18n.APP)
		self.window = xml.get_widget('history_manager_window')
		self.jids_listview = xml.get_widget('jids_listview')
		self.logs_listview = xml.get_widget('logs_listview')
		self.search_results_listview = xml.get_widget('search_results_listview')
		self.search_entry = xml.get_widget('search_entry')
		self.logs_scrolledwindow = xml.get_widget('logs_scrolledwindow')
		self.search_results_scrolledwindow = xml.get_widget(
			'search_results_scrolledwindow')
		self.welcome_label = xml.get_widget('welcome_label')
			
		self.logs_scrolledwindow.set_no_show_all(True)
		self.search_results_scrolledwindow.set_no_show_all(True)
		
		self.jids_already_in = [] # holds jids that we already have in DB
		self.AT_LEAST_ONE_DELETION_DONE = False
		
		self.con = sqlite.connect(LOG_DB_PATH, timeout = 20.0,
			isolation_level = 'IMMEDIATE')
		self.cur = self.con.cursor()

		self._init_jids_listview()
		self._init_logs_listview()
		self._init_search_results_listview()
		
		self._fill_jids_listview()
		
		self.search_entry.grab_focus()

		self.window.maximize()
		self.window.show_all()
		
		xml.signal_autoconnect(self)
	
	def _init_jids_listview(self):
		self.jids_liststore = gtk.ListStore(str, str) # jid, jid_id
		self.jids_listview.set_model(self.jids_liststore)
		self.jids_listview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

		renderer_text = gtk.CellRendererText() # holds jid
		col = gtk.TreeViewColumn('Contacts', renderer_text, text = 0)
		self.jids_listview.append_column(col)
		
		self.jids_listview.get_selection().connect('changed',
			self.on_jids_listview_selection_changed)

	def _init_logs_listview(self):
		# log_line_id (HIDDEN), jid_id (HIDDEN), time, message, subject
		self.logs_liststore = gtk.ListStore(str, str, str, str, str)
		self.logs_listview.set_model(self.logs_liststore)
		self.logs_listview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

		renderer_text = gtk.CellRendererText() # holds time
		col = gtk.TreeViewColumn('Time', renderer_text, text = C_UNIXTIME)
		col.set_sort_column_id(C_UNIXTIME) # user can click this header and sort
		col.set_resizable(True)
		self.logs_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds message
		col = gtk.TreeViewColumn('Message', renderer_text, text = C_MESSAGE)
		col.set_sort_column_id(C_MESSAGE) # user can click this header and sort
		col.set_resizable(True)
		self.logs_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds subject
		col = gtk.TreeViewColumn('Subject', renderer_text, text = C_SUBJECT)
		col.set_sort_column_id(C_SUBJECT) # user can click this header and sort
		col.set_resizable(True)
		self.logs_listview.append_column(col)

	def _init_search_results_listview(self):
		# log_line_id (HIDDEN), jid, time, message, subject
		self.search_results_liststore = gtk.ListStore(str, str, str, str, str)
		self.search_results_listview.set_model(self.search_results_liststore)
		
		renderer_text = gtk.CellRendererText() # holds JID (who said this)
		col = gtk.TreeViewColumn('JID', renderer_text, text = 1)
		col.set_sort_column_id(1) # user can click this header and sort
		col.set_resizable(True)
		self.search_results_listview.append_column(col)
		
		renderer_text = gtk.CellRendererText() # holds time
		col = gtk.TreeViewColumn('Time', renderer_text, text = C_UNIXTIME)
		col.set_sort_column_id(C_UNIXTIME) # user can click this header and sort
		col.set_resizable(True)
		self.search_results_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds message
		col = gtk.TreeViewColumn('Message', renderer_text, text = C_MESSAGE)
		col.set_sort_column_id(C_MESSAGE) # user can click this header and sort
		col.set_resizable(True)
		self.search_results_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds subject
		col = gtk.TreeViewColumn('Subject', renderer_text, text = C_SUBJECT)
		col.set_sort_column_id(C_SUBJECT) # user can click this header and sort
		col.set_resizable(True)
		self.search_results_listview.append_column(col)
	
	def on_history_manager_window_delete_event(self, widget, event):
		if self.AT_LEAST_ONE_DELETION_DONE:
			dialog = dialogs.YesNoDialog(
				_('Do you want to clean up the database?'),
				_('Normally allocated database size will not be freed, '
					'it will just become reusable. If you really want to reduce '
					'database filesize, click YES, else click NO.'
					'\n\nIn case you click YES, please wait...'))
			if dialog.get_response() == gtk.RESPONSE_YES:
				self.cur.execute('VACUUM')
				self.con.commit()
							
		gtk.main_quit()
	
	def _fill_jids_listview(self):
		self.cur.execute('SELECT jid, jid_id FROM jids')
		rows = self.cur.fetchall() # list of tupples: [(u'aaa@bbb',), (u'cc@dd',)]
		for row in rows:
			self.jids_already_in.append(row[0]) # jid
			self.jids_liststore.append(row) # jid, jid_id
	
	def on_jids_listview_selection_changed(self, widget, data = None):
		liststore, list_of_paths = self.jids_listview.get_selection()\
			.get_selected_rows()
		paths_len = len(list_of_paths)
		if paths_len == 0: # nothing is selected
			return
		elif paths_len == 1:
			do_clear = True
		else:
			do_clear = False
		
		self.welcome_label.hide()
		self.search_results_scrolledwindow.hide()
		self.logs_scrolledwindow.show()

		list_of_rowrefs = []
		for path in list_of_paths: # make them treerowrefs (it's needed)
			 list_of_rowrefs.append(gtk.TreeRowReference(liststore, path))
		
		for rowref in list_of_rowrefs:
			path = rowref.get_path()
			if path is None:
				continue
			jid = liststore[path][0] # jid
			self._fill_logs_listview(jid, do_clear)
	
	def _get_jid_id(self, jid):
		'''jids table has jid and jid_id
		logs table has log_id, jid_id, contact_name, time, kind, show, message
		so to ask logs we need jid_id that matches our jid in jids table
		this method wants jid and returns the jid_id for later sql-ing on logs
		'''
		if jid.find('/') != -1: # if it has a /
			jid_is_from_pm = self._jid_is_from_pm(jid)
			if not jid_is_from_pm: # it's normal jid with resource
				jid = jid.split('/', 1)[0] # remove the resource
		self.cur.execute('SELECT jid_id FROM jids WHERE jid = ?', (jid,))
		jid_id = self.cur.fetchone()[0]
		return jid_id

	def _get_jid_from_jid_id(self, jid_id):
		'''jids table has jid and jid_id
		this method accepts jid_id and returns the jid for later sql-ing on logs
		'''
		self.cur.execute('SELECT jid FROM jids WHERE jid_id = ?', (jid_id,))
		jid = self.cur.fetchone()[0]
		return jid

	def _jid_is_from_pm(self, jid):
		'''if jid is gajim@conf/nkour it's likely a pm one, how we know
		gajim@conf is not a normal guy and nkour is not his resource?
		we ask if gajim@conf is already in jids (with type room jid)
		this fails if user disables logging for room and only enables for
		pm (so higly unlikely) and if we fail we do not go chaos
		(user will see the first pm as if it was message in room's public chat)
		and after that all okay'''
		
		possible_room_jid, possible_nick = jid.split('/', 1)
		
		self.cur.execute('SELECT jid_id FROM jids WHERE jid = ? AND type = ?',
			(possible_room_jid, constants.JID_ROOM_TYPE))
		row = self.cur.fetchone()
		if row is not None:
			return True
		else:
			return False
	
	def _fill_logs_listview(self, jid, do_clear = True):
		'''fill the listview with all messages that user sent to or
		received from JID'''
		if do_clear:
			self.logs_liststore.clear() # clear the store
		# no need to lower jid in this context as jid is already lowered
		# as we use those jids from db
		jid_id = self._get_jid_id(jid)
		self.cur.execute('''
			SELECT log_line_id, jid_id, time, kind, message, subject FROM logs
			WHERE jid_id = ?
			ORDER BY time
			''', (jid_id,))
		
		results = self.cur.fetchall()
		for row in results:
			# FIXME: check kind and set color accordingly
			
			# exposed in UI (TreeViewColumns) are only time, message and subject
			# but store in liststore log_line_id, jid_id, time, message and subject
			time_ = row[2]
			try:
				time_ = time.strftime('%x', time.localtime(float(time_)))
			except ValueError:
				pass
			else:
				self.logs_liststore.append((row[0], row[1], time_, row[4], row[5]))

	def _fill_search_results_listview(self, text):
		'''ask db and fill listview with results that match text'''
		# FIXME: check kind and set color accordingly
		# exposed in UI (TreeViewColumns) are only JID, time, message and subject
		# but store in liststore jid, time, message and subject
		self.search_results_liststore.clear()
		like_sql = '%' + text + '%'
		self.cur.execute('''
			SELECT log_line_id, jid_id, time, kind, message, subject FROM logs
			WHERE message LIKE ? OR subject LIKE ?
			ORDER BY time
			''', (like_sql, like_sql))
		
		results = self.cur.fetchall()
		for row in results:
			# exposed in UI (TreeViewColumns) are only JID, time, message and subject
			# but store in liststore log_line_id, jid_id, time, message and subject
			time_ = row[2]
			try:
				time_ = time.strftime('%x', time.localtime(float(time_)))
			except ValueError:
				pass
			else:
				jid_id = row[1]
				jid = self._get_jid_from_jid_id(jid_id)
				
				self.search_results_liststore.append((row[0], jid, time_,
					row[4], row[5]))

	def on_logs_listview_key_press_event(self, widget, event):
		liststore, list_of_paths = self.logs_listview.get_selection()\
			.get_selected_rows()
		paths_len = len(list_of_paths)
		if paths_len == 0: # nothing is selected
			return
			
		if event.keyval == gtk.keysyms.Delete:
			pri_text = i18n.ngettext(
				'Do you really want to delete the selected message?',
				'Do you really want to delete the selected messages?', paths_len)
			dialog = dialogs.ConfirmationDialog(pri_text,
				_('This is an irreversible operation.'))
			if dialog.get_response() != gtk.RESPONSE_OK:
				return
			
			# delete rows from db that match log_line_id
			list_of_rowrefs = []
			for path in list_of_paths: # make them treerowrefs (it's needed)
				 list_of_rowrefs.append(gtk.TreeRowReference(liststore, path))
			
			for rowref in list_of_rowrefs:
				path = rowref.get_path()
				if path is None:
					continue
				log_line_id = liststore[path][0]
				del liststore[path] # remove from UI
				# remove from db
				self.cur.execute('''
					DELETE FROM logs
					WHERE log_line_id = ?
					''', (log_line_id,))
		
			self.con.commit()
			
			self.AT_LEAST_ONE_DELETION_DONE = True
			
	def on_jids_listview_key_press_event(self, widget, event):
		liststore, list_of_paths = self.jids_listview.get_selection()\
			.get_selected_rows()
		paths_len = len(list_of_paths)
		if paths_len == 0: # nothing is selected
			return
			
		if event.keyval == gtk.keysyms.Delete:
			pri_text = i18n.ngettext(
				'Do you really want to delete logs of the selected contact?',
				'Do you really want to delete logs of the selected contacts?',
				paths_len)
			dialog = dialogs.ConfirmationDialog(pri_text,
				_('This is an irreversible operation.'))
			if dialog.get_response() != gtk.RESPONSE_OK:
				return

			# delete all rows from db that match jid_id
			list_of_rowrefs = []
			for path in list_of_paths: # make them treerowrefs (it's needed)
				 list_of_rowrefs.append(gtk.TreeRowReference(liststore, path))
			
			for rowref in list_of_rowrefs:
				path = rowref.get_path()
				if path is None:
					continue
				jid_id = liststore[path][1]
				del liststore[path] # remove from UI
				# remove from db
				self.cur.execute('''
					DELETE FROM logs
					WHERE jid_id = ?
					''', (jid_id,))
			
				# now delete "jid, jid_id" row from jids table
				self.cur.execute('''
						DELETE FROM jids
						WHERE jid_id = ?
						''', (jid_id,))
		
			self.con.commit()
			
			self.AT_LEAST_ONE_DELETION_DONE = True

	def on_search_db_button_clicked(self, widget):
		text = self.search_entry.get_text()
		if text == '':
			return

		self.welcome_label.hide()
		self.logs_scrolledwindow.hide()
		self.search_results_scrolledwindow.show()
		
		self._fill_search_results_listview(text)

	def on_search_results_listview_row_activated(self, widget, path, column):
		# get log_line_id, jid_id from row we double clicked
		log_line_id = self.search_results_liststore[path][0]
		jid = self.search_results_liststore[path][1]
		# make it string as in gtk liststores I have them all as strings
		# as this is what db returns so I don't have to fight with types
		jid_id = str(self._get_jid_id(jid))
		
		iter_ = self.jids_liststore.get_iter_root()
		while iter_:
			# self.jids_liststore[iter_][1] holds jid_ids
			print `self.jids_liststore[iter_][1]`
			if self.jids_liststore[iter_][1] == jid_id:
				break
			iter_ = self.jids_liststore.iter_next(iter_)
		
		if iter_ is None:
			return

		path = self.jids_liststore.get_path(iter_)
		self.jids_listview.set_cursor(path)
		#FIXME: scroll to log_line_id

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application
	HistoryManager()
	gtk.main()
