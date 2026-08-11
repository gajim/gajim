# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import string


def is_valid_sha1(value: str) -> bool:
    """Return whether *value* is a canonical lowercase SHA-1 digest."""
    return len(value) == 40 and all(char in string.hexdigits[:16] for char in value)
