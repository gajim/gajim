# This is a port of um-crop-area.c from GNOME’s 'Cheese' application, see
# https://gitlab.gnome.org/GNOME/cheese/-/blob/3.34.0/libcheese/um-crop-area.c
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any
from typing import cast

import logging
from enum import IntEnum
from enum import unique
from pathlib import Path

import cairo
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.util.image import scale_with_ratio
from gajim.common.util.uri import get_file_path_from_dnd_dropped_uri

from gajim.gtk.dialogs import SimpleDialog
from gajim.gtk.filechoosers import AvatarFileChooserButton
from gajim.gtk.util.classes import SignalManager

log = logging.getLogger("gajim.gtk.avatar_selector")


@unique
class Loc(IntEnum):
    OUTSIDE = 0
    INSIDE = 1
    TOP = 2
    TOP_LEFT = 3
    TOP_RIGHT = 4
    BOTTOM = 5
    BOTTOM_LEFT = 6
    BOTTOM_RIGHT = 7
    LEFT = 8
    RIGHT = 9


@unique
class Range(IntEnum):
    BELOW = 0
    LOWER = 1
    BETWEEN = 2
    UPPER = 3
    ABOVE = 4


class AvatarSelector(Gtk.Box, SignalManager):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL, spacing=12)
        SignalManager.__init__(self)

        self.add_css_class("avatar-selector")

        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        self._connect(drop_target, "accept", self._on_drop_accept)
        self._connect(drop_target, "drop", self._on_file_drop)
        self.add_controller(drop_target)

        self._crop_area = CropArea()
        self._crop_area.set_vexpand(True)
        self.append(self._crop_area)

        self._file_chooser_button = AvatarFileChooserButton(label=_("Load Image"))
        self._file_chooser_button.set_halign(Gtk.Align.CENTER)
        self._connect(self._file_chooser_button, "path-picked", self._on_path_picked)
        self.append(self._file_chooser_button)

        self._helper_label = Gtk.Label(label=_("…or drop it here"))
        self._helper_label.add_css_class("bold")
        self._helper_label.add_css_class("dim-label")
        self._helper_label.set_vexpand(True)
        self.append(self._helper_label)

    def do_unroot(self, *args: Any) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)
        del self._file_chooser_button
        del self._crop_area

    def reset(self) -> None:
        self._crop_area.reset()
        self._file_chooser_button.reset()
        self._file_chooser_button.show()
        self._helper_label.show()

    def prepare_crop_area(self, path: str) -> None:
        pixbuf = self._get_pixbuf_from_path(path)
        if pixbuf is None:
            log.info("Could not load from path %s", path)
            return

        self._crop_area.set_pixbuf(pixbuf)
        self._file_chooser_button.hide()
        self._helper_label.hide()
        self._crop_area.show()

    def _on_path_picked(
        self, _button: AvatarFileChooserButton, paths: list[Path]
    ) -> None:
        if not paths:
            return

        self.prepare_crop_area(str(paths[0]))

    def _on_drop_accept(self, _target: Gtk.DropTarget, drop: Gdk.Drop) -> bool:
        formats = drop.get_formats()
        return bool(formats.contain_gtype(Gdk.FileList))

    def _on_file_drop(
        self, _target: Gtk.DropTarget, value: Gdk.FileList, _x: float, _y: float
    ) -> bool:
        files = value.get_files()
        if not files:
            return False

        path = get_file_path_from_dnd_dropped_uri(files[0].get_uri())
        if not path or not path.is_file():
            return False

        self.prepare_crop_area(str(path))
        return True

    @staticmethod
    def _get_pixbuf_from_path(path: str) -> GdkPixbuf.Pixbuf | None:
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            return pixbuf
        except GLib.Error as err:
            log.error("Unable to load file %s: %s", path, str(err))
            return None

    def get_prepared(self) -> bool:
        return bool(self._crop_area.get_pixbuf())

    @staticmethod
    def _scale_for_publish(
        pixbuf: GdkPixbuf.Pixbuf,
    ) -> tuple[GdkPixbuf.Pixbuf, int, int]:
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        if width > AvatarSize.PUBLISH or height > AvatarSize.PUBLISH:
            # Scale only down, never up
            width, height = scale_with_ratio(AvatarSize.PUBLISH, width, height)
            scaled_pixbuf = pixbuf.scale_simple(
                width, height, GdkPixbuf.InterpType.BILINEAR
            )
            assert scaled_pixbuf is not None
            return scaled_pixbuf, width, height
        return pixbuf, width, height

    def get_avatar_texture(self) -> tuple[Gdk.Texture, int, int] | None:
        pixbuf = self._crop_area.get_pixbuf()
        if pixbuf is None:
            return None
        scaled, width, height = self._scale_for_publish(pixbuf)

        return Gdk.Texture.new_for_pixbuf(scaled), width, height

    def get_avatar_bytes(self) -> tuple[bool, bytes | None, int, int]:
        pixbuf = self._crop_area.get_pixbuf()
        if pixbuf is None:
            return False, None, 0, 0
        scaled, width, height = self._scale_for_publish(pixbuf)

        success, data = scaled.save_to_bufferv("png", [], [])
        return success, data, width, height


class CropArea(Gtk.DrawingArea, SignalManager):
    def __init__(self) -> None:
        Gtk.DrawingArea.__init__(self, visible=False)
        SignalManager.__init__(self)

        self._image = Gdk.Rectangle()
        self._crop = Gdk.Rectangle()
        self._pixbuf: GdkPixbuf.Pixbuf | None = None
        self._browse_pixbuf: GdkPixbuf.Pixbuf | None = None
        self._color_shifted_pixbuf: GdkPixbuf.Pixbuf | None = None
        self._current_cursor: Any | None = None

        self._scale = 1.0
        self._image.x = 0
        self._image.y = 0
        self._image.width = 0
        self._image.height = 0
        self._active_region = Loc.OUTSIDE
        self._last_press_x = -1
        self._last_press_y = -1
        self._base_width = 10
        self._base_height = 10
        self._aspect = 1.0

        self.set_size_request(self._base_width, self._base_height)

        self.set_draw_func(self._on_draw)

        gesture_primary_click = Gtk.GestureClick(button=Gdk.BUTTON_PRIMARY)
        self._connect(gesture_primary_click, "pressed", self._on_button_press)
        self._connect(gesture_primary_click, "released", self._on_button_release)
        self.add_controller(gesture_primary_click)

        motion_controller = Gtk.EventControllerMotion()
        self._connect(motion_controller, "motion", self._on_motion)
        self.add_controller(motion_controller)

    def do_unroot(self, *args: Any) -> None:
        self._disconnect_all()
        self.set_draw_func(None)
        Gtk.DrawingArea.do_unroot(self)
        app.check_finalize(self)

    def set_min_size(self, width: int, height: int) -> None:
        self._base_width = width
        self._base_height = height
        self.set_size_request(self._base_width, self._base_height)

        if self._aspect > 0:
            self._aspect = self._base_width / self._base_height

    def set_contstrain_aspect(self, constrain: bool) -> None:
        if constrain:
            self._aspect = self._base_width / self._base_height
        else:
            self._aspect = -1

    def reset(self) -> None:
        self._browse_pixbuf = None
        self.hide()

    def set_pixbuf(self, pixbuf: GdkPixbuf.Pixbuf) -> None:
        self._browse_pixbuf = pixbuf
        width = pixbuf.get_width()
        height = pixbuf.get_height()

        self._crop.width = 2 * self._base_width
        self._crop.height = 2 * self._base_height
        self._crop.x = int(abs((width - self._crop.width) / 2))
        self._crop.y = int(abs((height - self._crop.height) / 2))

        self._scale = 1.0
        self._image.x = 0
        self._image.y = 0
        self._image.width = 0
        self._image.height = 0

        self._update_pixbufs()

        self.queue_draw()

    def get_pixbuf(self) -> GdkPixbuf.Pixbuf | None:
        if self._browse_pixbuf is None:
            return None

        width = self._browse_pixbuf.get_width()
        height = self._browse_pixbuf.get_height()
        width = min(self._crop.width, width - self._crop.x)
        height = min(self._crop.height, height - self._crop.y)

        if width <= 0 or height <= 0:
            return None

        return GdkPixbuf.Pixbuf.new_subpixbuf(
            self._browse_pixbuf, self._crop.x, self._crop.y, width, height
        )

    def _on_draw(
        self,
        _drawing_area: Gtk.DrawingArea,
        context: cairo.Context[cairo.ImageSurface],
        _width: int,
        _height: int,
    ) -> None:

        if self._browse_pixbuf is None:
            return

        self._update_pixbufs()

        if self._pixbuf is None:
            avatar_selector = cast(AvatarSelector, self.get_parent())
            avatar_selector.reset()
            SimpleDialog(
                _("Error Loading Image"), _("Selected image could not be loaded.")
            )
            return

        width = self._pixbuf.get_width()
        height = self._pixbuf.get_height()
        crop = self._crop_to_widget()

        ix = self._image.x
        iy = self._image.y

        assert self._color_shifted_pixbuf is not None
        Gdk.cairo_set_source_pixbuf(context, self._color_shifted_pixbuf, ix, iy)
        context.rectangle(ix, iy, width, crop.y - iy)
        context.rectangle(ix, crop.y, crop.x - ix, crop.height)
        context.rectangle(
            crop.x + crop.width, crop.y, width - crop.width - (crop.x - ix), crop.height
        )
        context.rectangle(
            ix, crop.y + crop.height, width, height - crop.height - (crop.y - iy)
        )
        context.fill()

        Gdk.cairo_set_source_pixbuf(context, self._pixbuf, ix, iy)
        context.rectangle(crop.x, crop.y, crop.width, crop.height)
        context.fill()

        if self._active_region != Loc.OUTSIDE:
            context.set_source_rgb(150, 150, 150)
            context.set_line_width(1.0)
            x1 = crop.x + crop.width / 3.0
            x2 = crop.x + 2 * crop.width / 3.0
            y1 = crop.y + crop.height / 3.0
            y2 = crop.y + 2 * crop.height / 3.0

            context.move_to(x1 + 0.5, crop.y)
            context.line_to(x1 + 0.5, crop.y + crop.height)

            context.move_to(x2 + 0.5, crop.y)
            context.line_to(x2 + 0.5, crop.y + crop.height)

            context.move_to(crop.x, y1 + 0.5)
            context.line_to(crop.x + crop.width, y1 + 0.5)

            context.move_to(crop.x, y2 + 0.5)
            context.line_to(crop.x + crop.width, y2 + 0.5)
            context.stroke()

        context.set_source_rgb(1, 1, 1)
        context.set_line_width(1.0)

        context.rectangle(
            crop.x + 0.5, crop.y + 0.5, crop.width - 1.0, crop.height - 1.0
        )
        context.stroke()

        context.set_source_rgb(1, 1, 1)
        context.set_line_width(2.0)
        context.rectangle(
            crop.x + 2.0, crop.y + 2.0, crop.width - 4.0, crop.height - 4.0
        )
        context.stroke()

    def _on_button_press(
        self,
        gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        if self._browse_pixbuf is None:
            return

        crop = self._crop_to_widget()

        self._last_press_x = (x - self._image.x) / self._scale
        self._last_press_y = (y - self._image.y) / self._scale
        self._active_region = self._find_location(crop, x, y)
        self.queue_draw()

    def _on_button_release(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        _x: float,
        _y: float,
    ) -> None:
        if self._browse_pixbuf is None:
            return

        self._crop_to_widget()
        self._last_press_x = -1
        self._last_press_y = -1
        self._active_region = Loc.OUTSIDE

        self.queue_draw()

    def _on_motion(
        self,
        _event_controller: Gtk.EventControllerMotion,
        x: float,
        y: float,
    ) -> None:
        # pylint: disable=too-many-boolean-expressions
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        if self._browse_pixbuf is None:
            return

        self._update_cursor(x, y)

        self._crop_to_widget()
        self.queue_draw()

        pb_width = self._browse_pixbuf.get_width()
        pb_height = self._browse_pixbuf.get_height()

        x_coord = int((x - self._image.x) / self._scale)
        y_coord = int((y - self._image.y) / self._scale)

        delta_x = int(x_coord - self._last_press_x)
        delta_y = int(y_coord - self._last_press_y)
        self._last_press_x = x_coord
        self._last_press_y = y_coord

        left = int(self._crop.x)
        right = int(self._crop.x + self._crop.width - 1)
        top = int(self._crop.y)
        bottom = int(self._crop.y + self._crop.height - 1)

        center_x = float((left + right) / 2.0)
        center_y = float((top + bottom) / 2.0)

        if self._active_region == Loc.INSIDE:
            width = right - left + 1
            height = bottom - top + 1

            left += delta_x
            right += delta_x
            top += delta_y
            bottom += delta_y

            left = max(left, 0)
            top = max(top, 0)
            right = min(right, pb_width)
            bottom = min(bottom, pb_height)

            adj_width = int(right - left + 1)
            adj_height = int(bottom - top + 1)
            if adj_width != width:
                if delta_x < 0:
                    right = left + width - 1
                else:
                    left = right - width + 1

            if adj_height != height:
                if delta_y < 0:
                    bottom = top + height - 1
                else:
                    top = bottom - height + 1

        elif self._active_region == Loc.TOP_LEFT:
            if self._aspect < 0:
                top = y_coord
                left = x_coord
            elif y_coord < self._eval_radial_line(
                center_x, center_y, left, top, x_coord
            ):
                top = y_coord
                new_width = float((bottom - top) * self._aspect)
                left = right - new_width
            else:
                left = x_coord
                new_height = float((right - left) / self._aspect)
                top = bottom - new_height

        elif self._active_region == Loc.TOP:
            top = y_coord
            if self._aspect > 0:
                new_width = float((bottom - top) * self._aspect)
                right = left + new_width

        elif self._active_region == Loc.TOP_RIGHT:
            if self._aspect < 0:
                top = y_coord
                right = x_coord
            elif y_coord < self._eval_radial_line(
                center_x, center_y, right, top, x_coord
            ):
                top = y_coord
                new_width = float((bottom - top) * self._aspect)
                right = left + new_width
            else:
                right = x_coord
                new_height = float((right - left) / self._aspect)
                top = bottom - new_height

        elif self._active_region == Loc.LEFT:
            left = x_coord
            if self._aspect > 0:
                new_height = float((right - left) / self._aspect)
                bottom = top + new_height

        elif self._active_region == Loc.BOTTOM_LEFT:
            if self._aspect < 0:
                bottom = y_coord
                left = x_coord
            elif y_coord < self._eval_radial_line(
                center_x, center_y, left, bottom, x_coord
            ):
                left = x_coord
                new_height = float((right - left) / self._aspect)
                bottom = top + new_height
            else:
                bottom = y_coord
                new_width = float((bottom - top) * self._aspect)
                left = right - new_width

        elif self._active_region == Loc.RIGHT:
            right = x_coord
            if self._aspect > 0:
                new_height = float((right - left) / self._aspect)
                bottom = top + new_height

        elif self._active_region == Loc.BOTTOM_RIGHT:
            if self._aspect < 0:
                bottom = y_coord
                right = x_coord
            elif y_coord < self._eval_radial_line(
                center_x, center_y, right, bottom, x_coord
            ):
                right = x_coord
                new_height = float((right - left) / self._aspect)
                bottom = top + new_height
            else:
                bottom = y_coord
                new_width = float((bottom - top) * self._aspect)
                right = left + new_width

        elif self._active_region == Loc.BOTTOM:
            bottom = y_coord
            if self._aspect > 0:
                new_width = float((bottom - top) * self._aspect)
                right = left + new_width
        else:
            return

        min_width = int(self._base_width / self._scale)
        min_height = int(self._base_height / self._scale)

        width = right - left + 1
        height = bottom - top + 1
        if self._aspect < 0:
            left = max(left, 0)
            top = max(top, 0)
            right = min(right, pb_width)
            bottom = min(bottom, pb_height)

            width = right - left + 1
            height = bottom - top + 1

            if self._active_region in (Loc.LEFT, Loc.TOP_LEFT, Loc.BOTTOM_LEFT):
                if width < min_width:
                    left = right - min_width
            elif self._active_region in (Loc.RIGHT, Loc.TOP_RIGHT, Loc.BOTTOM_RIGHT):
                if width < min_width:
                    right = left + min_width

            if self._active_region in (Loc.TOP, Loc.TOP_LEFT, Loc.TOP_RIGHT):
                if height < min_height:
                    top = bottom - min_height
            elif self._active_region in (Loc.BOTTOM, Loc.BOTTOM_LEFT, Loc.BOTTOM_RIGHT):
                if height < min_height:
                    bottom = top + min_height

        else:
            if (
                left < 0
                or top < 0
                or right > pb_width
                or bottom > pb_height
                or width < min_width
                or height < min_height
            ):
                left = self._crop.x
                right = self._crop.x + self._crop.width - 1
                top = self._crop.y
                bottom = self._crop.y + self._crop.height - 1

        self._crop.x = int(left)
        self._crop.y = int(top)
        self._crop.width = int(right - left + 1)
        self._crop.height = int(bottom - top + 1)
        self._crop_to_widget()

        self.queue_draw()

    def _update_pixbufs(self) -> None:
        allocated_width = self.get_width()
        allocated_height = self.get_height()

        assert self._browse_pixbuf
        width = self._browse_pixbuf.get_width()
        height = self._browse_pixbuf.get_height()

        scale = allocated_height / float(height)
        if scale * width > allocated_width:
            scale = allocated_width / float(width)

        dest_width = int(width * scale)
        dest_height = int(height * scale)

        if dest_width == 0 or dest_height == 0:
            log.warning("Image width or height is zero")
            return

        if (
            self._pixbuf is None
            or self._pixbuf.get_width() != allocated_width
            or self._pixbuf.get_height() != allocated_height
        ):

            self._pixbuf = GdkPixbuf.Pixbuf.new(
                GdkPixbuf.Colorspace.RGB,
                self._browse_pixbuf.get_has_alpha(),
                8,
                dest_width,
                dest_height,
            )

            if self._pixbuf is None:
                return

            self._pixbuf.fill(0x0)

            self._browse_pixbuf.scale(
                self._pixbuf,
                0,
                0,
                dest_width,
                dest_height,
                0,
                0,
                scale,
                scale,
                GdkPixbuf.InterpType.BILINEAR,
            )

            self._generate_color_shifted_pixbuf()

            if self._scale == 1.0:
                scale_to_80 = float(
                    min(
                        (self._pixbuf.get_width() * 0.8 / self._base_width),
                        (self._pixbuf.get_height() * 0.8 / self._base_height),
                    )
                )
                scale_to_image = float(
                    min(
                        (dest_width / self._base_width),
                        (dest_height / self._base_height),
                    )
                )
                crop_scale = float(min(scale_to_80, scale_to_image))

                self._crop.width = int(crop_scale * self._base_width / scale)
                self._crop.height = int(crop_scale * self._base_height / scale)
                self._crop.x = int(
                    (self._browse_pixbuf.get_width() - self._crop.width) / 2
                )
                self._crop.y = int(
                    (self._browse_pixbuf.get_height() - self._crop.height) / 2
                )

            self._scale = scale
            self._image.x = int((allocated_width - dest_width) / 2)
            self._image.y = int((allocated_height - dest_height) / 2)
            self._image.width = dest_width
            self._image.height = dest_height

    def _crop_to_widget(self) -> Gdk.Rectangle:
        crop = Gdk.Rectangle()
        crop.x = int(self._image.x + self._crop.x * self._scale)
        crop.y = int(self._image.y + self._crop.y * self._scale)
        crop.width = int(self._crop.width * self._scale)
        crop.height = int(self._crop.height * self._scale)
        return crop

    def _update_cursor(self, x_coord: float, y_coord: float) -> None:
        region = self._active_region
        if self._active_region == Loc.OUTSIDE:
            crop = self._crop_to_widget()
            region = self._find_location(crop, x_coord, y_coord)

        if region == Loc.TOP_LEFT:
            cursor_name = "nw-resize"
        elif region == Loc.TOP:
            cursor_name = "n-resize"
        elif region == Loc.TOP_RIGHT:
            cursor_name = "ne-resize"
        elif region == Loc.LEFT:
            cursor_name = "w-resize"
        elif region == Loc.INSIDE:
            cursor_name = "all-scroll"
        elif region == Loc.RIGHT:
            cursor_name = "e-resize"
        elif region == Loc.BOTTOM_LEFT:
            cursor_name = "sw-resize"
        elif region == Loc.BOTTOM:
            cursor_name = "s-resize"
        elif region == Loc.BOTTOM_RIGHT:
            cursor_name = "se-resize"
        else:  # Loc.OUTSIDE
            cursor_name = "default"

        if cursor_name is not self._current_cursor:
            self.set_cursor_from_name(cursor_name)
            self._current_cursor = cursor_name

    @staticmethod
    def _eval_radial_line(
        center_x: float, center_y: float, bounds_x: int, bounds_y: int, user_x: int
    ) -> int:
        slope_y = float(bounds_y - center_y)
        slope_x = bounds_x - center_x
        if slope_y == 0 or slope_x == 0:
            # Prevent division by zero
            return 0

        decision_slope = slope_y / slope_x
        decision_intercept = -float(decision_slope * bounds_x)
        return int(decision_slope * user_x + decision_intercept)

    def _find_location(
        self, rect: Gdk.Rectangle, x_coord: float, y_coord: float
    ) -> Loc:
        # pylint: disable=line-too-long
        location = [
            [Loc.OUTSIDE, Loc.OUTSIDE, Loc.OUTSIDE, Loc.OUTSIDE, Loc.OUTSIDE],
            [Loc.OUTSIDE, Loc.TOP_LEFT, Loc.TOP, Loc.TOP_RIGHT, Loc.OUTSIDE],
            [Loc.OUTSIDE, Loc.LEFT, Loc.INSIDE, Loc.RIGHT, Loc.OUTSIDE],
            [Loc.OUTSIDE, Loc.BOTTOM_LEFT, Loc.BOTTOM, Loc.BOTTOM_RIGHT, Loc.OUTSIDE],
            [Loc.OUTSIDE, Loc.OUTSIDE, Loc.OUTSIDE, Loc.OUTSIDE, Loc.OUTSIDE],
        ]
        # pylint: enable=line-too-long

        x_range = self._find_range(x_coord, rect.x, rect.x + rect.width)
        y_range = self._find_range(y_coord, rect.y, rect.y + rect.height)

        return location[y_range][x_range]

    @staticmethod
    def _find_range(coord: float, min_v: int, max_v: int) -> Range:
        tolerance = 12
        if coord < min_v - tolerance:
            return Range.BELOW
        if coord <= min_v + tolerance:
            return Range.LOWER
        if coord < max_v - tolerance:
            return Range.BETWEEN
        if coord <= max_v + tolerance:
            return Range.UPPER
        return Range.ABOVE

    def _generate_color_shifted_pixbuf(self) -> None:
        # pylint: disable=no-member
        assert self._pixbuf
        surface = cairo.ImageSurface(
            cairo.Format.ARGB32, self._pixbuf.get_width(), self._pixbuf.get_height()
        )
        context = cairo.Context(surface)
        # pylint: enable=no-member

        Gdk.cairo_set_source_pixbuf(context, self._pixbuf, 0, 0)
        context.paint()

        context.rectangle(0, 0, 1, 1)
        context.set_source_rgba(0, 0, 0, 0.5)
        context.paint()

        surface = context.get_target()
        assert isinstance(surface, cairo.ImageSurface)
        self._color_shifted_pixbuf = Gdk.pixbuf_get_from_surface(
            surface, 0, 0, surface.get_width(), surface.get_height()
        )
