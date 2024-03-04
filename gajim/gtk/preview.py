# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any
from typing import cast

import logging

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _
from gajim.common.preview import Preview
from gajim.common.preview_helpers import contains_audio_streams
from gajim.common.preview_helpers import format_geo_coords
from gajim.common.preview_helpers import get_icon_for_mime_type
from gajim.common.preview_helpers import split_geo_uri
from gajim.common.types import GdkPixbufType

from gajim.gtk.builder import get_builder
from gajim.gtk.menus import get_preview_menu
from gajim.gtk.preview_audio import AudioWidget
from gajim.gtk.util import ensure_not_destroyed
from gajim.gtk.util import GajimPopover
from gajim.gtk.util import get_cursor
from gajim.gtk.util import load_icon_pixbuf

log = logging.getLogger('gajim.gtk.preview')

PREVIEW_ACTIONS: dict[str, tuple[str, str]] = {
    'open': (_('Open'), 'preview-open'),
    'save_as': (_('Save as…'), 'preview-save-as'),
    'open_folder': (_('Open Folder'), 'preview-open-folder'),
    'copy_link_location': (_('Copy Link'), 'preview-copy-link'),
    'open_link_in_browser': (_('Open Link in Browser'), 'preview-open-link'),
    'download': (_('Download File'), 'preview-download'),
}


class PreviewWidget(Gtk.Box):
    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self)
        self.account = account
        self._preview: Preview | None = None

        self._destroyed = False

        if app.settings.get('use_kib_mib'):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        self._ui = get_builder('preview.ui')
        self._ui.connect_signals(self)
        self.add(self._ui.preview_stack)

        leftclick_action = app.settings.get('preview_leftclick_action')
        self._ui.icon_button.set_tooltip_text(
            PREVIEW_ACTIONS[leftclick_action][0])
        app.settings.connect_signal(
            'preview_leftclick_action', self._update_icon_button_tooltip)

        self.connect('destroy', self._on_destroy)

        self.show_all()

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        self._destroyed = True

    def _update_icon_button_tooltip(self, setting: str, *args: Any) -> None:
        self._ui.icon_button.set_tooltip_text(
            PREVIEW_ACTIONS[setting][0])

    def get_text(self) -> str:
        if self._preview is None:
            return ''
        return self._preview.uri

    @ensure_not_destroyed
    def update_progress(self, _preview: Preview, progress: float) -> None:
        self._ui.preview_stack.set_visible_child_name('preview')
        self._ui.download_button.hide()

        self._ui.progress_box.show()
        self._ui.progress_text.set_label(f'{int(progress * 100)} %')
        self._ui.progressbar.set_fraction(progress)
        self._ui.info_message.set_text(_('Downloading…'))
        self._ui.info_message.set_tooltip_text('')

    @ensure_not_destroyed
    def update(self, preview: Preview, data: GdkPixbufType | None) -> None:
        self._preview = preview

        self._ui.preview_stack.set_visible_child_name('preview')
        self._ui.progress_box.hide()
        self._ui.info_message.hide()

        if preview.is_geo_uri:
            data = load_icon_pixbuf('map', size=preview.size)

        if isinstance(data, GdkPixbuf.PixbufAnimation):
            image = Gtk.Image.new_from_animation(data)
            self._ui.image_button.set_image(image)
        elif isinstance(data, GdkPixbuf.Pixbuf):
            image = Gtk.Image.new_from_pixbuf(data)
            self._ui.image_button.set_image(image)
        else:
            icon = get_icon_for_mime_type(preview.mime_type)
            image = Gtk.Image.new_from_gicon(icon, Gtk.IconSize.DIALOG)
            self._ui.icon_button.set_image(image)

        self._ui.image_button.set_tooltip_text(preview.filename)

        if preview.is_geo_uri:
            self._ui.icon_event_box.hide()
            self._ui.file_name.set_text(_('Click to view location'))
            self._ui.file_name.set_selectable(False)
            self._ui.save_as_button.hide()
            self._ui.open_folder_button.hide()
            self._ui.download_button.hide()

            location = split_geo_uri(preview.uri)
            text = format_geo_coords(float(location.lat), float(location.lon))
            self._ui.file_size.set_text(text)
            self._ui.image_button.set_tooltip_text(
                _('Location at %s') % text)
            self._ui.preview_box.set_size_request(160, -1)
            return

        preview_enabled = app.settings.get('enable_file_preview')

        if preview_enabled and preview.is_previewable and preview.orig_exists:
            self._ui.icon_event_box.hide()
            self._ui.image_button.show()
            self._ui.save_as_button.show()
            self._ui.open_folder_button.show()
        else:
            self._ui.image_button.hide()
            self._ui.icon_event_box.show()
            image.set_property('pixel-size', 64)

        file_size_string = _('File size unknown')
        if preview.file_size != 0:
            file_size_string = GLib.format_size_full(
                preview.file_size, self._units)

        self._ui.link_button.set_uri(preview.uri)
        self._ui.link_button.set_tooltip_text(preview.uri)
        self._ui.link_button.set_label(preview.uri)
        label = cast(Gtk.Label, self._ui.link_button.get_children()[0])
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

            if (preview_enabled and
                    preview.orig_path is not None and
                    preview.is_audio and
                    app.is_installed('GST') and
                    contains_audio_streams(preview.orig_path)):
                self._ui.image_button.hide()
                audio_widget = AudioWidget(preview.orig_path)
                self._ui.right_box.pack_end(audio_widget, False, True, 0)
                self._ui.right_box.reorder_child(audio_widget, 1)
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
            allow_in_public = app.settings.get('preview_anonymous_muc')
            if (preview.context == 'public' and not
                    allow_in_public and not preview.from_us):
                image = Gtk.Image.new_from_icon_name(
                    'dialog-question', Gtk.IconSize.DIALOG)
                self._ui.icon_button.set_image(image)
                self._ui.download_button.show()
                file_size_string = _('Automatic preview disabled')

        self._ui.file_size.set_text(file_size_string)
        self._ui.file_name.set_text(preview.filename)
        self._ui.file_name.set_tooltip_text(preview.filename)

    def _on_download(self, _button: Gtk.Button) -> None:
        if self._preview is None:
            return

        variant = GLib.Variant('s', self._preview.id)
        app.window.activate_action('preview-download', variant)

    def _on_save_as(self, _button: Gtk.Button) -> None:
        assert self._preview is not None
        variant = GLib.Variant('s', self._preview.id)
        app.window.activate_action('preview-save-as', variant)

    def _on_open_folder(self, _button: Gtk.Button) -> None:
        assert self._preview is not None
        variant = GLib.Variant('s', self._preview.id)
        app.window.activate_action('preview-open-folder', variant)

    def _on_content_button_clicked(self, _button: Gtk.Button) -> None:
        if self._preview is None:
            return

        leftclick_action = app.settings.get('preview_leftclick_action')
        variant = GLib.Variant('s', self._preview.id)
        action = PREVIEW_ACTIONS[leftclick_action][1]
        app.window.activate_action(action, variant)

    def _on_button_press_event(self,
                               _button: Gtk.Button,
                               event: Gdk.EventButton
                               ) -> None:

        if self._preview is None:
            return

        if (event.type == Gdk.EventType.BUTTON_PRESS and
                event.button == Gdk.BUTTON_SECONDARY):
            menu = get_preview_menu(self._preview)
            popover = GajimPopover(menu, relative_to=self, event=event)
            popover.popup()

    def _on_cancel_download_clicked(self, _button: Gtk.Button) -> None:
        assert self._preview is not None
        app.preview_manager.cancel_download(self._preview)

    @staticmethod
    def _on_realize(event_box: Gtk.EventBox) -> None:
        window = event_box.get_window()
        assert window
        window.set_cursor(get_cursor('pointer'))
