# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import cast

from enum import IntEnum
from pathlib import Path

from gi.repository import Gtk

from gajim.common import app
from gajim.common.helpers import check_soundfile_path
from gajim.common.helpers import play_sound
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.filechoosers import FileChooserButton
from gajim.gtk.filechoosers import Filter
from gajim.gtk.widgets import GajimAppWindow

SOUNDS = {
    "attention_received": _("Attention Message Received"),
    "first_message_received": _("Message Received"),
    "contact_connected": _("Contact Connected"),
    "contact_disconnected": _("Contact Disconnected"),
    "message_sent": _("Message Sent"),
    "muc_message_highlight": _("Group Chat Message Highlight"),
    "muc_message_received": _("Group Chat Message Received"),
    "incoming-call-sound": _("Call Incoming"),
    "outgoing-call-sound": _("Call Outgoing"),
}


class Column(IntEnum):
    ENABLED = 0
    NAME = 1
    PATH = 2
    CONFIG = 3


class ManageSounds(GajimAppWindow):
    def __init__(self, transient_for: Gtk.Window | None = None) -> None:
        GajimAppWindow.__init__(
            self,
            name="ManageSounds",
            title=_("Manage Sounds"),
            default_width=400,
            default_height=400,
            transient_for=transient_for,
            modal=True,
        )

        self._ui = get_builder("manage_sounds.ui")
        self.set_child(self._ui.manage_sounds)

        liststore = Gtk.ListStore(bool, str, str, str)
        self._ui.sounds_treeview.set_model(liststore)

        last_path = app.settings.get("last_sounds_dir")
        last_path = Path(last_path) if last_path else None

        self._file_chooser_button = FileChooserButton(
            filters=[
                Filter(name=_("All files"), patterns=["*"]),
                Filter(name=_("WAV Sounds"), patterns=["*.wav"], default=True),
            ],
            label=_("Choose Sound"),
            initial_path=last_path,
        )
        self._file_chooser_button.set_hexpand(True)
        self._ui.sound_buttons_box.prepend(self._file_chooser_button)

        self._connect(liststore, "row-changed", self._on_row_changed)
        self._connect(
            self._ui.sounds_treeview, "cursor-changed", self._on_cursor_changed
        )
        self._connect(self._ui.toggle_cell_renderer, "toggled", self._on_toggle)
        self._connect(self._ui.clear_sound_button, "clicked", self._on_clear)
        self._connect(self._ui.play_sound_button, "clicked", self._on_play)
        self._connect(self._file_chooser_button, "path-picked", self._on_path_picked)

        self._fill_sound_treeview()

    @staticmethod
    def _on_row_changed(
        model: Gtk.TreeModel, path: Gtk.TreePath, iter_: Gtk.TreeIter
    ) -> None:
        sound_event = model[iter_][Column.CONFIG]
        app.settings.set_soundevent_setting(
            sound_event, "enabled", model[path][Column.ENABLED]
        )
        app.settings.set_soundevent_setting(
            sound_event, "path", model[iter_][Column.PATH]
        )

    def _on_toggle(self, _cell: Gtk.CellRendererToggle, path: Gtk.TreePath) -> None:
        if self._file_chooser_button.get_path() is None:
            return

        model = self._ui.sounds_treeview.get_model()
        assert model is not None

        model[path][Column.ENABLED] = not model[path][Column.ENABLED]

    def _fill_sound_treeview(self) -> None:
        model = cast(Gtk.ListStore, self._ui.sounds_treeview.get_model())
        model.clear()

        for sound_event, sound_name in SOUNDS.items():
            settings = app.settings.get_soundevent_settings(sound_event)
            model.append(
                [settings["enabled"], sound_name, settings["path"], sound_event]
            )

    def _on_cursor_changed(self, treeview: Gtk.TreeView) -> None:
        model, iter_ = treeview.get_selection().get_selected()
        assert iter_ is not None

        path_to_snd_file = check_soundfile_path(model[iter_][Column.PATH])
        if path_to_snd_file is None:
            self._file_chooser_button.reset()
            last_path = app.settings.get("last_sounds_dir")
            if last_path:
                self._file_chooser_button.set_inital_path(Path(last_path))
        else:
            self._file_chooser_button.set_path(path_to_snd_file)

    def _on_path_picked(self, button: FileChooserButton, file_paths: list[str]) -> None:
        if not file_paths:
            return

        path = file_paths[0]

        model, iter_ = self._ui.sounds_treeview.get_selection().get_selected()
        assert iter_ is not None

        app.settings.set("last_sounds_dir", str(Path(path).parent))

        model[iter_][Column.PATH] = str(path)
        model[iter_][Column.ENABLED] = True

    def _on_clear(self, _button: Gtk.Button) -> None:
        self._file_chooser_button.reset()
        model, iter_ = self._ui.sounds_treeview.get_selection().get_selected()
        assert iter_ is not None

        model[iter_][Column.PATH] = ""
        model[iter_][Column.ENABLED] = False

    def _on_play(self, _button: Gtk.Button) -> None:
        model, iter_ = self._ui.sounds_treeview.get_selection().get_selected()
        assert iter_ is not None

        snd_event_config_name = model[iter_][Column.CONFIG]
        play_sound(snd_event_config_name, None, force=True)

    def _cleanup(self) -> None:
        pass
