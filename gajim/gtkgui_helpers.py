# Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
# Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
# Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
# Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
# Copyright (C) 2006-2007 Junglecow J <junglecow AT gmail.com>
# Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
# Copyright (C) 2007 James Newton <redshodan AT gmail.com>
#                    Julien Pivotto <roidelapluie AT gmail.com>
# Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
# Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
#
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
import math
import logging
from io import BytesIO

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Pango

try:
    from PIL import Image
except Exception:
    pass

from gajim.common import app

HAS_PYWIN32 = True
if os.name == 'nt':
    try:
        import win32file
        import win32con
        import pywintypes
    except ImportError:
        HAS_PYWIN32 = False

log = logging.getLogger('gajim.gtkgui_helpers')


def get_pixbuf_from_data(file_data):
    """
    Get image data and returns GdkPixbuf.Pixbuf
    """
    pixbufloader = GdkPixbuf.PixbufLoader()
    try:
        pixbufloader.write(file_data)
        pixbufloader.close()
        pixbuf = pixbufloader.get_pixbuf()
    except GLib.GError:
        pixbufloader.close()

        log.warning('loading avatar using pixbufloader failed, trying to '
                    'convert avatar image using pillow')
        try:
            avatar = Image.open(BytesIO(file_data)).convert("RGBA")
            array = GLib.Bytes.new(avatar.tobytes())
            width, height = avatar.size
            pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(
                array, GdkPixbuf.Colorspace.RGB,
                True, 8, width, height, width * 4)
        except Exception:
            log.warning('Could not use pillow to convert avatar image, '
                        'image cannot be displayed', exc_info=True)
            return

    return pixbuf

def file_is_locked(path_to_file):
    """
    Return True if file is locked

    NOTE: Windows only.
    """
    if os.name != 'nt': # just in case
        return

    if not HAS_PYWIN32:
        return

    secur_att = pywintypes.SECURITY_ATTRIBUTES()
    secur_att.Initialize()

    try:
        # try make a handle for READING the file
        hfile = win32file.CreateFile(
                path_to_file,                   # path to file
                win32con.GENERIC_READ,          # open for reading
                0,                              # do not share with other proc
                secur_att,
                win32con.OPEN_EXISTING,         # existing file only
                win32con.FILE_ATTRIBUTE_NORMAL, # normal file
                0                               # no attr. template
        )
    except pywintypes.error:
        return True
    else: # in case all went ok, close file handle (go to hell WinAPI)
        hfile.Close()
        return False

def get_possible_button_event(event):
    """
    Mouse or keyboard caused the event?
    """
    if event.type == Gdk.EventType.KEY_PRESS:
        return 0 # no event.button so pass 0
    # BUTTON_PRESS event, so pass event.button
    return event.button


def scale_with_ratio(size, width, height):
    if height == width:
        return size, size
    if height > width:
        ratio = height / float(width)
        return int(size / ratio), size

    ratio = width / float(height)
    return size, int(size / ratio)

def scale_pixbuf(pixbuf, size):
    width, height = scale_with_ratio(size,
                                     pixbuf.get_width(),
                                     pixbuf.get_height())
    return pixbuf.scale_simple(width, height,
                               GdkPixbuf.InterpType.BILINEAR)

def scale_pixbuf_from_data(data, size):
    pixbuf = get_pixbuf_from_data(data)
    return scale_pixbuf(pixbuf, size)

def label_set_autowrap(widget):
    """
    Make labels automatically re-wrap if their containers are resized.
    Accepts label or container widgets
    """
    if isinstance(widget, Gtk.Container):
        children = widget.get_children()
        for i in list(range(len(children))):
            label_set_autowrap(children[i])
    elif isinstance(widget, Gtk.Label):
        widget.set_line_wrap(True)
        widget.connect_after('size-allocate', __label_size_allocate)

def __label_size_allocate(widget, allocation):
    """
    Callback which re-allocates the size of a label
    """
    layout = widget.get_layout()

    lw_old, lh_old = layout.get_size()
    # fixed width labels
    if lw_old/Pango.SCALE == allocation.width:
        return

    # set wrap width to the Pango.Layout of the labels ###
    widget.set_alignment(0.0, 0.0)
    layout.set_width(allocation.width * Pango.SCALE)
    lh = layout.get_size()[1]

    if lh_old != lh:
        widget.set_size_request(-1, lh / Pango.SCALE)

def get_action(action):
    return app.app.lookup_action(action)

def add_css_to_widget(widget, css):
    provider = Gtk.CssProvider()
    provider.load_from_data(bytes(css.encode()))
    context = widget.get_style_context()
    context.add_provider(provider,
                         Gtk.STYLE_PROVIDER_PRIORITY_USER)
