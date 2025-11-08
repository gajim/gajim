# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later
import typing

from pathlib import Path
from unittest.mock import MagicMock

import gi

try:
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst
except Exception:
    if typing.TYPE_CHECKING:
        from gi.repository import Gst

from gi.repository import Gst
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.audio_player import AudioPlayer
from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.filechoosers import Filter
from gajim.gtk.preview.audio import AudioPreviewWidget
from gajim.gtk.widgets import GajimAppWindow

from . import util

DEFAULT_AUDIO_FILE_PATH = util.get_gajim_dir() / "data/sounds/attention.wav"


class TestAudioWidget(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
        )

        self._box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )
        self.set_child(self._box)

        file_chooser_button = FileChooserButton(
            label="Select Audio File",
            filters=[
                Filter(name="All files", patterns=["*"]),
                Filter(name="WAV Sounds", patterns=["*.wav"]),
                Filter(name="MP3 Sounds", patterns=["*.mp3"], default=True),
            ],
            path=DEFAULT_AUDIO_FILE_PATH,
        )
        file_chooser_button.connect("path-picked", self._on_path_picked)
        self._box.append(file_chooser_button)

        self._audio_widget = AudioPreviewWidget(
            DEFAULT_AUDIO_FILE_PATH.name,
            DEFAULT_AUDIO_FILE_PATH.stat().st_size,
            DEFAULT_AUDIO_FILE_PATH,
        )
        self._box.append(self._audio_widget)

    def _on_path_picked(self, _button: FileChooserButton, paths: list[Path]) -> None:
        self._box.remove(self._audio_widget)
        del self._audio_widget

        self._audio_widget = AudioPreviewWidget(
            paths[0].as_posix(), paths[0].stat().st_size, paths[0]
        )
        self._box.append(self._audio_widget)


util.init_settings()

Gst.init()

app.is_installed = MagicMock(return_value=True)

app.init_process_pool()
app.audio_player = AudioPlayer()

window = TestAudioWidget()
window.show()

util.run_app()
