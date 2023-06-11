# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging
import traceback
from io import StringIO

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.events import DBMigrationError
from gajim.common.events import DBMigrationFinished
from gajim.common.events import DBMigrationProgress
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder

log = logging.getLogger('gajim.gtk.db_migration')


class DBMigration(Gtk.ApplicationWindow):
    def __init__(
        self,
    ) -> None:
        Gtk.ApplicationWindow.__init__(
            self,
            application=app.app,
            transient_for=app.window,
            window_position=Gtk.WindowPosition.CENTER,
            show_menubar=False,
            type_hint=Gdk.WindowTypeHint.DIALOG,
            resizable=True,
            width_request=600,
            height_request=300,
            modal=True,
            deletable=False,
            name='DBMigration',
            title=_('Database Migration')
        )

        self.set_keep_above(True)

        self._ui = get_builder('db_migration.ui')
        self.add(self._ui.box)
        self._ui.connect_signals(self)
        self.show_all()

        self.connect('destroy', self._on_destroy)

        app.ged.register_event_handler(
            'db-migration-progress',
            0,
            self._on_progress
        )
        app.ged.register_event_handler('db-migration-error', 0, self._on_error)
        app.ged.register_event_handler(
            'db-migration-finished',
            0,
            self._on_finished
        )

    def _on_progress(self, event: DBMigrationProgress) -> None:
        self._ui.stack.set_visible_child_name('progress-page')
        self._ui.status_label.set_text(f'{event.value} %')

        while Gtk.events_pending():
            Gtk.main_iteration()

    def _on_finished(self, event: DBMigrationFinished) -> None:
        self._ui.stack.set_visible_child_name('success-page')

    def _on_error(self, event: DBMigrationError) -> None:
        trace = StringIO()
        traceback.print_exception(
            type(event.exception),
            event.exception,
            event.exception.__traceback__,
            None,
            trace
        )
        self._ui.error_view.get_buffer().set_text(trace.getvalue())
        self._ui.stack.set_visible_child_name('error-page')

    def _on_error_copy_clicked(self, _button: Gtk.Button) -> None:
        text_buffer = self._ui.error_view.get_buffer()
        start, end = text_buffer.get_bounds()
        error_text = text_buffer.get_text(start, end, True)
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(error_text, -1)

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        self.destroy()

    def _on_destroy(self, _widget: DBMigration) -> None:
        app.check_finalize(self)
