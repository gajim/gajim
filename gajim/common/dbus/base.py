# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any

import logging

from gi.repository import Gio
from gi.repository import GLib

from gajim.common.util.version import gi_package_version

log = logging.getLogger("gajim.c.dbus")


class DBusService:
    def __init__(
        self,
        interface_info: Gio.DBusInterfaceInfo,
        object_path: str,
        bus: Gio.DBusConnection,
    ) -> None:
        self._interface_info = interface_info
        self._bus = bus
        self._object_path = object_path
        self._registration_id: int | None = None

    def register(self):
        if gi_package_version("GLib>=2.84.0"):
            register_method = self._bus.register_object_with_closures2
        else:
            register_method = self._bus.register_object

        try:
            self._registration_id = register_method(
                object_path=self._object_path,
                interface_info=self._interface_info,
                method_call_closure=self._on_method_call,
                get_property_closure=self._on_get_property,
            )
        except Exception as error:
            log.error(error)
            return

        assert self._registration_id

        self._interface_info.cache_build()

    def unregister(self):
        self._interface_info.cache_release()

        if self._registration_id is not None:
            try:
                self._bus.unregister_object(self._registration_id)
            except Exception as error:
                log.error(error)
            self._registration_id = None

    def _on_method_call(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        method_name: str,
        parameters: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        method_info = self._interface_info.lookup_method(method_name)
        if method_info is None:
            log.warning("Unknown method name called: %s", method_name)
            return

        args = parameters.unpack()
        log.info("Method %s called on %s, args: %s", method_name, self, args)

        method = getattr(self, method_name)
        result = method(*args)
        out_arg_types = "".join([arg.signature for arg in method_info.out_args])
        return_value = None

        if method_info.out_args:
            return_value = GLib.Variant(f"({out_arg_types})", result)

        invocation.return_value(return_value)

    def _on_get_property(
        self,
        _connection: Gio.DBusConnection,
        _sender: str,
        _object_path: str,
        _interface_name: str,
        property_name: str,
    ) -> GLib.Variant | None:
        property_info = self._interface_info.lookup_property(property_name)
        if property_info is None:
            log.warning("Unknown property requested: %s", property_name)
            return

        value = getattr(self, property_name)
        log.info(
            "GetProperty %s called on %s, return value: %s", property_name, self, value
        )

        return GLib.Variant(property_info.signature, value)

    def emit_signal(self, signal_name: str, args: Any = None) -> None:
        signal_info = self._interface_info.lookup_signal(signal_name)
        if signal_info is None:
            raise ValueError(f"Unknown signal: {signal_name}")

        if len(signal_info.args) == 0:
            parameters = None
        else:
            arg_types = "".join([arg.signature for arg in signal_info.args])
            parameters = GLib.Variant(f"({arg_types})", args)

        log.info("Emit Signal %s on %s, args: %s", signal_name, self, args)

        try:
            self._bus.emit_signal(
                destination_bus_name=None,
                object_path=self._object_path,
                interface_name=self._interface_info.name,
                signal_name=signal_name,
                parameters=parameters,
            )
        except Exception as error:
            log.error(error)
