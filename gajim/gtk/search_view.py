# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import datetime as dt
import itertools
import logging
import re
from collections.abc import Iterator

import cairo
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.const import Direction
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import ResourceContact
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message

from gajim.gtk.builder import get_builder
from gajim.gtk.conversation.message_widget import MessageWidget
from gajim.gtk.util import gtk_month
from gajim.gtk.util import python_month

log = logging.getLogger('gajim.gtk.search_view')


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

        self._account: str | None = None
        self._jid: JID | None = None
        self._results_iterator: Iterator[Message] | None = None

        self._first_date: dt.datetime | None = None
        self._last_date: dt.datetime | None = None

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
        self.show_all()

    def _on_account_state(self, _event: Any) -> None:
        self._clear()

    @staticmethod
    def _header_func(row: ResultRow, before: ResultRow | None) -> None:
        if before is None:
            row.set_header(RowHeader(
                row.account, row.remote_jid, row.timestamp))
        else:
            if before.remote_jid != row.remote_jid:
                row.set_header(RowHeader(
                    row.account, row.remote_jid, row.timestamp))
            elif before.local_timestamp.date() != row.local_timestamp.date():
                row.set_header(RowHeader(
                    row.account, row.remote_jid, row.timestamp))
            else:
                row.set_header(None)

    def _on_hide_clicked(self, _button: Gtk.Button) -> None:
        self.emit('hide-search')
        self._clear()

    def _clear(self) -> None:
        self._ui.search_entry.set_text('')
        self._clear_results()

    def _clear_results(self) -> None:
        # Unset the header_func to reduce load when clearing
        self._ui.results_listbox.set_header_func(None)

        for row in self._ui.results_listbox.get_children():
            self._ui.results_listbox.remove(row)
            row.destroy()

        self._ui.results_listbox.set_header_func(self._header_func)
        self._ui.results_scrolled.get_vadjustment().set_value(0)

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
                before_filters = min(dt.datetime.fromisoformat(date) for
                                     date in before_filters)
            except ValueError:
                self._ui.date_hint.show()
                return

        # after:date
        text, after_filters = self._strip_filters(text, 'after')
        if after_filters is not None:
            try:
                after_filters = min(dt.datetime.fromisoformat(date) for
                                    date in after_filters)
                # if only the day is specified, we want to look after the
                # end of that day.
                # if precision is increased,we do want to look during the
                # day as well.
                if after_filters.hour == after_filters.minute == 0:
                    after_filters += dt.timedelta(days=1)
            except ValueError:
                self._ui.date_hint.show()
                return

        everywhere = self._ui.search_checkbutton.get_active()
        context = self._account is not None and self._jid is not None
        if not context:
            # Started search without context -> show in UI
            self._ui.search_checkbutton.set_active(True)

        if not context or everywhere:
            account = None
            jid = None
        else:
            account = self._account
            jid = self._jid

        self._results_iterator = app.storage.archive.search_archive(
                account,
                jid,
                text,
                from_users=from_filters,
                before=before_filters,
                after=after_filters)

        self._add_results()

    @staticmethod
    def _strip_filters(text: str,
                       filter_name: str) -> tuple[str, list[str] | None]:
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
        assert self._results_iterator is not None
        for db_row in itertools.islice(self._results_iterator, 25):
            result_row = ResultRow(db_row)
            self._ui.results_listbox.add(result_row)

    def _on_edge_reached(self,
                         _scrolledwin: Gtk.ScrolledWindow,
                         pos: Gtk.PositionType) -> None:
        if pos != Gtk.PositionType.BOTTOM:
            return

        self._add_results()

    def _on_calender_button_clicked(self, menu_button: Gtk.MenuButton) -> None:
        if menu_button.get_active():
            self._update_calendar()

    def _update_calendar(self) -> None:
        self._ui.calendar.clear_marks()

        assert self._jid is not None
        assert self._account is not None

        first_log = app.storage.archive.get_first_message_ts(
            self._account, self._jid)
        if first_log is None:
            return
        self._first_date = first_log.astimezone()
        last_log = app.storage.archive.get_last_message_ts(
            self._account, self._jid)
        if last_log is None:
            return
        self._last_date = last_log.astimezone()
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

        assert self._jid is not None
        assert self._account is not None

        history_days = app.storage.archive.get_days_containing_messages(
            self._account, self._jid, year, month)
        for day in history_days:
            calendar.mark_day(day)

    def _on_date_selected(self, calendar: Gtk.Calendar) -> None:
        year, month, day = calendar.get_date()
        py_m = python_month(month)
        date = dt.datetime(year, py_m, day)
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
        delta = dt.timedelta(days=-1)
        assert self._first_date is not None
        self._select_date(delta, self._first_date.date(), Direction.NEXT)

    def _on_next_date_selected(self, _button: Gtk.Button) -> None:
        delta = dt.timedelta(days=1)
        assert self._last_date is not None
        self._select_date(delta, self._last_date.date(), Direction.PREV)

    def _select_date(self,
                     delta: dt.timedelta,
                     end_date: dt.date,
                     direction: Direction
                     ) -> None:
        # Iterate through days until history entry found or
        # supplied end_date (first_date/last_date) reached

        year, month, day = self._ui.calendar.get_date()
        py_m = python_month(month)
        date = dt.date(year, py_m, day)

        assert self._jid is not None
        assert self._account is not None

        day_has_messages = False
        while not day_has_messages:
            if direction == Direction.PREV:
                if end_date <= date:
                    return
            else:
                if end_date >= date:
                    return

            date = date + delta
            if date == end_date:
                break
            day_has_messages = self._ui.calendar.get_day_is_marked(date.day)

        gtk_m = gtk_month(date.month)
        if gtk_m != month or date.year != year:
            # Select month only if it's a different one
            self._ui.calendar.select_month(gtk_m, date.year)

        self._ui.calendar.select_day(date.day)

    def _scroll_to_date(self, date: dt.datetime) -> None:
        control = app.window.get_control()
        if not control.has_active_chat():
            return
        if control.contact.jid == self._jid:

            assert self._jid is not None
            assert self._account is not None

            meta = app.storage.archive.get_first_message_meta_for_date(
                self._account, self._jid, date)
            if meta is None:
                return

            control.scroll_to_message(*meta)

    @staticmethod
    def _on_row_activated(_listbox: SearchView, row: ResultRow) -> None:
        control = app.window.get_control()
        if control.has_active_chat():
            if control.contact.jid == row.remote_jid:
                control.scroll_to_message(row.pk, row.timestamp)
                return

        # Other chat or no control opened
        jid = row.remote_jid
        chat_type = 'chat'
        if row.type == MessageType.GROUPCHAT:
            chat_type = 'groupchat'
        elif row.type == MessageType.PM:
            chat_type = 'pm'
        app.window.add_chat(row.account, jid, chat_type, select=True)
        control = app.window.get_control()
        if control.has_active_chat():
            control.scroll_to_message(row.pk, row.timestamp)

    def set_focus(self) -> None:
        self._ui.search_entry.grab_focus()
        self._clear()

    def set_context(self, account: str | None, jid: JID | None) -> None:
        self._account = account
        self._jid = jid

        if self._account is None and self._jid is None:
            self._ui.calendar_button.set_sensitive(False)
            return

        self._ui.calendar_button.set_sensitive(True)


class RowHeader(Gtk.Box):
    def __init__(self, account: str, jid: JID, timestamp: dt.datetime) -> None:
        Gtk.Box.__init__(self)
        self.set_hexpand(True)

        self._ui = get_builder('search_view.ui')
        self.add(self._ui.header_box)

        client = app.get_client(account)
        contact = client.get_module('Contacts').get_contact(jid)
        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant)
        self._ui.header_name_label.set_text(contact.name or '')

        local_timestamp = timestamp.astimezone()

        format_string = app.settings.get('time_format')
        if local_timestamp.date() <= dt.datetime.today().date():
            format_string = app.settings.get('date_format')
        self._ui.header_date_label.set_text(local_timestamp.strftime(format_string))

        self.show_all()


class ResultRow(Gtk.ListBoxRow):
    def __init__(self, db_row: Message) -> None:
        Gtk.ListBoxRow.__init__(self)

        self._client = self._get_client(str(db_row.account.jid))
        self.account = self._client.account

        self.remote_jid = db_row.remote.jid
        self.direction = ChatDirection(db_row.direction)

        jid = db_row.remote.jid
        if (db_row.direction == ChatDirection.OUTGOING):
            jid = JID.from_string(self._client.get_own_jid().bare)

        self.pk = db_row.pk
        self.timestamp = db_row.timestamp
        self.local_timestamp = db_row.timestamp.astimezone()

        self.type = MessageType(db_row.type)

        self.contact = self._client.get_module('Contacts').get_contact(
            jid, groupchat=self.type == MessageType.GROUPCHAT)
        assert isinstance(
            self.contact,
            BareContact | GroupchatContact | GroupchatParticipant)

        self.get_style_context().add_class('search-view-row')
        self._ui = get_builder('search_view.ui')
        self.add(self._ui.result_row_grid)

        contact_name = self.contact.name
        if self.type == MessageType.GROUPCHAT:
            contact_name = db_row.resource or self.remote_jid.localpart
            assert contact_name is not None

        self._ui.row_name_label.set_text(contact_name)

        avatar = self._get_avatar(self.direction, contact_name)
        self._ui.row_avatar.set_from_surface(avatar)

        format_string = app.settings.get('time_format')
        self._ui.row_time_label.set_text(
            self.local_timestamp.strftime(format_string))

        text = db_row.text
        if db_row.corrections:
            text = db_row.get_last_correction().text

        assert text is not None

        message_widget = MessageWidget(self.account, selectable=False)
        message_widget.add_with_styling(text, nickname=contact_name)
        self._ui.result_row_grid.attach(message_widget, 1, 1, 2, 1)

        self.show_all()

    def _get_client(self, account_jid: str) -> Client:
        for client in app.get_clients():
            if client.is_own_jid(account_jid):
                return client

        raise ValueError('Unable to find account: %s' % account_jid)

    def _get_avatar(self,
                    direction: ChatDirection,
                    name: str) -> cairo.ImageSurface | None:

        scale = self.get_scale_factor()
        if isinstance(self.contact, GroupchatContact):
            contact = self.contact.get_resource(name)
            return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

        if direction == ChatDirection.OUTGOING:
            contact = self._client.get_module('Contacts').get_contact(
                self._client.get_own_jid().bare)
        else:
            contact = self.contact

        assert not isinstance(contact, GroupchatContact | ResourceContact)
        return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)
