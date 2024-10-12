# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import Any, Literal, NamedTuple, cast

import logging
import sys
from collections.abc import Callable
from pathlib import Path

from gi.repository import GLib, GObject, Gio, Pango
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.util import SignalManager

AcceptCallbackT = Callable[[list[str]], None]


log = logging.getLogger('gajim.gtk.filechooser')


class Filter(NamedTuple):
    name: str
    patterns: list[str]
    default: bool = False


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
            paths: list[str] = []
            for g_file in cast(list[Gio.File], dialog.get_files()):
                path = g_file.get_path()
                assert path is not None
                paths.append(path)
            accept_cb(paths)

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

        self.set_current_folder(Gio.File.new_for_path(path or str(Path.home())))
        if file_name is not None:
            self.set_current_name(file_name)
        self.set_select_multiple(select_multiple)
        self.set_modal(modal)
        self._add_filters(self._filters)

        self.connect('response', self._on_response, accept_cb, cancel_cb)
        self.show()


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

        self.set_current_folder(Gio.File.new_for_path(path or str(Path.home())))
        if file_name is not None:
            self.set_current_name(file_name)
        self.set_select_multiple(select_multiple)
        self.set_modal(modal)
        self._add_filters(self._filters)

        self.connect('response', self._on_response, accept_cb, cancel_cb)
        self.show()

    def _on_response(self,
                     dialog: Gtk.FileChooser | Gtk.FileChooserNative,
                     response: Gtk.ResponseType,
                     accept_cb: AcceptCallbackT,
                     cancel_cb: Callable[..., Any] | None
                     ) -> None:
        super()._on_response(dialog, response, accept_cb, cancel_cb)
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


class FileChooserButton(Gtk.Button, SignalManager):
    _cls_filters: list[Filter] = []
    __gsignals__ = {
        'path-picked': (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    def __init__(
        self,
        path: Path | None = None,
        mode: Literal['file', 'folder'] = 'file',
        filters: list[Filter] | None = None,
        label: str = '',
        tooltip: str = '',
        icon_name: str | None = None,
    ) -> None:

        Gtk.Button.__init__(self)
        SignalManager.__init__(self)
        self._path = path
        self._mode = mode
        self._filters = filters or self._cls_filters
        self._label_text = label
        self._has_tooltip = bool(tooltip)

        self.set_tooltip_text(tooltip)

        icon = Gtk.Image.new_from_icon_name(
            icon_name or 'system-file-manager-symbolic')

        self._label = Gtk.Label(
            label=label,
            ellipsize=Pango.EllipsizeMode.MIDDLE,
            max_width_chars=18,
            visible=bool(label),
        )

        box = Gtk.Box(spacing=12)
        box.append(icon)
        box.append(self._label)

        if path is not None:
            self.set_path(path)

        self.set_child(box)

        self._connect(self, 'clicked', self._on_clicked)

    def get_path(self) -> Path | None:
        return self._path

    def set_path(self, path: Path | None) -> None:
        if path is None:
            self.reset()
            return

        self._path = path
        if not self._has_tooltip:
            self._label.set_tooltip_text(str(path))

        if self._mode == 'file':
            self._label.set_text(_('File: %s') % path.name)
        else:
            self._label.set_text(_('Folder: %s') % path.as_posix())

    def reset(self) -> None:
        self._path = None
        self._label.set_text(self._label_text or '')
        self._label.set_tooltip_text(None)

    def _on_clicked(self, _button: FileChooserButton) -> None:
        dialog = Gtk.FileDialog()

        file_filter_model = Gio.ListStore()
        for f in self._filters:
            file_filter = Gtk.FileFilter(name=f.name, patterns=f.patterns)
            file_filter_model.append(file_filter)
            if f.default:
                dialog.set_default_filter(file_filter)

        if self._path is not None:
            file = Gio.File.new_for_path(str(self._path))
            if self._mode == 'file':
                dialog.set_initial_file(file)
            else:
                dialog.set_initial_folder(file)

        if self._filters:
            dialog.set_filters(file_filter_model)

        parent = cast(Gtk.Window, self.get_root())

        if self._mode == 'file':
            dialog.open(parent, None, self._on_file_picked)
        else:
            dialog.select_folder(parent, None, self._on_file_picked)

    def _set_error(self) -> None:
        log.warning('Could not get picked file/folder')
        self._label.set_text(_('Error'))
        if not self._has_tooltip:
            self._label.set_tooltip_text(_('Could not select file or folder'))
        self.emit('path-picked', [])

    def _on_file_picked(
        self, file_dialog: Gtk.FileDialog, result: Gio.AsyncResult
    ) -> None:
        self._path = None

        try:
            if self._mode == 'file':
                file = file_dialog.open_finish(result)
            else:
                file = file_dialog.select_folder_finish(result)
        except GLib.Error as e:
            if e.code == 2:
                # User dismissed dialog, do nothing
                return

            log.exception(e)
            self._set_error()
            return

        if file is None:
            self._set_error()
            return

        path = file.get_path()
        if path is None:
            self._set_error()
            return

        self.set_path(Path(path))

        self.emit('path-picked', [path])

    def do_unroot(self) -> None:
        Gtk.Button.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self)


class AvatarFileChooserButton(FileChooserButton):
    _cls_filters = [
        Filter(name=_('PNG files'), patterns=['*.png'], default=True),
        Filter(name=_('JPEG files'), patterns=['*.jp*g']),
        Filter(name=_('SVG files'), patterns=['*.svg']),
    ]
