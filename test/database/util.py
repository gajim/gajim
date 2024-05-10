from __future__ import annotations

from datetime import datetime
from datetime import timezone


def mk_utc_dt(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, timezone.utc)
