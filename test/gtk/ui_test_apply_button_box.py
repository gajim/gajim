# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import GLib
from gi.repository import Gtk

from gajim.gtk.apply_button_box import ApplyButtonBox
from gajim.gtk.window import GajimAppWindow

from . import util


class TestApplyButtonBox(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
            add_window_padding=True,
            header_bar=True,
        )

        box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=True)
        self.set_child(box)

        self._apply_button_box = ApplyButtonBox("Apply", self._on_clicked)
        self._apply_button_box.set_button_state(True)
        box.append(self._apply_button_box)

    def _on_clicked(self, _button: Gtk.Button) -> None:
        print("clicked")
        GLib.timeout_add_seconds(2, self._apply_button_box.set_success)
        GLib.timeout_add_seconds(
            5, self._apply_button_box.set_error, "An error occurred"
        )
        GLib.timeout_add_seconds(9, self._apply_button_box.set_button_state, True)
        print("Finished")


util.init_settings()

window = TestApplyButtonBox()
window.show()

util.run_app()
