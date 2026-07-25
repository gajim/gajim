# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import typing

import logging
from concurrent.futures import Future
from functools import partial
from pathlib import Path

from gi.repository import Adw
from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import IMAGE_MIME_TYPES
from gajim.common.const import VIDEO_MIME_TYPES
from gajim.common.multiprocess.thumbnail import create_thumbnail
from gajim.common.multiprocess.video_thumbnail import (
    extract_video_thumbnail_and_properties,
)
from gajim.common.util.filesystem import load_file_async
from gajim.common.util.image import image_size
from gajim.common.util.image import is_image_animated

from gajim.gtk.preview.animated_image import AnimatedImage
from gajim.gtk.preview.animated_image_backend import AnimatedImageBackend
from gajim.gtk.preview.animated_image_fallback_backend import (
    AnimatedImageFallbackBackend,
)
from gajim.gtk.preview.file_control_buttons import FileControlButtons
from gajim.gtk.preview.misc import LoadingBox  # noqa: F401 # type: ignore
from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string

log = logging.getLogger("gajim.gtk.preview.image")


MIN_PREVIEW_WIDTH = 100

# Previews are scaled down in steps of this many pixels.
PREVIEW_WIDTH_STEP = 10


class ImagePreviewLayout(Gtk.BinLayout):
    """Scales the preview down to the available width in discrete steps.

    do_measure() must report a height which does not depend on the width it is
    offered. A row which grows taller as it gets wider makes the height-for-width
    of the conversation's Gtk.ListBox non-monotonic, and GTK's size allocation
    then under-allocates it ("gtk_distribute_natural_allocation: assertion
    'extra_space >= 0' failed", triggered by an image preview followed by a
    wrapping message).

    The width the preview scales to is therefore not taken from the measured
    for_size, but re-picked from the last allocation, in steps and with
    hysteresis. Each individual measure pass stays self-consistent that way.
    """

    __gtype_name__ = "ImagePreviewLayout"

    def __init__(self) -> None:
        Gtk.BinLayout.__init__(self)
        self._dimension: tuple[int, int] | None = None
        self._preview_width: int | None = None
        self._update_id: int | None = None

    def set_preview_dimension(self, width: int, height: int) -> None:
        self._dimension = (max(width, 1), max(height, 1))
        self._preview_width = None
        self.layout_changed()

    def reset(self) -> None:
        if self._update_id is not None:
            GLib.source_remove(self._update_id)
            self._update_id = None

    def do_get_request_mode(self, widget: Gtk.Widget) -> Gtk.SizeRequestMode:
        return Gtk.SizeRequestMode.HEIGHT_FOR_WIDTH

    def _get_preview_size(self) -> tuple[int, int]:
        assert self._dimension is not None
        width, height = self._dimension

        if self._preview_width is None:
            # Nothing has been allocated yet, ask for the full size
            return width, height

        preview_width = min(
            max(self._preview_width, min(width, MIN_PREVIEW_WIDTH)), width
        )
        return preview_width, round(preview_width * height / width)

    def do_measure(
        self, widget: Gtk.Widget, orientation: Gtk.Orientation, for_size: int
    ) -> tuple[int, int, int, int]:
        if self._dimension is None:
            minimum, natural, *_ = Gtk.BinLayout.do_measure(
                self, widget, orientation, for_size
            )
            return minimum, natural, -1, -1

        width, _height = self._dimension
        _, preview_height = self._get_preview_size()

        if orientation == Gtk.Orientation.HORIZONTAL:
            # Keep asking for the full width, otherwise the preview could never
            # find out that there is room to grow again
            return min(width, MIN_PREVIEW_WIDTH), width, -1, -1

        return preview_height, preview_height, -1, -1

    def do_allocate(
        self, widget: Gtk.Widget, width: int, height: int, baseline: int
    ) -> None:
        available_width = width

        if self._dimension is not None:
            preview_width, _ = self._get_preview_size()
            # The height we reported belongs to preview_width, don't let the
            # image get any wider than that or it would be letterboxed
            width = min(width, preview_width)

        Gtk.BinLayout.do_allocate(self, widget, width, height, baseline)

        self._queue_preview_width(available_width)

    def _get_target_width(self, available_width: int) -> int:
        assert self._dimension is not None
        width, _height = self._dimension

        if available_width >= width:
            # There is room for the full size, don't round it down
            target = width
        else:
            target = max(
                available_width // PREVIEW_WIDTH_STEP * PREVIEW_WIDTH_STEP,
                PREVIEW_WIDTH_STEP,
            )

        if self._preview_width is None:
            return target

        if available_width < self._preview_width:
            # The preview does not fit anymore, it has to shrink
            return target

        if available_width - self._preview_width < 2 * PREVIEW_WIDTH_STEP:
            # Stay as is, only grow once there is a step to spare. This is the
            # hysteresis which keeps a scrollbar from toggling the size.
            return self._preview_width

        return target

    def _queue_preview_width(self, available_width: int) -> None:
        if self._dimension is None or self._update_id is not None:
            return

        target = self._get_target_width(available_width)
        if target == self._preview_width:
            return

        # Resizing from within size allocation is not allowed, defer it
        self._update_id = GLib.idle_add(self._apply_preview_width, target)

    def _apply_preview_width(self, target: int) -> bool:
        self._update_id = None

        if target != self._preview_width:
            self._preview_width = target
            self.layout_changed()

        return GLib.SOURCE_REMOVE


@Gtk.Template.from_string(string=get_ui_string("preview/image.ui"))
class ImagePreviewWidget(Gtk.Box, SignalManager):
    __gtype_name__ = "ImagePreviewWidget"

    __gsignals__ = {
        "display-error": (
            GObject.SignalFlags.RUN_LAST | GObject.SignalFlags.ACTION,
            None,
            (),
        )
    }

    _stack: Gtk.Stack = Gtk.Template.Child()
    _content_clamp: Adw.Clamp = Gtk.Template.Child()
    _content_overlay: Gtk.Overlay = Gtk.Template.Child()
    _image_button: Gtk.Button = Gtk.Template.Child()
    _picture: Gtk.Picture = Gtk.Template.Child()
    _play_image: Gtk.Image = Gtk.Template.Child()
    _file_control_buttons: FileControlButtons = Gtk.Template.Child()

    def __init__(
        self,
        filename: str,
        file_size: int,
        mime_type: str,
        orig_path: Path,
        thumb_path: Path,
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self._orig_path = orig_path
        self._thumb_path = thumb_path
        self._filename = filename
        self._mime_type = mime_type

        self._layout = ImagePreviewLayout()
        self.set_layout_manager(self._layout)

        if mime_type in IMAGE_MIME_TYPES:
            self._type = "image"
        elif mime_type in VIDEO_MIME_TYPES:
            self._type = "video"
        else:
            raise ValueError("Not supported mime type: %s" % mime_type)

        content_hover_controller = Gtk.EventControllerMotion()
        self._connect(content_hover_controller, "enter", self._on_content_cursor_enter)
        self._connect(content_hover_controller, "leave", self._on_content_cursor_leave)
        self.add_controller(content_hover_controller)

        self._file_control_buttons.set_file_size(file_size)
        self._file_control_buttons.set_file_name(filename)
        self._file_control_buttons.set_path(orig_path)

        pointer_cursor = Gdk.Cursor.new_from_name("pointer")
        self._image_button.set_cursor(pointer_cursor)
        self._image_button.set_action_target_value(
            GLib.Variant("s", str(self._orig_path))
        )

        if not self._thumb_path.exists():
            self._create_thumbnail(self._type)
        else:
            load_file_async(self._thumb_path, self._on_thumb_load_finished)

    def _on_thumb_load_finished(
        self, data: bytes | None, error: GLib.Error | None, user_data: typing.Any
    ) -> None:
        if data is None:
            log.error("Loading thumbnail failed, %s: %s", self._thumb_path.name, error)
            self.emit("display-error")
            return

        self._thumbnail = data
        self._display_image_preview()

    def _create_thumbnail(self, type_: typing.Literal["image", "video"]) -> None:
        if type_ == "image":
            self._create_image_thumbnail()
        elif type_ == "video":
            self._create_video_thumbnail()

    def _create_image_thumbnail(self) -> None:
        assert self._thumb_path is not None
        assert self._orig_path is not None
        try:
            future = app.process_pool.submit(
                create_thumbnail,
                self._orig_path,
                self._thumb_path,
                app.settings.get("preview_size") * app.window.get_scale_factor(),
                self._mime_type,
            )
            future.add_done_callback(
                partial(GLib.idle_add, self._create_thumbnail_finished)
            )
        except Exception as error:
            log.warning("Creating thumbnail failed for: %s %s", self._orig_path, error)
            self.emit("display-error")

    def _create_video_thumbnail(self) -> None:
        assert self._orig_path is not None

        try:
            future = app.process_pool.submit(
                extract_video_thumbnail_and_properties,
                self._orig_path,
                self._thumb_path,
                app.settings.get("preview_size"),
            )
            future.add_done_callback(
                partial(GLib.idle_add, self._create_thumbnail_finished)
            )
        except Exception as error:
            log.warning("Creating thumbnail failed for: %s %s", self._orig_path, error)
            self.emit("display-error")

    def _create_thumbnail_finished(
        self, future: Future[tuple[bytes, dict[str, typing.Any]]]
    ) -> bool:
        try:
            thumbnail_bytes, _metadata = future.result()
        except Exception as error:
            log.exception(
                "Creating thumbnail failed for: %s %s", self._orig_path, error
            )
            self.emit("display-error")

        else:
            self._thumbnail = thumbnail_bytes
            self._display_image_preview()

        return GLib.SOURCE_REMOVE

    def _display_image_preview(self) -> None:
        if self._mime_type == "image/gif" and is_image_animated(self._orig_path):
            self._display_animated_image_preview(AnimatedImageBackend)
            return

        if self._mime_type in [
            "image/webp",
            "image/avif",
            "image/png",
        ] and is_image_animated(self._orig_path):
            self._display_animated_image_preview(AnimatedImageFallbackBackend)
            return

        self._display_static_image_preview()

    def _image_preview_dimension(
        self, image_width: int, image_height: int
    ) -> tuple[int, int]:
        max_preview_size = app.settings.get("preview_size")
        if image_width > max_preview_size or image_height > max_preview_size:
            # Scale down with or height to max_preview_size
            if image_width > image_height:
                width = max_preview_size
                height = int(max_preview_size / image_width * image_height)
            else:
                width = int(max_preview_size / image_height * image_width)
                height = max_preview_size
        else:
            width = image_width
            height = image_height

        return width, height

    def _set_preview_dimension(self, width: int, height: int) -> None:
        self._content_clamp.set_maximum_size(width)
        self._content_clamp.set_tightening_threshold(width)
        self._layout.set_preview_dimension(width, height)

    def _display_static_image_preview(self) -> None:
        try:
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(self._thumbnail))
        except GLib.Error:
            log.exception("Could not load image %s", self._filename)
            self.emit("display-error")
            return

        texture_width = texture.get_width()
        texture_height = texture.get_height()

        width, height = self._image_preview_dimension(texture_width, texture_height)

        self._set_preview_dimension(width, height)
        self._image_button.set_tooltip_text(self._filename)
        self._picture.set_paintable(texture)

        if self._type == "video":
            self._image_button.add_css_class("preview-video-overlay")
            self._play_image.set_pixel_size(min(width, height) // 3)
            self._play_image.set_visible(True)

        self._stack.set_visible_child_name("preview")

    def _display_animated_image_preview(
        self, backend: typing.Any[AnimatedImageBackend, AnimatedImageFallbackBackend]
    ) -> None:
        image_width, image_height = image_size(self._orig_path)
        width, height = self._image_preview_dimension(image_width, image_height)

        animated_image = AnimatedImage(self._thumb_path, self._orig_path, backend)
        pointer_cursor = Gdk.Cursor.new_from_name("pointer")
        animated_image.set_cursor(pointer_cursor)

        self._connect(animated_image, "error", self._on_animated_image_error)

        self._set_preview_dimension(width, height)
        self._content_overlay.set_child(animated_image)
        self._image_button.set_tooltip_text(self._filename)
        self._stack.set_visible_child_name("preview")

    def _on_animated_image_error(self, _animated_image: AnimatedImage) -> None:
        Gio.AppInfo.launch_default_for_uri(self._orig_path.as_uri(), None)

    def _on_content_cursor_enter(
        self,
        _controller: Gtk.EventControllerMotion,
        _x: int,
        _y: int,
    ) -> None:
        self._file_control_buttons.set_visible(True)

    def _on_content_cursor_leave(
        self,
        _controller: Gtk.EventControllerMotion,
    ) -> None:
        self._file_control_buttons.set_visible(False)

    def do_unroot(self) -> None:
        self._layout.reset()
        Gtk.Box.do_unroot(self)
        self._disconnect_all()
