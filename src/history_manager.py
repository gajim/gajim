# -*- coding:utf-8 -*-
## src/history_manager.py
##
## Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2006-2007 Jean-Marie Traissard <jim AT lapin.org>
##                         Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006-2008 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2007 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
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

## NOTE: some method names may match those of logger.py but that's it
## someday (TM) should have common class that abstracts db connections and helpers on it
## the same can be said for history_window.py

import os

if os.name == 'nt':
	import warnings
	warnings.filterwarnings(action='ignore')

	if os.path.isdir('gtk'):
		# Used to create windows installer with GTK included
		paths = os.environ['PATH']
		list_ = paths.split(';')
		new_list = []
		for p in list_:
			if p.find('gtk') < 0 and p.find('GTK') < 0:
				new_list.append(p)
		new_list.insert(0, 'gtk/lib')
		new_list.insert(0, 'gtk/bin')
		os.environ['PATH'] = ';'.join(new_list)
		os.environ['GTK_BASEPATH'] = 'gtk'

import sys
import signal
import gtk
import gobject
import time
import locale

import getopt
from common import i18n

def parseOpts():
   config_path = None

   try:
      shortargs = 'hc:'
      longargs = 'help config_path='
      opts = getopt.getopt(sys.argv[1:], shortargs, longargs.split())[0]
   except getopt.error, msg:
      print str(msg)
      print 'for help use --help'
      sys.exit(2)
   for o, a in opts:
      if o in ('-h', '--help'):
         print 'history_manager [--help] [--config-path]'
         sys.exit()
      elif o in ('-c', '--config-path'):
         config_path = a
   return config_path

config_path = parseOpts()
del parseOpts

import common.configpaths
common.configpaths.gajimpaths.init(config_path)
del config_path
common.configpaths.gajimpaths.init_profile()
from common import exceptions
import dialogs
import gtkgui_helpers
from common.logger import LOG_DB_PATH, constants

#FIXME: constants should implement 2 way mappings
status = dict((constants.__dict__[i], i[5:].lower()) for i in \
	constants.__dict__.keys() if i.startswith('SHOW_'))
from common import gajim
from common import helpers

# time, message, subject
(
C_UNIXTIME,
C_MESSAGE,
C_SUBJECT,
C_NICKNAME
) = range(2, 6)


try:
	import sqlite3 as sqlite # python 2.5
except ImportError:
	try:
		from pysqlite2 import dbapi2 as sqlite
	except ImportError:
		raise exceptions.PysqliteNotAvailable


class HistoryManager:
	def __init__(self):
		path_to_file = os.path.join(gajim.DATA_DIR, 'pixmaps/gajim.png')
		pix = gtk.gdk.pixbuf_new_from_file(path_to_file)
		gtk.window_set_default_icon(pix) # set the icon to all newly opened windows

		if not os.path.exists(LOG_DB_PATH):
			dialogs.ErrorDialog(_('Cannot find history logs database'),
				'%s does not exist.' % LOG_DB_PATH)
			sys.exit()

		xml = gtkgui_helpers.get_glade('history_manager.glade')
		self.window = xml.get_widget('history_manager_window')
		self.jids_listview = xml.get_widget('jids_listview')
		self.logs_listview = xml.get_widget('logs_listview')
		self.search_results_listview = xml.get_widget('search_results_listview')
		self.search_entry = xml.get_widget('search_entry')
		self.logs_scrolledwindow = xml.get_widget('logs_scrolledwindow')
		self.search_results_scrolledwindow = xml.get_widget(
			'search_results_scrolledwindow')
		self.welcome_vbox = xml.get_widget('welcome_vbox')

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

		self.window.show_all()

		xml.signal_autoconnect(self)

	def _init_jids_listview(self):
		self.jids_liststore = gtk.ListStore(str, str) # jid, jid_id
		self.jids_listview.set_model(self.jids_liststore)
		self.jids_listview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

		renderer_text = gtk.CellRendererText() # holds jid
		col = gtk.TreeViewColumn(_('Contacts'), renderer_text, text = 0)
		self.jids_listview.append_column(col)

		self.jids_listview.get_selection().connect('changed',
			self.on_jids_listview_selection_changed)

	def _init_logs_listview(self):
		# log_line_id (HIDDEN), jid_id (HIDDEN), time, message, subject, nickname
		self.logs_liststore = gtk.ListStore(str, str, str, str, str, str)
		self.logs_listview.set_model(self.logs_liststore)
		self.logs_listview.get_selection().set_mode(gtk.SELECTION_MULTIPLE)

		renderer_text = gtk.CellRendererText() # holds time
		col = gtk.TreeViewColumn(_('Date'), renderer_text, text = C_UNIXTIME)
		col.set_sort_column_id(C_UNIXTIME) # user can click this header and sort
		col.set_resizable(True)
		self.logs_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds nickname
		col = gtk.TreeViewColumn(_('Nickname'), renderer_text, text = C_NICKNAME)
		col.set_sort_column_id(C_NICKNAME) # user can click this header and sort
		col.set_resizable(True)
		col.set_visible(False)
		self.nickname_col_for_logs = col
		self.logs_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds message
		col = gtk.TreeViewColumn(_('Message'), renderer_text, markup = C_MESSAGE)
		col.set_sort_column_id(C_MESSAGE) # user can click this header and sort
		col.set_resizable(True)
		self.message_col_for_logs = col
		self.logs_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds subject
		col = gtk.TreeViewColumn(_('Subject'), renderer_text, text = C_SUBJECT)
		col.set_sort_column_id(C_SUBJECT) # user can click this header and sort
		col.set_resizable(True)
		col.set_visible(False)
		self.subject_col_for_logs = col
		self.logs_listview.append_column(col)

	def _init_search_results_listview(self):
		# log_line_id (HIDDEN), jid, time, message, subject, nickname
		self.search_results_liststore = gtk.ListStore(str, str, str, str, str, str)
		self.search_results_listview.set_model(self.search_results_liststore)

		renderer_text = gtk.CellRendererText() # holds JID (who said this)
		col = gtk.TreeViewColumn(_('JID'), renderer_text, text = 1)
		col.set_sort_column_id(1) # user can click this header and sort
		col.set_resizable(True)
		self.search_results_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds time
		col = gtk.TreeViewColumn(_('Date'), renderer_text, text = C_UNIXTIME)
		col.set_sort_column_id(C_UNIXTIME) # user can click this header and sort
		col.set_resizable(True)
		self.search_results_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds message
		col = gtk.TreeViewColumn(_('Message'), renderer_text, text = C_MESSAGE)
		col.set_sort_column_id(C_MESSAGE) # user can click this header and sort
		col.set_resizable(True)
		self.search_results_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds subject
		col = gtk.TreeViewColumn(_('Subject'), renderer_text, text = C_SUBJECT)
		col.set_sort_column_id(C_SUBJECT) # user can click this header and sort
		col.set_resizable(True)
		self.search_results_listview.append_column(col)

		renderer_text = gtk.CellRendererText() # holds nickname
		col = gtk.TreeViewColumn(_('Nickname'), renderer_text, text = C_NICKNAME)
		col.set_sort_column_id(C_NICKNAME) # user can click this header and sort
		col.set_resizable(True)
		self.search_results_listview.append_column(col)

	def on_history_manager_window_delete_event(self, widget, event):
		if self.AT_LEAST_ONE_DELETION_DONE:
			def on_yes(clicked):
				self.cur.execute('VACUUM')
				self.con.commit()
				gtk.main_quit()

			def on_no():
				gtk.main_quit()

			dialogs.YesNoDialog(
				_('Do you want to clean up the database? '
				'(STRONGLY NOT RECOMMENDED IF GAJIM IS RUNNING)'),
				_('Normally allocated database size will not be freed, '
					'it will just become reusable. If you really want to reduce '
					'database filesize, click YES, else click NO.'
					'\n\nIn case you click YES, please wait...'),
				on_response_yes=on_yes, on_response_no=on_no)
			return

		gtk.main_quit()

	def _fill_jids_listview(self):
		# get those jids that have at least one entry in logs
		self.cur.execute('SELECT jid, jid_id FROM jids WHERE jid_id IN (SELECT '
			'distinct logs.jid_id FROM logs) ORDER BY jid')
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

		self.logs_liststore.clear() # clear the store

		self.welcome_vbox.hide()
		self.search_results_scrolledwindow.hide()
		self.logs_scrolledwindow.show()

		list_of_rowrefs = []
		for path in list_of_paths: # make them treerowrefs (it's needed)
			list_of_rowrefs.append(gtk.TreeRowReference(liststore, path))

		for rowref in list_of_rowrefs: # FILL THE STORE, for all rows selected
			path = rowref.get_path()
			if path is None:
				continue
			jid = liststore[path][0] # jid
			self._fill_logs_listview(jid)

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
		return str(jid_id)

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

		possible_room_jid = jid.split('/', 1)[0]

		self.cur.execute('SELECT jid_id FROM jids WHERE jid = ? AND type = ?',
			(possible_room_jid, constants.JID_ROOM_TYPE))
		row = self.cur.fetchone()
		if row is None:
			return False
		else:
			return True

	def _jid_is_room_type(self, jid):
		'''returns True/False if given id is room type or not
		eg. if it is room'''
		self.cur.execute('SELECT type FROM jids WHERE jid = ?', (jid,))
		row = self.cur.fetchone()
		if row is None:
			raise
		elif row[0] == constants.JID_ROOM_TYPE:
			return True
		else: # normal type
			return False

	def _fill_logs_listview(self, jid):
		'''fill the listview with all messages that user sent to or
		received from JID'''
		# no need to lower jid in this context as jid is already lowered
		# as we use those jids from db
		jid_id = self._get_jid_id(jid)
		self.cur.execute('''
			SELECT log_line_id, jid_id, time, kind, message, subject, contact_name, show
			FROM logs
			WHERE jid_id = ?
			ORDER BY time
			''', (jid_id,))

		results = self.cur.fetchall()

		if self._jid_is_room_type(jid): # is it room?
			self.nickname_col_for_logs.set_visible(True)
			self.subject_col_for_logs.set_visible(False)
		else:
			self.nickname_col_for_logs.set_visible(False)
			self.subject_col_for_logs.set_visible(True)

		for row in results:
			# exposed in UI (TreeViewColumns) are only
			# time, message, subject, nickname
			# but store in liststore
			# log_line_id, jid_id, time, message, subject, nickname
			log_line_id, jid_id, time_, kind, message, subject, nickname, show = row
			try:
				time_ = time.strftime('%x', time.localtime(float(time_))).decode(
					locale.getpreferredencoding())
			except ValueError:
				pass
			else:
				color = None
				if kind in (constants.KIND_SINGLE_MSG_RECV,
				constants.KIND_CHAT_MSG_RECV, constants.KIND_GC_MSG):
					# it is the other side
					color = gajim.config.get('inmsgcolor') # so incoming color
				elif kind in (constants.KIND_SINGLE_MSG_SENT,
				constants.KIND_CHAT_MSG_SENT): # it is us
					color = gajim.config.get('outmsgcolor') # so outgoing color
				elif kind in (constants.KIND_STATUS,
				constants.KIND_GCSTATUS): # is is statuses
					color = gajim.config.get('statusmsgcolor') # so status color
					# include status into (status) message
					if message is None:
						message = ''
					else:
						message = ' : ' + message
					message = helpers.get_uf_show(gajim.SHOW_LIST[show]) + message

				message_ = '<span'
				if color:
					message_ += ' foreground="%s"' % color
				message_ += '>%s</span>' % \
					gobject.markup_escape_text(message)
				self.logs_liststore.append((log_line_id, jid_id, time_, message_,
					subject, nickname))

	def _fill_search_results_listview(self, text):
		'''ask db and fill listview with results that match text'''
		self.search_results_liststore.clear()
		like_sql = '%' + text + '%'
		self.cur.execute('''
			SELECT log_line_id, jid_id, time, message, subject, contact_name
			FROM logs
			WHERE message LIKE ? OR subject LIKE ?
			ORDER BY time
			''', (like_sql, like_sql))

		results = self.cur.fetchall()
		for row in results:
			# exposed in UI (TreeViewColumns) are only
			# JID, time, message, subject, nickname
			# but store in liststore
			# log_line_id, jid (from jid_id), time, message, subject, nickname
			log_line_id, jid_id, time_, message, subject, nickname = row
			try:
				time_ = time.strftime('%x', time.localtime(float(time_))).decode(
					locale.getpreferredencoding())
			except ValueError:
				pass
			else:
				jid = self._get_jid_from_jid_id(jid_id)

				self.search_results_liststore.append((log_line_id, jid, time_,
					message, subject, nickname))

	def on_logs_listview_key_press_event(self, widget, event):
		liststore, list_of_paths = self.logs_listview.get_selection()\
			.get_selected_rows()
		if event.keyval == gtk.keysyms.Delete:
			self._delete_logs(liststore, list_of_paths)

	def on_listview_button_press_event(self, widget, event):
		if event.button == 3: # right click
			xml = gtkgui_helpers.get_glade('history_manager.glade', 'context_menu')
			if widget.name != 'jids_listview':
				xml.get_widget('export_menuitem').hide()
			xml.get_widget('delete_menuitem').connect('activate',
				self.on_delete_menuitem_activate, widget)

			xml.signal_autoconnect(self)
			xml.get_widget('context_menu').popup(None, None, None,
				event.button, event.time)
			return True

	def on_export_menuitem_activate(self, widget):
		xml = gtkgui_helpers.get_glade('history_manager.glade', 'filechooserdialog')
		xml.signal_autoconnect(self)

		dlg = xml.get_widget('filechooserdialog')
		dlg.set_title(_('Exporting History Logs...'))
		dlg.set_current_folder(gajim.HOME_DIR)
		dlg.props.do_overwrite_confirmation = True
		response = dlg.run()

		if response == gtk.RESPONSE_OK: # user want us to export ;)
			liststore, list_of_paths = self.jids_listview.get_selection()\
				.get_selected_rows()
			path_to_file = dlg.get_filename()
			self._export_jids_logs_to_file(liststore, list_of_paths, path_to_file)

		dlg.destroy()

	def on_delete_menuitem_activate(self, widget, listview):
		liststore, list_of_paths = listview.get_selection().get_selected_rows()
		if listview.name == 'jids_listview':
			self._delete_jid_logs(liststore, list_of_paths)
		elif listview.name in ('logs_listview', 'search_results_listview'):
			self._delete_logs(liststore, list_of_paths)
		else: # Huh ? We don't know this widget
			return

	def on_jids_listview_key_press_event(self, widget, event):
		liststore, list_of_paths = self.jids_listview.get_selection()\
			.get_selected_rows()
		if event.keyval == gtk.keysyms.Delete:
			self._delete_jid_logs(liststore, list_of_paths)

	def _export_jids_logs_to_file(self, liststore, list_of_paths, path_to_file):
		paths_len = len(list_of_paths)
		if paths_len == 0: # nothing is selected
			return

		list_of_rowrefs = []
		for path in list_of_paths: # make them treerowrefs (it's needed)
			list_of_rowrefs.append(gtk.TreeRowReference(liststore, path))

		for rowref in list_of_rowrefs:
			path = rowref.get_path()
			if path is None:
				continue
			jid_id = liststore[path][1]
			self.cur.execute('''
				SELECT time, kind, message, contact_name FROM logs
				WHERE jid_id = ?
				ORDER BY time
				''', (jid_id,))

		# FIXME: we may have two contacts selected to export. fix that
		# AT THIS TIME FIRST EXECUTE IS LOST! WTH!!!!!
		results = self.cur.fetchall()
		#print results[0]
		file_ = open(path_to_file, 'w')
		for row in results:
			# in store: time, kind, message, contact_name FROM logs
			# in text: JID or You or nickname (if it's gc_msg), time, message
			time_, kind, message, nickname = row
			if kind in (constants.KIND_SINGLE_MSG_RECV,
				constants.KIND_CHAT_MSG_RECV):
				who = self._get_jid_from_jid_id(jid_id)
			elif kind in (constants.KIND_SINGLE_MSG_SENT,
				constants.KIND_CHAT_MSG_SENT):
				who = _('You')
			elif kind == constants.KIND_GC_MSG:
				who = nickname
			else: # status or gc_status. do not save
				#print kind
				continue

			try:
				time_ = time.strftime('%x', time.localtime(float(time_))).decode(
					locale.getpreferredencoding())
			except ValueError:
				pass

			file_.write(_('%(who)s on %(time)s said: %(message)s\n') % {'who': who,
				'time': time_, 'message': message})

	def _delete_jid_logs(self, liststore, list_of_paths):
		paths_len = len(list_of_paths)
		if paths_len == 0: # nothing is selected
			return

		def on_ok(liststore, list_of_paths):
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

		pri_text = i18n.ngettext(
			'Do you really want to delete logs of the selected contact?',
			'Do you really want to delete logs of the selected contacts?',
			paths_len)
		dialogs.ConfirmationDialog(pri_text,
			_('This is an irreversible operation.'), on_response_ok = (on_ok,
			liststore, list_of_paths))

	def _delete_logs(self, liststore, list_of_paths):
		paths_len = len(list_of_paths)
		if paths_len == 0: # nothing is selected
			return

		def on_ok(liststore, list_of_paths):
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


		pri_text = i18n.ngettext(
			'Do you really want to delete the selected message?',
			'Do you really want to delete the selected messages?', paths_len)
		dialogs.ConfirmationDialog(pri_text,
			_('This is an irreversible operation.'), on_response_ok = (on_ok,
			liststore, list_of_paths))

	def on_search_db_button_clicked(self, widget):
		text = self.search_entry.get_text()
		if text == '':
			return

		self.welcome_vbox.hide()
		self.logs_scrolledwindow.hide()
		self.search_results_scrolledwindow.show()

		self._fill_search_results_listview(text)

	def on_search_results_listview_row_activated(self, widget, path, column):
		# get log_line_id, jid_id from row we double clicked
		log_line_id = self.search_results_liststore[path][0]
		jid = self.search_results_liststore[path][1]
		# make it string as in gtk liststores I have them all as strings
		# as this is what db returns so I don't have to fight with types
		jid_id = self._get_jid_id(jid)


		iter_ = self.jids_liststore.get_iter_root()
		while iter_:
			# self.jids_liststore[iter_][1] holds jid_ids
			if self.jids_liststore[iter_][1] == jid_id:
				break
			iter_ = self.jids_liststore.iter_next(iter_)

		if iter_ is None:
			return

		path = self.jids_liststore.get_path(iter_)
		self.jids_listview.set_cursor(path)

		iter_ = self.logs_liststore.get_iter_root()
		while iter_:
			# self.logs_liststore[iter_][0] holds lon_line_ids
			if self.logs_liststore[iter_][0] == log_line_id:
				break
			iter_ = self.logs_liststore.iter_next(iter_)

		path = self.logs_liststore.get_path(iter_)
		self.logs_listview.scroll_to_cell(path)

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application
	HistoryManager()
	gtk.main()

# vim: se ts=3:
