# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# Gajim is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from typing import Any
from typing import Callable
from typing import cast

import os
import sys
from pathlib import Path

from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.const import Filter

AcceptCallbackT = Callable[[list[str]], None]


def _require_native() -> bool:
    if app.is_flatpak():
        return True
    if sys.platform in ('win32', 'darwin'):
        return True
    return False


# Notes: Adding mime types to Gtk.FileFilter forces non-native dialogs

class BaseFileChooser:

    _preview_size: tuple[int, int]

    def add_filter(self, filter: Gtk.FileFilter) -> None:  # noqa: A002
        pass

    def set_filter(self, filter: Gtk.FileFilter) -> None:  # noqa: A002
        pass

    def _on_response(self,
                     dialog: Gtk.FileChooser | Gtk.FileChooserNative,
                     response: Gtk.ResponseType,
                     accept_cb: AcceptCallbackT,
                     cancel_cb: Callable[..., Any] | None
                     ) -> None:
        if response == Gtk.ResponseType.ACCEPT:
            accept_cb(dialog.get_filenames())

        if response in (Gtk.ResponseType.CANCEL,
                        Gtk.ResponseType.DELETE_EVENT):
            if cancel_cb is not None:
                cancel_cb()

    def _add_filters(self, filters: list[Filter]) -> None:
        for filterinfo in filters:
            filter_ = Gtk.FileFilter()
            filter_.set_name(filterinfo.name)
            if isinstance(filterinfo.pattern, list):
                for mime_type in filterinfo.pattern:
                    filter_.add_mime_type(mime_type)
            else:
                filter_.add_pattern(filterinfo.pattern)
            self.add_filter(filter_)
            if filterinfo.default:
                self.set_filter(filter_)

    def _update_preview(self, filechooser: Gtk.FileChooser) -> None:
        path_to_file = filechooser.get_preview_filename()
        preview = cast(Gtk.Image, filechooser.get_preview_widget())
        if path_to_file is None or os.path.isdir(path_to_file):
            # nothing to preview
            preview.clear()
            return
        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                path_to_file, *self._preview_size)
        except GLib.Error:
            preview.clear()
            return
        preview.set_from_pixbuf(pixbuf)


class BaseFileOpenDialog:

    _title = _('Choose File to Send…')
    _filters = [Filter(_('All files'), '*', True)]


class BaseAvatarChooserDialog:

    _title = _('Choose Avatar…')
    _preview_size = (100, 100)

    if _require_native():
        _filters = [Filter(_('PNG files'), '*.png', True),
                    Filter(_('JPEG files'), '*.jp*g', False),
                    Filter(_('SVG files'), '*.svg', False)]
    else:
        _filters = [Filter(_('Images'), ['image/*'], True)]


class NativeFileChooserDialog(Gtk.FileChooserNative, BaseFileChooser):

    _title = ''
    _filters: list[Filter] = []
    _action = Gtk.FileChooserAction.OPEN

    def __init__(self,
                 accept_cb: AcceptCallbackT,
                 cancel_cb: Callable[..., Any] | None = None,
                 transient_for: Gtk.Window | None = None,
                 path: str | None = None,
                 file_name: str | None = None,
                 select_multiple: bool = False,
                 modal: bool = False
                 ) -> None:

        if transient_for is None:
            transient_for = app.app.get_active_window()

        Gtk.FileChooserNative.__init__(self,
                                       title=self._title,
                                       action=self._action,
                                       transient_for=transient_for)

        self.set_current_folder(path or str(Path.home()))
        if file_name is not None:
            self.set_current_name(file_name)
        self.set_select_multiple(select_multiple)
        self.set_do_overwrite_confirmation(True)
        self.set_modal(modal)
        self._add_filters(self._filters)

        self.connect('response', self._on_response, accept_cb, cancel_cb)
        self.show()


class ArchiveChooserDialog(NativeFileChooserDialog):

    _title = _('Choose Archive')
    _filters = [Filter(_('All files'), '*', False),
                Filter(_('ZIP files'), '*.zip', True)]


class FileSaveDialog(NativeFileChooserDialog):

    _title = _('Save File as…')
    _filters = [Filter(_('All files'), '*', True)]
    _action = Gtk.FileChooserAction.SAVE


class NativeFileOpenDialog(BaseFileOpenDialog, NativeFileChooserDialog):
    pass


class NativeAvatarChooserDialog(BaseAvatarChooserDialog,
                                NativeFileChooserDialog):
    pass


class GtkFileChooserDialog(Gtk.FileChooserDialog, BaseFileChooser):

    _title = ''
    _filters: list[Filter] = []
    _action = Gtk.FileChooserAction.OPEN
    _preview_size = (200, 200)

    def __init__(self,
                 accept_cb: AcceptCallbackT,
                 cancel_cb: Callable[..., Any] | None = None,
                 transient_for: Gtk.Window | None = None,
                 path: str | None = None,
                 file_name: str | None = None,
                 select_multiple: bool = False,
                 preview: bool = True,
                 modal: bool = False
                 ) -> None:

        if transient_for is None:
            transient_for = app.app.get_active_window()

        Gtk.FileChooserDialog.__init__(
            self,
            title=self._title,
            action=self._action,
            transient_for=transient_for)

        self.add_button(_('_Cancel'), Gtk.ResponseType.CANCEL)
        open_button = self.add_button(_('_Open'), Gtk.ResponseType.ACCEPT)
        open_button.get_style_context().add_class('suggested-action')

        self.set_current_folder(path or str(Path.home()))
        if file_name is not None:
            self.set_current_name(file_name)
        self.set_select_multiple(select_multiple)
        self.set_do_overwrite_confirmation(True)
        self.set_modal(modal)
        self._add_filters(self._filters)

        if preview:
            self.set_use_preview_label(False)
            self.set_preview_widget(Gtk.Image())
            self.connect('selection-changed', self._update_preview)

        self.connect('response', self._on_response, accept_cb, cancel_cb)
        self.show()

    def _on_response(self, *args: Any) -> None:
        super()._on_response(*args)
        self.destroy()


class GtkFileOpenDialog(BaseFileOpenDialog, GtkFileChooserDialog):
    pass


class GtkAvatarChooserDialog(BaseAvatarChooserDialog, GtkFileChooserDialog):
    pass


if _require_native():
    FileChooserDialog = NativeFileOpenDialog
    AvatarChooserDialog = NativeAvatarChooserDialog
else:
    FileChooserDialog = GtkFileOpenDialog
    AvatarChooserDialog = GtkAvatarChooserDialog
