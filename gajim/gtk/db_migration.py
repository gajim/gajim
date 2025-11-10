# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import traceback
from io import StringIO

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
from gajim.gtk.widgets import GajimAppWindow

log = logging.getLogger("gajim.gtk.db_migration")


class DBMigration(GajimAppWindow, EventHelper):
    def __init__(
        self,
    ) -> None:
        GajimAppWindow.__init__(
            self,
            name="DBMigration",
            title=_("Database Migration"),
            default_width=600,
            default_height=300,
            add_window_padding=False,
            transient_for=app.window,
            modal=True,
        )
        EventHelper.__init__(self)

        self.window.set_deletable(False)
        self.window.set_resizable(False)

        self._ui = get_builder("db_migration.ui")
        self.set_child(self._ui.box)

        self._connect(
            self._ui.error_copy_button, "clicked", self._on_error_copy_clicked
        )
        self._connect(
            self._ui.error_close_button, "clicked", self._on_close_button_clicked
        )
        self._connect(
            self._ui.success_close_button, "clicked", self._on_close_button_clicked
        )

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
        self.window.set_transient_for(app.window)
        return GLib.SOURCE_CONTINUE

    def _cleanup(self) -> None:
        GLib.source_remove(self._timeout_id)
        self.unregister_events()

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
        self.window.get_clipboard().set(error_text)

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        self.close()
