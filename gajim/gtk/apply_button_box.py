# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from collections.abc import Callable

from gi.repository import Adw
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.util.classes import SignalManager


class ApplyButtonBox(Gtk.Box, SignalManager):
    def __init__(
        self, button_text: str, on_clicked: Callable[[Gtk.Button], Any]
    ) -> None:

        Gtk.Box.__init__(self, orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        SignalManager.__init__(self)

        self._status_image = Gtk.Image(visible=False)
        self._spinner = Adw.Spinner(visible=False)
        self._button = Gtk.Button(label=button_text, sensitive=False)
        self._button.add_css_class("suggested-action")
        self._connect(self._button, "clicked", self._on_clicked)
        self._connect(self._button, "clicked", on_clicked)

        self.append(self._button)
        self.append(self._status_image)
        self.append(self._spinner)

    def do_unroot(self) -> None:
        self._disconnect_all()
        Gtk.Box.do_unroot(self)
        app.check_finalize(self)

    def _on_clicked(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        self._spinner.set_visible(True)

    def set_button_state(self, state: bool) -> None:
        if state:
            self._status_image.set_visible(False)
        self._button.set_sensitive(state)

    def set_success(self) -> None:
        self._spinner.set_visible(False)
        self._set_status_image("success")

    def set_error(self, tooltip_text: str):
        self._spinner.set_visible(False)
        self._set_status_image("error", tooltip_text)
        self._button.set_sensitive(True)

    def _set_status_image(self, state: str, tooltip_text: str = "") -> None:
        self._status_image.remove_css_class("success")
        self._status_image.remove_css_class("warning")

        icon_name = "feather-check-symbolic"
        css_class = "success"

        if state == "error":
            icon_name = "dialog-warning-symbolic"
            css_class = "warning"

        self._status_image.set_from_icon_name(icon_name)
        self._status_image.add_css_class(css_class)
        self._status_image.set_tooltip_text(tooltip_text)
        self._status_image.set_visible(True)
