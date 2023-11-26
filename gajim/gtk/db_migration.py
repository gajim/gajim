# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from typing import Any

import logging
import shutil
import time
from collections.abc import Callable
from pathlib import Path
from sqlite3 import Connection

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.helpers import get_random_string
from gajim.common.i18n import _

from gajim.gtk.builder import get_builder

log = logging.getLogger('gajim.gtk.db_migration')


class DBMigration(Gtk.ApplicationWindow):
    def __init__(
        self,
        migration_routine: Callable[..., Any],
        db_connection: Connection,
        db_path: Path,
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

        random_string = get_random_string(6)
        db_backup_path = db_path.parent / f'{db_path.name}.{random_string}.old'
        try:
            shutil.copy(db_path, db_backup_path)
        except PermissionError as e:
            self._ui.error_label.set_text(
                _('Could not create backup file: %s') % e
            )
            self._ui.stack.set_visible_child_name('error-page')
            self._show_error_page()
            return

        self._ui.status_label.set_text(_('Migrating chat history database…'))
        migration_routine(db_connection).run()

        self._ui.stack.set_visible_child_name('success-page')
        time.sleep(5)
        self.destroy()

    def _show_error_page(self) -> None:
        self._ui.stack.set_visible_child_name('error-page')

    def _on_close_button_clicked(self, _button: Gtk.Button) -> None:
        self.destroy()

    def _on_destroy(self, _widget: DBMigration) -> None:
        app.check_finalize(self)
