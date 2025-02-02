# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from functools import lru_cache

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import GtkSource
from nbxmpp import util as nbxmpp_util

from gajim.common import app
from gajim.common import types
from gajim.common.modules.contacts import GroupchatParticipant


def text_to_color(text: str) -> tuple[float, float, float]:
    if app.css_config.prefer_dark:
        lightness = 60
    else:
        lightness = 40
    return nbxmpp_util.text_to_color(text, 100, lightness)


def get_contact_color(contact: types.ChatContactT) -> tuple[float, float, float]:

    if isinstance(contact, GroupchatParticipant):
        if contact.room.muc_context in (None, "public"):
            return text_to_color(contact.name)

        if contact.real_jid is not None:
            return text_to_color(str(contact.real_jid))

    return text_to_color(str(contact.jid))


def get_color_for_account(account: str) -> str:
    col_r, col_g, col_b = text_to_color(account)
    rgba = Gdk.RGBA()
    rgba.red = col_r
    rgba.green = col_g
    rgba.blue = col_b
    rgba.alpha = 1
    return rgba.to_string()


def convert_rgba_to_hex(rgba: Gdk.RGBA) -> str:
    red = int(rgba.red * 255)
    green = int(rgba.green * 255)
    blue = int(rgba.blue * 255)
    return f"#{red:02x}{green:02x}{blue:02x}"


@lru_cache(maxsize=1024)
def convert_rgb_string_to_float(rgb_string: str) -> tuple[float, float, float]:
    rgba = Gdk.RGBA()
    rgba.parse(rgb_string)
    return (rgba.red, rgba.green, rgba.blue)


def rgba_to_float(rgba: Gdk.RGBA) -> tuple[float, float, float]:
    return (rgba.red, rgba.green, rgba.blue)


def make_rgba(color_string: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.parse(color_string)
    return rgba


@lru_cache(maxsize=16)
def get_css_show_class(show: str) -> str:
    if show in ("online", "chat"):
        return ".gajim-status-online"
    if show == "away":
        return ".gajim-status-away"
    if show in ("dnd", "xa"):
        return ".gajim-status-dnd"
    if show == "connecting":
        return ".gajim-status-connecting"
    return ".gajim-status-offline"


def add_css_to_widget(widget: Gtk.Widget, css: str) -> None:
    provider = Gtk.CssProvider()
    provider.load_from_bytes(GLib.Bytes.new(css.encode("utf-8")))
    context = widget.get_style_context()
    context.add_provider(provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)


def get_source_view_style_scheme() -> GtkSource.StyleScheme | None:
    style_scheme_manager = GtkSource.StyleSchemeManager.get_default()
    if app.css_config.prefer_dark:
        return style_scheme_manager.get_scheme("solarized-dark")
    return style_scheme_manager.get_scheme("solarized-light")
