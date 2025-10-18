# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from dataclasses import field

log = logging.getLogger('gajim.c.preview')

AudioSampleT = list[tuple[float, float]]


@dataclass
class AudioPreviewState:
    duration: float = 0.0
    position: float = 0.0
    is_eos: bool = False
    speed: float = 1.0
    is_timestamp_positive: bool = True
    samples: AudioSampleT = field(default_factory=list[tuple[float, float]])
    is_audio_analyzed = False


class PreviewManager:
    def __init__(self) -> None:
        # Holds active audio preview sessions
        # for resuming after switching chats
        self._audio_sessions: dict[int, AudioPreviewState] = {}

        # References a stop function for each audio preview, which allows us
        # to stop previews by preview_id, see stop_audio_except(preview_id)
        self._audio_stop_functions: dict[int, Callable[..., None]] = {}

    def get_audio_state(self,
                        preview_id: int
                        ) -> AudioPreviewState:

        state = self._audio_sessions.get(preview_id)
        if state is not None:
            return state
        self._audio_sessions[preview_id] = AudioPreviewState()
        return self._audio_sessions[preview_id]

    def register_audio_stop_func(self,
                                 preview_id: int,
                                 stop_func: Callable[..., None]
                                 ) -> None:

        self._audio_stop_functions[preview_id] = stop_func

    def unregister_audio_stop_func(self, preview_id: int) -> None:
        self._audio_stop_functions.pop(preview_id, None)

    def stop_audio_except(self, preview_id: int) -> None:
        # Stops playback of all audio previews except of for preview_id.
        # This makes sure that only one preview is played at the time.
        for id_, stop_func in self._audio_stop_functions.items():
            if id_ != preview_id:
                stop_func()
