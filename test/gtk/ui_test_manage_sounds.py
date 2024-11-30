# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import tempfile

from gi.repository import Gtk

from gajim.common import app
from gajim.common import configpaths
from gajim.common.settings import Settings

from gajim.gtk.manage_sounds import ManageSounds

from . import util

ACCOUNT = "test"

app.settings = Settings(in_memory=True)
app.settings.init()

configpaths.set_separation(True)
configpaths.set_config_root(tempfile.gettempdir())
configpaths.init()

window = ManageSounds(Gtk.Window())
window.show()

util.run_app()
