# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging

from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.client import Client
from gajim.common.modules.contacts import GroupchatContact
from gajim.common.storage.archive.models import Occupant

from gajim.gtk.builder import get_builder
from gajim.gtk.util.classes import SignalManager

log = logging.getLogger("gajim.gtk.groupchat_blocks")


class GroupchatBlocks(Gtk.Box, SignalManager):
    def __init__(self, client: Client, contact: GroupchatContact) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL)
        SignalManager.__init__(self)

        self._client = client
        self._account = contact.account
        self._contact = contact
        self._model = Gio.ListStore(item_type=BlockListItem)

        self._ui = get_builder("groupchat_blocks.ui")
        self.append(self._ui.main)

        for occupant in app.storage.archive.get_blocked_occupants(
            contact.account, contact.jid
        ):
            self._model.append(BlockListItem(occupant))

        columns = [
            (self._ui.nickname_col, BlockViewItemLabel, "nickname"),
            (self._ui.id_col, BlockViewItemLabel, "id"),
        ]

        for col, widget, attr in columns:
            factory = col.get_factory()
            assert factory is not None
            self._connect(factory, "setup", self._on_factory_setup, widget)
            self._connect(factory, "bind", self._on_factory_bind, attr)
            self._connect(factory, "unbind", self._on_factory_unbind)

        expression = Gtk.PropertyExpression.new(
            this_type=BlockListItem,
            expression=None,
            property_name="nickname",
        )
        sorter = Gtk.StringSorter.new(expression=expression)
        sort_model = Gtk.SortListModel(model=self._model, sorter=sorter)

        expression = Gtk.PropertyExpression.new(
            this_type=BlockListItem,
            expression=None,
            property_name="nickname",
        )

        self._string_filter = Gtk.StringFilter.new(expression)

        filter_model = Gtk.FilterListModel(model=sort_model, filter=self._string_filter)

        self._selection_model = Gtk.MultiSelection(model=filter_model)
        self._ui.column_view.set_model(self._selection_model)

        self._connect(self._ui.search_entry, "search-changed", self._on_search_changed)
        self._connect(self._ui.remove_button, "clicked", self._on_remove_button_clicked)

    def _cleanup(self, *args: Any) -> None:
        self._client.disconnect_all_from_obj(self)
        del self._selection_model
        del self._model
        del self._string_filter
        del self._client
        del self._contact

    @staticmethod
    def _on_factory_setup(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, item_class: Any
    ) -> None:
        list_item.set_child(item_class())

    @staticmethod
    def _on_factory_bind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem, attr: str
    ) -> None:
        block_item = cast(BlockListItem, list_item.get_item())
        block_view_item = cast(BlockViewItemLabel, list_item.get_child())
        block_view_item.bind(block_item, attr)

    @staticmethod
    def _on_factory_unbind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        block_view_item = cast(BlockViewItemLabel, list_item.get_child())
        block_view_item.unbind()

    def _remove(self, item: BlockListItem) -> None:
        for index, item_ in enumerate(self._model):
            item_ = cast(BlockListItem, item_)
            if item_.id == item.id:
                self._model.remove(index)
                return

    def _get_selected_items(self) -> list[BlockListItem]:
        bitset = self._selection_model.get_selection()
        valid, iter_, value = Gtk.BitsetIter.init_first(bitset)

        items: list[BlockListItem] = []

        if not valid:
            return items

        items.append(cast(BlockListItem, self._selection_model.get_item(value)))

        while res := iter_.next():
            valid, value = res
            if not valid:
                break

            items.append(cast(BlockListItem, self._selection_model.get_item(value)))

        return items

    def _on_search_changed(self, search_entry: Gtk.SearchEntry) -> None:
        self._string_filter.set_search(search_entry.get_text())

    def _on_remove_button_clicked(self, _button: Gtk.Button) -> None:
        items = self._get_selected_items()
        if not items:
            return

        occupant_ids: list[str] = []
        for item in items:
            occupant_ids.append(item.id)
            self._remove(item)

        self._client.get_module("MucBlocking").set_block_occupants(
            self._contact.jid, occupant_ids, False
        )


class BlockListItem(GObject.Object):
    __gtype_name__ = "BlockListItem"

    id = GObject.Property(type=str)
    nickname = GObject.Property(type=str)

    def __init__(self, occupant: Occupant) -> None:
        super().__init__(
            id=occupant.id,
            nickname=occupant.nickname or "Unknown",
        )

    def __repr__(self) -> str:
        return f"BlockListItem: {self.id} {self.nickname}"


class BlockViewItemLabel(Gtk.Label):
    __gtype_name__ = "BlockViewItemLabel"

    def __init__(self) -> None:
        Gtk.Label.__init__(
            self,
            ellipsize=Pango.EllipsizeMode.END,
            width_chars=20,
            xalign=0,
        )

        self.__bindings: list[GObject.Binding] = []

    def bind(self, obj: BlockListItem, attr: str) -> None:
        bind_spec = [
            (attr, self, "label"),
        ]

        for source_prop, widget, target_prop in bind_spec:
            bind = obj.bind_property(
                source_prop, widget, target_prop, GObject.BindingFlags.SYNC_CREATE
            )
            self.__bindings.append(bind)

    def unbind(self) -> None:
        for bind in self.__bindings:
            bind.unbind()
        self.__bindings.clear()

    def do_unroot(self) -> None:
        Gtk.Label.do_unroot(self)
        app.check_finalize(self)
