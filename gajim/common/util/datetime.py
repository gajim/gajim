# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from datetime import datetime
from datetime import timezone

FIRST_UTC_DATETIME = datetime(1970, 1, 1, tzinfo=timezone.utc)
FIRST_LOCAL_DATETIME = FIRST_UTC_DATETIME.astimezone()


def convert_epoch_to_local_datetime(utc_timestamp: float) -> datetime:
    utc = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)
    return utc.astimezone()


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
