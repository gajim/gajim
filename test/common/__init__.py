# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gajim.main import gi_require_versions

gi_require_versions()

from gajim.common import app
from gajim.common.settings import Settings

app.settings = Settings(in_memory=True)
app.settings.init()
