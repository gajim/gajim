# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import logging
import sys
from pathlib import Path

from gi.repository import Gtk

if sys.platform == 'win32' or typing.TYPE_CHECKING:
    import winsound

if sys.platform == 'darwin' or typing.TYPE_CHECKING:
    from AppKit import NSSound

log = logging.getLogger('gajim.c.sound')


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
        flags = (winsound.SND_FILENAME |
                 winsound.SND_ASYNC |
                 winsound.SND_NODEFAULT)
        if loop:
            self._loop_in_progress = True
            flags = flags | winsound.SND_LOOP

        try:
            winsound.PlaySound(str(path), flags)
        except Exception:
            log.exception('Sound Playback Error')

    def stop(self) -> None:
        assert winsound is not None
        try:
            winsound.PlaySound(None, 0)
        except Exception:
            log.exception('Sound Playback Error')
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

    def __init__(self) -> None:
        self._media_file: Gtk.MediaFile | None = None

    def play(self, path: Path, loop: bool = False) -> None:
        if self.loop_in_progress():
            return

        self._media_file = Gtk.MediaFile.new_for_filename(str(path))

        if self._media_file.is_seekable():
            self._media_file.set_loop(loop)

        self._media_file.play()

    def stop(self) -> None:
        if self._media_file is None:
            return

        self._media_file.clear()

    def loop_in_progress(self) -> bool:
        return self._media_file is not None and self._media_file.get_loop()


def _init_platform() -> PlaySound:
    if sys.platform == 'win32':
        return PlatformWindows()

    if sys.platform == 'darwin':
        return PlatformMacOS()

    return PlatformUnix()


_platform_player = _init_platform()


def play(path: Path, loop: bool = False) -> None:
    _platform_player.play(path, loop)


def stop():
    _platform_player.stop()
