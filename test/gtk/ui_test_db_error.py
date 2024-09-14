# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gajim.common import app  # type: ignore # noqa: F401
from gajim.common import events

from gajim.gtk.db_error import DBErrorWindow

from . import util

event = events.DBError(database_name="cache", error="Disk error")

window = DBErrorWindow(event)
window.show()

util.run_app()
