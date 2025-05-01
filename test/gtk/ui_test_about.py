# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gajim.gtk.about import AboutDialog

from . import util

dialog = AboutDialog()
dialog.present()

util.run_app()
