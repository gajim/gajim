# Copyright (C) 2018 Philipp Hörist <philipp AT hoerist.com>
#
# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import annotations

from typing import cast
from typing import Literal
from typing import NamedTuple

import logging
from collections.abc import Callable
from pathlib import Path

from gi.repository import Gio
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.util.classes import SignalManager

AcceptCallbackT = Callable[[list[str]], None]


log = logging.getLogger("gajim.gtk.filechoosers")


class Filter(NamedTuple):
    name: str
    patterns: list[str]
    default: bool = False


class FileChooserButton(Gtk.Button, SignalManager):
    _cls_filters: list[Filter] = []
    __gsignals__ = {
        "path-picked": (GObject.SignalFlags.RUN_LAST, None, (object,)),
    }

    def __init__(
        self,
        path: Path | None = None,
        mode: Literal["file-open", "folder-open", "save"] = "file-open",
        multiple: bool = False,
        filters: list[Filter] | None = None,
        label: str = "",
        tooltip: str = "",
        icon_name: str | None = None,
        initial_path: Path | None = None,
    ) -> None:
        Gtk.Button.__init__(self)
        SignalManager.__init__(self)
        self._path = path
        self._initial_path = initial_path
        self._mode = mode
        self._multiple = multiple
        self._filters = filters or self._cls_filters
        self._label_text = label
        self._has_tooltip = bool(tooltip)

        self.set_tooltip_text(tooltip)

        icon = Gtk.Image.new_from_icon_name(icon_name or "lucide-folder-symbolic")

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

        self._connect(self, "clicked", self._on_clicked)

    def get_path(self) -> Path | None:
        return self._path

    def set_path(self, path: Path | None) -> None:
        if path is None:
            self.reset()
            return

        self._path = path
        if not self._has_tooltip and self._mode != "save":
            self._label.set_tooltip_text(str(path))

        match self._mode:
            case "file-open":
                self._label.set_text(_("File: %s") % path.name)
            case "folder-open":
                self._label.set_text(_("Folder: %s") % path.as_posix())
            case _:
                pass

    def set_inital_path(self, path: Path | None) -> None:
        self._initial_path = path

    def reset(self) -> None:
        self._path = None
        self._label.set_text(self._label_text or "")
        self._label.set_tooltip_text(None)

    def _on_clicked(self, _button: FileChooserButton) -> None:
        dialog = Gtk.FileDialog()

        file_filter_model = Gio.ListStore()
        for f in self._filters:
            file_filter = Gtk.FileFilter(name=f.name, patterns=f.patterns)
            file_filter_model.append(file_filter)
            if f.default:
                dialog.set_default_filter(file_filter)

        if self._path is None:
            initial_path = self._initial_path
        else:
            initial_path = self._path

        if initial_path is not None:
            file = Gio.File.new_for_path(str(initial_path))
            if initial_path.is_dir():
                dialog.set_initial_folder(file)
            else:
                dialog.set_initial_file(file)

        if self._filters:
            dialog.set_filters(file_filter_model)

        parent = cast(Gtk.Window, self.get_root())

        match (self._mode, self._multiple):
            case ("file-open", True):
                dialog.open_multiple(parent, None, self._on_file_picked)
            case ("file-open", False):
                dialog.open(parent, None, self._on_file_picked)
            case ("folder-open", True):
                dialog.select_multiple_folders(parent, None, self._on_file_picked)
            case ("folder-open", False):
                dialog.select_folder(parent, None, self._on_file_picked)
            case ("save", False):
                dialog.save(parent, None, self._on_file_picked)
            case _:
                raise ValueError("Unexpected file chooser configuration")

    def _set_error(self) -> None:
        log.warning("Could not get picked file/folder")
        self._label.set_text(_("Error"))
        if not self._has_tooltip:
            self._label.set_tooltip_text(_("Could not select file or folder"))
        self.emit("path-picked", [])

    def _on_file_picked(
        self, file_dialog: Gtk.FileDialog, result: Gio.AsyncResult
    ) -> None:
        try:
            match (self._mode, self._multiple):
                case ("file-open", True):
                    g_files = cast(
                        list[Gio.File], list(file_dialog.open_multiple_finish(result))
                    )
                case ("file-open", False):
                    g_files = [file_dialog.open_finish(result)]
                case ("folder-open", True):
                    g_files = cast(
                        list[Gio.File],
                        list(file_dialog.select_multiple_folders_finish(result)),
                    )
                case ("folder-open", False):
                    g_files = [file_dialog.select_folder_finish(result)]
                case ("save", False):
                    g_files = [file_dialog.save_finish(result)]
                case _:
                    raise ValueError("Unexpected file chooser configuration")

        except GLib.Error as e:
            if e.code == 2:
                # User dismissed dialog, do nothing
                return

            log.exception(e)
            self._set_error()
            return

        paths: list[Path] = []
        for f in g_files:
            path = f.get_path()
            if path is not None:
                paths.append(Path(path))

        if len(paths) == 1:
            self.set_path(paths[0])

        self.emit("path-picked", paths)

    def do_unroot(self) -> None:
        Gtk.Button.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self)


class AvatarFileChooserButton(FileChooserButton):
    _cls_filters = [
        Filter(name=_("PNG files"), patterns=["*.png"], default=True),
        Filter(name=_("JPEG files"), patterns=["*.jp*g"]),
        Filter(name=_("SVG files"), patterns=["*.svg"]),
    ]
