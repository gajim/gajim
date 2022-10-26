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

from typing import cast
from typing import Any
from typing import Optional

import logging
import shutil
import os
from pathlib import Path

from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.helpers import open_file
from gajim.common.helpers import open_uri
from gajim.common.i18n import _
from gajim.common.preview import Preview
from gajim.common.preview_helpers import split_geo_uri
from gajim.common.preview_helpers import format_geo_coords
from gajim.common.preview_helpers import contains_audio_streams
from gajim.common.preview_helpers import get_icon_for_mime_type
from gajim.common.types import GdkPixbufType

from .dialogs import ErrorDialog
from .filechoosers import FileSaveDialog
from .preview_audio import AudioWidget
from .builder import get_builder
from .util import ensure_not_destroyed
from .util import get_cursor
from .util import load_icon_pixbuf

log = logging.getLogger('gajim.gui.preview')

PREVIEW_CLICK_ACTIONS = {
    'open': _('Open'),
    'save_as': _('Save As…'),
    'open_folder': _('Open Folder'),
    'copy_link_location': _('Copy Link Location'),
    'open_link_in_browser': _('Open Link in Browser'),
}


class PreviewWidget(Gtk.Box):
    def __init__(self, account: str) -> None:
        Gtk.Box.__init__(self)
        self.account = account
        self._preview: Optional[Preview] = None

        self._destroyed = False

        if app.settings.get('use_kib_mib'):
            self._units = GLib.FormatSizeFlags.IEC_UNITS
        else:
            self._units = GLib.FormatSizeFlags.DEFAULT

        self._ui = get_builder('preview.ui')
        self._ui.connect_signals(self)
        self.add(self._ui.preview_box)

        leftclick_action = app.settings.get('preview_leftclick_action')
        self._ui.icon_button.set_tooltip_text(
            PREVIEW_CLICK_ACTIONS[leftclick_action])
        app.settings.connect_signal(
            'preview_leftclick_action', self._update_icon_button_tooltip)

        self.connect('destroy', self._on_destroy)

        self.show_all()

    def _on_destroy(self, _widget: Gtk.Widget) -> None:
        self._destroyed = True

    def _update_icon_button_tooltip(self, setting: str, *args: Any) -> None:
        self._ui.icon_button.set_tooltip_text(
            PREVIEW_CLICK_ACTIONS[setting])

    def get_text(self) -> str:
        if self._preview is None:
            return ''
        return self._preview.uri

    @ensure_not_destroyed
    def update_progress(self, _preview: Preview, progress: float) -> None:
        self._ui.download_button.hide()

        self._ui.progress_box.show()
        self._ui.progress_text.set_label(f'{int(progress * 100)} %')
        self._ui.progressbar.set_fraction(progress)
        self._ui.info_message.set_text(_('Downloading…'))
        self._ui.info_message.set_tooltip_text('')

    @ensure_not_destroyed
    def update(self, preview: Preview, data: Optional[GdkPixbufType]) -> None:
        self._preview = preview

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

        if preview.is_previewable and preview.orig_exists:
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
            self._ui.download_button.hide()
            self._ui.open_folder_button.show()
            self._ui.save_as_button.show()
            self._ui.link_button.hide()
            if (preview.orig_path is not None and preview.is_audio and
                    app.is_installed('GST') and
                    contains_audio_streams(preview.orig_path)):
                self._ui.image_button.hide()
                audio_widget = AudioWidget(preview.orig_path)
                self._ui.right_box.pack_end(audio_widget, False, True, 0)
                self._ui.right_box.reorder_child(audio_widget, 1)
        else:
            if preview.file_size == 0:
                self._ui.download_button.hide()
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

    def _get_context_menu(self) -> Gtk.Menu:
        def _destroy(menu: Gtk.Menu, _pspec: Any) -> None:
            visible = menu.get_property('visible')
            if not visible:
                GLib.idle_add(menu.destroy)

        menu = get_builder('preview_context_menu.ui')
        menu.connect_signals(self)
        menu.context_menu.connect('notify::visible', _destroy)

        assert self._preview
        if self._preview.is_aes_encrypted:
            menu.open_link_in_browser.hide()

        if self._preview.is_geo_uri:
            menu.download.hide()
            menu.open_link_in_browser.hide()
            menu.save_as.hide()
            menu.open_folder.hide()
            return menu.context_menu

        if self._preview.orig_exists:
            menu.download.hide()
        else:
            if self._preview.download_in_progress:
                menu.download.hide()
            menu.open.hide()
            menu.save_as.hide()
            menu.open_folder.hide()

        return menu.context_menu

    def _on_download(self, _menu: Gtk.Menu) -> None:
        if self._preview is None:
            return
        if not self._preview.orig_exists:
            app.preview_manager.download_content(self._preview, force=True)

    def _on_open(self, _menu: Gtk.Menu) -> None:
        if self._preview is None:
            return

        if self._preview.is_geo_uri:
            open_uri(self._preview.uri)
            return

        if not self._preview.orig_exists:
            app.preview_manager.download_content(self._preview, force=True)
            return

        assert self._preview.orig_path
        open_file(self._preview.orig_path)

    def _on_save_as(self, _menu: Gtk.Menu) -> None:
        assert self._preview is not None

        def _on_ok(target: str) -> None:
            assert self._preview is not None
            assert self._preview.orig_path is not None

            target_path = Path(target)
            orig_ext = self._preview.orig_path.suffix
            new_ext = target_path.suffix
            if orig_ext != new_ext:
                # Windows file chooser selects the full file name including
                # extension. Starting to type will overwrite the extension
                # as well. Restore the extension if it's lost.
                target_path = target_path.with_suffix(orig_ext)
            dirname = target_path.parent
            if not os.access(dirname, os.W_OK):
                ErrorDialog(
                    _('Directory "%s" is not writable') % dirname,
                    _('You do not have the proper permissions to '
                      'create files in this directory.'),
                    transient_for=app.app.get_active_window())
                return
            shutil.copyfile(str(self._preview.orig_path), target_path)
            file_dir = os.path.dirname(target_path)
            if file_dir:
                app.settings.set('last_save_dir', file_dir)

        if not self._preview.orig_exists:
            app.preview_manager.download_content(self._preview, force=True)
            return

        FileSaveDialog(_on_ok,
                       path=app.settings.get('last_save_dir'),
                       file_name=self._preview.filename,
                       transient_for=app.app.get_active_window())

    def _on_open_folder(self, _menu: Gtk.Menu) -> None:
        assert self._preview
        if not self._preview.orig_exists:
            app.preview_manager.download_content(self._preview, force=True)
            return
        assert self._preview.orig_path
        open_file(self._preview.orig_path.parent)

    def _on_copy_link_location(self, _menu: Gtk.Menu) -> None:
        display = Gdk.Display.get_default()
        assert display is not None
        clipboard = Gtk.Clipboard.get_default(display)
        assert self._preview
        clipboard.set_text(self._preview.uri, -1)

    def _on_open_link_in_browser(self, _menu: Gtk.Menu) -> None:
        assert self._preview
        if self._preview.is_aes_encrypted:
            if self._preview.is_geo_uri:
                open_uri(self._preview.uri)
                return
            assert self._preview.orig_path
            open_file(self._preview.orig_path)
        else:
            open_uri(self._preview.uri)

    def _on_content_button_clicked(self, _button: Gtk.Button) -> None:
        action = app.settings.get('preview_leftclick_action')
        method = getattr(self, f'_on_{action}')
        method(None)

    def _on_button_press_event(self,
                               _button: Gtk.Button,
                               event: Gdk.EventButton
                               ) -> None:
        if event.type == Gdk.EventType.BUTTON_PRESS and event.button == 3:
            # Right click
            menu = self._get_context_menu()
            menu.popup_at_pointer(event)

    def _on_cancel_download_clicked(self, _button: Gtk.Button) -> None:
        assert self._preview is not None
        app.preview_manager.cancel_download(self._preview)

    @staticmethod
    def _on_realize(event_box: Gtk.EventBox) -> None:
        window = event_box.get_window()
        assert window
        window.set_cursor(get_cursor('pointer'))
