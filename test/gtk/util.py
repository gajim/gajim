# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import logging
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import CSSPriority
from gajim.common.settings import Settings

from gajim.gtk.util.icons import get_icon_theme


def get_gajim_dir() -> Path:
    gajim_path = Path(__file__) / ".." / ".." / ".." / "gajim"
    return gajim_path.resolve()


def load_style(filename: str, priority: CSSPriority) -> None:
    path = get_gajim_dir() / "data" / "style" / filename
    try:
        with open(str(path), encoding="utf8") as file:
            css = file.read()
    except Exception:
        logging.exception("")
        return
    provider = Gtk.CssProvider()
    provider.load_from_bytes(GLib.Bytes.new(css.encode("utf-8")))
    display = Gdk.Display.get_default()
    assert display is not None
    Gtk.StyleContext.add_provider_for_display(display, provider, priority)


def init_settings() -> None:
    app.settings = Settings(in_memory=True)
    app.settings.init()


def run_app(load_default_styles: bool = True, load_custom_icons: bool = True) -> None:
    if load_default_styles:
        load_style("gajim.css", CSSPriority.APPLICATION)

    if load_custom_icons:
        icon_theme = get_icon_theme()
        icon_theme.add_search_path(str(get_gajim_dir() / "data/icons"))

    while Gtk.Window.get_toplevels().get_n_items() > 0:
        GLib.MainContext().default().iteration(True)
