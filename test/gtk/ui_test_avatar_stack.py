# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

import datetime as dt
from unittest.mock import MagicMock

from gi.repository import Gdk
from gi.repository import Gtk

from gajim.common import app
from gajim.common.const import AvatarSize

from gajim.gtk.avatar import generate_default_avatar
from gajim.gtk.conversation.avatar_stack import AvatarStack
from gajim.gtk.conversation.avatar_stack import AvatarStackData
from gajim.gtk.util.misc import convert_surface_to_texture
from gajim.gtk.widgets import GajimAppWindow

from . import util

ACCOUNT = "account"


class TestAvatarStack(GajimAppWindow):
    def __init__(self) -> None:
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=800,
            default_height=800,
        )

        app.app = MagicMock()
        app.app.avatar_storage.get_avatar_by_sha.side_effect = self._get_avatar_by_sha

        box = Gtk.Box(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER, hexpand=True)
        self.set_child(box)

        avatar_stack = AvatarStack()
        box.append(avatar_stack)

        data: list[AvatarStackData] = []
        for i in range(10):
            data.append(
                AvatarStackData(
                    nickname=f"Test {i + 1}",
                    timestamp=dt.datetime.now(tz=dt.UTC),
                    avatar_sha="test",
                )
            )
        avatar_stack.set_data(data)

    def _get_avatar_by_sha(self, sha: str, size: int, scale: int) -> Gdk.Texture | None:
        return convert_surface_to_texture(
            generate_default_avatar(
                "T", (0.2, 0.1, 0.7), AvatarSize.SMALL, self.get_scale_factor()
            )
        )


util.init_settings()

window = TestAvatarStack()
window.show()

util.run_app()
