# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from datetime import datetime
from datetime import UTC


def mk_utc_dt(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, UTC)
