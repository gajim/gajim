# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast
from typing import Literal

import locale
from collections.abc import Callable

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Graphene
from gi.repository import Gtk
from nbxmpp import JID

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.const import Direction
from gajim.common.i18n import _
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import GroupchatContact

from gajim.gtk.structs import StartChatParam
from gajim.gtk.util.misc import get_ui_string
from gajim.gtk.util.window import open_window
from gajim.gtk.widgets import AccountBadge

MAX_SEARCH_RESULTS = 15


@Gtk.Template(string=get_ui_string("universal_search.ui"))
class UniversalSearch(Gtk.Box):
    __gtype_name__ = "UniversalSearch"

    _dropdown: Gtk.Box = Gtk.Template.Child()
    _search_hint: Adw.StatusPage = Gtk.Template.Child()
    _results_box: Gtk.Box = Gtk.Template.Child()
    _filter_toggle_group: Adw.ToggleGroup = Gtk.Template.Child()
    _results_listbox: Gtk.ListBox = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.Box.__init__(self)

        # Enabled when starting to hide the dropdown
        self._block_visibility_signals = False

        self._model = Gio.ListStore(item_type=UniversalSearchResultItem)

        self._sorter = Gtk.CustomSorter.new(sort_func=self._sort_func)
        self._sort_model = Gtk.SortListModel(model=self._model, sorter=self._sorter)

        self._custom_filter = Gtk.CustomFilter.new(self._filter_func)
        self._filter_model = Gtk.FilterListModel(
            model=self._sort_model, filter=self._custom_filter
        )
        self._slice_model = Gtk.SliceListModel(
            model=self._filter_model, size=MAX_SEARCH_RESULTS
        )
        self._selection_model = Gtk.SingleSelection(model=self._slice_model)

        self._filter_toggle_group.connect(
            "notify::active",
            self._on_filter_toggle_changed,
        )

        self._results_listbox.connect(
            "row-activated", self._on_result_item_row_activated
        )

        focus_controller = Gtk.EventControllerFocus()
        focus_controller.connect("enter", self._on_search_focus_enter)
        self._search_entry = Gtk.SearchEntry(placeholder_text=_("Search…"))
        self._search_entry.add_controller(focus_controller)
        self._search_entry.connect("search-changed", self._on_search_changed)
        self._search_entry.connect("next-match", self._select_new_match, Direction.NEXT)
        self._search_entry.connect(
            "previous-match", self._select_new_match, Direction.PREV
        )
        self._search_entry.connect("activate", self._on_search_activate)

        gesture_primary_click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        gesture_primary_click.connect("pressed", self._on_button_pressed)
        self.add_controller(gesture_primary_click)

        event_controller_key = Gtk.EventControllerKey(
            propagation_phase=Gtk.PropagationPhase.BUBBLE
        )
        event_controller_key.connect("key-pressed", self._on_search_key_pressed)
        text = self._search_entry.get_delegate()
        assert isinstance(text, Gtk.Text)
        text.add_controller(event_controller_key)

    def get_search_entry(self) -> Gtk.SearchEntry:
        return self._search_entry

    def hide_search(self, block_signals: bool = False) -> bool:
        if self.is_visible():
            self._block_signals(block_signals)
            self._filter_toggle_group.set_active_name("all")
            self._search_entry.set_text("")
            self.set_visible(False)
            app.window.set_focus()
            GLib.timeout_add_seconds(1, self._block_signals, False)
            return True
        return False

    def _block_signals(self, block: bool) -> bool:
        self._block_visibility_signals = block
        return GLib.SOURCE_REMOVE

    def _on_button_pressed(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        """Hide search if click is outside dropdown."""
        if not self.is_visible():
            return

        success, result = self._dropdown.compute_bounds(self)
        if not success:
            return

        point = Graphene.Point().init(x, y)
        if result.contains_point(point):
            return

        self.hide_search()

    def _on_search_focus_enter(
        self, _focus_controller: Gtk.EventControllerFocus
    ) -> None:
        # We set the focus away from the search box while hiding.
        # Focus may come back when selecting a chat.
        if not self.is_visible() and not self._block_visibility_signals:
            self.set_visible(True)
            self._update_data_model()

    @staticmethod
    def _sort_func(
        obj1: Any,
        obj2: Any,
        _user_data: object | None,
    ) -> int:
        item1 = cast(UniversalSearchResultItem, obj1)
        item2 = cast(UniversalSearchResultItem, obj2)
        if item1.item_type == "message_search":
            return -1
        return locale.strcoll(item1.title.lower(), item2.title.lower())

    def _filter_func(self, obj: GObject.Object) -> bool:
        item = cast(UniversalSearchResultItem, obj)
        query = self._search_entry.get_text().strip().lower()
        type_filter = self._filter_toggle_group.get_active_name()
        match type_filter:
            case "actions":
                return query in item.search_string and item.item_type == "action"
            case "contacts":
                return query in item.search_string and item.item_type in (
                    "contact",
                    "group_chat",
                )
            case _:
                return query in item.search_string

    def _row_create_func(self, obj: GObject.Object) -> UniversalSearchResultItemRow:
        item = cast(UniversalSearchResultItem, obj)
        return UniversalSearchResultItemRow(
            item_type=item.item_type,
            title=item.title,
            description=item.description,
            paintable=item.paintable,
            icon_name=item.icon_name,
            account=item.account,
        )

    def _update_data_model(self) -> None:
        accounts = app.get_enabled_accounts_with_labels()

        scale = self.get_scale_factor()
        self._model.remove_all()

        for account, _label in accounts:
            client = app.get_client(account)
            # Contacts
            for jid, _data in client.get_module("Roster").iter():
                contact = client.get_module("Contacts").get_contact(jid)

                if isinstance(contact, GroupchatContact):
                    # Workaround if groupchats are in the roster
                    continue

                assert isinstance(contact, BareContact)
                avatar = contact.get_avatar(size=AvatarSize.START_CHAT, scale=scale)
                item = UniversalSearchResultItem(
                    item_type="contact",
                    search_string=f"{contact.name} {contact.original_name} {contact.jid}".casefold(),
                    title=contact.name,
                    description=str(contact.jid),
                    account=account,
                    jid=contact.jid,
                    paintable=avatar,
                )
                self._model.append(item)

            # Group chats
            bookmarks = client.get_module("Bookmarks").bookmarks
            for bookmark in bookmarks:
                contact = client.get_module("Contacts").get_contact(
                    bookmark.jid, groupchat=True
                )
                assert isinstance(contact, GroupchatContact)
                avatar = contact.get_avatar(size=AvatarSize.START_CHAT, scale=scale)
                item = UniversalSearchResultItem(
                    item_type="group_chat",
                    search_string=f"{contact.name} {contact.original_name} {contact.jid}".casefold(),
                    title=contact.name,
                    description=str(contact.jid),
                    account=account,
                    jid=contact.jid,
                    paintable=avatar,
                )
                self._model.append(item)

            # Actions
            profile_action = UniversalSearchResultItem(
                item_type="action",
                search_string=f"{_('Profile Picture')} {_('Avatar')}".casefold(),
                title=_("Profile"),
                description=_("Edit your contact details…"),
                account=account,
                icon_name="lucide-user-symbolic",
                callback=self._show_profile,
                callback_kwargs={"account": account},
            )
            self._model.append(profile_action)

        self._results_listbox.bind_model(self._selection_model, self._row_create_func)

    def _on_filter_toggle_changed(
        self, _toggle_group: Adw.ToggleGroup, _index: int
    ) -> None:
        self._custom_filter.changed(Gtk.FilterChange.DIFFERENT)

    def _on_search_changed(self, entry: Gtk.SearchEntry) -> None:
        query = entry.get_text().strip().lower()
        self._search_hint.set_visible(not query)
        self._results_box.set_visible(bool(query))

        if self._block_visibility_signals:
            # We reset the search input while hiding. This triggers a delayed change event.
            return

        self.set_visible(True)

        # The message search item needs to be updated with every change in order to
        # reflect the current search query.
        first_item = self._model.get_item(0)
        if first_item is not None and first_item.item_type == "message_search":
            self._model.remove(0)

        message_search_item = UniversalSearchResultItem(
            item_type="message_search",
            search_string=query.casefold(),
            title=_("Search for %s") % f"<b>{query}</b>",
            icon_name="lucide-search-symbolic",
        )
        self._model.insert(0, message_search_item)
        self._select_row(0)

        self._custom_filter.changed(Gtk.FilterChange.DIFFERENT)

    def _on_search_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        if keyval == Gdk.KEY_Down:
            self._search_entry.emit("next-match")
            return Gdk.EVENT_STOP

        if keyval == Gdk.KEY_Up:
            self._search_entry.emit("previous-match")
            return Gdk.EVENT_STOP

        return Gdk.EVENT_PROPAGATE

    def _select_new_match(self, _entry: Gtk.Entry, direction: Direction) -> None:
        selected_position = self._selection_model.get_selected()
        if selected_position == Gtk.INVALID_LIST_POSITION:
            return

        if direction == Direction.NEXT:
            selected_position += 1
        else:
            selected_position -= 1

        if not 0 <= selected_position < self._selection_model.get_n_items():
            return

        self._select_row(selected_position)

    def _select_row(self, position: int) -> None:
        self._selection_model.select_item(position, True)
        row = self._results_listbox.get_row_at_index(position)
        if row is not None:
            self._results_listbox.select_row(row)
            self._scroll_row_into_view(row)

    def _scroll_row_into_view(self, row: Gtk.ListBoxRow) -> None:
        """Scroll ListBox to row without giving it focus."""
        coordinates = row.translate_coordinates(self._results_listbox, 0, 0)
        if coordinates is None:
            return

        _x_coord, y_coord = coordinates
        _minimum_site, natural_size = row.get_preferred_size()
        adjustment = self._results_listbox.get_adjustment()
        assert adjustment is not None
        adjustment.set_value(
            y_coord - (adjustment.get_page_size() - natural_size.height) / 2
        )

    def _on_search_activate(self, _search_entry: Gtk.SearchEntry) -> None:
        item = cast(
            UniversalSearchResultItem, self._selection_model.get_selected_item()
        )
        self._on_item_activated(item)

    def _on_result_item_row_activated(
        self,
        _listbox: Gtk.ListBox,
        row: UniversalSearchResultItemRow,
    ) -> None:
        position = row.get_index()
        item = cast(UniversalSearchResultItem, self._selection_model.get_item(position))
        self._on_item_activated(item)

    def _on_item_activated(self, item: UniversalSearchResultItem) -> None:
        self.hide_search(block_signals=True)

        if item.account is not None and item.jid is not None:
            self._start_chat(item.account, item.jid)
            return

        if item.item_type == "action":
            item.callback(**item.callback_kwargs)
            return

        print(item.search_string)

    def _start_chat(self, account: str, jid: JID) -> None:
        app.window.start_chat_from_jid(StartChatParam(account=account, jid=jid))

    def _show_profile(self, account: str) -> None:
        open_window("ProfileWindow", account=account)


UniversalSearchResultItemType = Literal[
    "contact", "group_chat", "message_search", "action"
]


class UniversalSearchResultItem(GObject.Object):
    __gtype_name__ = "UniversalSearchResultItem"

    item_type = GObject.Property(type=str)
    search_string = GObject.Property(type=str)
    title = GObject.Property(type=str)
    description = GObject.Property(type=str, default=None)
    account = GObject.Property(type=str, default=None)
    jid = GObject.Property(type=str, default=None)
    paintable = GObject.Property(type=Gdk.Paintable, default=None)
    icon_name = GObject.Property(type=str, default=None)
    callback = GObject.Property(type=object, default=None)
    callback_kwargs = GObject.Property(type=object, default=None)

    def __init__(
        self,
        item_type: UniversalSearchResultItemType,
        search_string: str,
        title: str,
        description: str | None = None,
        account: str | None = None,
        jid: JID | None = None,
        paintable: Gdk.Paintable | None = None,
        icon_name: str | None = None,
        callback: Callable[..., Any] | None = None,
        callback_kwargs: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(
            item_type=item_type,
            search_string=search_string,
            title=title,
            description=description,
            account=account,
            jid=jid,
            paintable=paintable,
            icon_name=icon_name,
            callback=callback,
            callback_kwargs=callback_kwargs,
        )


@Gtk.Template(string=get_ui_string("universal_search_result_item_row.ui"))
class UniversalSearchResultItemRow(Gtk.ListBoxRow):
    __gtype_name__ = "UniversalSearchResultItemRow"

    _image: Gtk.Image = Gtk.Template.Child()
    _title: Gtk.Label = Gtk.Template.Child()
    _description: Gtk.Label = Gtk.Template.Child()
    _account_badge: AccountBadge = Gtk.Template.Child()

    def __init__(
        self,
        item_type: UniversalSearchResultItemType,
        title: str,
        description: str | None = None,
        paintable: Gdk.Paintable | None = None,
        icon_name: str | None = None,
        account: str | None = None,
    ) -> None:
        Gtk.ListBoxRow.__init__(self)

        if paintable is not None:
            self._image.set_from_paintable(paintable)
        if icon_name is not None:
            self._image.set_from_icon_name(icon_name)
            self._image.add_css_class("dimmed")

        if item_type == "message_search":
            self._title.set_markup(title)
        else:
            self._title.set_text(title)
            self._title.add_css_class("bold")

        if description is not None:
            self._description.set_text(description)
            self._description.set_visible(True)

        accounts = app.get_enabled_accounts_with_labels(connected_only=True)
        if account is not None and len(accounts) > 1:
            self._account_badge.set_account(account)
            self._account_badge.set_visible(True)
