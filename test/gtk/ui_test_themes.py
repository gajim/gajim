# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock

from gi.repository import Gtk
from gi.repository import Pango

from gajim.common import app
from gajim.common.const import StyleAttr

from gajim.gtk.themes import Themes

from . import util

ACCOUNT = "test"

util.init_settings()
app.settings.get_workspace_count = MagicMock(return_value=2)


def _get_value(
    selector: str, attr: str | StyleAttr, pre: bool = False
) -> str | Pango.FontDescription | None:
    if attr == StyleAttr.FONT:
        return Pango.FontDescription.from_string("Cantarell Italic Light 15")
    else:
        return "rgb(100, 10, 50)"


app.css_config = MagicMock()
app.css_config.get_value = _get_value

window = Themes(Gtk.Window())
window._update_preferences_window = MagicMock()  # type: ignore
window.show()

util.run_app()
