# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import datetime as dt
import itertools
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common import ged
from gajim.common.client import Client
from gajim.common.const import AvatarSize
from gajim.common.const import Direction
from gajim.common.ged import EventHelper
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.modules.contacts import GroupchatParticipant
from gajim.common.modules.contacts import ResourceContact
from gajim.common.storage.archive.const import ChatDirection
from gajim.common.storage.archive.const import MessageType
from gajim.common.storage.archive.models import Message

from gajim.gtk.builder import get_builder
from gajim.gtk.conversation.message_widget import MessageWidget
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import convert_py_to_glib_datetime

log = logging.getLogger("gajim.gtk.search_view")


class PlaceholderMode(Enum):
    INITIAL = "initial"
    SEARCHING = "searching"
    NO_RESULTS = "no_results"


class SearchView(Gtk.Box, SignalManager, EventHelper):
    __gtype_name__ = "SearchView"

    __gsignals__ = {
        "hide-search": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self) -> None:
        Gtk.Box.__init__(self, width_request=300)
        SignalManager.__init__(self)
        EventHelper.__init__(self)

        self._account: str | None = None
        self._jid: JID | None = None
        self._results_iterator: Iterator[Message] | None = None

        self._first_date: dt.datetime | None = None
        self._last_date: dt.datetime | None = None

        self._last_search_string = ""

        self._ui = get_builder("search_view.ui", ["search_box"])
        self._ui.results_listbox.set_header_func(self._header_func)
        self.append(self._ui.search_box)

        self._search_filters = SearchFilters()
        self._connect(
            self._search_filters, "filter-changed", self._on_search_filters_changed
        )
        self._connect(
            self._search_filters, "filter-activated", self._on_search_filters_activated
        )
        self._ui.search_filters_box.append(self._search_filters)

        self.register_events(
            [
                ("account-enabled", ged.GUI1, self._on_account_state),
                ("account-disabled", ged.GUI1, self._on_account_state),
            ]
        )

        self._connect(self._ui.calendar, "day-selected", self._on_date_selected)
        self._connect(self._ui.calendar, "notify::month", self._on_month_changed)
        self._connect(self._ui.calendar, "notify::year", self._on_month_changed)

        self._connect(
            self._ui.calendar_button, "notify::active", self._on_calender_button_clicked
        )
        self._connect(
            self._ui.first_day_button, "clicked", self._on_first_date_selected
        )
        self._connect(
            self._ui.previous_day_button, "clicked", self._on_previous_date_selected
        )
        self._connect(self._ui.next_day_button, "clicked", self._on_next_date_selected)
        self._connect(self._ui.last_day_button, "clicked", self._on_last_date_selected)
        self._connect(self._ui.close_button, "clicked", self._on_hide_clicked)
        self._connect(self._ui.search_entry, "activate", self._on_search)
        self._connect(
            self._ui.search_checkbutton, "toggled", self._on_search_all_toggled
        )
        self._connect(self._ui.results_scrolled, "edge-reached", self._on_edge_reached)
        self._connect(self._ui.results_listbox, "row-activated", self._on_row_activated)

    def do_unroot(self) -> None:
        self._disconnect_all()
        self.unregister_events()
        app.check_finalize(self)

    def _on_account_state(self, _event: Any) -> None:
        self._clear()

    @staticmethod
    def _header_func(row: ResultRow, before: ResultRow | None) -> None:
        if before is None:
            row.set_header(RowHeader(row.account, row.remote_jid, row.timestamp))
        else:
            if before.remote_jid != row.remote_jid:
                row.set_header(RowHeader(row.account, row.remote_jid, row.timestamp))
            elif before.local_timestamp.date() != row.local_timestamp.date():
                row.set_header(RowHeader(row.account, row.remote_jid, row.timestamp))
            else:
                row.set_header(None)

    def _on_hide_clicked(self, _button: Gtk.Button) -> None:
        self.emit("hide-search")
        self._clear()

    def _clear(self) -> None:
        self._last_search_string = ""
        self._ui.search_entry.set_text("")
        self._search_filters.reset()
        self._clear_results()

    def _clear_results(self) -> None:
        # Unset the header_func to reduce load when clearing
        self._ui.results_listbox.set_header_func(None)

        self._ui.results_listbox.remove_all()
        # Set placeholder again, otherwise it won't be shown
        self._ui.results_listbox.set_placeholder(self._ui.placeholder)

        self._ui.results_listbox.set_header_func(self._header_func)
        self._ui.results_scrolled.get_vadjustment().set_value(0)

        self._set_placeholder_mode(PlaceholderMode.INITIAL)

    def _on_search_all_toggled(self, _checkbutton: Gtk.CheckButton) -> None:
        # Reset state to allow changing scope while not changing search string
        self._last_search_string = ""

    def _on_search_filters_changed(self, _search_filters: SearchFilters) -> None:
        # Reset search string to allow new searches after changed filters
        self._last_search_string = ""

    def _on_search_filters_activated(self, _search_filters: SearchFilters) -> None:
        self._ui.search_entry.activate()

    def _on_search(self, entry: Gtk.Entry) -> None:
        text = entry.get_text()
        if text == self._last_search_string:
            # Return early if search string did not change
            # (prevents burst of db queries when holding enter).
            return

        self._last_search_string = text

        self._clear_results()
        if not text:
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

        search_filter = self._search_filters.get_filters()

        self._set_placeholder_mode(PlaceholderMode.SEARCHING)
        self._results_iterator = app.storage.archive.search_archive(
            account,
            jid,
            text,
            from_users=search_filter.usernames,
            before=search_filter.before,
            after=search_filter.after,
        )

        self._add_results()

    def _set_placeholder_mode(self, placeholder_mode: PlaceholderMode) -> None:
        self._ui.placeholder_image.remove_css_class("spin")

        if placeholder_mode == PlaceholderMode.SEARCHING:
            self._ui.placeholder_image.add_css_class("spin")
            icon_name = "view-refresh-symbolic"
            text = _("Searching…")

        elif placeholder_mode == PlaceholderMode.NO_RESULTS:
            icon_name = "action-unavailable-symbolic"
            text = _("No results")
        else:
            # PlaceholderMode.INITIAL
            icon_name = "system-search-symbolic"
            text = _("Search your conversation")

        self._ui.placeholder_image.set_from_icon_name(icon_name)
        self._ui.placeholder_label.set_text(text)

    def _add_results(self) -> None:
        assert self._results_iterator is not None
        has_results = False
        for message in itertools.islice(self._results_iterator, 25):

            # With the current database design for corrections, we found
            # no way of only searching within the last correction of a
            # message so the search can return the original message, the
            # last correction or any in between correction.

            if message.get_last_correction() is not None:
                # This is only true for original messages which have
                # corrections, dont show them because they are obsolete
                continue

            if message.correction_id:
                # This is only true for the correction of a message.
                # We need to find out if this correction is obsolete by
                # checking if this correction is the last correction

                original_message = app.storage.archive.get_corrected_message(message)
                if original_message is None:
                    continue

                last_correction = original_message.get_last_correction()
                assert last_correction is not None
                if message.pk != last_correction.pk:
                    # This was a search hit on a correction which is not
                    # the last correction available, so ignore it
                    continue

            result_row = ResultRow(message)
            self._ui.results_listbox.append(result_row)
            has_results = True

        if not has_results:
            self._set_placeholder_mode(PlaceholderMode.NO_RESULTS)

    def _on_edge_reached(
        self, _scrolledwin: Gtk.ScrolledWindow, pos: Gtk.PositionType
    ) -> None:
        if pos != Gtk.PositionType.BOTTOM:
            return

        self._add_results()

    def _on_calender_button_clicked(
        self, menu_button: Gtk.MenuButton, *args: Any
    ) -> None:
        if menu_button.get_active():
            self._update_calendar()

    def _update_calendar(self) -> None:
        assert self._jid is not None
        assert self._account is not None

        first_log = app.storage.archive.get_first_message_ts(self._account, self._jid)
        if first_log is None:
            return
        self._first_date = first_log.astimezone()
        last_log = app.storage.archive.get_last_message_ts(self._account, self._jid)
        if last_log is None:
            return
        self._last_date = last_log.astimezone()

        self._ui.calendar.select_day(convert_py_to_glib_datetime(self._last_date))
        self._update_marks()

    def _on_month_changed(self, _calendar: Gtk.Calendar, *args: Any) -> None:
        self._update_marks()

    def _on_year_changed(self, _calendar: Gtk.Calendar, *args: Any) -> None:
        self._update_marks()

    def _update_marks(self) -> None:
        # Mark days with history in calendar
        date_time = self._ui.calendar.get_date()
        if date_time.get_year() < 1900:
            new_date_time = GLib.DateTime.new_from_iso8601("1900-01-01T00:00:00Z")
            assert new_date_time
            self._ui.calendar.select_day(new_date_time)
            return

        self._ui.calendar.clear_marks()

        assert self._jid is not None
        assert self._account is not None

        history_days = app.storage.archive.get_days_containing_messages(
            self._account, self._jid, date_time.get_year(), date_time.get_month()
        )
        for day in history_days:
            self._ui.calendar.mark_day(day)

    def _on_date_selected(self, calendar: Gtk.Calendar) -> None:
        date_time = calendar.get_date()
        date = dt.datetime(*date_time.get_ymd())
        self._scroll_to_date(date)

    def _on_first_date_selected(self, _button: Gtk.Button) -> None:
        assert self._first_date is not None
        self._ui.calendar.select_day(convert_py_to_glib_datetime(self._first_date))

    def _on_last_date_selected(self, _button: Gtk.Button) -> None:
        assert self._last_date is not None
        self._ui.calendar.select_day(convert_py_to_glib_datetime(self._last_date))

    def _on_previous_date_selected(self, _button: Gtk.Button) -> None:
        delta = dt.timedelta(days=-1)
        assert self._first_date is not None
        self._select_date(delta, self._first_date.date(), Direction.NEXT)

    def _on_next_date_selected(self, _button: Gtk.Button) -> None:
        delta = dt.timedelta(days=1)
        assert self._last_date is not None
        self._select_date(delta, self._last_date.date(), Direction.PREV)

    def _select_date(
        self, delta: dt.timedelta, end_date: dt.date, direction: Direction
    ) -> None:
        # Iterate through days until history entry found or
        # supplied end_date (first_date/last_date) reached

        g_datetime = self._ui.calendar.get_date()
        date = dt.date(*g_datetime.get_ymd())

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

        self._ui.calendar.select_day(convert_py_to_glib_datetime(date))

    def _scroll_to_date(self, date: dt.datetime) -> None:
        control = app.window.get_control()
        if not control.has_active_chat():
            return
        if control.contact.jid == self._jid:

            assert self._jid is not None
            assert self._account is not None

            meta = app.storage.archive.get_first_message_meta_for_date(
                self._account, self._jid, date
            )
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
        chat_type = "chat"
        if row.type == MessageType.GROUPCHAT:
            chat_type = "groupchat"
        elif row.type == MessageType.PM:
            chat_type = "pm"
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
        self._last_search_string = ""

        self._search_filters.set_context(account, jid)

        if self._account is None and self._jid is None:
            self._ui.calendar_button.set_sensitive(False)
            return

        self._ui.calendar_button.set_sensitive(True)


class RowHeader(Gtk.Box):
    def __init__(self, account: str, jid: JID, timestamp: dt.datetime) -> None:
        Gtk.Box.__init__(self)
        self.set_hexpand(True)

        self._ui = get_builder("search_view.ui", ["header_box"])
        self.append(self._ui.header_box)

        client = app.get_client(account)
        contact = client.get_module("Contacts").get_contact(jid)
        assert isinstance(
            contact, BareContact | GroupchatContact | GroupchatParticipant
        )
        self._ui.header_name_label.set_text(contact.name or "")

        local_timestamp = timestamp.astimezone()

        format_string = app.settings.get("time_format")
        if local_timestamp.date() <= dt.datetime.today().date():
            format_string = app.settings.get("date_format")
        self._ui.header_date_label.set_text(local_timestamp.strftime(format_string))


class ResultRow(Gtk.ListBoxRow):
    def __init__(self, db_row: Message) -> None:
        Gtk.ListBoxRow.__init__(self)

        self._client = self._get_client(str(db_row.account.jid))
        self.account = self._client.account

        self.remote_jid = db_row.remote.jid
        self.direction = ChatDirection(db_row.direction)

        jid = db_row.remote.jid
        if db_row.direction == ChatDirection.OUTGOING:
            jid = JID.from_string(self._client.get_own_jid().bare)

        self.pk = db_row.pk
        self.timestamp = db_row.timestamp
        self.local_timestamp = db_row.timestamp.astimezone()

        self.type = MessageType(db_row.type)

        self.contact = self._client.get_module("Contacts").get_contact(
            jid, groupchat=self.type == MessageType.GROUPCHAT
        )
        assert isinstance(
            self.contact, BareContact | GroupchatContact | GroupchatParticipant
        )

        self.add_css_class("search-view-row")
        self.add_css_class("opacity-0")

        self._ui = get_builder("search_view.ui", ["result_row_grid"])
        self.set_child(self._ui.result_row_grid)

        contact_name = self.contact.name
        if self.type == MessageType.GROUPCHAT:
            contact_name = db_row.resource or self.remote_jid.localpart
            assert contact_name is not None

        self._ui.row_name_label.set_text(contact_name)

        avatar = self._get_avatar(self.direction, contact_name)
        self._ui.row_avatar.set_pixel_size(AvatarSize.ROSTER)
        self._ui.row_avatar.set_from_paintable(avatar)

        format_string = app.settings.get("time_format")
        self._ui.row_time_label.set_text(self.local_timestamp.strftime(format_string))

        text = db_row.text
        assert text is not None

        message_widget = MessageWidget(self.account, selectable=False)
        message_widget.add_with_styling(text, nickname=contact_name)
        self._ui.result_row_grid.attach(message_widget, 1, 1, 2, 1)

        GLib.timeout_add(100, self.remove_css_class, "opacity-0")

    def do_unroot(self) -> None:
        Gtk.ListBoxRow.do_unroot(self)
        app.check_finalize(self)

    def _get_client(self, account_jid: str) -> Client:
        for client in app.get_clients():
            if client.is_own_jid(account_jid):
                return client

        raise ValueError("Unable to find account: %s" % account_jid)

    def _get_avatar(self, direction: ChatDirection, name: str) -> Gdk.Texture | None:

        scale = self.get_scale_factor()
        if isinstance(self.contact, GroupchatContact):
            contact = self.contact.get_resource(name)
            return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)

        if direction == ChatDirection.OUTGOING:
            contact = self._client.get_module("Contacts").get_contact(
                self._client.get_own_jid().bare
            )
        else:
            contact = self.contact

        assert not isinstance(contact, GroupchatContact | ResourceContact)
        return contact.get_avatar(AvatarSize.ROSTER, scale, add_show=False)


@dataclass
class SearchFilterData:
    usernames: list[str] | None
    before: dt.datetime | None
    after: dt.datetime | None


class SearchFilters(Gtk.Expander, SignalManager):

    __gsignals__ = {
        "filter-changed": (GObject.SignalFlags.RUN_LAST, None, ()),
        "filter-activated": (
            GObject.SignalFlags.RUN_LAST,
            None,
            (),
        ),
    }

    def __init__(self) -> None:
        Gtk.Expander.__init__(self, label=_("Search Filters"))
        SignalManager.__init__(self)

        self._after: dt.datetime | None = None
        self._before: dt.datetime | None = None

        self._ui = get_builder(
            "search_view.ui", ["filter_date_selector_popover", "search_filters_grid"]
        )
        self.set_child(self._ui.search_filters_grid)

        self._connect(
            self._ui.filter_from_entry, "changed", self._on_filter_from_changed
        )
        self._connect(
            self._ui.filter_from_entry, "activate", self._on_from_entry_activated
        )
        self._connect(
            self._ui.filter_date_before_calendar, "day-selected", self._on_date_selected
        )
        self._connect(
            self._ui.filter_date_after_calendar, "day-selected", self._on_date_selected
        )

        self._connect(
            self._ui.filter_date_before_reset_button,
            "clicked",
            self._on_date_reset_clicked,
        )
        self._connect(
            self._ui.filter_date_after_reset_button,
            "clicked",
            self._on_date_reset_clicked,
        )

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Expander.do_unroot(self)
        app.check_finalize(self)

    def _on_filter_from_changed(self, _entry: Gtk.Entry) -> None:
        self._update_state()

    def _on_from_entry_activated(self, _entry: Gtk.Entry) -> None:
        self.emit("filter-activated")

    def _on_date_selected(self, calendar: Gtk.Calendar) -> None:
        g_datetime = calendar.get_date()
        datetime = dt.datetime(*g_datetime.get_ymd(), tzinfo=dt.UTC)
        date_format = app.settings.get("date_format")

        if self._ui.filter_before_button.get_active():
            self._before = datetime
            self._ui.filter_before_label.set_text(datetime.strftime(date_format))

        elif self._ui.filter_after_button.get_active():
            self._after = datetime
            self._ui.filter_after_label.set_text(datetime.strftime(date_format))

        else:
            raise ValueError

        self._update_state()
        self.emit("filter-activated")

    def _on_date_reset_clicked(self, _button: Gtk.Button) -> None:
        if self._ui.filter_before_button.get_active():
            self._before = None
            self._ui.filter_before_label.set_text("-")
            self._ui.filter_date_before_popover.popdown()

        elif self._ui.filter_after_button.get_active():
            self._after = None
            self._ui.filter_after_label.set_text("-")
            self._ui.filter_date_after_popover.popdown()

        else:
            raise ValueError

        self._update_state()
        self.emit("filter-activated")

    def _update_state(self) -> None:
        from_filter = self._ui.filter_from_entry.get_text()

        if any((from_filter, self._before, self._after)):
            self.set_label(_("Search Filters (Active)"))
        else:
            self.set_label(_("Search Filters"))

        self.emit("filter-changed")

    def reset(self) -> None:
        self._before = None
        self._after = None

        self._ui.filter_before_label.set_text("-")
        self._ui.filter_after_label.set_text("-")

        self._ui.filter_from_entry.set_text("")

        self.set_label(_("Search Filters"))

    def set_context(self, account: str | None, jid: JID | None) -> None:
        if account is None or jid is None:
            self._ui.filter_from_desc_label.set_visible(False)
            self._ui.filter_from_entry.set_visible(False)
            return

        client = app.get_client(account)
        contact = client.get_module("Contacts").get_contact(jid)
        visible = not isinstance(contact, BareContact)
        self._ui.filter_from_desc_label.set_visible(visible)
        self._ui.filter_from_entry.set_visible(visible)

    def get_filters(self) -> SearchFilterData:
        usernames: list[str] = []
        username = self._ui.filter_from_entry.get_text() or None
        if username is not None:
            usernames.append(username)

        return SearchFilterData(
            usernames=usernames or None,
            before=self._before,
            after=self._after,
        )
