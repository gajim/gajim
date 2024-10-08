# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast
from typing import Any
from typing import Literal

import logging
from pathlib import Path

from gi.repository import Gdk
from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.builder import Builder
from gajim.gtk.util import SignalManager

log = logging.getLogger('gajim.gtk.widgets')


class GajimAppWindow(SignalManager):
    def __init__(
        self,
        *,
        name: str,
        title: str | None = None,
        default_width: int = 0,
        default_height: int = 0,
        transient_for: Gtk.Window | None = None,
        add_window_padding: bool = True,
    ) -> None:

        self.window = Gtk.ApplicationWindow(
            application=app.app,
            resizable=True,
            name=name,
            title=title,
            default_width=default_width,
            default_height=default_height,
            transient_for=transient_for,
        )
        SignalManager.__init__(self)

        log.debug('Load Window: %s', name)

        self._ui = cast(Builder, None)

        self.window.add_css_class('gajim-app-window')

        if add_window_padding:
            self.window.add_css_class('window-padding')

        self.window.set_child(Gtk.Box())

        self.__default_controller = Gtk.EventControllerKey(
            propagation_phase=Gtk.PropagationPhase.CAPTURE
        )
        self.window.add_controller(self.__default_controller)

        self._connect_after(self.__default_controller, 'key-pressed', self.__on_key_pressed)
        self._connect_after(self.window, 'close-request', self.__on_close_request)

    def present(self) -> None:
        self.window.present()

    def show(self) -> None:
        self.window.show()

    def set_child(self, child: Gtk.Widget | None = None) -> None:
        box = cast(Gtk.Box, self.window.get_child())
        current_child = box.get_first_child()
        if current_child is not None:
            box.remove(current_child)

        if child is None:
            return

        box.append(child)

    def get_default_controller(self) -> Gtk.EventController:
        return self.__default_controller

    def __on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        keyval: int,
        keycode: int,
        state: Gdk.ModifierType
    ) -> bool:

        if keyval == Gdk.KEY_Escape:
            self.window.close()
            return Gdk.EVENT_STOP
        return Gdk.EVENT_PROPAGATE

    def __on_close_request(self, _widget: Gtk.ApplicationWindow) -> bool:
        log.debug('Initiate Cleanup: %s', self.window.get_name())
        self._disconnect_all()
        self._cleanup()
        app.check_finalize(self.window)
        app.check_finalize(self)

        del self._ui
        del self.__default_controller
        del self.window

        return Gdk.EVENT_PROPAGATE

    def _cleanup(self) -> None:
        raise NotImplementedError


class FileChooserButton(Gtk.Button):

    __gsignals__ = {
        'path-picked': (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(
        self,
        path: Path | None = None,
        mode: Literal['open'] | Literal['select'] = 'open',
        filters: Gio.ListStore | None = None,
        default_filter: Gtk.FileFilter | None = None,
        default_label: str | None = None,
        transient_for: Gtk.Window | None = None,
    ) -> None:
        Gtk.Button.__init__(self)
        self._path = path
        self._mode = mode
        self._filters = filters or Gio.ListStore()
        self._default_filter = default_filter

        if default_label is None:
            if mode == 'open':
                self._default_label = _('Select File…')
            else:
                self._default_label = _('Select Folder…')
        else:
            self._default_label = default_label

        self._transient_for = transient_for

        self._label = Gtk.Label(
            ellipsize=Pango.EllipsizeMode.MIDDLE, max_width_chars=18
        )

        icon = Gtk.Image.new_from_icon_name('system-file-manager-symbolic')

        box = Gtk.Box(spacing=12)
        box.append(icon)
        box.append(self._label)
        self.set_child(box)

        if path is None:
            self._label.set_text(self._default_label)
        else:
            self._label.set_text(path.name if path.is_file() else path.as_posix())
            self._label.set_tooltip_text(str(self._path))

        self.connect('clicked', self._on_clicked)

    def get_path(self) -> Path | None:
        return self._path

    def set_path(self, path: Path) -> None:
        self._path = path
        self._label.set_tooltip_text(str(self._path))
        if self._mode == 'open':
            self._label.set_text(_('File: %s') % self._path.name)
        else:
            self._label.set_text(_('Folder: %s') % self._path.as_posix())

    def add_filter(self, file_filter: Gtk.FileFilter) -> None:
        self._filters.append(file_filter)

    def set_default_filter(self, default_filter: Gtk.FileFilter) -> None:
        self._default_filter = default_filter

    def reset(self) -> None:
        self._path = None
        self._label.set_text(self._default_label)
        self._label.set_tooltip_text(None)

    def _on_clicked(self, _button: FileChooserButton) -> None:
        dialog = Gtk.FileDialog()

        if self._path is not None:
            file = Gio.File.new_for_path(str(self._path))
            if self._mode == 'open':
                dialog.set_initial_file(file)
            else:
                dialog.set_initial_folder(file)

        if self._filters:
            dialog.set_filters(self._filters)

        if self._default_filter:
            dialog.set_default_filter(self._default_filter)

        if self._mode == 'open':
            dialog.open(self._transient_for, None, self._on_file_picked)
        else:
            dialog.select_folder(self._transient_for, None, self._on_file_picked)

    def _set_error(self) -> None:
        log.warning('Could not get picked file/folder')
        self._label.set_text(_('Error'))
        self._label.set_tooltip_text(_('Could not select file or folder'))
        self.emit('path-picked', '')

    def _on_file_picked(
        self, file_dialog: Gtk.FileDialog, result: Gio.AsyncResult
    ) -> None:
        self._path = None

        try:
            if self._mode == 'open':
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

        self.emit('path-picked', path)
