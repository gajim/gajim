# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Gtk

from gajim.gtk.groupchat_nick_chooser import GroupChatNickChooser
from gajim.gtk.widgets import GajimAppWindow

from . import util


class TestGroupChatNickChooser(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=700,
            default_height=700,
        )

        self._main_box = Gtk.Box(
            hexpand=True, halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER
        )

        self._nick_chooser = GroupChatNickChooser()
        self._nick_chooser.set_text("Fancy Nickname")

        self._main_box.append(self._nick_chooser)

        self.set_child(self._main_box)

    def _cleanup(self) -> None:
        pass


util.init_settings()

window = TestGroupChatNickChooser()
window.show()

util.run_app()
