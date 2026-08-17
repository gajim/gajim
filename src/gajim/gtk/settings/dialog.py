# SPDX-FileCopyrightText: Contributors to Gajim <https://gajim.org/>
#
# SPDX-License-Identifier: GPL-3.0-only


from gi.repository import Adw
from gi.repository import Gtk

from gajim.gtk.const import Setting
from gajim.gtk.settings.group import GajimPreferencesGroup
from gajim.gtk.settings.page import GajimPreferencePage
from gajim.gtk.window import GajimAppWindow


class SettingsDialog(GajimAppWindow):
    def __init__(
        self,
        parent: Gtk.Window,
        title: str,
        flags: Gtk.DialogFlags,
        settings: list[Setting],
        account: str,
    ) -> None:
        GajimAppWindow.__init__(
            self,
            name="SettingsDialog",
            title=title,
            default_width=250,
            transient_for=parent,
        )

        self.account = account
        if flags == Gtk.DialogFlags.MODAL:
            self.set_modal(True)

        elif flags == Gtk.DialogFlags.DESTROY_WITH_PARENT:
            self.set_destroy_with_parent(True)

        self._nav = Adw.NavigationView()
        self._group = GajimPreferencesGroup("main")
        page = GajimPreferencePage(title, groups=[self._group])
        self._nav.add(page)

        for setting in settings:
            self._group.add_setting(setting)

        self.set_child(self._nav)
        self.show()

    def _cleanup(self) -> None:
        del self._group

    def get_setting(self, name: str):
        return self._group.get_setting(name)
