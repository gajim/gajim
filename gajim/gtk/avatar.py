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

from __future__ import annotations

from typing import Optional
from typing import Union

import logging
import hashlib
from math import pi
from functools import lru_cache
from collections import defaultdict
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GdkPixbuf
import cairo
from nbxmpp.protocol import JID

from gajim.common import types
from gajim.common import app
from gajim.common import configpaths
from gajim.common.helpers import Singleton
from gajim.common.helpers import get_groupchat_name
from gajim.common.const import AvatarSize
from gajim.common.const import StyleAttr

from .const import DEFAULT_WORKSPACE_COLOR
from .util import load_pixbuf
from .util import load_icon_pixbuf
from .util import text_to_color
from .util import scale_with_ratio
from .util import get_css_show_class
from .util import convert_rgb_string_to_float
from .util import rgba_to_float
from .util import make_rgba

log = logging.getLogger('gajim.gui.avatar')


AvatarCacheT = dict[JID, dict[tuple[int, int, Optional[str]],
                              cairo.ImageSurface]]


def generate_avatar(letters: str,
                    color: tuple[float, float, float],
                    size: int,
                    scale: int) -> cairo.ImageSurface:

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


@lru_cache(maxsize=None)
def generate_default_avatar(letter: str,
                            color_string: str,
                            size: int,
                            scale: int,
                            style: str = 'circle') -> cairo.ImageSurface:

    color = text_to_color(color_string)
    surface = generate_avatar(letter, color, size, scale)
    surface = clip(surface, style)
    surface.set_device_scale(scale, scale)
    return surface


@lru_cache(maxsize=None)
def make_workspace_avatar(letter: str,
                          color: tuple[float, float, float],
                          size: int,
                          scale: int,
                          style: str = 'round-corners') -> cairo.ImageSurface:

    surface = generate_avatar(letter, color, size, scale)
    surface = clip(surface, style)
    surface.set_device_scale(scale, scale)
    return surface


def add_status_to_avatar(surface: cairo.ImageSurface,
                         show: str) -> cairo.ImageSurface:

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


def get_icon_avatar(size: int,
                    scale: int,
                    icon_name: str) -> cairo.ImageSurface:

    if scale is not None:
        size = size * scale

    width = size
    height = size

    surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
    context = cairo.Context(surface)

    pixbuf = load_icon_pixbuf(icon_name, size=size, scale=scale)
    Gdk.cairo_set_source_pixbuf(
        context,
        pixbuf,
        0,
        0)
    context.paint()

    return context.get_target()


@lru_cache(maxsize=128)
def get_show_circle(show, size: int, scale: int) -> cairo.ImageSurface:
    if not isinstance(show, str):
        show = show.value

    size = size * scale
    center = size / 2
    radius = size / 3

    surface = cairo.ImageSurface(cairo.Format.ARGB32, size, size)
    context = cairo.Context(surface)

    css_color = get_css_show_class(show)
    color = convert_rgb_string_to_float(
        app.css_config.get_value(css_color, StyleAttr.COLOR))

    context.set_source_rgb(*color)
    context.set_operator(cairo.Operator.OVER)
    context.arc(center, center, radius, 0, 2 * pi)
    context.fill()

    if show == 'dnd':
        line_length = radius * 0.65
        context.move_to(center - line_length, center)
        context.line_to(center + line_length, center)

        context.set_source_rgb(255, 255, 255)
        context.set_line_width(size / 10)
        context.stroke()

    return context.get_target()


def fit(surface: cairo.ImageSurface, size: int) -> cairo.ImageSurface:
    width = surface.get_width()
    height = surface.get_height()
    if width == height:
        return surface

    # Fit any non-square image by:
    # 1. cutting a square from the original surface
    # 2. scaling the square to the desired size
    min_size = min(width, height)
    factor = size / min_size

    square_surface = square(surface, min_size)

    new_surface = cairo.ImageSurface(cairo.Format.ARGB32, size, size)
    new_surface.set_device_scale(*surface.get_device_scale())
    context = cairo.Context(new_surface)
    context.scale(factor, factor)
    context.set_source_surface(square_surface, 0, 0)
    context.paint()
    return context.get_target()


def square(surface: cairo.ImageSurface, size: int) -> cairo.ImageSurface:
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


def clip(surface: cairo.ImageSurface, mode: str) -> cairo.ImageSurface:
    if mode == 'circle':
        return clip_circle(surface)
    if mode == 'round-corners':
        return round_corners(surface)
    raise ValueError('clip mode unknown: %s' % mode)


def clip_circle(surface: cairo.ImageSurface) -> cairo.ImageSurface:
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


def round_corners(surface: cairo.ImageSurface) -> cairo.ImageSurface:
    new_surface = cairo.ImageSurface(cairo.Format.ARGB32,
                                     surface.get_width(),
                                     surface.get_height())

    new_surface.set_device_scale(*surface.get_device_scale())
    context = cairo.Context(new_surface)
    context.set_source_surface(surface, 0, 0)

    width = surface.get_width()
    height = surface.get_height()
    scale = surface.get_device_scale()[0]
    radius = 9 * scale
    degrees = pi / 180

    context.new_sub_path()
    context.arc(width - radius, radius, radius, -90 * degrees, 0 * degrees)
    context.arc(width - radius, height - radius, radius, 0 * degrees, 90 * degrees)
    context.arc(radius, height - radius, radius, 90 * degrees, 180 * degrees)
    context.arc(radius, radius, radius, 180 * degrees, 270 * degrees)
    context.close_path()
    context.clip()

    context.paint()

    return context.get_target()


def convert_to_greyscale(surface: cairo.ImageSurface) -> cairo.ImageSurface:
    context = cairo.Context(surface)
    context.set_operator(cairo.Operator.HSL_COLOR)
    context.set_source_rgb(1, 1, 1)
    context.rectangle(0, 0, surface.get_width(), surface.get_height())
    context.fill()
    context.set_operator(cairo.Operator.ATOP)
    context.set_source_rgba(1, 1, 1, 0.5)
    context.rectangle(0, 0, surface.get_width(), surface.get_height())
    context.fill()
    return context.get_target()


class AvatarStorage(metaclass=Singleton):
    def __init__(self):
        self._cache: AvatarCacheT = defaultdict(dict)

    def invalidate_cache(self, jid: JID) -> None:
        self._cache.pop(jid, None)

    def get_pixbuf(self,
                   contact: Union[types.BareContact,
                                  types.GroupchatContact,
                                  types.GroupchatParticipant],
                   size: int,
                   scale: int,
                   show: Optional[str] = None,
                   default: bool = False,
                   transport_icon: Optional[str] = None,
                   style: str = 'circle') -> Optional[GdkPixbuf.Pixbuf]:

        surface = self.get_surface(
            contact, size, scale, show, default, transport_icon, style)
        return Gdk.pixbuf_get_from_surface(surface, 0, 0, size, size)

    def get_surface(self,
                    contact: Union[types.BareContact,
                                   types.GroupchatContact,
                                   types.GroupchatParticipant],
                    size: int,
                    scale: int,
                    show: Optional[str] = None,
                    default: bool = False,
                    transport_icon: Optional[str] = None,
                    style: str = 'circle') -> cairo.ImageSurface:

        jid = contact.jid

        if transport_icon is not None:
            surface = get_icon_avatar(size, scale, transport_icon)
            if show is not None:
                surface = add_status_to_avatar(surface, show)
            self._cache[jid][(size, scale, show)] = surface
            return surface

        if not default:
            surface = self._cache[jid].get((size, scale, show))
            if surface is not None:
                return surface

            surface = self._get_avatar_from_storage(contact, size, scale, style)
            if surface is not None:
                if show is not None:
                    surface = add_status_to_avatar(surface, show)
                self._cache[jid][(size, scale, show)] = surface
                return surface

        name = contact.name
        color_string = str(contact.jid)

        letter = self._generate_letter(name)
        surface = generate_default_avatar(
            letter, color_string, size, scale, style=style)
        if show is not None:
            surface = add_status_to_avatar(surface, show)
        self._cache[jid][(size, scale, show)] = surface
        return surface

    def get_muc_surface(self,
                        account: str,
                        jid: JID,
                        size: int,
                        scale: int,
                        default: bool = False,
                        transport_icon: Optional[str] = None,
                        style: str = 'circle') -> Optional[cairo.ImageSurface]:

        if transport_icon is not None:
            surface = get_icon_avatar(size, scale, transport_icon)
            self._cache[jid][(size, scale)] = surface
            return surface

        if not default:
            surface = self._cache[jid].get((size, scale))
            if surface is not None:
                return surface

            avatar_sha = app.storage.cache.get_muc(jid, 'avatar')
            if avatar_sha is not None:
                surface = self.surface_from_filename(avatar_sha, size, scale)
                if surface is None:
                    return None
                surface = clip(surface, style)
                self._cache[jid][(size, scale)] = surface
                return surface

        con = app.connections[account]
        name = get_groupchat_name(con, jid)
        letter = self._generate_letter(name)
        surface = generate_default_avatar(letter, str(jid), size, scale, style)
        self._cache[jid][(size, scale)] = surface
        return surface

    def get_workspace_surface(self,
                              workspace_id: str,
                              size: int,
                              scale: int) -> Optional[cairo.ImageSurface]:

        surface = self._cache[workspace_id].get((size, scale))
        if surface is not None:
            return surface

        name = app.settings.get_workspace_setting(workspace_id, 'name')
        color = app.settings.get_workspace_setting(workspace_id, 'color')
        avatar_sha = app.settings.get_workspace_setting(
            workspace_id, 'avatar_sha')
        if avatar_sha:
            surface = self._load_surface_from_storage(avatar_sha, size, scale)
            if surface is not None:
                return clip(surface, 'round-corners')
            else:
                # avatar_sha set, but image is missing
                # (e.g. avatar cache deleted)
                app.settings.set_workspace_setting(
                    workspace_id, 'avatar_sha', '')

        rgba = make_rgba(color or DEFAULT_WORKSPACE_COLOR)
        letter = name[:1].upper()
        surface = make_workspace_avatar(
            letter, rgba_to_float(rgba), size, scale)
        self._cache[workspace_id][(size, scale)] = surface
        return surface

    @staticmethod
    def _load_for_publish(path: str) -> Optional[tuple[bool, bytes]]:
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
    def save_avatar(data: bytes) -> Optional[str]:
        """
        Save an avatar to the harddisk

        :param data:  bytes

        returns SHA1 value of the avatar or None on error
        """
        if data is None:
            return None

        sha = hashlib.sha1(data).hexdigest()
        path = configpaths.get('AVATAR') / sha
        try:
            with open(path, 'wb') as output_file:
                output_file.write(data)
        except Exception:
            log.error('Storing avatar failed', exc_info=True)
            return None
        return sha

    @staticmethod
    def get_avatar_path(filename: str) -> Optional[Path]:
        path = configpaths.get('AVATAR') / filename
        if not path.is_file():
            return None
        return path

    def surface_from_filename(self,
                              filename: str,
                              size: int,
                              scale: int) -> Optional[cairo.ImageSurface]:

        size = size * scale
        path = self.get_avatar_path(filename)
        if path is None:
            return None

        pixbuf = load_pixbuf(path, size)
        if pixbuf is None:
            return None

        surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale)
        return fit(surface, size)

    def _load_surface_from_storage(self,
                                   filename: str,
                                   size: int,
                                   scale: int) -> Optional[cairo.ImageSurface]:

        size = size * scale
        path = self.get_avatar_path(filename)
        if path is None:
            return None

        pixbuf = load_pixbuf(path, size)
        if pixbuf is None:
            return None
        surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, scale)
        return fit(surface, size)

    def _get_avatar_from_storage(self,
                                 contact: Union[types.BareContact,
                                                types.GroupchatContact,
                                                types.GroupchatParticipant],
                                 size: int,
                                 scale: int,
                                 style: str) -> Optional[cairo.ImageSurface]:

        avatar_sha = contact.avatar_sha
        if avatar_sha is None:
            return None

        surface = self._load_surface_from_storage(avatar_sha, size, scale)
        if surface is None:
            return None
        return clip(surface, style)

    @staticmethod
    def _generate_letter(name: str) -> str:
        for letter in name:
            if letter.isalpha():
                return letter.capitalize()
        return name[0].capitalize()
