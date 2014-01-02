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
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GObject
from gi.repository import Pango
import os
import sys
import importlib

import logging
log = logging.getLogger('gajim.gtkgui_helpers')

from common import i18n
from common import gajim
from common import pep

gtk_icon_theme = Gtk.IconTheme.get_default()
gtk_icon_theme.append_search_path(gajim.ICONS_DIR)

def get_icon_pixmap(icon_name, size=16, quiet=False):
    try:
        return gtk_icon_theme.load_icon(icon_name, size, 0)
    except GObject.GError as e:
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
    except GObject.GError as e:
        log.error("Unable to find icon %s: %s" % (icon_name, str(e)))

import vcard
import dialogs


HAS_PYWIN32 = True
if os.name == 'nt':
    try:
        import win32file
        import win32con
        import pywintypes
    except ImportError:
        HAS_PYWIN32 = False

from common import helpers

screen_w = Gdk.Screen.width()
screen_h = Gdk.Screen.height()

def add_image_to_menuitem(menuitem, icon_name):
    img = Gtk.Image()
    path_img = get_icon_path(icon_name)
    img.set_from_file(path_img)
    menuitem.set_image(img)

def add_image_to_button(button, icon_name):
    add_image_to_menuitem(button, icon_name)

GUI_DIR = os.path.join(gajim.DATA_DIR, 'gui')
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

    completion.set_property('text_column', 1)
    completion.set_model(liststore)
    entry.set_completion(completion)
    return liststore


def popup_emoticons_under_button(menu, button, parent_win):
    """
    Popup the emoticons menu under button, which is in parent_win
    """
    window_x1, window_y1 = parent_win.get_origin()[1:]

    def position_menu_under_button(menu, data):
        # inline function, which will not keep refs, when used as CB
        alloc = button.get_allocation()
        button_x, button_y = alloc.x, alloc.y
        translated_coordinates = button.translate_coordinates(
            gajim.interface.roster.window, 0, 0)
        if translated_coordinates:
            button_x, button_y = translated_coordinates

        # now convert them to X11-relative
        window_x, window_y = window_x1, window_y1
        x = window_x + button_x
        y = window_y + button_y

        menu_height = menu.size_request().height

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
    font_name = gajim.config.get_per('themes', theme, option)
    font_desc = Pango.FontDescription()
    font_prop_str =  gajim.config.get_per('themes', theme, option + 'attrs')
    if font_prop_str:
        if font_prop_str.find('B') != -1:
            font_desc.set_weight(Pango.Weight.BOLD)
        if font_prop_str.find('I') != -1:
            font_desc.set_style(Pango.Style.ITALIC)
    fd = Pango.FontDescription(font_name)
    fd.merge(font_desc, True)
    return fd.to_string()

def get_default_font():
    """
    Get the desktop setting for application font first check for GNOME, then
    Xfce and last KDE it returns None on failure or else a string 'Font Size'
    """
    try:
        from gi.repository import GConf
        client = GConf.Client.get_default()
        value = client.get_string("/desktop/gnome/interface/font_name")
        return value.decode("utf8")
    except ImportError:
        pass

    # try to get Xfce default font
    # Xfce 4.2 and higher follow freedesktop.org's Base Directory Specification
    # see http://www.xfce.org/~benny/xfce/file-locations.html
    # and http://freedesktop.org/Standards/basedir-spec
    xdg_config_home = os.environ.get('XDG_CONFIG_HOME', '')
    if xdg_config_home == '':
        xdg_config_home = os.path.expanduser('~/.config') # default
    xfce_config_file = os.path.join(xdg_config_home,
        'xfce4/mcs_settings/Gtk.xml')

    kde_config_file = os.path.expanduser('~/.kde/share/config/kdeglobals')

    if os.path.exists(xfce_config_file):
        try:
            for line in open(xfce_config_file):
                if line.find('name="Gtk/FontName"') != -1:
                    start = line.find('value="') + 7
                    return line[start:line.find('"', start)]
        except Exception:
            #we talk about file
            print(_('Error: cannot open %s for reading') % xfce_config_file,
                file=sys.stderr)

    elif os.path.exists(kde_config_file):
        try:
            for line in open(kde_config_file):
                if line.find('font=') == 0: # font=Verdana,9,other_numbers
                    start = 5 # 5 is len('font=')
                    line = line[start:]
                    values = line.split(',')
                    font_name = values[0]
                    font_size = values[1]
                    font_string = '%s %s' % (font_name, font_size) # Verdana 9
                    return font_string
        except Exception:
            #we talk about file
            print(_('Error: cannot open %s for reading') % kde_config_file,
                file=sys.stderr)

    return None

def get_running_processes():
    """
    Return running processes or None (if /proc does not exist)
    """
    if os.path.isdir('/proc'):
        # under Linux: checking if 'gnome-session' or
        # 'startkde' programs were run before gajim, by
        # checking /proc (if it exists)
        #
        # if something is unclear, read `man proc`;
        # if /proc exists, directories that have only numbers
        # in their names contain data about processes.
        # /proc/[xxx]/exe is a symlink to executable started
        # as process number [xxx].
        # filter out everything that we are not interested in:
        files = os.listdir('/proc')

        # files that doesn't have only digits in names...
        files = [f for f in files if f.isdigit()]

        # files that aren't directories...
        files = [f for f in files if os.path.isdir('/proc/' + f)]

        # processes owned by somebody not running gajim...
        # (we check if we have access to that file)
        files = [f for f in files if os.access('/proc/' + f +'/exe', os.F_OK)]

        # be sure that /proc/[number]/exe is really a symlink
        # to avoid TBs in incorrectly configured systems
        files = [f for f in files if os.path.islink('/proc/' + f + '/exe')]

        # list of processes
        processes = [os.path.basename(os.readlink('/proc/' + f +'/exe')) for f \
            in files]

        return processes
    return []

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

class HashDigest:
    def __init__(self, algo, digest):
        self.algo = self.cleanID(algo)
        self.digest = self.cleanID(digest)

    def cleanID(self, id_):
        id_ = id_.strip().lower()
        for strip in (' :.-_'):
            id_ = id_.replace(strip, '')
        return id_

    def __eq__(self, other):
        sa, sd = self.algo, self.digest
        if isinstance(other, self.__class__):
            oa, od = other.algo, other.digest
        elif isinstance(other, basestring):
            sa, oa, od = None, None, self.cleanID(other)
        elif isinstance(other, tuple) and len(other) == 2:
            oa, od = self.cleanID(other[0]), self.cleanID(other[1])
        else:
            return False

        return sa == oa and sd == od

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        return self.algo ^ self.digest

    def __str__(self):
        prettydigest = ''
        for i in list(range(0, len(self.digest), 2)):
            prettydigest += self.digest[i:i + 2] + ':'
        return prettydigest[:-1]

    def __repr__(self):
        return "%s(%s, %s)" % (self.__class__, repr(self.algo), repr(str(self)))

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
    if gajim.config.get('use_urgency_hint'):
        if unread_messages_no > 0:
            window.props.urgency_hint = True
        else:
            window.props.urgency_hint = False

def get_abspath_for_script(scriptname, want_type = False):
    """
    Check if we are svn or normal user and return abspath to asked script if
    want_type is True we return 'svn' or 'install'
    """
    if os.path.isdir('.svn'): # we are svn user
        type_ = 'svn'
        cwd = os.getcwd() # it's always ending with src

        if scriptname == 'gajim-remote':
            path_to_script = cwd + '/gajim-remote.py'

        elif scriptname == 'gajim':
            script = '#!/bin/sh\n' # the script we may create
            script += 'cd %s' % cwd
            path_to_script = cwd + '/../scripts/gajim_sm_script'

            try:
                if os.path.exists(path_to_script):
                    os.remove(path_to_script)

                f = open(path_to_script, 'w')
                script += '\nexec python -OOt gajim.py $0 $@\n'
                f.write(script)
                f.close()
                os.chmod(path_to_script, 0o700)
            except OSError: # do not traceback (could be a permission problem)
                #we talk about a file here
                s = _('Could not write to %s. Session Management support will '
                    'not work') % path_to_script
                print(s, file=sys.stderr)

    else: # normal user (not svn user)
        type_ = 'install'
        # always make it like '/usr/local/bin/gajim'
        path_to_script = helpers.is_in_path(scriptname, True)


    if want_type:
        return path_to_script, type_
    else:
        return path_to_script

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
    except GObject.GError: # 'unknown image format'
        pixbufloader.close()
        pixbuf = None
        if want_type:
            return None, None
        else:
            return None

    if want_type:
        typ = pixbufloader.get_format().get_name()
        return pixbuf, typ
    else:
        return pixbuf

def get_invisible_cursor():
    import cairo
    s = cairo.ImageSurface(cairo.FORMAT_A1, 1, 1)
    cursor_pixbuf = Gdk.pixbuf_get_from_surface(s, 0, 0, 1, 1)
    cursor = Gdk.Cursor.new_from_pixbuf(Gdk.Display.get_default(), \
        cursor_pixbuf, 0, 0)
    return cursor

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

def get_scaled_pixbuf(pixbuf, kind):
    """
    Return scaled pixbuf, keeping ratio etc or None kind is either "chat",
    "roster", "notification", "tooltip", "vcard"
    """
    # resize to a width / height for the avatar not to have distortion
    # (keep aspect ratio)
    width = gajim.config.get(kind + '_avatar_width')
    height = gajim.config.get(kind + '_avatar_height')
    if width < 1 or height < 1:
        return None

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

def get_avatar_pixbuf_from_cache(fjid, use_local=True):
    """
    Check if jid has cached avatar and if that avatar is valid image (can be
    shown)

    Returns None if there is no image in vcard/
    Returns 'ask' if cached vcard should not be used (user changed his vcard, so
    we have new sha) or if we don't have the vcard
    """
    jid, nick = gajim.get_room_and_nick_from_fjid(fjid)
    if gajim.config.get('hide_avatar_of_transport') and\
            gajim.jid_is_transport(jid):
        # don't show avatar for the transport itself
        return None

    if any(jid in gajim.contacts.get_gc_list(acc) for acc in \
    gajim.contacts.get_accounts()):
        is_groupchat_contact = True
    else:
        is_groupchat_contact = False

    puny_jid = helpers.sanitize_filename(jid)
    if is_groupchat_contact:
        puny_nick = helpers.sanitize_filename(nick)
        path = os.path.join(gajim.VCARD_PATH, puny_jid, puny_nick)
        local_avatar_basepath = os.path.join(gajim.AVATAR_PATH, puny_jid,
                puny_nick) + '_local'
    else:
        path = os.path.join(gajim.VCARD_PATH, puny_jid)
        local_avatar_basepath = os.path.join(gajim.AVATAR_PATH, puny_jid) + \
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

    vcard_dict = list(gajim.connections.values())[0].get_cached_vcard(fjid,
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

def decode_filechooser_file_paths(file_paths):
    """
    Decode as UTF-8 under Windows and ask sys.getfilesystemencoding() in POSIX
    file_paths MUST be LIST
    """
    file_paths_list = list()

    if os.name == 'nt': # decode as UTF-8 under Windows
        for file_path in file_paths:
            file_path = file_path.decode('utf8')
            file_paths_list.append(file_path)
    else:
        for file_path in file_paths:
            try:
                file_path = file_path.decode(sys.getfilesystemencoding())
            except Exception:
                try:
                    file_path = file_path
                except Exception:
                    pass
            file_paths_list.append(file_path)

    return file_paths_list

def possibly_set_gajim_as_xmpp_handler():
    """
    Register (by default only the first time) 'xmmp:' to Gajim
    """
    path_to_dot_kde = os.path.expanduser('~/.kde')
    if os.path.exists(path_to_dot_kde):
        path_to_kde_file = os.path.join(path_to_dot_kde,
                'share/services/xmpp.protocol')
    else:
        path_to_kde_file = None

    def set_gajim_as_xmpp_handler(is_checked=None):
        if is_checked is not None:
            # come from confirmation dialog
            gajim.config.set('check_if_gajim_is_default', is_checked)
        path_to_gajim_script, typ = get_abspath_for_script('gajim-remote', True)
        if path_to_gajim_script:
            if typ == 'svn':
                command = path_to_gajim_script + ' handle_uri %s'
            else: # 'installed'
                command = 'gajim-remote handle_uri %s'

            # setting for GNOME/Gconf
            client.set_bool('/desktop/gnome/url-handlers/xmpp/enabled', True)
            client.set_string('/desktop/gnome/url-handlers/xmpp/command',
                command)
            client.set_bool('/desktop/gnome/url-handlers/xmpp/needs_terminal',
                False)

            # setting for KDE
            if path_to_kde_file is not None: # user has run kde at least once
                try:
                    f = open(path_to_kde_file, 'a')
                    f.write('''\
[Protocol]
exec=%s "%%u"
protocol=xmpp
input=none
output=none
helper=true
listing=false
reading=false
writing=false
makedir=false
deleting=false
icon=gajim
Description=xmpp
''' % command)
                    f.close()
                except IOError:
                    log.debug("I/O Error writing settings to %s",
                        repr(path_to_kde_file), exc_info=True)
        else: # no gajim remote, stop ask user everytime
            gajim.config.set('check_if_gajim_is_default', False)

    try:
        GConf = importlib.import_module('gi.repository.GConf')
        # in try because daemon may not be there
        client = GConf.Client.get_default()
    except Exception:
        return

    old_command = client.get_string('/desktop/gnome/url-handlers/xmpp/command')
    if not old_command or old_command.endswith(' open_chat %s'):
        # first time (GNOME/GCONF) or old Gajim version
        we_set = True
    elif path_to_kde_file is not None and not os.path.exists(path_to_kde_file):
        # only the first time (KDE)
        we_set = True
    else:
        we_set = False

    if we_set:
        set_gajim_as_xmpp_handler()
    elif old_command and not old_command.endswith(' handle_uri %s'):
        # xmpp: is currently handled by another program, so ask the user
        pritext = _('Gajim is not the default Jabber client')
        sectext = _('Would you like to make Gajim the default Jabber client?')
        checktext = _('Always check to see if Gajim is the default Jabber '
            'client on startup')
        def on_cancel(checked):
            gajim.config.set('check_if_gajim_is_default', checked)
        dlg = dialogs.ConfirmationDialogCheck(pritext, sectext, checktext,
            set_gajim_as_xmpp_handler, on_cancel)
        if gajim.config.get('check_if_gajim_is_default'):
            dlg.checkbutton.set_active(True)

def escape_underscore(s):
    """
    Escape underlines to prevent them from being interpreted as keyboard
    accelerators
    """
    return s.replace('_', '__')

def get_state_image_from_file_path_show(file_path, show):
    state_file = show.replace(' ', '_')
    files = []
    files.append(os.path.join(file_path, state_file + '.png'))
    files.append(os.path.join(file_path, state_file + '.gif'))
    image = Gtk.Image()
    image.set_from_pixbuf(None)
    for file_ in files:
        if os.path.exists(file_):
            image.set_from_file(file_)
            break

    return image

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
        file_path = decode_filechooser_file_paths((file_path,))[0]
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

    dialog = dialogs.FileChooserDialog(title_text=_('Save Image as...'),
        action=Gtk.FileChooserAction.SAVE, buttons=(Gtk.STOCK_CANCEL,
        Gtk.ResponseType.CANCEL, Gtk.STOCK_SAVE, Gtk.ResponseType.OK),
        default_response=Gtk.ResponseType.OK,
        current_folder=gajim.config.get('last_save_dir'), on_response_ok=on_ok,
        on_response_cancel=on_cancel)

    dialog.set_current_name(default_name + '.jpeg')
    dialog.connect('delete-event', lambda widget, event:
        on_cancel(widget))

def on_bm_header_changed_state(widget, event):
    widget.set_state(Gtk.StateType.NORMAL) #do not allow selected_state

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
    col.pack_start(cell, True, True, 0)
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
    iconset = gajim.config.get('iconset')
    path = os.path.join(helpers.get_iconset_path(iconset), '16x16', '')
    icon_list = _load_icon_list([icon_name], path)
    return icon_list[icon_name]

def load_mood_icon(icon_name):
    """
    Load an icon from the mood iconset in 16x16
    """
    iconset = gajim.config.get('mood_iconset')
    path = os.path.join(helpers.get_mood_iconset_path(iconset), '')
    icon_list = _load_icon_list([icon_name], path)
    return icon_list[icon_name]

def load_activity_icon(category, activity = None):
    """
    Load an icon from the activity iconset in 16x16
    """
    iconset = gajim.config.get('activity_iconset')
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
            path = os.path.join(gajim.DATA_DIR, 'emoticons', 'static',
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
    iconset = gajim.config.get('iconset')
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
    iconset = gajim.config.get('iconset')
    if iconset:
        if helpers.get_iconset_path(iconset):
            path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
            if not os.path.exists(path):
                iconset = gajim.config.DEFAULT_ICONSET
                gajim.config.set('iconset', iconset)
        else:
            iconset = gajim.config.DEFAULT_ICONSET
            gajim.config.set('iconset', iconset)
    else:
        iconset = gajim.config.DEFAULT_ICONSET
        gajim.config.set('iconset', iconset)

    path = os.path.join(helpers.get_iconset_path(iconset), '16x16')
    gajim.interface.jabber_state_images['16'] = load_iconset(path)

    pixo, pixc = load_icons_meta()
    gajim.interface.jabber_state_images['opened'] = load_iconset(path, pixo)
    gajim.interface.jabber_state_images['closed'] = load_iconset(path, pixc)

    path = os.path.join(helpers.get_iconset_path(iconset), '32x32')
    gajim.interface.jabber_state_images['32'] = load_iconset(path)

    path = os.path.join(helpers.get_iconset_path(iconset), '24x24')
    if (os.path.exists(path)):
        gajim.interface.jabber_state_images['24'] = load_iconset(path)
    else:
        # Resize 32x32 icons to 24x24
        for each in gajim.interface.jabber_state_images['32']:
            img = Gtk.Image()
            pix = gajim.interface.jabber_state_images['32'][each]
            pix_type = pix.get_storage_type()
            if pix_type == Gtk.ImageType.ANIMATION:
                animation = pix.get_animation()
                pixbuf = animation.get_static_image()
            elif pix_type == Gtk.ImageType.EMPTY:
                pix = gajim.interface.jabber_state_images['16'][each]
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
            gajim.interface.jabber_state_images['24'][each] = img

def reload_jabber_state_images():
    make_jabber_state_images()
    gajim.interface.roster.update_jabber_state_images()

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
