# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from gi.repository import Adw
from gi.repository import Gtk

from gajim.gtk.sidebar_switcher import SideBarMenuItem
from gajim.gtk.sidebar_switcher import SideBarSwitcher
from gajim.gtk.widgets import GajimAppWindow

from . import util

PAGES = ["A", "B", "B1", "B2", "B3", "C", "D", "E", "E1", "E2", "E3", "F"]


class TestSideBarSwitcher(GajimAppWindow):
    def __init__(self):
        GajimAppWindow.__init__(
            self,
            name="",
            title=__class__.__name__,
            default_width=600,
            default_height=600,
            add_window_padding=False,
            header_bar=False,
        )

        stack = Gtk.Stack()
        for p in PAGES:
            stack.add_named(Gtk.Label(label=p), p)

        side_bar_switcher = SideBarSwitcher()
        side_bar_switcher.set_with_menu(
            stack,
            [
                SideBarMenuItem("A", "A", icon_name="lucide-laptop-symbolic"),
                SideBarMenuItem(
                    "B",
                    "B",
                    icon_name="user-available-symbolic",
                    children=[
                        SideBarMenuItem("B1", "B1", icon_name="lucide-laptop-symbolic"),
                        SideBarMenuItem("B2", "B2", icon_name="lucide-laptop-symbolic"),
                        SideBarMenuItem("B3", "B3", icon_name="lucide-laptop-symbolic"),
                    ],
                ),
                SideBarMenuItem(
                    "C",
                    "C",
                    group="Group 1",
                    icon_name="lucide-message-circle-symbolic",
                ),
                SideBarMenuItem(
                    "D",
                    "D",
                    group="Group 1",
                    icon_name="lucide-mic-symbolic",
                ),
                SideBarMenuItem(
                    "E",
                    "E",
                    group="Group 2",
                    icon_name="lucide-megaphone-symbolic",
                    children=[
                        SideBarMenuItem("E1", "E1", icon_name="lucide-laptop-symbolic"),
                        SideBarMenuItem("E2", "E2", icon_name="lucide-laptop-symbolic"),
                        SideBarMenuItem("E3", "E3", icon_name="lucide-laptop-symbolic"),
                    ],
                ),
                SideBarMenuItem("F", "F", icon_name="lucide-palette-symbolic"),
            ],
        )

        toolbar = Adw.ToolbarView(content=side_bar_switcher)
        toolbar.add_top_bar(Adw.HeaderBar())

        sidebar_page = Adw.NavigationPage(
            title="Preferences", tag="sidebar", child=toolbar
        )

        toolbar = Adw.ToolbarView(content=stack)
        toolbar.add_top_bar(Adw.HeaderBar())

        content_page = Adw.NavigationPage(title=" ", tag="content", child=toolbar)

        nav = Adw.NavigationSplitView(sidebar=sidebar_page, content=content_page)

        self.set_child(nav)


util.init_settings()

window = TestSideBarSwitcher()
window.show()

util.run_app()
