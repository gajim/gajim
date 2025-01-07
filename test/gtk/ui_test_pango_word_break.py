# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import unicodedata

from gi.repository import Gtk
from gi.repository import Pango

from gajim.gtk.util import process_non_spacing_marks
from gajim.gtk.widgets import GajimAppWindow

from . import util

FATAL_STRING = "aر ॣॣb"


class TestPangoWordWrap(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
        )

        box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            orientation=Gtk.Orientation.VERTICAL,
            hexpand=True,
            spacing=12,
        )
        self.set_child(box)

        label1 = Gtk.Label(
            label=FATAL_STRING, wrap=True, wrap_mode=get_pango_wrap_mode(FATAL_STRING)
        )
        box.append(label1)

        label2 = Gtk.Label(
            label=process_non_spacing_marks(FATAL_STRING),
            wrap=True,
            wrap_mode=Pango.WrapMode.WORD_CHAR,
        )
        box.append(label2)


def get_pango_wrap_mode(string: str) -> Pango.WrapMode:
    for char in string:
        if unicodedata.category(char) == "Mn":
            return Pango.WrapMode.WORD
    return Pango.WrapMode.WORD_CHAR


window = TestPangoWordWrap()
window.show()

util.run_app()
