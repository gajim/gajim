# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from typing import Any
from typing import List
from typing import Tuple


import os
import sys
import logging
import xml.etree.ElementTree as ET

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib

from gajim.common import app
from gajim.common import configpaths
from gajim.common import i18n
from gajim.common.i18n import _

_icon_theme = Gtk.IconTheme.get_default()
_icon_theme.append_search_path(configpaths.get('ICONS'))

log = logging.getLogger('gajim.gtk.util')


class Builder:
    def __init__(self,
                 filename: str,
                 widgets: List[str] = None,
                 domain: str = None,
                 gettext_: Any = None) -> None:
        self._builder = Gtk.Builder()

        if domain is None:
            domain = i18n.DOMAIN
        self._builder.set_translation_domain(domain)

        if gettext_ is None:
            gettext_ = _

        file_path = os.path.join(configpaths.get('GUI'), filename)

        if sys.platform == "win32":
            # This is a workaround for non working translation on Windows
            tree = ET.parse(file_path)
            for node in tree.iter():
                if 'translatable' in node.attrib and node.text is not None:
                    node.text = gettext_(node.text)

            xml_text = ET.tostring(tree.getroot(),
                                   encoding='unicode',
                                   method='xml')

            if widgets is not None:
                self._builder.add_objects_from_string(xml_text, widgets)
            else:
                # Workaround
                # https://gitlab.gnome.org/GNOME/pygobject/issues/255
                Gtk.Builder.__mro__[1].add_from_string(
                    self._builder, xml_text, len(xml_text.encode("utf-8")))
        else:
            if widgets is not None:
                self._builder.add_objects_from_file(file_path, widgets)
            else:
                self._builder.add_from_file(file_path)

    def __getattr__(self, name):
        try:
            return getattr(self._builder, name)
        except AttributeError:
            return self._builder.get_object(name)


def get_builder(file_name: str, widgets: List[str] = None) -> Builder:
    return Builder(file_name, widgets)


def load_icon(icon_name, widget, size=16, pixbuf=False,
              flags=Gtk.IconLookupFlags.FORCE_SIZE):

    scale = widget.get_scale_factor()
    if not scale:
        log.warning('Could not determine scale factor')
        scale = 1

    try:
        iconinfo = _icon_theme.lookup_icon_for_scale(
            icon_name, size, scale, flags)
        if pixbuf:
            return iconinfo.load_icon()
        return iconinfo.load_surface(None)
    except GLib.GError as error:
        log.error('Unable to load icon %s: %s', icon_name, str(error))


def get_iconset_name_for(name: str) -> str:
    if name == 'not in roster':
        name = 'notinroster'
    iconset = app.config.get('iconset')
    if not iconset:
        iconset = app.config.DEFAULT_ICONSET
    return '%s-%s' % (iconset, name)


def get_total_screen_geometry() -> Tuple[int, int]:
    screen = Gdk.Screen.get_default()
    window = Gdk.Screen.get_root_window(screen)
    width, height = window.get_width(), window.get_height()
    log.debug('Get screen geometry: %s %s', width, height)
    return width, height


def resize_window(window: Gtk.Window, width: int, height: int) -> None:
    """
    Resize window, but also checks if huge window or negative values
    """
    screen_w, screen_h = get_total_screen_geometry()
    if not width or not height:
        return
    if width > screen_w:
        width = screen_w
    if height > screen_h:
        height = screen_h
    window.resize(abs(width), abs(height))


def move_window(window: Gtk.Window, pos_x: int, pos_y: int) -> None:
    """
    Move the window, but also check if out of screen
    """
    screen_w, screen_h = get_total_screen_geometry()
    if pos_x < 0:
        pos_x = 0
    if pos_y < 0:
        pos_y = 0
    width, height = window.get_size()
    if pos_x + width > screen_w:
        pos_x = screen_w - width
    if pos_y + height > screen_h:
        pos_y = screen_h - height
    window.move(pos_x, pos_y)


def get_completion_liststore(entry: Gtk.Entry) -> Gtk.ListStore:
    """
    Create a completion model for entry widget completion list consists of
    (Pixbuf, Text) rows
    """
    completion = Gtk.EntryCompletion()
    liststore = Gtk.ListStore(str, str)

    render_pixbuf = Gtk.CellRendererPixbuf()
    completion.pack_start(render_pixbuf, False)
    completion.add_attribute(render_pixbuf, 'icon_name', 0)

    render_text = Gtk.CellRendererText()
    completion.pack_start(render_text, True)
    completion.add_attribute(render_text, 'text', 1)
    completion.set_property('text_column', 1)
    completion.set_model(liststore)
    entry.set_completion(completion)
    return liststore


def get_cursor(attr: str) -> Gdk.Cursor:
    display = Gdk.Display.get_default()
    cursor = getattr(Gdk.CursorType, attr)
    return Gdk.Cursor.new_for_display(display, cursor)


def scroll_to_end(widget: Gtk.ScrolledWindow) -> bool:
    """Scrolls to the end of a GtkScrolledWindow.

    Args:
        widget (GtkScrolledWindow)

    Returns:
        bool: The return value is False so it can be used with GLib.idle_add.
    """
    adj_v = widget.get_vadjustment()
    if adj_v is None:
        # This can happen when the Widget is already destroyed when called
        # from GLib.idle_add
        return False
    max_scroll_pos = adj_v.get_upper() - adj_v.get_page_size()
    adj_v.set_value(max_scroll_pos)

    adj_h = widget.get_hadjustment()
    adj_h.set_value(0)
    return False


def at_the_end(widget: Gtk.ScrolledWindow) -> bool:
    """Determines if a Scrollbar in a GtkScrolledWindow is at the end.

    Args:
        widget (GtkScrolledWindow)

    Returns:
        bool: The return value is True if at the end, False if not.
    """
    adj_v = widget.get_vadjustment()
    max_scroll_pos = adj_v.get_upper() - adj_v.get_page_size()
    return adj_v.get_value() == max_scroll_pos


def get_image_button(icon_name, tooltip, toggle=False):
    if toggle:
        button = Gtk.ToggleButton()
        image = Gtk.Image.new_from_icon_name(icon_name, Gtk.IconSize.MENU)
        button.set_image(image)
    else:
        button = Gtk.Button.new_from_icon_name(
            icon_name, Gtk.IconSize.MENU)
    button.set_tooltip_text(tooltip)
    return button


def python_month(month: int) -> int:
    return month + 1


def gtk_month(month: int) -> int:
    return month - 1


def convert_rgb_to_hex(rgb_string: str) -> str:
    rgb = Gdk.RGBA()
    rgb.parse(rgb_string)
    rgb.to_color()

    red = int(rgb.red * 255)
    green = int(rgb.green * 255)
    blue = int(rgb.blue * 255)
    return '#%02x%02x%02x' % (red, green, blue)


def get_primary_accel_mod():
    """
    Returns the primary Gdk.ModifierType modifier.
    cmd on osx, ctrl everywhere else.
    """
    return Gtk.accelerator_parse("<Primary>")[1]


def get_hardware_key_codes(keyval):
    keymap = Gdk.Keymap.get_for_display(Gdk.Display.get_default())

    valid, key_map_keys = keymap.get_entries_for_keyval(keyval)
    if not valid:
        return []
    return [key.keycode for key in key_map_keys]
