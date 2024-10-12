# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path
from unittest.mock import MagicMock

from gi.repository import Gst
from gi.repository import Gtk

from gajim.common import app
from gajim.common.preview import AudioPreviewState

from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.filechoosers import Filter
from gajim.gtk.preview_audio import AudioWidget
from gajim.gtk.widgets import GajimAppWindow

from . import util


class AudioWidgetTest(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name='',
            title='AudioWidget Test',
            default_width=600,
            default_height=600,
        )

        self._box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=True, orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self.set_child(self._box)

        file_chooser_button = FileChooserButton(
            label='Select Audio File',
            filters=[
                Filter(name='All files', patterns=['*']),
                Filter(name='MP3 Sounds', patterns=['*.mp3'], default=True),
            ],
        )
        file_chooser_button.connect('path-picked', self._on_path_picked)
        self._box.append(file_chooser_button)

        self._audio_widget = None

    def _on_path_picked(self, _button: FileChooserButton, paths: list[Path]) -> None:
        if self._audio_widget is not None:
            self._box.remove(self._audio_widget)

        self._audio_widget = AudioWidget(paths[0])
        self._box.append(self._audio_widget)


_success, _argv = Gst.init_check(None)

app.preview_manager = MagicMock()
app.preview_manager.get_audio_state = MagicMock(return_value=AudioPreviewState())

window = AudioWidgetTest()
window.show()

util.run_app()
