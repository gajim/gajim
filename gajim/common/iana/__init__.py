# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import NamedTuple

from gajim.common.iana.time_zones import WINDOWS_ZONES
from gajim.common.iana.time_zones import ZONES


class ZoneData(NamedTuple):
    key: str
    name: str

    @classmethod
    def from_key(cls, key: str) -> ZoneData:
        name = key.replace("_", " ")
        return cls(key, name)


def get_zone_data(key: str) -> ZoneData | None:
    if key not in ZONES:
        key = WINDOWS_ZONES.get(key, "")

    if not key:
        return None

    return ZoneData.from_key(key)
