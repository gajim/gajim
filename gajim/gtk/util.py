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

from gi.repository import Gtk
from gi.repository import GLib
import xml.etree.ElementTree as ET

from gajim.common import i18n
from gajim.common import configpaths

_icon_theme = Gtk.IconTheme.get_default()
_icon_theme.append_search_path(configpaths.get('ICONS'))

log = logging.getLogger('gajim.gtk.util')


def load_icon(icon_name, widget, size=16,
              flags=Gtk.IconLookupFlags.FORCE_SIZE):

    scale = widget.get_scale_factor()
    if not scale:
        log.warning('Could not determine scale factor')
        scale = 1

    try:
        iconinfo = _icon_theme.lookup_icon_for_scale(
            icon_name, size, scale, flags)
        return iconinfo.load_surface(None)
    except GLib.GError as e:
        log.error('Unable to load icon %s: %s', icon_name, str(e))


def get_builder(file_name, widget=None):
    file_path = os.path.join(configpaths.get('GUI'), file_name)
    builder = _translate(file_path, widget)
    builder.set_translation_domain(i18n.DOMAIN)
    return builder


def _translate(gui_file, widget):
    """
    This is a workaround for non working translation on Windows
    """
    if sys.platform == "win32":
        tree = ET.parse(gui_file)
        for node in tree.iter():
            if 'translatable' in node.attrib:
                node.text = _(node.text)
        xml_text = ET.tostring(tree.getroot(),
                               encoding='unicode',
                               method='xml')
        if widget is not None:
            builder = Gtk.Builder()
            builder.add_objects_from_string(xml_text, [widget])
            return builder
        return Gtk.Builder.new_from_string(xml_text, -1)
    else:
        if widget is not None:
            builder = Gtk.Builder()
            builder.add_objects_from_file(gui_file, [widget])
            return builder
        return Gtk.Builder.new_from_file(gui_file)
