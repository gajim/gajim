# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Literal

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common.i18n import _


class MessageSelection(Gtk.Grid):
    __gsignals__ = {
        "copy": (GObject.SignalFlags.RUN_LAST, None, ()),
        "delete": (GObject.SignalFlags.RUN_LAST, None, ()),
        "cancel": (GObject.SignalFlags.RUN_LAST, None, ()),
    }

    def __init__(self) -> None:
        Gtk.Grid.__init__(
            self,
            row_spacing=18,
            column_spacing=6,
            visible=False,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.END,
        )

        self.add_css_class("toolbar")
        self.add_css_class("osd")

        label = Gtk.Label(
            label=_("Click messages to select them\n(Ctrl + Double Click to deselect)")
        )
        self.attach(label, 0, 0, 2, 1)

        cancel_button = Gtk.Button(label=_("Cancel"))
        cancel_button.connect("clicked", self._emit, "cancel")
        self.attach(cancel_button, 0, 1, 1, 1)

        self._copy_button = Gtk.Button(label=_("Copy Text"), visible=False)
        self._copy_button.add_css_class("suggested-action")
        self._copy_button.connect("clicked", self._emit, "copy")
        self.attach(self._copy_button, 1, 1, 1, 1)

        self._delete_button = Gtk.Button(label=_("Delete messages…"), visible=False)
        self._delete_button.add_css_class("destructive-action")
        self._delete_button.connect("clicked", self._emit, "delete")
        self.attach(self._delete_button, 1, 1, 1, 1)

    def set_mode(self, mode: Literal["delete", "copy"]) -> None:
        self._copy_button.set_visible(mode == "copy")
        self._delete_button.set_visible(mode == "delete")

    def _emit(self, _button: Gtk.Button, signal: str) -> None:
        self.emit(signal)
