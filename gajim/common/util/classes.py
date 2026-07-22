# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


from __future__ import annotations

from typing import Any
from typing import Generic
from typing import TypedDict
from typing import TypeVar

from datetime import datetime
from enum import IntEnum

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject

_K = TypeVar("_K")
_V = TypeVar("_V")


class Singleton(type):
    _instances: dict[Any, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class SettingsAction(Gio.SimpleAction):
    def simple_bind_property(
        self, target: GObject.Object, target_property: str
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
    def _transform_to_ptype(binding: GObject.Binding, variant: GLib.Variant) -> str:
        return variant.unpack()


class CacheResult(IntEnum):
    HIT = 0
    MISS = 1


class CacheItem(TypedDict, Generic[_V]):
    value: _V
    created: datetime


class TTLCache(Generic[_K, _V]):
    def __init__(self, *, ttl_seconds: int, extend_ttl_on_hit: bool):
        self._cache_items: dict[_K, CacheItem[_V]] = {}
        self._ttl_seconds = ttl_seconds
        self._extend_ttl_on_hit = extend_ttl_on_hit

    def get(self, key: _K) -> tuple[_V | None, CacheResult]:
        if self._is_expired(key):
            return None, CacheResult.MISS

        if self._extend_ttl_on_hit:
            self._cache_items[key]["created"] = datetime.now()
        return self._cache_items[key]["value"], CacheResult.HIT

    def add(self, key: _K, value: _V) -> None:
        self._cache_items[key] = CacheItem(value=value, created=datetime.now())

    def _is_expired(self, key: _K) -> bool:
        if key not in self._cache_items:
            return True

        time_diff = datetime.now() - self._cache_items[key]["created"]
        if time_diff.total_seconds() > self._ttl_seconds:
            del self._cache_items[key]
            return True

        return False

    def __contains__(self, key: _K) -> bool:
        return not self._is_expired(key)
