import time

from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import CSSPriority
from gajim.common.events import DBMigrationError
from gajim.common.events import DBMigrationFinished
from gajim.common.events import DBMigrationProgress

from gajim.gtk.db_migration import DBMigration

from . import util

util.load_style('gajim.css', CSSPriority.APPLICATION)


def _on_progress_clicked(_button: Gtk.Button) -> None:
    count = 100000
    for i in range(100000):
        time.sleep(0.0000001)
        if i % 1000 == 0:
            app.ged.raise_event(DBMigrationProgress(count=count, progress=i))


def _on_finish_clicked(_button: Gtk.Button) -> None:
    app.ged.raise_event(DBMigrationFinished())


def _on_error_clicked(_button: Gtk.Button) -> None:
    try:
        test = 1 / 0  # type: ignore # noqa: F841
    except ZeroDivisionError as e:
        app.ged.raise_event(DBMigrationError(exception=e))


win = DBMigration()
box = win.get_children()[0]
assert isinstance(box, Gtk.Box)
button_box = Gtk.Box(spacing=12, halign=Gtk.Align.CENTER)
box.add(button_box)

progress_button = Gtk.Button(label='Progress')
progress_button.connect('clicked', _on_progress_clicked)
button_box.add(progress_button)

finish_button = Gtk.Button(label='Finish')
finish_button.connect('clicked', _on_finish_clicked)
button_box.add(finish_button)

error_button = Gtk.Button(label='Error')
error_button.connect('clicked', _on_error_clicked)
button_box.add(error_button)

win.connect('destroy', Gtk.main_quit)
win.show_all()

Gtk.main()
