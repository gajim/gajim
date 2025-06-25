# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import TypeVar

from gi.repository import Gio
from gi.repository import GObject

_T = TypeVar("_T")


class SignalManager:
    def __init__(self) -> None:
        self._signal_data: list[tuple[GObject.Object | Gio.Action, int]] = []

    def _connect(
        self,
        obj: GObject.Object | Gio.Action,
        signal_name: str,
        callback: Any,
        *args: Any,
    ) -> int:

        signal_id = obj.connect(signal_name, callback, *args)
        self._signal_data.append((obj, signal_id))
        return signal_id

    def _connect_after(
        self, obj: GObject.Object, signal_name: str, callback: Any, *args: Any
    ) -> int:

        signal_id = obj.connect_after(signal_name, callback, *args)
        self._signal_data.append((obj, signal_id))
        return signal_id

    def _disconnect_all(self):
        for obj, signal_id in self._signal_data:
            obj.disconnect(signal_id)
        self._signal_data.clear()

    def _disconnect_object(self, obj: GObject.Object) -> None:
        for obj_, signal_id in list(self._signal_data):
            if obj is obj_:
                obj.disconnect(signal_id)
                self._signal_data.remove((obj, signal_id))
