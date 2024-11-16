# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

from gi.repository import Gio
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app

GajimDropDownDataT = dict[str, str] | list[str]


class GajimDropDown(Gtk.DropDown):
    def __init__(
        self,
        data: GajimDropDownDataT | None = None,
        fixed_width: int = -1,
    ) -> None:

        Gtk.DropDown.__init__(self)

        self._kwargs: dict[str, Any] = {
            "width_chars": fixed_width,
            "max_width_chars": fixed_width,
        }

        self._model = Gio.ListStore(item_type=KeyValueItem)
        list_store_expression = Gtk.PropertyExpression.new(
            KeyValueItem,
            None,
            "value",
        )

        self.set_expression(list_store_expression)
        self.set_search_match_mode(Gtk.StringFilterMatchMode.SUBSTRING)
        self.set_model(self._model)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_factory_setup, KeyValueViewItem, self._kwargs)
        factory.connect("bind", self._on_factory_bind)

        self.set_factory(factory)

        factory = Gtk.SignalListItemFactory()
        factory.connect("setup", self._on_factory_setup, KeyValueViewListItem, {})
        factory.connect("bind", self._on_factory_bind)

        self.set_list_factory(factory)

        self.set_data(data)

    @staticmethod
    def _on_factory_setup(
        _factory: Gtk.SignalListItemFactory,
        list_item: Gtk.ListItem,
        view_item: Any,
        kwargs: dict[str, Any],
    ) -> None:
        list_item.set_child(view_item(**kwargs))

    @staticmethod
    def _on_factory_bind(
        _factory: Gtk.SignalListItemFactory, list_item: Gtk.ListItem
    ) -> None:
        view_item = cast(KeyValueViewItem, list_item.get_child())
        obj = cast(KeyValueItem, list_item.get_item())
        view_item.bind(obj)

    def set_data(self, data: GajimDropDownDataT | None) -> None:
        self._model.remove_all()

        if not data:
            return

        items: list[KeyValueItem] = []
        if isinstance(data, dict):
            for key, value in data.items():
                items.append(KeyValueItem(key=key, value=value))

        if isinstance(data, list):
            for entry in data:
                items.append(KeyValueItem(key=entry, value=entry))

        self._model.splice(0, 0, items)

    def select_key(self, key: Any) -> None:
        for pos in range(self._model.get_n_items()):
            item = self._model.get_item(pos)
            assert item is not None
            if item.props.key == key:
                self.set_selected(pos)

    def do_unroot(self) -> None:
        Gtk.DropDown.do_unroot(self)
        self.set_model(None)
        self._model.remove_all()
        app.check_finalize(self._model)
        del self._model
        app.check_finalize(self)


class KeyValueItem(GObject.Object):
    key = GObject.Property(type=object, flags=GObject.ParamFlags.READWRITE)
    value = GObject.Property(type=str, flags=GObject.ParamFlags.READWRITE)


class KeyValueViewItem(Gtk.Label):
    def __init__(self, **kwargs: Any):
        Gtk.Label.__init__(self, ellipsize=Pango.EllipsizeMode.END, xalign=0, **kwargs)

    def bind(self, item: KeyValueItem) -> None:
        self.set_label(item.value)


class KeyValueViewListItem(Gtk.Label):
    def __init__(self, **kwargs: Any):
        Gtk.Label.__init__(self, ellipsize=Pango.EllipsizeMode.END, xalign=0, **kwargs)

    def bind(self, item: KeyValueItem) -> None:
        self.set_label(item.value)
