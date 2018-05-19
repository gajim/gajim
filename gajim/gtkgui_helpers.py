# -*- coding:utf-8 -*-
## src/gtkgui_helpers.py
##
## Copyright (C) 2003-2014 Yann Leboulanger <asterix AT lagaule.org>
## Copyright (C) 2005-2006 Dimitur Kirov <dkirov AT gmail.com>
## Copyright (C) 2005-2007 Nikos Kouremenos <kourem AT gmail.com>
## Copyright (C) 2006 Travis Shirk <travis AT pobox.com>
## Copyright (C) 2006-2007 Junglecow J <junglecow AT gmail.com>
## Copyright (C) 2006-2008 Jean-Marie Traissard <jim AT lapin.org>
## Copyright (C) 2007 James Newton <redshodan AT gmail.com>
##                    Julien Pivotto <roidelapluie AT gmail.com>
## Copyright (C) 2007-2008 Stephan Erb <steve-e AT h3c.de>
## Copyright (C) 2008 Jonathan Schleifer <js-gajim AT webkeks.org>
##
## This file is part of Gajim.
##
## Gajim is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published
## by the Free Software Foundation; version 3 only.
##
## Gajim is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with Gajim. If not, see <http://www.gnu.org/licenses/>.
##

import xml.sax.saxutils
import gi
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Pango
import cairo
import os
import sys
import math
try:
    from PIL import Image
except:
    pass
from io import BytesIO

import logging
log = logging.getLogger('gajim.gtkgui_helpers')

from gajim.common import i18n
from gajim.common import app
from gajim.common import pep
from gajim.common import configpaths
from gajim.filechoosers import AvatarSaveDialog

gtk_icon_theme = Gtk.IconTheme.get_default()
gtk_icon_theme.append_search_path(configpaths.get('ICONS'))

class Color:
    BLACK = Gdk.RGBA(red=0, green=0, blue=0, alpha=1)
    GREEN = Gdk.RGBA(red=115/255, green=210/255, blue=22/255, alpha=1)
    RED = Gdk.RGBA(red=204/255, green=0, blue=0, alpha=1)
    GREY = Gdk.RGBA(red=195/255, green=195/255, blue=192/255, alpha=1)
    ORANGE = Gdk.RGBA(red=245/255, green=121/255, blue=0/255, alpha=1)

def get_icon_pixmap(icon_name, size=16, color=None, quiet=False):
    try:
        iconinfo = gtk_icon_theme.lookup_icon(icon_name, size, 0)
        if not iconinfo:
            raise GLib.GError
        if color:
            pixbuf, was_symbolic = iconinfo.load_symbolic(*color)
            return pixbuf
        return iconinfo.load_icon()
    except GLib.GError as e:
        if not quiet:
            log.error('Unable to load icon %s: %s' % (icon_name, str(e)))

def get_icon_path(icon_name, size=16):
    try:
        icon_info = gtk_icon_theme.lookup_icon(icon_name, size, 0)
        if icon_info == None:
            log.error('Icon not found: %s' % icon_name)
            return ""
        else:
            return icon_info.get_filename()
    except GLib.GError as e:
        log.error("Unable to find icon %s: %s" % (icon_name, str(e)))


HAS_PYWIN32 = True
if os.name == 'nt':
    try:
        import win32file
        import win32con
        import pywintypes
    except ImportError:
        HAS_PYWIN32 = False

from gajim.common import helpers

def get_total_screen_geometry():
    screen = Gdk.Screen.get_default()
    window = Gdk.Screen.get_root_window(screen)
    return window.get_width(), window.get_height()

def add_image_to_button(button, icon_name):
    img = Gtk.Image()
    path_img = get_icon_path(icon_name)
    img.set_from_file(path_img)
    button.set_image(img)

def get_image_button(icon_name, tooltip, toggle=False):
    if toggle:
        button = Gtk.ToggleButton()
        icon = get_icon_pixmap(icon_name)
        image = Gtk.Image()
        image.set_from_pixbuf(icon)
        button.set_image(image)
    else:
        button = Gtk.Button.new_from_icon_name(
            icon_name, Gtk.IconSize.MENU)
    button.set_tooltip_text(tooltip)
    return button

def get_gtk_builder(file_name, widget=None):
    file_path = os.path.join(configpaths.get('GUI'), file_name)
    builder = Gtk.Builder()
    builder.set_translation_domain(i18n.DOMAIN)
    if widget:
        builder.add_objects_from_file(file_path, [widget])
    else:
        builder.add_from_file(file_path)
    return builder

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

def get_theme_font_for_option(theme, option):
    """
    Return string description of the font, stored in theme preferences
    """
    font_name = app.config.get_per('themes', theme, option)
    font_desc = Pango.FontDescription()
    font_prop_str =  app.config.get_per('themes', theme, option + 'attrs')
    if font_prop_str:
        if font_prop_str.find('B') != -1:
            font_desc.set_weight(Pango.Weight.BOLD)
        if font_prop_str.find('I') != -1:
            font_desc.set_style(Pango.Style.ITALIC)
    fd = Pango.FontDescription(font_name)
    fd.merge(font_desc, True)
    return fd.to_string()

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


class ServersXMLHandler(xml.sax.ContentHandler):
    def __init__(self):
        xml.sax.ContentHandler.__init__(self)
        self.servers = []

    def startElement(self, name, attributes):
        if name == 'item':
            if 'jid' in attributes.getNames():
                self.servers.append(attributes.getValue('jid'))

    def endElement(self, name):
        pass

def parse_server_xml(path_to_file):
    try:
        handler = ServersXMLHandler()
        xml.sax.parse(path_to_file, handler)
        return handler.servers
    # handle exception if unable to open file
    except IOError as message:
        print(_('Error reading file:') + str(message), file=sys.stderr)
    # handle exception parsing file
    except xml.sax.SAXParseException as message:
        print(_('Error parsing file:') + str(message), file=sys.stderr)

def set_unset_urgency_hint(window, unread_messages_no):
    """
    Sets/unset urgency hint in window argument depending if we have unread
    messages or not
    """
    if app.config.get('use_urgency_hint'):
        if unread_messages_no > 0:
            window.props.urgency_hint = True
        else:
            window.props.urgency_hint = False

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

def get_cursor(attr):
    display = Gdk.Display.get_default()
    cursor = getattr(Gdk.CursorType, attr)
    return Gdk.Cursor.new_for_display(display, cursor)

def get_current_desktop(window):
    """
    Return the current virtual desktop for given window

    NOTE: Window is a GDK window.
    """
    prop = window.property_get('_NET_CURRENT_DESKTOP')
    if prop is None: # it means it's normal window (not root window)
        # so we look for it's current virtual desktop in another property
        prop = window.property_get('_NET_WM_DESKTOP')

    if prop is not None:
        # f.e. prop is ('CARDINAL', 32, [0]) we want 0 or 1.. from [0]
        current_virtual_desktop_no = prop[2][0]
        return current_virtual_desktop_no

def possibly_move_window_in_current_desktop(window):
    """
    Moves GTK window to current virtual desktop if it is not in the current
    virtual desktop

    NOTE: Window is a GDK window.
    """
    #TODO: property_get doesn't work:
    #prop_atom = Gdk.Atom.intern('_NET_CURRENT_DESKTOP', False)
    #type_atom = Gdk.Atom.intern("CARDINAL", False)
    #w = Gdk.Screen.get_default().get_root_window()
    #Gdk.property_get(w, prop_atom, type_atom, 0, 9999, False)
    return False
    if os.name == 'nt':
        return False

    root_window = Gdk.Screen.get_default().get_root_window()
    # current user's vd
    current_virtual_desktop_no = get_current_desktop(root_window)

    # vd roster window is in
    window_virtual_desktop = get_current_desktop(window.window)

    # if one of those is None, something went wrong and we cannot know
    # VD info, just hide it (default action) and not show it afterwards
    if None not in (window_virtual_desktop, current_virtual_desktop_no):
        if current_virtual_desktop_no != window_virtual_desktop:
            # we are in another VD that the window was
            # so show it in current VD
            window.present()
            return True
    return False

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

def get_fade_color(treeview, selected, focused):
    """
    Get a gdk RGBA color that is between foreground and background in 0.3
    0.7 respectively colors of the cell for the given treeview
    """
    context = treeview.get_style_context()
    if selected:
        if focused: # is the window focused?
            state = Gtk.StateFlags.SELECTED
        else: # is it not? NOTE: many gtk themes change bg on this
            state = Gtk.StateFlags.ACTIVE
    else:
        state = Gtk.StateFlags.NORMAL

    bg = context.get_property('background-color', state)
    fg = context.get_color(state)

    p = 0.3 # background
    q = 0.7 # foreground # p + q should do 1.0
    return Gdk.RGBA(bg.red*p + fg.red*q, bg.green*p + fg.green*q,
        bg.blue*p + fg.blue*q)

def make_gtk_month_python_month(month):
    """
    GTK starts counting months from 0, so January is 0 but Python's time start
    from 1, so align to Python

    NOTE: Month MUST be an integer.
    """
    return month + 1

def make_python_month_gtk_month(month):
    return month - 1

def make_pixbuf_grayscale(pixbuf):
    pixbuf2 = pixbuf.copy()
    pixbuf.saturate_and_pixelate(pixbuf2, 0.0, False)
    return pixbuf2

def get_possible_button_event(event):
    """
    Mouse or keyboard caused the event?
    """
    if event.type == Gdk.EventType.KEY_PRESS:
        return 0 # no event.button so pass 0
    # BUTTON_PRESS event, so pass event.button
    return event.button

def destroy_widget(widget):
    widget.destroy()

def scale_with_ratio(size, width, height):
    if height == width:
        return size, size
    if height > width:
        ratio = height / float(width)
        return int(size / ratio), size
    else:
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

def on_avatar_save_as_menuitem_activate(widget, avatar, default_name=''):
    from gajim import dialogs
    def on_continue(response, file_path):
        if response < 0:
            return

        app.config.set('last_save_dir', os.path.dirname(file_path))
        if isinstance(avatar, str):
            # We got a SHA
            pixbuf = app.interface.get_avatar(avatar)
        else:
            # We got a pixbuf
            pixbuf = avatar
        extension = os.path.splitext(file_path)[1]
        if not extension:
            # Silently save as Jpeg image
            image_format = 'png'
            file_path += '.png'
        else:
            image_format = extension[1:] # remove leading dot

        # Save image
        try:
            pixbuf.savev(file_path, image_format, [], [])
        except Exception as e:
            log.error('Error saving avatar: %s' % str(e))
            if os.path.exists(file_path):
                os.remove(file_path)
            new_file_path = '.'.join(file_path.split('.')[:-1]) + '.png'
            def on_ok(file_path, pixbuf):
                pixbuf.savev(file_path, 'png', [], [])
            dialogs.ConfirmationDialog(_('Extension not supported'),
                _('Image cannot be saved in %(type)s format. Save as '
                '%(new_filename)s?') % {'type': image_format,
                'new_filename': new_file_path},
                on_response_ok = (on_ok, new_file_path, pixbuf))

    def on_ok(file_path):
        if os.path.exists(file_path):
            # check if we have write permissions
            if not os.access(file_path, os.W_OK):
                file_name = os.path.basename(file_path)
                dialogs.ErrorDialog(_('Cannot overwrite existing file "%s"') % \
                    file_name, _('A file with this name already exists and you '
                    'do not have permission to overwrite it.'))
                return
            dialog2 = dialogs.FTOverwriteConfirmationDialog(
                _('This file already exists'), _('What do you want to do?'),
                propose_resume=False, on_response=(on_continue, file_path))
            dialog2.set_destroy_with_parent(True)
        else:
            dirname = os.path.dirname(file_path)
            if not os.access(dirname, os.W_OK):
                dialogs.ErrorDialog(_('Directory "%s" is not writable') % \
                    dirname, _('You do not have permission to create files in '
                    'this directory.'))
                return

        on_continue(0, file_path)

    transient = app.app.get_active_window()
    AvatarSaveDialog(on_ok,
                     path=app.config.get('last_save_dir'),
                     file_name='%s.png' % default_name,
                     transient_for=transient)

def create_combobox(value_list, selected_value = None):
    """
    Value_list is [(label1, value1)]
    """
    liststore = Gtk.ListStore(str, str)
    combobox = Gtk.ComboBox.new_with_model(liststore)
    cell = Gtk.CellRendererText()
    combobox.pack_start(cell, True)
    combobox.add_attribute(cell, 'text', 0)
    i = -1
    for value in value_list:
        liststore.append(value)
        if selected_value == value[1]:
            i = value_list.index(value)
    if i > -1:
        combobox.set_active(i)
    combobox.show_all()
    return combobox

def create_list_multi(value_list, selected_values=None):
    """
    Value_list is [(label1, value1)]
    """
    liststore = Gtk.ListStore(str, str)
    treeview = Gtk.TreeView.new_with_model(liststore)
    treeview.get_selection().set_mode(Gtk.SelectionMode.MULTIPLE)
    treeview.set_headers_visible(False)
    col = Gtk.TreeViewColumn()
    treeview.append_column(col)
    cell = Gtk.CellRendererText()
    col.pack_start(cell, True)
    col.set_attributes(cell, text=0)
    for value in value_list:
        iter = liststore.append(value)
        if value[1] in selected_values:
            treeview.get_selection().select_iter(iter)
    treeview.show_all()
    return treeview

def load_iconset(path, pixbuf2=None, transport=False):
    """
    Load full iconset from the given path, and add pixbuf2 on top left of each
    static images
    """
    path += '/'
    if transport:
        list_ = ('online', 'chat', 'away', 'xa', 'dnd', 'offline',
                'not in roster')
    else:
        list_ = ('connecting', 'online', 'chat', 'away', 'xa', 'dnd',
                'invisible', 'offline', 'error', 'requested', 'event', 'opened',
                'closed', 'not in roster', 'muc_active', 'muc_inactive')
        if pixbuf2:
            list_ = ('connecting', 'online', 'chat', 'away', 'xa', 'dnd',
                    'offline', 'error', 'requested', 'event', 'not in roster')
    return _load_icon_list(list_, path, pixbuf2)

def load_mood_icon(icon_name):
    """
    Load an icon from the mood iconset in 16x16
    """
    iconset = app.config.get('mood_iconset')
    path = os.path.join(helpers.get_mood_iconset_path(iconset), '')
    icon_list = _load_icon_list([icon_name], path)
    return icon_list[icon_name]

def load_activity_icon(category, activity = None):
    """
    Load an icon from the activity iconset in 16x16
    """
    iconset = app.config.get('activity_iconset')
    path = os.path.join(helpers.get_activity_iconset_path(iconset),
            category, '')
    if activity is None:
        activity = 'category'
    icon_list = _load_icon_list([activity], path)
    return icon_list[activity]

def get_pep_as_pixbuf(pep_class):
    if isinstance(pep_class, pep.UserMoodPEP):
        assert not pep_class._retracted
        received_mood = pep_class._pep_specific_data['mood']
        mood = received_mood if received_mood in pep.MOODS else 'unknown'
        pixbuf = load_mood_icon(mood).get_pixbuf()
        return pixbuf
    elif isinstance(pep_class, pep.UserTunePEP):
        icon = get_icon_pixmap('audio-x-generic', quiet=True)
        if not icon:
            path = os.path.join(configpaths.get('DATA'), 'emoticons', 'static',
                'music.png')
            return GdkPixbuf.Pixbuf.new_from_file(path)
        return icon
    elif isinstance(pep_class, pep.UserActivityPEP):
        assert not pep_class._retracted
        pep_ = pep_class._pep_specific_data
        activity = pep_['activity']

        has_known_activity = activity in pep.ACTIVITIES
        has_known_subactivity = (has_known_activity  and ('subactivity' in pep_)
                and (pep_['subactivity'] in pep.ACTIVITIES[activity]))

        if has_known_activity:
            if has_known_subactivity:
                subactivity = pep_['subactivity']
                return load_activity_icon(activity, subactivity).get_pixbuf()
            else:
                return load_activity_icon(activity).get_pixbuf()
        else:
            return load_activity_icon('unknown').get_pixbuf()
    elif isinstance(pep_class, pep.UserLocationPEP):
        icon = get_icon_pixmap('applications-internet', quiet=True)
        if not icon:
            icon = get_icon_pixmap('gajim-earth')
        return icon
    return None

def get_iconset_name_for(name):
    if name == 'not in roster':
        name = 'notinroster'
    iconset = app.config.get('iconset')
    if not iconset:
        iconset = app.config.DEFAULT_ICONSET
    return '%s-%s' % (iconset, name)

def load_icons_meta():
    """
    Load and return  - AND + small icons to put on top left of an icon for meta
    contacts
    """
    iconset = app.config.get('iconset')
    path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
    # try to find opened_meta.png file, else opened.png else nopixbuf merge
    path_opened = os.path.join(path, 'opened_meta.png')
    if not os.path.isfile(path_opened):
        path_opened = os.path.join(path, 'opened.png')
    if os.path.isfile(path_opened):
        pixo = GdkPixbuf.Pixbuf.new_from_file(path_opened)
    else:
        pixo = None
    # Same thing for closed
    path_closed = os.path.join(path, 'opened_meta.png')
    if not os.path.isfile(path_closed):
        path_closed = os.path.join(path, 'closed.png')
    if os.path.isfile(path_closed):
        pixc = GdkPixbuf.Pixbuf.new_from_file(path_closed)
    else:
        pixc = None
    return pixo, pixc

def _load_icon_list(icons_list, path, pixbuf2 = None):
    """
    Load icons in icons_list from the given path, and add pixbuf2 on top left of
    each static images
    """
    imgs = {}
    for icon in icons_list:
        # try to open a pixfile with the correct method
        icon_file = icon.replace(' ', '_')
        files = []
        files.append(path + icon_file + '.gif')
        files.append(path + icon_file + '.png')
        image = Gtk.Image()
        image.show()
        imgs[icon] = image
        for file_ in files: # loop seeking for either gif or png
            if os.path.exists(file_):
                image.set_from_file(file_)
                if pixbuf2 and image.get_storage_type() == Gtk.ImageType.PIXBUF:
                    # add pixbuf2 on top-left corner of image
                    pixbuf1 = image.get_pixbuf()
                    pixbuf2.composite(pixbuf1, 0, 0,
                            pixbuf2.get_property('width'),
                            pixbuf2.get_property('height'), 0, 0, 1.0, 1.0,
                            GdkPixbuf.InterpType.NEAREST, 255)
                    image.set_from_pixbuf(pixbuf1)
                break
    return imgs

def make_jabber_state_images():
    """
    Initialize jabber_state_images dictionary
    """
    iconset = app.config.get('iconset')
    if iconset:
        if helpers.get_iconset_path(iconset):
            path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
            if not os.path.exists(path):
                iconset = app.config.DEFAULT_ICONSET
                app.config.set('iconset', iconset)
        else:
            iconset = app.config.DEFAULT_ICONSET
            app.config.set('iconset', iconset)
    else:
        iconset = app.config.DEFAULT_ICONSET
        app.config.set('iconset', iconset)

    path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
    app.interface.jabber_state_images['16'] = load_iconset(path)

    pixo, pixc = load_icons_meta()
    app.interface.jabber_state_images['opened'] = load_iconset(path, pixo)
    app.interface.jabber_state_images['closed'] = load_iconset(path, pixc)

    path = os.path.join(helpers.get_iconset_path(iconset), '32x32')
    app.interface.jabber_state_images['32'] = load_iconset(path)

    path = os.path.join(helpers.get_iconset_path(iconset), '24x24')
    if (os.path.exists(path)):
        app.interface.jabber_state_images['24'] = load_iconset(path)
    else:
        # Resize 32x32 icons to 24x24
        for each in app.interface.jabber_state_images['32']:
            img = Gtk.Image()
            pix = app.interface.jabber_state_images['32'][each]
            pix_type = pix.get_storage_type()
            if pix_type == Gtk.ImageType.ANIMATION:
                animation = pix.get_animation()
                pixbuf = animation.get_static_image()
            elif pix_type == Gtk.ImageType.EMPTY:
                pix = app.interface.jabber_state_images['16'][each]
                pix_16_type = pix.get_storage_type()
                if pix_16_type == Gtk.ImageType.ANIMATION:
                    animation = pix.get_animation()
                    pixbuf = animation.get_static_image()
                else:
                    pixbuf = pix.get_pixbuf()
            else:
                pixbuf = pix.get_pixbuf()
            scaled_pix = pixbuf.scale_simple(24, 24, GdkPixbuf.InterpType.BILINEAR)
            img.set_from_pixbuf(scaled_pix)
            app.interface.jabber_state_images['24'][each] = img

def reload_jabber_state_images():
    make_jabber_state_images()
    app.interface.roster.update_jabber_state_images()

def label_set_autowrap(widget):
    """
    Make labels automatically re-wrap if their containers are resized.
    Accepts label or container widgets
    """
    if isinstance (widget, Gtk.Container):
        children = widget.get_children()
        for i in list(range (len (children))):
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
    layout.set_width (allocation.width * Pango.SCALE)
    lh = layout.get_size()[1]

    if lh_old != lh:
        widget.set_size_request (-1, lh / Pango.SCALE)

def get_action(action):
    return app.app.lookup_action(action)

def load_css():
    path = os.path.join(configpaths.get('DATA'), 'style', 'gajim.css')
    try:
        with open(path, "r") as f:
            css = f.read()
    except Exception as exc:
        print('Error loading css: %s', exc)
        return

    provider = Gtk.CssProvider()
    css = "\n".join((css, convert_config_to_css()))
    provider.load_from_data(bytes(css.encode()))
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

def convert_config_to_css():
    css = ''
    themed_widgets = {
        'ChatControl-BannerEventBox': ('bannerbgcolor', 'background'),
        'ChatControl-BannerNameLabel': ('bannertextcolor', 'color'),
        'ChatControl-BannerLabel': ('bannertextcolor', 'color'),
        'GroupChatControl-BannerEventBox': ('bannerbgcolor', 'background'),
        'GroupChatControl-BannerNameLabel': ('bannertextcolor', 'color'),
        'GroupChatControl-BannerLabel': ('bannertextcolor', 'color'),
        'Discovery-BannerEventBox': ('bannerbgcolor', 'background'),
        'Discovery-BannerLabel': ('bannertextcolor', 'color')}

    classes = {'state_composing_color': ('', 'color'),
               'state_inactive_color': ('', 'color'),
               'state_gone_color': ('', 'color'),
               'state_paused_color': ('', 'color'),
               'msgcorrectingcolor': ('text', 'background'),
               'state_muc_directed_msg_color': ('', 'color'),
               'state_muc_msg_color': ('', 'color')}


    theme = app.config.get('roster_theme')
    for key, values in themed_widgets.items():
        config, attr = values
        css += '#{} {{'.format(key)
        value = app.config.get_per('themes', theme, config)
        if value:
            css += '{attr}: {color};\n'.format(attr=attr, color=value)
        css += '}\n'

    for key, values in classes.items():
        node, attr = values
        value = app.config.get_per('themes', theme, key)
        if value:
            css += '.theme_{cls} {node} {{ {attr}: {color}; }}\n'.format(
                cls=key, node=node, attr=attr, color=value)

    css += add_css_font()

    return css

def add_css_class(widget, class_name):
    style = widget.get_style_context()
    for css_cls in style.list_classes():
        if css_cls.startswith('theme_'):
            style.remove_class(css_cls)
    if class_name:
        style.add_class('theme_' + class_name)

def add_css_to_widget(widget, css):
    provider = Gtk.CssProvider()
    provider.load_from_data(bytes(css.encode()))
    context = widget.get_style_context()
    context.add_provider(provider,
                         Gtk.STYLE_PROVIDER_PRIORITY_USER)

def remove_css_class(widget, class_name):
    style = widget.get_style_context()
    style.remove_class('theme_' + class_name)

def add_css_font():
    conversation_font = app.config.get('conversation_font')
    if not conversation_font:
        return ''
    font = Pango.FontDescription(conversation_font)
    unit = "pt" if Gtk.check_version(3, 22, 0) is None else "px"
    css = """
    .font_custom {{
      font-family: "{family}";
      font-size: {size}{unit};
      font-weight: {weight};
    }}""".format(
        family=font.get_family(),
        size=int(round(font.get_size() / Pango.SCALE)),
        unit=unit,
        weight=pango_to_css_weight(font.get_weight()))
    css = css.replace("font-size: 0{unit};".format(unit=unit), "")
    css = css.replace("font-weight: 0;", "")
    css = "\n".join(filter(lambda x: x.strip(), css.splitlines()))
    return css

def draw_affiliation(surface, affiliation):
    icon_size = 16
    size = 4 * 1
    if affiliation not in ('owner', 'admin', 'member'):
        return
    ctx = cairo.Context(surface)
    ctx.rectangle(icon_size-size, icon_size-size, size, size)
    if affiliation == 'owner':
        ctx.set_source_rgb(204/255, 0, 0)
    elif affiliation == 'admin':
        ctx.set_source_rgb(255/255, 140/255, 0)
    elif affiliation == 'member':
        ctx.set_source_rgb(0, 255/255, 0)
    ctx.fill()

def get_image_from_icon_name(icon_name, scale):
    icon = get_iconset_name_for(icon_name)
    surface = gtk_icon_theme.load_surface(icon, 16, scale, None, 0)
    return Gtk.Image.new_from_surface(surface)

def pango_to_css_weight(number):
    # Pango allows for weight values between 100 and 1000
    # CSS allows only full hundred numbers like 100, 200 ..
    number = int(number)
    if number < 100:
        return 100
    if number > 900:
        return 900
    return int(math.ceil(number / 100.0)) * 100
