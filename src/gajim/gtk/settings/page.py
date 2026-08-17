# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only

from typing import Any
from typing import cast

from gi.repository import Adw
from gi.repository import Gtk

from gajim.common import app

from gajim.gtk.settings.group import GajimPreferencesGroup


class GajimPreferencePage(Adw.NavigationPage):
    key: str = ""
    icon_name: str = ""
    label: str = ""

    def __init__(
        self,
        title: str,
        groups: list[Any],
        tag_prefix: str = "",
    ) -> None:
        Adw.NavigationPage.__init__(self, tag=f"{tag_prefix}{self.key}", title=title)

        self._pref_page = Adw.PreferencesPage()
        toolbar = Adw.ToolbarView(content=self._pref_page)
        toolbar.add_top_bar(Adw.HeaderBar())
        self.set_child(toolbar)

        self._groups: list[GajimPreferencesGroup] = []

        for group in groups:
            if not isinstance(group, GajimPreferencesGroup):
                group = group()
            self._groups.append(group)
            self._pref_page.add(group)

    def do_unroot(self) -> None:
        Adw.NavigationPage.do_unroot(self)
        app.check_finalize(self)

    def add(self, group: GajimPreferencesGroup | Adw.PreferencesGroup) -> None:
        if isinstance(group, GajimPreferencesGroup):
            self._groups.append(group)
        self._pref_page.add(group)

    def get_group(self, key: str) -> GajimPreferencesGroup | None:
        for group in self._groups:
            if group.key == key:
                return group

    def set_content(self, widget: Gtk.Widget) -> None:
        toolbar = cast(Adw.ToolbarView, self.get_child())
        toolbar.set_content(widget)
