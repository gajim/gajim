# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from unittest.mock import MagicMock

from gajim.common import app
from tests.gtk import util

from gajim.gtk.workspace_dialog import WorkspaceDialog

ACCOUNT = "test"

util.init_settings()
app.settings.get_workspace_count = MagicMock(return_value=2)

window = WorkspaceDialog()
window.show()

util.run_app()
