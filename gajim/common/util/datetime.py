# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from datetime import datetime
from datetime import timezone


def convert_epoch_to_local_datetime(utc_timestamp: float) -> datetime:
    utc = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
    return utc.astimezone()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
