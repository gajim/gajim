# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


from __future__ import annotations

from typing import Any

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject


class Singleton(type):

    _instances: dict[Any, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(
                *args, **kwargs)
        return cls._instances[cls]


class SettingsAction(Gio.SimpleAction):

    def simple_bind_property(
        self,
        target: GObject.Object,
        target_property: str
    ) -> None:

        self.bind_property(
            "state",
            target,
            target_property,
            GObject.BindingFlags.SYNC_CREATE,
            transform_to=self._transform_to_ptype,
        )

    def change_state(self, value: GLib.Variant | Any) -> None:
        if not isinstance(value, GLib.Variant):
            v_type = self.get_state_type()
            assert v_type is not None
            value = GLib.Variant(v_type.dup_string(), value)
        super().change_state(value)

    @staticmethod
    def _transform_to_ptype(
        binding: GObject.Binding, variant: GLib.Variant
    ) -> str:
        return variant.unpack()
