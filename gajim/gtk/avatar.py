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
import logging
import hashlib
from math import pi
from functools import lru_cache
from collections import defaultdict

from gi.repository import Gdk
from gi.repository import GdkPixbuf
import cairo

from gajim.common import app
from gajim.common import configpaths
from gajim.common.helpers import Singleton
from gajim.common.helpers import get_groupchat_name
from gajim.common.const import AvatarSize
from gajim.common.const import StyleAttr

from gajim.gtk.util import load_pixbuf
from gajim.gtk.util import text_to_color
from gajim.gtk.util import scale_with_ratio
from gajim.gtk.util import get_css_show_class
from gajim.gtk.util import convert_rgb_string_to_float

log = logging.getLogger('gajim.gtk.avatar')


def generate_avatar(letters, color, size, scale):
    # Get color for nickname with XEP-0392
    color_r, color_g, color_b = color

    # Set up colors and size
    if scale is not None:
        size = size * scale

    width = size
    height = size
    font_size = size * 0.5

    # Set up surface
    surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
    context = cairo.Context(surface)

    context.set_source_rgb(color_r, color_g, color_b)
    context.rectangle(0, 0, width, height)
    context.fill()

    # Draw letters
    context.select_font_face('sans-serif',
                             cairo.FontSlant.NORMAL,
                             cairo.FontWeight.NORMAL)
    context.set_font_size(font_size)
    extends = context.text_extents(letters)
    x_bearing = extends.x_bearing
    y_bearing = extends.y_bearing
    ex_width = extends.width
    ex_height = extends.height

    x_pos = width / 2 - (ex_width / 2 + x_bearing)
    y_pos = height / 2 - (ex_height / 2 + y_bearing)
    context.move_to(x_pos, y_pos)
    context.set_source_rgb(0.95, 0.95, 0.95)
    context.set_operator(cairo.Operator.OVER)
    context.show_text(letters)

    return context.get_target()


def add_status_to_avatar(surface, show):
    width = surface.get_width()
    height = surface.get_height()

    new_surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
    new_surface.set_device_scale(*surface.get_device_scale())

    scale = surface.get_device_scale()[0]

    context = cairo.Context(new_surface)
    context.set_source_surface(surface, 0, 0)
    context.paint()

    # Correct height and width for scale
    width = width / scale
    height = height / scale

    clip_radius = width / 5.5
    center_x = width - clip_radius
    center_y = height - clip_radius

    context.set_source_rgb(255, 255, 255)
    context.set_operator(cairo.Operator.CLEAR)
    context.arc(center_x, center_y, clip_radius, 0, 2 * pi)
    context.fill()

    css_color = get_css_show_class(show)
    color = convert_rgb_string_to_float(
        app.css_config.get_value(css_color, StyleAttr.COLOR))

    show_radius = clip_radius * 0.75

    context.set_source_rgb(*color)
    context.set_operator(cairo.Operator.OVER)
    context.arc(center_x, center_y, show_radius, 0, 2 * pi)
    context.fill()

    if show == 'dnd':
        line_length = clip_radius / 2
        context.move_to(center_x - line_length, center_y)
        context.line_to(center_x + line_length, center_y)

        context.set_source_rgb(255, 255, 255)
        context.set_line_width(clip_radius / 4)
        context.stroke()

    return context.get_target()


def square(surface, size):
    width = surface.get_width()
    height = surface.get_height()
    if width == height:
        return surface

    new_surface = cairo.ImageSurface(cairo.Format.ARGB32, size, size)
    new_surface.set_device_scale(*surface.get_device_scale())
    context = cairo.Context(new_surface)

    scale = surface.get_device_scale()[0]

    if width == size:
        x_pos = 0
        y_pos = (size - height) / 2 / scale
    else:
        y_pos = 0
        x_pos = (size - width) / 2 / scale

    context.set_source_surface(surface, x_pos, y_pos)
    context.paint()
    return context.get_target()


def clip_circle(surface):
    new_surface = cairo.ImageSurface(cairo.Format.ARGB32,
                                     surface.get_width(),
                                     surface.get_height())

    new_surface.set_device_scale(*surface.get_device_scale())
    context = cairo.Context(new_surface)
    context.set_source_surface(surface, 0, 0)

    width = surface.get_width()
    height = surface.get_height()
    scale = surface.get_device_scale()[0]
    radius = width / 2 / scale

    context.arc(width / 2 / scale, height / 2 / scale, radius, 0, 2 * pi)

    context.clip()
    context.paint()

    return context.get_target()


def get_avatar_from_pixbuf(pixbuf, scale, show=None):
    size = max(pixbuf.get_width(), pixbuf.get_height())
    size *= scale
    surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale)
    if surface is None:
        return None
    surface = square(surface, size)
    if surface is None:
        return None
    surface = clip_circle(surface)
    if surface is None:
        return None
    if show is not None:
        return add_status_to_avatar(surface, show)
    return surface


class AvatarStorage(metaclass=Singleton):
    def __init__(self):
        self._cache = defaultdict(dict)

    def invalidate_cache(self, jid):
        self._cache.pop(jid, None)

    def get_pixbuf(self, contact, size, scale, show=None):
        surface = self.get_surface(contact, size, scale, show)
        return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)

    def get_surface(self, contact, size, scale, show=None):
        jid = contact.jid
        if contact.is_gc_contact:
            jid = contact.get_full_jid()

        surface = self._cache[jid].get((size, scale, show))
        if surface is not None:
            return surface

        surface = self._get_avatar_from_storage(contact, size, scale)
        if surface is not None:
            if show is not None:
                surface = add_status_to_avatar(surface, show)
            self._cache[jid][(size, scale, show)] = surface
            return surface

        name = contact.get_shown_name()
        # Use nickname for group chats and bare JID for single contacts
        if contact.is_gc_contact:
            color_string = contact.name
        else:
            color_string = contact.jid

        letter = self._generate_letter(name)
        surface = self._generate_default_avatar(
            letter, color_string, size, scale)
        if show is not None:
            surface = add_status_to_avatar(surface, show)
        self._cache[jid][(size, scale, show)] = surface
        return surface

    def get_muc_surface(self, account, jid, size, scale):
        surface = self._cache[jid].get((size, scale))
        if surface is not None:
            return surface

        avatar_sha = app.logger.get_muc_avatar_sha(jid)
        if avatar_sha is not None:
            surface = self.surface_from_filename(avatar_sha, size, scale)
            if surface is None:
                return None
            surface = clip_circle(surface)
            self._cache[jid][(size, scale)] = surface
            return surface

        con = app.connections[account]
        name = get_groupchat_name(con, jid)
        letter = self._generate_letter(name)
        surface = self._generate_default_avatar(letter, jid, size, scale)
        self._cache[jid][(size, scale)] = surface
        return surface

    def prepare_for_publish(self, path):
        success, data = self._load_for_publish(path)
        if not success:
            return None, None

        sha = self.save_avatar(data)
        if sha is None:
            return None, None
        return data, sha

    @staticmethod
    def _load_for_publish(path):
        pixbuf = load_pixbuf(path)
        if pixbuf is None:
            return None

        width = pixbuf.get_width()
        height = pixbuf.get_height()
        if width > AvatarSize.PUBLISH or height > AvatarSize.PUBLISH:
            # Scale only down, never up
            width, height = scale_with_ratio(AvatarSize.PUBLISH, width, height)
            pixbuf = pixbuf.scale_simple(width,
                                         height,
                                         GdkPixbuf.InterpType.BILINEAR)

        return pixbuf.save_to_bufferv('png', [], [])

    @staticmethod
    def save_avatar(data):
        """
        Save an avatar to the harddisk

        :param data:  bytes

        returns SHA1 value of the avatar or None on error
        """
        if data is None:
            return None

        sha = hashlib.sha1(data).hexdigest()
        path = os.path.join(configpaths.get('AVATAR'), sha)
        try:
            with open(path, 'wb') as output_file:
                output_file.write(data)
        except Exception:
            log.error('Storing avatar failed', exc_info=True)
            return None
        return sha

    @staticmethod
    def get_avatar_path(filename):
        path = os.path.join(configpaths.get('AVATAR'), filename)
        if not os.path.isfile(path):
            return None
        return path

    def surface_from_filename(self, filename, size, scale):
        size = size * scale
        path = self.get_avatar_path(filename)
        if path is None:
            return None

        pixbuf = load_pixbuf(path, size)
        if pixbuf is None:
            return None

        surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale)
        return square(surface, size)

    def _load_surface_from_storage(self, contact, size, scale):
        filename = contact.avatar_sha
        size = size * scale
        path = self.get_avatar_path(filename)
        if path is None:
            return None

        pixbuf = load_pixbuf(path, size)
        if pixbuf is None:
            return None
        surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale)
        return square(surface, size)

    def _get_avatar_from_storage(self, contact, size, scale):
        if contact.avatar_sha is None:
            return None

        surface = self._load_surface_from_storage(contact, size, scale)
        if surface is None:
            return None
        return clip_circle(surface)

    @staticmethod
    def _generate_letter(name):
        for letter in name:
            if letter.isalpha():
                return letter.capitalize()
        return name[0].capitalize()

    @staticmethod
    @lru_cache(maxsize=2048)
    def _generate_default_avatar(letter, color_string, size, scale):
        color = text_to_color(color_string)
        surface = generate_avatar(letter, color, size, scale)
        surface = clip_circle(surface)
        surface.set_device_scale(scale, scale)
        return surface
