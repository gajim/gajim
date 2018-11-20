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

from gajim.common.i18n import _
from gajim.common import app
from gajim.common import helpers
from gajim.common.const import PEPEventType
from gajim.common.const import ACTIVITIES
from gajim.common.const import MOODS

HAS_PYWIN32 = True
if os.name == 'nt':
    try:
        import win32file
        import win32con
        import pywintypes
    except ImportError:
        HAS_PYWIN32 = False

log = logging.getLogger('gajim.gtkgui_helpers')


class Color:
    BLACK = Gdk.RGBA(red=0, green=0, blue=0, alpha=1)
    GREEN = Gdk.RGBA(red=115/255, green=210/255, blue=22/255, alpha=1)
    RED = Gdk.RGBA(red=204/255, green=0, blue=0, alpha=1)
    GREY = Gdk.RGBA(red=195/255, green=195/255, blue=192/255, alpha=1)
    ORANGE = Gdk.RGBA(red=245/255, green=121/255, blue=0/255, alpha=1)


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

def destroy_widget(widget):
    widget.destroy()

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

def on_avatar_save_as_menuitem_activate(widget, avatar, default_name=''):
    from gajim.gtk.dialogs import ErrorDialog
    from gajim.gtk.dialogs import ConfirmationDialog
    from gajim.gtk.dialogs import FTOverwriteConfirmationDialog
    from gajim.gtk.filechoosers import AvatarSaveDialog
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
        except Exception as error:
            log.error('Error saving avatar: %s', error)
            if os.path.exists(file_path):
                os.remove(file_path)
            new_file_path = '.'.join(file_path.split('.')[:-1]) + '.png'
            def on_ok(file_path, pixbuf):
                pixbuf.savev(file_path, 'png', [], [])
            ConfirmationDialog(_('Extension not supported'),
                _('Image cannot be saved in %(type)s format. Save as '
                '%(new_filename)s?') % {'type': image_format,
                'new_filename': new_file_path},
                on_response_ok=(on_ok, new_file_path, pixbuf))

    def on_ok(file_path):
        if os.path.exists(file_path):
            # check if we have write permissions
            if not os.access(file_path, os.W_OK):
                file_name = os.path.basename(file_path)
                ErrorDialog(_('Cannot overwrite existing file "%s"') % \
                    file_name, _('A file with this name already exists and you '
                    'do not have permission to overwrite it.'))
                return
            dialog2 = FTOverwriteConfirmationDialog(
                _('This file already exists'), _('What do you want to do?'),
                propose_resume=False, on_response=(on_continue, file_path))
            dialog2.set_destroy_with_parent(True)
        else:
            dirname = os.path.dirname(file_path)
            if not os.access(dirname, os.W_OK):
                ErrorDialog(_('Directory "%s" is not writable') % \
                    dirname, _('You do not have permission to create files in '
                    'this directory.'))
                return

        on_continue(0, file_path)

    transient = app.app.get_active_window()
    AvatarSaveDialog(on_ok,
                     path=app.config.get('last_save_dir'),
                     file_name='%s.png' % default_name,
                     transient_for=transient)

def create_combobox(value_list, selected_value=None):
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
        iter_ = liststore.append(value)
        if value[1] in selected_values:
            treeview.get_selection().select_iter(iter_)
    treeview.show_all()
    return treeview

def load_mood_icon(icon_name):
    """
    Load an icon from the mood iconset in 16x16
    """
    iconset = app.config.get('mood_iconset')
    path = os.path.join(helpers.get_mood_iconset_path(iconset), '')
    icon_list = _load_icon_list([icon_name], path)
    return icon_list[icon_name]

def load_activity_icon(category, activity=None):
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

def get_pep_icon(pep_class):
    if pep_class == PEPEventType.MOOD:
        received_mood = pep_class.data['mood']
        mood = received_mood if received_mood in MOODS else 'unknown'
        pixbuf = load_mood_icon(mood).get_pixbuf()
        return pixbuf

    if pep_class == PEPEventType.TUNE:
        return 'audio-x-generic'

    if pep_class == PEPEventType.ACTIVITY:
        pep_ = pep_class.data
        activity = pep_['activity']

        has_known_activity = activity in ACTIVITIES
        has_known_subactivity = (has_known_activity and
                                 'subactivity' in pep_ and
                                 pep_['subactivity'] in ACTIVITIES[activity])

        if has_known_activity:
            if has_known_subactivity:
                subactivity = pep_['subactivity']
                return load_activity_icon(activity, subactivity).get_pixbuf()
            return load_activity_icon(activity).get_pixbuf()
        return load_activity_icon('unknown').get_pixbuf()

    if pep_class == PEPEventType.LOCATION:
        return 'applications-internet'

    return None

def _load_icon_list(icons_list, path, pixbuf2=None):
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

def add_css_class(widget, class_name, prefix=None):
    if class_name and prefix:
        class_name = prefix + class_name

    style = widget.get_style_context()
    if prefix is not None:
        # Remove all css classes with prefix
        for css_cls in style.list_classes():
            if css_cls.startswith(prefix):
                style.remove_class(css_cls)

    if class_name is not None:
        style.add_class(class_name)

def add_css_to_widget(widget, css):
    provider = Gtk.CssProvider()
    provider.load_from_data(bytes(css.encode()))
    context = widget.get_style_context()
    context.add_provider(provider,
                         Gtk.STYLE_PROVIDER_PRIORITY_USER)

def remove_css_class(widget, class_name):
    style = widget.get_style_context()
    style.remove_class(class_name)

def pango_to_css_weight(number):
    # Pango allows for weight values between 100 and 1000
    # CSS allows only full hundred numbers like 100, 200 ..
    number = int(number)
    if number < 100:
        return 100
    if number > 900:
        return 900
    return int(math.ceil(number / 100.0)) * 100
