# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

from collections.abc import Callable

from gi.repository import Gtk


class ApplyButtonBox(Gtk.Box):
    def __init__(self,
                 button_text: str,
                 on_clicked: Callable[[Gtk.Button], Any]) -> None:

        Gtk.Box.__init__(self,
                         orientation=Gtk.Orientation.HORIZONTAL,
                         spacing=6)

        self._status_image = Gtk.Image(no_show_all=True)
        self._spinner = Gtk.Spinner(no_show_all=True)
        self._button = Gtk.Button(label=button_text, sensitive=False)
        self._button.get_style_context().add_class('suggested-action')
        self._button.connect('clicked', self._on_clicked)
        self._button.connect('clicked', on_clicked)

        self.add(self._status_image)
        self.add(self._spinner)
        self.add(self._button)

    def _on_clicked(self, button: Gtk.Button) -> None:
        button.set_sensitive(False)
        self._spinner.show()
        self._spinner.start()

    def set_button_state(self, state: bool) -> None:
        if state:
            self._status_image.hide()
        self._button.set_sensitive(state)

    def set_success(self) -> None:
        self._spinner.stop()
        self._spinner.hide()
        self._set_status_image('success')

    def set_error(self, tooltip_text: str):
        self._spinner.stop()
        self._spinner.hide()
        self._set_status_image('error', tooltip_text)
        self._button.set_sensitive(True)

    def _set_status_image(self, state: str, tooltip_text: str = '') -> None:
        icon_name = 'feather-check-symbolic'
        css_class = 'success-color'

        if state == 'error':
            icon_name = 'dialog-warning-symbolic'
            css_class = 'warning-color'

        self._status_image.set_from_icon_name(icon_name, Gtk.IconSize.MENU)
        self._status_image.get_style_context().add_class(css_class)
        self._status_image.set_tooltip_text(tooltip_text)
        self._status_image.show()
