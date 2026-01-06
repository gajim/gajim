# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from typing import cast

import time

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.events import DBMigrationError
from gajim.common.events import DBMigrationFinished
from gajim.common.events import DBMigrationProgress
from gajim.common.events import DBMigrationStart

from gajim.gtk.db_migration import DBMigration

from . import util


class DBMigrationTest:
    def __init__(self) -> None:
        self._progressing = False

        window = DBMigration()
        box = cast(Gtk.Box, window.get_content())
        box.set_orientation(Gtk.Orientation.VERTICAL)

        button_box = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
        box.append(button_box)

        progress_button = Gtk.Button(label="Progress")
        progress_button.connect("clicked", self._on_progress_clicked)
        button_box.append(progress_button)

        finish_button = Gtk.Button(label="Finish")
        finish_button.connect("clicked", self._on_finish_clicked)
        button_box.append(finish_button)

        error_button = Gtk.Button(label="Error")
        error_button.connect("clicked", self._on_error_clicked)
        button_box.append(error_button)

        window.show()

        GLib.timeout_add_seconds(3, self._add_window)

        self._progress()

    def _add_window(self) -> None:
        # Simulate main window becoming available
        app.window = Gtk.Window(width_request=800, height_request=800)
        app.window.show()

    def _progress(self) -> None:
        app.ged.raise_event(DBMigrationStart(version=1))
        self._progressing = True

        count = 100000
        for i in range(100000):
            if not self._progressing:
                break

            time.sleep(0.0000001)
            if i % 1000 == 0:
                app.ged.raise_event(DBMigrationProgress(count=count, progress=i))

    def _on_progress_clicked(self, _button: Gtk.Button) -> None:
        self._progress()

    def _on_finish_clicked(self, _button: Gtk.Button) -> None:
        self._progressing = False

        app.ged.raise_event(DBMigrationFinished())

    def _on_error_clicked(self, _button: Gtk.Button) -> None:
        self._progressing = False

        try:
            test = 1 / 0  # type: ignore # noqa: F841
        except ZeroDivisionError as e:
            app.ged.raise_event(DBMigrationError(exception=e))


util.init_settings()

DBMigrationTest()

util.run_app()
