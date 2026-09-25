# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from gajim.gtk.about import AboutDialog

from . import util

dialog = AboutDialog()
dialog.present()

util.run_app()
