# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.window import GajimAppWindow


class QuitDialog(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="QuitDialog",
            title=_("Quit Gajim"),
            transient_for=app.window,
            modal=True,
            add_window_padding=True,
            header_bar=True,
        )

        self._ui = get_builder("quit_dialog.ui")

        self._connect(self._ui.hide_button, "clicked", self._on_button_clicked)
        self._connect(self._ui.minimize_button, "clicked", self._on_button_clicked)
        self._connect(self._ui.quit_button, "clicked", self._on_button_clicked)

        self.set_child(self._ui.box)

    def _on_button_clicked(self, button: Gtk.Button) -> None:
        action = button.get_name()

        if self._ui.remember_checkbutton.get_active():
            app.settings.set("confirm_on_window_delete", False)
            app.settings.set("action_on_close", action)

        if action == "minimize":
            app.window.minimize()
        elif action == "hide":
            app.window.hide_window()
        elif action == "quit":
            app.app.start_shutdown()

        self.close()

    def _cleanup(self):
        pass
