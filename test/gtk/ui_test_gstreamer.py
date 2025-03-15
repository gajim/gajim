# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock

import gi

gi.require_version("Gst", "1.0")

from gi.repository import Gst
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.gstreamer import create_video_elements
from gajim.gtk.widgets import GajimAppWindow

from . import util


class TestGstreamer(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=800,
            default_height=800,
        )

        box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=True)
        self.set_child(box)

        video_elements = create_video_elements()
        if video_elements is None:
            return

        sink, paintable, name = video_elements
        print(sink, paintable, name)

        pipeline = Gst.Pipeline.new()
        pipeline.add(sink)

        if name == "gtkglsink":
            src = Gst.ElementFactory.make("gltestsrc")
        else:
            src = Gst.ElementFactory.make("videotestsrc")

        if src is None:
            return

        pipeline.add(src)
        src.link(sink)
        pipeline.set_state(Gst.State.PLAYING)

        picture = Gtk.Picture(hexpand=True, vexpand=True, paintable=paintable)
        box.append(picture)


Gst.init()

app.is_installed = MagicMock(return_value=True)

util.init_settings()

window = TestGstreamer()
window.show()

util.run_app()
