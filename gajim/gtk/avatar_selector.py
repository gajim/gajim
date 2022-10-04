# This is a port of um-crop-area.c from GNOME’s 'Cheese' application, see
# https://gitlab.gnome.org/GNOME/cheese/-/blob/3.34.0/libcheese/um-crop-area.c
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

from typing import Any
from typing import cast
from typing import Optional

import os
import logging
from enum import IntEnum
from enum import unique

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk
import cairo

from gajim.common import app
from gajim.common.const import AvatarSize
from gajim.common.i18n import _
from gajim.common.helpers import get_file_path_from_dnd_dropped_uri

from .dialogs import ErrorDialog
from .filechoosers import AvatarChooserDialog
from .util import scale_with_ratio

log = logging.getLogger('gajim.gui.avatar_selector')


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


class AvatarSelector(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self, orientation=Gtk.Orientation.VERTICAL,
                         spacing=12)
        self.get_style_context().add_class('avatar-selector')

        uri_entry = Gtk.TargetEntry.new(
            'text/uri-list', Gtk.TargetFlags.OTHER_APP, 80)
        dst_targets = Gtk.TargetList.new([uri_entry])

        self.drag_dest_set(
            Gtk.DestDefaults.ALL,
            [uri_entry],
            Gdk.DragAction.COPY | Gdk.DragAction.MOVE)
        self.drag_dest_set_target_list(dst_targets)
        self.connect('drag-data-received', self._on_drag_data_received)
        self.connect('destroy', self._on_destroy)

        self._crop_area = CropArea()
        self._crop_area.set_vexpand(True)
        self.add(self._crop_area)

        self._load_button = Gtk.Button()
        self._load_button.set_label(_('Load Image'))
        self._load_button.set_halign(Gtk.Align.CENTER)
        self._load_button.set_no_show_all(True)
        self._load_button.connect('clicked', self._on_load_clicked)
        self._load_button.show()
        self.add(self._load_button)

        self._helper_label = Gtk.Label(
            label=_('…or drop it here'))
        self._helper_label.get_style_context().add_class('bold')
        self._helper_label.get_style_context().add_class('dim-label')
        self._helper_label.set_vexpand(True)
        self._helper_label.set_no_show_all(True)
        self._helper_label.show()
        self.add(self._helper_label)

        self.show_all()

    def _on_destroy(self, *args: Any) -> None:
        app.check_finalize(self)

    def reset(self) -> None:
        self._load_button.show()
        self._helper_label.show()
        self._crop_area.hide()

    def prepare_crop_area(self, path: str) -> None:
        pixbuf = self._get_pixbuf_from_path(path)
        if pixbuf is None:
            log.info('Could not load from path %s', path)
            return

        self._crop_area.set_pixbuf(pixbuf)
        self._load_button.hide()
        self._helper_label.hide()
        self._crop_area.show()

    def _on_load_clicked(self, _button: Gtk.Button) -> None:
        def _on_file_selected(path: str) -> None:
            self.prepare_crop_area(path)

        AvatarChooserDialog(_on_file_selected,
                            transient_for=self.get_toplevel(),
                            modal=True)

    def _on_drag_data_received(self,
                               _widget: Gtk.Widget,
                               _context: Gdk.DragContext,
                               _x_coord: int,
                               _y_coord: int,
                               selection: Gtk.SelectionData,
                               target_type: int,
                               _timestamp: int
                               ) -> None:
        if not selection.get_data():
            return

        if target_type == 80:
            uri_split = selection.get_uris()  # Might be more than one
            path = get_file_path_from_dnd_dropped_uri(uri_split[0])
            if not os.path.isfile(path):
                return
            self.prepare_crop_area(path)

    @staticmethod
    def _get_pixbuf_from_path(path: str) -> Optional[GdkPixbuf.Pixbuf]:
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(path)
            return pixbuf
        except GLib.Error as err:
            log.error('Unable to load file %s: %s', path, str(err))
            return None

    def get_prepared(self) -> bool:
        return bool(self._crop_area.get_pixbuf())

    @staticmethod
    def _scale_for_publish(pixbuf: GdkPixbuf.Pixbuf
                           ) -> tuple[GdkPixbuf.Pixbuf, int, int]:
        width = pixbuf.get_width()
        height = pixbuf.get_height()
        if width > AvatarSize.PUBLISH or height > AvatarSize.PUBLISH:
            # Scale only down, never up
            width, height = scale_with_ratio(AvatarSize.PUBLISH, width, height)
            scaled_pixbuf = pixbuf.scale_simple(
                width, height, GdkPixbuf.InterpType.BILINEAR)
            assert scaled_pixbuf is not None
            return scaled_pixbuf, width, height
        return pixbuf, width, height

    def get_avatar_surface(self) -> Optional[tuple[cairo.ImageSurface,
                                                   int,
                                                   int]]:
        pixbuf = self._crop_area.get_pixbuf()
        if pixbuf is None:
            return None
        scaled, width, height = self._scale_for_publish(pixbuf)

        return Gdk.cairo_surface_create_from_pixbuf(
            scaled, self.get_scale_factor()), width, height

    def get_avatar_bytes(self) -> tuple[bool, Optional[bytes], int, int]:
        pixbuf = self._crop_area.get_pixbuf()
        if pixbuf is None:
            return False, None, 0, 0
        scaled, width, height = self._scale_for_publish(pixbuf)

        success, data = scaled.save_to_bufferv('png', [], [])
        return success, data, width, height


class CropArea(Gtk.DrawingArea):
    def __init__(self) -> None:
        Gtk.DrawingArea.__init__(self)
        self.set_no_show_all(True)
        self.add_events(
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.POINTER_MOTION_MASK)

        self._image = Gdk.Rectangle()
        self._crop = Gdk.Rectangle()
        self._pixbuf: Optional[GdkPixbuf.Pixbuf] = None
        self._browse_pixbuf: Optional[GdkPixbuf.Pixbuf] = None
        self._color_shifted_pixbuf: Optional[GdkPixbuf.Pixbuf] = None
        self._current_cursor: Optional[Gdk.CursorType] = None

        self._scale = float(0.0)
        self._image.x = 0
        self._image.y = 0
        self._image.width = 0
        self._image.height = 0
        self._active_region = Loc.OUTSIDE
        self._last_press_x = -1
        self._last_press_y = -1
        self._base_width = 10
        self._base_height = 10
        self._aspect = float(1.0)

        self.set_size_request(self._base_width, self._base_height)

        self.connect('draw', self._on_draw)
        self.connect('button-press-event', self._on_button_press)
        self.connect('button-release-event', self._on_button_release)
        self.connect('motion-notify-event', self._on_motion_notify)

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

    def set_pixbuf(self, pixbuf: Optional[GdkPixbuf.Pixbuf]) -> None:
        if pixbuf is None:
            self._browse_pixbuf = None
            avatar_selector = cast(AvatarSelector, self.get_parent())
            avatar_selector.reset()
            return

        self._browse_pixbuf = pixbuf
        width = pixbuf.get_width()
        height = pixbuf.get_height()

        self._crop.width = 2 * self._base_width
        self._crop.height = 2 * self._base_height
        self._crop.x = int(abs((width - self._crop.width) / 2))
        self._crop.y = int(abs((height - self._crop.height) / 2))

        self._scale = 0.0
        self._image.x = 0
        self._image.y = 0
        self._image.width = 0
        self._image.height = 0

        self.queue_draw()

    def get_pixbuf(self) -> Optional[GdkPixbuf.Pixbuf]:
        if self._browse_pixbuf is None:
            return None

        width = self._browse_pixbuf.get_width()
        height = self._browse_pixbuf.get_height()
        width = min(self._crop.width, width - self._crop.x)
        height = min(self._crop.height, height - self._crop.y)

        if width <= 0 or height <= 0:
            return None

        return GdkPixbuf.Pixbuf.new_subpixbuf(
            self._browse_pixbuf, self._crop.x, self._crop.y, width, height)

    def _on_draw(self, _widget: Gtk.Widget, context: cairo.Context) -> bool:
        if self._browse_pixbuf is None:
            return False

        self._update_pixbufs()

        if self._pixbuf is None:
            ErrorDialog(_('Error Loading Image'),
                        _('Selected image could not be loaded.'))
            self.set_pixbuf(None)
            return False

        width = self._pixbuf.get_width()
        height = self._pixbuf.get_height()
        crop = self._crop_to_widget()

        ix = self._image.x
        iy = self._image.y

        assert self._color_shifted_pixbuf is not None
        Gdk.cairo_set_source_pixbuf(
            context, self._color_shifted_pixbuf, ix, iy)
        context.rectangle(
            ix,
            iy,
            width,
            crop.y - iy)
        context.rectangle(
            ix,
            crop.y,
            crop.x - ix,
            crop.height)
        context.rectangle(
            crop.x + crop.width,
            crop.y,
            width - crop.width - (crop.x - ix),
            crop.height)
        context.rectangle(
            ix,
            crop.y + crop.height,
            width,
            height - crop.height - (crop.y - iy))
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
            crop.x + 0.5,
            crop.y + 0.5,
            crop.width - 1.0,
            crop.height - 1.0)
        context.stroke()

        context.set_source_rgb(1, 1, 1)
        context.set_line_width(2.0)
        context.rectangle(
            crop.x + 2.0,
            crop.y + 2.0,
            crop.width - 4.0,
            crop.height - 4.0)
        context.stroke()

        return False

    def _on_button_press(self,
                         _widget: Gtk.Widget,
                         event: Gdk.EventButton
                         ) -> bool:
        if self._browse_pixbuf is None:
            return False

        crop = self._crop_to_widget()

        self._last_press_x = (event.x - self._image.x) / self._scale
        self._last_press_y = (event.y - self._image.y) / self._scale
        self._active_region = self._find_location(crop, event.x, event.y)

        self.queue_draw_area(
            crop.x - 1, crop.y - 1, crop.width + 2, crop.height + 2)

        return False

    def _on_button_release(self,
                           _widget: Gtk.Widget,
                           _event: Gdk.EventButton
                           ) -> bool:
        if self._browse_pixbuf is None:
            return False

        crop = self._crop_to_widget()
        self._last_press_x = -1
        self._last_press_y = -1
        self._active_region = Loc.OUTSIDE

        self.queue_draw_area(
            crop.x - 1, crop.y - 1, crop.width + 2, crop.height + 2)

        return False

    def _on_motion_notify(self,
                          _widget: Gtk.Widget,
                          event: Gdk.EventMotion
                          ) -> bool:
        # pylint: disable=too-many-boolean-expressions
        # pylint: disable=too-many-branches
        # pylint: disable=too-many-statements
        if self._browse_pixbuf is None:
            return False

        self._update_cursor(event.x, event.y)

        damage = self._crop_to_widget()
        self.queue_draw_area(
            damage.x - 1, damage.y - 1, damage.width + 2, damage.height + 2)

        pb_width = self._browse_pixbuf.get_width()
        pb_height = self._browse_pixbuf.get_height()

        x_coord = int((event.x - self._image.x) / self._scale)
        y_coord = int((event.y - self._image.y) / self._scale)

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
                    center_x, center_y, left, top, x_coord):
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
                    center_x, center_y, right, top, x_coord):
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
                    center_x, center_y, left, bottom, x_coord):
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
                    center_x, center_y, right, bottom, x_coord):
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
            return False

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

            if self._active_region in (
                    Loc.LEFT, Loc.TOP_LEFT, Loc.BOTTOM_LEFT):
                if width < min_width:
                    left = right - min_width
            elif self._active_region in (
                    Loc.RIGHT, Loc.TOP_RIGHT, Loc.BOTTOM_RIGHT):
                if width < min_width:
                    right = left + min_width

            if self._active_region in (
                    Loc.TOP, Loc.TOP_LEFT, Loc.TOP_RIGHT):
                if height < min_height:
                    top = bottom - min_height
            elif self._active_region in (
                    Loc.BOTTOM, Loc.BOTTOM_LEFT, Loc.BOTTOM_RIGHT):
                if height < min_height:
                    bottom = top + min_height

        else:
            if (left < 0 or top < 0 or
                    right > pb_width or bottom > pb_height or
                    width < min_width or height < min_height):
                left = self._crop.x
                right = self._crop.x + self._crop.width - 1
                top = self._crop.y
                bottom = self._crop.y + self._crop.height - 1

        self._crop.x = int(left)
        self._crop.y = int(top)
        self._crop.width = int(right - left + 1)
        self._crop.height = int(bottom - top + 1)

        damage = self._crop_to_widget()
        self.queue_draw_area(
            damage.x - 1, damage.y - 1, damage.width + 2, damage.height + 2)

        return False

    def _update_pixbufs(self) -> None:
        allocation = self.get_allocation()
        assert self._browse_pixbuf
        width = self._browse_pixbuf.get_width()
        height = self._browse_pixbuf.get_height()

        scale = allocation.height / float(height)
        if scale * width > allocation.width:
            scale = allocation.width / float(width)

        dest_width = int(width * scale)
        dest_height = int(height * scale)

        if dest_width == 0 or dest_height == 0:
            log.warning('Image width or height is zero')
            return

        if (self._pixbuf is None or
                self._pixbuf.get_width() != allocation.width or
                self._pixbuf.get_height() != allocation.height):

            self._pixbuf = GdkPixbuf.Pixbuf.new(
                GdkPixbuf.Colorspace.RGB,
                self._browse_pixbuf.get_has_alpha(),
                8,
                dest_width,
                dest_height)

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
                GdkPixbuf.InterpType.BILINEAR)

            self._generate_color_shifted_pixbuf()

            if self._scale == 0.0:
                scale_to_80 = float(min(
                    (self._pixbuf.get_width() * 0.8 / self._base_width),
                    (self._pixbuf.get_height() * 0.8 / self._base_height)))
                scale_to_image = float(min(
                    (dest_width / self._base_width),
                    (dest_height / self._base_height)))
                crop_scale = float(min(scale_to_80, scale_to_image))

                self._crop.width = int(crop_scale * self._base_width / scale)
                self._crop.height = int(crop_scale * self._base_height / scale)
                self._crop.x = int((
                    self._browse_pixbuf.get_width() - self._crop.width) / 2)
                self._crop.y = int((
                    self._browse_pixbuf.get_height() - self._crop.height) / 2)

            self._scale = scale
            self._image.x = int((allocation.width - dest_width) / 2)
            self._image.y = int((allocation.height - dest_height) / 2)
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
            cursor_type = Gdk.CursorType.TOP_LEFT_CORNER
        elif region == Loc.TOP:
            cursor_type = Gdk.CursorType.TOP_SIDE
        elif region == Loc.TOP_RIGHT:
            cursor_type = Gdk.CursorType.TOP_RIGHT_CORNER
        elif region == Loc.LEFT:
            cursor_type = Gdk.CursorType.LEFT_SIDE
        elif region == Loc.INSIDE:
            cursor_type = Gdk.CursorType.FLEUR
        elif region == Loc.RIGHT:
            cursor_type = Gdk.CursorType.RIGHT_SIDE
        elif region == Loc.BOTTOM_LEFT:
            cursor_type = Gdk.CursorType.BOTTOM_LEFT_CORNER
        elif region == Loc.BOTTOM:
            cursor_type = Gdk.CursorType.BOTTOM_SIDE
        elif region == Loc.BOTTOM_RIGHT:
            cursor_type = Gdk.CursorType.BOTTOM_RIGHT_CORNER
        else:  # Loc.OUTSIDE
            cursor_type = Gdk.CursorType.LEFT_PTR

        if cursor_type is not self._current_cursor:
            default_display = Gdk.Display.get_default()
            if default_display is None:
                return
            cursor = Gdk.Cursor.new_for_display(
                default_display,
                cursor_type)
            window = self.get_window()
            assert window
            window.set_cursor(cursor)
            self._current_cursor = cursor_type

    @staticmethod
    def _eval_radial_line(center_x: float,
                          center_y: float,
                          bounds_x: int,
                          bounds_y: int,
                          user_x: int
                          ) -> int:
        slope_y = float(bounds_y - center_y)
        slope_x = bounds_x - center_x
        if slope_y == 0 or slope_x == 0:
            # Prevent division by zero
            return 0

        decision_slope = slope_y / slope_x
        decision_intercept = - float(decision_slope * bounds_x)
        return int(decision_slope * user_x + decision_intercept)

    def _find_location(self,
                       rect: Gdk.Rectangle,
                       x_coord: float,
                       y_coord: float
                       ) -> Loc:
        # pylint: disable=line-too-long
        location = [
            [Loc.OUTSIDE, Loc.OUTSIDE, Loc.OUTSIDE, Loc.OUTSIDE, Loc.OUTSIDE],
            [Loc.OUTSIDE, Loc.TOP_LEFT, Loc.TOP, Loc.TOP_RIGHT, Loc.OUTSIDE],
            [Loc.OUTSIDE, Loc.LEFT, Loc.INSIDE, Loc.RIGHT, Loc.OUTSIDE],
            [Loc.OUTSIDE, Loc.BOTTOM_LEFT, Loc.BOTTOM, Loc.BOTTOM_RIGHT,
             Loc.OUTSIDE],
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
            cairo.Format.ARGB32,
            self._pixbuf.get_width(),
            self._pixbuf.get_height())
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
            surface, 0, 0, surface.get_width(), surface.get_height())
