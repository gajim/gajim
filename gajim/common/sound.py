# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing
from typing import Any

import logging
import sys
from pathlib import Path

from gi.repository import Gio
from gi.repository import GLib

from gajim.common import app

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
        self._cancellable: Gio.Cancellable | None = None

    def play(self, path: Path, loop: bool = False) -> None:
        if not app.is_installed('GSOUND'):
            return

        if self.loop_in_progress():
            return

        attrs = {'media.filename': str(path)}

        if loop:
            self._play_loop(attrs)
        else:
            try:
                app.gsound_ctx.play_simple(attrs, self._cancellable)
            except GLib.Error as error:
                log.error('Could not play sound: %s', error.message)
                self._cancellable = None

    def _play_loop(self, attrs: dict[str, str]) -> None:
        self._cancellable = Gio.Cancellable()
        try:
            app.gsound_ctx.play_full(attrs,
                                     self._cancellable,
                                     self._on_play_finished,
                                     attrs)
        except GLib.Error as error:
            log.error('Could not play sound: %s', error.message)
            self._cancellable = None

    def _on_play_finished(self,
                          _context: Any,
                          res: Gio.AsyncResult,
                          user_data: dict[str, str]) -> None:
        try:
            app.gsound_ctx.play_full_finish(res)
        except GLib.Error as error:
            quark = GLib.quark_try_string('g-io-error-quark')
            if error.matches(quark, Gio.IOErrorEnum.CANCELLED):
                self._cancellable = None
                return
            log.error('Could not play sound: %s', error.message)

        self._play_loop(user_data)

    def stop(self) -> None:
        if self._cancellable is None or self._cancellable.is_cancelled():
            return
        self._cancellable.cancel()
        self._cancellable = None

    def loop_in_progress(self) -> bool:
        return self._cancellable is not None


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
