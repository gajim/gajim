# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gtk
from nbxmpp.protocol import InvalidJid
from nbxmpp.protocol import validate_resourcepart

from gajim.gtk.builder import get_builder


class NickChooser(Gtk.MenuButton):
    def __init__(self) -> None:
        Gtk.MenuButton.__init__(self)
        self._ui = get_builder('groupchat_nick_chooser.ui')
        self.add(self._ui.button_content)
        self.set_receives_default(False)
        self.set_popover(self._ui.popover)

        self._ui.popover.set_default_widget(
            self._ui.apply_button)
        self.connect('toggled', self._on_nickname_button_toggled)
        self._ui.entry.connect('changed', self._on_nickname_changed)
        self._ui.apply_button.connect('clicked', self._on_apply_nickname)

    def get_text(self) -> str:
        return self._ui.entry.get_text()

    def set_text(self, text: str) -> None:
        self._ui.entry.set_text(text)
        self._ui.label.set_text(text)

    def _on_nickname_button_toggled(self, _widget: Gtk.MenuButton) -> None:
        self._ui.entry.grab_focus()

    def _on_nickname_changed(self, entry: Gtk.Entry) -> None:
        try:
            validate_resourcepart(entry.get_text())
            self._ui.apply_button.set_sensitive(True)
        except InvalidJid:
            self._ui.apply_button.set_sensitive(False)

    def _on_apply_nickname(self, _button: Gtk.Button) -> None:
        nickname = self._ui.entry.get_text()
        self._ui.popover.popdown()
        self._ui.label.set_text(nickname)
