# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import logging
from collections.abc import Callable

from gi.repository import Gio

from gajim.common.dbus.base import DBusService
from gajim.common.dbus.menu import DBusMenu
from gajim.common.dbus.menu import DBusMenuService

SNI_NODE_INFO = Gio.DBusNodeInfo.new_for_xml(
    """
<?xml version="1.0" encoding="UTF-8"?>
<node>
    <interface name="org.kde.StatusNotifierItem">
        <property name="Category" type="s" access="read"/>
        <property name="Id" type="s" access="read"/>
        <property name="Title" type="s" access="read"/>
        <property name="ToolTip" type="(sa(iiay)ss)" access="read"/>
        <property name="Menu" type="o" access="read"/>
        <property name="ItemIsMenu" type="b" access="read"/>
        <property name="IconName" type="s" access="read"/>
        <property name="IconThemePath" type="s" access="read"/>
        <property name="Status" type="s" access="read"/>
        <property name="AttentionIconName" type="s" access="read"/>
        <method name="Activate">
            <arg name="x" type="i" direction="in"/>
            <arg name="y" type="i" direction="in"/>
        </method>
        <method name="SecondaryActivate">
            <arg name="x" type="i" direction="in"/>
            <arg name="y" type="i" direction="in"/>
        </method>
        <signal name="NewIcon"/>
        <signal name="NewTooltip"/>
        <signal name="NewStatus">
          <arg name="status" type="s"/>
        </signal>
        <signal name="NewMenu" />
        <signal name="NewTitle" />
        <signal name="NewAttentionIcon" />
        <signal name="NewOverlayIcon" />
        <signal name="NewMenu" />
    </interface>
</node>"""
).interfaces[0]


log = logging.getLogger("gajim.c.tray.linux")


class StatusNotifierItemService(DBusService):

    Category = "Communications"
    Id = "org.gajim.Gajim"
    Title = "Gajim"
    Status = "Active"
    IconName = ""
    IconThemePath = ""
    AttentionIconName = ""
    ToolTip: tuple[str, list[Any], str, str] = ("", [], "Gajim", "")
    ItemIsMenu = False
    Menu = "/StatusNotifierItem/Menu"

    def __init__(
        self,
        session_bus: Gio.DBusConnection,
        menu: DBusMenu,
        theme_path: str | None,
        on_activate_callback: Callable[[], None],
    ):
        super().__init__(
            interface_info=SNI_NODE_INFO,
            object_path="/StatusNotifierItem",
            bus=session_bus,
        )

        if theme_path is not None:
            self.IconThemePath = theme_path

        self._on_activate_callback = on_activate_callback
        self._registered = False
        self._cancellable: Gio.Cancellable | None = None
        self._bus = session_bus
        self._menu = DBusMenuService("/StatusNotifierItem/Menu", session_bus, menu)

    def register(self):
        if self._registered:
            return

        self._registered = True
        self._cancellable = Gio.Cancellable()
        self._menu.register()
        super().register()

        def _on_finish(src: Gio.DBusProxy, res: Gio.AsyncResult) -> None:
            self._cancellable = None
            try:
                proxy = Gio.DBusProxy.new_finish(res)
                proxy.RegisterStatusNotifierItem(  # pyright: ignore
                    "(s)", "/StatusNotifierItem"
                )
            except Exception as error:
                log.error(error)
                return

        Gio.DBusProxy.new(
            connection=self._bus,
            flags=Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
            info=None,
            name="org.kde.StatusNotifierWatcher",
            object_path="/StatusNotifierWatcher",
            interface_name="org.kde.StatusNotifierWatcher",
            cancellable=self._cancellable,
            callback=_on_finish,
        )

    def unregister(self):
        if self._cancellable is not None:
            self._cancellable.cancel()

        super().unregister()
        self._menu.unregister()
        self._registered = False

    def Activate(self, _x: int, _y: int) -> None:
        self._on_activate_callback()

    def SecondaryActivate(self, _x: int, _y: int) -> None:
        self._on_activate_callback()

    def get_visible(self) -> bool:
        return self._registered

    def set_menu(self, menu: DBusMenu) -> None:
        self._menu.set_menu(menu)

    def set_icon(self, icon: str) -> None:
        self.IconName = icon
        self.emit_signal("NewIcon")

    def set_tooltip(self, title: str, description: str) -> None:
        self.ToolTip = ("", [], title, description)
        self.emit_signal("NewTooltip")
