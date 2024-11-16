# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import GObject
from gi.repository import Gtk

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.util import SignalManager


class ChatFilter(Gtk.Box, SignalManager):

    __gsignals__ = {
        "filter-changed": (GObject.SignalFlags.RUN_LAST, None, (str,)),
    }

    def __init__(self, icons: bool = False) -> None:
        Gtk.Box.__init__(self, halign=Gtk.Align.CENTER)
        SignalManager.__init__(self)

        toolbar = Gtk.Box()
        toolbar.add_css_class("toolbar")
        if icons:
            toolbar.add_css_class("chat-filter-icons")

        self._all_button = Gtk.ToggleButton(active=True)
        if icons:
            self._all_button.set_icon_name("feather-home-symbolic")
            self._all_button.set_tooltip_text(_("All"))
        else:
            self._all_button.set_label(_("All"))

        self._connect(self._all_button, "clicked", self._on_button_clicked, "all")
        toolbar.append(self._all_button)

        chats_button = Gtk.ToggleButton(group=self._all_button)
        if icons:
            chats_button.set_icon_name("feather-user-symbolic")
            chats_button.set_tooltip_text(_("Chats"))
        else:
            chats_button.set_label(_("Chats"))

        self._connect(chats_button, "clicked", self._on_button_clicked, "chats")
        toolbar.append(chats_button)

        group_chats_button = Gtk.ToggleButton(group=self._all_button)
        if icons:
            group_chats_button.set_icon_name("feather-users-symbolic")
            group_chats_button.set_tooltip_text(_("Group Chats"))
        else:
            group_chats_button.set_label(_("Group Chats"))

        self._connect(
            group_chats_button, "clicked", self._on_button_clicked, "group_chats"
        )
        toolbar.append(group_chats_button)

        self.append(toolbar)

    def do_unroot(self) -> None:
        Gtk.Box.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self)

    def _on_button_clicked(self, button: Gtk.ToggleButton, filter_name: str) -> None:
        if button.get_active():
            self.emit("filter-changed", filter_name)

    def reset(self) -> None:
        self._all_button.set_active(True)
        self.emit("filter-changed", "all")
