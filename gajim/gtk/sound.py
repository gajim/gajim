# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import logging
import sys
from pathlib import Path

from gajim.common import app
from gajim.common import configpaths

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


def check_soundfile_path(file_: str, dirs: list[Path] | None = None) -> Path | None:
    """
    Check if the sound file exists

    :param file_: the file to check, absolute or relative to 'dirs' path
    :param dirs: list of knows paths to fallback if the file doesn't exists
                                     (eg: ~/.gajim/sounds/, DATADIR/sounds...).
    :return      the path to file or None if it doesn't exists.
    """
    if not file_:
        return None
    if Path(file_).exists():
        return Path(file_)

    if dirs is None:
        dirs = [configpaths.get("MY_DATA"), configpaths.get("DATA")]

    for dir_ in dirs:
        dir_ = dir_ / "sounds" / file_
        if dir_.exists():
            return dir_
    return None


def allow_sound_notification(account: str | None, sound_event: str) -> bool:
    if not app.settings.get("sounds_on"):
        return False

    if account is None:
        return True

    client = app.get_client(account)
    if client.status != "online" and not app.settings.get("sounddnd"):
        return False
    if app.settings.get_soundevent_settings(sound_event)["enabled"]:  # noqa: SIM103
        return True
    return False


def play(
    sound_event: str,
    account: str | None,
    *,
    force: bool = False,
    loop: bool = False,
) -> None:

    if force or allow_sound_notification(account, sound_event):
        str_path_to_soundfile = typing.cast(
            str, app.settings.get_soundevent_settings(sound_event)["path"]
        )
        path_to_soundfile = check_soundfile_path(str_path_to_soundfile)
        if path_to_soundfile is None:
            return

        _platform_player.play(path_to_soundfile, loop)


def stop():
    _platform_player.stop()


def _init_platform() -> PlaySound:
    if sys.platform == "win32":
        return PlatformWindows()

    if sys.platform == "darwin":
        return PlatformMacOS()

    return PlatformUnix()


_platform_player = _init_platform()
