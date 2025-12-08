# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import dataclasses
import logging
from collections.abc import Sequence

from gi.repository import Gio
from gi.repository import GLib

from gajim.common.dbus.base import DBusService

GetGroupPropertiesT = list[tuple[int, dict[str, GLib.Variant]]]

MENU_NODE_INFO = Gio.DBusNodeInfo.new_for_xml(
    """
<?xml version="1.0" encoding="UTF-8"?>
<node>
    <interface name="com.canonical.dbusmenu">
        <property name="Version" type="u" access="read" />
        <property name="TextDirection" type="s" access="read" />
        <property name="Status" type="s" access="read" />
        <property name="IconThemePath" type="as" access="read" />
        <method name="GetLayout">
            <arg type="i" name="parentId" direction="in" />
            <arg type="i" name="recursionDepth" direction="in" />
            <arg type="as" name="propertyNames" direction="in"  />
            <arg type="u" name="revision" direction="out" />
            <arg type="(ia{sv}av)" name="layout" direction="out" />
        </method>
        <method name="GetGroupProperties">
            <arg type="ai" name="ids" direction="in"/>
            <arg type="as" name="propertyNames" direction="in" />
            <arg type="a(ia{sv})" name="properties" direction="out" />
        </method>
        <method name="GetProperty">
            <arg type="i" name="id" direction="in" />
            <arg type="s" name="name" direction="in" />
            <arg type="v" name="value" direction="out" />
        </method>
        <method name="Event">
            <arg type="i" name="id" direction="in" />
            <arg type="s" name="eventId" direction="in" />
            <arg type="v" name="data" direction="in" />
            <arg type="u" name="timestamp" direction="in" />
        </method>
        <method name="EventGroup">
            <arg type="a(isvu)" name="events" direction="in" />
            <arg type="ai" name="idErrors" direction="out" />
        </method>
        <method name="AboutToShow">
            <arg type="i" name="id" direction="in" />
            <arg type="b" name="needUpdate" direction="out" />
        </method>
        <method name="AboutToShowGroup">
            <arg type="ai" name="ids" direction="in" />
            <arg type="ai" name="updatesNeeded" direction="out" />
            <arg type="ai" name="idErrors" direction="out" />
        </method>
        <signal name="LayoutUpdated">
            <arg type="u" name="revision" direction="out" />
            <arg type="i" name="parent" direction="out" />
        </signal>
        <signal name="ItemsPropertiesUpdated">
            <arg type="a(ia{sv})" name="updatedProps" direction="out" />
            <arg type="a(ias)" name="removedProps" direction="out" />
        </signal>
    </interface>
</node>"""
).interfaces[0]


PROPERTY_NAMES = [
    "children-display",
    "disposition",
    "enabled",
    "icon-name",
    "label",
    "toggle-state",
    "toggle-type",
    "type",
    "visible",
]


log = logging.getLogger("gajim.c.dbus.dbusmenu")


def get_children_from_parent(
    parent_id: int, items: list[DBusMenuItem]
) -> list[DBusMenuItem] | None:
    for item in items:
        if item.children:
            if item.id == parent_id:
                return item.children

            ret = get_children_from_parent(parent_id, item.children)
            if ret is not None:
                return ret

    return None


def remove_invalid_properties(properties: list[str]) -> list[str]:
    return [p for p in properties if p in PROPERTY_NAMES]


@dataclasses.dataclass
class DBusMenu:
    items: list[DBusMenuItem]

    def get_children(self, parent_id: int) -> list[DBusMenuItem]:
        if parent_id == 0:
            return self.items
        children = get_children_from_parent(parent_id, self.items)
        if children is None:
            return []
        return children

    def serialize(
        self, parent_id: int, recursion_depth: int, property_names: list[str]
    ) -> list[GLib.Variant]:
        children = self.get_children(parent_id)
        return [item.serialize(recursion_depth, property_names) for item in children]


@dataclasses.dataclass
class DBusMenuItem:
    id: int
    label: str = ""
    callback: Any = None
    type: str = "standard"
    disposition = "normal"
    enabled: bool = True
    visible: bool = True
    toggle_type: str = ""
    toggle_state: int = -1
    icon_name: str = ""
    children_display: str = ""
    children: list[DBusMenuItem] | None = None

    def flip_toggle_state(self) -> None:
        if self.toggle_state in (0, -1):
            self.toggle_state = 1
        else:
            self.toggle_state = 0

    def serialize_prop(self, name: str) -> GLib.Variant:
        name = name.replace("-", "_")
        value = getattr(self, name)
        if isinstance(value, str):
            return GLib.Variant("s", value)

        if isinstance(value, bool):
            return GLib.Variant("b", value)

        if isinstance(value, int):
            return GLib.Variant("i", value)

        raise ValueError

    def serialize_props(self, property_names: list[str]) -> dict[str, GLib.Variant]:
        result: dict[str, GLib.Variant] = {}

        if not property_names:
            property_names = PROPERTY_NAMES

        for prop in property_names:
            variant = self.serialize_prop(prop)
            result[prop.replace("_", "-")] = variant

        return result

    def serialize(
        self, recursion_depth: int, property_names: list[str]
    ) -> GLib.Variant:
        props = self.serialize_props(property_names)

        children = []
        if recursion_depth > 1 or recursion_depth == -1:
            if self.children:
                children = [
                    item.serialize(recursion_depth - 1, property_names)
                    for item in self.children
                ]

        return GLib.Variant("(ia{sv}av)", (self.id, props, children))


class DBusMenuService(DBusService):
    Status = "normal"
    IconThemePath = ""
    Version = 3
    TextDirection = "ltr"

    def __init__(
        self, object_path: str, session_bus: Gio.DBusConnection, menu: DBusMenu
    ) -> None:
        super().__init__(
            interface_info=MENU_NODE_INFO, object_path=object_path, bus=session_bus
        )

        self._revision = 0
        self._menu = menu

        self.set_menu(menu)

    def set_menu(self, menu: DBusMenu) -> None:
        self._menu = menu
        self._flat_items = self._get_flat_items(self._menu.items)

        self.LayoutUpdated()

    def _get_flat_items(
        self,
        items: list[DBusMenuItem],
        flat_items: dict[int, DBusMenuItem] | None = None,
    ) -> dict[int, DBusMenuItem]:
        if flat_items is None:
            flat_items = {}

        for item in items:
            flat_items[item.id] = item

            if item.children is not None:
                flat_items = self._get_flat_items(item.children, flat_items)

        return flat_items

    def GetLayout(
        self, parent_id: int, recursion_depth: int, property_names: list[str]
    ) -> tuple[int, tuple[int, dict[str, GLib.Variant], list[GLib.Variant]]]:
        property_names = remove_invalid_properties(property_names)

        children = self._menu.serialize(parent_id, recursion_depth, property_names)

        ret = (
            self._revision,
            (0, {"children-display": GLib.Variant("s", "submenu")}, children),
        )

        return ret

    def GetGroupProperties(
        self, item_ids: Sequence[int], property_names: list[str]
    ) -> tuple[GetGroupPropertiesT]:
        ret: GetGroupPropertiesT = []

        property_names = remove_invalid_properties(property_names)

        if not item_ids:
            # Empty means all items
            item_ids = list(self._flat_items.keys())

        for item_id in item_ids:
            if item_id == 0:
                # Sometimes it requests the parent, but the parent has not properties
                continue

            item = self._flat_items.get(item_id)
            if item is None:
                log.warning("Unknown item id: %s", item_id)
                continue

            ret.append((item.id, item.serialize_props(property_names)))

        return (ret,)

    def GetProperty(self, item_id: int, name: str) -> GLib.Variant | None:
        if name not in PROPERTY_NAMES:
            log.warning("Unsupported property: %s", name)
            return None

        item = self._flat_items.get(item_id)
        if item is None:
            log.warning("Unknown item id: %s", item_id)
            return None

        return item.serialize_prop(name)

    def Event(self, item_id: int, event_id: str, _data: Any, _timestamp: Any) -> None:
        if event_id != "clicked":
            return

        item = self._flat_items.get(item_id)
        if item is None:
            log.warning("Unknown item id %s", item_id)
            return

        if item.callback is not None:
            item.callback()

        if item.toggle_type == "checkmark":
            item.flip_toggle_state()
            self.ItemsPropertiesUpdated(item, "toggle-state")

    def EventGroup(
        self, events: list[tuple[int, str, GLib.Variant, int]]
    ) -> tuple[list[int]]:
        not_found: list[int] = []

        for item_id, event_id, _data, _timestamp in events:
            if event_id != "clicked":
                continue

            item = self._flat_items.get(item_id)
            if item is None:
                not_found.append(item_id)
                continue

            if item.callback is not None:
                item.callback()

            if item.toggle_type == "checkmark":
                item.flip_toggle_state()
                self.ItemsPropertiesUpdated(item, "toggle-state")

        return (not_found,)

    def AboutToShow(self, item_id: int) -> tuple[bool]:
        return (False,)

    def AboutToShowGroup(self, item_ids: list[int]) -> tuple[list[Any], list[int]]:
        not_found: list[int] = []

        for item_id in item_ids:
            if item_id not in self._flat_items:
                not_found.append(item_id)
                continue

        return ([], not_found)

    def LayoutUpdated(self, parent: int = 0) -> None:
        self._revision += 1
        self.emit_signal("LayoutUpdated", (self._revision, parent))

    def ItemsPropertiesUpdated(self, item: DBusMenuItem, property_name: str) -> None:
        updated = [(item.id, {property_name: item.serialize_prop(property_name)})]
        self.emit_signal("ItemsPropertiesUpdated", (updated, []))
