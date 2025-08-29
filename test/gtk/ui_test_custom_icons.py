# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import Any

import os
from pathlib import Path

from gi.repository import Adw
from gi.repository import Gtk

from gajim.gtk.widgets import GajimAppWindow

from . import util

CUSTOM_ICONS_PATH = util.get_gajim_dir() / "data/icons"


class TestCustomIcons(GajimAppWindow):
    """A test window which lists all of Gajim's custom scalable icons.
    This allows us to quickly check if symbolic display is working correctly, see:
    https://dev.gajim.org/gajim/gajim/-/wikis/Icon-Resources#symbolic-svgs
    """

    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
        )

        box = Gtk.Box(spacing=18, orientation=Gtk.Orientation.VERTICAL)
        self.set_child(box)

        switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        switch.connect("notify::active", self._on_theme_switched)

        reload_button = Gtk.Button(label="Reload")
        reload_button.connect("clicked", self._on_reload_clicked)

        controls_box = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        controls_box.append(Gtk.Label(label="Light"))
        controls_box.append(switch)
        controls_box.append(Gtk.Label(label="dark"))
        controls_box.append(reload_button)
        box.append(controls_box)

        self._adw_style_manager = Adw.StyleManager.get_default()
        color_scheme = self._adw_style_manager.get_color_scheme()
        switch.set_active(color_scheme == Adw.ColorScheme.FORCE_DARK)

        scrolled_window = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER, vexpand=True
        )
        box.append(scrolled_window)
        self._flow_box = Gtk.FlowBox(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            row_spacing=6,
            column_spacing=12,
            min_children_per_line=10,
        )
        scrolled_window.set_child(self._flow_box)

        self._load_images()

    def _cleanup(self):
        pass

    def _on_theme_switched(self, switch: Gtk.Switch, args: Any) -> None:
        if switch.get_active():
            self._adw_style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        else:
            self._adw_style_manager.set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)

    def _on_reload_clicked(self, _button: Gtk.Button) -> None:
        self._load_images()

    def _load_images(self) -> None:
        self._flow_box.remove_all()

        for _root, _dirs, files in os.walk(CUSTOM_ICONS_PATH):
            for file in sorted(files):
                file_path = Path(file)

                if not file_path.suffix == ".svg":
                    continue

                image = Gtk.Image.new_from_icon_name(file_path.stem)
                image.set_tooltip_text(file)
                image.set_pixel_size(48)
                self._flow_box.append(image)


util.init_settings()

window = TestCustomIcons()
window.show()

util.run_app()
