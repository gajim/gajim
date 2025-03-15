# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.gtk.widgets import GajimAppWindow

from . import util


class TestDNDFile(GajimAppWindow):
    def __init__(self):
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
            hexpand=True,
            width_request=300,
            height_request=300,
        )
        box.add_css_class("dnd-area")
        self.set_child(box)

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect("accept", self._on_drop_accept)
        drop_target.connect("drop", self._on_file_drop)
        box.add_controller(drop_target)

        label = Gtk.Label(label="Drop files here", hexpand=True)
        box.append(label)

    def _on_drop_accept(self, _target: Gtk.DropTarget, drop: Gdk.Drop) -> bool:
        formats = drop.get_formats()
        return bool(formats.contain_gtype(Gdk.FileList))

    def _on_file_drop(
        self, _target: Gtk.DropTarget, value: Gdk.FileList, _x: float, _y: float
    ) -> bool:
        files = value.get_files()
        print([file.get_basename() for file in files])
        return True


util.init_settings()

window = TestDNDFile()
window.show()

util.run_app()
