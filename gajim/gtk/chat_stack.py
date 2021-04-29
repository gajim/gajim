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

import logging

from gi.repository import Gtk

from gajim.gui.controls.chat import ChatControl
from gajim.gui.controls.groupchat import GroupchatControl
from gajim.gui.controls.private import PrivateChatControl


log = logging.getLogger('gajim.gui.chatstack')


class ChatStack(Gtk.Stack):
    def __init__(self):
        Gtk.Stack.__init__(self)

        self.set_vexpand(True)
        self.set_hexpand(True)

        self.add_named(Gtk.Box(), 'empty')

        self.show_all()
        self._controls = {}

    def get_control(self, account, jid):
        try:
            return self._controls[(account, jid)]
        except KeyError:
            return None

    def get_controls(self, account=None):
        if account is None:
            for control in self._controls.values():
                yield control
            return

        for key, control in self._controls.items():
            if key[0] == account:
                yield control

    def add_chat(self, account, jid):
        if self._controls.get((account, jid)) is not None:
            # Control is already in the Stack
            return

        chat_control = ChatControl(account, jid)
        self._controls[(account, jid)] = chat_control
        self.add_named(chat_control.widget, f'{account}:{jid}')
        chat_control.widget.show_all()

    def add_group_chat(self, account, jid):
        if self._controls.get((account, jid)) is not None:
            return

        control = GroupchatControl(account, jid)
        self._controls[(account, jid)] = control
        self.add_named(control.widget, f'{account}:{jid}')
        control.widget.show_all()

    def add_private_chat(self, account, jid):
        control = PrivateChatControl(account, jid)
        self._controls[(account, str(jid))] = control
        self.add_named(control.widget, f'{account}:{jid}')
        control.widget.show_all()

    def remove_chat(self, account, jid):
        control = self._controls.pop((account, jid))
        self.remove(control.widget)
        control.shutdown()

    def show_chat(self, account, jid):
        self.set_visible_child_name(f'{account}:{jid}')

    def clear(self):
        self.set_visible_child_name('empty')

    def process_event(self, event):
        control = self.get_control(event.account, event.jid)
        control.process_event(event)

    def remove_chats_for_account(self, account):
        for chat_account, jid in list(self._controls.keys()):
            if chat_account != account:
                continue
            self.remove_chat(account, jid)
