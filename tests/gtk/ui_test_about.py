# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from tests.gtk import util

from gajim.gtk.about import AboutDialog

dialog = AboutDialog()
dialog.present()

util.run_app()
