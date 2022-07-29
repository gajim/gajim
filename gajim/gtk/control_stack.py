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

from typing import Any
from typing import Optional
from typing import Generator

import logging

from gi.repository import Gtk

from nbxmpp import JID

from .controls.chat import ChatControl
from .controls.groupchat import GroupchatControl
from .controls.private import PrivateChatControl

from .types import ControlT

log = logging.getLogger('gajim.gui.controlstack')


class ControlStack(Gtk.Stack):
    def __init__(self):
        Gtk.Stack.__init__(self)
        self.set_vexpand(True)
        self.set_hexpand(True)

        self.add_named(Gtk.Box(), 'empty')

        self.show_all()
        self._controls: dict[tuple[str, JID], ControlT] = {}
        self._current_control: Optional[ControlT] = None

    def get_control(self, account: str, jid: JID) -> Optional[ControlT]:
        try:
            return self._controls[(account, jid)]
        except KeyError:
            return None

    def get_current_control(self) -> Optional[ControlT]:
        return self._current_control

    def get_controls(self, account: Optional[str]
                     ) -> Generator[ControlT, None, None]:
        if account is None:
            for control in self._controls.values():
                yield control
            return

        for key, control in self._controls.items():
            if key[0] == account:
                yield control

    def add_chat(self, account: str, jid: JID) -> None:
        if self._controls.get((account, jid)) is not None:
            # Control is already in the Stack
            return

        chat_control = ChatControl(account, jid)
        self._controls[(account, jid)] = chat_control
        self.add_named(chat_control.widget, f'{account}:{jid}')
        chat_control.widget.show_all()

    def add_group_chat(self, account: str, jid: JID) -> None:
        if self._controls.get((account, jid)) is not None:
            return

        control = GroupchatControl(account, jid)
        self._controls[(account, jid)] = control
        self.add_named(control.widget, f'{account}:{jid}')
        control.widget.show_all()

    def add_private_chat(self, account: str, jid: JID) -> None:
        control = PrivateChatControl(account, jid)
        self._controls[(account, jid)] = control
        self.add_named(control.widget, f'{account}:{jid}')
        control.widget.show_all()

    def remove_chat(self, account: str, jid: JID) -> None:
        control = self._controls.pop((account, jid))
        self.remove(control.widget)
        control.shutdown()

    def show_chat(self, account: str, jid: JID) -> None:
        new_name = f'{account}:{jid}'
        current_name = self.get_visible_child_name()
        assert current_name is not None

        if current_name == new_name:
            return

        control = self.get_control(account, jid)
        if control is None:
            log.warning('No Control found for %s, %s', account, jid)
            return

        if self._current_control is not None:
            self._current_control.reset_view()

        control.load_messages()
        self._current_control = control

        self.set_visible_child_name(new_name)

    def is_chat_loaded(self, account: str, jid: JID) -> bool:
        control = self.get_control(account, jid)
        if control is None:
            return False
        return control.is_chat_loaded

    def clear(self) -> None:
        self.set_visible_child_name('empty')
        self._current_control = None

    def process_event(self, event: Any) -> None:
        control = self.get_control(event.account, event.jid)
        if control is None:
            return
        control.process_event(event)

    def remove_chats_for_account(self, account: str) -> None:
        for chat_account, jid in list(self._controls.keys()):
            if chat_account != account:
                continue
            self.remove_chat(account, jid)
