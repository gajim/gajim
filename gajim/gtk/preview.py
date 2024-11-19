# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any
from typing import cast

import logging

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.preview import Preview
from gajim.common.util.preview import contains_audio_streams
from gajim.common.util.preview import format_geo_coords
from gajim.common.util.preview import get_icon_for_mime_type
from gajim.common.util.preview import split_geo_uri

from gajim.gtk.builder import get_builder
from gajim.gtk.menus import get_preview_menu
from gajim.gtk.preview_audio import AudioWidget
from gajim.gtk.util import ensure_not_destroyed
from gajim.gtk.util import GajimPopover
from gajim.gtk.util import SignalManager

log = logging.getLogger("gajim.gtk.preview")

PREVIEW_ACTIONS: dict[str, tuple[str, str]] = {
    "open": (_("Open"), "win.preview-open"),
    "save_as": (_("Save as…"), "win.preview-save-as"),
    "open_folder": (_("Open Folder"), "win.preview-open-folder"),
    "copy_link_location": (_("Copy Link"), "win.preview-copy-link"),
    "open_link_in_browser": (_("Open Link in Browser"), "win.preview-open-link"),
    "download": (_("Download File"), "win.preview-download"),
}


class PreviewWidget(Gtk.Box, SignalManager):
    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        self.account = account
        self._preview: Preview | None = None

        self._destroyed = False

        if app.settings.get("use_kib_mib"):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        self._ui = get_builder("preview.ui")
        self.append(self._ui.preview_stack)

        self._connect(self._ui.icon_button, "clicked", self._on_content_button_clicked)
        self._connect(
            self._ui.cancel_download_button, "clicked", self._on_cancel_download_clicked
        )
        self._connect(self._ui.image_button, "clicked", self._on_content_button_clicked)

        content_hover_controller = Gtk.EventControllerMotion()
        self._connect(content_hover_controller, "enter", self._on_content_cursor_enter)
        self._connect(content_hover_controller, "leave", self._on_content_cursor_leave)
        self._ui.preview_box.add_controller(content_hover_controller)

        self._connect(self._ui.open_folder_button, "clicked", self._on_open_folder)
        self._connect(self._ui.save_as_button, "clicked", self._on_save_as)
        self._connect(self._ui.download_button, "clicked", self._on_download)

        pointer_cursor = Gdk.Cursor.new_from_name("pointer")
        self._ui.icon_button.set_cursor(pointer_cursor)
        self._ui.cancel_download_button.set_cursor(pointer_cursor)
        self._ui.image_button.set_cursor(pointer_cursor)
        self._ui.download_button.set_cursor(pointer_cursor)
        self._ui.save_as_button.set_cursor(pointer_cursor)
        self._ui.open_folder_button.set_cursor(pointer_cursor)

        self._menu_popover = GajimPopover(None)
        self.append(self._menu_popover)

        leftclick_action = app.settings.get("preview_leftclick_action")
        self._ui.icon_button.set_tooltip_text(PREVIEW_ACTIONS[leftclick_action][0])

        gesture_secondary_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        self._connect(gesture_secondary_click, "pressed", self._on_preview_clicked)
        self.add_controller(gesture_secondary_click)

        app.settings.connect_signal(
            "preview_leftclick_action", self._update_icon_button_tooltip
        )

    def do_unroot(self) -> None:
        self._destroyed = True
        self._disconnect_all()
        app.settings.disconnect_signals(self)
        self._preview = None
        del self._preview
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _update_icon_button_tooltip(self, setting: str, *args: Any) -> None:
        self._ui.icon_button.set_tooltip_text(PREVIEW_ACTIONS[setting][0])

    def get_text(self) -> str:
        if self._preview is None:
            return ""
        return self._preview.uri

    @ensure_not_destroyed
    def update_progress(self, preview: Preview, progress: float) -> None:
        self._preview = preview

        self._ui.preview_stack.set_visible_child_name("preview")
        self._ui.download_button.hide()

        self._ui.progress_box.show()
        self._ui.progress_text.set_label(f"{int(progress * 100)} %")
        self._ui.progressbar.set_fraction(progress)
        self._ui.info_message.set_text(_("Downloading…"))
        self._ui.info_message.set_tooltip_text("")

    @ensure_not_destroyed
    def update(self, preview: Preview, data: bytes | None) -> None:
        self._preview = preview

        self._ui.preview_stack.set_visible_child_name("preview")
        self._ui.progress_box.hide()
        self._ui.info_message.hide()

        if preview.is_geo_uri:
            image = Gtk.Image.new_from_gicon(Gio.ThemedIcon(name="map"))
            image.set_pixel_size(preview.size)
            self._ui.image_button.set_child(image)

            self._ui.icon_event_box.hide()
            self._ui.file_name.set_text(_("Click to view location"))
            self._ui.file_name.set_selectable(False)
            self._ui.save_as_button.hide()
            self._ui.open_folder_button.hide()
            self._ui.download_button.hide()

            location = split_geo_uri(preview.uri)
            text = format_geo_coords(float(location.lat), float(location.lon))
            self._ui.file_size.set_text(text)
            self._ui.image_button.set_tooltip_text(_("Location at %s") % text)
            self._ui.preview_box.set_size_request(160, -1)
            return

        self._ui.image_button.set_tooltip_text(preview.filename)

        if data is not None:
            texture = Gdk.Texture.new_from_bytes(GLib.Bytes.new(data))

            max_preview_size = app.settings.get("preview_size")

            texture_width = texture.get_width()
            texture_height = texture.get_height()

            if texture_width > max_preview_size or texture_height > max_preview_size:
                # Scale down with or height to max_preview_size
                if texture_width > texture_height:
                    width = max_preview_size
                    height = int(max_preview_size / texture_width * texture_height)
                else:
                    width = int(max_preview_size / texture_height * texture_width)
                    height = max_preview_size
            else:
                width = texture_width
                height = texture_height

            image = Gtk.Picture.new_for_paintable(texture)
            image.add_css_class("preview-image")
            image.set_size_request(width, height)

            self._ui.image_button.set_child(image)
            self._ui.image_button.set_tooltip_text(None)

            self._ui.button_box.unparent()
            self._ui.content_overlay.add_overlay(self._ui.button_box)
            self._ui.button_box.set_visible(False)

            self._ui.button_box.set_valign(Gtk.Align.END)
            self._ui.button_box.set_halign(Gtk.Align.FILL)
            self._ui.button_box.set_can_target(True)

            self._ui.preview_stack.remove_css_class("preview-stack")
            self._ui.preview_stack.add_css_class("preview-stack-image")
            self._ui.button_box.add_css_class("preview-image-overlay")
            self._ui.open_folder_button.add_css_class("preview-image-overlay-button")
            self._ui.save_as_button.add_css_class("preview-image-overlay-button")

        else:
            icon = get_icon_for_mime_type(preview.mime_type)
            image = Gtk.Image.new_from_gicon(icon)
            image.set_pixel_size(64)
            self._ui.icon_button.set_child(image)

        preview_enabled = app.settings.get("enable_file_preview")

        if preview_enabled and preview.is_previewable and preview.orig_exists:
            self._ui.icon_event_box.hide()
            self._ui.image_button.show()
            self._ui.save_as_button.show()
            self._ui.open_folder_button.show()
        else:
            self._ui.image_button.hide()
            self._ui.icon_event_box.show()

        file_size_string = _("File size unknown")
        if preview.file_size != 0:
            file_size_string = GLib.format_size_full(preview.file_size, self._units)

        self._ui.link_button.set_uri(preview.uri)
        self._ui.link_button.set_tooltip_text(preview.uri)
        self._ui.link_button.set_label(preview.uri)
        label = cast(Gtk.Label, self._ui.link_button.get_child())
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(32)

        if preview.info_message is not None:
            self._ui.info_message.set_text(preview.info_message)
            self._ui.info_message.set_tooltip_text(preview.info_message)
            self._ui.info_message.show()

        if preview.orig_exists:
            if preview_enabled:
                self._ui.link_button.hide()

            self._ui.download_button.hide()
            self._ui.open_folder_button.show()
            self._ui.save_as_button.show()

            if (
                preview_enabled
                and preview.orig_path is not None
                and preview.is_audio
                and app.is_installed("GST")
                and contains_audio_streams(preview.orig_path)
            ):
                self._ui.image_button.hide()
                audio_widget = AudioWidget(preview.orig_path)
                self._ui.right_box.append(audio_widget)
                self._ui.right_box.reorder_child_after(
                    audio_widget, self._ui.content_box
                )
        else:
            if preview.file_size == 0:
                if preview_enabled:
                    self._ui.download_button.hide()
                else:
                    self._ui.download_button.show()
                self._ui.link_button.show()
            else:
                self._ui.download_button.show()
            self._ui.save_as_button.hide()
            self._ui.open_folder_button.hide()
            allow_in_public = app.settings.get("preview_anonymous_muc")
            if (
                preview.context == "public"
                and not allow_in_public
                and not preview.from_us
            ):
                image = Gtk.Image.new_from_icon_name("dialog-question")
                image.set_pixel_size(64)
                self._ui.icon_button.set_child(image)
                self._ui.download_button.show()
                file_size_string = _("Automatic preview disabled")

        self._ui.file_size.set_text(file_size_string)
        self._ui.file_name.set_text(preview.filename)
        self._ui.file_name.set_tooltip_text(preview.filename)

    def _on_download(self, _button: Gtk.Button) -> None:
        if self._preview is None:
            return

        variant = GLib.Variant("s", self._preview.id)
        app.window.activate_action("win.preview-download", variant)

    def _on_save_as(self, _button: Gtk.Button) -> None:
        assert self._preview is not None
        variant = GLib.Variant("s", self._preview.id)
        app.window.activate_action("win.preview-save-as", variant)

    def _on_open_folder(self, _button: Gtk.Button) -> None:
        assert self._preview is not None
        variant = GLib.Variant("s", self._preview.id)
        app.window.activate_action("win.preview-open-folder", variant)

    def _on_content_button_clicked(self, _button: Gtk.Button) -> None:
        if self._preview is None:
            return

        leftclick_action = app.settings.get("preview_leftclick_action")
        variant = GLib.Variant("s", self._preview.id)
        action = PREVIEW_ACTIONS[leftclick_action][1]
        app.window.activate_action(action, variant)

    def _on_preview_clicked(
        self,
        _gesture_click: Gtk.GestureClick,
        _n_press: int,
        x: float,
        y: float,
    ) -> None:
        if self._preview is None:
            return

        menu = get_preview_menu(self._preview)
        self._menu_popover.set_menu_model(menu)
        self._menu_popover.set_pointing_to_coord(x, y)
        self._menu_popover.popup()

    def _on_content_cursor_enter(
        self,
        _controller: Gtk.EventControllerMotion,
        _x: int,
        _y: int,
    ) -> None:
        assert self._preview is not None
        if self._preview.mime_type.startswith("image/"):
            self._ui.button_box.set_visible(True)

    def _on_content_cursor_leave(
        self,
        _controller: Gtk.EventControllerMotion,
    ) -> None:
        assert self._preview is not None
        if self._preview.mime_type.startswith("image/"):
            self._ui.button_box.set_visible(False)

    def _on_cancel_download_clicked(self, _button: Gtk.Button) -> None:
        assert self._preview is not None
        app.preview_manager.cancel_download(self._preview)
