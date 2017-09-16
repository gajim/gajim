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
import os
import sys
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

gtk_icon_theme = Gtk.IconTheme.get_default()
gtk_icon_theme.append_search_path(app.ICONS_DIR)

class Color:
    BLACK = Gdk.RGBA(red=0, green=0, blue=0, alpha=1)
    GREEN = Gdk.RGBA(red=115/255, green=210/255, blue=22/255, alpha=1)
    RED = Gdk.RGBA(red=204/255, green=0, blue=0, alpha=1)

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

from gajim import vcard
from gajim import dialogs


HAS_PYWIN32 = True
if os.name == 'nt':
    try:
        import win32file
        import win32con
        import pywintypes
    except ImportError:
        HAS_PYWIN32 = False

from gajim.common import helpers

screen_w = Gdk.Screen.width()
screen_h = Gdk.Screen.height()

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
    button.set_tooltip_text(_(tooltip))
    return button

GUI_DIR = os.path.join(app.DATA_DIR, 'gui')
def get_gtk_builder(file_name, widget=None):
    file_path = os.path.join(GUI_DIR, file_name)
    builder = Gtk.Builder()
    builder.set_translation_domain(i18n.APP)
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
    liststore = Gtk.ListStore(GdkPixbuf.Pixbuf, str)

    render_pixbuf = Gtk.CellRendererPixbuf()
    completion.pack_start(render_pixbuf, False)
    completion.add_attribute(render_pixbuf, 'pixbuf', 0)

    render_text = Gtk.CellRendererText()
    completion.pack_start(render_text, True)
    completion.add_attribute(render_text, 'text', 1)
    completion.set_property('text_column', 1)
    completion.set_model(liststore)
    entry.set_completion(completion)
    return liststore


def popup_emoticons_under_button(menu, button, parent_win):
    """
    Popup the emoticons menu under button, which is in parent_win
    """
    window_x1, window_y1 = parent_win.get_origin()[1:]

    def position_menu_under_button(menu, _x=None, _y=None, data=None):
        # inline function, which will not keep refs, when used as CB
        alloc = button.get_allocation()
        button_x, button_y = alloc.x, alloc.y
        translated_coordinates = button.translate_coordinates(
            app.interface.roster.window, 0, 0)
        if translated_coordinates:
            button_x, button_y = translated_coordinates

        # now convert them to X11-relative
        window_x, window_y = window_x1, window_y1
        x = window_x + button_x
        y = window_y + button_y

        menu_height = menu.get_preferred_size()[0].height

        ## should we pop down or up?
        if (y + alloc.height + menu_height < Gdk.Screen.height()):
            # now move the menu below the button
            y += alloc.height
        else:
            # now move the menu above the button
            y -= menu_height

        # push_in is True so all the menuitems are always inside screen
        push_in = True
        return (x, y, push_in)

    menu.popup(None, None, position_menu_under_button, None, 1, 0)

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

# feeding the image directly into the pixbuf seems possible, but is error prone and causes image distortions and segfaults.
# see http://stackoverflow.com/a/8892894/3528174
# and https://developer.gnome.org/gdk-pixbuf/unstable/gdk-pixbuf-Image-Data-in-Memory.html#gdk-pixbuf-new-from-bytes
# to learn how this could be done (or look into the mercurial history)
def get_pixbuf_from_data(file_data, want_type = False):
    """
    Get image data and returns GdkPixbuf.Pixbuf if want_type is True it also
    returns 'jpeg', 'png' etc
    """
    pixbufloader = GdkPixbuf.PixbufLoader()
    try:
        pixbufloader.write(file_data)
        pixbufloader.close()
        pixbuf = pixbufloader.get_pixbuf()
    except GLib.GError: # 'unknown image format'
        pixbufloader.close()

        # try to open and convert this image to png using pillow (if available)
        log.debug("loading avatar using pixbufloader failed, trying to convert avatar image using pillow (if available)")
        try:
            avatar = Image.open(BytesIO(file_data)).convert("RGBA")
            arr = GLib.Bytes.new(avatar.tobytes())
            width, height = avatar.size
            pixbuf = GdkPixbuf.Pixbuf.new_from_bytes(arr, GdkPixbuf.Colorspace.RGB, True, 8, width, height, width * 4)
        except:
            log.info("Could not use pillow to convert avatar image, image cannot be displayed")
            if want_type:
                return None, None
            else:
                return None

    if want_type:
        typ = pixbufloader.get_format() and pixbufloader.get_format().get_name() or None
        return pixbuf, typ
    else:
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
    bg = context.get_background_color(state)
    fg = context.get_color(state)

    p = 0.3 # background
    q = 0.7 # foreground # p + q should do 1.0
    return Gdk.RGBA(bg.red*p + fg.red*q, bg.green*p + fg.green*q,
        bg.blue*p + fg.blue*q)

def get_scaled_pixbuf_by_size(pixbuf, width, height):
    # Pixbuf size
    pix_width = pixbuf.get_width()
    pix_height = pixbuf.get_height()
    # don't make avatars bigger than they are
    if pix_width < width and pix_height < height:
        return pixbuf # we don't want to make avatar bigger

    ratio = float(pix_width) / float(pix_height)
    if ratio > 1:
        w = width
        h = int(w / ratio)
    else:
        h = height
        w = int(h * ratio)
    scaled_buf = pixbuf.scale_simple(w, h, GdkPixbuf.InterpType.HYPER)
    return scaled_buf

def get_scaled_pixbuf(pixbuf, kind):
    """
    Return scaled pixbuf, keeping ratio etc or None kind is either "chat",
    "roster", "notification", "tooltip", "vcard"
    """
    # resize to a width / height for the avatar not to have distortion
    # (keep aspect ratio)
    width = app.config.get(kind + '_avatar_width')
    height = app.config.get(kind + '_avatar_height')
    if width < 1 or height < 1:
        return None

    return get_scaled_pixbuf_by_size(pixbuf, width, height)

def get_avatar_pixbuf_from_cache(fjid, use_local=True):
    """
    Check if jid has cached avatar and if that avatar is valid image (can be
    shown)

    Returns None if there is no image in vcard/
    Returns 'ask' if cached vcard should not be used (user changed his vcard, so
    we have new sha) or if we don't have the vcard
    """
    jid, nick = app.get_room_and_nick_from_fjid(fjid)
    if app.config.get('hide_avatar_of_transport') and\
            app.jid_is_transport(jid):
        # don't show avatar for the transport itself
        return None

    if any(jid in app.contacts.get_gc_list(acc) for acc in \
    app.contacts.get_accounts()):
        is_groupchat_contact = True
    else:
        is_groupchat_contact = False

    puny_jid = helpers.sanitize_filename(jid)
    if is_groupchat_contact:
        puny_nick = helpers.sanitize_filename(nick)
        path = os.path.join(app.VCARD_PATH, puny_jid, puny_nick)
        local_avatar_basepath = os.path.join(app.AVATAR_PATH, puny_jid,
                puny_nick) + '_local'
    else:
        path = os.path.join(app.VCARD_PATH, puny_jid)
        local_avatar_basepath = os.path.join(app.AVATAR_PATH, puny_jid) + \
                '_local'
    if use_local:
        for extension in ('.png', '.jpeg'):
            local_avatar_path = local_avatar_basepath + extension
            if os.path.isfile(local_avatar_path):
                avatar_file = open(local_avatar_path, 'rb')
                avatar_data = avatar_file.read()
                avatar_file.close()
                return get_pixbuf_from_data(avatar_data)

    if not os.path.isfile(path):
        return 'ask'

    vcard_dict = list(app.connections.values())[0].get_cached_vcard(fjid,
            is_groupchat_contact)
    if not vcard_dict: # This can happen if cached vcard is too old
        return 'ask'
    if 'PHOTO' not in vcard_dict:
        return None
    pixbuf = vcard.get_avatar_pixbuf_encoded_mime(vcard_dict['PHOTO'])[0]
    return pixbuf

def make_gtk_month_python_month(month):
    """
    GTK starts counting months from 0, so January is 0 but Python's time start
    from 1, so align to Python

    NOTE: Month MUST be an integer.
    """
    return month + 1

def make_python_month_gtk_month(month):
    return month - 1

def make_color_string(color):
    """
    Create #aabbcc color string from gtk color
    """
    col = '#'
    for i in ('red', 'green', 'blue'):
        h = hex(int(getattr(color, i) / (16*16)))
        h = h.split('x')[1]
        if len(h) == 1:
            h = '0' + h
        col += h
    return col

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

def on_avatar_save_as_menuitem_activate(widget, jid, default_name=''):
    def on_continue(response, file_path):
        if response < 0:
            return
        pixbuf = get_avatar_pixbuf_from_cache(jid)
        extension = os.path.splitext(file_path)[1]
        if not extension:
            # Silently save as Jpeg image
            image_format = 'jpeg'
            file_path += '.jpeg'
        elif extension == 'jpg':
            image_format = 'jpeg'
        else:
            image_format = extension[1:] # remove leading dot

        # Save image
        try:
            pixbuf.savev(file_path, image_format, [], [])
        except Exception as e:
            log.debug('Error saving avatar: %s' % str(e))
            if os.path.exists(file_path):
                os.remove(file_path)
            new_file_path = '.'.join(file_path.split('.')[:-1]) + '.jpeg'
            def on_ok(file_path, pixbuf):
                pixbuf.savev(file_path, 'jpeg', [], [])
            dialogs.ConfirmationDialog(_('Extension not supported'),
                _('Image cannot be saved in %(type)s format. Save as '
                '%(new_filename)s?') % {'type': image_format,
                'new_filename': new_file_path},
                on_response_ok = (on_ok, new_file_path, pixbuf))
        else:
            dialog.destroy()

    def on_ok(widget):
        file_path = dialog.get_filename()
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
                propose_resume=False, on_response=(on_continue, file_path),
                transient_for=dialog)
            dialog2.set_destroy_with_parent(True)
        else:
            dirname = os.path.dirname(file_path)
            if not os.access(dirname, os.W_OK):
                dialogs.ErrorDialog(_('Directory "%s" is not writable') % \
                    dirname, _('You do not have permission to create files in '
                    'this directory.'))
                return

        on_continue(0, file_path)

    def on_cancel(widget):
        dialog.destroy()

    dialog = dialogs.FileChooserDialog(title_text=_('Save Image as…'),
        action=Gtk.FileChooserAction.SAVE, buttons=(Gtk.STOCK_CANCEL,
        Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK),
        default_response=Gtk.ResponseType.OK,
        current_folder=app.config.get('last_save_dir'), on_response_ok=on_ok,
        on_response_cancel=on_cancel)

    dialog.set_current_name(default_name + '.jpeg')
    dialog.connect('delete-event', lambda widget, event:
        on_cancel(widget))

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

def load_icon(icon_name):
    """
    Load an icon from the iconset in 16x16
    """
    iconset = app.config.get('iconset')
    path = os.path.join(helpers.get_iconset_path(iconset), '16x16', '')
    icon_list = _load_icon_list([icon_name], path)
    return icon_list[icon_name]

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
            path = os.path.join(app.DATA_DIR, 'emoticons', 'static',
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
      font-family: {family};
      font-size: {size}{unit};
      font-weight: {weight};
    }}""".format(
        family=font.get_family(),
        size=int(round(font.get_size() / Pango.SCALE)),
        unit=unit,
        weight=int(font.get_weight()))
    css = css.replace("font-size: 0{unit};".format(unit=unit), "")
    css = css.replace("font-weight: 0;", "")
    css = "\n".join(filter(lambda x: x.strip(), css.splitlines()))
    return css
