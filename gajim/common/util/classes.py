# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only


from __future__ import annotations

from typing import Any


class Singleton(type):

    _instances: dict[Any, Any] = {}

    def __call__(cls, *args: Any, **kwargs: Any):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(
                *args, **kwargs)
        return cls._instances[cls]
