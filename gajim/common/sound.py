# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import Optional

import sys
import logging
from pathlib import Path

from gi.repository import Gio
from gi.repository import GLib

from gajim.common import app

if sys.platform == 'win32':
    import winsound

elif sys.platform == 'darwin':
    from AppKit import NSSound


log = logging.getLogger('gajim.c.sound')


class PlaySound:

    def play(self, path: Path, loop: bool = False) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError


class PlatformWindows(PlaySound):

    def play(self, path: Path, loop: bool = False) -> None:
        flags = (winsound.SND_FILENAME |
                 winsound.SND_ASYNC |
                 winsound.SND_NODEFAULT)
        if loop:
            flags = flags | winsound.SND_LOOP

        try:
            winsound.PlaySound(str(path), flags)
        except Exception:
            log.exception('Sound Playback Error')

    def stop(self) -> None:
        try:
            winsound.PlaySound(None, 0)
        except Exception:
            log.exception('Sound Playback Error')


class PlatformMacOS(PlaySound):

    def play(self, path: Path, loop: bool = False) -> None:
        sound = NSSound.alloc()
        sound.initWithContentsOfFile_byReference_(str(path), True)
        sound.play()

    def stop(self) -> None:
        pass


class PlatformUnix(PlaySound):

    def __init__(self) -> None:
        self._cancellable: Optional[Gio.Cancellable] = None

    def play(self, path: Path, loop: bool = False) -> None:
        if not app.is_installed('GSOUND'):
            return

        attrs = {'media.filename': str(path)}
        self._cancellable = Gio.Cancellable()

        if loop:
            self._play_loop(attrs)
        else:
            try:
                app.gsound_ctx.play_simple(attrs, self._cancellable)
            except GLib.Error as error:
                log.error('Could not play sound: %s', error.message)
                self._cancellable = None

    def _play_loop(self, attrs: dict[str, str]) -> None:
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
                return
            log.error('Could not play sound: %s', error.message)

        self._play_loop(user_data)

    def stop(self) -> None:
        if self._cancellable is None or self._cancellable.is_cancelled():
            return
        self._cancellable.cancel()
        self._cancellable = None


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
