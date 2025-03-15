# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from gi.repository import Gtk

from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.filechoosers import Filter
from gajim.gtk.widgets import GajimAppWindow

from . import util


class TestFileChooserButton(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
        )

        box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=True)
        self.set_child(box)

        file_chooser_button = FileChooserButton(
            filters=[
                Filter(name="All files", patterns=["*"]),
                Filter(name="Wav Sounds", patterns=["*.wav"]),
            ]
        )
        file_chooser_button.connect("path-picked", self._on_file_picked)
        box.append(file_chooser_button)

    def _on_file_picked(
        self, _file_chooser_button: FileChooserButton, file_paths: list[Path]
    ) -> None:
        print(file_paths)


util.init_settings()

window = TestFileChooserButton()
window.show()

util.run_app()
