# This file is part of Gajim.
#
# Gajim is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published
# by the Free Software Foundation; version 3 only.
#
# Gajim is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Gajim. If not, see <http://www.gnu.org/licenses/>.

from __future__ import annotations

from gi.repository import GLib
from gi.repository import Gtk

from gajim.common import app
from gajim.common.types import ChatContactT
from gajim.common.modules.contacts import GroupchatContact

from gajim.gui.builder import get_builder


class GroupchatState(Gtk.Box):
    def __init__(self) -> None:
        Gtk.Box.__init__(self)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.END)
        self.set_no_show_all(True)

        self._contact = None

        self._ui = get_builder('groupchat_state.ui')
        self._ui.connect_signals(self)
        self.add(self._ui.groupchat_state)
        self.show_all()
        self.hide()

    def clear(self) -> None:
        if self._contact is not None:
            self._contact.disconnect_all_from_obj(self)

        self._contact = None
        self.hide()

    def switch_contact(self, contact: ChatContactT) -> None:
        self.clear()

        if not isinstance(contact, GroupchatContact):
            return

        self._contact = contact
        self._contact.connect('state-changed', self._on_muc_state_changed)

        self._update_state(contact)

    def _on_muc_state_changed(self,
                              contact: GroupchatContact,
                              _signal_name: str
                              ) -> None:

        self._update_state(contact)

    def _update_state(self, contact: GroupchatContact) -> None:
        if contact.is_joining:
            self._ui.groupchat_state.set_visible_child_name('joining')

        elif contact.is_not_joined:
            self._ui.groupchat_state.set_visible_child_name('not-joined')

        self.set_visible(not contact.is_joined)

    def set_fetching(self) -> None:
        self._ui.groupchat_state.set_visible_child_name('fetching')

    def _on_join_clicked(self, _button: Gtk.Button) -> None:
        assert self._contact is not None
        client = app.get_client(self._contact.account)
        client.get_module('MUC').join(self._contact.jid)

    def _on_abort_clicked(self, _button: Gtk.Button) -> None:
        assert self._contact is not None
        app.window.activate_action(
            'remove-chat',
            GLib.Variant(
                'as', [self._contact.account, str(self._contact.jid)]))
