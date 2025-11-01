# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import functools
import hashlib
import logging
import math
from collections import defaultdict
from math import pi
from pathlib import Path

import cairo
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import Pango
from gi.repository import PangoCairo
from nbxmpp.protocol import JID

import gajim.common.storage.archive.models as mod
from gajim.common import app
from gajim.common import configpaths
from gajim.common import types
from gajim.common.const import AvatarSize
from gajim.common.const import StyleAttr
from gajim.common.modules.contacts import BareContact
from gajim.common.modules.contacts import ResourceContact
from gajim.common.util.classes import Singleton
from gajim.common.util.image import get_pixbuf_from_file
from gajim.common.util.image import scale_with_ratio
from gajim.common.util.muc import get_groupchat_name
from gajim.common.util.status import get_client_status
from gajim.common.util.status import get_global_show

from gajim.gtk.const import DEFAULT_WORKSPACE_COLOR
from gajim.gtk.util.icons import load_icon_surface
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.util.misc import convert_texture_to_surface
from gajim.gtk.util.misc import get_first_graphemes
from gajim.gtk.util.styling import convert_rgb_string_to_float
from gajim.gtk.util.styling import get_contact_color
from gajim.gtk.util.styling import get_css_show_class
from gajim.gtk.util.styling import make_rgba
from gajim.gtk.util.styling import rgba_to_float
from gajim.gtk.util.styling import text_to_color

log = logging.getLogger("gajim.gtk.avatar")


AvatarCacheT = dict[
    JID | str, dict[tuple[int, int, str | None, str | None], Gdk.Texture]
]
OccupantAvatarCacheT = dict[JID, dict[tuple[str, int, int], Gdk.Texture]]

CIRCLE_RATIO = 0.18
CIRCLE_FILL_RATIO = 0.80


def generate_avatar_letter(text: str) -> str:
    return get_first_graphemes(text.lstrip(), 1).upper()


def generate_avatar(
    letters: str, color: tuple[float, float, float], size: int, scale: int
) -> cairo.ImageSurface:

    # Get color for nickname with XEP-0392
    color_r, color_g, color_b = color

    # Set up colors and size
    size = size * scale

    width = size
    height = size
    font_size = size * 0.4

    # Set up surface
    surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
    context = cairo.Context(surface)

    context.set_source_rgb(color_r, color_g, color_b)
    context.rectangle(0, 0, width, height)
    context.fill()

    # Draw letters
    layout = PangoCairo.create_layout(context)
    layout.set_text(generate_avatar_letter(letters))

    description = Pango.FontDescription()
    description.set_family("Sans")
    description.set_size(int(font_size * Pango.SCALE))

    layout.set_font_description(description)

    _ink_rect, logical_rect = layout.get_extents()
    layout_width = logical_rect.width / Pango.SCALE
    layout_height = logical_rect.height / Pango.SCALE
    x_pos = (width - layout_width) / 2
    y_pos = (height - layout_height) / 2

    context.move_to(x_pos, y_pos)
    context.set_source_rgb(0.95, 0.95, 0.95)
    context.set_operator(cairo.Operator.OVER)
    PangoCairo.show_layout(context, layout)

    return context.get_target()


@functools.cache
def generate_default_avatar(
    letter: str,
    color: tuple[float, float, float],
    size: int,
    scale: int,
    style: str = "circle",
) -> cairo.ImageSurface:

    surface = generate_avatar(letter, color, size, scale)
    surface = clip(surface, style)
    surface.set_device_scale(scale, scale)
    return surface


@functools.cache
def make_workspace_avatar(
    letter: str,
    color: tuple[float, float, float],
    size: int,
    scale: int,
    style: str = "round-corners",
) -> Gdk.Texture:

    surface = generate_avatar(letter, color, size, scale)
    surface.set_device_scale(scale, scale)
    return convert_surface_to_texture(clip(surface, style))


def add_transport_to_avatar(
    surface: cairo.ImageSurface,
    transport_icon: str,
) -> cairo.ImageSurface:

    scale = surface.get_device_scale()[0]
    width = surface.get_width()
    height = surface.get_height()

    transport_surface = load_icon_surface(
        transport_icon, math.floor(width / scale * CIRCLE_RATIO * 2), int(scale)
    )
    if transport_surface is None:
        return surface

    new_surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
    new_surface.set_device_scale(*surface.get_device_scale())

    context = cairo.Context(new_surface)
    context.set_source_surface(surface, 0, 0)
    context.paint()

    width = width / scale

    clip_radius = width * CIRCLE_RATIO
    center_x = clip_radius
    center_y = clip_radius

    context.set_source_rgb(255, 255, 255)
    context.set_operator(cairo.Operator.CLEAR)
    context.arc(center_x, center_y, clip_radius, 0, 2 * pi)
    context.fill()

    clip_radius *= CIRCLE_FILL_RATIO
    t_width = transport_surface.get_width() / scale
    t_height = transport_surface.get_height() / scale

    context.set_source_surface(
        transport_surface, center_x - t_width / 2, center_y - t_height / 2
    )
    context.set_operator(cairo.Operator.OVER)
    context.arc(center_x, center_y, clip_radius, 0, 2 * pi)
    context.fill()

    return context.get_target()


def add_status_to_avatar(surface: cairo.ImageSurface, show: str) -> cairo.ImageSurface:

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

    clip_radius = width * CIRCLE_RATIO
    center_x = width - clip_radius
    center_y = height - clip_radius

    context.set_source_rgb(255, 255, 255)
    context.set_operator(cairo.Operator.CLEAR)
    context.arc(center_x, center_y, clip_radius, 0, 2 * pi)
    context.fill()

    css_color = get_css_show_class(show)
    color = convert_rgb_string_to_float(
        app.css_config.get_value(css_color, StyleAttr.COLOR)
    )

    show_radius = clip_radius * CIRCLE_FILL_RATIO

    context.set_source_rgb(*color)
    context.set_operator(cairo.Operator.OVER)
    context.arc(center_x, center_y, show_radius, 0, 2 * pi)
    context.fill()

    if show == "dnd":
        line_length = clip_radius / 2
        context.move_to(center_x - line_length, center_y)
        context.line_to(center_x + line_length, center_y)

        context.set_source_rgb(255, 255, 255)
        context.set_line_width(clip_radius / 4)
        context.stroke()

    return context.get_target()


def merge_avatars(avatar1: Gdk.Texture, avatar2: Gdk.Texture) -> Gdk.Texture:
    """
    Includes avatar2 in the bottom right corner of avatar1
    """
    new_surface = cairo.ImageSurface(
        cairo.Format.ARGB32,
        avatar1.get_width(),
        avatar1.get_height(),
    )

    context = cairo.Context(new_surface)
    context.set_source_surface(convert_texture_to_surface(avatar1), 0, 0)
    context.paint()

    context.scale(0.5, 0.5)
    context.set_source_rgb(255, 255, 255)
    context.set_operator(cairo.Operator.CLEAR)
    context.arc(
        avatar1.get_width() * 1.5,
        avatar1.get_height() * 1.5,
        avatar1.get_width() / CIRCLE_FILL_RATIO / 2,
        0,
        2 * pi,
    )
    context.fill()

    context = cairo.Context(new_surface)
    context.scale(0.5, 0.5)
    context.set_source_surface(
        convert_texture_to_surface(avatar2),
        avatar1.get_width(),
        avatar1.get_height(),
    )
    context.paint()
    return convert_surface_to_texture(new_surface)


@functools.lru_cache(maxsize=128)
def get_show_circle(
    show: str | types.PresenceShowT, size: int, scale: int
) -> cairo.ImageSurface:

    if not isinstance(show, str):
        show = show.value

    width = size * scale
    height = width

    surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
    surface.set_device_scale(scale, scale)
    context = cairo.Context(surface)

    css_color = get_css_show_class(show)
    color = convert_rgb_string_to_float(
        app.css_config.get_value(css_color, StyleAttr.COLOR)
    )

    center = size / 2
    radius = size / 3

    context.set_source_rgb(*color)
    context.set_operator(cairo.Operator.OVER)
    context.arc(center, center, radius, 0, 2 * pi)
    context.fill()

    if show == "dnd":
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
    if mode == "circle":
        return clip_circle(surface)
    if mode == "round-corners":
        return round_corners(surface)
    raise ValueError("clip mode unknown: %s" % mode)


def clip_circle(surface: cairo.ImageSurface) -> cairo.ImageSurface:
    new_surface = cairo.ImageSurface(
        cairo.Format.ARGB32, surface.get_width(), surface.get_height()
    )

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
    width = surface.get_width()
    height = surface.get_height()
    scale = surface.get_device_scale()[0]

    new_surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
    new_surface.set_device_scale(*surface.get_device_scale())
    context = cairo.Context(new_surface)
    context.set_source_surface(surface, 0, 0)

    width = width / scale
    height = height / scale

    radius = 9
    degrees = pi / 180

    context.new_sub_path()
    context.arc(width - radius, radius, radius, -90 * degrees, 0 * degrees)
    context.arc(
        width - radius, height - radius, radius, 0 * degrees, 90 * degrees
    )  # noqa: E501
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
        self._occupant_cache: OccupantAvatarCacheT = defaultdict(dict)

    def invalidate_cache(self, jid: JID | str) -> None:
        self._cache.pop(jid, None)

    def remove_avatar(self, contact: types.ChatContactT) -> None:
        if not contact.avatar_sha:
            return
        path = self.get_avatar_path(contact.avatar_sha)
        if path is None:
            return
        path.unlink(missing_ok=True)
        self._cache.pop(contact.jid, None)

    def get_texture(
        self,
        contact: (
            types.BareContact | types.GroupchatContact | types.GroupchatParticipant
        ),
        size: int,
        scale: int,
        show: str | None = None,
        default: bool = False,
        transport_icon: str | None = None,
        style: str = "circle",
    ) -> Gdk.Texture:

        jid = contact.jid

        if not default:
            texture = self._cache[jid].get((size, scale, show, transport_icon))
            if texture is not None:
                return texture

            surface = self._get_avatar_from_storage(
                contact.avatar_sha, size, scale, style
            )
            if surface is not None:
                if show is not None:
                    surface = add_status_to_avatar(surface, show)

                if transport_icon is not None:
                    surface = add_transport_to_avatar(surface, transport_icon)

                texture = convert_surface_to_texture(surface)
                self._cache[jid][(size, scale, show, transport_icon)] = texture
                return texture

        name = contact.name
        color = get_contact_color(contact)
        letter = generate_avatar_letter(name)
        surface = generate_default_avatar(letter, color, size, scale, style=style)
        if show is not None:
            surface = add_status_to_avatar(surface, show)

        if transport_icon is not None:
            surface = add_transport_to_avatar(surface, transport_icon)

        texture = convert_surface_to_texture(surface)
        self._cache[jid][(size, scale, show, transport_icon)] = texture
        return texture

    def get_muc_texture(
        self,
        account: str,
        jid: JID,
        size: int,
        scale: int,
        default: bool = False,
        transport_icon: str | None = None,
        style: str = "circle",
    ) -> Gdk.Texture:

        if not default:
            texture = self._cache[jid].get((size, scale, None, transport_icon))
            if texture is not None:
                return texture

            avatar_sha = app.storage.cache.get_muc(account, jid, "avatar")
            if avatar_sha is not None:
                surface = self.surface_from_filename(avatar_sha, size, scale)
                if surface is not None:
                    # clip first to avoid clipping the transport icon
                    surface = clip(surface, style)

                    if transport_icon is not None:
                        surface = add_transport_to_avatar(surface, transport_icon)

                    texture = convert_surface_to_texture(surface)
                    self._cache[jid][(size, scale, None, transport_icon)] = texture
                    return texture

                # avatar_sha set, but image is missing
                # (e.g. avatar cache deleted)
                app.storage.cache.set_muc(account, jid, "avatar", None)

        client = app.get_client(account)
        contact = client.get_module("Contacts").get_contact_if_exists(jid)
        assert contact is not None
        assert not isinstance(contact, ResourceContact)

        name = get_groupchat_name(client, jid)
        color = get_contact_color(contact)
        letter = generate_avatar_letter(name)
        surface = generate_default_avatar(letter, color, size, scale, style)
        if transport_icon is not None:
            surface = add_transport_to_avatar(surface, transport_icon)

        texture = convert_surface_to_texture(surface)
        self._cache[jid][(size, scale, None, transport_icon)] = texture
        return texture

    def get_occupant_texture(
        self,
        jid: JID,
        occupant: mod.Occupant | str,
        size: int,
        scale: int,
        style: str = "circle",
    ) -> Gdk.Texture:

        if isinstance(occupant, str):
            key = occupant
            nickname = occupant
            avatar_sha = None
            real_remote = None
        else:
            key = occupant.id
            assert occupant.nickname is not None
            nickname = occupant.nickname
            avatar_sha = occupant.avatar_sha
            real_remote = occupant.real_remote

        texture = self._occupant_cache[jid].get((key, size, scale))
        if texture is not None:
            return texture

        surface = self._get_avatar_from_storage(avatar_sha, size, scale, style)
        if surface is not None:
            texture = convert_surface_to_texture(surface)
            self._occupant_cache[jid][(key, size, scale)] = texture
            return texture

        if real_remote is not None:
            color = text_to_color(str(real_remote.jid))
        else:
            color = text_to_color(nickname)

        letter = generate_avatar_letter(nickname)
        surface = generate_default_avatar(letter, color, size, scale, style=style)

        texture = convert_surface_to_texture(surface)
        self._occupant_cache[jid][(key, size, scale)] = texture
        return texture

    def get_own_avatar_texture(
        self, account: str, size: int, scale: int, add_show: bool = False
    ) -> Gdk.Texture | None:
        client = app.get_client(account)
        self_contact = client.get_module("Contacts").get_contact(
            client.get_own_jid().bare
        )
        assert isinstance(self_contact, BareContact)
        return self_contact.get_avatar(size, scale, add_show=add_show)

    def get_workspace_texture(
        self, workspace_id: str, size: int, scale: int
    ) -> Gdk.Texture | None:

        texture = self._cache[workspace_id].get((size, scale, None, None))
        if texture is not None:
            return texture

        name = app.settings.get_workspace_setting(workspace_id, "name")
        color = app.settings.get_workspace_setting(workspace_id, "color")
        avatar_sha = app.settings.get_workspace_setting(workspace_id, "avatar_sha")
        if avatar_sha:
            surface = self.surface_from_filename(avatar_sha, size, scale)
            if surface is not None:
                surface = clip(surface, "round-corners")
                texture = convert_surface_to_texture(surface)
                return texture

            # avatar_sha set, but image is missing
            # (e.g. avatar cache deleted)
            app.settings.set_workspace_setting(workspace_id, "avatar_sha", "")

        rgba = make_rgba(color or DEFAULT_WORKSPACE_COLOR)
        texture = make_workspace_avatar(name, rgba_to_float(rgba), size, scale)

        self._cache[workspace_id][(size, scale, None, None)] = texture
        return texture

    @staticmethod
    def get_account_button_texture(
        account: str | None, size: int, scale: int, connectivity_issues: bool
    ) -> Gdk.Texture:
        width = size * scale
        height = width

        if connectivity_issues:
            surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
            context = cairo.Context(surface)

            context.set_source_rgb(0.75, 0.75, 0.75)
            context.rectangle(0, 0, width, height)
            context.fill()
            icon_surface = load_icon_surface("lucide-cloud-off", int(size * 0.7), scale)
            if icon_surface is not None:
                pos = (width - width * 0.7) / 2
                context.set_source_surface(icon_surface, pos, pos)
                context.paint_with_alpha(0.6)

            surface.set_device_scale(scale, scale)
            surface = clip_circle(context.get_target())
            return convert_surface_to_texture(surface)

        if account is not None:
            jid = app.get_jid_from_account(account)
            client = app.get_client(account)
            contact = client.get_module("Contacts").get_contact(jid)
            assert isinstance(contact, BareContact)
            return app.app.avatar_storage.get_texture(
                contact, size, scale, get_client_status(account)
            )

        # Paint default avatar on grey background (incl. show)
        surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
        context = cairo.Context(surface)

        context.set_source_rgb(0.75, 0.75, 0.75)
        context.rectangle(0, 0, width, height)
        context.fill()

        icon_surface = load_icon_surface("lucide-user", int(size * 0.7), scale)
        if icon_surface is not None:
            pos = (width - width * 0.7) / 2
            context.set_source_surface(icon_surface, pos, pos)
            context.paint_with_alpha(0.6)

        surface.set_device_scale(scale, scale)
        surface = clip_circle(context.get_target())
        surface = add_status_to_avatar(surface, get_global_show())
        return convert_surface_to_texture(surface)

    @staticmethod
    def get_gajim_circle_icon(size: int, scale: int) -> Gdk.Texture:
        # Paint activity icon on grey background
        width = size * scale
        height = width

        surface = cairo.ImageSurface(cairo.Format.ARGB32, width, height)
        context = cairo.Context(surface)

        context.set_source_rgb(1, 1, 1)
        context.rectangle(0, 0, width, height)
        context.fill()

        icon_surface = load_icon_surface("gajim", int(size * 0.6), scale)
        if icon_surface is not None:
            pos = (width - width * 0.6) / 2
            context.set_source_surface(icon_surface, pos, pos)
            context.paint()

        surface.set_device_scale(scale, scale)
        surface = clip_circle(context.get_target())
        return convert_surface_to_texture(surface)

    @staticmethod
    def _load_for_publish(path: str) -> tuple[bool, bytes] | None:
        pixbuf = get_pixbuf_from_file(path)
        if pixbuf is None:
            return None

        width = pixbuf.get_width()
        height = pixbuf.get_height()
        if width > AvatarSize.PUBLISH or height > AvatarSize.PUBLISH:
            # Scale only down, never up
            width, height = scale_with_ratio(AvatarSize.PUBLISH, width, height)
            pixbuf = pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)

        assert pixbuf is not None
        return pixbuf.save_to_bufferv("png", [], [])

    @staticmethod
    def save_avatar(data: bytes) -> str | None:
        """
        Save an avatar to the harddisk

        :param data:  bytes

        returns SHA1 value of the avatar or None on error
        """

        sha = hashlib.sha1(data).hexdigest()
        path = configpaths.get("AVATAR") / sha
        try:
            with open(path, "wb") as output_file:
                output_file.write(data)
        except Exception:
            log.exception("Storing avatar failed")
            return None
        return sha

    @staticmethod
    def get_avatar_path(filename: str) -> Path | None:
        path = configpaths.get("AVATAR") / filename
        if not path.is_file():
            return None
        return path

    def avatar_exists(self, filename: str) -> bool:
        return self.get_avatar_path(filename) is not None

    def surface_from_filename(
        self, filename: str, size: int, scale: int
    ) -> cairo.ImageSurface | None:

        size = size * scale
        path = self.get_avatar_path(filename)
        if path is None:
            return None

        pixbuf = get_pixbuf_from_file(path, size)
        if pixbuf is None:
            return None

        if pixbuf.get_n_channels() == 3:
            cairo_format = cairo.Format.RGB24
        else:
            cairo_format = cairo.Format.ARGB32

        surface = cairo.ImageSurface(
            cairo_format, pixbuf.get_width(), pixbuf.get_height()
        )

        context = cairo.Context(surface)

        Gdk.cairo_set_source_pixbuf(context, pixbuf, 0, 0)
        context.paint()

        return fit(context.get_target(), size)

    def _get_avatar_from_storage(
        self,
        sha: str | None,
        size: int,
        scale: int,
        style: str,
    ) -> cairo.ImageSurface | None:

        if sha is None:
            return None

        surface = self.surface_from_filename(sha, size, scale)
        if surface is None:
            return None
        return clip(surface, style)
