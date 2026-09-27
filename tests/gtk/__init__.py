# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Adw

from gajim.common import configpaths
from gajim.main import gi_require_versions

gi_require_versions()

configpaths.init()
Adw.init()
