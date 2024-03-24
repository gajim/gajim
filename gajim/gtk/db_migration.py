# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

import logging

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

        self._ui = get_builder('db_migration.ui')
        self.add(self._ui.box)
        self._ui.connect_signals(self)
        self.show_all()

        self.connect('destroy', self._on_destroy)

        self._ui.stack.set_visible_child_name('migration-page')
        self._ui.status_label.set_text(_('Migrating chat history database…'))

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
        self._ui.status_label.set_text(_('Migrated %s messages…') % event.count)

        while Gtk.events_pending():
            Gtk.main_iteration()

    def _on_finished(self, event: DBMigrationFinished) -> None:
        self._ui.stack.set_visible_child_name('success-page')

    def _on_error(self, event: DBMigrationError) -> None:
        self._ui.error_label.set_text(
            _('Database migration failed: %s') % event.exception
        )
        self._ui.stack.set_visible_child_name('error-page')

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        self.destroy()

    def _on_destroy(self, _widget: DBMigration) -> None:
        app.check_finalize(self)
