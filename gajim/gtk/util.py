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

import os
import sys
import logging
import xml.etree.ElementTree as ET

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GLib

from gajim.common import app
from gajim.common import i18n
from gajim.common import configpaths

_icon_theme = Gtk.IconTheme.get_default()
_icon_theme.append_search_path(configpaths.get('ICONS'))

log = logging.getLogger('gajim.gtk.util')


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
    except GLib.GError as e:
        log.error('Unable to load icon %s: %s', icon_name, str(e))


def get_builder(file_name, widget=None):
    file_path = os.path.join(configpaths.get('GUI'), file_name)

    builder = Gtk.Builder()
    builder.set_translation_domain(i18n.DOMAIN)

    if sys.platform == "win32":
        # This is a workaround for non working translation on Windows
        tree = ET.parse(file_path)
        for node in tree.iter():
            if 'translatable' in node.attrib:
                node.text = _(node.text)
        xml_text = ET.tostring(tree.getroot(),
                               encoding='unicode',
                               method='xml')

        if widget is not None:
            builder.add_objects_from_string(xml_text, [widget])
        else:
            builder.add_from_string(xml_text, -1)
    else:
        if widget is not None:
            builder.add_objects_from_file(file_path, [widget])
        else:
            builder.add_from_file(file_path)
    return builder


def get_iconset_name_for(name):
    if name == 'not in roster':
        name = 'notinroster'
    iconset = app.config.get('iconset')
    if not iconset:
        iconset = app.config.DEFAULT_ICONSET
    return '%s-%s' % (iconset, name)


def get_total_screen_geometry():
    screen = Gdk.Screen.get_default()
    window = Gdk.Screen.get_root_window(screen)
    w, h = window.get_width(), window.get_height()
    log.debug('Get screen geometry: %s %s', w, h)
    return w, h


def resize_window(window, w, h):
    """
    Resize window, but also checks if huge window or negative values
    """
    screen_w, screen_h = get_total_screen_geometry()
    if not w or not h:
        return
    if w > screen_w:
        w = screen_w
    if h > screen_h:
        h = screen_h
    window.resize(abs(w), abs(h))


def move_window(window, x, y):
    """
    Move the window, but also check if out of screen
    """
    screen_w, screen_h = get_total_screen_geometry()
    if x < 0:
        x = 0
    if y < 0:
        y = 0
    w, h = window.get_size()
    if x + w > screen_w:
        x = screen_w - w
    if y + h > screen_h:
        y = screen_h - h
    window.move(x, y)


def get_completion_liststore(entry):
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


def get_cursor(attr):
    display = Gdk.Display.get_default()
    cursor = getattr(Gdk.CursorType, attr)
    return Gdk.Cursor.new_for_display(display, cursor)


def scroll_to_end(widget):
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


def at_the_end(widget):
    """Determines if a Scrollbar in a GtkScrolledWindow is at the end.

    Args:
        widget (GtkScrolledWindow)

    Returns:
        bool: The return value is True if at the end, False if not.
    """
    adj_v = widget.get_vadjustment()
    max_scroll_pos = adj_v.get_upper() - adj_v.get_page_size()
    at_the_end = (adj_v.get_value() == max_scroll_pos)
    return at_the_end


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


def python_month(month):
    return month + 1


def gtk_month(month):
    return month - 1
