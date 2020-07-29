# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005 Vincent Hanquez <tab AT snarc.org>
# Copyright (C) 2005-2006 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Dimitur Kirov <dkirov AT gmail.com>
#                    Travis Shirk <travis AT pobox.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Brendan Taylor <whateley AT gmail.com>
#
# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

import time
import datetime
from enum import IntEnum
from enum import unique

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GLib

from gajim.common import app
from gajim.common import helpers
from gajim.common import exceptions
from gajim.common.i18n import _
from gajim.common.const import ShowConstant
from gajim.common.const import KindConstant
from gajim.common.const import StyleAttr

from gajim import conversation_textview

from gajim.gtk.util import python_month
from gajim.gtk.util import gtk_month
from gajim.gtk.util import resize_window
from gajim.gtk.util import move_window
from gajim.gtk.util import get_icon_name
from gajim.gtk.util import get_completion_liststore
from gajim.gtk.util import get_builder
from gajim.gtk.util import scroll_to_end

from gajim.gtk.dialogs import ErrorDialog

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


class HistoryWindow(Gtk.ApplicationWindow):
    def __init__(self, jid=None, account=None):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Conversation History'))

        self._ui = get_builder('history_window.ui')

        self.add(self._ui.history_box)

        self.history_textview = conversation_textview.ConversationTextview(
            account, used_in_history_window=True)
        self._ui.scrolledwindow.add(self.history_textview.tv)
        self.history_buffer = self.history_textview.tv.get_buffer()
        highlight_color = app.css_config.get_value(
            '.gajim-search-highlight', StyleAttr.COLOR)
        self.history_buffer.create_tag('highlight', background=highlight_color)
        self.history_buffer.create_tag('invisible', invisible=True)

        self.clearing_search = False

        # jid, contact_name, date, message, time, log_line_id
        model = Gtk.ListStore(str, str, str, str, str, int)
        self._ui.results_treeview.set_model(model)
        col = Gtk.TreeViewColumn(_('Name'))
        self._ui.results_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', Column.CONTACT_NAME)
        # user can click this header and sort
        col.set_sort_column_id(Column.CONTACT_NAME)
        col.set_resizable(True)

        col = Gtk.TreeViewColumn(_('Date'))
        self._ui.results_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', Column.UNIXTIME)
        # user can click this header and sort
        col.set_sort_column_id(Column.UNIXTIME)
        col.set_resizable(True)

        col = Gtk.TreeViewColumn(_('Message'))
        self._ui.results_treeview.append_column(col)
        renderer = Gtk.CellRendererText()
        col.pack_start(renderer, True)
        col.add_attribute(renderer, 'text', Column.MESSAGE)
        col.set_resizable(True)

        self.jid = None  # The history we are currently viewing
        self.account = account
        self.completion_dict = {}
        self.accounts_seen_online = []  # Update dict when new accounts connect
        self.jids_to_search = []

        # This will load history too
        task = self._fill_completion_dict()
        GLib.idle_add(next, task)

        if jid:
            self._ui.query_entry.get_child().set_text(jid)
        else:
            self._load_history(None)

        resize_window(self,
                      app.settings.get('history_window_width'),
                      app.settings.get('history_window_height'))
        move_window(self,
                    app.settings.get('history_window_x-position'),
                    app.settings.get('history_window_y-position'))

        self._ui.connect_signals(self)
        self.connect('delete-event', self._on_delete)
        self.connect('destroy', self._on_destroy)
        self.connect('key-press-event', self._on_key_press)
        self.show_all()

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
        liststore = get_completion_liststore(
            self._ui.query_entry.get_child())
        liststore.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self._ui.query_entry.get_child().get_completion().connect(
            'match-selected', self.on_jid_entry_match_selected)

        self._ui.query_entry.set_model(liststore)

        # Add all jids in logs.db:
        db_jids = app.logger.get_jids_in_db()
        completion_dict = dict.fromkeys(db_jids)

        self.accounts_seen_online = list(app.contacts.get_accounts())

        # Enhance contacts of online accounts with contact.
        # Needed for mapping below
        for account in self.accounts_seen_online:
            completion_dict.update(
                helpers.get_contact_dict_for_account(account))

        muc_active_icon = get_icon_name('muc-active')
        online_icon = get_icon_name('online')

        keys = list(completion_dict.keys())
        # Move the actual jid at first so we load history faster
        actual_jid = self._ui.query_entry.get_child().get_text()
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
                # Corresponding account is offline, we know nothing
                info_name = completed.split('@')[0]
                info_completion = completed
                info_jid = completed

            info_acc = self._get_account_for_jid(info_jid)

            if (app.logger.jid_is_room_jid(completed) or
                    app.logger.jid_is_from_pm(completed)):
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
            self.completion_dict[key] = (
                info_jid, info_acc, info_name, info_completion)
            self.completion_dict[completed] = (
                info_jid, info_acc, info_name, info_completion)
            if completed2:
                if len(completed2) > 70:
                    completed2 = completed2[:70] + '[\u2026]'
                liststore.append((icon, completed2))
                self.completion_dict[completed2] = (
                    info_jid, info_acc, info_name, info_completion2)
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

    def _on_delete(self, widget, *args):
        self.save_state()

    def _on_destroy(self, widget):
        # PluginSystem: removing GUI extension points connected with
        # HistoryWindow instance object
        app.plugin_manager.remove_gui_extension_point(
            'history_window', self)
        self.history_textview.del_handlers()

    def _on_key_press(self, widget, event):
        if event.keyval == Gdk.KEY_Escape:
            if self._ui.results_scrolledwindow.get_visible():
                self._ui.results_scrolledwindow.set_visible(False)
                return
            self.save_state()
            self.destroy()

    def on_jid_entry_match_selected(self, widget, model, iter_, *args):
        self._jid_entry_search(model[iter_][1])
        return True

    def on_jid_entry_changed(self, widget):
        # only if selected from combobox
        jid = self._ui.query_entry.get_child().get_text()
        if jid == self._ui.query_entry.get_active_id():
            self._jid_entry_search(jid)

    def on_jid_entry_activate(self, widget):
        self._jid_entry_search(self._ui.query_entry.get_child().get_text())

    def _jid_entry_search(self, jid):
        self._load_history(jid, self.account)
        self._ui.results_scrolledwindow.set_visible(False)

    def _load_history(self, jid_or_name, account=None):
        """
        Load history for the given jid/name and show it
        """
        if jid_or_name and jid_or_name in self.completion_dict:
            # a full qualified jid or a contact name was entered
            info_jid, info_account, _info_name, info_completion = self.completion_dict[jid_or_name]
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
                self._ui.log_history_checkbutton.set_sensitive(False)
            else:
                # Are log disabled for account ?
                if self.account in app.config.get_per(
                        'accounts', self.account, 'no_log_for').split(' '):
                    self._ui.log_history_checkbutton.set_active(False)
                    self._ui.log_history_checkbutton.set_sensitive(False)
                else:
                    # Are log disabled for jid ?
                    log = True
                    if self.jid in app.config.get_per(
                            'accounts', self.account, 'no_log_for').split(' '):
                        log = False
                    self._ui.log_history_checkbutton.set_active(log)
                    self._ui.log_history_checkbutton.set_sensitive(True)

            self.jids_to_search = [info_jid]

            # Get first/last date we have logs with contact
            self.first_log = app.logger.get_first_date_that_has_logs(
                self.account, self.jid)
            self.first_day = self._get_date_from_timestamp(self.first_log)
            self.last_log = app.logger.get_last_date_that_has_logs(
                self.account, self.jid)
            self.last_day = self._get_date_from_timestamp(self.last_log)

            # Select logs for last date we have logs with contact
            self._ui.search_menu_button.set_sensitive(True)
            month = gtk_month(self.last_day.month)
            self._ui.calendar.select_month(month, self.last_day.year)
            self._ui.calendar.select_day(self.last_day.day)

            self._ui.button_previous_day.set_sensitive(True)
            self._ui.button_next_day.set_sensitive(True)
            self._ui.button_first_day.set_sensitive(True)
            self._ui.button_last_day.set_sensitive(True)

            self._ui.search_entry.set_sensitive(True)
            self._ui.search_entry.grab_focus()

            self._ui.query_entry.get_child().set_text(info_completion)

        else:
            # neither a valid jid, nor an existing contact name was entered
            # we have got nothing to show or to search in
            self.jid = None
            self.account = None

            self.history_buffer.set_text('')  # clear the buffer
            self._ui.search_entry.set_sensitive(False)

            self._ui.log_history_checkbutton.set_sensitive(False)
            self._ui.search_menu_button.set_sensitive(False)
            self._ui.calendar.clear_marks()
            self._ui.button_previous_day.set_sensitive(False)
            self._ui.button_next_day.set_sensitive(False)
            self._ui.button_first_day.set_sensitive(False)
            self._ui.button_last_day.set_sensitive(False)

            self._ui.results_scrolledwindow.set_visible(False)

    def on_calendar_day_selected(self, widget):
        if not self.jid:
            return
        year, month, day = self._ui.calendar.get_date()  # integers
        month = python_month(month)
        date_str = datetime.date(year, month, day).strftime('%x')
        self._ui.date_label.set_text(date_str)
        self._load_conversation(year, month, day)
        GLib.idle_add(scroll_to_end, self._ui.scrolledwindow)

    def on_calendar_month_changed(self, widget):
        """
        Ask for days in this month, if they have logs it bolds them
        (marks them)
        """
        if not self.jid:
            return
        year, month, _day = widget.get_date()  # integers
        if year < 1900:
            widget.select_month(0, 1900)
            widget.select_day(1)
            return

        widget.clear_marks()
        month = python_month(month)

        try:
            log_days = app.logger.get_days_with_logs(
                self.account, self.jid, year, month)
        except exceptions.PysqliteOperationalError as error:
            ErrorDialog(_('Disk Error'), str(error))
            return

        for date in log_days:
            widget.mark_day(date.day)

    def _get_date_from_timestamp(self, timestamp):
        # Conversion from timestamp to date
        log = time.localtime(timestamp)
        y, m, d = log[0], log[1], log[2]
        date = datetime.datetime(y, m, d)
        return date

    def _change_date(self, widget):
        # Get day selected in calendar
        y, m, d = self._ui.calendar.get_date()
        py_m = python_month(m)
        _date = datetime.datetime(y, py_m, d)

        if widget is self._ui.button_first_day:
            gtk_m = gtk_month(self.first_day.month)
            self._ui.calendar.select_month(gtk_m, self.first_day.year)
            self._ui.calendar.select_day(self.first_day.day)
            return

        if widget is self._ui.button_last_day:
            gtk_m = gtk_month(
                self.last_day.month)
            self._ui.calendar.select_month(gtk_m, self.last_day.year)
            self._ui.calendar.select_day(self.last_day.day)
            return

        if widget is self._ui.button_previous_day:
            end_date = self.first_day
            timedelta = datetime.timedelta(days=-1)
            if end_date >= _date:
                return
        elif widget is self._ui.button_next_day:
            end_date = self.last_day
            timedelta = datetime.timedelta(days=1)
            if end_date <= _date:
                return

        # Iterate through days until log entry found or
        # supplied end_date (first_log / last_log) reached
        logs = None
        while logs is None:
            _date = _date + timedelta
            if _date == end_date:
                break
            try:
                logs = app.logger.get_date_has_logs(
                    self.account, self.jid, _date)
            except exceptions.PysqliteOperationalError as e:
                ErrorDialog(_('Disk Error'), str(e))
                return

        gtk_m = gtk_month(_date.month)
        self._ui.calendar.select_month(gtk_m, _date.year)
        self._ui.calendar.select_day(_date.day)

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
        show_status = self._ui.show_status_checkbutton.get_active()

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

        if app.settings.get('print_time') == 'always':
            timestamp_str = app.settings.get('time_stamp')
            timestamp_str = helpers.from_one_line(timestamp_str)
            tim = time.strftime(timestamp_str, time.localtime(float(tim)))
            buf.insert(end_iter, tim)
        elif app.settings.get('print_time') == 'sometimes':
            every_foo_seconds = 60 * app.settings.get(
                'print_ichat_every_foo_minutes')
            seconds_passed = tim - self.last_time_printout
            if seconds_passed > every_foo_seconds:
                self.last_time_printout = tim
                tim = time.strftime('%X ', time.localtime(float(tim)))
                buf.insert_with_tags_by_name(
                    end_iter, tim + '\n', 'time_sometimes')

        # print the encryption icon
        if kind in (KindConstant.CHAT_MSG_SENT,
                    KindConstant.CHAT_MSG_RECV):
            self.history_textview.print_encryption_status(
                end_iter, additional_data)

        tag_name = ''
        tag_msg = ''

        show = self._get_string_show_from_constant_int(show)

        if kind == KindConstant.GC_MSG:
            tag_name = 'incoming'
        elif kind in (KindConstant.SINGLE_MSG_RECV,
                      KindConstant.CHAT_MSG_RECV):
            contact_name = self.completion_dict[self.jid][InfoColumn.NAME]
            tag_name = 'incoming'
            tag_msg = 'incomingtxt'
        elif kind in (KindConstant.SINGLE_MSG_SENT,
                      KindConstant.CHAT_MSG_SENT):
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
                message = _('%(nick)s is now %(status)s: %(status_msg)s') % {
                    'nick': contact_name,
                    'status': helpers.get_uf_show(show),
                    'status_msg': message}
            else:
                message = _('%(nick)s is now %(status)s') % {
                    'nick': contact_name,
                    'status': helpers.get_uf_show(show)}
            tag_msg = 'status'
        else:  # 'status'
            # message here (if not None) is status message
            if show is None:  # it means error
                if message:
                    message = _('Error: %s') % message
                else:
                    message = _('Error')
            elif message:
                message = _('Status is now: %(status)s: %(status_msg)s') % {
                    'status': helpers.get_uf_show(show),
                    'status_msg': message}
            else:
                message = _('Status is now: %(status)s') % {
                    'status': helpers.get_uf_show(show)}
            tag_msg = 'status'

        if message.startswith('/me ') or message.startswith('/me\n'):
            tag_msg = tag_name
        else:
            # do not do this if gcstats, avoid dupping contact_name
            # eg. nkour: nkour is now Offline
            if contact_name and kind != KindConstant.GCSTATUS:
                # add stuff before and after contact name
                before_str = app.settings.get('before_nickname')
                before_str = helpers.from_one_line(before_str)
                after_str = app.settings.get('after_nickname')
                after_str = helpers.from_one_line(after_str)
                format_ = before_str + contact_name + after_str + ' '
                if tag_name:
                    buf.insert_with_tags_by_name(end_iter, format_, tag_name)
                else:
                    buf.insert(end_iter, format_)
        if subject:
            message = _('Subject: %s\n') % subject + message

        if tag_msg:
            self.history_textview.print_real_text(
                message,
                [tag_msg],
                name=contact_name,
                additional_data=additional_data)
        else:
            self.history_textview.print_real_text(
                message,
                name=contact_name,
                additional_data=additional_data)
        self.history_textview.print_real_text('\n', text_tags=['eol'])

    def on_search_complete_history_toggled(self, widget):
        self._ui.date_label.get_style_context().remove_class('tagged')

    def on_search_in_date_toggled(self, widget):
        self._ui.date_label.get_style_context().add_class('tagged')

    def on_search_entry_activate(self, widget):
        text = self._ui.search_entry.get_text()

        model = self._ui.results_treeview.get_model()
        self.clearing_search = True
        model.clear()
        self.clearing_search = False

        start = self.history_buffer.get_start_iter()
        end = self.history_buffer.get_end_iter()
        self.history_buffer.remove_tag_by_name('highlight', start, end)

        if text == '':
            self._ui.results_scrolledwindow.set_visible(False)
            return

        self._ui.results_scrolledwindow.set_visible(True)

        # perform search in preselected jids
        # jids are preselected with the query_entry
        for jid in self.jids_to_search:
            account = self.completion_dict[jid][InfoColumn.ACCOUNT]
            if account is None:
                # We do not know an account. This can only happen if
                # the contact is offine, or if we browse a groupchat history.
                # The account is not needed, a dummy can be set.
                # This may leed to wrong self nick in the displayed history
                account = list(app.contacts.get_accounts())[0]

            date = None
            if self._ui.search_in_date.get_active():
                year, month, day = self._ui.calendar.get_date()  # integers
                month = python_month(month)
                date = datetime.datetime(year, month, day)

            show_status = self._ui.show_status_checkbutton.get_active()

            results = app.logger.search_log(account, jid, text, date)
            result_found = False
            # FIXME:
            # add "subject:  | message: " in message column if kind is single
            # also do we need show at all? (we do not search on subject)
            for row in results:
                if not show_status and row.kind in (KindConstant.GCSTATUS,
                                                    KindConstant.STATUS):
                    continue

                contact_name = row.contact_name
                if not contact_name:
                    if row.kind == KindConstant.CHAT_MSG_SENT:
                        contact_name = app.nicks[account]
                    else:
                        contact_name = self.completion_dict[jid][InfoColumn.NAME]

                local_time = time.localtime(row.time)
                date = time.strftime('%Y-%m-%d', local_time)

                result_found = True
                model.append((jid, contact_name, date, row.message,
                              str(row.time), row.log_line_id))

            if result_found:
                self._ui.results_treeview.set_cursor(0)

    def on_results_treeview_cursor_changed(self, *args):
        """
        A row was selected, get date from row, and select it in calendar
        which results to showing conversation logs for that date
        """
        if self.clearing_search:
            return

        # get currently selected date
        cur_year, cur_month, cur_day = self._ui.calendar.get_date()
        cur_month = python_month(cur_month)
        model, paths = self._ui.results_treeview.get_selection().get_selected_rows()

        if not paths:
            return

        path = paths[0]
        # make it a tuple (Y, M, D, 0, 0, 0...)
        tim = time.strptime(model[path][Column.UNIXTIME], '%Y-%m-%d')
        year = tim[0]
        gtk_m = tim[1]
        month = gtk_month(gtk_m)
        day = tim[2]

        # switch to belonging logfile if necessary
        log_jid = model[path][Column.LOG_JID]
        if log_jid != self.jid:
            self._load_history(log_jid, None)

        # avoid rerunning mark days algo if same month and year!
        if year != cur_year or gtk_m != cur_month:
            self._ui.calendar.select_month(month, year)

        if year != cur_year or gtk_m != cur_month or day != cur_day:
            self._ui.calendar.select_day(day)

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

        self.history_buffer.apply_tag_by_name(
            'highlight', match_start, match_end)
        mark = self.history_buffer.create_mark('match', match_start, True)
        GLib.idle_add(
            self.history_textview.tv.scroll_to_mark, mark, 0, True, 0.0, 0.5)

    def on_log_history_checkbutton_toggled(self, widget, *args):
        # log conversation history?
        oldlog = True
        no_log_for = app.config.get_per(
            'accounts', self.account, 'no_log_for').split()
        if self.jid in no_log_for:
            oldlog = False
        log = widget.get_active()
        if not log and self.jid not in no_log_for:
            no_log_for.append(self.jid)
        if log and self.jid in no_log_for:
            no_log_for.remove(self.jid)
        if oldlog != log:
            app.config.set_per(
                'accounts', self.account, 'no_log_for', ' '.join(no_log_for))

    def on_show_status_checkbutton_toggled(self, widget):
        # reload logs
        self.on_calendar_day_selected(None)

    def open_history(self, jid, account):
        """
        Load chat history of the specified jid
        """
        self._ui.query_entry.get_child().set_text(jid)
        if account and account not in self.accounts_seen_online:
            # Update dict to not only show bare jid
            GLib.idle_add(next, self._fill_completion_dict())
        else:
            # Only in that case because it's called by
            # self._fill_completion_dict() otherwise
            self._load_history(jid, account)
        self._ui.results_scrolledwindow.set_visible(False)

    def save_state(self):
        x, y = self.get_window().get_root_origin()
        width, height = self.get_size()

        app.settings.set('history_window_x-position', x)
        app.settings.set('history_window_y-position', y)
        app.settings.set('history_window_width', width)
        app.settings.set('history_window_height', height)
