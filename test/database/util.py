# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

import logging
import sys
from datetime import datetime
from datetime import UTC


def mk_utc_dt(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, UTC)


def attach_debug_logger(log_module: str) -> None:
    logger = logging.getLogger(log_module)
    logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler(sys.stdout)
    logger.addHandler(stream_handler)
