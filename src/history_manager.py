## history_manager.py
##
## Contributors for this file:
## - Nikos Kouremenos <kourem@gmail.com>
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
## Copyright (C) 2006 Yann Le Boulanger <asterix@lagaule.org>
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

# log_line_id (HIDDEN), jid_id (HIDDEN), time, message, subject
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
		
		self.xml = gtk.glade.XML('history_manager.glade',
			'history_manager_window', i18n.APP)
		self.window = self.xml.get_widget('history_manager_window')
		self.jids_listview = self.xml.get_widget('jids_listview')
		self.logs_listview = self.xml.get_widget('logs_listview')
		
		self.jids_already_in = [] # holds jids that we already have in DB
		
		self.con = sqlite.connect(LOG_DB_PATH, timeout = 20.0,
			isolation_level = 'IMMEDIATE')
		self.cur = self.con.cursor()

		self._init_jids_listview()
		self._init_logs_listview()
		
		self._fill_jids_listview()
		
		
		#self.jids_listview.get_selection().unselect_all()

		self.window.maximize()
		self.window.show_all()
		
		self.xml.signal_autoconnect(self)
	
	def _init_jids_listview(self):
		self.jids_liststore = gtk.ListStore(str) # jid
		self.jids_listview.set_model(self.jids_liststore)
		
		renderer_text = gtk.CellRendererText() # holds jid
		col = gtk.TreeViewColumn('Contacts', renderer_text, text = 0)
		self.jids_listview.append_column(col)
		
	def _init_logs_listview(self):
		# log_line_id (HIDDEN), jid_id (HIDDEN), time, message, subject
		self.logs_liststore = gtk.ListStore(str, str, str, str, str)
		self.logs_listview.set_model(self.logs_liststore)
		
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
	
	def on_history_manager_window_delete_event(self, widget, event):
		gtk.main_quit()
	
	def _fill_jids_listview(self):
		self.cur.execute('SELECT jid FROM jids')
		rows = self.cur.fetchall() # list of tupples: [(u'aaa@bbb',), (u'cc@dd',)]
		for row in rows:
			# row[0] is first item of row (the only result here, the jid)
			self.jids_already_in.append(row[0])
			self.jids_liststore.append(row)
	
	def on_jids_listview_cursor_changed(self, widget, data = None):
		model, iter_ = self.jids_listview.get_selection().get_selected()
		jid = model[iter_][0] # jid
		self._fill_logs_listview(jid)
	
	def _get_jid_id(self, jid):
		'''jids table has jid and jid_id
		logs table has log_id, jid_id, contact_name, time, kind, show, message
		so to ask logs we need jid_id that matches our jid in jids table
		this method asks jid and returns the jid_id for later sql-ing on logs
		'''
		if jid.find('/') != -1: # if it has a /
			jid_is_from_pm = self._jid_is_from_pm(jid)
			if not jid_is_from_pm: # it's normal jid with resource
				jid = jid.split('/', 1)[0] # remove the resource
		self.cur.execute('SELECT jid_id FROM jids WHERE jid="%s"' % jid)
		jid_id = self.cur.fetchone()[0]
		return jid_id

	def _jid_is_from_pm(self, jid):
		'''if jid is gajim@conf/nkour it's likely a pm one, how we know
		gajim@conf is not a normal guy and nkour is not his resource?
		we ask if gajim@conf is already in jids (with type room jid)
		this fails if user disables logging for room and only enables for
		pm (so higly unlikely) and if we fail we do not go chaos
		(user will see the first pm as if it was message in room's public chat)
		and after that all okay'''
		
		possible_room_jid, possible_nick = jid.split('/', 1)
		
		self.cur.execute('SELECT jid_id FROM jids WHERE jid="%s" AND type=%d' %\
			(possible_room_jid, constants.JID_ROOM_TYPE))
		row = self.cur.fetchone()
		if row is not None:
			return True
		else:
			return False
	
	def _fill_logs_listview(self, jid):
		'''fill the listview with all messages that user sent to or
		received from JID'''
		# no need to lower jid in this context as jid is already lowered
		# as we use those jids from db
		jid_id = self._get_jid_id(jid)
		self.cur.execute('''
			SELECT log_line_id, jid_id, time, kind, message, subject FROM logs
			WHERE jid_id = %d
			ORDER BY time
			''' % (jid_id,))
		
		results = self.cur.fetchall()
		for row in results:
			# FIXME: check kind and set color accordingly
			
			# exposed in UI (TreeViewColumns) are only time, message and subject
			# but store in liststore log_line_id, jid_id, time, message and subject
			time_ = row[2]
			time_ = time.strftime('%x', time.localtime(float(time_)))
			self.logs_liststore.append((row[0], row[1], time_, row[4], row[5]))

if __name__ == '__main__':
	signal.signal(signal.SIGINT, signal.SIG_DFL) # ^C exits the application
	HistoryManager()
	gtk.main()
