# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from enum import IntEnum


class AudioPlayerState(IntEnum):
    NULL = 0
    READY = 1
    PAUSED = 2
    PLAYING = 3


class FTState(IntEnum):
    CREATED = 0
    PREPARING = 1
    ENCRYPTING = 2
    DECRYPTING = 3
    STARTED = 4
    IN_PROGRESS = 5
    FINISHED = 6
    ERROR = 7
    CANCELLED = 8


class PreviewState(IntEnum):
    INIT = 0
    DOWNLOADING = 1
    OFFER_DOWNLOAD = 2
    DOWNLOADED = 3
    DISPLAY = 4
    ERROR = 5
