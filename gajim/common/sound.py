# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import logging
import sys
from pathlib import Path

from gajim.gtk.audio_player import AudioPlayer

if sys.platform == "win32" or typing.TYPE_CHECKING:
    import winsound

if sys.platform == "darwin" or typing.TYPE_CHECKING:
    from AppKit import NSSound

log = logging.getLogger("gajim.c.sound")


class PlaySound:
    def play(self, path: Path, loop: bool = False) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def loop_in_progress(self) -> bool:
        raise NotImplementedError


class PlatformWindows(PlaySound):
    def __init__(self) -> None:
        self._loop_in_progress = False

    def play(self, path: Path, loop: bool = False) -> None:
        if self._loop_in_progress:
            return

        assert winsound is not None
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT
        if loop:
            self._loop_in_progress = True
            flags = flags | winsound.SND_LOOP

        try:
            winsound.PlaySound(str(path), flags)
        except Exception:
            log.exception("Sound Playback Error")

    def stop(self) -> None:
        assert winsound is not None
        try:
            winsound.PlaySound(None, 0)
        except Exception:
            log.exception("Sound Playback Error")
        self._loop_in_progress = False

    def loop_in_progress(self) -> bool:
        return self._loop_in_progress


class PlatformMacOS(PlaySound):
    def play(self, path: Path, loop: bool = False) -> None:
        assert NSSound is not None
        sound = NSSound.alloc()
        sound.initWithContentsOfFile_byReference_(str(path), True)
        sound.play()

    def stop(self) -> None:
        pass

    def loop_in_progress(self) -> bool:
        return False


class PlatformUnix(PlaySound):
    _SOUND_PREVIEW_ID = 0

    def __init__(self) -> None:
        self._loop_in_progress = False
        self._audio_player = AudioPlayer()

    @property
    def sound_preview_id(self) -> int:
        return self._SOUND_PREVIEW_ID

    def play(self, path: Path, loop: bool = False) -> None:
        if self._loop_in_progress:
            return

        self.stop()
        self._audio_player.get_audio_state(self._SOUND_PREVIEW_ID)
        self._loop_in_progress = loop
        self._audio_player.play_audio_file(
            path, self._SOUND_PREVIEW_ID, loop=loop, from_start=True
        )

    def stop(self) -> None:
        self._loop_in_progress = False
        self._audio_player.stop(self._SOUND_PREVIEW_ID)

    def loop_in_progress(self) -> bool:
        return self._loop_in_progress


def _init_platform() -> PlaySound:
    if sys.platform == "win32":
        return PlatformWindows()

    if sys.platform == "darwin":
        return PlatformMacOS()

    return PlatformUnix()


_platform_player = _init_platform()


def play(path: Path, loop: bool = False) -> None:
    _platform_player.play(path, loop)


def stop():
    _platform_player.stop()
