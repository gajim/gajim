# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.events import DBError
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.dialogs import ConfirmationDialog
from gajim.gtk.dialogs import DialogButton
from gajim.gtk.widgets import GajimAppWindow


class DBErrorWindow(GajimAppWindow):
    def __init__(self, event: DBError) -> None:
        GajimAppWindow.__init__(
            self,
            default_width=500,
            name="DBError",
            title=_("Database Error"),
            transient_for=app.window,
            modal=True,
        )

        self.window.set_deletable(False)

        self._ui = get_builder("db_error.ui")
        self.set_child(self._ui.grid)

        self._database_name = event.database_name

        self._ui.database_name.set_text(self._database_name)
        self._ui.database_error.set_text(event.error)

        if self._database_name == "cache":
            self._ui.reset_database_button.set_visible(True)

        self._connect(
            self._ui.reset_database_button, "clicked", self._on_reset_database_clicked
        )

        controller = self.get_default_controller()
        self._connect(controller, "key-pressed", self._on_key_pressed)

    def _on_key_pressed(
        self,
        _event_controller_key: Gtk.EventControllerKey,
        _keyval: int,
        _keycode: int,
        _state: Gdk.ModifierType,
    ) -> bool:
        # Prevent default controller from closing window on Esc
        return Gdk.EVENT_STOP

    def _on_reset_database_clicked(self, _button: Gtk.Button) -> None:
        def _reset() -> None:
            if self._database_name == "cache":
                app.storage.cache.reset_storage()

            app.app.activate_action("quit")

        ConfirmationDialog(
            _("Reset Database?"),
            _(
                "All data in this database will be lost.\n"
                'Do you want to reset the "%s" database?'
            )
            % self._database_name,
            [
                DialogButton.make("Cancel"),
                DialogButton.make("Remove", text=_("Reset"), callback=_reset),
            ],
            transient_for=self.window,
        )

    def _cleanup(self) -> None:
        pass
