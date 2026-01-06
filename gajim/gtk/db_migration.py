# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import traceback
from io import StringIO

from gi.repository import Adw
from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.events import DBMigrationError
from gajim.common.events import DBMigrationFinished
from gajim.common.events import DBMigrationProgress
from gajim.common.events import DBMigrationStart
from gajim.common.ged import EventHelper
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder
from gajim.gtk.util.classes import SignalManager

log = logging.getLogger("gajim.gtk.db_migration")

# Beware that many services are not initialized in Gajim when this dialog runs
# This dialog should not access any Gajim settings, or inherit from classes
# which access Gajim settings.


class DBMigration(Adw.ApplicationWindow, EventHelper, SignalManager):
    def __init__(
        self,
    ) -> None:
        Adw.ApplicationWindow.__init__(
            self,
            name="DBMigration",
            title=_("Database Migration"),
            default_width=600,
            default_height=300,
            modal=True,
        )
        EventHelper.__init__(self)
        SignalManager.__init__(self)

        self.set_deletable(False)
        self.set_resizable(False)

        self._ui = get_builder("db_migration.ui")
        self.set_content(self._ui.box)

        self._connect(
            self._ui.error_copy_button, "clicked", self._on_error_copy_clicked
        )
        self._connect(
            self._ui.error_close_button, "clicked", self._on_close_button_clicked
        )
        self._connect(
            self._ui.success_close_button, "clicked", self._on_close_button_clicked
        )
        self._connect(self, "close-request", self._on_close_request)

        self.register_events(
            [
                ("db-migration-start", 0, self._on_start),
                ("db-migration-progress", 0, self._on_progress),
                ("db-migration-error", 0, self._on_error),
                ("db-migration-finished", 0, self._on_finished),
            ]
        )

        self._timeout_id = GLib.timeout_add(100, self._set_transient)

    def _set_transient(self) -> int:
        # Set transient on every update to make sure transient is set as
        # soon as main window is available
        self.set_transient_for(app.window)
        return GLib.SOURCE_CONTINUE

    def _on_close_request(self, _widget: Adw.ApplicationWindow) -> None:
        log.debug("Initiate Cleanup: %s", self.get_name())
        self._disconnect_all()
        self.unregister_events()
        GLib.source_remove(self._timeout_id)
        app.check_finalize(self)

    def _on_start(self, event: DBMigrationStart) -> None:
        self._ui.stack.set_visible_child_name("progress-page")
        self._ui.status_label.set_text("0 %")
        self._ui.version_label.set_text(_("Migration to version %s") % event.version)

        context = GLib.MainContext.default()
        while context.pending():
            context.iteration(may_block=False)

    def _on_progress(self, event: DBMigrationProgress) -> None:
        self._ui.status_label.set_text(f"{event.value} %")

        context = GLib.MainContext.default()
        while context.pending():
            context.iteration(may_block=False)

    def _on_finished(self, _event: DBMigrationFinished) -> None:
        self._ui.stack.set_visible_child_name("success-page")
        GLib.timeout_add_seconds(2, self.present)

    def _on_error(self, event: DBMigrationError) -> None:
        trace = StringIO()
        traceback.print_exception(
            type(event.exception),
            event.exception,
            event.exception.__traceback__,
            None,
            trace,
        )
        self._ui.error_view.get_buffer().set_text(trace.getvalue())
        self._ui.stack.set_visible_child_name("error-page")

    def _on_error_copy_clicked(self, _button: Gtk.Button) -> None:
        text_buffer = self._ui.error_view.get_buffer()
        start, end = text_buffer.get_bounds()
        error_text = text_buffer.get_text(start, end, True)
        self.get_clipboard().set(error_text)

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        self.close()
