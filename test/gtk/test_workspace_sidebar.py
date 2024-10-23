# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from unittest.mock import MagicMock

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.settings import Settings

from gajim.gtk.avatar import make_workspace_avatar
from gajim.gtk.const import DEFAULT_WORKSPACE_COLOR
from gajim.gtk.util import make_rgba
from gajim.gtk.util import rgba_to_float
from gajim.gtk.widgets import GajimAppWindow
from gajim.gtk.workspace_side_bar import WorkspaceSideBar

from . import util


class TestWorkspaceSideBar(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name='',
            title=__class__.__name__,
            default_width=600,
            default_height=800,
        )

        self._box = Gtk.Box(
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            hexpand=True,
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
        )
        self.set_child(self._box)

        chat_page = MagicMock()
        sidebar = WorkspaceSideBar(chat_page)
        self._box.append(sidebar)

        app.app = MagicMock()
        app.app.avatar_storage.get_workspace_texture.side_effect = (
            self._get_workspace_texture
        )

        for workspace_id in app.settings.get_workspaces():
            sidebar.add_workspace(workspace_id)

    def _get_workspace_texture(
        self, workspace_id: str, size: int, scale: int
    ) -> Gdk.Texture | None:
        name = app.settings.get_workspace_setting(workspace_id, 'name')
        rgba = make_rgba(DEFAULT_WORKSPACE_COLOR)
        return make_workspace_avatar(name, rgba_to_float(rgba), size, scale)


app.window = MagicMock()
app.settings = Settings(in_memory=True)
app.settings.init()

for i in range(10):
    app.settings.add_workspace(str(i))


window = TestWorkspaceSideBar()
window.show()

util.run_app()
