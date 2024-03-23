# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.events import DBMigrationError
from gajim.common.events import DBMigrationProgress
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder

log = logging.getLogger('gajim.gtk.db_migration')


class DBMigration(Gtk.ApplicationWindow):
    def __init__(
        self,
    ) -> None:
        Gtk.ApplicationWindow.__init__(self)
        self.set_application(app.app)
        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_show_menubar(False)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_resizable(True)
        self.set_name('DBMigration')
        self.set_title(_('Database Migration'))

        self.set_resizable(False)
        self.set_modal(True)
        self.set_deletable(False)

        self._ui = get_builder('db_migration.ui')
        self.add(self._ui.stack)
        self._ui.connect_signals(self)

        self._ui.status_label.set_text(_('Creating backup…'))

        self.connect('destroy', self._on_destroy)

        self.show_all()

        self._ui.status_label.set_text(_('Migrating chat history database…'))

        self._ui.stack.set_visible_child_name('success-page')

        app.ged.register_event_handler('db-migration-progress', 0, self._on_progress)
        app.ged.register_event_handler('db-migration-error', 0, self._on_error)

    def _on_progress(self, _event: DBMigrationProgress) -> None:
        while Gtk.events_pending():
            Gtk.main_iteration()

    def _on_error(self, event: DBMigrationError) -> None:
        self._ui.error_label.set_text(
            _('Database migration failed: %s') % event.exception
        )
        self._show_error_page()

    def _show_error_page(self) -> None:
        self._ui.stack.set_visible_child_name('error-page')

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        self.destroy()

    def _on_destroy(self, _widget: DBMigration) -> None:
        app.check_finalize(self)
