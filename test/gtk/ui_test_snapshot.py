# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gdk
from gi.repository import Graphene
from gi.repository import Gsk
from gi.repository import Gtk

from gajim.gtk.widgets import GajimAppWindow

from . import util

DEFAULT_IMAGE_FILE_PATH = (
    util.get_gajim_dir() / 'data/icons/hicolor/96x96/apps/gajim.png'
)


class TestSnapshot(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name='',
            title=__class__.__name__,
            default_width=600,
            default_height=600,
        )

        box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )
        self.set_child(box)

        self._image = Gtk.Image()
        self._image.set_pixel_size(100)
        box.append(self._image)

        self._paint()

    def _paint(self) -> None:
        texture = Gdk.Texture.new_from_filename(str(DEFAULT_IMAGE_FILE_PATH))

        snapshot = Gtk.Snapshot.new()
        rect = Graphene.Rect().init(0, 0, texture.get_width(), texture.get_height())
        snapshot.append_texture(texture, rect)

        cutout_rect = Graphene.Rect().init(50, 50, 50, 50)

        color = Gdk.RGBA()
        color.parse('rgb(70, 0, 190)')

        rounded_rect = Gsk.RoundedRect()
        rounded_rect.init_from_rect(cutout_rect, radius=25)

        snapshot.push_rounded_clip(rounded_rect)
        snapshot.append_color(color, cutout_rect)
        snapshot.pop()

        overlay_rect = Graphene.Rect().init(55, 55, 40, 40)
        snapshot.append_scaled_texture(
            texture, Gsk.ScalingFilter.TRILINEAR, overlay_rect
        )

        self._image.set_from_paintable(snapshot.to_paintable())


window = TestSnapshot()
window.show()

util.run_app()
