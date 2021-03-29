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
from gajim.common.i18n import _
from gajim.common.const import KindConstant
from gajim.common.exceptions import PysqliteOperationalError

# from gajim import conversation_textview

from .conversation.view import ConversationView
from .util import python_month
from .util import gtk_month
from .util import resize_window
from .util import move_window
from .util import get_icon_name
from .util import get_completion_liststore
from .util import get_builder
from .util import scroll_to_end

from .dialogs import ErrorDialog


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
    def __init__(self, account=None, jid=None):
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_title(_('Conversation History'))

        self.account = account
        self.jid = jid

        self._client = app.get_client(account)
        self._contact = None
        if jid is not None:
            self._contact = self._client.get_module('Contacts').get_contact(
                jid)

        self._ui = get_builder('history_window.ui')
        self.add(self._ui.history_box)

        self._conversation_view = ConversationView(
            account, self._contact, history_mode=True)
        self._ui.scrolledwindow.add(self._conversation_view)
        self._ui.scrolledwindow.set_focus_vadjustment(Gtk.Adjustment())

        self._clearing_search = False
        self._first_day = None
        self._last_day = None

        self._completion_dict = {}
        self._accounts_seen_online = []  # Update dict when new accounts connect
        self._jids_to_search = []

        # This will load history too
        task = self._fill_completion_dict()
        GLib.idle_add(next, task)

        if jid:
            self._ui.query_entry.set_text(jid)
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

    def _on_delete(self, _widget, *args):
        self._save_state()

    def _on_destroy(self, _widget):
        app.plugin_manager.remove_gui_extension_point(
            'history_window', self)

    def _on_key_press(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            if self._ui.results_scrolledwindow.get_visible():
                self._ui.results_scrolledwindow.set_visible(False)
                return
            self._save_state()
            self.destroy()

    def _on_jid_entry_match_selected(self, _widget, model, iter_, *args):
        self._jid_entry_search(model[iter_][1])
        return True

    def _on_query_combo_changed(self, combo):
        # only if selected from combobox
        jid = self._ui.query_entry.get_text()
        if jid == combo.get_active_id():
            self._jid_entry_search(jid)

    def _on_jid_entry_activate(self, entry):
        self._jid_entry_search(entry.get_text())

    def _jid_entry_search(self, jid):
        self._load_history(jid, self.account)
        self._ui.results_scrolledwindow.set_visible(False)

    def _fill_completion_dict(self):
        """
        Fill completion_dict for key auto completion. Then load history for
        current jid (by calling another function)

        Key will be either jid or full_completion_name (contact name or long
        description like "pm-contact from groupchat....").

        {key : (jid, account, nick_name, full_completion_name}
        This is a generator and does pseudo-threading via idle_add().
        """
        liststore = get_completion_liststore(self._ui.query_entry)
        liststore.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        self._ui.query_entry.get_completion().connect(
            'match-selected', self._on_jid_entry_match_selected)

        self._ui.query_combo.set_model(liststore)

        # Add all jids in logs.db:
        db_jids = app.storage.archive.get_jids_in_db()
        completion_dict = dict.fromkeys(db_jids)

        self._accounts_seen_online = list(app.settings.get_active_accounts())

        # Enhance contacts of online accounts with contact.
        # Needed for mapping below
        for account in self._accounts_seen_online:
            completion_dict.update(
                helpers.get_contact_dict_for_account(account))

        muc_active_icon = get_icon_name('muc-active')
        online_icon = get_icon_name('online')

        keys = list(completion_dict.keys())
        # Move the actual jid at first so we load history faster
        actual_jid = self._ui.query_entry.get_text()
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
                info_name = contact.name
                info_completion = info_name
                info_jid = contact.jid
            else:
                # Corresponding account is offline, we know nothing
                info_name = completed.split('@')[0]
                info_completion = completed
                info_jid = completed

            info_acc = self._get_account_for_jid(info_jid)

            if (app.storage.archive.jid_is_room_jid(completed) or
                    app.storage.archive.jid_is_from_pm(completed)):
                icon = muc_active_icon
                if app.storage.archive.jid_is_from_pm(completed):
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
            self._completion_dict[key] = (
                info_jid, info_acc, info_name, info_completion)
            self._completion_dict[completed] = (
                info_jid, info_acc, info_name, info_completion)
            if completed2:
                if len(completed2) > 70:
                    completed2 = completed2[:70] + '[\u2026]'
                liststore.append((icon, completed2))
                self._completion_dict[completed2] = (
                    info_jid, info_acc, info_name, info_completion2)
            if key == actual_jid:
                self._load_history(info_jid, self.account or info_acc)
            yield True
        keys.sort()
        yield False

    @staticmethod
    def _get_account_for_jid(jid):
        """
        Return the corresponding account of the jid. May be None if an account
        could not be found
        """
        accounts = app.settings.get_active_accounts()
        account = None
        for acc in accounts:
            jid_list = app.contacts.get_jid_list(acc)
            gc_list = app.contacts.get_gc_list(acc)
            if jid in jid_list or jid in gc_list:
                account = acc
                break
        return account

    def _load_history(self, jid_or_name, account=None):
        """
        Load history for the given jid/name and show it
        """
        if jid_or_name and jid_or_name in self._completion_dict:
            # a full qualified jid or a contact name was entered
            info_jid, info_account, _info_name, info_completion = self._completion_dict[jid_or_name]
            self._jids_to_search = [info_jid]
            self.jid = info_jid

            if account:
                self.account = account
            else:
                self.account = info_account
            if self.account is None:
                # We don't know account. Probably a gc not opened or an
                # account not connected.
                # Disable possibility to say if we want to log or not
                self._ui.store_history_switch.set_sensitive(False)
            else:
                # Are logs disabled for account ?
                no_log_for = app.settings.get_account_setting(
                    self.account, 'no_log_for').split(' ')
                if self.account in no_log_for:
                    self._ui.store_history_switch.set_active(False)
                    self._ui.store_history_switch.set_sensitive(False)
                else:
                    # Are logs disabled for jid ?
                    self._ui.store_history_switch.set_active(
                        str(self.jid) not in no_log_for)
                    self._ui.store_history_switch.set_sensitive(True)

            self._jids_to_search = [info_jid]

            # Get first/last date we have logs with contact
            self.first_log = app.storage.archive.get_first_date_that_has_logs(
                self.account, self.jid)
            self._first_day = self._get_date_from_timestamp(self.first_log)
            self.last_log = app.storage.archive.get_last_date_that_has_logs(
                self.account, self.jid)
            self._last_day = self._get_date_from_timestamp(self.last_log)

            # Select logs for last date we have logs with contact
            self._ui.search_menu_button.set_sensitive(True)
            month = gtk_month(self._last_day.month)
            self._ui.calendar.select_month(month, self._last_day.year)
            self._ui.calendar.select_day(self._last_day.day)

            self._ui.button_previous_day.set_sensitive(True)
            self._ui.button_next_day.set_sensitive(True)
            self._ui.button_first_day.set_sensitive(True)
            self._ui.button_last_day.set_sensitive(True)

            self._ui.search_entry.set_sensitive(True)
            self._ui.search_entry.grab_focus()

            self._ui.query_entry.set_text(info_completion)

        else:
            # neither a valid jid, nor an existing contact name was entered
            # we have got nothing to show or to search in
            self.jid = None
            self.account = None

            self._ui.search_entry.set_sensitive(False)
            self._ui.store_history_switch.set_sensitive(False)
            self._ui.search_menu_button.set_sensitive(False)
            self._ui.calendar.clear_marks()
            self._ui.button_previous_day.set_sensitive(False)
            self._ui.button_next_day.set_sensitive(False)
            self._ui.button_first_day.set_sensitive(False)
            self._ui.button_last_day.set_sensitive(False)

            self._ui.results_scrolledwindow.set_visible(False)

    def _on_day_selected(self, *args):
        if not self.jid:
            return
        year, month, day = self._ui.calendar.get_date()  # integers
        month = python_month(month)
        date_str = datetime.date(year, month, day).strftime('%x')
        self._ui.date_label.set_text(date_str)
        self._load_conversation(year, month, day)
        GLib.idle_add(scroll_to_end, self._ui.scrolledwindow)

    def _on_month_changed(self, calendar):
        """
        Ask for days in this month, if they have logs it bolds them
        (marks them)
        """
        if not self.jid:
            return
        year, month, _day = calendar.get_date()  # integers
        if year < 2000:
            calendar.select_month(0, 2000)
            calendar.select_day(1)
            return

        calendar.clear_marks()
        month = python_month(month)

        try:
            log_days = app.storage.archive.get_days_with_logs(
                self.account, self.jid, year, month)
        except PysqliteOperationalError as err:
            ErrorDialog(_('Disk Error'), str(err))
            return

        for date in log_days:
            calendar.mark_day(date.day)

    @staticmethod
    def _get_date_from_timestamp(timestamp):
        # Conversion from timestamp to date
        log = time.localtime(timestamp)
        year, mmonth, day = log[0], log[1], log[2]
        date = datetime.datetime(year, mmonth, day)
        return date

    def _change_date(self, button):
        year, month, day = self._ui.calendar.get_date()
        python_m = python_month(month)
        date_ = datetime.datetime(year, python_m, day)

        if button is self._ui.button_first_day:
            gtk_m = gtk_month(self._first_day.month)
            self._ui.calendar.select_month(gtk_m, self._first_day.year)
            self._ui.calendar.select_day(self._first_day.day)
            return

        if button is self._ui.button_last_day:
            gtk_m = gtk_month(self._last_day.month)
            self._ui.calendar.select_month(gtk_m, self._last_day.year)
            self._ui.calendar.select_day(self._last_day.day)
            return

        if button is self._ui.button_previous_day:
            end_date = self._first_day
            timedelta = datetime.timedelta(days=-1)
            if end_date >= date_:
                return

        if button is self._ui.button_next_day:
            end_date = self._last_day
            timedelta = datetime.timedelta(days=1)
            if end_date <= date_:
                return

        # Iterate through days until log entry found or
        # supplied end_date (first_log / last_log) reached
        logs = None
        while logs is None:
            date_ = date_ + timedelta
            if date_ == end_date:
                break
            try:
                logs = app.storage.archive.get_date_has_logs(
                    self.account, self.jid, date_)
            except PysqliteOperationalError as err:
                ErrorDialog(_('Disk Error'), str(err))
                return

        gtk_m = gtk_month(date_.month)
        self._ui.calendar.select_month(gtk_m, date_.year)
        self._ui.calendar.select_day(date_.day)

    def _load_conversation(self, year, month, day):
        """
        Load the conversation between `self.jid` and `self.account` held on the
        given date into the history textbuffer. Values for `month` and `day`
        are 1-based.
        """
        self._conversation_view.clear()

        show_status = self._ui.show_status_checkbutton.get_active()
        date = datetime.datetime(year, month, day)

        messages = app.storage.archive.get_messages_for_date(
            self.account, self.jid, date)
        for msg in messages:
            if not show_status and msg.kind in (KindConstant.STATUS,
                                                KindConstant.GCSTATUS):
                continue
            if not msg.message and msg.kind not in (KindConstant.STATUS,
                                                    KindConstant.GCSTATUS):
                continue

            kind = 'status'
            contact_name = msg.contact_name
            if msg.kind in (
                    KindConstant.SINGLE_MSG_RECV, KindConstant.CHAT_MSG_RECV):
                kind = 'incoming'
                contact_name = self._contact.name
            elif msg.kind == KindConstant.GC_MSG:
                kind = 'incoming'
            elif msg.kind in (
                    KindConstant.SINGLE_MSG_SENT, KindConstant.CHAT_MSG_SENT):
                kind = 'outgoing'
                contact_name = app.nicks[self.account]

            self._conversation_view.add_message(
                msg.message,
                kind,
                contact_name,
                msg.time,
                subject=msg.subject,
                additional_data=msg.additional_data,
                history=True,
                log_line_id=msg.log_line_id)

    def _on_search_complete_history(self, _widget):
        self._ui.date_label.get_style_context().remove_class('tagged')

    def _on_search_in_date(self, _widget):
        self._ui.date_label.get_style_context().add_class('tagged')

    def _on_search_entry_activate(self, entry):
        text = entry.get_text()

        model = self._ui.results_treeview.get_model()
        self._clearing_search = True
        model.clear()
        self._clearing_search = False

        if text == '':
            self._ui.results_scrolledwindow.set_visible(False)
            return

        self._ui.results_scrolledwindow.set_visible(True)

        # perform search in preselected jids
        # jids are preselected with the query_combo
        for jid in self._jids_to_search:
            account = self._completion_dict[jid][InfoColumn.ACCOUNT]
            if account is None:
                # We do not know an account. This can only happen if
                # the contact is offine, or if we browse a groupchat history.
                # The account is not needed, a dummy can be set.
                # This may leed to wrong self nick in the displayed history
                account = list(app.settings.get_active_accounts())[0]

            date = None
            if self._ui.search_in_date.get_active():
                year, month, day = self._ui.calendar.get_date()  # integers
                month = python_month(month)
                date = datetime.datetime(year, month, day)

            show_status = self._ui.show_status_checkbutton.get_active()

            results = app.storage.archive.search_log(account, jid, text, date)
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
                        contact_name = self._completion_dict[jid][InfoColumn.NAME]

                local_time = time.localtime(row.time)
                date = time.strftime('%Y-%m-%d', local_time)

                result_found = True
                model.append((str(jid), contact_name, date, row.message,
                              str(row.time), str(row.log_line_id)))

            if result_found:
                self._ui.results_treeview.set_cursor(0)

    def _on_results_cursor_changed(self, treeview):
        """
        A row was selected, get date from row, and select it in calendar
        which results to showing conversation logs for that date
        """
        if self._clearing_search:
            return

        # get currently selected date
        cur_year, cur_month, cur_day = self._ui.calendar.get_date()
        cur_month = python_month(cur_month)
        model, paths = treeview.get_selection().get_selected_rows()

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
        for row in self._conversation_view.iter_rows():
            row.get_style_context().remove_class(
                'conversation-search-highlight')

        row = self._conversation_view.get_row_by_log_line_id(int(log_line_id))
        if row is not None:
            row.get_style_context().add_class('conversation-search-highlight')
            # This scrolls the ListBox to the highlighted row
            row.grab_focus()
            self._ui.results_treeview.grab_focus()

    def _on_log_history(self, switch, *args):
        jid = str(self.jid)
        oldlog = True
        no_log_for = app.settings.get_account_setting(
            self.account, 'no_log_for').split()
        if jid in no_log_for:
            oldlog = False
        log = switch.get_active()
        if not log and jid not in no_log_for:
            no_log_for.append(jid)
        if log and jid in no_log_for:
            no_log_for.remove(jid)
        if oldlog != log:
            app.settings.set_account_setting(
                self.account, 'no_log_for', ' '.join(no_log_for))

    def _on_show_status(self, _widget):
        # Reload logs
        self._on_day_selected(None)

    def _save_state(self):
        x_pos, y_pos = self.get_window().get_root_origin()
        width, height = self.get_size()
        app.settings.set('history_window_x-position', x_pos)
        app.settings.set('history_window_y-position', y_pos)
        app.settings.set('history_window_width', width)
        app.settings.set('history_window_height', height)
