# -*- coding:utf-8 -*-
## src/history_window.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
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

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib
import time
import calendar
import datetime

from enum import IntEnum, unique

from gajim import gtkgui_helpers
from gajim import conversation_textview
from gajim import dialogs

from gajim.common import app
from gajim.common import helpers
from gajim.common import exceptions

from gajim.common.logger import ShowConstant, KindConstant

@unique
class InfoColumn(IntEnum):
    '''Completion dict'''
    JID = 0
    ACCOUNT = 1
    NAME = 2
    COMPLETION = 3

@unique
class Column(IntEnum):
    LOG_JID = 0
    CONTACT_NAME = 1
    UNIXTIME = 2
    MESSAGE = 3
    TIME = 4
    LOG_LINE_ID = 5

class HistoryWindow:
    """
    Class for browsing logs of conversations with contacts
    """

    def __init__(self, jid=None, account=None):
        xml = gtkgui_helpers.get_gtk_builder('history_window.ui')
        self.window = xml.get_object('history_window')
        self.window.set_application(app.app)
        self.calendar = xml.get_object('calendar')
        scrolledwindow = xml.get_object('scrolledwindow')
        self.history_textview = conversation_textview.ConversationTextview(
            account, used_in_history_window = True)
        scrolledwindow.add(self.history_textview.tv)
        self.history_buffer = self.history_textview.tv.get_buffer()
        self.history_buffer.create_tag('highlight', background='yellow')
        self.history_buffer.create_tag('invisible', invisible=True)
        self.checkbutton = xml.get_object('log_history_checkbutton')
        self.checkbutton.connect('toggled',
            self.on_log_history_checkbutton_toggled)
        self.show_status_checkbutton = xml.get_object('show_status_checkbutton')
        self.search_entry = xml.get_object('search_entry')
        self.query_liststore = xml.get_object('query_liststore')
        self.jid_entry = xml.get_object('query_entry')
        self.jid_entry.connect('activate', self.on_jid_entry_activate)
        self.results_treeview = xml.get_object('results_treeview')
        self.results_window = xml.get_object('results_scrolledwindow')
        self.search_in_date = xml.get_object('search_in_date')

        # jid, contact_name, date, message, time, log_line_id
        model = Gtk.ListStore(str, str, str, str, str, int)
        self.results_treeview.set_model(model)
        col = Gtk.TreeViewColumn(_('Name'))
        self.results_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', Column.CONTACT_NAME)
        col.set_sort_column_id(Column.CONTACT_NAME) # user can click this header and sort
        col.set_resizable(True)

        col = Gtk.TreeViewColumn(_('Date'))
        self.results_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', Column.UNIXTIME)
        col.set_sort_column_id(Column.UNIXTIME) # user can click this header and sort
        col.set_resizable(True)

        col = Gtk.TreeViewColumn(_('Message'))
        self.results_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', Column.MESSAGE)
        col.set_resizable(True)

        self.jid = None # The history we are currently viewing
        self.account = account
        self.completion_dict = {}
        self.accounts_seen_online = [] # Update dict when new accounts connect
        self.jids_to_search = []

        # This will load history too
        task = self._fill_completion_dict()
        GLib.idle_add(next, task)

        if jid:
            self.jid_entry.set_text(jid)
        else:
            self._load_history(None)

        gtkgui_helpers.resize_window(self.window,
                app.config.get('history_window_width'),
                app.config.get('history_window_height'))
        gtkgui_helpers.move_window(self.window,
                app.config.get('history_window_x-position'),
                app.config.get('history_window_y-position'))

        xml.connect_signals(self)
        self.window.show_all()

        # PluginSystem: adding GUI extension point for
        # HistoryWindow instance object
        app.plugin_manager.gui_extension_point(
            'history_window', self)

    def _fill_completion_dict(self):
        """
        Fill completion_dict for key auto completion. Then load history for
        current jid (by calling another function)

        Key will be either jid or full_completion_name (contact name or long
        description like "pm-contact from groupchat....").

        {key : (jid, account, nick_name, full_completion_name}
        This is a generator and does pseudo-threading via idle_add().
        """
        liststore = gtkgui_helpers.get_completion_liststore(self.jid_entry)

        # Add all jids in logs.db:
        db_jids = app.logger.get_jids_in_db()
        completion_dict = dict.fromkeys(db_jids)

        self.accounts_seen_online = list(app.contacts.get_accounts())

        # Enhance contacts of online accounts with contact. Needed for mapping below
        for account in self.accounts_seen_online:
            completion_dict.update(helpers.get_contact_dict_for_account(account))

        muc_active_icon = gtkgui_helpers.get_iconset_name_for('muc-active')
        online_icon = gtkgui_helpers.get_iconset_name_for('online')

        keys = list(completion_dict.keys())
        # Move the actual jid at first so we load history faster
        actual_jid = self.jid_entry.get_text()
        if actual_jid in keys:
            keys.remove(actual_jid)
            keys.insert(0, actual_jid)
        if '' in keys:
            keys.remove('')
        if None in keys:
            keys.remove(None)
        # Map jid to info tuple
        # Warning : This for is time critical with big DB
        for key in keys:
            completed = key
            completed2 = None
            contact = completion_dict[completed]
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

            if app.logger.jid_is_room_jid(completed) or\
            app.logger.jid_is_from_pm(completed):
                icon = muc_active_icon
                if app.logger.jid_is_from_pm(completed):
                    # It's PM. Make it easier to find
                    room, nick = app.get_room_and_nick_from_fjid(completed)
                    info_completion = '%s from %s' % (nick, room)
                    completed = info_completion
                    info_completion2 = '%s/%s' % (room, nick)
                    completed2 = info_completion2
                    info_name = nick
            else:
                icon = online_icon

            if len(completed) > 70:
                completed = completed[:70] + '[\u2026]'
            liststore.append((icon, completed))
            self.completion_dict[key] = (info_jid, info_acc, info_name,
                info_completion)
            self.completion_dict[completed] = (info_jid, info_acc,
                info_name, info_completion)
            if completed2:
                if len(completed2) > 70:
                    completed2 = completed2[:70] + '[\u2026]'
                liststore.append((icon, completed2))
                self.completion_dict[completed2] = (info_jid, info_acc,
                    info_name, info_completion2)
            if key == actual_jid:
                self._load_history(info_jid, self.account or info_acc)
            yield True
        keys.sort()
        yield False

    def _get_account_for_jid(self, jid):
        """
        Return the corresponding account of the jid. May be None if an account
        could not be found
        """
        accounts = app.contacts.get_accounts()
        account = None
        for acc in accounts:
            jid_list = app.contacts.get_jid_list(acc)
            gc_list = app.contacts.get_gc_list(acc)
            if jid in jid_list or jid in gc_list:
                account = acc
                break
        return account

    def on_history_window_destroy(self, widget):
        # PluginSystem: removing GUI extension points connected with
        # HistoryWindow instance object
        app.plugin_manager.remove_gui_extension_point(
            'history_window', self)
        self.history_textview.del_handlers()
        del app.interface.instances['logs']

    def on_history_window_key_press_event(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.save_state()
            self.window.destroy()

    def on_close_button_clicked(self, widget):
        self.save_state()
        self.window.destroy()

    def on_jid_entry_activate(self, widget):
        jid = self.jid_entry.get_text()
        self._load_history(jid, self.account)
        self.results_window.set_property('visible', False)

    def on_jid_entry_focus(self, widget, event):
        widget.select_region(0, -1) # select text

    def _load_history(self, jid_or_name, account=None):
        """
        Load history for the given jid/name and show it
        """
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
                if self.account in app.config.get_per('accounts', self.account,
                        'no_log_for').split(' '):
                    self.checkbutton.set_active(False)
                    self.checkbutton.set_sensitive(False)
                else:
                    # Are log disabled for jid ?
                    log = True
                    if self.jid in app.config.get_per('accounts', self.account,
                            'no_log_for').split(' '):
                        log = False
                    self.checkbutton.set_active(log)
                    self.checkbutton.set_sensitive(True)

            self.jids_to_search = [info_jid]

            # select logs for last date we have logs with contact
            self.calendar.set_sensitive(True)
            last_log = \
                    app.logger.get_last_date_that_has_logs(self.account, self.jid)

            date = time.localtime(last_log)

            y, m, d = date[0], date[1], date[2]
            gtk_month = gtkgui_helpers.make_python_month_gtk_month(m)
            self.calendar.select_month(gtk_month, y)
            self.calendar.select_day(d)

            self.search_entry.set_sensitive(True)
            self.search_entry.grab_focus()

            title = _('Conversation History with %s') % info_name
            self.window.set_title(title)
            self.jid_entry.set_text(info_completion)

        else:   # neither a valid jid, nor an existing contact name was entered
            # we have got nothing to show or to search in
            self.jid = None
            self.account = None

            self.history_buffer.set_text('') # clear the buffer
            self.search_entry.set_sensitive(False)

            self.checkbutton.set_sensitive(False)
            self.calendar.set_sensitive(False)
            self.calendar.clear_marks()

            self.results_window.set_property('visible', False)

            title = _('Conversation History')
            self.window.set_title(title)

    def on_calendar_day_selected(self, widget):
        if not self.jid:
            return
        year, month, day = self.calendar.get_date() # integers
        month = gtkgui_helpers.make_gtk_month_python_month(month)
        self._load_conversation(year, month, day)

    def on_calendar_month_changed(self, widget):
        """
        Ask for days in this month, if they have logs it bolds them (marks them)
        """
        if not self.jid:
            return
        year, month, day = widget.get_date() # integers
        if year < 1900:
            widget.select_month(0, 1900)
            widget.select_day(1)
            return

        widget.clear_marks()
        month = gtkgui_helpers.make_gtk_month_python_month(month)

        try:
            log_days = app.logger.get_days_with_logs(
                self.account, self.jid, year, month)
        except exceptions.PysqliteOperationalError as e:
            dialogs.ErrorDialog(_('Disk Error'), str(e))
            return

        for date in log_days:
            widget.mark_day(date.day)

    def _get_string_show_from_constant_int(self, show):
        if show == ShowConstant.ONLINE:
            show = 'online'
        elif show == ShowConstant.CHAT:
            show = 'chat'
        elif show == ShowConstant.AWAY:
            show = 'away'
        elif show == ShowConstant.XA:
            show = 'xa'
        elif show == ShowConstant.DND:
            show = 'dnd'
        elif show == ShowConstant.OFFLINE:
            show = 'offline'

        return show

    def _load_conversation(self, year, month, day):
        """
        Load the conversation between `self.jid` and `self.account` held on the
        given date into the history textbuffer. Values for `month` and `day`
        are 1-based.
        """
        self.history_buffer.set_text('')
        self.last_time_printout = 0
        show_status = self.show_status_checkbutton.get_active()

        date = datetime.datetime(year, month, day)

        conversation = app.logger.get_conversation_for_date(
            self.account, self.jid, date)

        for message in conversation:
            if not show_status and message.kind in (KindConstant.GCSTATUS,
                                                    KindConstant.STATUS):
                continue
            self._add_message(message)

    def _add_message(self, msg):
        if not msg.message and msg.kind not in (KindConstant.STATUS,
                                                KindConstant.GCSTATUS):
            return

        tim = msg.time
        kind = msg.kind
        show = msg.show
        message = msg.message
        subject = msg.subject
        log_line_id = msg.log_line_id
        contact_name = msg.contact_name
        additional_data = msg.additional_data

        buf = self.history_buffer
        end_iter = buf.get_end_iter()

        # Make the beginning of every message searchable by its log_line_id
        buf.create_mark(str(log_line_id), end_iter, left_gravity=True)

        if app.config.get('print_time') == 'always':
            timestamp_str = app.config.get('time_stamp')
            timestamp_str = helpers.from_one_line(timestamp_str)
            tim = time.strftime(timestamp_str, time.localtime(float(tim)))
            buf.insert(end_iter, tim)
        elif app.config.get('print_time') == 'sometimes':
            every_foo_seconds = 60 * app.config.get(
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

        if kind == KindConstant.GC_MSG:
            tag_name = 'incoming'
        elif kind in (KindConstant.SINGLE_MSG_RECV, KindConstant.CHAT_MSG_RECV):
            contact_name = self.completion_dict[self.jid][InfoColumn.NAME]
            tag_name = 'incoming'
            tag_msg = 'incomingtxt'
        elif kind in (KindConstant.SINGLE_MSG_SENT, KindConstant.CHAT_MSG_SENT):
            if self.account:
                contact_name = app.nicks[self.account]
            else:
                # we don't have roster, we don't know our own nick, use first
                # account one (urk!)
                account = list(app.contacts.get_accounts())[0]
                contact_name = app.nicks[account]
            tag_name = 'outgoing'
            tag_msg = 'outgoingtxt'
        elif kind == KindConstant.GCSTATUS:
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
            if show is None: # it means error
                if message:
                    message = _('Error: %s') % message
                else:
                    message = _('Error')
            elif message:
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
            if contact_name and kind != KindConstant.GCSTATUS:
                # add stuff before and after contact name
                before_str = app.config.get('before_nickname')
                before_str = helpers.from_one_line(before_str)
                after_str = app.config.get('after_nickname')
                after_str = helpers.from_one_line(after_str)
                format = before_str + contact_name + after_str + ' '
                if tag_name:
                    buf.insert_with_tags_by_name(end_iter, format, tag_name)
                else:
                    buf.insert(end_iter, format)
        if subject:
            message = _('Subject: %s\n') % subject + message
        xhtml = None
        if message.startswith('<body '):
            xhtml = message

        if tag_msg:
            self.history_textview.print_real_text(message, [tag_msg],
                    name=contact_name, xhtml=xhtml, additional_data=additional_data)
        else:
            self.history_textview.print_real_text(message, name=contact_name,
                xhtml=xhtml, additional_data=additional_data)
        self.history_textview.print_real_text('\n', text_tags=['eol'])

    def on_search_entry_activate(self, widget):
        text = self.search_entry.get_text()
        model = self.results_treeview.get_model()
        model.clear()
        if text == '':
            self.results_window.set_property('visible', False)
            return
        else:
            self.results_window.set_property('visible', True)

        # perform search in preselected jids
        # jids are preselected with the query_entry
        for jid in self.jids_to_search:
            account = self.completion_dict[jid][InfoColumn.ACCOUNT]
            if account is None:
                # We do not know an account. This can only happen if the contact is offine,
                # or if we browse a groupchat history. The account is not needed, a dummy can
                # be set.
                # This may leed to wrong self nick in the displayed history (Uggh!)
                account = list(app.contacts.get_accounts())[0]

            date = None
            if self.search_in_date.get_active():
                year, month, day = self.calendar.get_date() # integers
                month = gtkgui_helpers.make_gtk_month_python_month(month)
                date = datetime.datetime(year, month, day)

            show_status = self.show_status_checkbutton.get_active()

            results = app.logger.search_log(account, jid, text, date)
            #FIXME:
            # add "subject:  | message: " in message column if kind is single
            # also do we need show at all? (we do not search on subject)
            for row in results:
                if not show_status and row.kind in (KindConstant.GCSTATUS,
                                                    KindConstant.STATUS):
                    continue

                contact_name = row.contact_name
                if not contact_name:
                    if row.kind == KindConstant.CHAT_MSG_SENT: # it's us! :)
                        contact_name = app.nicks[account]
                    else:
                        contact_name = self.completion_dict[jid][InfoColumn.NAME]

                local_time = time.localtime(row.time)
                date = time.strftime('%Y-%m-%d', local_time)

                model.append((jid, contact_name, date, row.message,
                              str(row.time), row.log_line_id))

    def on_results_treeview_row_activated(self, widget, path, column):
        """
        A row was double clicked, get date from row, and select it in calendar
        which results to showing conversation logs for that date
        """
        # get currently selected date
        cur_year, cur_month, cur_day = self.calendar.get_date()
        cur_month = gtkgui_helpers.make_gtk_month_python_month(cur_month)
        model = widget.get_model()
        # make it a tuple (Y, M, D, 0, 0, 0...)
        tim = time.strptime(model[path][Column.UNIXTIME], '%Y-%m-%d')
        year = tim[0]
        gtk_month = tim[1]
        month = gtkgui_helpers.make_python_month_gtk_month(gtk_month)
        day = tim[2]

        # switch to belonging logfile if necessary
        log_jid = model[path][Column.LOG_JID]
        if log_jid != self.jid:
            self._load_history(log_jid, None)

        # avoid reruning mark days algo if same month and year!
        if year != cur_year or gtk_month != cur_month:
            self.calendar.select_month(month, year)

        if year != cur_year or gtk_month != cur_month or day != cur_day:
            self.calendar.select_day(day)

        self._scroll_to_message_and_highlight(model[path][Column.LOG_LINE_ID])

    def _scroll_to_message_and_highlight(self, log_line_id):
        """
        Scroll to a message and highlight it
        """

        def iterator_has_mark(iterator, mark_name):
            for mark in iterator.get_marks():
                if mark.get_name() == mark_name:
                    return True
            return False

        # Clear previous search result by removing the highlighting. The scroll
        # mark is automatically removed when the new one is set.
        start = self.history_buffer.get_start_iter()
        end = self.history_buffer.get_end_iter()
        self.history_buffer.remove_tag_by_name('highlight', start, end)

        log_line_id = str(log_line_id)
        line = start
        while not iterator_has_mark(line, log_line_id):
            if not line.forward_line():
                return

        match_start = line
        match_end = match_start.copy()
        match_end.forward_to_tag_toggle(self.history_buffer.eol_tag)

        self.history_buffer.apply_tag_by_name('highlight', match_start, match_end)
        mark = self.history_buffer.create_mark('match', match_start, True)
        GLib.idle_add(self.history_textview.tv.scroll_to_mark, mark, 0, True, 0.0, 0.5)

    def on_log_history_checkbutton_toggled(self, widget):
        # log conversation history?
        oldlog = True
        no_log_for = app.config.get_per('accounts', self.account,
                'no_log_for').split()
        if self.jid in no_log_for:
            oldlog = False
        log = widget.get_active()
        if not log and not self.jid in no_log_for:
            no_log_for.append(self.jid)
        if log and self.jid in no_log_for:
            no_log_for.remove(self.jid)
        if oldlog != log:
            app.config.set_per('accounts', self.account, 'no_log_for',
                    ' '.join(no_log_for))

    def on_show_status_checkbutton_toggled(self, widget):
        # reload logs
        self.on_calendar_day_selected(None)

    def open_history(self, jid, account):
        """
        Load chat history of the specified jid
        """
        self.jid_entry.set_text(jid)
        if account and account not in self.accounts_seen_online:
            # Update dict to not only show bare jid
            GLib.idle_add(next, self._fill_completion_dict())
        else:
            # Only in that case because it's called by self._fill_completion_dict()
            # otherwise
            self._load_history(jid, account)
        self.results_window.set_property('visible', False)

    def save_state(self):
        x, y = self.window.get_window().get_root_origin()
        width, height = self.window.get_size()

        app.config.set('history_window_x-position', x)
        app.config.set('history_window_y-position', y)
        app.config.set('history_window_width', width)
        app.config.set('history_window_height', height)
