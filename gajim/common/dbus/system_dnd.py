# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import logging
import sys

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject

from gajim.common import app
from gajim.common.events import DndChanged

log = logging.getLogger("gajim.c.dbus.system_dnd")


class DoNotDisturbListener:
    _instance: DoNotDisturbListener | None = None

    @classmethod
    def get(cls) -> DoNotDisturbListener:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        self._inhibited: bool = False

        if sys.platform in ("win32", "darwin"):
            return

        try:
            self._dbus_proxy = Gio.DBusProxy.new_for_bus(
                Gio.BusType.SESSION,
                Gio.DBusProxyFlags.NONE,
                None,
                "org.freedesktop.Notifications",
                "/org/freedesktop/Notifications",
                "org.freedesktop.DBus.Properties",
                None,
                self._on_proxy_ready,
            )
        except GLib.Error as error:
            log.info("Notifications service not found: %s", error)
            return

    def read_inhibited(self) -> None:
        if self._dbus_proxy is None:
            return

        self._dbus_proxy.call(
            "Get",
            GLib.Variant(
                "(ss)",
                ("org.freedesktop.Notifications", "Inhibited"),
            ),
            Gio.DBusCallFlags.NO_AUTO_START,
            1000,  # 1 second timeout
            None,
            self._on_read_inhibited,
        )

    def _on_proxy_ready(self, _source: GObject.Object, result: Gio.AsyncResult) -> None:
        assert self._dbus_proxy is None

        try:
            self._dbus_proxy = Gio.DBusProxy.new_for_bus_finish(result)
        except GLib.Error as error:
            log.info("Notifications service not found: %s", error)
            return

        self._dbus_proxy.connect("g-signal", self._signal_properties_changed)
        self.read_inhibited()

    def _on_read_inhibited(
        self, _source: GObject.Object, result: Gio.AsyncResult
    ) -> None:
        assert self._dbus_proxy is not None

        try:
            value = self._dbus_proxy.call_finish(result)
            self._inhibited = value.unpack()[0]
        except GLib.Error as error:
            log.error("Couldn't read Do Not Disturb state: %s", error.message)

    def _emit(self, inhibited: bool) -> None:
        self._inhibited = inhibited
        app.ged.raise_event(DndChanged(inhibited=inhibited))

    def _signal_properties_changed(
        self,
        _proxy: Gio.DBusProxy,
        _sender_name: str | None,
        signal_name: str,
        parameters: GLib.Variant,
        *_user_data: Any,
    ) -> None:
        if signal_name != "PropertiesChanged":
            return

        interface, changed, _invalidated = parameters.unpack()

        if interface != "org.freedesktop.Notifications":
            return

        if "Inhibited" not in changed:
            return

        self._inhibited = changed["Inhibited"]
        self._emit(self._inhibited)

    @property
    def inhibited(self) -> bool:
        return self._inhibited
