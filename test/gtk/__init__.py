# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw

from gajim.common import configpaths
from gajim.main import gi_require_versions

gi_require_versions()

configpaths.init()
Adw.init()
