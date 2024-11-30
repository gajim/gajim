# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk

from gajim.gtk.groupchat_nick import NickChooser
from gajim.gtk.widgets import GajimAppWindow

from . import util


class TestNickChooser(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=700,
            default_height=700,
        )

        self._main_box = Gtk.Box(
            hexpand=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER
        )

        self._nick_chooser = NickChooser()
        self._nick_chooser.set_text("Fancy Nickname")

        self._main_box.append(self._nick_chooser)

        self.set_child(self._main_box)

    def _cleanup(self) -> None:
        pass


window = TestNickChooser()
window.show()

util.run_app()
