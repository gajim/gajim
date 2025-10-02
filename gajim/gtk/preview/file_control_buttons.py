# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from pathlib import Path

from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string


@Gtk.Template.from_string(string=get_ui_string("preview/file_control_buttons.ui"))
class FileControlButtons(Gtk.Box, SignalManager):

    __gtype_name__ = "FileControlButtons"

    _file_name_label: Gtk.Label = Gtk.Template.Child()
    _file_size_label: Gtk.Label = Gtk.Template.Child()
    _open_folder_button: Gtk.Button = Gtk.Template.Child()
    _save_as_button: Gtk.Button = Gtk.Template.Child()

    def __init__(
        self, path: Path | None = None, file_name: str = "", file_size: int = 0
    ) -> None:
        Gtk.Box.__init__(self)
        SignalManager.__init__(self)

        pointer_cursor = Gdk.Cursor.new_from_name("pointer")
        self._save_as_button.set_cursor(pointer_cursor)
        self._open_folder_button.set_cursor(pointer_cursor)

        if path is not None:
            self.set_path(path)

        self.set_file_name(file_name)
        self.set_file_size(file_size)

    def set_path(self, path: Path) -> None:
        self._open_folder_button.set_action_target_value(GLib.Variant("s", str(path)))
        self._save_as_button.set_action_target_value(GLib.Variant("s", str(path)))
        self.set_buttons_visible(True)

    def set_file_name(self, file_name: str):
        self._file_name_label.set_text(file_name)

    def set_file_size(self, file_size: int):
        unit = GLib.FormatSizeFlags.DEFAULT
        if app.settings.get("use_kib_mib"):
            unit = GLib.FormatSizeFlags.IEC_UNITS

        file_size_string = ""
        if file_size > 0:
            file_size_string = GLib.format_size_full(file_size, unit)

        self._file_size_label.set_text(file_size_string)
        self._file_size_label.set_visible(bool(file_size_string))

    def set_buttons_visible(self, visible: bool) -> None:
        self._open_folder_button.set_visible(visible)
        self._save_as_button.set_visible(visible)

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)
        self._disconnect_all()
