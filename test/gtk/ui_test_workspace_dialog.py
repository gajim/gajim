# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock

from gajim.common import app

from gajim.gtk.workspace_dialog import WorkspaceDialog

from . import util

ACCOUNT = "test"

util.init_settings()
app.settings.get_workspace_count = MagicMock(return_value=2)

window = WorkspaceDialog()
window.show()

util.run_app()
