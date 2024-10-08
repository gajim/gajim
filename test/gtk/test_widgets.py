# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk

from gajim.gtk.widgets import FileChooserButton
from gajim.gtk.widgets import GajimAppWindow

from . import util


class FileChooserButtonTest(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name='',
            title='FileChooserButton Test',
            default_width=600,
            default_height=600,
        )

        box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=True)
        self.set_child(box)

        file_chooser_button = FileChooserButton()
        file_chooser_button.connect('path-picked', self._on_file_picked)
        box.append(file_chooser_button)

        filter_ = Gtk.FileFilter()
        filter_.set_name('Wav Sounds')
        filter_.add_pattern('*.wav')
        file_chooser_button.add_filter(filter_)

    def _on_file_picked(
        self, _file_chooser_button: FileChooserButton, file_path: str
    ) -> None:
        print(file_path)


window = FileChooserButtonTest()
window.show()

util.run_app()
