# This file is part of Gajim.
#
# SPDX-License-Identifier: GPL-3.0-only

from gi.repository import Gtk
from nbxmpp.protocol import validate_resourcepart

from gajim.common import app
from gajim.common.i18n import _

from gajim.gtk.util.classes import SignalManager
from gajim.gtk.util.misc import get_ui_string


@Gtk.Template(string=get_ui_string("groupchat_nick_chooser.ui"))
class GroupChatNickChooser(Gtk.MenuButton, SignalManager):

    __gtype_name__ = "GroupChatNickChooser"

    _label: Gtk.Label = Gtk.Template.Child()
    _popover: Gtk.Popover = Gtk.Template.Child()
    _entry: Gtk.Entry = Gtk.Template.Child()
    _apply_button: Gtk.Button = Gtk.Template.Child()

    def __init__(self) -> None:
        Gtk.MenuButton.__init__(self)
        SignalManager.__init__(self)

        self._connect(self, "notify::active", self._on_nickname_button_toggled)
        self._connect(self._entry, "changed", self._on_nickname_changed)
        self._connect(self._apply_button, "clicked", self._on_apply_nickname)

    def do_unroot(self) -> None:
        Gtk.MenuButton.do_unroot(self)
        self._disconnect_all()
        app.check_finalize(self)

    def get_text(self) -> str:
        return self._entry.get_text()

    def set_text(self, text: str) -> None:
        self._entry.set_text(text)
        self._label.set_text(text)

    def _on_nickname_button_toggled(
        self, _widget: Gtk.MenuButton, _active: bool
    ) -> None:
        self._entry.grab_focus()

    def _on_nickname_changed(self, entry: Gtk.Entry) -> None:
        try:
            validate_resourcepart(entry.get_text())
            self._apply_button.set_sensitive(True)
            self._apply_button.set_tooltip_text(None)
        except Exception:
            self._apply_button.set_sensitive(False)
            self._apply_button.set_tooltip_text(
                _("Nickname contains invalid characters")
            )

    def _on_apply_nickname(self, _button: Gtk.Button) -> None:
        nickname = self._entry.get_text()
        self._popover.popdown()
        self._label.set_text(nickname)
