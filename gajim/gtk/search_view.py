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

from __future__ import annotations

from typing import Any
from typing import Iterator
from typing import Optional

from datetime import datetime
from datetime import timedelta
import itertools
import logging
import time
import re

from gi.repository import GObject
from gi.repository import Gtk
import cairo

from nbxmpp import JID

from gajim.common import app
from gajim.common import ged
from gajim.common.const import AvatarSize
from gajim.common.const import Direction
from gajim.common.const import KindConstant
from gajim.common.storage.archive import SearchLogRow

from .conversation.message_widget import MessageWidget
from .builder import get_builder
from .util import gtk_month
from .util import python_month

log = logging.getLogger('gajim.gui.search_view')


class SearchView(Gtk.Box):
    __gsignals__ = {
        'hide-search': (
            GObject.SignalFlags.RUN_FIRST,
            None,
            ()),
    }

    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        self.set_size_request(300, -1)

        self._account: Optional[str] = None
        self._jid: Optional[JID] = None
        self._results_iterator: Optional[Iterator[SearchLogRow]] = None
        self._scope: str = 'everywhere'

        self._first_date: Optional[datetime] = None
        self._last_date: Optional[datetime] = None

        self._ui = get_builder('search_view.ui')
        self._ui.results_listbox.set_header_func(self._header_func)
        self.add(self._ui.search_box)

        self._ui.connect_signals(self)

        app.ged.register_event_handler('account-enabled',
                                       ged.GUI1,
                                       self._on_account_state)
        app.ged.register_event_handler('account-disabled',
                                       ged.GUI1,
                                       self._on_account_state)
        self._update_calendar()
        self.show_all()

    def _on_account_state(self, _event: Any) -> None:
        self.clear()

    @staticmethod
    def _header_func(row: ResultRow, before: ResultRow) -> None:
        if before is None:
            row.set_header(RowHeader(row.account, row.jid, row.time))
        else:
            date1 = time.strftime('%x', time.localtime(row.time))
            date2 = time.strftime('%x', time.localtime(before.time))
            if before.jid != row.jid:
                row.set_header(RowHeader(row.account, row.jid, row.time))
            elif date1 != date2:
                row.set_header(RowHeader(row.account, row.jid, row.time))
            else:
                row.set_header(None)

    def _on_hide_clicked(self, _button: Gtk.Button) -> None:
        self.emit('hide-search')
        self.clear()

    def clear(self) -> None:
        self._ui.search_entry.set_text('')
        self._clear_results()

    def _clear_results(self) -> None:
        for row in self._ui.results_listbox.get_children():
            self._ui.results_listbox.remove(row)
            row.destroy()

    def _on_search(self, entry: Gtk.Entry) -> None:
        self._clear_results()
        self._ui.date_hint.hide()
        text = entry.get_text()
        if not text:
            return

        # from:user
        # This works only for MUC, because contact_name is not
        # available for single contacts in logs.db.
        text, from_filters = self._strip_filters(text, 'from')

        # before:date
        text, before_filters = self._strip_filters(text, 'before')
        if before_filters is not None:
            try:
                before_filters = min([datetime.fromisoformat(date) for
                                      date in before_filters])
            except ValueError:
                self._ui.date_hint.show()
                return

        # after:date
        text, after_filters = self._strip_filters(text, 'after')
        if after_filters is not None:
            try:
                after_filters = min([datetime.fromisoformat(date) for
                                     date in after_filters])
                # if only the day is specified, we want to look after the
                # end of that day.
                # if precision is increased,we do want to look during the
                # day as well.
                if after_filters.hour == after_filters.minute == 0:
                    after_filters += timedelta(days=1)
            except ValueError:
                self._ui.date_hint.show()
                return

        everywhere = self._ui.search_checkbutton.get_active()
        context = self._account is not None and self._jid is not None

        if not context or everywhere:
            self._scope = 'everywhere'
            self._results_iterator = app.storage.archive.search_all_logs(
                text,
                from_users=from_filters,
                before=before_filters,
                after=after_filters)
        else:
            self._scope = 'contact'
            self._results_iterator = app.storage.archive.search_log(
                self._account,
                self._jid,
                text,
                from_users=from_filters,
                before=before_filters,
                after=after_filters)

        self._add_results()

    @staticmethod
    def _strip_filters(text: str,
                       filter_name: str) -> tuple[str, Optional[list[str]]]:
        filters: list[str] = []
        start = 0
        new_text = ''
        for search_filter in re.finditer(filter_name + r':(\S+)\s?', text):
            end, new_start = search_filter.span()
            new_text += text[start:end]
            filters.append(search_filter.group(1))
            start = new_start
        new_text += text[start:]
        return new_text, filters or None

    def _add_results(self) -> None:
        accounts = self._get_accounts()
        assert self._results_iterator is not None
        for msg in itertools.islice(self._results_iterator, 25):
            if self._scope == 'everywhere':
                archive_jid = app.storage.archive.get_jid_from_id(msg.jid_id)
                result_row = ResultRow(
                    msg,
                    accounts[msg.account_id],
                    archive_jid.jid)
            else:
                assert self._account is not None
                assert self._jid is not None
                result_row = ResultRow(msg, self._account, self._jid)

            self._ui.results_listbox.add(result_row)

    def _on_edge_reached(self,
                         _scrolledwin: Gtk.ScrolledWindow,
                         pos: Gtk.PositionType) -> None:
        if pos != Gtk.PositionType.BOTTOM:
            return

        self._add_results()

    def _update_calendar(self) -> None:
        if self._scope == 'everywhere':
            self._ui.calendar_button.set_sensitive(False)
        else:
            self._ui.calendar_button.set_sensitive(True)

            first_log = app.storage.archive.get_first_history_timestamp(
                self._account, self._jid)
            if first_log is None:
                return
            self._first_date = self._get_date_from_timestamp(first_log)
            last_log = app.storage.archive.get_last_history_timestamp(
                self._account, self._jid)
            if last_log is None:
                return
            self._last_date = self._get_date_from_timestamp(last_log)

            month = gtk_month(self._last_date.month)
            self._ui.calendar.select_month(month, self._last_date.year)

    def _on_month_changed(self, calendar: Gtk.Calendar) -> None:
        # Mark days with history in calendar
        year, month, _day = calendar.get_date()
        if year < 1900:
            calendar.select_month(0, 1900)
            calendar.select_day(1)
            return

        calendar.clear_marks()
        month = python_month(month)

        history_days = app.storage.archive.get_days_with_history(
            self._account, self._jid, year, month)
        for date in history_days:
            calendar.mark_day(date.day)

    def _on_date_selected(self, calendar: Gtk.Calendar) -> None:
        year, month, day = calendar.get_date()
        py_m = python_month(month)
        date = datetime(year, py_m, day)
        self._scroll_to_date(date)

    def _on_first_date_selected(self, _button: Gtk.Button) -> None:
        assert self._first_date is not None
        gtk_m = gtk_month(self._first_date.month)
        self._ui.calendar.select_month(gtk_m, self._first_date.year)
        self._ui.calendar.select_day(self._first_date.day)

    def _on_last_date_selected(self, _button: Gtk.Button) -> None:
        assert self._last_date is not None
        gtk_m = gtk_month(self._last_date.month)
        self._ui.calendar.select_month(gtk_m, self._last_date.year)
        self._ui.calendar.select_day(self._last_date.day)

    def _on_previous_date_selected(self, _button: Gtk.Button) -> None:
        delta = timedelta(days=-1)
        assert self._first_date is not None
        self._select_date(delta, self._first_date, Direction.NEXT)

    def _on_next_date_selected(self, _button: Gtk.Button) -> None:
        delta = timedelta(days=1)
        assert self._last_date is not None
        self._select_date(delta, self._last_date, Direction.PREV)

    def _select_date(self,
                     delta: timedelta,
                     end_date: datetime,
                     direction: Direction
                     ) -> None:
        # Iterate through days until history entry found or
        # supplied end_date (first_date/last_date) reached
        year, month, day = self._ui.calendar.get_date()
        py_m = python_month(month)
        date = datetime(year, py_m, day)

        history = None
        while history is None:
            if direction == Direction.PREV:
                if end_date <= date:
                    return
            else:
                if end_date >= date:
                    return

            date = date + delta
            if date == end_date:
                break
            history = app.storage.archive.date_has_history(
                self._account, self._jid, date)

        gtk_m = gtk_month(date.month)
        self._ui.calendar.select_month(gtk_m, date.year)
        self._ui.calendar.select_day(date.day)

    def _scroll_to_date(self, date: datetime) -> None:
        control = app.window.get_active_control()
        if control is None:
            return
        if control.contact.jid == self._jid:
            meta_row = app.storage.archive.get_first_message_meta_for_date(
                self._account, self._jid, date)
            if meta_row is None:
                return
            control.scroll_to_message(
                meta_row.log_line_id,
                meta_row.time)

    @staticmethod
    def _get_date_from_timestamp(timestamp: float) -> datetime:
        localtime = time.localtime(timestamp)
        year, month, day = localtime[0], localtime[1], localtime[2]
        date = datetime(year, month, day)
        return date

    @staticmethod
    def _get_accounts() -> dict[int, str]:
        accounts: dict[int, str] = {}
        for account in app.settings.get_accounts():
            account_id = app.storage.archive.get_account_id(account)
            accounts[account_id] = account
        return accounts

    @staticmethod
    def _on_row_activated(_listbox: SearchView, row: ResultRow) -> None:
        control = app.window.get_active_control()
        if control is not None:
            if control.contact.jid == row.jid:
                control.scroll_to_message(row.log_line_id, row.timestamp)
                return

        # Wrong chat or no control opened
        # TODO: type 'pm' is KindConstant.CHAT_MSG_RECV, too
        jid = JID.from_string(row.jid)
        app.window.add_chat(row.account, jid, row.type, select=True)
        control = app.window.get_active_control()
        if control is not None:
            control.scroll_to_message(row.log_line_id, row.timestamp)

    def set_focus(self) -> None:
        self._ui.search_entry.grab_focus()

    def set_context(self, account: Optional[str], jid: Optional[JID]) -> None:
        self._account = account
        self._jid = jid
        everywhere = bool(jid is None)
        self._ui.search_checkbutton.set_active(everywhere)
        context = account is not None and jid is not None
        if not context or everywhere:
            self._scope = 'everywhere'
        else:
            self._scope = 'contact'
        self._update_calendar()


class RowHeader(Gtk.Box):
    def __init__(self, account: str, jid: JID, timestamp: float) -> None:
        Gtk.Box.__init__(self)
        self.set_hexpand(True)

        self._ui = get_builder('search_view.ui')
        self.add(self._ui.header_box)

        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)
        self._ui.header_name_label.set_text(contact.name or '')

        local_time = time.localtime(timestamp)
        date = time.strftime('%x', local_time)
        self._ui.header_date_label.set_text(date)

        self.show_all()


class ResultRow(Gtk.ListBoxRow):
    def __init__(self, msg: SearchLogRow, account: str, jid: JID) -> None:
        Gtk.ListBoxRow.__init__(self)
        self.account = account
        self.jid = jid
        self.time = msg.time
        self._client = app.get_client(account)

        self.log_line_id = msg.log_line_id
        self.timestamp = msg.time
        self.kind = msg.kind

        self.type = 'contact'
        if msg.kind == KindConstant.GC_MSG:
            self.type = 'groupchat'

        self.contact = self._client.get_module('Contacts').get_contact(
            jid, groupchat=self.type == 'groupchat')

        self.get_style_context().add_class('conversation-row')
        self._ui = get_builder('search_view.ui')
        self.add(self._ui.result_row_grid)

        kind = 'status'
        contact_name = msg.contact_name
        if msg.kind in (
                KindConstant.SINGLE_MSG_RECV, KindConstant.CHAT_MSG_RECV):
            kind = 'incoming'
            contact_name = self.contact.name
        elif msg.kind == KindConstant.GC_MSG:
            kind = 'incoming'
        elif msg.kind in (
                KindConstant.SINGLE_MSG_SENT, KindConstant.CHAT_MSG_SENT):
            kind = 'outgoing'
            contact_name = app.nicks[account]
        self._ui.row_name_label.set_text(contact_name)

        avatar = self._get_avatar(kind, contact_name)
        self._ui.row_avatar.set_from_surface(avatar)

        local_time = time.localtime(msg.time)
        date = time.strftime('%H:%M', local_time)
        self._ui.row_time_label.set_label(date)

        message_widget = MessageWidget(account, selectable=False)
        message_widget.add_with_styling(msg.message, nickname=contact_name)
        self._ui.result_row_grid.attach(message_widget, 1, 1, 2, 1)

        self.show_all()

    def _get_avatar(self,
                    kind: str,
                    name: str) -> Optional[cairo.ImageSurface]:

        scale = self.get_scale_factor()
        if self.contact.is_groupchat:
            contact = self.contact.get_resource(name)
            return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

        if kind == 'outgoing':
            contact = self._client.get_module('Contacts').get_contact(
                str(self._client.get_own_jid().bare))
        else:
            contact = self.contact

        return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)
