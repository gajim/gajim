# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

import logging

import cairo
from gi.repository import Gdk
from gi.repository import Gsk
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.util.misc import convert_texture_to_surface

log = logging.getLogger("gajim.gtk.util.icons")


def icon_exists(name: str) -> bool:
    return get_icon_theme().has_icon(name)


def get_icon_theme() -> Gtk.IconTheme:
    display = Gdk.Display.get_default()
    assert display is not None
    return Gtk.IconTheme.get_for_display(display)


def find_texture_node(node: Gsk.RenderNode | None) -> Gsk.TextureNode | None:
    if isinstance(node, Gsk.TextureNode):
        return node

    if isinstance(node, Gsk.TransformNode):
        return find_texture_node(node.get_child())

    if isinstance(node, Gsk.ContainerNode):
        for i in range(node.get_n_children()):
            child = node.get_child(i)
            texture_node = find_texture_node(child)
            if texture_node is not None:
                return texture_node

    return None


def load_icon_surface(
    icon_name: str,
    size: int = 16,
    scale: int | None = None,
) -> cairo.ImageSurface | None:
    if scale is None:
        scale = app.window.get_scale_factor()

    if not scale:
        log.warning("Could not determine scale factor")
        scale = 1

    icon_theme = get_icon_theme()
    icon = icon_theme.lookup_icon(
        icon_name,
        None,
        size,
        scale,
        Gtk.TextDirection.NONE,
        0,  # pyright: ignore
    )

    snapshot = Gtk.Snapshot()
    icon.snapshot(snapshot, size, size)

    texture_node = find_texture_node(snapshot.to_node())
    if texture_node is None:
        log.error("Could not find texture node")
        return None

    texture = texture_node.get_texture()
    return convert_texture_to_surface(texture)


def get_tray_icon_name(name: str) -> str:
    prefix = "gajim"
    if app.is_flatpak():
        prefix = app.get_default_app_id()
    return f"{prefix}-status-{name}"


def get_account_tune_icon_name(account: str) -> str | None:
    client = app.get_client(account)
    tune = client.get_module("UserTune").get_current_tune()
    return None if tune is None else "lucide-music-symbolic"


def get_account_location_icon_name(account: str) -> str | None:
    client = app.get_client(account)
    location = client.get_module("UserLocation").get_current_location()
    return None if location is None else "lucide-map-pin-symbolic"
