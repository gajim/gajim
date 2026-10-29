# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import sys

from gi.repository import Gtk

from gajim.common import app
from gajim.common.helpers import idle_add_once
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

        if sys.platform == "darwin":
            # macOS has no system tray, the hidden app is restored from the Dock
            hide_label = _("_Hide (Dock Icon)")
            restore_hint = _("Click Gajim’s icon in the Dock to restore the window.")
        else:
            hide_label = _("_Hide (Tray Icon)")
            restore_hint = _("Use Gajim’s system tray icon to restore the window.")

        self._ui.hide_button.set_label(hide_label)
        self._ui.description_label.set_text(
            _(
                "Sure you want to quit Gajim?\n"
                "You won’t be able to send and receive messages if you do.\n\n"
                "Alternatively, you can either minimize Gajim’s window, or hide "
                "it completely. {restore_hint}"
            ).format(restore_hint=restore_hint)
        )

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
            # Call with idle because closing the Quit Dialog
            # writes window size to settings and this can only happen
            # when the CoreApplication shutdown was not called first
            idle_add_once(app.app.start_shutdown)

        self.close()

    def _cleanup(self):
        pass
