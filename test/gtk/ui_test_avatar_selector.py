# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk

from gajim.gtk.avatar_selector import AvatarSelector
from gajim.gtk.widgets import GajimAppWindow

from . import util

DEFAULT_IMAGE_FILE_PATH = (
    util.get_gajim_dir() / "data/icons/hicolor/96x96/apps/gajim.png"
)


class TestAvatarSelector(GajimAppWindow):
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

        avatar_selector = AvatarSelector()
        avatar_selector.prepare_crop_area(str(DEFAULT_IMAGE_FILE_PATH))
        box.append(avatar_selector)


window = TestAvatarSelector()
window.show()

util.run_app()
