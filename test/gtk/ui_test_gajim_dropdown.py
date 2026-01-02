# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

from gi.repository import Gtk

from gajim.gtk.dropdown import GajimDropDown
from gajim.gtk.window import GajimAppWindow

from . import util


class TestGajimDropDown(GajimAppWindow):
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

        box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )
        self.set_child(box)

        gajim_drop_down1: GajimDropDown[str] = GajimDropDown(fixed_width=20)
        gajim_drop_down1.set_data(
            {
                "key1": "Test 10000",
                "key2": "Test 2 Very Very Very Very Very Long Key",
                "key3": "Test 3",
                "Key": "Value",
                "Another Key": "Another Value",
            }
        )
        gajim_drop_down1.set_enable_search(True)
        gajim_drop_down1.connect("notify::selected", self._on_item_selected)
        box.append(gajim_drop_down1)

        gajim_drop_down2: GajimDropDown[str] = GajimDropDown(
            data=["key1", "key2", "key3"]
        )
        gajim_drop_down2.set_selected(2)
        gajim_drop_down2.connect("notify::selected", self._on_item_selected)
        box.append(gajim_drop_down2)

    def _on_item_selected(self, drop_down: GajimDropDown[str], *args: Any) -> None:
        print("Index:", drop_down.get_selected())
        item = drop_down.get_selected_item()
        if item is not None:
            print("Item key:", item.get_property("key"))
            print("Item value:", item.get_property("value"))

    def _cleanup(self) -> None:
        pass


util.init_settings()

window = TestGajimDropDown()
window.show()

util.run_app()
